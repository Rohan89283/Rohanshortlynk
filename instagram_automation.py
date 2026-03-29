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
            options.add_argument('--disable-features=TranslateUI,BlinkGenPropertyTrees,VizDisplayCompositor')
            options.add_argument('--disable-ipc-flooding-protection')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--enable-features=NetworkService,NetworkServiceInProcess')
            options.add_argument('--force-color-profile=srgb')
            options.add_argument('--hide-scrollbars')
            options.add_argument('--metrics-recording-only')
            options.add_argument('--mute-audio')

            # Force English language at browser level
            options.add_argument('--lang=en-US')
            options.add_argument('--accept-lang=en-US,en')
            options.add_experimental_option('prefs', {
                'intl.accept_languages': 'en-US,en',
                'profile.default_content_setting_values.notifications': 2
            })

            ua = UserAgent()
            user_agent = ua.random
            options.add_argument(f'user-agent={user_agent}')

            self.driver = uc.Chrome(options=options, version_main=int(chrome_version), use_subprocess=False)

            # Anti-detection scripts and language override
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {"userAgent": user_agent})
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")

            # Force English language in JavaScript
            self.driver.execute_script("""
                Object.defineProperty(navigator, 'language', {get: () => 'en-US'});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)

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
        logger.info("\n" + "🔎" * 40)
        logger.info(f"🔎 SEARCHING FOR: {step_name}")
        logger.info(f"🔎 Check iframes: {check_iframes}")
        logger.info("🔎" * 40 + "\n")

        # First try in main content
        logger.info("📄 Searching in MAIN CONTENT...")
        success, msg = self._try_find_and_click_internal(selectors, step_name, timeout, verify_text)
        if success:
            logger.info(f"✓✓✓ FOUND IN MAIN CONTENT: {step_name}")
            return success, msg

        logger.info(f"❌ NOT FOUND in main content")

        # If not found and check_iframes is True, try in iframes
        if check_iframes:
            logger.info(f"\n🖼️  Checking iframes...")
            iframes = self.check_iframes()
            logger.info(f"🖼️  Found {len(iframes)} iframes on page")

            for idx, iframe in enumerate(iframes):
                try:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"🖼️  [IFRAME {idx+1}/{len(iframes)}] Switching to iframe...")

                    # Try to get iframe info
                    try:
                        iframe_id = iframe.get_attribute('id')
                        iframe_name = iframe.get_attribute('name')
                        iframe_src = iframe.get_attribute('src')
                        logger.info(f"   ID: {iframe_id}")
                        logger.info(f"   Name: {iframe_name}")
                        logger.info(f"   Src: {iframe_src[:80] if iframe_src else 'None'}")
                    except:
                        logger.info(f"   Could not get iframe details")

                    logger.info(f"{'='*60}")

                    self.driver.switch_to.frame(iframe)

                    success, msg = self._try_find_and_click_internal(selectors, step_name, timeout, verify_text)

                    # Switch back to main content
                    self.driver.switch_to.default_content()

                    if success:
                        logger.info(f"✓✓✓ FOUND IN IFRAME {idx+1}: {step_name}")
                        return True, f"{msg} (found in iframe {idx+1})"
                    else:
                        logger.info(f"❌ NOT FOUND in iframe {idx+1}")

                except Exception as e:
                    logger.warning(f"❌ Error in iframe {idx+1}: {str(e)[:100]}")
                    self.driver.switch_to.default_content()
                    continue

        logger.error(f"❌❌❌ FINAL FAILURE: '{step_name}' not found in main content or any iframes")
        return False, f"✗ {step_name}: Not found in main content or iframes"

    def _try_find_and_click_internal(self, selectors, step_name, timeout=10, verify_text=None):
        """Internal method to find and click element"""
        logger.info("=" * 80)
        logger.info(f"🔍 ATTEMPTING TO FIND AND CLICK: {step_name}")
        logger.info(f"Total selectors to try: {len(selectors)}")
        logger.info("=" * 80)

        for idx, selector_info in enumerate(selectors, 1):
            selector_type = selector_info.get('type', 'xpath')
            selector = selector_info.get('selector')
            description = selector_info.get('desc', selector)
            expected_text = selector_info.get('verify_text', verify_text)

            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"[ATTEMPT {idx}/{len(selectors)}]")
                logger.info(f"Selector Type: {selector_type}")
                logger.info(f"Description: {description}")
                logger.info(f"Selector: {selector}")
                logger.info(f"Expected Text: {expected_text}")
                logger.info(f"{'='*60}")

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
                    logger.warning(f"❌ Unknown selector type: {selector_type}")
                    continue

                logger.info(f"✓ Element FOUND using {selector_type}")
                logger.info(f"   Tag name: {element.tag_name}")

                # Get element location
                try:
                    location = element.location
                    size = element.size
                    logger.info(f"   Location: x={location['x']}, y={location['y']}")
                    logger.info(f"   Size: width={size['width']}, height={size['height']}")
                except Exception as e:
                    logger.debug(f"   Could not get element location/size: {e}")

                # Verify element text if required
                if expected_text:
                    element_text = element.text.strip()
                    logger.info(f"   Element text: '{element_text}'")
                    if expected_text.lower() not in element_text.lower():
                        logger.warning(f"❌ Text mismatch: Expected '{expected_text}', got '{element_text}'")
                        continue
                    logger.info(f"✓ Text VERIFIED: '{expected_text}' found in '{element_text}'")
                else:
                    try:
                        element_text = element.text.strip()
                        if element_text:
                            logger.info(f"   Element text: '{element_text}'")
                    except:
                        pass

                # Check if element is visible and enabled
                is_displayed = element.is_displayed()
                is_enabled = element.is_enabled()

                logger.info(f"   Is visible: {is_displayed}")
                logger.info(f"   Is enabled: {is_enabled}")

                if not is_displayed:
                    logger.warning(f"❌ Element not visible, skipping")
                    continue

                if not is_enabled:
                    logger.warning(f"❌ Element not enabled, skipping")
                    continue

                logger.info(f"✓ Element is VISIBLE and ENABLED")

                # Scroll into view
                logger.info("   Scrolling element into view...")
                self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                time.sleep(0.8)

                # Highlight element briefly for debugging
                logger.info("   Highlighting element...")
                original_style = element.get_attribute('style')
                self.driver.execute_script("arguments[0].setAttribute('style', arguments[1]);",
                                         element, original_style + "border: 3px solid red;")
                time.sleep(0.3)
                self.driver.execute_script("arguments[0].setAttribute('style', arguments[1]);",
                                         element, original_style)

                # Try multiple click methods
                click_success = False
                click_method = "unknown"

                logger.info("   Attempting to click element...")

                # Method 1: Regular click
                try:
                    logger.info("   [CLICK METHOD 1] Trying element.click()...")
                    element.click()
                    click_success = True
                    click_method = "element.click()"
                    logger.info(f"✓✓✓ SUCCESSFULLY CLICKED using: {click_method}")
                except Exception as e1:
                    logger.warning(f"   [CLICK METHOD 1] Failed: {str(e1)[:100]}")

                    # Method 2: JavaScript click
                    try:
                        logger.info("   [CLICK METHOD 2] Trying JavaScript click...")
                        self.driver.execute_script("arguments[0].click();", element)
                        click_success = True
                        click_method = "JavaScript click"
                        logger.info(f"✓✓✓ SUCCESSFULLY CLICKED using: {click_method}")
                    except Exception as e2:
                        logger.warning(f"   [CLICK METHOD 2] Failed: {str(e2)[:100]}")

                        # Method 3: Action chains
                        try:
                            logger.info("   [CLICK METHOD 3] Trying ActionChains...")
                            from selenium.webdriver.common.action_chains import ActionChains
                            ActionChains(self.driver).move_to_element(element).click().perform()
                            click_success = True
                            click_method = "ActionChains"
                            logger.info(f"✓✓✓ SUCCESSFULLY CLICKED using: {click_method}")
                        except Exception as e3:
                            logger.warning(f"   [CLICK METHOD 3] Failed: {str(e3)[:100]}")

                if click_success:
                    logger.info("=" * 80)
                    logger.info(f"🎉🎉🎉 SUCCESS SUMMARY FOR {step_name} 🎉🎉🎉")
                    logger.info(f"   ✓ Found with: {selector_type}")
                    logger.info(f"   ✓ Selector: {selector}")
                    logger.info(f"   ✓ Description: {description}")
                    logger.info(f"   ✓ Clicked with: {click_method}")
                    logger.info(f"   ✓ Attempt number: {idx}/{len(selectors)}")
                    logger.info(f"   ✓ Step: {step_name}")
                    logger.info("=" * 80 + "\n")
                    success_msg = f"✓ {step_name}: SUCCESS | Selector: {selector_type} | Click: {click_method} | Attempt: {idx}/{len(selectors)}"
                    return True, success_msg
                else:
                    logger.warning(f"❌ ALL 3 CLICK METHODS FAILED for this element")
                    continue

            except TimeoutException:
                logger.warning(f"⏱️  TIMEOUT: Element not found with {selector_type} within {timeout}s")
                logger.warning(f"   Selector: {selector}")
                continue
            except Exception as e:
                logger.warning(f"❌ EXCEPTION with {selector_type}")
                logger.warning(f"   Description: {description[:50]}")
                logger.warning(f"   Error: {str(e)[:150]}")
                continue

        logger.error("=" * 80)
        logger.error(f"❌❌❌ COMPLETE FAILURE FOR: {step_name}")
        logger.error(f"   Tried {len(selectors)} different selectors")
        logger.error(f"   None of them worked")
        logger.error("=" * 80)
        return False, f"✗ {step_name}: All selectors failed (tried {len(selectors)} methods)"

    def check_url_contains(self, expected_substring):
        """Check if current URL contains expected substring"""
        current_url = self.driver.current_url
        return expected_substring in current_url, current_url

    async def run_automation(self):
        """Main automation flow - stops on first failure"""
        try:
            await self.send_update("🚀 Starting automation process...")

            # Setup driver
            if not self.setup_driver():
                await self.send_update("❌ Failed to setup Chrome driver")
                return False, []

            await self.send_update("✓ Chrome driver initialized successfully")

            # ==================== STEP 1 ====================
            await self.send_update("\n📍 STEP 1: Logging into Instagram with cookies...")
            await self.send_update("🔐 Navigating to Instagram and setting cookies...")

            # Go to Instagram and set cookies
            if not self.set_instagram_cookies():
                await self.send_update("❌ STEP 1 FAILED: Could not set Instagram cookies")
                self.take_screenshot("step1_FAILED_cookies")
                return False, self.screenshots

            await self.send_update("✓ Cookies set, refreshing page...")
            self.driver.refresh()
            time.sleep(3)

            # Verify login by checking onetap URL
            await self.send_update("🔍 Verifying Instagram login...")
            self.driver.get("https://www.instagram.com/accounts/onetap/")
            time.sleep(2)

            current_url = self.driver.current_url
            logger.info(f"Instagram verification URL: {current_url}")

            if "onetap" in current_url or "instagram.com" in current_url:
                # Check if we're logged in (not redirected to login page)
                if "/accounts/login" in current_url:
                    await self.send_update("❌ STEP 1 FAILED: Instagram login failed (redirected to login)")
                    self.take_screenshot("step1_FAILED_not_logged_in")
                    return False, self.screenshots

                await self.send_update("✓ STEP 1 SUCCESS: Instagram login verified!")
                logger.info(f"Login verified at: {current_url}")
            else:
                await self.send_update("❌ STEP 1 FAILED: Unexpected URL after login attempt")
                self.take_screenshot("step1_FAILED_unexpected_url")
                return False, self.screenshots

            # ==================== STEP 2 ====================
            await self.send_update("\n📍 STEP 2: Navigating to Facebook Business and clicking 'Log in with Instagram'...")
            await self.send_update("🌐 Loading Facebook Business login page...")

            self.driver.get("https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs")
            time.sleep(4)

            contains, url = self.check_url_contains("business.facebook.com")
            if not contains:
                await self.send_update(f"❌ STEP 2 FAILED: Not on Facebook Business page")
                await self.send_update(f"URL: {url}")
                self.take_screenshot("step2_FAILED_wrong_page")
                return False, self.screenshots

            logger.info(f"Facebook Business page loaded: {url}")
            await self.send_update("✓ Facebook Business page loaded")
            await self.send_update("🔍 Searching for 'Log in with Instagram' button...")

            # List all buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 2 - LISTING ALL BUTTONS:")
            self.list_clickable_elements(keyword="Instagram")
            logger.info("=" * 60)

            ig_login_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//span[@class='x1lliihq x193iq5w x6ikm8r x10wlt62 xlyipyv xuxw1ft' and text()='Log in with Instagram']",
                    'desc': 'XPath - Exact span class and text',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//span[text()='Log in with Instagram']/ancestor::div[@role='button']",
                    'desc': 'XPath - Exact Instagram text with ancestor button',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//span[@class='x1lliihq x193iq5w x6ikm8r x10wlt62 xlyipyv xuxw1ft']",
                    'desc': 'XPath - Span with exact classes',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@role='button'][.//span[contains(text(), 'Log in with Instagram')]]",
                    'desc': 'XPath - Button containing Instagram span',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@role='button' and contains(., 'Log in with Instagram') and not(contains(., 'Facebook'))]",
                    'desc': 'XPath - Instagram button (excluding Facebook)',
                    'verify_text': 'Instagram'
                },
                {
                    'type': 'xpath',
                    'selector': "//span[contains(@class, 'x1lliihq') and text()='Log in with Instagram']/parent::*",
                    'desc': 'XPath - Span parent element',
                    'verify_text': 'Instagram'
                },
            ]

            success, msg = self.try_find_and_click(ig_login_selectors, "STEP 2 - Instagram Login", timeout=15, verify_text='Instagram')
            await self.send_update(msg)

            if not success:
                await self.send_update("❌ STEP 2 FAILED: Could not find 'Log in with Instagram' button")
                self.take_screenshot("step2_FAILED_button_not_found")
                return False, self.screenshots

            await self.send_update("✓ STEP 2 SUCCESS: Clicked 'Log in with Instagram'")
            time.sleep(3)

            # ==================== STEP 3 ====================
            await self.send_update("\n📍 STEP 3: Handling Instagram OAuth popup...")
            time.sleep(3)

            # Check if new window/tab opened
            if len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to OAuth popup window")
                time.sleep(2)

            current_url = self.driver.current_url
            logger.info(f"OAuth popup URL: {current_url}")
            await self.send_update(f"Current URL: {current_url[:80]}...")

            # Verify we're on Instagram OAuth page
            if "instagram.com/oauth" not in current_url and "instagram.com" not in current_url:
                await self.send_update("❌ STEP 3 FAILED: Not on Instagram OAuth page")
                await self.send_update(f"URL: {current_url[:100]}")
                self.take_screenshot("step3_FAILED_not_oauth")
                return False, self.screenshots

            await self.send_update("✓ Instagram OAuth page detected")
            await self.send_update("🔍 Looking for 'Log in as [username]' button...")

            # List all buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 3 - LISTING ALL BUTTONS:")
            self.list_clickable_elements(keyword="Log in")
            logger.info("=" * 60)

            # Look for "Log in as" button with flexible username
            login_as_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//div[@class='x1i10hfl xjqpnuy xc5r6h4 xqeqjp1 x1phubyo x972fbf x10w94by x1qhh985 x14e42zd xdl72j9 x2lah0s x3ct3a4 xdj266r x14z9mp xat24cr x1lziwak x2lwn1j xeuugli xexx8yu x18d9i69 x1hl2dhg xggy1nq x1ja2u2z x1t137rt x1q0g3np x1lku1pv x1a2a7pz x6s0dn4 xjyslct x1ejq31n x18oe1m7 x1sy0etr xstzfhl x9f619 x9bdzbf x1ypdohk x1f6kntn xwhw2v2 xl56j7k x17ydfre x1n2onr6 x2b8uid xlyipyv x87ps6o x14atkfc x5c86q x18br7mf x1i0vuye x6nl9eh x1a5l9x9 x7vuprf x1mg3h75 xn3w4p2 x106a9eq x1xnnf8n x18cabeq x158me93 xk4oym4 x1uugd1q x3nfvp2' and @role='button' and contains(text(), 'Log in as')]",
                    'desc': 'XPath - Exact div class with Log in as text',
                    'verify_text': 'Log in as'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@role='button' and contains(text(), 'Log in as')]",
                    'desc': 'XPath - Role button with Log in as text',
                    'verify_text': 'Log in as'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[contains(@class, 'x1i10hfl') and @role='button' and contains(text(), 'Log in as')]",
                    'desc': 'XPath - Class x1i10hfl with role button',
                    'verify_text': 'Log in as'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[@role='button' and starts-with(text(), 'Log in as')]",
                    'desc': 'XPath - Any role button starting with Log in as',
                    'verify_text': 'Log in as'
                },
                {
                    'type': 'css',
                    'selector': "div.x1i10hfl.xjqpnuy.xc5r6h4[role='button']",
                    'desc': 'CSS - Div with role button and classes',
                    'verify_text': 'Log in as'
                },
            ]

            success, msg = self.try_find_and_click(login_as_selectors, "STEP 3 - Log in as", timeout=15, verify_text='Log in as')

            if not success:
                await self.send_update("❌ STEP 3 FAILED: Could not find 'Log in as' button")
                self.take_screenshot("step3_FAILED_no_login_as_button")
                return False, self.screenshots

            await self.send_update("✓ STEP 3 SUCCESS: Clicked 'Log in as [username]'")

            # Immediately switch back to main window (popup will close automatically)
            await self.send_update("🔄 Switching back to main window...")
            time.sleep(2)  # Brief wait for popup to start closing

            # The popup closes automatically, switch to the first (main) window
            self.driver.switch_to.window(self.driver.window_handles[0])
            logger.info("✓ Switched back to main window after clicking 'Log in as'")

            # ==================== STEP 4 ====================
            await self.send_update("\n📍 STEP 4: Waiting for redirect to Facebook Business home...")

            # Wait for the main page to redirect (popup closed, main page should refresh)
            time.sleep(6)
            current_url = self.driver.current_url
            logger.info(f"Final URL: {current_url}")
            await self.send_update(f"📊 Current URL: {current_url[:80]}...")

            # Check if we're on Business home page
            if "business.facebook.com/latest/home" in current_url or "business_id=" in current_url or "asset_id=" in current_url:
                await self.send_update(f"✅ STEP 4 SUCCESS: Redirected to Facebook Business home!")
                await self.send_update(f"✅ URL confirmed: {current_url}")
                logger.info(f"✅ SUCCESS! Business ID detected in URL")
            else:
                await self.send_update(f"❌ STEP 4 FAILED: Not on Business home page")
                await self.send_update(f"Expected: business.facebook.com/latest/home?business_id=...")
                await self.send_update(f"Got: {current_url[:100]}")
                self.take_screenshot("step4_FAILED_wrong_url")
                return False, self.screenshots

            self.take_screenshot("step4_SUCCESS_home_page")

            # ==================== STEP 5 ====================
            await self.send_update("\n📍 STEP 5: Navigating to Facebook Ads Center...")
            time.sleep(2)

            # Force Facebook to English by setting multiple language cookies
            logger.info("🌍 Forcing Facebook Business to English language...")
            await self.send_update("🌍 Setting Facebook to English...")

            try:
                # First visit Facebook to set the domain for cookies
                self.driver.get("https://business.facebook.com")
                time.sleep(2)

                # Set multiple locale cookies to English (United States)
                language_cookies = [
                    {'name': 'locale', 'value': 'en_US', 'domain': '.facebook.com', 'path': '/'},
                    {'name': 'locale', 'value': 'en_US', 'domain': '.business.facebook.com', 'path': '/'},
                    {'name': 'i18n_language', 'value': 'en_US', 'domain': '.facebook.com', 'path': '/'},
                    {'name': 'lang', 'value': 'en', 'domain': '.facebook.com', 'path': '/'},
                ]

                for cookie in language_cookies:
                    try:
                        self.driver.add_cookie(cookie)
                        logger.info(f"✓ Set {cookie['name']} cookie")
                    except Exception as cookie_error:
                        logger.warning(f"Could not set {cookie['name']} cookie: {cookie_error}")

                logger.info("✓ Facebook language set to English (en_US)")
                await self.send_update("✓ Facebook language configured")
            except Exception as e:
                logger.warning(f"Could not set Facebook locale cookies: {e}")
                # Continue anyway as the URL may still work

            # Navigate to Facebook Ads Center - simplified URL
            ads_center_url = "https://business.facebook.com/latest/ad_center/"
            logger.info(f"Navigating to: {ads_center_url}")
            await self.send_update(f"🌐 Going to: {ads_center_url}")

            try:
                self.driver.get(ads_center_url)
                time.sleep(8)

                # Force English language via JavaScript after page load
                try:
                    self.driver.execute_script("""
                        document.documentElement.lang = 'en';
                        if (window.localStorage) {
                            localStorage.setItem('locale', 'en_US');
                            localStorage.setItem('i18n_language', 'en_US');
                        }
                    """)
                    logger.info("✓ JavaScript language override applied")
                except Exception as js_error:
                    logger.warning(f"Could not apply JavaScript language override: {js_error}")

                self.take_screenshot("step5_navigated_to_ads_center")

                # Check if driver session is still valid
                current_url = self.driver.current_url
                logger.info(f"Step 5 URL after navigation: {current_url}")
                await self.send_update(f"📊 Current URL: {current_url[:80]}...")
            except Exception as nav_error:
                logger.error(f"❌ Navigation to Ads Center failed: {nav_error}")
                await self.send_update(f"❌ Failed to load Ads Center page")
                self.take_screenshot("step5_FAILED_navigation_crash")
                return False, self.screenshots

            # Wait for page to load
            await self.send_update("⏳ Waiting for Ads Center page to load...")
            time.sleep(3)

            # List all buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 5 - LISTING ALL BUTTONS:")
            self.list_clickable_elements(keyword="Get started")
            logger.info("=" * 60)

            get_started_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//div[text()='Get started']",
                    'desc': 'XPath - Any div with Get started text',
                    'verify_text': 'Get started'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[@role='button' and contains(text(), 'Get started')]",
                    'desc': 'XPath - Role button containing Get started',
                    'verify_text': 'Get started'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[contains(text(), 'Get started')]",
                    'desc': 'XPath - Any element containing Get started',
                    'verify_text': 'Get started'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@class='x1vvvo52 x1fvot60 xk50ysn xxio538 x1heor9g xuxw1ft x6ikm8r x10wlt62 xlyipyv x1h4wwuj xeuugli' and text()='Get started']",
                    'desc': 'XPath - Exact div class with Get started text',
                    'verify_text': 'Get started'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[contains(@class, 'x1vvvo52')]//div[text()='Get started']",
                    'desc': 'XPath - Div with x1vvvo52 class containing Get started',
                    'verify_text': 'Get started'
                },
            ]

            success, msg = self.try_find_and_click(get_started_selectors, "STEP 5 - Get started", timeout=15, verify_text='Get started', check_iframes=True)
            await self.send_update(msg)

            if not success:
                await self.send_update("❌ STEP 5 FAILED: Could not find 'Get started' button")
                self.take_screenshot("step5_FAILED_no_get_started")
                return False, self.screenshots

            await self.send_update("✓ STEP 5 SUCCESS: Clicked 'Get started' button")
            time.sleep(5)

            self.take_screenshot("step5_SUCCESS_clicked_get_started")

            # ==================== STEP 6 ====================
            await self.send_update("\n📍 STEP 6: Navigated to boosted item picker, clicking first 'Continue'...")

            current_url = self.driver.current_url
            logger.info(f"Step 6 URL: {current_url}")
            await self.send_update(f"📊 Current URL: {current_url[:80]}...")

            # Verify we're on boosted_item_picker page
            if "boosted_item_picker" not in current_url:
                await self.send_update(f"⚠️ Warning: Not on expected boosted_item_picker page")
                await self.send_update(f"Current URL: {current_url[:100]}")

            time.sleep(4)

            # List all buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 6 - LISTING ALL BUTTONS:")
            self.list_clickable_elements(keyword="Continue")
            logger.info("=" * 60)

            continue_selectors_step6 = [
                {
                    'type': 'xpath',
                    'selector': "//div[@role='dialog']//div[text()='Continue']",
                    'desc': 'XPath - Continue button inside dialog modal',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[contains(@aria-label, 'dialog') or contains(@role, 'dialog')]//div[text()='Continue']",
                    'desc': 'XPath - Continue button inside aria-label dialog',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[text()='Continue']",
                    'desc': 'XPath - Any div with Continue text',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[@role='button' and contains(text(), 'Continue')]",
                    'desc': 'XPath - Role button containing Continue',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[contains(text(), 'Continue')]",
                    'desc': 'XPath - Any element containing Continue',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@class='x1vvvo52 x1fvot60 xk50ysn xxio538 x1heor9g xuxw1ft x6ikm8r x10wlt62 xlyipyv x1h4wwuj xeuugli' and text()='Continue']",
                    'desc': 'XPath - Exact div class with Continue text (fallback)',
                    'verify_text': 'Continue'
                },
            ]

            success, msg = self.try_find_and_click(continue_selectors_step6, "STEP 6 - First Continue", timeout=15, verify_text='Continue', check_iframes=True)
            await self.send_update(msg)

            if not success:
                await self.send_update("❌ STEP 6 FAILED: Could not find first 'Continue' button")
                self.take_screenshot("step6_FAILED_no_continue")
                return False, self.screenshots

            await self.send_update("✓ STEP 6 SUCCESS: Clicked first 'Continue' button")
            time.sleep(4)

            self.take_screenshot("step6_SUCCESS_clicked_continue")

            # ==================== STEP 7 ====================
            await self.send_update("\n📍 STEP 7: Popup appeared, clicking second 'Continue' button...")
            time.sleep(3)

            # List all buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 7 - LISTING ALL BUTTONS:")
            self.list_clickable_elements(keyword="Continue")
            logger.info("=" * 60)

            continue_selectors_step7 = [
                {
                    'type': 'xpath',
                    'selector': "//div[@role='dialog']//div[text()='Continue']",
                    'desc': 'XPath - Continue button inside dialog modal',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[contains(@aria-label, 'dialog') or contains(@role, 'dialog')]//div[text()='Continue']",
                    'desc': 'XPath - Continue button inside aria-label dialog',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[text()='Continue']",
                    'desc': 'XPath - Any div with Continue text',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[@role='button' and contains(text(), 'Continue')]",
                    'desc': 'XPath - Role button containing Continue',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//*[contains(text(), 'Continue')]",
                    'desc': 'XPath - Any element containing Continue',
                    'verify_text': 'Continue'
                },
                {
                    'type': 'xpath',
                    'selector': "//div[@class='x6s0dn4 x78zum5 x1q0g3np xozqiw3 x2lwn1j xeuugli x1iyjqo2 x8va1my x1hc1fzr x13dflua x6o7n8i xxziih7 x12w9bfk xl56j7k xh8yej3']//div[@class='x1vvvo52 x1fvot60 xk50ysn xxio538 x1heor9g xuxw1ft x6ikm8r x10wlt62 xlyipyv x1h4wwuj xeuugli' and text()='Continue']",
                    'desc': 'XPath - Exact nested div classes with Continue text (fallback)',
                    'verify_text': 'Continue'
                },
            ]

            success, msg = self.try_find_and_click(continue_selectors_step7, "STEP 7 - Second Continue (Popup)", timeout=15, verify_text='Continue', check_iframes=True)
            await self.send_update(msg)

            if not success:
                await self.send_update("❌ STEP 7 FAILED: Could not find second 'Continue' button in popup")
                self.take_screenshot("step7_FAILED_no_popup_continue")
                return False, self.screenshots

            await self.send_update("✓ STEP 7 SUCCESS: Clicked second 'Continue' button in popup")
            time.sleep(5)

            self.take_screenshot("step7_SUCCESS_clicked_popup_continue")

            # ==================== STEP 8 ====================
            await self.send_update("\n📍 STEP 8: New tab opened for authorization, clicking 'Continue as' button...")
            time.sleep(3)

            # Check if new window/tab opened
            if len(self.driver.window_handles) > 1:
                await self.send_update(f"✓ Detected {len(self.driver.window_handles)} windows, switching to new tab...")
                self.driver.switch_to.window(self.driver.window_handles[-1])
                await self.send_update("✓ Switched to authorization tab")
                time.sleep(3)

            current_url = self.driver.current_url
            logger.info(f"Step 8 URL: {current_url}")
            await self.send_update(f"📊 Current URL: {current_url[:80]}...")

            # Verify we're on OIDC authorization page
            if "oidc" not in current_url:
                await self.send_update(f"⚠️ Warning: Not on expected OIDC authorization page")
                await self.send_update(f"Current URL: {current_url[:100]}")

            # List all buttons for debugging
            logger.info("=" * 60)
            logger.info("STEP 8 - LISTING ALL BUTTONS:")
            self.list_clickable_elements(keyword="Continue")
            logger.info("=" * 60)

            continue_as_selectors = [
                {
                    'type': 'xpath',
                    'selector': "//button[@class='_42ft _4jy0 layerConfirm _1-af _4jy6 _4jy1 selected _51sy' and @name='__CONFIRM__' and @type='submit' and starts-with(text(), 'Continue as')]",
                    'desc': 'XPath - Exact button class with Continue as text',
                    'verify_text': 'Continue as'
                },
                {
                    'type': 'xpath',
                    'selector': "//button[@name='__CONFIRM__' and @type='submit' and contains(text(), 'Continue as')]",
                    'desc': 'XPath - Button with __CONFIRM__ name and Continue as text',
                    'verify_text': 'Continue as'
                },
                {
                    'type': 'xpath',
                    'selector': "//button[@type='submit' and contains(text(), 'Continue as')]",
                    'desc': 'XPath - Submit button with Continue as text',
                    'verify_text': 'Continue as'
                },
                {
                    'type': 'xpath',
                    'selector': "//button[contains(@class, 'layerConfirm') and contains(text(), 'Continue as')]",
                    'desc': 'XPath - Button with layerConfirm class',
                    'verify_text': 'Continue as'
                },
                {
                    'type': 'xpath',
                    'selector': "//button[contains(text(), 'Continue as')]",
                    'desc': 'XPath - Any button containing Continue as',
                    'verify_text': 'Continue as'
                },
                {
                    'type': 'css',
                    'selector': "button._42ft._4jy0.layerConfirm[name='__CONFIRM__']",
                    'desc': 'CSS - Button with exact classes and __CONFIRM__ name',
                    'verify_text': 'Continue as'
                },
            ]

            success, msg = self.try_find_and_click(continue_as_selectors, "STEP 8 - Continue as", timeout=15, verify_text='Continue as', check_iframes=True)
            await self.send_update(msg)

            if not success:
                await self.send_update("❌ STEP 8 FAILED: Could not find 'Continue as' button")
                self.take_screenshot("step8_FAILED_no_continue_as")
                return False, self.screenshots

            await self.send_update("✓ STEP 8 SUCCESS: Clicked 'Continue as' button")
            time.sleep(5)

            self.take_screenshot("step8_SUCCESS_clicked_continue_as")

            # Wait for redirect and switch back to main tab
            await self.send_update("🔄 Waiting for authorization to complete...")
            time.sleep(5)

            # Check URL after authorization
            current_url = self.driver.current_url
            logger.info(f"After authorization URL: {current_url}")

            # Close new tab if still open and switch to main tab
            if len(self.driver.window_handles) > 1:
                await self.send_update("🔄 Closing authorization tab and switching to main window...")
                self.driver.close()
                self.driver.switch_to.window(self.driver.window_handles[0])
                await self.send_update("✓ Switched back to main window")
                time.sleep(3)

            current_url = self.driver.current_url
            logger.info(f"Main window URL: {current_url}")
            await self.send_update(f"📊 Main window URL: {current_url[:80]}...")

            self.take_screenshot("step8_SUCCESS_back_to_main")

            # ==================== FINAL ====================
            await self.send_update("\n✅ ALL 8 STEPS COMPLETED SUCCESSFULLY!")
            await self.send_update("✅ Instagram account fully connected to Facebook Business Manager")
            await self.send_update("✅ Authorization completed successfully")
            await self.send_update(f"✅ Final URL: {current_url[:100]}")
            await self.send_update(f"\n📊 Total screenshots captured: {len(self.screenshots)}")

            if len(self.screenshots) > 0:
                await self.send_update("📸 Sending screenshots for review...")

            logger.info("=" * 60)
            logger.info("AUTOMATION COMPLETED SUCCESSFULLY!")
            logger.info(f"Final URL: {current_url}")
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
