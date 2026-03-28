import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)

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

async def check_instagram_cookie(cookie_string: str, user_id=None, proxy_info=None, update_callback=None):
    """
    Simple Instagram cookie checker - Step 1 only

    Returns: dict with 'valid', 'screenshot', 'message', 'username'
    """
    driver = None

    try:
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--lang=en-US')
        chrome_options.binary_location = '/usr/bin/google-chrome'

        driver = webdriver.Chrome(options=chrome_options)

        if update_callback:
            await update_callback(1, "Loading Instagram...")

        driver.get('https://www.instagram.com/')

        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        cookies = parse_cookie_string(cookie_string)
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except:
                pass

        if update_callback:
            await update_callback(1, "Checking login status...")

        driver.refresh()

        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        current_url = driver.current_url
        page_source = driver.page_source.lower()

        is_logged_in = '/accounts/login' not in current_url

        username = "N/A"
        if is_logged_in:
            import re
            username_match = re.search(r'"username":"([^"]+)"', driver.page_source)
            if username_match:
                username = username_match.group(1)

        screenshot = driver.get_screenshot_as_png()

        return {
            'valid': is_logged_in,
            'screenshot': screenshot,
            'message': "Valid cookie - Logged in!" if is_logged_in else "Invalid cookie",
            'username': username,
            'url': current_url,
            'step1_complete': is_logged_in
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            'valid': False,
            'screenshot': None,
            'message': f"Error: {str(e)[:100]}",
            'username': 'N/A',
            'url': None,
            'step1_complete': False
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
