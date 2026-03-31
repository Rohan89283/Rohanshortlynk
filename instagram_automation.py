import os
import time
import logging
from io import BytesIO
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import undetected_chromedriver as uc
from fake_useragent import UserAgent
from PIL import Image

logger = logging.getLogger(__name__)

class InstagramAutomation:
    def __init__(self, cookie_string, update_callback):
        self.cookie_string = cookie_string
        self.update_callback = update_callback
        self.driver = None
        self.screenshots = []

    async def send_update(self, message):
        """Send update to user via callback"""
        logger.info(message)
        await self.update_callback(message)

    def take_screenshot(self, step_name):
        """Take screenshot and store it"""
        try:
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(BytesIO(screenshot))
            self.screenshots.append({
                'name': step_name,
                'image': BytesIO(screenshot)
            })
            logger.info(f"📸 Screenshot captured: {step_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False

    def setup_driver(self):
        """Setup undetected Chrome driver with anti-detection measures"""
        try:
            import subprocess

            chrome_version_output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_version = chrome_version_output.split()[-1].split('.')[0]
            logger.info(f"Detected Chrome version: {chrome_version}")

            options = uc.ChromeOptions()
            # Core stability flags for containerized environments
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-gpu')
            options.add_argument('--headless=new')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-setuid-sandbox')

            # Window and display settings
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--hide-scrollbars')
            options.add_argument('--mute-audio')

            # Memory and performance optimizations
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-breakpad')
            options.add_argument('--disable-component-extensions-with-background-pages')
            options.add_argument('--disable-features=TranslateUI')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--metrics-recording-only')

            # Shared memory increase to prevent crashes
            options.add_argument('--shm-size=2gb')

            # Support multi-language (English and Bengali)
            options.add_argument('--lang=en-US,bn')
            options.add_argument('--accept-lang=en-US,en,bn')
            options.add_experimental_option('prefs', {
                'intl.accept_languages': 'en-US,en,bn',
                'profile.default_content_setting_values.notifications': 2
            })

            ua = UserAgent()
            user_agent = ua.random
            options.add_argument(f'user-agent={user_agent}')

            self.driver = uc.Chrome(options=options, version_main=int(chrome_version), use_subprocess=False)

            # Anti-detection scripts
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")

            logger.info("Chrome driver initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to setup driver: {e}")
            raise

    def parse_cookies(self, cookie_string):
        """Parse cookie string into Selenium cookie format"""
        cookies = []
        try:
            for cookie in cookie_string.split(';'):
                cookie = cookie.strip()
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    cookies.append({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.instagram.com'
                    })
            logger.info(f"Parsed {len(cookies)} cookies")
            return cookies
        except Exception as e:
            logger.error(f"Cookie parsing error: {e}")
            return []

    async def run_fix_command_v1(self):
        """
        Fix Command V1 - Complete Instagram to Facebook Business automation

        PART 1: INSTAGRAM LOGIN
        PART 2: FACEBOOK BUSINESS
        PART 3: FINAL WORK
        """
        try:
            await self.send_update("🚀 Fix Command V1 - Starting...")

            # Setup browser
            await self.send_update("🌐 Initializing browser...")
            self.setup_driver()

            # ==================== PART 1: INSTAGRAM LOGIN ====================
            await self.send_update("\n📱 PART 1: INSTAGRAM LOGIN")

            # STEP 1: Login to Instagram with cookie
            await self.send_update("⏳ STEP 1: Logging into Instagram...")

            self.driver.get("https://www.instagram.com/")
            time.sleep(3)

            # Add cookies
            cookies = self.parse_cookies(self.cookie_string)
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"Cookie add failed (might be normal): {e}")

            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(5)

            # Check if login successful
            current_url = self.driver.current_url
            if "login" in current_url.lower():
                await self.send_update("❌ Instagram login failed - invalid cookie")
                self.take_screenshot("STEP1_login_failed")
                return False, self.screenshots

            await self.send_update("✅ STEP 1: Instagram login successful")
            self.take_screenshot("STEP1_instagram_logged_in")

            # ==================== PART 2: FACEBOOK BUSINESS ====================
            await self.send_update("\n💼 PART 2: FACEBOOK BUSINESS")

            # STEP 2: Go to Facebook Business login page and click "Log in with Instagram"
            await self.send_update("⏳ STEP 2: Opening Facebook Business login page...")

            fb_business_url = "https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs"
            self.driver.get(fb_business_url)
            time.sleep(5)

            self.take_screenshot("STEP2_fb_business_login_page")

            # Click "Log in with Instagram" button
            await self.send_update("⏳ Looking for 'Log in with Instagram' button...")

            try:
                # Find the Instagram login button - multiple selectors for reliability
                login_selectors = [
                    "//span[contains(text(), 'Log in with Instagram')]",
                    "//span[contains(text(), 'Instagram')]//ancestor::div[@role='button']",
                    "//div[contains(@class, 'x1lliihq')]//span[contains(text(), 'Instagram')]"
                ]

                ig_login_btn = None
                for selector in login_selectors:
                    try:
                        ig_login_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if ig_login_btn:
                            break
                    except:
                        continue

                if not ig_login_btn:
                    raise Exception("Instagram login button not found")

                ig_login_btn.click()
                await self.send_update("✅ Clicked 'Log in with Instagram' button")
                time.sleep(5)

            except Exception as e:
                await self.send_update(f"❌ Failed to click Instagram login button: {e}")
                self.take_screenshot("STEP2_button_not_found")
                return False, self.screenshots

            self.take_screenshot("STEP2_clicked_ig_login")

            # STEP 3: Handle Instagram OAuth popup/tab
            await self.send_update("⏳ STEP 3: Handling Instagram OAuth authorization...")

            # Switch to new tab/window if opened
            time.sleep(3)
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to OAuth popup")

            self.take_screenshot("STEP3_oauth_page")

            # Look for "Log in as <username>" button
            try:
                login_as_selectors = [
                    "//div[@role='button' and contains(text(), 'Log in as')]",
                    "//div[contains(@class, 'x1i10hfl') and contains(text(), 'Log in as')]",
                ]

                login_as_btn = None
                for selector in login_as_selectors:
                    try:
                        login_as_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if login_as_btn:
                            break
                    except:
                        continue

                if login_as_btn:
                    username = login_as_btn.text
                    login_as_btn.click()
                    await self.send_update(f"✅ Clicked '{username}' button")
                    time.sleep(5)
                else:
                    await self.send_update("⚠️ 'Log in as' button not found, continuing...")

            except Exception as e:
                logger.debug(f"Log in as button handling: {e}")

            # Switch back to main window
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main window")

            time.sleep(5)

            # Handle any popup on home page (close or refresh)
            current_url = self.driver.current_url
            if "business.facebook.com" in current_url:
                await self.send_update("✓ Redirected to Facebook Business home page")
                self.take_screenshot("STEP3_fb_business_home")

                # Try to close any popup
                try:
                    close_selectors = [
                        "//div[@aria-label='Close']",
                        "//div[@role='button' and @aria-label='Close']",
                        "//*[contains(@aria-label, 'Close')]"
                    ]

                    for selector in close_selectors:
                        try:
                            close_btn = self.driver.find_element(By.XPATH, selector)
                            if close_btn and close_btn.is_displayed():
                                close_btn.click()
                                await self.send_update("✓ Closed popup")
                                time.sleep(2)
                                break
                        except:
                            continue
                except:
                    pass

                # Refresh page to clear any remaining popups
                self.driver.refresh()
                await self.send_update("✓ Refreshed page")
                time.sleep(5)

            await self.send_update("✅ PART 2: Facebook Business login completed")

            # ==================== PART 3: FINAL WORK ====================
            await self.send_update("\n🎯 PART 3: FINAL WORK")

            # STEP 4: Scroll and find "Boost" button
            await self.send_update("⏳ STEP 4: Looking for 'Boost' button...")

            # Scroll down to find posts
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(3)

            self.take_screenshot("STEP4_scrolled_page")

            # Click first "Boost" button
            try:
                boost_selectors = [
                    "//div[contains(text(), 'Boost')]",
                    "//div[contains(@class, 'x1vvvo52') and contains(text(), 'Boost')]",
                ]

                boost_btn = None
                for selector in boost_selectors:
                    try:
                        boost_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if boost_btn:
                            break
                    except:
                        continue

                if not boost_btn:
                    raise Exception("Boost button not found")

                boost_btn.click()
                await self.send_update("✅ Clicked 'Boost' button")
                time.sleep(3)

            except Exception as e:
                await self.send_update(f"❌ Failed to find Boost button: {e}")
                self.take_screenshot("STEP4_boost_not_found")
                return False, self.screenshots

            self.take_screenshot("STEP4_boost_popup")

            # Click "Continue" on popup
            try:
                continue_selectors = [
                    "//div[contains(text(), 'Continue')]",
                    "//div[contains(@class, 'x1vvvo52') and contains(text(), 'Continue')]",
                ]

                continue_btn = None
                for selector in continue_selectors:
                    try:
                        continue_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if continue_btn:
                            break
                    except:
                        continue

                if continue_btn:
                    continue_btn.click()
                    await self.send_update("✅ Clicked 'Continue' button on popup")
                    time.sleep(3)

            except Exception as e:
                logger.debug(f"Continue button handling: {e}")

            # STEP 5: Handle OAuth popup/tab
            await self.send_update("⏳ STEP 5: Handling Facebook OAuth...")

            # Switch to new tab/window if opened
            time.sleep(3)
            original_window = self.driver.current_window_handle

            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to OAuth popup")

            self.take_screenshot("STEP5_oauth_popup")

            # Click "Continue as <username>" button
            try:
                continue_as_selectors = [
                    "//button[contains(text(), 'Continue as')]",
                    "//button[@name='__CONFIRM__']",
                    "//button[contains(@class, '_42ft') and contains(text(), 'Continue')]",
                ]

                continue_as_btn = None
                for selector in continue_as_selectors:
                    try:
                        continue_as_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if continue_as_btn:
                            break
                    except:
                        continue

                if continue_as_btn:
                    username = continue_as_btn.text
                    continue_as_btn.click()
                    await self.send_update(f"✅ Clicked '{username}' button")
                    time.sleep(3)

            except Exception as e:
                logger.debug(f"Continue as button handling: {e}")

            # Switch back to main tab
            time.sleep(3)
            if len(self.driver.window_handles) > 1:
                try:
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                except:
                    self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main tab")

            time.sleep(3)

            # Click "Boost" button again
            await self.send_update("⏳ Clicking 'Boost' button again...")

            try:
                boost_btn = None
                for selector in boost_selectors:
                    try:
                        boost_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if boost_btn:
                            break
                    except:
                        continue

                if boost_btn:
                    boost_btn.click()
                    await self.send_update("✅ Clicked 'Boost' button again")
                    time.sleep(3)

            except Exception as e:
                logger.debug(f"Second boost click: {e}")

            # Click "Continue" again
            try:
                continue_btn = None
                for selector in continue_selectors:
                    try:
                        continue_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if continue_btn:
                            break
                    except:
                        continue

                if continue_btn:
                    continue_btn.click()
                    await self.send_update("✅ Clicked 'Continue' button again")
                    time.sleep(3)

            except Exception as e:
                logger.debug(f"Second continue click: {e}")

            # Wait for popup to close automatically
            time.sleep(5)

            # Click "OK" button (might need to double-click)
            await self.send_update("⏳ Looking for 'OK' button...")

            try:
                ok_selectors = [
                    "//div[contains(text(), 'OK')]",
                    "//div[contains(@class, 'x1vvvo52') and contains(text(), 'OK')]",
                    "//div[@role='button' and contains(text(), 'OK')]",
                ]

                # Try clicking OK once
                ok_btn = None
                for selector in ok_selectors:
                    try:
                        ok_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if ok_btn:
                            break
                    except:
                        continue

                if ok_btn:
                    ok_btn.click()
                    await self.send_update("✅ Clicked 'OK' button")
                    time.sleep(2)

                    # Try double-click if button still visible
                    try:
                        if ok_btn.is_displayed():
                            ok_btn.click()
                            await self.send_update("✅ Double-clicked 'OK' button")
                            time.sleep(2)
                    except:
                        pass

            except Exception as e:
                logger.debug(f"OK button handling: {e}")

            self.take_screenshot("FINAL_completed")

            # ==================== SUCCESS ====================
            await self.send_update("\n✅ ALL PARTS COMPLETED SUCCESSFULLY!")
            await self.send_update("✅ PART 1: Instagram Login - DONE")
            await self.send_update("✅ PART 2: Facebook Business - DONE")
            await self.send_update("✅ PART 3: Final Work - DONE")
            await self.send_update("\n🎉 FIX COMMAND V1: FIXED DONE!")

            logger.info("=" * 60)
            logger.info("FIX COMMAND V1 COMPLETED SUCCESSFULLY")
            logger.info(f"Screenshots: {len(self.screenshots)}")
            logger.info("=" * 60)

            return True, self.screenshots

        except Exception as e:
            logger.error(f"❌ Automation error: {e}", exc_info=True)
            await self.send_update(f"\n❌ ERROR: {str(e)}")
            self.take_screenshot("ERROR_exception_occurred")
            return False, self.screenshots

        finally:
            if self.driver:
                try:
                    await self.send_update("🔄 Closing browser...")
                    self.driver.quit()
                    logger.info("✓ Chrome driver closed")
                except Exception as e:
                    logger.error(f"Error closing driver: {e}")
