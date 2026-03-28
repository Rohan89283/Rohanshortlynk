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

                    # STEP 3: Navigate to Ad Center and click Get started
                    logger.info("=" * 80)
                    logger.info("STARTING STEP 3: Ad Center Navigation")
                    logger.info("=" * 80)

                    try:
                        if update_callback:
                            await update_callback(3, "Navigating to Ad Center...")

                        ad_center_url = "https://business.facebook.com/latest/ad_center/ads_summary?locale=en_US"
                        logger.info(f"Navigating to Ad Center: {ad_center_url}")

                        driver.get(ad_center_url)
                        logger.info("✓ Navigation initiated to Ad Center")

                        # Ensure locale cookie is still set
                        try:
                            driver.add_cookie({
                                'name': 'locale',
                                'value': 'en_US',
                                'domain': '.facebook.com',
                                'path': '/'
                            })
                            logger.info("✓ Locale cookie refreshed for Ad Center")
                        except Exception as e:
                            logger.warning(f"Could not refresh locale cookie for Ad Center: {e}")

                        # Wait for page to load
                        if update_callback:
                            await update_callback(3, "Loading Ad Center page...")

                        time.sleep(5)
                        logger.info("✓ Page load wait complete")

                        # Additional wait for dynamic content
                        time.sleep(3)

                        ad_center_final_url = driver.current_url
                        logger.info(f"Ad Center URL: {ad_center_final_url}")

                        # Check if we're on the ad center page
                        on_ad_center = 'ad_center' in ad_center_final_url or 'ads_summary' in ad_center_final_url

                        if on_ad_center:
                            logger.info("✅ Successfully reached Ad Center page!")
                            if update_callback:
                                await update_callback(3, "✅ On Ad Center page!")
                        else:
                            logger.info(f"⚠️ May not be on Ad Center. Current: {ad_center_final_url}")

                        # Try to find and click "Get started" button
                        get_started_clicked = False
                        continue_clicked = False

                        if update_callback:
                            await update_callback(3, "Looking for 'Get started' button...")

                        logger.info("Searching for 'Get started' button...")
                        try:
                            # Try multiple selectors for the "Get started" button
                            possible_selectors = [
                                "//span[contains(text(), 'Get started')]",
                                "//div[contains(text(), 'Get started')]",
                                "//button[contains(., 'Get started')]",
                                "//a[contains(., 'Get started')]",
                            ]

                            for selector in possible_selectors:
                                try:
                                    get_started_button = WebDriverWait(driver, 5).until(
                                        EC.element_to_be_clickable((By.XPATH, selector))
                                    )
                                    logger.info(f"Found 'Get started' button using selector: {selector}")

                                    # Click the button
                                    get_started_button.click()
                                    get_started_clicked = True
                                    logger.info("✓ Clicked 'Get started' button")

                                    if update_callback:
                                        await update_callback(3, "Clicked 'Get started', waiting for page...")

                                    # Wait for page to load after click
                                    time.sleep(5)

                                    # Update URL after click
                                    ad_center_final_url = driver.current_url
                                    logger.info(f"URL after 'Get started' click: {ad_center_final_url}")

                                    break
                                except Exception as e:
                                    logger.debug(f"Selector {selector} did not work: {e}")
                                    continue

                            if not get_started_clicked:
                                logger.info("No 'Get started' button found - may already be past initial screen")

                        except Exception as e:
                            logger.warning(f"Failed to click 'Get started' button: {e}")

                        # Try to find and click first "Continue" button
                        if update_callback:
                            await update_callback(3, "Looking for first 'Continue' button...")

                        logger.info("Searching for first 'Continue' button...")
                        try:
                            # Try multiple selectors for the "Continue" button
                            continue_selectors = [
                                "//span[contains(text(), 'Continue')]",
                                "//div[contains(text(), 'Continue')]",
                                "//button[contains(., 'Continue')]",
                                "//a[contains(., 'Continue')]",
                            ]

                            for selector in continue_selectors:
                                try:
                                    continue_button = WebDriverWait(driver, 5).until(
                                        EC.element_to_be_clickable((By.XPATH, selector))
                                    )
                                    logger.info(f"Found first 'Continue' button using selector: {selector}")

                                    # Click the button
                                    continue_button.click()
                                    continue_clicked = True
                                    logger.info("✓ Clicked first 'Continue' button")

                                    if update_callback:
                                        await update_callback(3, "Clicked first 'Continue', waiting for page...")

                                    # Wait for page to load after click
                                    time.sleep(5)

                                    # Update URL after click
                                    ad_center_final_url = driver.current_url
                                    logger.info(f"URL after first 'Continue' click: {ad_center_final_url}")

                                    break
                                except Exception as e:
                                    logger.debug(f"Selector {selector} did not work: {e}")
                                    continue

                            if not continue_clicked:
                                logger.info("No first 'Continue' button found - may already be past that screen")

                        except Exception as e:
                            logger.warning(f"Failed to click first 'Continue' button: {e}")

                        # Try to find and click second "Continue" button
                        continue_clicked_2 = False
                        if update_callback:
                            await update_callback(3, "Looking for second 'Continue' button...")

                        logger.info("Searching for second 'Continue' button...")
                        try:
                            # Try multiple selectors for the second "Continue" button
                            for selector in continue_selectors:
                                try:
                                    continue_button_2 = WebDriverWait(driver, 5).until(
                                        EC.element_to_be_clickable((By.XPATH, selector))
                                    )
                                    logger.info(f"Found second 'Continue' button using selector: {selector}")

                                    # Click the button
                                    continue_button_2.click()
                                    continue_clicked_2 = True
                                    logger.info("✓ Clicked second 'Continue' button")

                                    if update_callback:
                                        await update_callback(3, "Clicked second 'Continue', waiting for page...")

                                    # Wait for page to load after click
                                    time.sleep(5)

                                    # Update URL after click
                                    ad_center_final_url = driver.current_url
                                    logger.info(f"URL after second 'Continue' click: {ad_center_final_url}")

                                    break
                                except Exception as e:
                                    logger.debug(f"Selector {selector} did not work: {e}")
                                    continue

                            if not continue_clicked_2:
                                logger.info("No second 'Continue' button found - may already be past that screen")

                        except Exception as e:
                            logger.warning(f"Failed to click second 'Continue' button: {e}")

                        # Take screenshot at END of Step 3
                        screenshot_step3 = driver.get_screenshot_as_png()
                        logger.info("✓ Step 3 screenshot captured (Ad Center page after second Continue)")

                        logger.info("=" * 80)
                        logger.info("STEP 3: COMPLETED - Ad Center check done!")
                        logger.info(f"On Ad Center: {on_ad_center}")
                        logger.info(f"Get started clicked: {get_started_clicked}")
                        logger.info(f"Continue clicked (1st): {continue_clicked}")
                        logger.info(f"Continue clicked (2nd): {continue_clicked_2}")
                        logger.info("=" * 80)

                        # Update result with step 3 data
                        result['screenshot_step3'] = screenshot_step3
                        result['step3_complete'] = True
                        result['step3_current_url'] = ad_center_final_url
                        result['step3_on_ad_center'] = on_ad_center
                        result['step3_get_started_clicked'] = get_started_clicked
                        result['step3_continue_clicked'] = continue_clicked
                        result['step3_continue_clicked_2'] = continue_clicked_2

                    except Exception as e:
                        logger.error(f"Step 3 failed: {e}", exc_info=True)

                        # Capture screenshot even on failure
                        screenshot_step3_error = None
                        error_url = "N/A"
                        try:
                            screenshot_step3_error = driver.get_screenshot_as_png()
                            error_url = driver.current_url
                            logger.info(f"✓ Step 3 error screenshot captured. URL: {error_url}")
                        except Exception as screenshot_error:
                            logger.error(f"✗ Failed to capture Step 3 error screenshot: {screenshot_error}")

                        result['step3_complete'] = False
                        result['screenshot_step3'] = screenshot_step3_error
                        result['step3_current_url'] = error_url
                        result['step3_error'] = str(e)
                        result['step3_on_ad_center'] = False

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
