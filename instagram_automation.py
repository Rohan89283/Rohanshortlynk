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
            user_agent = ua.random
            options.add_argument(f'user-agent={user_agent}')

            self.driver = uc.Chrome(options=options, version_main=int(chrome_version), use_subprocess=False)

            # Anti-detection scripts
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")

            logger.info(f"✓ Chrome driver initialized with user agent: {user_agent[:50]}...")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to setup driver: {e}")
            return False

    def set_instagram_cookies(self):
        """Set Instagram cookies from cookie string"""
        try:
            self.driver.get("https://www.instagram.com")
            time.sleep(2)

            cookies = self.cookie_string.split(';')
            cookie_count = 0
            for cookie in cookies:
                cookie = cookie.strip()
                if '=' in cookie:
                    name, value = cookie.split('=', 1)
                    try:
                        self.driver.add_cookie({
                            'name': name.strip(),
                            'value': value.strip(),
                            'domain': '.instagram.com'
                        })
                        cookie_count += 1
                    except Exception as e:
                        logger.debug(f"Could not add cookie {name}: {e}")

            logger.info(f"✓ Set {cookie_count} Instagram cookies")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to set cookies: {e}")
            return False

    def list_clickable_elements(self, keyword=None):
        """List all clickable elements on the page, optionally filtered by keyword"""
        try:
            buttons = self.driver.find_elements(By.XPATH, "//*[@role='button' or self::button or self::a]")
            logger.info(f"Found {len(buttons)} clickable elements on page")

            filtered = []
            for idx, btn in enumerate(buttons[:20]):
                try:
                    text = btn.text.strip()[:60]
                    tag = btn.tag_name
                    role = btn.get_attribute('role') or 'no-role'

                    if keyword:
                        if keyword.lower() in text.lower():
                            filtered.append(btn)
                            logger.info(f"  ✓ Match {len(filtered)}: <{tag}> role='{role}' text='{text}'")
                    else:
                        logger.info(f"  Element {idx+1}: <{tag}> role='{role}' text='{text}'")
                except:
                    pass

            if keyword:
                logger.info(f"Found {len(filtered)} elements matching '{keyword}'")
                return filtered
            return buttons[:20]

        except Exception as e:
            logger.debug(f"Error listing elements: {e}")
            return []

    def check_iframes(self):
        """Check and list all iframes on the page"""
        try:
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"Found {len(iframes)} iframe(s) on page")
            for idx, iframe in enumerate(iframes):
                iframe_id = iframe.get_attribute('id') or 'no-id'
                iframe_name = iframe.get_attribute('name') or 'no-name'
                iframe_src = iframe.get_attribute('src') or 'no-src'
                logger.info(f"  Iframe {idx+1}: id='{iframe_id}', name='{iframe_name}', src='{iframe_src[:60]}'")
            return iframes
        except Exception as e:
            logger.debug(f"Error checking iframes: {e}")
            return []

    def try_find_and_click(self, selectors, step_name, timeout=10, verify_text=None, check_iframes=True):
        """Try multiple selectors to find and click an element with verification"""
        # First try in main content
        success, msg = self._try_find_and_click_internal(selectors, step_name, timeout, verify_text)
        if success:
            return success, msg

        # If not found and check_iframes is True, try in iframes
        if check_iframes:
            logger.info(f"Element not found in main content, checking iframes...")
            iframes = self.check_iframes()

            for idx, iframe in enumerate(iframes):
                try:
                    logger.info(f"Switching to iframe {idx+1}/{len(iframes)}")
                    self.driver.switch_to.frame(iframe)

                    success, msg = self._try_find_and_click_internal(selectors, step_name, timeout, verify_text)

                    # Switch back to main content
                    self.driver.switch_to.default_content()

                    if success:
                        return True, f"{msg} (found in iframe {idx+1})"

                except Exception as e:
                    logger.debug(f"Error in iframe {idx+1}: {e}")
                    self.driver.switch_to.default_content()
                    continue

        return False, f"✗ {step_name}: Not found in main content or iframes"

    def _try_find_and_click_internal(self, selectors, step_name, timeout=10, verify_text=None):
        """Internal method to find and click element"""
        for idx, selector_info in enumerate(selectors, 1):
            selector_type = selector_info.get('type', 'xpath')
            selector = selector_info.get('selector')
            description = selector_info.get('desc', selector)
            expected_text = selector_info.get('verify_text', verify_text)

            try:
                logger.info(f"[{idx}/{len(selectors)}] Trying {selector_type}: {description[:60]}")

                if selector_type == 'xpath':
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                elif selector_type == 'css':
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                elif selector_type == 'class':
                    element = WebDriverWait(self.driver, timeout).until(
                        EC.presence_of_element_located((By.CLASS_NAME, selector))
                    )
                else:
                    logger.debug(f"Unknown selector type: {selector_type}")
                    continue

                # Verify element text if required
                if expected_text:
                    element_text = element.text.strip()
                    logger.info(f"Element found. Text: '{element_text}'")
                    if expected_text.lower() not in element_text.lower():
                        logger.debug(f"Text mismatch: Expected '{expected_text}', got '{element_text}'")
                        continue
                    logger.info(f"✓ Text verified: '{expected_text}' found in '{element_text}'")
                else:
                    logger.info(f"Element found: {element.tag_name}")

                # Check if element is visible and enabled
                if not element.is_displayed():
                    logger.debug(f"Element not visible, skipping")
                    continue

                if not element.is_enabled():
                    logger.debug(f"Element not enabled, skipping")
                    continue

                logger.info(f"✓ Element is visible and enabled")

                # Scroll into view
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.8)

                # Highlight element briefly for debugging
                original_style = element.get_attribute('style')
                self.driver.execute_script("arguments[0].setAttribute('style', arguments[1]);",
                                         element, original_style + "border: 3px solid red;")
                time.sleep(0.3)
                self.driver.execute_script("arguments[0].setAttribute('style', arguments[1]);",
                                         element, original_style)

                # Try multiple click methods
                click_success = False
                click_method = "unknown"

                # Method 1: Regular click
                try:
                    element.click()
                    click_success = True
                    click_method = "element.click()"
                    logger.info(f"✓ Clicked using: {click_method}")
                except Exception as e1:
                    logger.debug(f"Method 1 (element.click) failed: {str(e1)[:50]}")

                    # Method 2: JavaScript click
                    try:
                        self.driver.execute_script("arguments[0].click();", element)
                        click_success = True
                        click_method = "javascript click"
                        logger.info(f"✓ Clicked using: {click_method}")
                    except Exception as e2:
                        logger.debug(f"Method 2 (JS click) failed: {str(e2)[:50]}")

                        # Method 3: Action chains
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            ActionChains(self.driver).move_to_element(element).click().perform()
                            click_success = True
                            click_method = "ActionChains"
                            logger.info(f"✓ Clicked using: {click_method}")
                        except Exception as e3:
                            logger.debug(f"Method 3 (ActionChains) failed: {str(e3)[:50]}")

                if click_success:
                    success_msg = f"✓ {step_name}: SUCCESS using {selector_type} - {description[:40]}"
                    logger.info(success_msg)
                    logger.info(f"Click method: {click_method}")
                    return True, f"{success_msg} (Method: {click_method})"
                else:
                    logger.debug(f"All click methods failed for this element")
                    continue

            except Exception as e:
                logger.debug(f"✗ {step_name}: {selector_type} '{description[:30]}...' failed - {str(e)[:100]}")
                continue

        logger.error(f"❌ {step_name}: All {len(selectors)} selectors failed!")
        return False, f"✗ {step_name}: All selectors failed (tried {len(selectors)} methods)"

    def check_url_contains(self, expected_substring):
        """Check if current URL contains expected substring"""
        current_url = self.driver.current_url
        return expected_substring in current_url, current_url

    async def run_automation(self):
        """Main automation flow with all steps"""
        try:
            await self.send_update("🚀 Starting automation process...")

            # Setup driver
            if not self.setup_driver():
                await self.send_update("❌ Failed to setup Chrome driver")
                return False, []

            await self.send_update("✓ Chrome driver initialized successfully")

            # ==================== STEP 1 ====================
            await self.send_update("\n📍 STEP 1: Navigating to Facebook Business login page...")
            self.driver.get("https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs")
            time.sleep(4)
            self.take_screenshot("step1_fb_business_page")

            contains, url = self.check_url_contains("business.facebook.com")
            if contains:
                await self.send_update(f"✓ STEP 1: Page loaded successfully")
                logger.info(f"URL: {url}")
            else:
                await self.send_update(f"⚠️ STEP 1: Unexpected URL: {url}")

            # ==================== STEP 2 ====================
            await self.send_update("\n📍 STEP 2: Finding and clicking 'Log in with Instagram' button...")
            await self.send_update("🔍 Searching for Instagram button (NOT Facebook)...")

            # List all buttons for debugging
            logger.info("=" * 60)
            logger.info("LISTING ALL BUTTONS ON PAGE:")
            self.list_clickable_elements(keyword="Instagram")
            logger.info("=" * 60)

            ig_login_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//span[text()='Log in with Instagram']/ancestor::div[@role='button']",
                    'desc': 'XPath - Exact Instagram text with ancestor button',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@role='button'][.//span[contains(text(), 'Instagram')]]",
                    'desc': 'XPath - Button containing Instagram span',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@role='button' and contains(., 'Log in with Instagram') and not(contains(., 'Facebook'))]",
                    'desc': 'XPath - Button with Instagram text (excluding Facebook)',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//span[contains(@class, 'x1lliihq') and text()='Log in with Instagram']/parent::*",
                    'desc': 'XPath - Span with Instagram text (parent element)',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[contains(text(), 'Log in with Instagram')]",
                    'desc': 'XPath - Any element with Instagram login text',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//button[contains(., 'Instagram')]",
                    'desc': 'XPath - Button element with Instagram',
                    'verify_text': 'Instagram'
                },
            ]

            success, msg = self.try_find_and_click(ig_login_selectors, "STEP 2 - Instagram Login", timeout=15, verify_text='Instagram')
            await self.send_update(msg)

            if not success:
                self.take_screenshot("step2_FAILED_button_not_found")
                await self.send_update("❌ STEP 2 FAILED: Could not find Instagram login button")
                return False, self.screenshots

            time.sleep(4)
            self.take_screenshot("step2_clicked_instagram_login")

            # ==================== STEP 3 ====================
            await self.send_update("\n📍 STEP 3: Handling Instagram login popup...")

            # Check if new window opened
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to Instagram login window")
                time.sleep(2)

            current_url = self.driver.current_url
            logger.info(f"Current URL: {current_url}")

            if "instagram.com" not in current_url:
                await self.send_update(f"⚠️ Not on Instagram page. URL: {current_url[:100]}")
                self.take_screenshot("step3_not_instagram")
                return False, self.screenshots

            await self.send_update("✓ Instagram login page opened")
            self.take_screenshot("step3_instagram_login_page")

            # Set cookies
            await self.send_update("🔐 Setting Instagram cookies...")
            if not self.set_instagram_cookies():
                await self.send_update("❌ Failed to set cookies")
                self.take_screenshot("step3_FAILED_cookies")
                return False, self.screenshots

            await self.send_update("✓ Cookies set successfully, refreshing page...")
            self.driver.refresh()
            time.sleep(4)
            self.take_screenshot("step3_after_cookies_refresh")

            # Check for "Not Now" button (notifications popup)
            await self.send_update("🔍 Checking for notification popup...")
            not_now_selectors = [
                {'type': 'xpath', 'selector': "//button[contains(text(), 'Not Now')]", 'desc': 'Not Now button'},
                {'type': 'xpath', 'selector': "//button[contains(text(), 'Not now')]", 'desc': 'Not now button (lowercase)'},
                {'type': 'css', 'selector': "button._a9--._ap36._a9_1", 'desc': 'Not now button class'},
            ]

            success, msg = self.try_find_and_click(not_now_selectors, "Dismiss Notifications", timeout=5)
            if success:
                await self.send_update("✓ Dismissed notification popup (login successful)")
                time.sleep(2)
            else:
                await self.send_update("ℹ️ No notification popup found")

            # Look for "Log in as" button
            await self.send_update("🔍 Looking for 'Log in as' button...")
            login_as_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//div[@role='button' and contains(text(), 'Log in as')]",
                    'desc': 'Log in as button with role'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[contains(@class, 'x1i10hfl') and contains(text(), 'Log in as')]",
                    'desc': 'Log in as with class'
                },
                {
                    'type': 'css',
                    'selector': "div.x1i10hfl.xjqpnuy.xc5r6h4",
                    'desc': 'Button with specific classes'
                },
            ]

            success, msg = self.try_find_and_click(login_as_selectors, "STEP 3 - Log in as", timeout=8)
            if success:
                await self.send_update(msg)
                await self.send_update("✓ STEP 3: Login successful!")
                time.sleep(3)
                self.take_screenshot("step3_logged_in_success")
            else:
                await self.send_update("ℹ️ No 'Log in as' button found, checking if already logged in...")
                self.take_screenshot("step3_no_login_as_button")

            # ==================== STEP 4 ====================
            await self.send_update("\n📍 STEP 4: Verifying redirect to Facebook Business home...")

            # Switch back to main window if needed
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Switched back to main window")

            time.sleep(5)
            current_url = self.driver.current_url
            logger.info(f"Home page URL: {current_url}")

            if "business.facebook.com/latest/home" in current_url or "business_id=" in current_url:
                await self.send_update(f"✓ STEP 4: Successfully on Business home page!")
                await self.send_update(f"URL confirmed: {current_url[:80]}...")
                self.take_screenshot("step4_business_home_SUCCESS")
            else:
                await self.send_update(f"⚠️ STEP 4: Unexpected URL")
                await self.send_update(f"Current URL: {current_url[:100]}...")
                self.take_screenshot("step4_unexpected_url")

            # ==================== STEP 5 ====================
            await self.send_update("\n📍 STEP 5: Finding and clicking 'Create ad' button...")

            # List buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 5 - LISTING BUTTONS:")
            self.list_clickable_elements(keyword="ad")
            logger.info("=" * 60)

            create_ad_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//div[contains(text(), 'Create ad')]",
                    'desc': 'XPath - div with Create ad text'
                },
                {
                    'type': 'xpath',
                    'selector': "//button[contains(., 'Create ad')]",
                    'desc': 'XPath - button with Create ad'
                },
                {
                    'type': 'css',
                    'selector': "div.x1vvvo52.x1fvot60.xk50ysn.xxio538.x1heor9g.xuxw1ft.x6ikm8r.x10wlt62.xlyipyv.x1h4wwuj.xeuugli",
                    'desc': 'CSS - Create ad button classes'
                },
            ]

            success, msg = self.try_find_and_click(create_ad_selectors, "STEP 5 - Create Ad", timeout=15)
            await self.send_update(msg)

            if not success:
                self.take_screenshot("step5_FAILED_create_ad_not_found")
                await self.send_update("❌ STEP 5 FAILED: Could not find Create ad button")
                return False, self.screenshots

            time.sleep(4)
            self.take_screenshot("step5_clicked_create_ad")
            await self.send_update("✓ STEP 5: Create ad button clicked successfully")

            # ==================== STEP 6 ====================
            await self.send_update("\n📍 STEP 6: Navigating to boosted item picker...")
            time.sleep(3)

            current_url = self.driver.current_url
            if "boosted_item_picker" in current_url:
                await self.send_update("✓ On boosted item picker page")
                logger.info(f"Picker URL: {current_url}")

            self.take_screenshot("step6_boosted_item_picker_page")

            await self.send_update("📍 STEP 6a: Clicking FIRST Continue button...")

            # List buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 6a - LISTING BUTTONS:")
            self.list_clickable_elements(keyword="Continue")
            logger.info("=" * 60)

            continue_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//div[contains(text(), 'Continue') and contains(@class, 'x1vvvo52')]",
                    'desc': 'XPath - Continue button with class'
                },
                {
                    'type': 'xpath',
                    'selector': "//button[contains(., 'Continue')]",
                    'desc': 'XPath - Continue button element'
                },
                {
                    'type': 'css',
                    'selector': "div.x1vvvo52.x1fvot60.xk50ysn.xxio538.x1heor9g.xuxw1ft.x6ikm8r.x10wlt62.xlyipyv.x1h4wwuj.xeuugli",
                    'desc': 'CSS - Continue button classes'
                },
            ]

            success, msg = self.try_find_and_click(continue_selectors, "STEP 6a - First Continue", timeout=15)
            await self.send_update(msg)

            if not success:
                self.take_screenshot("step6a_FAILED_first_continue")
                await self.send_update("❌ STEP 6a FAILED: Could not find first Continue button")
                return False, self.screenshots

            time.sleep(3)
            self.take_screenshot("step6a_first_continue_clicked")

            # Click SECOND Continue in popup
            await self.send_update("📍 STEP 6b: Clicking SECOND Continue button in popup...")

            continue_popup_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//div[contains(@class, 'x6s0dn4')]//div[contains(text(), 'Continue') and contains(@class, 'x1vvvo52')]",
                    'desc': 'XPath - Continue in popup container'
                },
                {
                    'type': 'css',
                    'selector': "div.x6s0dn4 div.x1vvvo52",
                    'desc': 'CSS - Popup Continue button'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[contains(@class, 'x6s0dn4')]//div[text()='Continue']",
                    'desc': 'XPath - Exact Continue text in popup'
                },
            ]

            time.sleep(2)
            success, msg = self.try_find_and_click(continue_popup_selectors, "STEP 6b - Second Continue", timeout=15)
            await self.send_update(msg)

            if not success:
                self.take_screenshot("step6b_FAILED_second_continue")
                await self.send_update("❌ STEP 6b FAILED: Could not find second Continue button")
                return False, self.screenshots

            time.sleep(4)
            self.take_screenshot("step6b_second_continue_clicked")
            await self.send_update("✓ STEP 6: Both Continue buttons clicked successfully")

            # ==================== STEP 7 ====================
            await self.send_update("\n📍 STEP 7: Handling Facebook OIDC authorization popup...")

            # Check for new window
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to authorization window")
                time.sleep(3)

            current_url = self.driver.current_url
            logger.info(f"OIDC URL: {current_url}")

            if "oidc" not in current_url:
                await self.send_update(f"⚠️ Not on OIDC page. URL: {current_url[:100]}")
                self.take_screenshot("step7_not_oidc_page")
            else:
                await self.send_update("✓ OIDC authorization page opened")
                self.take_screenshot("step7_oidc_authorization_page")

                # Click "Continue as" button
                await self.send_update("🔍 Looking for 'Continue as' button...")
                continue_as_selectors = [
                    {
                        'type': 'xpath',
                        'selector': "//button[@name='__CONFIRM__']",
                        'desc': 'XPath - Confirm button by name'
                    },
                    {
                        'type': 'xpath',
                        'selector': "//button[contains(text(), 'Continue as')]",
                        'desc': 'XPath - Continue as text'
                    },
                    {
                        'type': 'css',
                        'selector': "button._42ft._4jy0.layerConfirm",
                        'desc': 'CSS - Continue button classes'
                    },
                    {
                        'type': 'css',
                        'selector': "button[name='__CONFIRM__']",
                        'desc': 'CSS - Confirm button'
                    },
                ]

                success, msg = self.try_find_and_click(continue_as_selectors, "STEP 7 - Continue As", timeout=15)
                await self.send_update(msg)

                if not success:
                    self.take_screenshot("step7_FAILED_continue_as")
                    await self.send_update("❌ STEP 7 FAILED: Could not find Continue As button")
                    return False, self.screenshots

                time.sleep(4)
                self.take_screenshot("step7_authorization_clicked")
                await self.send_update("✓ STEP 7: Authorization completed")

                # Check redirect URL
                time.sleep(2)
                current_url = self.driver.current_url
                if "code=" in current_url and "state=" in current_url:
                    await self.send_update("✓ Authorization callback received")
                    logger.info(f"Callback URL: {current_url[:150]}...")

            # Return to main window
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Returned to main window")

            time.sleep(5)

            # ==================== STEP 8 ====================
            await self.send_update("\n📍 STEP 8: Repeating Continue button clicks...")

            self.take_screenshot("step8_before_continue_repeat")

            # First Continue again
            await self.send_update("📍 STEP 8a: Clicking first Continue (repeat)...")
            success, msg = self.try_find_and_click(continue_selectors, "STEP 8a - First Continue (repeat)", timeout=15)
            await self.send_update(msg)

            if success:
                time.sleep(3)
                self.take_screenshot("step8a_first_continue_repeat")

                # Second Continue again
                await self.send_update("📍 STEP 8b: Clicking second Continue (repeat)...")
                success2, msg2 = self.try_find_and_click(continue_popup_selectors, "STEP 8b - Second Continue (repeat)", timeout=15)
                await self.send_update(msg2)

                if success2:
                    await self.send_update("✓ STEP 8: Both Continue buttons clicked (repeat)")
                    time.sleep(4)
                    self.take_screenshot("step8b_second_continue_repeat")
            else:
                await self.send_update("ℹ️ STEP 8: Continue buttons may not be needed (already processed)")

            time.sleep(5)
            self.take_screenshot("step8_after_final_clicks")

            # ==================== FINAL ====================
            await self.send_update("\n📍 Checking final status...")

            current_url = self.driver.current_url
            logger.info(f"Final URL: {current_url}")
            await self.send_update(f"Final URL: {current_url[:100]}...")

            self.take_screenshot("final_result_page")

            # Check for success indicators
            time.sleep(3)
            page_text = self.driver.find_element(By.TAG_NAME, "body").text

            if any(keyword in page_text.lower() for keyword in ['success', 'complete', 'connected', 'done']):
                await self.send_update("✅ Success indicators found on page")

            await self.send_update("\n✅ AUTOMATION PROCESS COMPLETED!")
            await self.send_update(f"📊 Total screenshots captured: {len(self.screenshots)}")
            await self.send_update("📸 Sending all screenshots for review...")

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
