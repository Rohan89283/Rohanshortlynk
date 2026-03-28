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
from typing import Optional, Dict

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
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

def check_instagram_cookie(cookie_string: str, user_id: Optional[int] = None, proxy_info: Optional[Dict] = None, update_callback=None) -> dict:
    """
    Check Instagram cookie validity and return screenshot

    Args:
        cookie_string: Instagram cookies string
        user_id: Telegram user ID (for proxy rotation)
        proxy_info: Optional proxy dict (if None, will fetch from database)
        update_callback: Optional callback function for status updates

    Returns: dict with 'valid' (bool), 'screenshot' (bytes), 'message' (str), 'proxy_used' (str)
    """
    driver = None
    proxy_manager = None
    active_proxy = None

    try:
        # Get proxy if user_id provided and no proxy_info
        if user_id and not proxy_info:
            try:
                from proxy_manager import ProxyManager
                proxy_manager = ProxyManager()
                active_proxy = proxy_manager.get_next_proxy(user_id)
                if active_proxy:
                    proxy_info = active_proxy
                    logger.info(f"Using proxy: {proxy_info['host']}:{proxy_info['port']}")
            except Exception as e:
                logger.warning(f"Failed to get proxy: {e}")

        # Setup Chrome options with anti-detection
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')

        # Use random user agent
        import random
        user_agent = random.choice(USER_AGENTS)
        chrome_options.add_argument(f'user-agent={user_agent}')

        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-software-rasterizer')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-setuid-sandbox')
        chrome_options.add_argument('--remote-debugging-port=9222')

        # Additional anti-detection measures
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=IsolateOrigins,site-per-process')
        chrome_options.add_argument('--allow-running-insecure-content')
        chrome_options.add_argument('--lang=en-US,en;q=0.9')
        chrome_options.add_argument('--disable-infobars')

        chrome_options.add_experimental_option('excludeSwitches', ['enable-automation', 'enable-logging'])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        # Set preferences to avoid detection
        prefs = {
            'credentials_enable_service': False,
            'profile.password_manager_enabled': False,
            'profile.default_content_setting_values.notifications': 2,
            'webrtc.ip_handling_policy': 'disable_non_proxied_udp',
            'webrtc.multiple_routes_enabled': False,
            'webrtc.nonproxied_udp_enabled': False,
            'intl.accept_languages': 'en-US,en'
        }
        chrome_options.add_experimental_option('prefs', prefs)

        # Add binary location
        chrome_options.binary_location = '/usr/bin/google-chrome'

        # Add proxy if available
        if proxy_info:
            # Check if proxy has authentication
            if proxy_info.get('username') and proxy_info.get('password'):
                # Use Chrome extension for authenticated proxy
                from proxy_auth import create_proxy_auth_extension
                plugin_file = create_proxy_auth_extension(proxy_info)
                chrome_options.add_extension(plugin_file)
                logger.info(f"Chrome configured with authenticated proxy: {proxy_info['host']}:{proxy_info['port']}")
            else:
                # Use simple proxy without auth
                proxy_url = f"{proxy_info['host']}:{proxy_info['port']}"
                chrome_options.add_argument(f'--proxy-server={proxy_url}')
                logger.info(f"Chrome configured with proxy: {proxy_url}")

        # Initialize driver
        logger.info("Initializing Chrome WebDriver...")
        try:
            driver = webdriver.Chrome(options=chrome_options)
        except Exception as e:
            logger.error(f"Failed to initialize Chrome: {e}")
            return {
                'valid': False,
                'screenshot': None,
                'message': f"Chrome initialization failed: {str(e)[:100]}",
                'url': None,
                'proxy_used': f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"
            }

        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Go to Instagram
        logger.info("Navigating to Instagram...")
        driver.get('https://www.instagram.com/')
        time.sleep(1)

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
        time.sleep(2)

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
            username = "N/A"
            total_posts = "N/A"
            location = "N/A"

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

                    # Try to extract username from page
                    try:
                        import re
                        import json

                        # Look for username in script tags
                        username_match = re.search(r'"username":"([^"]+)"', driver.page_source)
                        if username_match:
                            username = username_match.group(1)
                            logger.info(f"Found username: {username}")
                    except Exception as e:
                        logger.warning(f"Failed to extract username: {e}")

            # Try to get location from proxy
            if proxy_info:
                try:
                    location = f"{proxy_info['host']}"
                except:
                    location = "Proxy"
            else:
                location = "Direct Connection"

            # Take screenshot for Step 1
            screenshot_step1 = driver.get_screenshot_as_png()

            # Update proxy success
            if proxy_manager and active_proxy:
                proxy_manager.update_proxy_usage(active_proxy['id'], True)

            proxy_used = f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"

            result = {
                'valid': is_logged_in,
                'screenshot': screenshot_step1,
                'screenshot_step2': None,
                'screenshot_step3': None,
                'message': message,
                'url': current_url,
                'proxy_used': proxy_used,
                'username': username,
                'total_posts': total_posts,
                'location': location,
                'step1_complete': is_logged_in,
                'step2_complete': False,
                'step3_complete': False
            }

            # If login successful, proceed to Step 2 - Facebook Business Manager
            if is_logged_in:
                try:
                    logger.info("Step 1 completed. Starting Step 2 - Facebook Business Manager...")

                    # Navigate to Facebook Business Manager with English locale
                    logger.info("Navigating to Facebook Business Manager...")
                    driver.get('https://business.facebook.com/latest/home?locale=en_US')

                    # Wait for page to fully load (reduced wait time)
                    time.sleep(3)

                    # Inject anti-detection scripts and force English language
                    driver.execute_script("""
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                        Object.defineProperty(navigator, 'language', {get: () => 'en-US'});

                        // Force locale to English
                        if (window.localStorage) {
                            window.localStorage.setItem('locale', 'en_US');
                            window.localStorage.setItem('_js_datr', 'en_US');
                        }
                    """)

                    # Try to click "Log in with Instagram" button
                    try:
                        # Wait for the login page to appear
                        WebDriverWait(driver, 10).until(
                            lambda d: d.execute_script('return document.readyState') == 'complete'
                        )

                        # Look for Instagram login button - try multiple selectors
                        instagram_login_clicked = False

                        # Method 1: Try finding by text in all clickable elements
                        try:
                            all_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Instagram') or contains(text(), 'instagram')]")
                            for element in all_elements:
                                if 'log in' in element.text.lower() or 'login' in element.text.lower():
                                    # Scroll to element
                                    driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                    time.sleep(0.5)
                                    # Click using JavaScript
                                    driver.execute_script("arguments[0].click();", element)
                                    instagram_login_clicked = True
                                    logger.info(f"Clicked Instagram login using XPath: {element.text}")
                                    break
                        except Exception as e:
                            logger.warning(f"Method 1 failed: {e}")

                        # Method 2: Try finding button elements
                        if not instagram_login_clicked:
                            try:
                                buttons = driver.find_elements(By.TAG_NAME, 'button')
                                for button in buttons:
                                    if 'instagram' in button.text.lower():
                                        driver.execute_script("arguments[0].scrollIntoView(true);", button)
                                        time.sleep(0.5)
                                        driver.execute_script("arguments[0].click();", button)
                                        instagram_login_clicked = True
                                        logger.info(f"Clicked Instagram login button: {button.text}")
                                        break
                            except Exception as e:
                                logger.warning(f"Method 2 failed: {e}")

                        # Method 3: Try finding by div/span with Instagram text
                        if not instagram_login_clicked:
                            try:
                                clickable_elements = driver.find_elements(By.CSS_SELECTOR, "div[role='button'], span[role='button'], div[tabindex='0']")
                                for element in clickable_elements:
                                    if 'instagram' in element.text.lower():
                                        driver.execute_script("arguments[0].scrollIntoView(true);", element)
                                        time.sleep(0.5)
                                        driver.execute_script("arguments[0].click();", element)
                                        instagram_login_clicked = True
                                        logger.info(f"Clicked Instagram login element: {element.text}")
                                        break
                            except Exception as e:
                                logger.warning(f"Method 3 failed: {e}")

                        # If clicked, wait for redirect and page load
                        if instagram_login_clicked:
                            logger.info("Instagram login button clicked! Waiting for page to load...")
                            time.sleep(5)  # Reduced wait time

                            # Wait for page to be fully loaded
                            WebDriverWait(driver, 10).until(
                                lambda d: d.execute_script('return document.readyState') == 'complete'
                            )

                            # Additional wait for dynamic content
                            time.sleep(2)

                            logger.info(f"Current URL after click: {driver.current_url}")
                        else:
                            logger.warning("Instagram login button not found, taking screenshot of current page")

                    except Exception as e:
                        logger.warning(f"Failed to click Instagram login: {e}")

                    # Take screenshot for Step 2
                    screenshot_step2 = driver.get_screenshot_as_png()

                    result['screenshot_step2'] = screenshot_step2
                    result['step2_complete'] = True

                    logger.info("Step 2 completed - Screenshot captured")

                    # Step 3: Navigate to Facebook Ad Center
                    try:
                        logger.info("Starting Step 3 - Facebook Ad Center...")

                        # Navigate to Facebook Ad Center with English locale
                        logger.info("Navigating to Facebook Ad Center...")
                        driver.get('https://business.facebook.com/latest/ad_center/ads_summary?locale=en_US')

                        # Wait for page to fully load
                        time.sleep(8)

                        # Force English language again
                        driver.execute_script("""
                            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                            Object.defineProperty(navigator, 'language', {get: () => 'en-US'});

                            if (window.localStorage) {
                                window.localStorage.setItem('locale', 'en_US');
                            }
                        """)

                        # Wait for page to be fully loaded
                        WebDriverWait(driver, 15).until(
                            lambda d: d.execute_script('return document.readyState') == 'complete'
                        )

                        # Additional wait for dynamic content
                        time.sleep(3)

                        logger.info(f"Current URL at Step 3: {driver.current_url}")

                        # Take screenshot for Step 3
                        screenshot_step3 = driver.get_screenshot_as_png()

                        result['screenshot_step3'] = screenshot_step3
                        result['step3_complete'] = True

                        logger.info("Step 3 completed - Screenshot captured")

                    except Exception as e:
                        logger.warning(f"Step 3 failed: {e}")
                        result['step3_complete'] = False

                except Exception as e:
                    logger.warning(f"Step 2 failed: {e}")
                    result['step2_complete'] = False
                    result['step3_complete'] = False

            return result

        except TimeoutException:
            screenshot = driver.get_screenshot_as_png()
            if proxy_manager and active_proxy:
                proxy_manager.update_proxy_usage(active_proxy['id'], False)

            proxy_used = f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"
            location = f"{proxy_info['host']}" if proxy_info else "Direct Connection"

            return {
                'valid': False,
                'screenshot': screenshot,
                'screenshot_step2': None,
                'screenshot_step3': None,
                'message': "Timeout while checking login status",
                'url': driver.current_url,
                'proxy_used': proxy_used,
                'username': 'N/A',
                'total_posts': 'N/A',
                'location': location,
                'step1_complete': False,
                'step2_complete': False,
                'step3_complete': False
            }

    except WebDriverException as e:
        logger.error(f"WebDriver error: {e}")
        if proxy_manager and active_proxy:
            proxy_manager.update_proxy_usage(active_proxy['id'], False)

        proxy_used = f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"
        location = f"{proxy_info['host']}" if proxy_info else "Direct Connection"

        return {
            'valid': False,
            'screenshot': None,
            'screenshot_step2': None,
            'screenshot_step3': None,
            'message': f"Browser error: {str(e)[:100]}",
            'url': None,
            'proxy_used': proxy_used,
            'username': 'N/A',
            'total_posts': 'N/A',
            'location': location,
            'step1_complete': False,
            'step2_complete': False,
            'step3_complete': False
        }
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if proxy_manager and active_proxy:
            proxy_manager.update_proxy_usage(active_proxy['id'], False)

        proxy_used = f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"
        location = f"{proxy_info['host']}" if proxy_info else "Direct Connection"

        return {
            'valid': False,
            'screenshot': None,
            'screenshot_step2': None,
            'screenshot_step3': None,
            'message': f"Error: {str(e)[:100]}",
            'url': None,
            'proxy_used': proxy_used,
            'username': 'N/A',
            'total_posts': 'N/A',
            'location': location,
            'step1_complete': False,
            'step2_complete': False,
            'step3_complete': False
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
