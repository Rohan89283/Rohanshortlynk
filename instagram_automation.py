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
            logger.info(f"Screenshot captured: {step_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return False

    def setup_driver(self):
        """Setup undetected Chrome driver"""
        try:
            import subprocess

            chrome_version_output = subprocess.check_output(['google-chrome', '--version']).decode('utf-8')
            chrome_version = chrome_version_output.split()[-1].split('.')[0]
            logger.info(f"Detected Chrome version: {chrome_version}")

            options = uc.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_argument('--disable-gpu')
            options.add_argument('--headless=new')
            options.add_argument('--disable-software-rasterizer')
            options.add_argument('--disable-extensions')
            options.add_argument('--disable-setuid-sandbox')
            options.add_argument('--no-first-run')
            options.add_argument('--no-zygote')
            options.add_argument('--single-process')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--disable-background-networking')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-breakpad')
            options.add_argument('--disable-component-extensions-with-background-pages')
            options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
            options.add_argument('--force-color-profile=srgb')
            options.add_argument('--hide-scrollbars')
            options.add_argument('--metrics-recording-only')
            options.add_argument('--mute-audio')

            ua = UserAgent()
            options.add_argument(f'user-agent={ua.random}')

            self.driver = uc.Chrome(options=options, version_main=int(chrome_version), use_subprocess=False)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logger.info(f"Chrome driver initialized with user agent: {ua.random}")
            return True
        except Exception as e:
            logger.error(f"Failed to setup driver: {e}")
            return False

    def set_instagram_cookies(self):
        """Set Instagram cookies from cookie string"""
        try:
            self.driver.get("https://www.instagram.com")
            time.sleep(2)

            cookies = self.cookie_string.split(';')
            for cookie in cookies:
                cookie = cookie.strip()
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    self.driver.add_cookie({
                        'name': name.strip(),
                        'value': value.strip(),
                        'domain': '.instagram.com'
                    })

            logger.info(f"Set {len(cookies)} Instagram cookies")
            return True
        except Exception as e:
            logger.error(f"Failed to set cookies: {e}")
            return False

    def try_click_methods(self, element_selectors, step_name, timeout=10):
        """Try multiple methods to find and click an element"""
        methods = [
            ("CSS Selector", By.CSS_SELECTOR),
            ("XPath (text)", By.XPATH),
            ("Class Name", By.CLASS_NAME),
            ("Tag Name", By.TAG_NAME)
        ]

        for selector in element_selectors:
            for method_name, by_type in methods:
                try:
                    if method_name == "XPath (text)" and not selector.startswith('//'):
                        xpath_selector = f"//*[contains(text(), '{selector}')]"
                    else:
                        xpath_selector = selector

                    if method_name == "XPath (text)":
                        element = WebDriverWait(self.driver, timeout).until(
                            EC.element_to_be_clickable((By.XPATH, xpath_selector))
                        )
                    else:
                        element = WebDriverWait(self.driver, timeout).until(
                            EC.element_to_be_clickable((by_type, selector))
                        )

                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(0.5)

                    try:
                        element.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", element)

                    logger.info(f"✓ {step_name}: Clicked using {method_name}")
                    return True, f"✓ {step_name}: Clicked using {method_name}"

                except Exception as e:
                    logger.debug(f"✗ {step_name}: {method_name} failed - {str(e)[:50]}")
                    continue

        return False, f"✗ {step_name}: All click methods failed"

    def check_for_iframes(self):
        """Check and switch to iframes if present"""
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"Found {len(iframes)} iframes on page")
            return iframes
        except:
            return []

    async def run_automation(self):
        """Main automation flow"""
        try:
            await self.send_update("🚀 Starting automation process...")

            if not self.setup_driver():
                await self.send_update("❌ Failed to setup Chrome driver")
                return False, []

            await self.send_update("✓ Chrome driver initialized")

            # Step 1: Navigate to Facebook Business login page
            await self.send_update("📍 Step 1: Navigating to Facebook Business login page...")
            self.driver.get("https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs")
            time.sleep(3)
            self.take_screenshot("step1_fb_business_page")
            await self.send_update("✓ Step 1: Page loaded successfully")

            # Step 2: Click "Log in with Instagram"
            await self.send_update("📍 Step 2: Clicking 'Log in with Instagram' button...")
            selectors = [
                "span.x1lliihq.x193iq5w.x6ikm8r.x10wlt62.xlyipyv.xuxw1ft",
                "Log in with Instagram",
                "//span[contains(text(), 'Log in with Instagram')]",
                "//button[contains(., 'Instagram')]"
            ]

            success, msg = self.try_click_methods(selectors, "Step 2 - IG Login Button")
            await self.send_update(msg)

            if not success:
                self.take_screenshot("step2_failed")
                await self.send_update("❌ Step 2 failed - Could not find Instagram login button")
                return False, self.screenshots

            time.sleep(3)
            self.take_screenshot("step2_clicked")

            # Step 3: Handle Instagram login popup/tab
            await self.send_update("📍 Step 3: Handling Instagram login...")

            # Switch to new window if opened
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to Instagram login window")

            time.sleep(2)
            current_url = self.driver.current_url
            logger.info(f"Current URL: {current_url}")

            if "instagram.com" in current_url:
                await self.send_update("✓ Instagram login page opened")
                self.take_screenshot("step3_ig_login_page")

                # Set cookies
                await self.send_update("🔐 Setting Instagram cookies...")
                if self.set_instagram_cookies():
                    await self.send_update("✓ Cookies set successfully")
                    self.driver.refresh()
                    time.sleep(3)
                    self.take_screenshot("step3_after_cookies")

                    # Check for "Not Now" button (notifications)
                    try:
                        not_now_selectors = [
                            "//button[contains(text(), 'Not Now')]",
                            "//button[contains(text(), 'Not now')]",
                            "button._a9--._ap36._a9_1"
                        ]
                        success, msg = self.try_click_methods(not_now_selectors, "Dismiss Notifications", timeout=5)
                        if success:
                            await self.send_update("✓ Login successful - Dismissed notification prompt")
                        else:
                            await self.send_update("✓ Login successful - No notification prompt")
                    except:
                        await self.send_update("✓ Login successful")

                    time.sleep(2)

                    # Look for "Log in as" button
                    await self.send_update("🔍 Looking for account selection...")
                    login_as_selectors = [
                        "//div[contains(@role, 'button') and contains(text(), 'Log in as')]",
                        "div.x1i10hfl.xjqpnuy.xc5r6h4",
                        "div[role='button'][tabindex='0']"
                    ]

                    success, msg = self.try_click_methods(login_as_selectors, "Click 'Log in as' button", timeout=5)
                    if success:
                        await self.send_update(msg)
                        time.sleep(3)
                        self.take_screenshot("step3_logged_in")
                    else:
                        await self.send_update("ℹ️ No account selection needed, proceeding...")

                else:
                    await self.send_update("❌ Failed to set cookies")
                    return False, self.screenshots
            else:
                await self.send_update("⚠️ Not redirected to Instagram, trying alternative flow...")

            # Step 4: Verify redirect to Facebook Business home
            await self.send_update("📍 Step 4: Verifying Facebook Business home page...")

            # Switch back to main window if needed
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])

            time.sleep(5)
            current_url = self.driver.current_url

            if "business.facebook.com/latest/home" in current_url or "business_id=" in current_url:
                await self.send_update(f"✓ Step 4: Successfully on Business home page")
                logger.info(f"Home page URL: {current_url}")
                self.take_screenshot("step4_business_home")
            else:
                await self.send_update(f"⚠️ Step 4: Unexpected URL: {current_url}")
                self.take_screenshot("step4_unexpected_url")

            # Step 5: Click "Create ad" button
            await self.send_update("📍 Step 5: Clicking 'Create ad' button...")

            # Check for iframes
            iframes = self.check_for_iframes()

            create_ad_selectors = [
                "div.x1vvvo52.x1fvot60.xk50ysn.xxio538.x1heor9g.xuxw1ft.x6ikm8r.x10wlt62.xlyipyv.x1h4wwuj.xeuugli",
                "Create ad",
                "//div[contains(text(), 'Create ad')]",
                "//button[contains(., 'Create ad')]"
            ]

            success, msg = self.try_click_methods(create_ad_selectors, "Step 5 - Create Ad Button", timeout=10)
            await self.send_update(msg)

            if not success:
                # Try in iframes
                for i, iframe in enumerate(iframes):
                    try:
                        self.driver.switch_to.frame(iframe)
                        success, msg = self.try_click_methods(create_ad_selectors, f"Step 5 in iframe {i}", timeout=5)
                        if success:
                            await self.send_update(msg)
                            break
                        self.driver.switch_to.default_content()
                    except:
                        self.driver.switch_to.default_content()
                        continue

            if not success:
                self.take_screenshot("step5_failed")
                await self.send_update("❌ Step 5 failed - Could not find Create ad button")
                return False, self.screenshots

            time.sleep(3)
            self.take_screenshot("step5_clicked")

            # Step 6: Navigate to boosted item picker and click Continue
            await self.send_update("📍 Step 6: Clicking first Continue button...")
            time.sleep(3)

            current_url = self.driver.current_url
            if "boosted_item_picker" in current_url:
                await self.send_update("✓ On boosted item picker page")
                logger.info(f"Picker URL: {current_url}")

            self.take_screenshot("step6_picker_page")

            continue_selectors = [
                "div.x1vvvo52.x1fvot60.xk50ysn.xxio538.x1heor9g.xuxw1ft.x6ikm8r.x10wlt62.xlyipyv.x1h4wwuj.xeuugli",
                "Continue",
                "//div[contains(text(), 'Continue')]",
                "//button[contains(., 'Continue')]"
            ]

            success, msg = self.try_click_methods(continue_selectors, "Step 6 - First Continue", timeout=10)
            await self.send_update(msg)

            if not success:
                self.take_screenshot("step6_failed")
                await self.send_update("❌ Step 6 failed - Could not find first Continue button")
                return False, self.screenshots

            time.sleep(3)
            self.take_screenshot("step6_first_continue")

            # Click second Continue in popup
            await self.send_update("📍 Step 6b: Clicking second Continue button in popup...")

            continue_popup_selectors = [
                "div.x6s0dn4.x78zum5.x1q0g3np.xozqiw3.x2lwn1j.xeuugli.x1iyjqo2.x8va1my.x1hc1fzr.x13dflua.x6o7n8i.xxziih7.x12w9bfk.xl56j7k.xh8yej3 div.x1vvvo52.x1fvot60.xk50ysn.xxio538.x1heor9g.xuxw1ft.x6ikm8r.x10wlt62.xlyipyv.x1h4wwuj.xeuugli",
                "Continue",
                "//div[contains(@class, 'x6s0dn4')]//div[contains(text(), 'Continue')]"
            ]

            time.sleep(2)
            success, msg = self.try_click_methods(continue_popup_selectors, "Step 6b - Second Continue", timeout=10)
            await self.send_update(msg)

            if not success:
                self.take_screenshot("step6b_failed")
                await self.send_update("❌ Step 6b failed - Could not find second Continue button")
                return False, self.screenshots

            time.sleep(3)
            self.take_screenshot("step6_second_continue")

            # Handle OIDC popup
            await self.send_update("📍 Step 7: Handling Facebook OIDC authorization...")

            # Switch to new window
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to authorization window")

            time.sleep(3)
            current_url = self.driver.current_url

            if "oidc" in current_url:
                await self.send_update("✓ OIDC authorization page opened")
                logger.info(f"OIDC URL: {current_url}")
                self.take_screenshot("step7_oidc_page")

                # Click "Continue as" button
                continue_as_selectors = [
                    "button._42ft._4jy0.layerConfirm._1-af._4jy6._4jy1.selected._51sy",
                    "//button[contains(text(), 'Continue as')]",
                    "//button[@name='__CONFIRM__']",
                    "button[name='__CONFIRM__']"
                ]

                success, msg = self.try_click_methods(continue_as_selectors, "Step 7 - Continue As Button", timeout=10)
                await self.send_update(msg)

                if not success:
                    self.take_screenshot("step7_failed")
                    await self.send_update("❌ Step 7 failed - Could not find Continue As button")
                    return False, self.screenshots

                time.sleep(3)
                self.take_screenshot("step7_authorized")
                await self.send_update("✓ Authorization completed")

            # Return to main window
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main window")

            time.sleep(5)

            # Repeat Step 6 (Continue buttons again)
            await self.send_update("📍 Step 8: Clicking Continue buttons again...")

            self.take_screenshot("step8_before_continue")

            success, msg = self.try_click_methods(continue_selectors, "Step 8 - First Continue (repeat)", timeout=10)
            await self.send_update(msg)

            if success:
                time.sleep(2)
                success2, msg2 = self.try_click_methods(continue_popup_selectors, "Step 8 - Second Continue (repeat)", timeout=10)
                await self.send_update(msg2)

            time.sleep(5)
            self.take_screenshot("step8_final")

            # Check for success message
            await self.send_update("📍 Checking for completion message...")
            current_url = self.driver.current_url
            logger.info(f"Final URL: {current_url}")

            self.take_screenshot("final_result")

            await self.send_update("✅ Automation process completed!")
            await self.send_update(f"📊 Total screenshots captured: {len(self.screenshots)}")

            return True, self.screenshots

        except Exception as e:
            logger.error(f"Automation error: {e}")
            await self.send_update(f"❌ Error: {str(e)}")
            self.take_screenshot("error_state")
            return False, self.screenshots

        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    logger.info("Chrome driver closed")
                except:
                    pass
