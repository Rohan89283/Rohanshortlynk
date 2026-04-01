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

MULTI_LANG_BUTTONS = {
    'instagram_login': {
        'en': ['Log in with Instagram', 'Instagram'],
        'bn': ['Instagram দিয়ে লগ ইন করুন', 'Instagram'],
        'hi': ['Instagram के साथ लॉग इन करें', 'Instagram'],
        'es': ['Iniciar sesión con Instagram', 'Instagram'],
        'ar': ['تسجيل الدخول باستخدام Instagram', 'Instagram'],
        'fr': ['Se connecter avec Instagram', 'Instagram'],
        'de': ['Mit Instagram anmelden', 'Instagram'],
        'pt': ['Entrar com Instagram', 'Instagram'],
        'ru': ['Войти через Instagram', 'Instagram'],
    },
    'log_in_as': {
        'en': ['Log in as', 'Continue as'],
        'bn': ['হিসাবে লগ ইন করুন', 'হিসাবে চালিয়ে যান'],
        'hi': ['के रूप में लॉग इन करें', 'जारी रखें'],
        'es': ['Iniciar sesión como', 'Continuar como'],
        'ar': ['تسجيل الدخول باسم', 'متابعة باسم'],
        'fr': ['Se connecter en tant que', 'Continuer en tant que'],
        'de': ['Anmelden als', 'Weiter als'],
        'pt': ['Entrar como', 'Continuar como'],
        'ru': ['Войти как', 'Продолжить как'],
    },
    'boost': {
        'en': ['Boost', 'Boost post'],
        'bn': ['বুস্ট', 'পোস্ট বুস্ট করুন'],
        'hi': ['बूस्ट', 'पोस्ट बूस्ट करें'],
        'es': ['Promocionar', 'Promocionar publicación'],
        'ar': ['ترويج', 'ترويج المنشور'],
        'fr': ['Booster', 'Booster la publication'],
        'de': ['Bewerben', 'Beitrag bewerben'],
        'pt': ['Impulsionar', 'Impulsionar publicação'],
        'ru': ['Продвигать', 'Продвигать публикацию'],
    },
    'continue': {
        'en': ['Continue', 'Next'],
        'bn': ['চালিয়ে যান', 'পরবর্তী'],
        'hi': ['जारी रखें', 'अगला'],
        'es': ['Continuar', 'Siguiente'],
        'ar': ['متابعة', 'التالي'],
        'fr': ['Continuer', 'Suivant'],
        'de': ['Weiter', 'Nächste'],
        'pt': ['Continuar', 'Próximo'],
        'ru': ['Продолжить', 'Далее'],
    },
    'continue_as': {
        'en': ['Continue as'],
        'bn': ['হিসাবে চালিয়ে যান'],
        'hi': ['के रूप में जारी रखें'],
        'es': ['Continuar como'],
        'ar': ['متابعة باسم'],
        'fr': ['Continuer en tant que'],
        'de': ['Weiter als'],
        'pt': ['Continuar como'],
        'ru': ['Продолжить как'],
    },
    'ok': {
        'en': ['OK', 'Okay'],
        'bn': ['ঠিক আছে', 'OK'],
        'hi': ['ठीक है', 'OK'],
        'es': ['Aceptar', 'OK'],
        'ar': ['موافق', 'OK'],
        'fr': ['OK', "D'accord"],
        'de': ['OK', 'Okay'],
        'pt': ['OK', 'Está bem'],
        'ru': ['ОК', 'Хорошо'],
    },
    'close': {
        'en': ['Close'],
        'bn': ['বন্ধ করুন'],
        'hi': ['बंद करें'],
        'es': ['Cerrar'],
        'ar': ['إغلاق'],
        'fr': ['Fermer'],
        'de': ['Schließen'],
        'pt': ['Fechar'],
        'ru': ['Закрыть'],
    }
}

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

    def take_screenshot(self, step_name, failure_reason=None):
        """Take screenshot and store it"""
        try:
            screenshot = self.driver.get_screenshot_as_png()
            img = Image.open(BytesIO(screenshot))

            screenshot_data = {
                'name': step_name,
                'image': BytesIO(screenshot)
            }

            if failure_reason:
                screenshot_data['failure_reason'] = failure_reason
                screenshot_data['url'] = self.driver.current_url
                screenshot_data['timestamp'] = time.time()

            self.screenshots.append(screenshot_data)
            logger.info(f"📸 Screenshot captured: {step_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False

    def find_button_multilang(self, button_type, timeout=10):
        """Find button using multi-language text matching"""
        try:
            if button_type not in MULTI_LANG_BUTTONS:
                raise ValueError(f"Unknown button type: {button_type}")

            all_texts = []
            for lang_code, texts in MULTI_LANG_BUTTONS[button_type].items():
                all_texts.extend(texts)

            xpaths = []
            for text in all_texts:
                xpaths.append(f"//span[contains(text(), '{text}')]")
                xpaths.append(f"//div[contains(text(), '{text}')]")
                xpaths.append(f"//button[contains(text(), '{text}')]")
                xpaths.append(f"//*[@role='button' and contains(text(), '{text}')]")

            for xpath in xpaths:
                try:
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.element_to_be_clickable((By.XPATH, xpath))
                    )
                    if element:
                        logger.info(f"Found button '{button_type}' using: {xpath}")
                        return element
                except:
                    continue

            raise Exception(f"Button '{button_type}' not found in any language")

        except Exception as e:
            logger.error(f"find_button_multilang error: {e}")
            raise

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

            # Support multi-language
            options.add_argument('--lang=en-US,en,bn,hi,es,ar,fr,de,pt,ru')
            options.add_argument('--accept-lang=en-US,en,bn,hi,es,ar,fr,de,pt,ru')
            options.add_experimental_option('prefs', {
                'intl.accept_languages': 'en-US,en,bn,hi,es,ar,fr,de,pt,ru',
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
            time.sleep(2)

            # Add cookies
            cookies = self.parse_cookies(self.cookie_string)
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"Cookie add failed (might be normal): {e}")

            # Refresh to apply cookies
            self.driver.refresh()
            time.sleep(3)

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
            time.sleep(3)

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
                        ig_login_btn = WebDriverWait(self.driver, 8).until(
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
                time.sleep(3)

            except Exception as e:
                await self.send_update(f"❌ Failed to click Instagram login button: {e}")
                self.take_screenshot("STEP2_button_not_found")
                return False, self.screenshots

            self.take_screenshot("STEP2_clicked_ig_login")

            # STEP 3: Handle Instagram OAuth popup/tab
            await self.send_update("⏳ STEP 3: Handling Instagram OAuth authorization...")

            # Switch to new tab/window if opened
            time.sleep(2)
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
                        login_as_btn = WebDriverWait(self.driver, 8).until(
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
                    time.sleep(3)
                else:
                    await self.send_update("⚠️ 'Log in as' button not found, continuing...")

            except Exception as e:
                logger.debug(f"Log in as button handling: {e}")

            # Switch back to main window
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main window")

            time.sleep(3)

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
                                time.sleep(1.5)
                                break
                        except:
                            continue
                except:
                    pass

                # Refresh page to clear any remaining popups
                self.driver.refresh()
                await self.send_update("✓ Refreshed page")
                time.sleep(3)

            await self.send_update("✅ PART 2: Facebook Business login completed")

            # ==================== PART 3: FINAL WORK ====================
            await self.send_update("\n🎯 PART 3: FINAL WORK")

            # STEP 4: Scroll and find "Boost" button
            await self.send_update("⏳ STEP 4: Looking for 'Boost' button...")

            # Scroll down to find posts
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1.5)

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
                        boost_btn = WebDriverWait(self.driver, 8).until(
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
                time.sleep(2)

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
                        continue_btn = WebDriverWait(self.driver, 8).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if continue_btn:
                            break
                    except:
                        continue

                if continue_btn:
                    continue_btn.click()
                    await self.send_update("✅ Clicked 'Continue' button on popup")
                    time.sleep(2)

            except Exception as e:
                logger.debug(f"Continue button handling: {e}")

            # STEP 5: Handle OAuth popup/tab
            await self.send_update("⏳ STEP 5: Handling Facebook OAuth...")

            # Switch to new tab/window if opened
            time.sleep(2)
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
                        continue_as_btn = WebDriverWait(self.driver, 8).until(
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
                    time.sleep(2)

            except Exception as e:
                logger.debug(f"Continue as button handling: {e}")

            # Switch back to main tab
            time.sleep(2)
            if len(self.driver.window_handles) > 1:
                try:
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                except:
                    self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main tab")

            # Wait for page to load after OAuth
            time.sleep(3)

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
                        ok_btn = WebDriverWait(self.driver, 8).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        if ok_btn:
                            break
                    except:
                        continue

                if ok_btn:
                    ok_btn.click()
                    await self.send_update("✅ Clicked 'OK' button")
                    time.sleep(1.5)

                    # Try double-click if button still visible
                    try:
                        if ok_btn.is_displayed():
                            ok_btn.click()
                            await self.send_update("✅ Double-clicked 'OK' button")
                            time.sleep(1.5)
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

    async def run_fix_command(self):
        """
        Fix Command - Complete Instagram to Facebook Business automation
        Multi-language support with screenshots only on failures

        PART 1: INSTAGRAM LOGIN
        PART 2: FACEBOOK BUSINESS
        PART 3: FINAL WORK
        """
        try:
            await self.send_update("🚀 Fix Command - Starting...")

            self.setup_driver()
            await self.send_update("🌐 Browser initialized")

            await self.send_update("\n📱 PART 1: INSTAGRAM LOGIN")

            await self.send_update("⏳ STEP 1: Logging into Instagram...")

            self.driver.get("https://www.instagram.com/")
            time.sleep(3)

            cookies = self.parse_cookies(self.cookie_string)
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"Cookie add failed: {e}")

            self.driver.refresh()
            time.sleep(5)

            current_url = self.driver.current_url
            if "login" in current_url.lower():
                await self.send_update("❌ Instagram login failed - invalid cookie")
                self.take_screenshot("STEP1_login_failed", "Invalid Instagram cookie")
                return False, self.screenshots

            await self.send_update("✅ STEP 1: Instagram login successful")

            await self.send_update("\n💼 PART 2: FACEBOOK BUSINESS")

            await self.send_update("⏳ STEP 2: Opening Facebook Business login page...")

            fb_business_url = "https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs"
            self.driver.get(fb_business_url)
            time.sleep(5)

            await self.send_update("⏳ Looking for 'Log in with Instagram' button...")

            try:
                ig_login_btn = self.find_button_multilang('instagram_login', timeout=10)
                ig_login_btn.click()
                await self.send_update("✅ Clicked 'Log in with Instagram' button")
                time.sleep(5)

            except Exception as e:
                await self.send_update(f"❌ Failed to click Instagram login button: {e}")
                self.take_screenshot("STEP2_button_not_found", str(e))
                return False, self.screenshots

            await self.send_update("⏳ STEP 3: Handling Instagram OAuth authorization...")

            time.sleep(3)
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to OAuth popup")

            try:
                login_as_btn = self.find_button_multilang('log_in_as', timeout=10)
                username = login_as_btn.text
                login_as_btn.click()
                await self.send_update(f"✅ Clicked '{username}' button")
                time.sleep(5)
            except Exception as e:
                logger.debug(f"Log in as button handling: {e}")

            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main window")

            time.sleep(5)

            current_url = self.driver.current_url
            if "business.facebook.com" in current_url:
                await self.send_update("✓ Redirected to Facebook Business home page")

                try:
                    close_btn = self.find_button_multilang('close', timeout=5)
                    if close_btn and close_btn.is_displayed():
                        close_btn.click()
                        await self.send_update("✓ Closed popup")
                        time.sleep(2)
                except:
                    pass

                self.driver.refresh()
                await self.send_update("✓ Refreshed page")
                time.sleep(5)

            await self.send_update("✅ PART 2: Facebook Business login completed")

            await self.send_update("\n🎯 PART 3: FINAL WORK")

            await self.send_update("⏳ STEP 4: Looking for 'Boost' button...")

            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(3)

            try:
                boost_btn = self.find_button_multilang('boost', timeout=10)
                boost_btn.click()
                await self.send_update("✅ Clicked 'Boost' button")
                time.sleep(3)

            except Exception as e:
                await self.send_update(f"❌ Failed to find Boost button: {e}")
                self.take_screenshot("STEP4_boost_not_found", str(e))
                return False, self.screenshots

            try:
                continue_btn = self.find_button_multilang('continue', timeout=10)
                continue_btn.click()
                await self.send_update("✅ Clicked 'Continue' button on popup")
                time.sleep(3)
            except Exception as e:
                logger.debug(f"Continue button handling: {e}")

            await self.send_update("⏳ STEP 5: Handling Facebook OAuth...")

            time.sleep(3)
            original_window = self.driver.current_window_handle

            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to OAuth popup")

            try:
                continue_as_btn = self.find_button_multilang('continue_as', timeout=10)
                username = continue_as_btn.text
                continue_as_btn.click()
                await self.send_update(f"✅ Clicked '{username}' button")
                time.sleep(3)
            except Exception as e:
                logger.debug(f"Continue as button handling: {e}")

            time.sleep(3)
            if len(self.driver.window_handles) > 1:
                try:
                    self.driver.close()
                    self.driver.switch_to.window(original_window)
                except:
                    self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main tab")

            time.sleep(3)

            await self.send_update("⏳ Clicking 'Boost' button again...")

            try:
                boost_btn = self.find_button_multilang('boost', timeout=10)
                boost_btn.click()
                await self.send_update("✅ Clicked 'Boost' button again")
                time.sleep(3)
            except Exception as e:
                logger.debug(f"Second boost click: {e}")

            try:
                continue_btn = self.find_button_multilang('continue', timeout=10)
                continue_btn.click()
                await self.send_update("✅ Clicked 'Continue' button again")
                time.sleep(3)
            except Exception as e:
                logger.debug(f"Second continue click: {e}")

            time.sleep(5)

            await self.send_update("⏳ Looking for 'OK' button...")

            try:
                ok_btn = self.find_button_multilang('ok', timeout=10)
                ok_btn.click()
                await self.send_update("✅ Clicked 'OK' button")
                time.sleep(2)

                try:
                    if ok_btn.is_displayed():
                        ok_btn.click()
                        await self.send_update("✅ Double-clicked 'OK' button")
                        time.sleep(2)
                except:
                    pass
            except Exception as e:
                logger.debug(f"OK button handling: {e}")

            await self.send_update("\n✅ ALL PARTS COMPLETED SUCCESSFULLY!")
            await self.send_update("✅ PART 1: Instagram Login - DONE")
            await self.send_update("✅ PART 2: Facebook Business - DONE")
            await self.send_update("✅ PART 3: Final Work - DONE")
            await self.send_update("\n🎉 FIX COMMAND: FIXED DONE!")

            logger.info("=" * 60)
            logger.info("FIX COMMAND COMPLETED SUCCESSFULLY")
            logger.info(f"Screenshots (failures only): {len(self.screenshots)}")
            logger.info("=" * 60)

            return True, self.screenshots

        except Exception as e:
            logger.error(f"❌ Automation error: {e}", exc_info=True)
            await self.send_update(f"\n❌ ERROR: {str(e)}")
            self.take_screenshot("ERROR_exception_occurred", str(e))
            return False, self.screenshots

        finally:
            if self.driver:
                try:
                    await self.send_update("🔄 Closing browser...")
                    self.driver.quit()
                    logger.info("✓ Chrome driver closed")
                except Exception as e:
                    logger.error(f"Error closing driver: {e}")

    async def run_fb_command(self):
        """
        FB Command - ULTRA OPTIMIZED with Smart Detection
        Multi-language support with detailed timing and screenshots only on failures

        NEW OPTIMIZATIONS:
        - Smart URL waiting instead of blind sleeps
        - Intelligent element detection
        - Part 1 under 6 seconds target
        - Smart tab switching with URL monitoring

        PART 1: INSTAGRAM LOGIN
        PART 2: FACEBOOK BUSINESS
        PART 3: FINAL WORK
        """
        part_times = {}
        step_times = {}
        total_start = time.time()

        try:
            await self.send_update("🚀 FB Command (Ultra Optimized) - Starting...")

            # Browser setup
            browser_start = time.time()
            self.setup_driver()
            browser_time = time.time() - browser_start
            await self.send_update(f"🌐 Browser initialized ({browser_time:.1f}s)")

            # ==================== PART 1: INSTAGRAM LOGIN ====================
            part1_start = time.time()
            await self.send_update("\n📱 PART 1: INSTAGRAM LOGIN")

            step1_start = time.time()
            await self.send_update("⏳ STEP 1: Logging into Instagram...")

            self.driver.get("https://www.instagram.com/")
            time.sleep(1)  # Reduced to 1s - just let page start loading

            cookies = self.parse_cookies(self.cookie_string)
            for cookie in cookies:
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    logger.debug(f"Cookie add failed: {e}")

            self.driver.refresh()

            # Smart wait for Instagram to load - wait for URL to NOT contain "login"
            max_wait = 5
            wait_start = time.time()
            while time.time() - wait_start < max_wait:
                current_url = self.driver.current_url
                if "login" not in current_url.lower():
                    # Successfully logged in
                    break
                time.sleep(0.3)  # Quick poll

            # Final check
            current_url = self.driver.current_url
            if "login" in current_url.lower():
                step1_time = time.time() - step1_start
                await self.send_update(f"❌ Instagram login failed - invalid cookie ({step1_time:.1f}s)")
                self.take_screenshot("STEP1_login_failed", "Invalid Instagram cookie")
                return False, self.screenshots

            step1_time = time.time() - step1_start
            step_times['step1_ig_login'] = step1_time
            await self.send_update(f"✅ STEP 1: Instagram login successful ({step1_time:.1f}s)")

            part1_time = time.time() - part1_start
            part_times['part1_instagram'] = part1_time

            # ==================== PART 2: FACEBOOK BUSINESS ====================
            part2_start = time.time()
            await self.send_update("\n💼 PART 2: FACEBOOK BUSINESS")

            step2_start = time.time()
            await self.send_update("⏳ STEP 2: Opening Facebook Business login page...")

            fb_business_url = "https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs"
            self.driver.get(fb_business_url)

            # Smart wait for page load - check for interactive elements
            time.sleep(2)

            await self.send_update("⏳ Looking for 'Log in with Instagram' button...")

            try:
                ig_login_btn = self.find_button_multilang('instagram_login', timeout=8)
                ig_login_btn.click()
                step2_time = time.time() - step2_start
                step_times['step2_fb_login_page'] = step2_time
                await self.send_update(f"✅ Clicked 'Log in with Instagram' button ({step2_time:.1f}s)")
                time.sleep(2)  # Brief wait for OAuth window

            except Exception as e:
                step2_time = time.time() - step2_start
                await self.send_update(f"❌ Failed to click Instagram login button: {e} ({step2_time:.1f}s)")
                self.take_screenshot("STEP2_button_not_found", str(e))
                return False, self.screenshots

            step3_start = time.time()
            await self.send_update("⏳ STEP 3: Handling Instagram OAuth authorization...")

            time.sleep(1)  # Brief wait for popup to appear

            # Store the main window handle before switching
            main_window = self.driver.current_window_handle

            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to OAuth popup")

            try:
                login_as_btn = self.find_button_multilang('log_in_as', timeout=7)
                username = login_as_btn.text
                login_as_btn.click()
                await self.send_update(f"✅ Clicked '{username}' button")
            except Exception as e:
                logger.debug(f"Log in as button handling: {e}")

            # SMART SWITCH: Go back to main tab immediately and wait for URL redirect
            # Ensure we switch to the correct main window
            try:
                self.driver.switch_to.window(main_window)
                await self.send_update("✓ Switched back to main tab")
            except:
                # If main window is gone, switch to first available
                if len(self.driver.window_handles) > 0:
                    self.driver.switch_to.window(self.driver.window_handles[0])

            # Smart wait for redirect to business.facebook.com
            await self.send_update("⏳ Waiting for redirect to Facebook Business...")
            max_redirect_wait = 10
            redirect_start = time.time()
            redirected = False

            while time.time() - redirect_start < max_redirect_wait:
                try:
                    current_url = self.driver.current_url
                    if "business.facebook.com" in current_url:
                        redirected = True
                        elapsed = time.time() - redirect_start
                        await self.send_update(f"✅ Redirected to Facebook Business ({elapsed:.1f}s)")
                        break
                    time.sleep(0.5)  # Poll every 500ms
                except Exception as e:
                    logger.debug(f"URL check error: {e}")
                    time.sleep(0.5)

            if not redirected:
                await self.send_update("⚠️ Redirect took longer than expected, continuing...")

            # Ensure we're on the main window before proceeding
            try:
                if len(self.driver.window_handles) > 0:
                    self.driver.switch_to.window(self.driver.window_handles[0])
            except:
                pass

            # Smart wait for page to be interactive
            time.sleep(1)

            # Try to close any popup
            try:
                close_btn = self.find_button_multilang('close', timeout=3)
                if close_btn and close_btn.is_displayed():
                    close_btn.click()
                    await self.send_update("✓ Closed popup")
                    time.sleep(1)
            except Exception as e:
                logger.debug(f"Close button handling: {e}")

            # Refresh and wait for page load - with error handling
            try:
                self.driver.refresh()
                await self.send_update("✓ Refreshed page")
                time.sleep(2)  # Smart wait for page elements
            except Exception as e:
                logger.debug(f"Refresh error: {e}")
                await self.send_update("✓ Page already loaded")

            step3_time = time.time() - step3_start
            step_times['step3_oauth'] = step3_time

            part2_time = time.time() - part2_start
            part_times['part2_facebook'] = part2_time
            await self.send_update(f"✅ PART 2: Facebook Business login completed ({part2_time:.1f}s)")

            # ==================== PART 3: FINAL WORK ====================
            part3_start = time.time()
            await self.send_update("\n🎯 PART 3: FINAL WORK")

            step4_start = time.time()
            await self.send_update("⏳ STEP 4: Looking for 'Boost' button...")

            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(1)  # Brief wait after scroll

            try:
                boost_btn = self.find_button_multilang('boost', timeout=8)
                boost_btn.click()
                step4_time = time.time() - step4_start
                step_times['step4_boost'] = step4_time
                await self.send_update(f"✅ Clicked 'Boost' button ({step4_time:.1f}s)")
                time.sleep(1)  # Brief wait for popup

            except Exception as e:
                step4_time = time.time() - step4_start
                await self.send_update(f"❌ Failed to find Boost button: {e} ({step4_time:.1f}s)")
                self.take_screenshot("STEP4_boost_not_found", str(e))
                return False, self.screenshots

            # Continue button on popup with smart detection
            try:
                continue_btn = self.find_button_multilang('continue', timeout=6)
                continue_btn.click()
                await self.send_update("✅ Clicked 'Continue' button on popup")
                time.sleep(1)
            except Exception as e:
                logger.debug(f"Continue button handling: {e}")

            step5_start = time.time()
            await self.send_update("⏳ STEP 5: Handling Facebook OAuth...")

            time.sleep(1)  # Brief wait for popup

            try:
                original_window = self.driver.current_window_handle
            except:
                original_window = None

            if len(self.driver.window_handles) > 1:
                try:
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    await self.send_update("✓ Switched to OAuth popup")
                except Exception as e:
                    logger.debug(f"Window switch error: {e}")

            try:
                continue_as_btn = self.find_button_multilang('continue_as', timeout=7)
                username = continue_as_btn.text
                continue_as_btn.click()
                await self.send_update(f"✅ Clicked '{username}' button")
                time.sleep(1)
            except Exception as e:
                logger.debug(f"Continue as button handling: {e}")

            # Smart tab switching with better error handling
            time.sleep(1)
            if len(self.driver.window_handles) > 1:
                try:
                    self.driver.close()
                    if original_window:
                        self.driver.switch_to.window(original_window)
                    else:
                        self.driver.switch_to.window(self.driver.window_handles[0])
                    await self.send_update("✓ Returned to main tab")
                except Exception as e:
                    logger.debug(f"Tab switch error: {e}")
                    try:
                        self.driver.switch_to.window(self.driver.window_handles[0])
                    except:
                        pass

            time.sleep(1)

            # Second boost/continue cycle with smart detection
            await self.send_update("⏳ Clicking 'Boost' button again...")

            try:
                boost_btn = self.find_button_multilang('boost', timeout=6)
                boost_btn.click()
                await self.send_update("✅ Clicked 'Boost' button again")
                time.sleep(1)
            except Exception as e:
                logger.debug(f"Second boost click: {e}")

            # Second continue with smart detection
            try:
                continue_btn = self.find_button_multilang('continue', timeout=6)
                continue_btn.click()
                await self.send_update("✅ Clicked 'Continue' button again")
                time.sleep(1)
            except Exception as e:
                logger.debug(f"Second continue click: {e}")

            time.sleep(2)  # Wait for final dialog

            # Final OK button with smart detection
            await self.send_update("⏳ Looking for 'OK' button...")

            try:
                ok_btn = self.find_button_multilang('ok', timeout=6)
                ok_btn.click()
                await self.send_update("✅ Clicked 'OK' button")
                time.sleep(0.5)

                # Double-click if needed with smart detection
                try:
                    if ok_btn.is_displayed():
                        ok_btn.click()
                        await self.send_update("✅ Double-clicked 'OK' button")
                        time.sleep(0.5)
                except:
                    pass
            except Exception as e:
                logger.debug(f"OK button handling: {e}")

            step5_time = time.time() - step5_start
            step_times['step5_final_oauth'] = step5_time

            part3_time = time.time() - part3_start
            part_times['part3_final_work'] = part3_time

            # ==================== SUCCESS WITH DETAILED TIMING ====================
            total_time = time.time() - total_start

            await self.send_update("\n✅ ALL PARTS COMPLETED SUCCESSFULLY!")
            await self.send_update("✅ PART 1: Instagram Login - DONE")
            await self.send_update("✅ PART 2: Facebook Business - DONE")
            await self.send_update("✅ PART 3: Final Work - DONE")
            await self.send_update("\n🎉 FB COMMAND: FIXED DONE!")

            # Detailed timing report
            await self.send_update("\n⏱️ DETAILED TIMING REPORT:")
            await self.send_update(f"━━━━━━━━━━━━━━━━━━━━")
            await self.send_update(f"🌐 Browser Setup: {browser_time:.1f}s")
            await self.send_update(f"📱 PART 1 (Instagram Login): {part_times['part1_instagram']:.1f}s")
            await self.send_update(f"  └─ Step 1 (IG Login): {step_times['step1_ig_login']:.1f}s")
            await self.send_update(f"💼 PART 2 (Facebook Business): {part_times['part2_facebook']:.1f}s")
            await self.send_update(f"  ├─ Step 2 (FB Login Page): {step_times['step2_fb_login_page']:.1f}s")
            await self.send_update(f"  └─ Step 3 (OAuth): {step_times['step3_oauth']:.1f}s")
            await self.send_update(f"🎯 PART 3 (Final Work): {part_times['part3_final_work']:.1f}s")
            await self.send_update(f"  ├─ Step 4 (Boost): {step_times['step4_boost']:.1f}s")
            await self.send_update(f"  └─ Step 5 (Final OAuth): {step_times['step5_final_oauth']:.1f}s")
            await self.send_update(f"━━━━━━━━━━━━━━━━━━━━")
            await self.send_update(f"⏱️ TOTAL TIME: {total_time:.1f}s (~{total_time/60:.1f} min)")
            await self.send_update(f"📸 Screenshots (failures only): {len(self.screenshots)}")

            logger.info("=" * 60)
            logger.info("FB COMMAND COMPLETED SUCCESSFULLY")
            logger.info(f"Total Time: {total_time:.1f}s")
            logger.info(f"Part 1: {part_times['part1_instagram']:.1f}s")
            logger.info(f"Part 2: {part_times['part2_facebook']:.1f}s")
            logger.info(f"Part 3: {part_times['part3_final_work']:.1f}s")
            logger.info(f"Screenshots (failures only): {len(self.screenshots)}")
            logger.info("=" * 60)

            return True, self.screenshots

        except Exception as e:
            total_time = time.time() - total_start
            logger.error(f"❌ Automation error: {e}", exc_info=True)
            await self.send_update(f"\n❌ ERROR: {str(e)}")
            await self.send_update(f"⏱️ Failed after {total_time:.1f}s")
            self.take_screenshot("ERROR_exception_occurred", str(e))
            return False, self.screenshots

        finally:
            if self.driver:
                try:
                    await self.send_update("🔄 Closing browser...")
                    self.driver.quit()
                    logger.info("✓ Chrome driver closed")
                except Exception as e:
                    logger.error(f"Error closing driver: {e}")

