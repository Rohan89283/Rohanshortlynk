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
                'screenshot_step2': None,
                'screenshot_oauth': None,
                'screenshot_step3': None,
                'message': f"Chrome initialization failed: {str(e)[:100]}",
                'url': None,
                'proxy_used': f"{proxy_info['host']}:{proxy_info['port']}" if proxy_info else "Direct"
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
                'screenshot_step2_before': None,
                'screenshot_step2_after_click': None,
                'screenshot_step2': None,
                'screenshot_oauth': None,
                'screenshot_step3': None,
                'message': message,
                'url': current_url,
                'proxy_used': proxy_used,
                'username': username,
                'total_posts': total_posts,
                'location': location,
                'step1_complete': is_logged_in,
                'step2_complete': False,
                'step2_method': None,
                'step3_complete': False
            }

            # If login successful, proceed to Step 2 - Facebook Business Manager
            if is_logged_in:
                try:
                    logger.info("=" * 80)
                    logger.info("STEP 2: Facebook Business Manager - STARTING")
                    logger.info("=" * 80)

                    if update_callback:
                        await update_callback(2, "Navigating to Meta Business...")

                    # Navigate to Facebook Business Manager with English locale
                    logger.info("Navigating to: https://business.facebook.com/latest/home?locale=en_US")
                    driver.get('https://business.facebook.com/latest/home?locale=en_US')

                    # Wait for page to fully load
                    WebDriverWait(driver, 10).until(
                        lambda d: d.execute_script('return document.readyState') == 'complete'
                    )

                    # Get initial URL
                    initial_url = driver.current_url
                    logger.info(f"Initial URL after navigation: {initial_url}")

                    # Take screenshot before any interaction
                    try:
                        screenshot_before = driver.get_screenshot_as_png()
                        result['screenshot_step2_before'] = screenshot_before
                        logger.info("Screenshot captured BEFORE looking for Instagram login")
                    except Exception as e:
                        logger.warning(f"Failed to capture before screenshot: {e}")

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
                        if update_callback:
                            await update_callback(2, "Looking for Instagram login...")

                        # Wait for any dynamic content to load
                        time.sleep(2)

                        logger.info("Searching for Instagram login button with ALL methods...")

                        # Store all found elements
                        instagram_elements = []
                        instagram_login_clicked = False
                        successful_method = None

                        # METHOD 1: Exact text "Log in with Instagram"
                        logger.info("METHOD 1: Searching for exact text 'Log in with Instagram'...")
                        try:
                            elements = driver.find_elements(By.XPATH,
                                "//*[normalize-space(text())='Log in with Instagram'] | "
                                "//*[contains(normalize-space(text()), 'Log in with Instagram')]"
                            )
                            logger.info(f"Found {len(elements)} elements with exact text")
                            for idx, elem in enumerate(elements):
                                try:
                                    if elem.is_displayed():
                                        instagram_elements.append(('METHOD1', idx, elem, elem.text))
                                        logger.info(f"  Element {idx}: visible=True, text='{elem.text}'")
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 1 search failed: {e}")

                        # METHOD 2: Contains "Instagram" in buttons/links
                        logger.info("METHOD 2: Searching for buttons/links containing 'Instagram'...")
                        try:
                            elements = driver.find_elements(By.XPATH,
                                "//button[contains(translate(., 'INSTAGRAM', 'instagram'), 'instagram')] | "
                                "//a[contains(translate(., 'INSTAGRAM', 'instagram'), 'instagram')] | "
                                "//div[@role='button' and contains(translate(., 'INSTAGRAM', 'instagram'), 'instagram')]"
                            )
                            logger.info(f"Found {len(elements)} clickable elements with Instagram")
                            for idx, elem in enumerate(elements):
                                try:
                                    if elem.is_displayed():
                                        instagram_elements.append(('METHOD2', idx, elem, elem.text))
                                        logger.info(f"  Element {idx}: visible=True, text='{elem.text}'")
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 2 search failed: {e}")

                        # METHOD 3: aria-label containing Instagram
                        logger.info("METHOD 3: Searching for aria-label containing 'Instagram'...")
                        try:
                            elements = driver.find_elements(By.XPATH,
                                "//*[contains(translate(@aria-label, 'INSTAGRAM', 'instagram'), 'instagram')]"
                            )
                            logger.info(f"Found {len(elements)} elements with Instagram in aria-label")
                            for idx, elem in enumerate(elements):
                                try:
                                    if elem.is_displayed():
                                        aria_label = elem.get_attribute('aria-label')
                                        instagram_elements.append(('METHOD3', idx, elem, elem.text or aria_label))
                                        logger.info(f"  Element {idx}: visible=True, text='{elem.text}', aria-label='{aria_label}'")
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 3 search failed: {e}")

                        # METHOD 4: All clickable elements (brute force)
                        logger.info("METHOD 4: Checking ALL clickable elements...")
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR,
                                "a, button, div[role='button'], span[role='button'], input[type='button'], input[type='submit']"
                            )
                            logger.info(f"Found {len(elements)} total clickable elements")
                            found_count = 0
                            for idx, elem in enumerate(elements):
                                try:
                                    text = elem.text.lower()
                                    if 'instagram' in text and elem.is_displayed():
                                        instagram_elements.append(('METHOD4', idx, elem, elem.text))
                                        logger.info(f"  Element {idx}: visible=True, text='{elem.text}'")
                                        found_count += 1
                                        if found_count >= 5:  # Limit to first 5 to avoid spam
                                            logger.info(f"  ... (showing first 5 of potentially more)")
                                            break
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 4 search failed: {e}")

                        logger.info(f"\nTotal Instagram-related elements found: {len(instagram_elements)}")

                        # Now try clicking each element with DIFFERENT click methods
                        for method_name, idx, element, text in instagram_elements:
                            if instagram_login_clicked:
                                break

                            logger.info(f"\nAttempting to click: {method_name}[{idx}] - '{text}'")

                            # CLICK TECHNIQUE 1: JavaScript click
                            try:
                                logger.info("  CLICK TECHNIQUE 1: JavaScript click...")
                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", element)
                                time.sleep(0.3)
                                old_url = driver.current_url
                                driver.execute_script("arguments[0].click();", element)
                                time.sleep(1.5)
                                new_url = driver.current_url

                                if old_url != new_url:
                                    logger.info(f"  ✅ SUCCESS! URL changed: {old_url} -> {new_url}")
                                    instagram_login_clicked = True
                                    successful_method = f"{method_name}[{idx}] + JS_CLICK"
                                    break
                                else:
                                    logger.info(f"  ❌ No URL change")
                            except Exception as e:
                                logger.warning(f"  ❌ JS click failed: {e}")

                            # CLICK TECHNIQUE 2: Selenium native click
                            if not instagram_login_clicked:
                                try:
                                    logger.info("  CLICK TECHNIQUE 2: Selenium native click...")
                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", element)
                                    time.sleep(0.3)
                                    old_url = driver.current_url
                                    element.click()
                                    time.sleep(1.5)
                                    new_url = driver.current_url

                                    if old_url != new_url:
                                        logger.info(f"  ✅ SUCCESS! URL changed: {old_url} -> {new_url}")
                                        instagram_login_clicked = True
                                        successful_method = f"{method_name}[{idx}] + NATIVE_CLICK"
                                        break
                                    else:
                                        logger.info(f"  ❌ No URL change")
                                except Exception as e:
                                    logger.warning(f"  ❌ Native click failed: {e}")

                            # CLICK TECHNIQUE 3: ActionChains click
                            if not instagram_login_clicked:
                                try:
                                    from selenium.webdriver.common.action_chains import ActionChains
                                    logger.info("  CLICK TECHNIQUE 3: ActionChains click...")
                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", element)
                                    time.sleep(0.3)
                                    old_url = driver.current_url
                                    ActionChains(driver).move_to_element(element).click().perform()
                                    time.sleep(1.5)
                                    new_url = driver.current_url

                                    if old_url != new_url:
                                        logger.info(f"  ✅ SUCCESS! URL changed: {old_url} -> {new_url}")
                                        instagram_login_clicked = True
                                        successful_method = f"{method_name}[{idx}] + ACTION_CLICK"
                                        break
                                    else:
                                        logger.info(f"  ❌ No URL change")
                                except Exception as e:
                                    logger.warning(f"  ❌ ActionChains click failed: {e}")

                        # Log result
                        if instagram_login_clicked:
                            logger.info(f"\n🎉 INSTAGRAM LOGIN CLICKED SUCCESSFULLY!")
                            logger.info(f"🎯 Successful method: {successful_method}")

                            if update_callback:
                                await update_callback(2, "Logging in with Instagram...")

                            # Wait for page to load
                            WebDriverWait(driver, 10).until(
                                lambda d: d.execute_script('return document.readyState') == 'complete'
                            )
                            time.sleep(1.5)

                            # Check current URL
                            current_url = driver.current_url
                            logger.info(f"Current URL after click: {current_url}")

                            # Take screenshot after click
                            try:
                                screenshot_after_click = driver.get_screenshot_as_png()
                                result['screenshot_step2_after_click'] = screenshot_after_click
                                logger.info("Screenshot captured AFTER clicking Instagram login")
                            except Exception as e:
                                logger.warning(f"Failed to capture after-click screenshot: {e}")

                            # Look for OAuth confirmation page
                            if 'instagram.com/oauth' in current_url or 'instagram.com/accounts' in current_url:
                                logger.info("✅ Detected Instagram OAuth page!")

                                # Take screenshot of OAuth page
                                try:
                                    screenshot_oauth = driver.get_screenshot_as_png()
                                    result['screenshot_oauth'] = screenshot_oauth
                                    logger.info("OAuth page screenshot captured")
                                except Exception as e:
                                    logger.warning(f"Failed to capture OAuth screenshot: {e}")

                                # Look for confirmation button
                                try:
                                    logger.info("Looking for 'Log in as' confirmation button...")
                                    login_confirmed = False

                                    # Try finding confirmation button
                                    confirm_buttons = driver.find_elements(By.XPATH,
                                        "//button[contains(., 'Log in as')] | //a[contains(., 'Log in as')] | "
                                        "//div[@role='button' and contains(., 'Log in as')] | "
                                        "//button[contains(., 'Continue')] | //button[@type='submit']"
                                    )

                                    logger.info(f"Found {len(confirm_buttons)} potential confirmation buttons")

                                    for btn in confirm_buttons:
                                        try:
                                            if btn.is_displayed():
                                                logger.info(f"Clicking confirmation button: {btn.text}")
                                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                                                time.sleep(0.3)
                                                driver.execute_script("arguments[0].click();", btn)
                                                login_confirmed = True
                                                logger.info(f"✅ Clicked confirmation button: {btn.text}")
                                                break
                                        except:
                                            continue

                                    if login_confirmed:
                                        logger.info("Confirmation button clicked - waiting for redirect...")
                                        if update_callback:
                                            await update_callback(2, "Confirming login...")
                                    else:
                                        logger.warning("No confirmation button found")

                                except Exception as e:
                                    logger.warning(f"Error looking for confirmation button: {e}")

                            # Wait for redirect to Business Manager
                            logger.info("Waiting for redirect to Business Manager...")
                            try:
                                WebDriverWait(driver, 15).until(
                                    lambda d: 'business.facebook.com' in d.current_url
                                )
                                logger.info("✅ Successfully redirected to Business Manager")
                            except TimeoutException:
                                logger.warning("⏱️ Timeout waiting for redirect to Business Manager")

                            # Final URL check
                            WebDriverWait(driver, 10).until(
                                lambda d: d.execute_script('return document.readyState') == 'complete'
                            )
                            time.sleep(1)

                            final_url = driver.current_url
                            logger.info(f"Final URL after OAuth flow: {final_url}")

                        else:
                            logger.warning("❌ NO INSTAGRAM LOGIN BUTTON FOUND OR CLICKED")
                            logger.warning("Checking if already logged in...")

                            current_url = driver.current_url
                            if 'business.facebook.com' in current_url and 'login' not in current_url.lower():
                                logger.info("✅ Already logged into Business Manager")
                            else:
                                logger.warning(f"⚠️ Still on login/start page: {current_url}")

                    except Exception as e:
                        logger.error(f"❌ ERROR in Instagram login flow: {e}")
                        import traceback
                        logger.error(traceback.format_exc())

                    # Take final screenshot after Step 2
                    try:
                        screenshot_step2 = driver.get_screenshot_as_png()
                        result['screenshot_step2'] = screenshot_step2
                        logger.info("Final Step 2 screenshot captured")
                    except Exception as e:
                        logger.warning(f"Failed to capture Step 2 final screenshot: {e}")

                    # Log all URLs visited
                    try:
                        all_urls = driver.execute_script("return window.performance.getEntriesByType('navigation').map(e => e.name);")
                        logger.info(f"All navigation URLs: {all_urls}")
                    except:
                        pass

                    result['step2_complete'] = True
                    result['step2_method'] = successful_method if instagram_login_clicked else "Not clicked"
                    logger.info("=" * 80)
                    logger.info("STEP 2: COMPLETED")
                    logger.info("=" * 80)

                    # Step 3: Navigate to Facebook Ad Center
                    try:
                        logger.info("Starting Step 3 - Facebook Ad Center...")
                        if update_callback:
                            await update_callback(3, "Navigating to Ad Center...")

                        # Navigate to Facebook Ad Center with English locale
                        logger.info("Navigating to Facebook Ad Center...")
                        driver.get('https://business.facebook.com/latest/ad_center/ads_summary?locale=en_US')

                        # Wait for page to be fully loaded
                        WebDriverWait(driver, 10).until(
                            lambda d: d.execute_script('return document.readyState') == 'complete'
                        )

                        # Force English language again
                        driver.execute_script("""
                            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                            Object.defineProperty(navigator, 'language', {get: () => 'en-US'});

                            if (window.localStorage) {
                                window.localStorage.setItem('locale', 'en_US');
                            }
                        """)

                        if update_callback:
                            await update_callback(3, "Loading Ad Center data...")

                        # Wait for dynamic content to load (minimal wait)
                        time.sleep(2)

                        current_url = driver.current_url
                        logger.info(f"Current URL at Step 3: {current_url}")

                        # Check if we're actually on the Ad Center or still on login page
                        if 'login' in current_url.lower() or 'get started' in driver.page_source.lower()[:5000]:
                            logger.warning("Still on login page, attempting to click Instagram login again")

                            # Try to click Instagram login button again
                            try:
                                elements = driver.find_elements(By.XPATH, "//a[contains(., 'Instagram')] | //button[contains(., 'Instagram')] | //div[contains(., 'Instagram')]")
                                for element in elements:
                                    if 'instagram' in element.text.lower():
                                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                                        time.sleep(0.3)
                                        driver.execute_script("arguments[0].click();", element)
                                        logger.info("Clicked Instagram login in Step 3")

                                        # Wait for redirect to business.facebook.com
                                        try:
                                            WebDriverWait(driver, 15).until(
                                                lambda d: 'business.facebook.com' in d.current_url and 'login' not in d.current_url.lower()
                                            )
                                        except TimeoutException:
                                            logger.warning("Timeout waiting for redirect")

                                        WebDriverWait(driver, 10).until(
                                            lambda d: d.execute_script('return document.readyState') == 'complete'
                                        )

                                        # Try navigating to Ad Center again
                                        driver.get('https://business.facebook.com/latest/ad_center/ads_summary?locale=en_US')
                                        WebDriverWait(driver, 10).until(
                                            lambda d: d.execute_script('return document.readyState') == 'complete'
                                        )
                                        time.sleep(1.5)
                                        break
                            except Exception as e:
                                logger.warning(f"Failed to re-click Instagram login: {e}")

                        if update_callback:
                            await update_callback(3, "Capturing screenshot...")

                        # Wait for page content to be fully rendered
                        time.sleep(2)

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
                'screenshot_oauth': None,
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
            'screenshot_oauth': None,
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
            'screenshot_oauth': None,
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
