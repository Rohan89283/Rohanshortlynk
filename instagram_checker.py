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

        # Force English language
        chrome_options.add_argument('--lang=en-US')
        chrome_options.add_experimental_option('prefs', {
            'intl.accept_languages': 'en-US,en',
            'intl.selected_languages': 'en-US,en'
        })

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

        # Set locale to English for Facebook/Meta pages
        logger.info("Setting locale preferences to English...")
        driver.get('https://www.facebook.com/')
        time.sleep(1)

        # Set Facebook locale cookie to English
        try:
            driver.add_cookie({
                'name': 'locale',
                'value': 'en_US',
                'domain': '.facebook.com',
                'path': '/'
            })
            logger.info("✓ Facebook locale cookie set to en_US")
        except Exception as e:
            logger.warning(f"Could not set Facebook locale cookie: {e}")

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

            # Update proxy success
            if proxy_manager and active_proxy:
                proxy_manager.update_proxy_usage(active_proxy['id'], True)

            proxy_used = f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"

            result = {
                'valid': is_logged_in,
                'screenshot': None,  # Will capture at end of Step 1
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
                # Take screenshot at END of Step 1
                screenshot_step1 = driver.get_screenshot_as_png()
                result['screenshot'] = screenshot_step1
                logger.info("✓ Step 1 screenshot captured (Instagram logged in)")

                logger.info("=" * 80)
                logger.info("STEP 1: COMPLETED - Instagram login successful!")
                logger.info("=" * 80)

                # STEP 2: Navigate to Meta Business Suite and handle popup/direct flow
                try:
                    logger.info("=" * 80)
                    logger.info("STARTING STEP 2: Meta Business Suite Navigation")
                    logger.info("=" * 80)

                    if update_callback:
                        await update_callback(2, "Navigating to Meta Business Suite...")

                    # Store initial window handle
                    logger.info("Getting current window handle...")
                    original_window = driver.current_window_handle
                    logger.info(f"✓ Original window handle: {original_window}")

                    # Navigate to Meta Business Suite login page with locale parameter
                    meta_business_url = "https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs&locale=en_US"
                    logger.info(f"Navigating to: {meta_business_url[:100]}...")
                    driver.get(meta_business_url)
                    logger.info("✓ Navigation initiated")

                    # Set locale cookie for Facebook Business
                    try:
                        driver.add_cookie({
                            'name': 'locale',
                            'value': 'en_US',
                            'domain': '.facebook.com',
                            'path': '/'
                        })
                        logger.info("✓ Facebook locale cookie refreshed to en_US")
                    except Exception as e:
                        logger.warning(f"Could not refresh locale cookie: {e}")

                    # Wait for page to load
                    logger.info("Waiting for page to load completely...")
                    WebDriverWait(driver, 10).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )
                    logger.info("✓ Page loaded")
                    time.sleep(3)
                    logger.info("✓ Additional wait complete")

                    # Log current URL
                    current_page_url = driver.current_url
                    logger.info(f"Current URL: {current_page_url}")

                    # Check if we're already on business home page (URL check)
                    is_on_business_home = 'business.facebook.com/latest' in current_page_url or 'business.facebook.com/?nav' in current_page_url

                    if is_on_business_home:
                        logger.info("✓ Already on Business home page - no popup/login needed!")
                        if update_callback:
                            await update_callback(2, "Already on Business home page!")

                        # Set all step 2 variables for direct flow
                        popup_url = None
                        popup_url_after_login = None
                        main_url_after_login = current_page_url
                        login_button_clicked = False
                        instagram_login_clicked = False
                        new_tab_info = {
                            'new_tab_opened': False,
                            'total_windows': 1,
                            'window_handles': [original_window],
                            'flow_type': 'direct_to_home'
                        }
                    else:
                        # Not on business home yet - need to click Instagram login
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
                            await update_callback(2, "Checking for popup/new tab...")

                        # Check for new windows/tabs
                        windows_after = driver.window_handles
                        logger.info(f"Windows after click: {len(windows_after)}")

                        # Capture current URL and page info
                        current_url = driver.current_url
                        logger.info(f"Current URL after click: {current_url}")

                        popup_url = None
                        popup_url_after_login = None
                        main_url_after_login = None
                        login_button_clicked = False

                        # Check if popup/new tab opened
                        if len(windows_after) > 1:
                            logger.info("✓ New tab/popup detected!")
                            new_tab_info = {
                                'new_tab_opened': True,
                                'total_windows': len(windows_after),
                                'window_handles': windows_after,
                                'flow_type': 'popup_flow'
                            }

                            for window_handle in windows_after:
                                if window_handle != original_window:
                                    try:
                                        driver.switch_to.window(window_handle)
                                        popup_url = driver.current_url
                                        logger.info(f"Switched to popup window. URL: {popup_url}")

                                        # Check if popup is a callback URL (auto-closes)
                                        if '/callback/' in popup_url or '/idtoken/' in popup_url:
                                            logger.info("✓ Popup is auto-login callback - will close automatically")
                                            if update_callback:
                                                await update_callback(2, "Auto-login popup detected, waiting for redirect...")

                                            # Wait for auto-close
                                            time.sleep(3)
                                        else:
                                            # Try to click "Log in as username" button
                                            if update_callback:
                                                await update_callback(2, "Looking for 'Log in as' button...")

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
                                                        login_as_button = WebDriverWait(driver, 3).until(
                                                            EC.element_to_be_clickable((By.XPATH, selector))
                                                        )
                                                        logger.info(f"Found 'Log in as' button using selector: {selector}")
                                                        login_as_button.click()
                                                        login_button_clicked = True
                                                        logger.info("✓ Clicked 'Log in as' button")
                                                        time.sleep(3)
                                                        break
                                                    except:
                                                        continue

                                                if not login_button_clicked:
                                                    logger.info("No 'Log in as' button found - may auto-redirect")

                                            except Exception as e:
                                                logger.info(f"No login button needed: {e}")

                                    except Exception as popup_error:
                                        logger.info(f"Popup handling completed or closed: {popup_error}")

                                    # Switch back to original window
                                    try:
                                        driver.switch_to.window(original_window)
                                        logger.info("✓ Switched back to main window")
                                    except:
                                        # If original window doesn't exist, use first available
                                        available_windows = driver.window_handles
                                        if available_windows:
                                            driver.switch_to.window(available_windows[0])
                                            logger.info("✓ Switched to available window")

                                    # Wait for redirect to complete
                                    time.sleep(3)
                                    main_url_after_login = driver.current_url
                                    logger.info(f"Main window URL after popup: {main_url_after_login}")
                                    break
                        else:
                            # No popup - check if we're already on business home
                            logger.info("✓ No popup detected - checking if on Business home page...")
                            new_tab_info = {
                                'new_tab_opened': False,
                                'total_windows': 1,
                                'window_handles': windows_after,
                                'flow_type': 'direct_no_popup'
                            }

                            # Wait a bit for any redirect
                            time.sleep(3)
                            main_url_after_login = driver.current_url
                            logger.info(f"Current URL (no popup): {main_url_after_login}")

                            # Check if we're on business home
                            if 'business.facebook.com/latest' in main_url_after_login or 'business.facebook.com/?nav' in main_url_after_login:
                                logger.info("✓ Already on Business home page!")

                    # Final check: Verify we're on business home page
                    final_url = driver.current_url
                    logger.info(f"Final URL: {final_url}")

                    # Check if we successfully reached business home
                    on_business_home = (
                        'business.facebook.com/latest' in final_url or
                        'business.facebook.com/?nav' in final_url or
                        'business.facebook.com/home' in final_url
                    )

                    if on_business_home:
                        logger.info("✅ Successfully reached Business Suite home page!")
                        if update_callback:
                            await update_callback(2, "✅ On Business Suite home page!")
                    else:
                        logger.info(f"⚠️ Not yet on Business home page. Current: {final_url}")

                    # Take screenshot at END of Step 2 (final destination)
                    screenshot_step2 = driver.get_screenshot_as_png()
                    logger.info("✓ Step 2 screenshot captured (Business Suite final page)")

                    logger.info("=" * 80)
                    logger.info("STEP 2: COMPLETED - Meta Business Suite check done!")
                    logger.info(f"Flow type: {new_tab_info.get('flow_type', 'unknown')}")
                    logger.info(f"On Business Home: {on_business_home}")
                    logger.info("=" * 80)

                    # Update result with step 2 data
                    result['screenshot_step2'] = screenshot_step2
                    result['step2_complete'] = True
                    result['step2_instagram_clicked'] = instagram_login_clicked
                    result['step2_login_button_clicked'] = login_button_clicked
                    result['step2_current_url'] = final_url
                    result['step2_popup_url'] = popup_url
                    result['step2_new_tab_info'] = new_tab_info
                    result['step2_on_business_home'] = on_business_home

                    # STEP 3: Click "Create ad" -> Continue -> Continue -> Continue as
                    logger.info("=" * 80)
                    logger.info("STARTING STEP 3: Create Ad Flow")
                    logger.info("=" * 80)

                    try:
                        # Stay on business home page - no URL change needed
                        current_url = driver.current_url
                        logger.info(f"Current page (Business Home): {current_url}")

                        # Wait for page to be ready
                        time.sleep(2)

                        screenshot_after_create_ad = None
                        screenshot_after_continue_1 = None
                        screenshot_after_continue_2 = None
                        screenshot_after_continue_as = None

                        create_ad_clicked = False
                        continue_1_clicked = False
                        continue_2_clicked = False
                        continue_as_clicked = False
                        popup_opened = False

                        # STEP 3.1: Click "Create ad" button
                        # ===================================
                        if update_callback:
                            await update_callback(3, "Looking for 'Create ad' button...")

                        logger.info("🔍 Searching for 'Create ad' button...")
                        try:
                            # Target the exact div with specific classes
                            create_ad_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH,
                                    "//div[contains(@class, 'x1vvvo52') and contains(@class, 'x1fvot60') and contains(@class, 'xk50ysn') and text()='Create ad']"
                                ))
                            )
                            logger.info("✓ Found 'Create ad' button")

                            # Scroll into view
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", create_ad_button)
                            time.sleep(1)

                            # Click using JavaScript
                            driver.execute_script("arguments[0].click();", create_ad_button)
                            create_ad_clicked = True
                            logger.info("✅ CLICKED 'Create ad' button")

                            if update_callback:
                                await update_callback(3, "✓ Clicked 'Create ad', waiting...")

                            time.sleep(3)

                            # Take screenshot after clicking "Create ad"
                            screenshot_after_create_ad = driver.get_screenshot_as_png()
                            logger.info("✓ Screenshot captured after 'Create ad' click")

                        except Exception as e:
                            logger.error(f"❌ Failed to click 'Create ad' button: {e}")
                            # Try fallback selector
                            try:
                                create_ad_fallback = driver.find_element(By.XPATH, "//*[contains(text(), 'Create ad')]")
                                driver.execute_script("arguments[0].click();", create_ad_fallback)
                                create_ad_clicked = True
                                logger.info("✅ CLICKED 'Create ad' (fallback)")
                                time.sleep(3)
                                screenshot_after_create_ad = driver.get_screenshot_as_png()
                            except Exception as fallback_error:
                                logger.error(f"❌ Fallback also failed: {fallback_error}")

                        # STEP 3.2: Click first "Continue" button
                        # ========================================
                        if update_callback:
                            await update_callback(3, "Looking for first 'Continue' button...")

                        logger.info("🔍 Searching for first 'Continue' button...")
                        try:
                            # Target the exact div with specific classes
                            continue_button_1 = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.XPATH,
                                    "//div[contains(@class, 'x1vvvo52') and contains(@class, 'x1fvot60') and contains(@class, 'xk50ysn') and text()='Continue']"
                                ))
                            )
                            logger.info("✓ Found first 'Continue' button")

                            # Scroll into view
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", continue_button_1)
                            time.sleep(1)

                            # Click using JavaScript
                            driver.execute_script("arguments[0].click();", continue_button_1)
                            continue_1_clicked = True
                            logger.info("✅ CLICKED first 'Continue' button")

                            if update_callback:
                                await update_callback(3, "✓ Clicked first 'Continue', waiting...")

                            time.sleep(3)

                            # Take screenshot after clicking first "Continue"
                            screenshot_after_continue_1 = driver.get_screenshot_as_png()
                            logger.info("✓ Screenshot captured after first 'Continue' click")

                        except Exception as e:
                            logger.error(f"❌ Failed to click first 'Continue' button: {e}")

                        # STEP 3.3: Click second "Continue" button (in popup dialog)
                        # ===========================================================
                        if update_callback:
                            await update_callback(3, "Looking for second 'Continue' button in popup...")

                        logger.info("🔍 Searching for second 'Continue' button in popup dialog...")

                        try:
                            # Wait for popup dialog to appear
                            time.sleep(2)

                            # Find the second Continue button (should be in a popup/dialog)
                            # Try to find it with role=button parent
                            continue_found = False

                            try:
                                # Method 1: Find the Continue text div and get its role=button parent
                                continue_text_divs = driver.find_elements(By.XPATH,
                                    "//div[contains(@class, 'x1vvvo52') and contains(@class, 'x1fvot60') and contains(@class, 'xk50ysn') and text()='Continue']"
                                )

                                if continue_text_divs:
                                    logger.info(f"✓ Found {len(continue_text_divs)} Continue text div(s)")

                                    # Try to find the one with role=button ancestor
                                    for text_div in continue_text_divs:
                                        try:
                                            clickable_parent = text_div.find_element(By.XPATH, "./ancestor::div[@role='button'][1]")
                                            if clickable_parent.is_displayed():
                                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", clickable_parent)
                                                time.sleep(1)
                                                driver.execute_script("arguments[0].click();", clickable_parent)
                                                continue_2_clicked = True
                                                continue_found = True
                                                logger.info("✅ CLICKED second 'Continue' button (via role=button parent)")
                                                break
                                        except:
                                            continue

                                    # If no role=button parent found, try clicking the div itself
                                    if not continue_found:
                                        for text_div in continue_text_divs:
                                            try:
                                                if text_div.is_displayed():
                                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", text_div)
                                                    time.sleep(1)
                                                    driver.execute_script("arguments[0].click();", text_div)
                                                    continue_2_clicked = True
                                                    continue_found = True
                                                    logger.info("✅ CLICKED second 'Continue' button (direct)")
                                                    break
                                            except:
                                                continue

                            except Exception as e:
                                logger.debug(f"Method 1 failed: {e}")

                            if not continue_found:
                                logger.error("❌ Could NOT find/click second Continue button")

                            if update_callback:
                                await update_callback(3, "✓ Clicked second 'Continue', waiting...")

                            time.sleep(3)

                            # Take screenshot after second Continue
                            screenshot_after_continue_2 = driver.get_screenshot_as_png()
                            logger.info("✓ Screenshot captured after second 'Continue' click")

                        except Exception as e:
                            logger.error(f"❌ Failed to click second 'Continue' button: {e}")

                        # STEP 3.4: Check for popup tab and click "Continue as" button
                        # ============================================================
                        logger.info("🔍 Checking for popup tab after second 'Continue' click...")
                        try:
                            time.sleep(2)
                            current_windows = driver.window_handles
                            logger.info(f"Window handles: {len(current_windows)}")

                            if len(current_windows) > 1:
                                popup_opened = True
                                logger.info("✓ Popup tab opened!")

                                if update_callback:
                                    await update_callback(3, "Switching to popup tab...")

                                # Store main window
                                main_window = driver.current_window_handle

                                # Switch to popup tab
                                for window in current_windows:
                                    if window != main_window:
                                        driver.switch_to.window(window)
                                        popup_url = driver.current_url
                                        logger.info(f"✓ Switched to popup tab. URL: {popup_url}")

                                        # Wait for popup content to load
                                        time.sleep(2)

                                        # Look for "Continue as [username]" button
                                        if update_callback:
                                            await update_callback(3, "Looking for 'Continue as' button...")

                                        logger.info("🔍 Searching for 'Continue as' button...")
                                        try:
                                            # Target exact button with all classes
                                            continue_as_button = WebDriverWait(driver, 10).until(
                                                EC.element_to_be_clickable((By.XPATH,
                                                    "//button[@value='1' and @name='__CONFIRM__' and @type='submit' and contains(@class, 'layerConfirm')]"
                                                ))
                                            )
                                            logger.info("✓ Found 'Continue as' button")

                                            # Scroll into view
                                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", continue_as_button)
                                            time.sleep(1)

                                            # Click
                                            continue_as_button.click()
                                            continue_as_clicked = True
                                            logger.info("✅ CLICKED 'Continue as' button")

                                            if update_callback:
                                                await update_callback(3, "✓ Clicked 'Continue as', waiting...")

                                            time.sleep(3)

                                        except Exception as e:
                                            logger.error(f"❌ Failed to click 'Continue as' button: {e}")
                                            # Try fallback selector
                                            try:
                                                continue_as_fallback = driver.find_element(By.XPATH, "//button[@name='__CONFIRM__']")
                                                continue_as_fallback.click()
                                                continue_as_clicked = True
                                                logger.info("✅ CLICKED 'Continue as' (fallback)")
                                                time.sleep(3)
                                            except Exception as fallback_error:
                                                logger.error(f"❌ Fallback also failed: {fallback_error}")

                                        # Take screenshot in popup tab
                                        screenshot_after_continue_as = driver.get_screenshot_as_png()
                                        logger.info("✓ Screenshot captured in popup tab after 'Continue as' click")

                                        # Close popup tab
                                        driver.close()
                                        logger.info("✓ Closed popup tab")

                                        # Switch back to main window
                                        driver.switch_to.window(main_window)
                                        logger.info("✓ Switched back to main window")
                                        break
                            else:
                                logger.warning("⚠️ Popup tab did NOT open after second Continue click")

                        except Exception as e:
                            logger.error(f"❌ Error during popup tab handling: {e}")

                        logger.info("=" * 80)
                        logger.info("STEP 3: COMPLETED - Create Ad Flow Done!")
                        logger.info(f"'Create ad' clicked: {create_ad_clicked}")
                        logger.info(f"First 'Continue' clicked: {continue_1_clicked}")
                        logger.info(f"Second 'Continue' clicked: {continue_2_clicked}")
                        logger.info(f"Popup tab opened: {popup_opened}")
                        logger.info(f"'Continue as' clicked: {continue_as_clicked}")
                        logger.info("=" * 80)

                        final_url = driver.current_url
                        logger.info(f"Final URL: {final_url}")

                        # Update result with step 3 data
                        result['screenshot_after_create_ad'] = screenshot_after_create_ad
                        result['screenshot_after_continue_1'] = screenshot_after_continue_1
                        result['screenshot_after_continue_2'] = screenshot_after_continue_2
                        result['screenshot_after_continue_as'] = screenshot_after_continue_as
                        result['step3_complete'] = True
                        result['step3_current_url'] = final_url
                        result['step3_create_ad_clicked'] = create_ad_clicked
                        result['step3_continue_1_clicked'] = continue_1_clicked
                        result['step3_continue_2_clicked'] = continue_2_clicked
                        result['step3_popup_opened'] = popup_opened
                        result['step3_continue_as_clicked'] = continue_as_clicked

                    except Exception as e:
                        logger.error(f"Step 3 failed: {e}", exc_info=True)

                        # Capture screenshot even on failure
                        screenshot_error = None
                        error_url = "N/A"
                        try:
                            screenshot_error = driver.get_screenshot_as_png()
                            error_url = driver.current_url
                            logger.info(f"✓ Step 3 error screenshot captured. URL: {error_url}")
                        except Exception as screenshot_error_ex:
                            logger.error(f"✗ Failed to capture Step 3 error screenshot: {screenshot_error_ex}")

                        result['step3_complete'] = False
                        result['screenshot_after_create_ad'] = screenshot_error
                        result['screenshot_after_continue_1'] = None
                        result['screenshot_after_continue_2'] = None
                        result['screenshot_after_continue_as'] = None
                        result['step3_current_url'] = error_url
                        result['step3_error'] = str(e)
                        result['step3_create_ad_clicked'] = False
                        result['step3_continue_1_clicked'] = False
                        result['step3_continue_2_clicked'] = False
                        result['step3_popup_opened'] = False
                        result['step3_continue_as_clicked'] = False

                except Exception as e:
                    logger.error(f"Step 2 failed: {e}", exc_info=True)

                    # Capture screenshot even on failure
                    screenshot_step2_error = None
                    error_url = "N/A"
                    try:
                        screenshot_step2_error = driver.get_screenshot_as_png()
                        error_url = driver.current_url
                        logger.info(f"✓ Step 2 error screenshot captured. URL: {error_url}")
                    except Exception as screenshot_error:
                        logger.error(f"✗ Failed to capture Step 2 error screenshot: {screenshot_error}")

                    result['step2_complete'] = False
                    result['screenshot_step2'] = screenshot_step2_error
                    result['step2_current_url'] = error_url
                    result['step2_error'] = str(e)
                    result['step2_instagram_clicked'] = False
                    result['step2_login_button_clicked'] = False
                    result['step2_popup_url'] = None
                    result['step2_new_tab_info'] = {'new_tab_opened': False, 'total_windows': 1}
                    result['step2_on_business_home'] = False

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
