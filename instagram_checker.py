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
                'screenshot_oauth_before': None,
                'screenshot_oauth_after': None,
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
                'step2_button_html': None,
                'step2_click_technique': None,
                'step2_urls_visited': [],
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

                        # Helper function to strictly filter Instagram login elements (NOT Facebook)
                        def is_instagram_login_only(text, aria_label=None):
                            """Check if this is Instagram login button and NOT Facebook"""
                            if not text and not aria_label:
                                return False

                            combined_text = f"{text or ''} {aria_label or ''}".lower()

                            # MUST contain "instagram"
                            if 'instagram' not in combined_text:
                                return False

                            # MUST NOT contain "facebook" or "fb"
                            if 'facebook' in combined_text or ' fb ' in combined_text:
                                logger.info(f"  ❌ REJECTED (contains Facebook/FB): '{text}'")
                                return False

                            # Should contain login-related words
                            has_login = any(word in combined_text for word in ['log in', 'login', 'sign in', 'signin'])

                            if has_login:
                                logger.info(f"  ✅ ACCEPTED: '{text}'")
                                return True

                            return False

                        # METHOD 1: Exact text "Log in with Instagram" (HIGHEST PRIORITY)
                        logger.info("METHOD 1: Searching for EXACT text 'Log in with Instagram'...")
                        try:
                            elements = driver.find_elements(By.XPATH,
                                "//*[normalize-space(text())='Log in with Instagram']"
                            )
                            logger.info(f"Found {len(elements)} elements with EXACT text")
                            for idx, elem in enumerate(elements):
                                try:
                                    if elem.is_displayed():
                                        text = elem.text
                                        if is_instagram_login_only(text):
                                            # Prioritize this by adding it first
                                            instagram_elements.insert(0, ('METHOD1-EXACT', idx, elem, text))
                                            logger.info(f"  🎯 PRIORITY Element {idx}: text='{text}'")
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 1 search failed: {e}")

                        # METHOD 2: Contains "Log in with Instagram" (partial match)
                        logger.info("METHOD 2: Searching for text containing 'Log in with Instagram'...")
                        try:
                            elements = driver.find_elements(By.XPATH,
                                "//*[contains(normalize-space(text()), 'Log in with Instagram')]"
                            )
                            logger.info(f"Found {len(elements)} elements with partial match")
                            for idx, elem in enumerate(elements):
                                try:
                                    if elem.is_displayed():
                                        text = elem.text
                                        if is_instagram_login_only(text):
                                            instagram_elements.append(('METHOD2-CONTAINS', idx, elem, text))
                                            logger.info(f"  ✅ Element {idx}: text='{text}'")
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 2 search failed: {e}")

                        # METHOD 3: Buttons/links with "Instagram" AND "log in" (NO Facebook)
                        logger.info("METHOD 3: Searching for Instagram login buttons (strict filter)...")
                        try:
                            elements = driver.find_elements(By.XPATH,
                                "//button[contains(translate(., 'INSTAGRAM', 'instagram'), 'instagram') and "
                                "contains(translate(., 'LOG IN', 'log in'), 'log in')] | "
                                "//a[contains(translate(., 'INSTAGRAM', 'instagram'), 'instagram') and "
                                "contains(translate(., 'LOG IN', 'log in'), 'log in')] | "
                                "//div[@role='button' and contains(translate(., 'INSTAGRAM', 'instagram'), 'instagram') and "
                                "contains(translate(., 'LOG IN', 'log in'), 'log in')]"
                            )
                            logger.info(f"Found {len(elements)} Instagram + Login elements")
                            for idx, elem in enumerate(elements):
                                try:
                                    if elem.is_displayed():
                                        text = elem.text
                                        # Strict filter - MUST pass
                                        if is_instagram_login_only(text):
                                            instagram_elements.append(('METHOD3-STRICT', idx, elem, text))
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 3 search failed: {e}")

                        # METHOD 4: aria-label with "Instagram" (NO Facebook)
                        logger.info("METHOD 4: Searching for aria-label with Instagram...")
                        try:
                            elements = driver.find_elements(By.XPATH,
                                "//*[contains(translate(@aria-label, 'INSTAGRAM', 'instagram'), 'instagram')]"
                            )
                            logger.info(f"Found {len(elements)} elements with Instagram in aria-label")
                            for idx, elem in enumerate(elements):
                                try:
                                    if elem.is_displayed():
                                        aria_label = elem.get_attribute('aria-label')
                                        text = elem.text
                                        if is_instagram_login_only(text, aria_label):
                                            instagram_elements.append(('METHOD4-ARIA', idx, elem, text or aria_label))
                                except:
                                    pass
                        except Exception as e:
                            logger.warning(f"METHOD 4 search failed: {e}")

                        # Log all found elements with their text
                        logger.info(f"\n📊 Total FILTERED Instagram login elements: {len(instagram_elements)}")
                        for method, idx, elem, text in instagram_elements:
                            logger.info(f"  - {method}[{idx}]: '{text}'")

                        # Track URLs visited
                        urls_visited = [driver.current_url]

                        # Now try clicking each element with DIFFERENT click methods
                        for method_name, idx, element, text in instagram_elements:
                            if instagram_login_clicked:
                                break

                            logger.info(f"\n{'='*60}")
                            logger.info(f"Attempting: {method_name}[{idx}] - '{text}'")
                            logger.info(f"{'='*60}")

                            # Get button outerHTML for debugging
                            try:
                                button_html = element.get_attribute('outerHTML')
                                logger.info(f"Button HTML: {button_html[:300]}...")
                                result['step2_button_html'] = button_html
                            except Exception as e:
                                logger.warning(f"Failed to get button HTML: {e}")

                            # Remove any overlays that might block the click
                            try:
                                driver.execute_script("""
                                    // Remove any overlays or blocking elements
                                    var overlays = document.querySelectorAll('[class*="overlay"], [class*="modal"], [class*="popup"]');
                                    overlays.forEach(el => el.style.display = 'none');
                                """)
                            except:
                                pass

                            # CLICK TECHNIQUE 1: JavaScript click with force
                            try:
                                logger.info("  🖱️  TECHNIQUE 1: JavaScript click (forced)")

                                # Make element visible and clickable
                                driver.execute_script("""
                                    arguments[0].style.display = 'block';
                                    arguments[0].style.visibility = 'visible';
                                    arguments[0].style.pointerEvents = 'auto';
                                """, element)

                                # Scroll to element
                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", element)
                                time.sleep(1)

                                old_url = driver.current_url
                                logger.info(f"  URL before click: {old_url}")

                                # Force click with JavaScript
                                driver.execute_script("arguments[0].click();", element)

                                # Wait longer for redirect
                                time.sleep(3)

                                new_url = driver.current_url
                                logger.info(f"  URL after click: {new_url}")
                                urls_visited.append(new_url)

                                # Check if URL changed to Instagram OAuth
                                if old_url != new_url:
                                    if 'instagram.com' in new_url:
                                        logger.info(f"  ✅ SUCCESS! Redirected to Instagram: {new_url}")
                                        instagram_login_clicked = True
                                        successful_method = f"{method_name}[{idx}]"
                                        result['step2_click_technique'] = "JS_CLICK_FORCED"
                                        break
                                    elif 'facebook.com/login' in new_url:
                                        logger.warning(f"  ❌ Wrong page - Facebook login: {new_url}")
                                        driver.back()
                                        time.sleep(1)
                                    else:
                                        logger.info(f"  ⚠️  URL changed to: {new_url} (might be redirecting...)")
                                        # Wait a bit more to see if it redirects to Instagram
                                        time.sleep(2)
                                        final_url = driver.current_url
                                        if 'instagram.com' in final_url:
                                            logger.info(f"  ✅ SUCCESS! Final redirect to Instagram: {final_url}")
                                            instagram_login_clicked = True
                                            successful_method = f"{method_name}[{idx}]"
                                            result['step2_click_technique'] = "JS_CLICK_FORCED"
                                            urls_visited.append(final_url)
                                            break
                                        else:
                                            logger.warning(f"  ❌ Still not on Instagram: {final_url}")
                                else:
                                    logger.info(f"  ❌ No URL change - button click had no effect")
                            except Exception as e:
                                logger.warning(f"  ❌ JS click failed: {e}")

                            # CLICK TECHNIQUE 2: Direct href navigation (if it's a link)
                            if not instagram_login_clicked:
                                try:
                                    logger.info("  🖱️  TECHNIQUE 2: Direct href navigation")

                                    # Check if element has href
                                    href = element.get_attribute('href')
                                    if href:
                                        logger.info(f"  Found href: {href}")
                                        old_url = driver.current_url

                                        # Navigate directly to the href
                                        driver.get(href)
                                        time.sleep(3)

                                        new_url = driver.current_url
                                        logger.info(f"  URL after navigation: {new_url}")
                                        urls_visited.append(new_url)

                                        if 'instagram.com' in new_url:
                                            logger.info(f"  ✅ SUCCESS! Redirected to Instagram: {new_url}")
                                            instagram_login_clicked = True
                                            successful_method = f"{method_name}[{idx}]"
                                            result['step2_click_technique'] = "DIRECT_HREF"
                                            break
                                    else:
                                        logger.info(f"  ❌ No href attribute - skipping")
                                except Exception as e:
                                    logger.warning(f"  ❌ Direct href navigation failed: {e}")

                            # CLICK TECHNIQUE 3: Selenium native click with WebDriverWait
                            if not instagram_login_clicked:
                                try:
                                    logger.info("  🖱️  TECHNIQUE 3: Selenium native click with wait")

                                    # Wait for element to be clickable
                                    from selenium.webdriver.support import expected_conditions as EC
                                    WebDriverWait(driver, 5).until(EC.element_to_be_clickable(element))

                                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'auto', block: 'center'});", element)
                                    time.sleep(1)

                                    old_url = driver.current_url
                                    logger.info(f"  URL before click: {old_url}")

                                    element.click()
                                    time.sleep(3)

                                    new_url = driver.current_url
                                    logger.info(f"  URL after click: {new_url}")
                                    urls_visited.append(new_url)

                                    if old_url != new_url:
                                        if 'instagram.com' in new_url:
                                            logger.info(f"  ✅ SUCCESS! Redirected to Instagram: {new_url}")
                                            instagram_login_clicked = True
                                            successful_method = f"{method_name}[{idx}]"
                                            result['step2_click_technique'] = "NATIVE_CLICK_WAIT"
                                            break
                                        elif 'facebook.com/login' in new_url:
                                            logger.warning(f"  ❌ Wrong page - Facebook login: {new_url}")
                                            driver.back()
                                            time.sleep(1)
                                        else:
                                            # Wait for potential redirect
                                            time.sleep(2)
                                            final_url = driver.current_url
                                            if 'instagram.com' in final_url:
                                                logger.info(f"  ✅ SUCCESS! Final redirect to Instagram: {final_url}")
                                                instagram_login_clicked = True
                                                successful_method = f"{method_name}[{idx}]"
                                                result['step2_click_technique'] = "NATIVE_CLICK_WAIT"
                                                urls_visited.append(final_url)
                                                break
                                    else:
                                        logger.info(f"  ❌ No URL change")
                                except Exception as e:
                                    logger.warning(f"  ❌ Native click with wait failed: {e}")

                        # Store URLs visited
                        result['step2_urls_visited'] = urls_visited

                        # Log result
                        if instagram_login_clicked:
                            logger.info(f"\n{'='*80}")
                            logger.info(f"🎉 INSTAGRAM LOGIN CLICKED SUCCESSFULLY!")
                            logger.info(f"🎯 Successful method: {successful_method}")
                            logger.info(f"{'='*80}")

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
                                logger.info("=" * 80)
                                logger.info("✅ DETECTED INSTAGRAM OAUTH PAGE!")
                                logger.info("=" * 80)
                                logger.info(f"OAuth URL: {current_url}")

                                # Take screenshot of OAuth page BEFORE clicking
                                try:
                                    screenshot_oauth_before = driver.get_screenshot_as_png()
                                    result['screenshot_oauth_before'] = screenshot_oauth_before
                                    result['screenshot_oauth'] = screenshot_oauth_before  # Keep for compatibility
                                    logger.info("✅ OAuth page screenshot captured (BEFORE)")
                                except Exception as e:
                                    logger.warning(f"Failed to capture OAuth BEFORE screenshot: {e}")

                                # Look for confirmation button
                                try:
                                    logger.info("Searching for 'Log in as' confirmation button...")
                                    login_confirmed = False
                                    oauth_button_html = None

                                    # Try finding confirmation button with multiple selectors
                                    confirm_buttons = driver.find_elements(By.XPATH,
                                        "//button[contains(., 'Log in as')] | "
                                        "//a[contains(., 'Log in as')] | "
                                        "//div[@role='button' and contains(., 'Log in as')] | "
                                        "//button[contains(., 'Continue')] | "
                                        "//button[@type='submit'] | "
                                        "//button[contains(@class, '_acan')] | "
                                        "//button[contains(@class, '_acas')]"
                                    )

                                    logger.info(f"Found {len(confirm_buttons)} potential OAuth confirmation buttons")

                                    # Log all found buttons
                                    for i, btn in enumerate(confirm_buttons):
                                        try:
                                            if btn.is_displayed():
                                                btn_text = btn.text
                                                btn_html = btn.get_attribute('outerHTML')
                                                logger.info(f"  Button {i}: text='{btn_text}', html={btn_html[:150]}...")
                                        except:
                                            pass

                                    # Try clicking each button
                                    for btn_idx, btn in enumerate(confirm_buttons):
                                        try:
                                            if btn.is_displayed():
                                                btn_text = btn.text
                                                logger.info(f"\nAttempting to click OAuth button {btn_idx}: '{btn_text}'")

                                                # Get button HTML
                                                oauth_button_html = btn.get_attribute('outerHTML')

                                                # Scroll to button
                                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                                                time.sleep(0.5)

                                                # Get URL before click
                                                url_before_oauth_click = driver.current_url
                                                logger.info(f"  URL before OAuth click: {url_before_oauth_click}")

                                                # Click the button
                                                driver.execute_script("arguments[0].click();", btn)
                                                time.sleep(2)

                                                # Get URL after click
                                                url_after_oauth_click = driver.current_url
                                                logger.info(f"  URL after OAuth click: {url_after_oauth_click}")
                                                urls_visited.append(url_after_oauth_click)

                                                # Check if URL changed
                                                if url_before_oauth_click != url_after_oauth_click:
                                                    login_confirmed = True
                                                    logger.info(f"✅ OAuth confirmation button clicked successfully!")
                                                    logger.info(f"✅ Button text: '{btn_text}'")
                                                    logger.info(f"✅ Button HTML: {oauth_button_html[:200]}...")
                                                    break
                                                else:
                                                    logger.warning(f"  ⚠️  No URL change after clicking button {btn_idx}")
                                        except Exception as e:
                                            logger.warning(f"  ❌ Failed to click button {btn_idx}: {e}")
                                            continue

                                    if login_confirmed:
                                        logger.info("OAuth confirmation successful - waiting for redirect...")
                                        if update_callback:
                                            await update_callback(2, "OAuth confirmed, redirecting...")

                                        # Wait for page to load
                                        time.sleep(2)

                                        # Take screenshot AFTER clicking OAuth button
                                        try:
                                            screenshot_oauth_after = driver.get_screenshot_as_png()
                                            result['screenshot_oauth_after'] = screenshot_oauth_after
                                            logger.info("✅ OAuth page screenshot captured (AFTER)")
                                        except Exception as e:
                                            logger.warning(f"Failed to capture OAuth AFTER screenshot: {e}")
                                    else:
                                        logger.warning("=" * 80)
                                        logger.warning("⚠️  NO OAUTH CONFIRMATION BUTTON CLICKED")
                                        logger.warning("=" * 80)
                                        logger.warning("May auto-redirect or require manual confirmation")

                                        # Still take "after" screenshot showing current state
                                        try:
                                            screenshot_oauth_after = driver.get_screenshot_as_png()
                                            result['screenshot_oauth_after'] = screenshot_oauth_after
                                            logger.info("Screenshot captured (OAuth page - no button clicked)")
                                        except:
                                            pass

                                except Exception as e:
                                    logger.error(f"❌ ERROR looking for OAuth confirmation button: {e}")
                                    import traceback
                                    logger.error(traceback.format_exc())
                            else:
                                logger.warning(f"⚠️  Not on Instagram OAuth page. Current URL: {current_url}")

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
                            logger.warning("=" * 80)
                            logger.warning("❌ NO INSTAGRAM LOGIN BUTTON FOUND OR SUCCESSFULLY CLICKED")
                            logger.warning("=" * 80)
                            logger.warning("Checking if already logged in...")

                            current_url = driver.current_url
                            if 'business.facebook.com' in current_url and 'login' not in current_url.lower():
                                logger.info("✅ Already logged into Business Manager")
                            else:
                                logger.warning(f"⚠️ Still on login/start page: {current_url}")

                                # Save page source for debugging
                                try:
                                    page_text = driver.find_element(By.TAG_NAME, 'body').text
                                    logger.info(f"Page body text preview: {page_text[:500]}...")
                                except:
                                    pass

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

                    # Verify we're on Business Manager home page
                    final_step2_url = driver.current_url
                    logger.info(f"Final Step 2 URL: {final_step2_url}")

                    if 'business.facebook.com' in final_step2_url and 'loginpage' not in final_step2_url:
                        logger.info("✅ Successfully reached Business Manager home page!")
                        result['step2_complete'] = True
                    else:
                        logger.warning(f"⚠️  Still on login page or unexpected URL: {final_step2_url}")
                        result['step2_complete'] = False

                    result['step2_method'] = successful_method if instagram_login_clicked else "Not clicked"
                    logger.info("=" * 80)
                    logger.info(f"STEP 2: {'COMPLETED' if result['step2_complete'] else 'INCOMPLETE'}")
                    logger.info("=" * 80)

                    # STEP 3 DISABLED FOR NOW - FOCUSING ON STEP 2
                    logger.info("=" * 80)
                    logger.info("STEP 3: DISABLED (Focusing on Step 2)")
                    logger.info("=" * 80)

                    # Step 3: Navigate to Facebook Ad Center
                    if False:  # Disabled
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
