import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from io import BytesIO

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]

def parse_cookie_string(cookie_string: str) -> list:
    """Parse cookie string into list of cookie dictionaries"""
    cookies = []
    for cookie_part in cookie_string.split(';'):
        cookie_part = cookie_part.strip()
        if '=' in cookie_part:
            name, value = cookie_part.split('=', 1)
            cookies.append({
                'name': name.strip(),
                'value': value.strip(),
                'domain': '.instagram.com',
                'path': '/',
            })
    return cookies

def check_instagram_cookie(cookie_string: str) -> dict:
    """
    Check Instagram cookie validity and return screenshot
    Returns: dict with 'valid' (bool), 'screenshot' (bytes), 'message' (str)
    """
    driver = None
    try:
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument(f'user-agent={USER_AGENTS[0]}')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Go to Instagram
        logger.info("Navigating to Instagram...")
        driver.get('https://www.instagram.com/')
        time.sleep(2)

        # Parse and add cookies
        cookies = parse_cookie_string(cookie_string)
        logger.info(f"Adding {len(cookies)} cookies...")
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.warning(f"Failed to add cookie {cookie['name']}: {e}")

        # Refresh to apply cookies
        driver.refresh()
        time.sleep(3)

        # Check if logged in by looking for specific elements
        try:
            # Wait for page to load
            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )

            # Check if we're logged in (look for home feed or profile elements)
            current_url = driver.current_url
            page_source = driver.page_source.lower()

            is_logged_in = False
            message = "Cookie is invalid - not logged in"

            # Multiple checks for login status
            if '/accounts/login' not in current_url:
                # Check for common logged-in indicators
                if any(indicator in page_source for indicator in [
                    'class="x1iyjqo2',  # Instagram's obfuscated class names
                    'data-testid="user-avatar"',
                    '"viewerId"',
                    'direct/inbox',
                ]):
                    is_logged_in = True
                    message = "Cookie is valid - Successfully logged in!"
                    logger.info("Login successful!")

            # Take screenshot
            screenshot = driver.get_screenshot_as_png()

            return {
                'valid': is_logged_in,
                'screenshot': screenshot,
                'message': message,
                'url': current_url
            }

        except TimeoutException:
            screenshot = driver.get_screenshot_as_png()
            return {
                'valid': False,
                'screenshot': screenshot,
                'message': "Timeout while checking login status",
                'url': driver.current_url
            }

    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
        return {
            'valid': False,
            'screenshot': None,
            'message': f"Browser error: {str(e)[:100]}",
            'url': None
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {
            'valid': False,
            'screenshot': None,
            'message': f"Error: {str(e)[:100]}",
            'url': None
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
