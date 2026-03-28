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

async def check_instagram_cookie(cookie_string: str, user_id: Optional[int] = None, proxy_info: Optional[Dict] = None, update_callback=None) -> dict:
    """
    Check Instagram cookie validity and return screenshot

    Args:
        cookie_string: Instagram cookies string
        user_id: Telegram user ID (for proxy rotation)
        proxy_info: Optional proxy dict (if None, will fetch from database)
        update_callback: Optional async callback function for status updates (step, message)

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

        # Use eager page load strategy for faster loading
        chrome_options.page_load_strategy = 'eager'

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
                'proxy_used': f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct",
                'step1_complete': False
            }

        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # Go to Instagram
        logger.info("Navigating to Instagram...")
        if update_callback:
            await update_callback(1, "Loading Instagram...")
        driver.get('https://www.instagram.com/')

        # Wait for initial page load
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        # Parse and add cookies
        cookies = parse_cookie_string(cookie_string)
        logger.info(f"Adding {len(cookies)} cookies...")
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.warning(f"Failed to add cookie {cookie['name']}: {e}")

        # Refresh to apply cookies
        if update_callback:
            await update_callback(1, "Applying cookies...")
        driver.refresh()

        # Wait for page to reload with cookies
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script('return document.readyState') == 'complete'
        )

        # Check if logged in by looking for specific elements
        try:
            # Wait for page to load (reduced timeout)
            WebDriverWait(driver, 6).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )

            # Check if we're logged in (look for home feed or profile elements)
            if update_callback:
                await update_callback(1, "Verifying login status...")
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
            logger.info("Step 1 screenshot captured")

            # Update proxy success
            if proxy_manager and active_proxy:
                proxy_manager.update_proxy_usage(active_proxy['id'], True)

            proxy_used = f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"

            result = {
                'valid': is_logged_in,
                'screenshot': screenshot_step1,
                'message': message,
                'url': current_url,
                'proxy_used': proxy_used,
                'username': username,
                'total_posts': total_posts,
                'location': location,
                'step1_complete': is_logged_in
            }

            # Login check complete
            if is_logged_in:
                logger.info("=" * 80)
                logger.info("STEP 1: COMPLETED - Instagram login successful!")
                logger.info("=" * 80)

                # STEP 2: Navigate to Meta Business Suite and click Instagram login
                try:
                    if update_callback:
                        await update_callback(2, "Navigating to Meta Business Suite...")

                    logger.info("STEP 2: Navigating to Meta Business Suite...")

                    # Store initial window handle
                    original_window = driver.current_window_handle
                    logger.info(f"Original window handle: {original_window}")

                    # Navigate to Meta Business Suite login page
                    meta_business_url = "https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs"
                    driver.get(meta_business_url)

                    # Wait for page to load
                    WebDriverWait(driver, 10).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                    time.sleep(3)

                    if update_callback:
                        await update_callback(2, "Looking for 'Log in with Instagram' button...")

                    # Try to find and click "Log in with Instagram" button
                    logger.info("Searching for 'Log in with Instagram' button...")

                    instagram_login_clicked = False
                    try:
                        # Try multiple selectors for the Instagram login button
                        possible_selectors = [
                            "//span[contains(text(), 'Log in with Instagram')]",
                            "//div[contains(text(), 'Log in with Instagram')]",
                            "//button[contains(., 'Log in with Instagram')]",
                            "//a[contains(., 'Log in with Instagram')]",
                        ]

                        for selector in possible_selectors:
                            try:
                                instagram_button = WebDriverWait(driver, 5).until(
                                    EC.element_to_be_clickable((By.XPATH, selector))
                                )
                                logger.info(f"Found Instagram login button using selector: {selector}")

                                # Get count of windows before click
                                windows_before = len(driver.window_handles)
                                logger.info(f"Windows before click: {windows_before}")

                                # Click the button
                                instagram_button.click()
                                instagram_login_clicked = True
                                logger.info("Clicked 'Log in with Instagram' button")
                                break
                            except:
                                continue

                        if not instagram_login_clicked:
                            logger.warning("Could not find 'Log in with Instagram' button")

                    except Exception as e:
                        logger.warning(f"Failed to click Instagram login button: {e}")

                    # Wait a moment for any popups/tabs to open
                    time.sleep(3)

                    if update_callback:
                        await update_callback(2, "Checking for new tabs/popups...")

                    # Check for new windows/tabs
                    windows_after = driver.window_handles
                    logger.info(f"Windows after click: {len(windows_after)}")

                    new_tab_info = {
                        'new_tab_opened': len(windows_after) > len([original_window]),
                        'total_windows': len(windows_after),
                        'window_handles': windows_after
                    }

                    # Capture current URL and page info
                    current_url = driver.current_url
                    logger.info(f"Current URL after click: {current_url}")

                    # Take screenshot after click (main window)
                    screenshot_step2_main = driver.get_screenshot_as_png()
                    logger.info("Step 2 main window screenshot captured")

                    screenshot_step2_popup = None
                    screenshot_step2_after_login = None
                    popup_url = None
                    popup_url_after_login = None
                    main_url_after_login = None
                    login_button_clicked = False

                    # If new window/tab opened, switch to it and capture
                    if len(windows_after) > 1:
                        logger.info("New tab/popup detected!")
                        for window_handle in windows_after:
                            if window_handle != original_window:
                                driver.switch_to.window(window_handle)
                                popup_url = driver.current_url
                                logger.info(f"Switched to new window. URL: {popup_url}")
                                time.sleep(2)
                                screenshot_step2_popup = driver.get_screenshot_as_png()
                                logger.info("Step 2 popup screenshot captured")

                                # Now try to click "Log in as" button in the popup
                                if update_callback:
                                    await update_callback(2, "Clicking 'Log in as' button...")

                                logger.info("Searching for 'Log in as' button in popup...")
                                try:
                                    # Try multiple selectors for the "Log in as" button
                                    login_as_selectors = [
                                        "//button[contains(., 'Log in as')]",
                                        "//span[contains(text(), 'Log in as')]",
                                        "//div[contains(text(), 'Log in as')]",
                                        "//*[contains(text(), 'Log in as')]",
                                    ]

                                    for selector in login_as_selectors:
                                        try:
                                            login_as_button = WebDriverWait(driver, 5).until(
                                                EC.element_to_be_clickable((By.XPATH, selector))
                                            )
                                            logger.info(f"Found 'Log in as' button using selector: {selector}")
                                            login_as_button.click()
                                            login_button_clicked = True
                                            logger.info("Clicked 'Log in as' button")
                                            break
                                        except:
                                            continue

                                    if not login_button_clicked:
                                        logger.warning("Could not find 'Log in as' button")

                                except Exception as e:
                                    logger.warning(f"Failed to click 'Log in as' button: {e}")

                                # Wait for page to load after clicking
                                if login_button_clicked:
                                    time.sleep(4)
                                    popup_url_after_login = driver.current_url
                                    logger.info(f"Popup URL after login: {popup_url_after_login}")
                                    screenshot_step2_after_login = driver.get_screenshot_as_png()
                                    logger.info("Popup screenshot after login captured")

                                # Switch back to original window
                                driver.switch_to.window(original_window)

                                # Check main window URL after login
                                time.sleep(2)
                                main_url_after_login = driver.current_url
                                logger.info(f"Main window URL after login: {main_url_after_login}")
                                break

                    logger.info("=" * 80)
                    logger.info("STEP 2: COMPLETED - Meta Business Suite check done!")
                    logger.info("=" * 80)

                    # Update result with step 2 data
                    result['screenshot_step2'] = screenshot_step2_main
                    result['screenshot_step2_popup'] = screenshot_step2_popup
                    result['screenshot_step2_after_login'] = screenshot_step2_after_login
                    result['step2_complete'] = True
                    result['step2_instagram_clicked'] = instagram_login_clicked
                    result['step2_login_button_clicked'] = login_button_clicked
                    result['step2_current_url'] = current_url
                    result['step2_popup_url'] = popup_url
                    result['step2_popup_url_after_login'] = popup_url_after_login
                    result['step2_main_url_after_login'] = main_url_after_login
                    result['step2_new_tab_info'] = new_tab_info

                except Exception as e:
                    logger.error(f"Step 2 failed: {e}")

                    # Capture screenshot even on failure
                    try:
                        screenshot_step2_error = driver.get_screenshot_as_png()
                        error_url = driver.current_url
                        logger.info(f"Step 2 error screenshot captured. URL: {error_url}")
                    except:
                        screenshot_step2_error = None
                        error_url = "N/A"

                    result['step2_complete'] = False
                    result['screenshot_step2'] = screenshot_step2_error
                    result['step2_current_url'] = error_url
                    result['step2_instagram_clicked'] = False
                    result['step2_login_button_clicked'] = False
                    result['step2_popup_url'] = None
                    result['step2_popup_url_after_login'] = None
                    result['step2_main_url_after_login'] = None
                    result['step2_new_tab_info'] = {'new_tab_opened': False, 'total_windows': 1}

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
                'message': "Timeout while checking login status",
                'url': driver.current_url,
                'proxy_used': proxy_used,
                'username': 'N/A',
                'total_posts': 'N/A',
                'location': location,
                'step1_complete': False
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
            'message': f"Browser error: {str(e)[:100]}",
            'url': None,
            'proxy_used': proxy_used,
            'username': 'N/A',
            'total_posts': 'N/A',
            'location': location,
            'step1_complete': False
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
            'message': f"Error: {str(e)[:100]}",
            'url': None,
            'proxy_used': proxy_used,
            'username': 'N/A',
            'total_posts': 'N/A',
            'location': location,
            'step1_complete': False
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
