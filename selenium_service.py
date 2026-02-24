from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from config import HEADLESS, MOODLE_LOGIN_URL, MOODLE_MY_URL
import logging

logger = logging.getLogger(__name__)

class SeleniumService:
    def __init__(self):
        self.options = Options()
        if HEADLESS:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')

    def perform_login(self, login, password):
        driver = None
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.options)
            driver.set_page_load_timeout(30)  # timeout for page load
            
            try:
                driver.get(MOODLE_LOGIN_URL)
            except TimeoutException:
                return False, "Timeout: Moodle server is not responding. Please check your connection or try again later."
            except WebDriverException as e:
                if "net::ERR_CONNECTION_TIMED_OUT" in str(e):
                    return False, "Connection timeout: Unable to reach Moodle server. Check your network connection."
                raise

            # login
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, 'username')))

            # log pass
            driver.find_element(By.ID, 'username').send_keys(login)
            driver.find_element(By.ID, 'password').send_keys(password)

            # click login
            login_button = driver.find_element(By.ID, 'loginbtn')
            login_button.click()

            WebDriverWait(driver, 15).until(EC.url_contains('/my'))

            import time
            logger.info("Redirected to /my. Waiting 10 seconds for dashboard data to load...")
            time.sleep(10)
            logger.info("Dashboard wait completed, continuing...")

            if 'login' in driver.current_url:
                return False, "Login failed: Invalid credentials or other error"

            try:
                course_links = driver.find_elements(By.CSS_SELECTOR, '.card.dashboard-card a')
                logger.info(f"Searching for course links with '.card.dashboard-card a': found {len(course_links)} total")
                
                if course_links:
                    logger.info(f"Found {len(course_links)} course links, will visit each one")
                    
                    course_urls = []
                    for link in course_links:
                        try:
                            href = link.get_attribute('href')
                            if href and '/my/#' not in href:  # Ignore /my/# links
                                course_urls.append(href)
                            elif href and '/my/#' in href:
                                logger.debug(f"Skipping /my/# link: {href}")
                        except Exception as e:
                            logger.debug(f"Error collecting URL: {e}")
                    
                    logger.info(f"Collected {len(course_urls)} valid course URLs")
                    
                    visited_any = False
                    max_visits = min(len(course_urls), 50)
                    
                    for idx, course_url in enumerate(course_urls[:max_visits], start=1):
                        try:
                            logger.info(f"Visiting course #{idx}: {course_url}")
                            driver.get(course_url)
                            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                            logger.info(f"✓ Successfully visited course #{idx}")
                            visited_any = True
                        except Exception as nav_e:
                            logger.warning(f"Failed to visit course link {course_url}: {nav_e}")
                        finally:
                            try:
                                logger.debug(f"Returning to /my/...")
                                driver.get(MOODLE_MY_URL)
                                WebDriverWait(driver, 5).until(EC.url_contains('/my'))
                                import time
                                time.sleep(2)
                            except Exception as e:
                                logger.warning(f"Error returning to /my/: {e}")
                    
                    if not visited_any:
                        logger.warning("No course links were successfully visited; trying fallback")
                        links = driver.find_elements(By.CSS_SELECTOR, '[data-course-id] a')
                        logger.info(f"Fallback: searching for [data-course-id] a: found {len(links)}")
                        if links:
                            course_url = links[0].get_attribute('href')
                            driver.get(course_url)
                            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                            driver.get(MOODLE_MY_URL)
                            WebDriverWait(driver, 5).until(EC.url_contains('/my'))
                else:
                    logger.info("No '.card.dashboard-card a' found; trying fallback selectors")
                    
                    try:
                        page_source = driver.page_source
                        if 'dashboard-card' in page_source:
                            logger.info("✓ Page contains 'dashboard-card' text BUT selector didn't find it - might be in iframe/shadow DOM")
                        else:
                            logger.warning("✗ Page does NOT contain 'dashboard-card' - course cards may not have loaded")
                        
                        all_course_divs = driver.find_elements(By.CSS_SELECTOR, '[data-course-id]')
                        logger.info(f"Elements with [data-course-id] attribute found: {len(all_course_divs)}")
                        
                        if all_course_divs:
                            first_div = all_course_divs[0]
                            logger.info(f"First [data-course-id] element outer HTML (first 500 chars):")
                            outer_html = first_div.get_attribute('outerHTML')
                            logger.info(outer_html[:500] if outer_html else "No outer HTML")
                            
                            parent = first_div.find_element(By.XPATH, '..')
                            parent_html = parent.get_attribute('outerHTML')
                            logger.info(f"Parent element outer HTML (first 300 chars):")
                            logger.info(parent_html[:300] if parent_html else "No parent HTML")
                        
                        if not all_course_divs:
                            with open('moodle_page_debug.html', 'w', encoding='utf-8') as f:
                                f.write(page_source)
                            driver.save_screenshot('moodle_page_debug.png')
                            logger.warning("Saved debug files: moodle_page_debug.html, moodle_page_debug.png")
                    except Exception as debug_e:
                        logger.warning(f"Debug logging error: {debug_e}")
                    
                    links = driver.find_elements(By.CSS_SELECTOR, '[data-course-id] a')
                    logger.info(f"Fallback: searching for [data-course-id] a: found {len(links)}")
                    if links:
                        course_url = links[0].get_attribute('href')
                        driver.get(course_url)
                        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, 'body')))
                        driver.get(MOODLE_MY_URL)
                        WebDriverWait(driver, 5).until(EC.url_contains('/my'))
                    else:
                        logger.warning("No course link found in any fallback path; skipping course navigation")
            except Exception as e:
                logger.error(f"Error navigating to course: {e}")

            return True, "Login successful"

        except TimeoutException:
            return False, "Timeout during login process"
        except NoSuchElementException as e:
            return False, f"Element not found: {e}"
        except WebDriverException as e:
            error_msg = str(e)
            if "net::ERR_CONNECTION_TIMED_OUT" in error_msg:
                return False, "Connection timeout: Unable to reach Moodle server. Check your network."
            return False, f"WebDriver error: {e}"
        except Exception as e:
            return False, f"Unexpected error: {e}"
        finally:
            if driver:
                driver.quit()