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
    Instagram cookie checker with Step 1 (login check) and Step 2 (Facebook Business Suite)

    Returns: dict with 'valid', 'message', 'username', 'step2_status'
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

        if not is_logged_in:
            return {
                'valid': False,
                'screenshot': None,
                'message': "Invalid cookie",
                'username': 'N/A',
                'url': current_url,
                'step1_complete': False,
                'step2_complete': False,
                'step2_status': 'Skipped - Step 1 failed'
            }

        # Step 2: Navigate to Facebook Business Suite and click "Login with Instagram"
        step2_success = False
        step2_status = ""
        screenshots = []

        if update_callback:
            await update_callback(2, "Navigating to Facebook Business login page...")

        try:
            import time
            from selenium.webdriver.common.by import By

            # Navigate to the specific Facebook Business login URL
            driver.get('https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs')

            time.sleep(3)

            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )

            if update_callback:
                await update_callback(2, "Taking screenshot before clicking...")

            time.sleep(2)

            # Take screenshot before clicking
            screenshot_before = driver.get_screenshot_as_png()
            screenshots.append(('before_click.png', screenshot_before))

            if update_callback:
                await update_callback(2, "Looking for 'Log in with Instagram' button...")

            # Try to find and click the Instagram login button by span text
            login_button_found = False
            popup_detected = False

            try:
                # Store initial window handles
                initial_windows = driver.window_handles
                initial_window_count = len(initial_windows)

                # Try to find the span with the specific text
                spans = driver.find_elements(By.TAG_NAME, "span")

                for span in spans:
                    try:
                        text = span.text.strip()
                        if text == "Log in with Instagram":
                            if update_callback:
                                await update_callback(2, "Found button! Clicking...")

                            # Try to click the span or its parent
                            try:
                                span.click()
                            except:
                                # If span click fails, try parent element
                                parent = span.find_element(By.XPATH, "..")
                                parent.click()

                            login_button_found = True
                            time.sleep(2)

                            # Check for new windows/tabs
                            current_windows = driver.window_handles
                            if len(current_windows) > initial_window_count:
                                popup_detected = True
                                if update_callback:
                                    await update_callback(2, "Popup/new tab detected! Taking screenshot...")

                                # Switch to new window
                                for window in current_windows:
                                    if window not in initial_windows:
                                        driver.switch_to.window(window)
                                        time.sleep(1)
                                        screenshot_popup = driver.get_screenshot_as_png()
                                        screenshots.append(('popup.png', screenshot_popup))
                                        break

                                step2_status = "Clicked successfully - Popup detected"
                            else:
                                # Take screenshot of same page after click
                                time.sleep(1)
                                screenshot_after = driver.get_screenshot_as_png()
                                screenshots.append(('after_click.png', screenshot_after))
                                step2_status = "Clicked successfully - No popup detected"

                            step2_success = True
                            break
                    except:
                        continue

                if not login_button_found:
                    # Try JavaScript click as fallback
                    clicked = driver.execute_script("""
                        const spans = document.querySelectorAll('span');
                        for (const span of spans) {
                            if (span.textContent.trim() === 'Log in with Instagram') {
                                span.click();
                                return true;
                            }
                        }
                        return false;
                    """)

                    if clicked:
                        time.sleep(2)

                        # Check for new windows/tabs
                        current_windows = driver.window_handles
                        if len(current_windows) > initial_window_count:
                            popup_detected = True
                            for window in current_windows:
                                if window not in initial_windows:
                                    driver.switch_to.window(window)
                                    time.sleep(1)
                                    screenshot_popup = driver.get_screenshot_as_png()
                                    screenshots.append(('popup.png', screenshot_popup))
                                    break
                            step2_status = "Clicked (JS) - Popup detected"
                        else:
                            screenshot_after = driver.get_screenshot_as_png()
                            screenshots.append(('after_click.png', screenshot_after))
                            step2_status = "Clicked (JS) - No popup detected"

                        step2_success = True
                    else:
                        step2_status = "Could not find 'Log in with Instagram' button"

            except Exception as e:
                logger.warning(f"Error finding/clicking button: {e}")
                step2_status = f"Error: {str(e)[:100]}"

        except Exception as e:
            logger.warning(f"Error in Step 2: {e}")
            step2_status = f"Error: {str(e)[:100]}"

        return {
            'valid': is_logged_in,
            'screenshot': None,
            'screenshots': screenshots,
            'message': f"Valid cookie - Logged in! Step 2: {step2_status}",
            'username': username,
            'url': current_url,
            'step1_complete': is_logged_in,
            'step2_complete': step2_success,
            'step2_status': step2_status
        }

    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            'valid': False,
            'screenshot': None,
            'message': f"Error: {str(e)[:100]}",
            'username': 'N/A',
            'url': None,
            'step1_complete': False,
            'step2_complete': False,
            'step2_status': 'Error in Step 1'
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
