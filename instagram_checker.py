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

        if update_callback:
            await update_callback(2, "Navigating to Facebook Business Suite...")

        try:
            import time
            from selenium.webdriver.common.by import By

            driver.get('https://business.facebook.com/latest/home')

            time.sleep(3)

            WebDriverWait(driver, 10).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )

            if update_callback:
                await update_callback(2, "Looking for 'Login with Instagram' button...")

            time.sleep(2)

            # Try to find and click the Instagram login button
            login_button_found = False
            try:
                # Try finding by text content
                buttons = driver.find_elements(By.TAG_NAME, "button")
                links = driver.find_elements(By.TAG_NAME, "a")
                all_clickable = buttons + links

                for element in all_clickable:
                    try:
                        text = element.text.lower()
                        if 'instagram' in text and ('login' in text or 'log in' in text or 'continue' in text):
                            if update_callback:
                                await update_callback(2, "Clicking 'Login with Instagram'...")
                            element.click()
                            login_button_found = True
                            time.sleep(3)
                            step2_success = True
                            step2_status = "Successfully clicked 'Login with Instagram'"
                            break
                    except:
                        continue

                if not login_button_found:
                    # Try JavaScript click
                    clicked = driver.execute_script("""
                        const elements = [...document.querySelectorAll('button, a, span, div[role="button"]')];
                        for (const el of elements) {
                            const text = el.textContent.toLowerCase();
                            if (text.includes('instagram') && (text.includes('login') || text.includes('log in') || text.includes('continue'))) {
                                el.click();
                                return true;
                            }
                        }
                        return false;
                    """)
                    if clicked:
                        time.sleep(3)
                        step2_success = True
                        step2_status = "Successfully clicked 'Login with Instagram' (JS)"
                    else:
                        step2_status = "Could not find 'Login with Instagram' button"

            except Exception as e:
                logger.warning(f"Error finding/clicking button: {e}")
                step2_status = f"Error finding button: {str(e)[:100]}"

        except Exception as e:
            logger.warning(f"Error in Step 2: {e}")
            step2_status = f"Error: {str(e)[:100]}"

        return {
            'valid': is_logged_in,
            'screenshot': None,
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
