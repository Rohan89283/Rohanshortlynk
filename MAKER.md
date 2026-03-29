# MAKER.md - Development Prompts & Technical Documentation

This document contains the complete development prompts, architecture decisions, and technical details for the Instagram Business Automation Bot.

## Project Overview

**Purpose**: Automate the complete flow of connecting an Instagram account to Facebook Business Manager for advertising purposes via a Telegram bot.

**Core Requirement**: User sends Instagram cookies via `/ig` command, bot automates the entire 9-step connection process with real-time updates.

---

## Main Command: `/ig`

### Command Format
```
/ig <instagram_cookies>
```

### Example
```
/ig sessionid=abc123xyz; ds_user_id=456789; csrftoken=token123
```

### Behavior

When user sends `/ig` command with cookies:

1. **Parse cookies** from the command argument
2. **Create database session** in `automation_sessions` table with status='running'
3. **Initialize Chrome driver** with anti-detection measures
4. **Execute 9-step automation** (see below)
5. **Send real-time updates** to Telegram after each step
6. **Capture screenshots** on failures only
7. **Update database** with final status (completed/failed)
8. **Send completion message** with final URL or error details

### Cookie Format

Expected format: `key1=value1; key2=value2; key3=value3`

Required cookies:
- `sessionid` - Instagram session identifier
- `ds_user_id` - Instagram user ID
- `csrftoken` - CSRF token for requests

### Response Messages

**On Start:**
```
🚀 Starting automation process...
✓ Chrome driver initialized successfully
```

**During Execution:**
```
📍 STEP 1: Logging into Instagram with cookies...
✓ STEP 1 SUCCESS: Instagram login verified!

📍 STEP 2: Navigating to Facebook Business and clicking 'Log in with Instagram'...
✓ STEP 2 SUCCESS: Clicked 'Log in with Instagram'

... (continues for all 9 steps)
```

**On Success:**
```
✅ ALL 9 STEPS COMPLETED SUCCESSFULLY!
✅ Instagram account fully connected to Facebook Business Manager
✅ Full authorization flow completed successfully
✅ Final URL: https://business.facebook.com/latest/...
```

**On Failure:**
```
❌ STEP X FAILED: Could not find [button name]
[Screenshot showing the failure state with element highlighted]
```

---

## 9-Step Automation Flow

### STEP 1: Instagram Login Verification

**Goal**: Verify Instagram cookies are valid and user is logged in

**Process**:
1. Navigate to `https://www.instagram.com`
2. Add all cookies from user's command to browser
3. Refresh the page to apply cookies
4. Check current URL

**Success Criteria**:
- URL contains `/accounts/onetap/` (Instagram's post-login page)
- NOT redirected to login page

**Failure Points**:
- Invalid cookies → redirects to login
- Expired session → redirects to login
- Wrong cookie format → cookies not set

**Code Location**: `instagram_automation.py` line ~250-300

**Selectors**: None (URL verification only)

---

### STEP 2: Click "Log in with Instagram"

**Goal**: Navigate to Facebook Business and click Instagram login button

**URL**: `https://business.facebook.com/business/loginpage/?next=https%3A%2F%2Fbusiness.facebook.com%2F%3Fnav_ref%3Dbiz_unified_f3_login_page_to_mbs&login_options%5B0%5D=FB&login_options%5B1%5D=IG&login_options%5B2%5D=SSO&config_ref=biz_login_tool_flavor_mbs`

**Process**:
1. Navigate to Facebook Business login page
2. Wait for page to load (5 seconds)
3. List all clickable elements on page (debugging)
4. Try 3 optimized selectors to find Instagram login button
5. Verify button text contains "Instagram" (NOT "Facebook")
6. Highlight button with red border
7. Click using one of 3 methods

**Selectors** (in priority order):

1. **XPath - Exact span class and text (WORKED)**
   ```xpath
   //span[@class='x1lliihq x193iq5w x6ikm8r x10wlt62 xlyipyv xuxw1ft' and text()='Log in with Instagram']
   ```

2. **XPath - Exact Instagram text with ancestor button**
   ```xpath
   //span[text()='Log in with Instagram']/ancestor::div[@role='button']
   ```

3. **XPath - Instagram button (excluding Facebook)**
   ```xpath
   //div[@role='button' and contains(., 'Log in with Instagram') and not(contains(., 'Facebook'))]
   ```

**Text Verification**: Must contain "Instagram"

**Success**: Button clicked, page starts transitioning

**Failure Points**:
- Button not found after all selectors
- Wrong button clicked (Facebook instead of Instagram)
- Page structure changed

**Code Location**: `instagram_automation.py` line ~320-370

---

### STEP 3: Handle OAuth Popup (if needed)

**Goal**: Handle Instagram OAuth authorization popup if it appears

**Process**:
1. Wait 5 seconds for popup to potentially open
2. Check number of window handles
3. If 2+ windows: popup opened
   - Switch to new popup window
   - Find "Log in as [username]" button
   - Click it
   - Close popup
   - Switch back to main window
4. If 1 window: already authenticated, skip this step

**Selectors for OAuth Button**:

1. **Button with exact text match**
   ```xpath
   //button[starts-with(text(), 'Log in as')]
   ```

2. **Button inside form**
   ```xpath
   //form//button[contains(text(), 'Log in')]
   ```

**Success**:
- Popup handled (if appeared)
- Or skipped (if no popup)

**Failure Points**:
- Popup appears but button not found
- Can't switch windows
- Session already exists (not really a failure)

**Code Location**: `instagram_automation.py` line ~380-420

---

### STEP 4: Wait for Business Manager Redirect

**Goal**: Verify successful redirect to Facebook Business home page

**Process**:
1. Wait up to 10 seconds
2. Check URL 3 times (with delays)
3. Verify URL contains `business_id=`

**Success Criteria**:
- URL contains `business.facebook.com/latest/`
- URL has `business_id=` parameter
- No longer on login page

**Failure Points**:
- Stuck on login page
- Redirected to error page
- business_id not in URL

**Code Location**: `instagram_automation.py` line ~430-470

**Selectors**: None (URL verification only)

---

### STEP 5: Navigate to Ads Center and Click "Get started"

**Goal**: Go to Ads Center and initiate ad creation flow

**URL**: `https://business.facebook.com/latest/ad_center/`

**Process**:
1. Navigate to ad_center URL
2. Wait 10 seconds for page load
3. List all clickable elements
4. Find "Get started" button
5. Click it

**Selectors**:

1. **XPath - Any div with Get started text (WORKED)**
   ```xpath
   //div[text()='Get started']
   ```

2. **XPath - Role button containing Get started**
   ```xpath
   //*[@role='button' and contains(text(), 'Get started')]
   ```

**Text Verification**: Must contain "Get started"

**Success**: Button clicked, navigates to boosted item picker

**Failure Points**:
- Button not visible
- Already past this step
- Ads Center not loading

**Code Location**: `instagram_automation.py` line ~480-530

---

### STEP 6: Click First "Continue" Button

**Goal**: Select an item to boost and click Continue

**Expected URL**: `boosted_item_picker`

**Process**:
1. Wait 5 seconds after previous step
2. List all Continue buttons on page
3. Find first Continue button (outside dialog)
4. Click it

**Selectors**:

1. **XPath - Any div with Continue text (WORKED)**
   ```xpath
   //div[text()='Continue']
   ```

2. **XPath - Continue button inside dialog modal**
   ```xpath
   //div[@role='dialog']//div[text()='Continue']
   ```

3. **XPath - Role button containing Continue**
   ```xpath
   //*[@role='button' and contains(text(), 'Continue')]
   ```

**Text Verification**: Must contain "Continue"

**Success**: Continue clicked, popup/dialog appears

**Failure Points**:
- No items available to boost
- Continue button disabled
- Already selected item

**Code Location**: `instagram_automation.py` line ~540-590

---

### STEP 7: Click Second "Continue" in Popup

**Goal**: Confirm selection in popup dialog

**Process**:
1. Wait 4 seconds for popup to fully appear
2. List all Continue buttons
3. Find Continue button INSIDE dialog/popup
4. Click it

**Selectors**:

1. **XPath - Continue button inside dialog modal (WORKED)**
   ```xpath
   //div[@role='dialog']//div[text()='Continue']
   ```

2. **XPath - Any div with Continue text**
   ```xpath
   //div[text()='Continue']
   ```

3. **XPath - Role button containing Continue**
   ```xpath
   //*[@role='button' and contains(text(), 'Continue')]
   ```

**Text Verification**: Must contain "Continue"

**Success**: Dialog Continue clicked, authorization flow starts

**Failure Points**:
- Dialog doesn't appear
- Button inside dialog not clickable
- Already confirmed

**Code Location**: `instagram_automation.py` line ~600-650

---

### STEP 8: Authorization - Continue As [username]

**Goal**: Authorize Facebook Business to access Instagram account

**Process**:
1. Wait 5 seconds for new tab to open
2. Detect 2 window handles (new OIDC tab)
3. Switch to authorization tab
4. Find "Continue as [username]" button
5. Click it
6. Wait 5 seconds for authorization to process
7. Close authorization tab
8. Switch back to main window

**Expected URL**: `business.facebook.com/oidc/`

**Selectors**:

1. **XPath - Exact button class with Continue as text (WORKED)**
   ```xpath
   //button[@class='_42ft _4jy0 layerConfirm _1-af _4jy6 _4jy1 selected _51sy' and @name='__CONFIRM__' and @type='submit' and starts-with(text(), 'Continue as')]
   ```

2. **XPath - Button with __CONFIRM__ name and Continue as text**
   ```xpath
   //button[@name='__CONFIRM__' and @type='submit' and contains(text(), 'Continue as')]
   ```

3. **XPath - Any button containing Continue as**
   ```xpath
   //button[contains(text(), 'Continue as')]
   ```

**Text Verification**: Must contain "Continue as"

**Success**: Authorization granted, tab closes, back to main window

**Failure Points**:
- Authorization tab doesn't open
- Button not found in OIDC page
- Can't switch windows
- Authorization rejected

**Code Location**: `instagram_automation.py` line ~660-730

---

### STEP 9: Click Third "Continue" Button

**Goal**: Final confirmation after authorization

**Process**:
1. Back on main window after authorization
2. Wait 3 seconds
3. List all Continue buttons
4. Find third Continue button
5. Click it
6. Wait for potential new tab to open and auto-close
7. Monitor tab for up to 10 seconds
8. Manually close if doesn't auto-close

**Selectors**:

1. **XPath - Continue button inside dialog modal**
   ```xpath
   //div[@role='dialog']//div[text()='Continue']
   ```

2. **XPath - Any div with Continue text**
   ```xpath
   //div[text()='Continue']
   ```

3. **XPath - Role button containing Continue**
   ```xpath
   //*[@role='button' and contains(text(), 'Continue')]
   ```

**Text Verification**: Must contain "Continue"

**Success**: Final Continue clicked, automation complete

**Failure Points**:
- Final Continue button not appearing
- Tab doesn't close
- Stuck in authorization loop

**Code Location**: `instagram_automation.py` line ~740-800

---

## Button Detection System

### Multi-Strategy Approach

For each button, the bot tries multiple strategies:

1. **Selector Type Priority**:
   - XPath (most reliable for dynamic Facebook UI)
   - CSS Selectors (faster but less flexible)
   - Role-based (accessibility attributes)

2. **Text Verification**:
   - Every button's text is verified before clicking
   - Prevents clicking wrong buttons with similar selectors

3. **Visual Highlighting**:
   - Red border added before clicking
   - Visible in screenshots
   - Helps debugging failures

4. **Three Click Methods**:

   **Method 1: Standard Selenium Click**
   ```python
   element.click()
   ```
   - Fastest and most reliable
   - Works 90% of the time

   **Method 2: JavaScript Click**
   ```python
   driver.execute_script("arguments[0].click();", element)
   ```
   - Bypasses overlays and visibility checks
   - Works when element is covered

   **Method 3: ActionChains**
   ```python
   ActionChains(driver).move_to_element(element).click().perform()
   ```
   - Simulates real mouse movement
   - Most human-like behavior

5. **Iframe Handling**:
   - Searches main page first
   - If not found, switches to each iframe
   - Searches within iframe
   - Switches back to main content

### Debug Logging

**Before Search**:
```
============================================================
STEP X - LISTING ALL BUTTONS:
Found 26 clickable elements on page
  ✓ Match 1: <div> role='button' text='Get started'
  ✓ Match 2: <div> role='button' text='Continue'
Found 2 elements matching 'Continue'
============================================================
```

**During Search**:
```
🔍 ATTEMPTING TO FIND AND CLICK: STEP X - Button Name
Total selectors to try: 6

[ATTEMPT 1/6]
Selector Type: xpath
Description: XPath - Exact span class and text
Selector: //span[@class='...' and text()='...']
Expected Text: Instagram

✓ Element FOUND using xpath
   Tag name: span
   Location: x=1516, y=454
   Size: width=135, height=17
   Element text: 'Log in with Instagram'
✓ Text VERIFIED: 'Instagram' found in 'Log in with Instagram'
   Is visible: True
   Is enabled: True
✓ Element is VISIBLE and ENABLED
   Scrolling element into view...
   Highlighting element...
   Attempting to click element...
   [CLICK METHOD 1] Trying element.click()...
✓✓✓ SUCCESSFULLY CLICKED using: element.click()
```

**After Success**:
```
🎉🎉🎉 SUCCESS SUMMARY FOR STEP X 🎉🎉🎉
   ✓ Found with: xpath
   ✓ Selector: //div[text()='Continue']
   ✓ Description: XPath - Any div with Continue text (WORKED)
   ✓ Clicked with: element.click()
   ✓ Attempt number: 1/6
   ✓ Step: STEP X - Button Name
```

### Helper Functions

**`list_clickable_elements(keyword=None)`**
- Lists all buttons/clickable elements on page
- Filters by keyword if provided
- Used for debugging before each search

**`try_find_and_click(selectors, step_name, timeout=15, verify_text=None, check_iframes=True)`**
- Main button detection function
- Tries each selector in order
- Verifies text if specified
- Checks iframes if needed
- Returns (success: bool, message: str)

**`highlight_element(element)`**
- Adds red border to element
- Visible in screenshots
- Helps identify what was clicked

**`take_screenshot(step_name)`**
- Captures current page state
- Stores in memory (base64)
- Sent via Telegram on failures

---

## Database Integration

### Tables

**bot_activity**
- Logs every command execution
- Fields: user_id, username, command, created_at
- Used for analytics and monitoring

**automation_sessions**
- Tracks each automation run
- Fields: user_id, status, step_reached, screenshot_count, error_message, duration_seconds, created_at, completed_at
- Status: 'running', 'completed', 'failed'

### Flow

1. **Session Start**: Create session with status='running'
2. **During Execution**: Update step_reached after each step
3. **On Failure**: Update status='failed', add error_message, increment screenshot_count
4. **On Success**: Update status='completed', set completed_at, calculate duration_seconds

### Queries

**Get recent sessions**:
```sql
SELECT * FROM automation_sessions
WHERE user_id = 935200729
ORDER BY created_at DESC
LIMIT 10;
```

**Get failure rate**:
```sql
SELECT
  status,
  COUNT(*) as count,
  AVG(step_reached) as avg_step
FROM automation_sessions
GROUP BY status;
```

---

## Anti-Detection Measures

### undetected-chromedriver

Uses `undetected-chromedriver` library to avoid bot detection:

```python
import undetected_chromedriver as uc

options = uc.ChromeOptions()
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-blink-features=AutomationControlled')

driver = uc.Chrome(options=options, use_subprocess=False)
```

### Fake User Agent

```python
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
options.add_argument(f'user-agent={user_agent}')
```

### Other Measures

- Random delays between steps (3-5 seconds)
- Scrolling elements into view before clicking
- Mouse movement simulation with ActionChains
- Realistic browser window size (1920x1080)

---

## Error Handling

### Stop-on-Failure Logic

- Each step returns (success: bool, message: str)
- If step fails, automation stops immediately
- Error message sent to user via Telegram
- Screenshot captured and sent
- Database updated with failure status

### Error Types

1. **Cookie Errors**: Invalid format, expired session
2. **Element Not Found**: Button/selector not found after all attempts
3. **Navigation Errors**: Wrong URL, failed redirect
4. **Window Handling**: Can't switch tabs, popup not appearing
5. **Click Errors**: Element not clickable, covered by overlay

### Recovery Strategies

Currently: **None** (fails immediately)

Potential future enhancements:
- Retry failed steps (max 3 attempts)
- Alternative flows (different URLs)
- User intervention prompts

---

## Deployment Configuration

### Docker Setup

**Dockerfile**:
```dockerfile
FROM python:3.11-slim

# Install Chrome and dependencies
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    && wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

### Railway Configuration

**railway.json**:
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "Dockerfile"
  },
  "deploy": {
    "startCommand": "python main.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Environment Variables

**Required in Railway**:
- `BOT_TOKEN` - From @BotFather
- `VITE_SUPABASE_URL` - Supabase project URL
- `VITE_SUPABASE_SUPABASE_ANON_KEY` - Supabase anon key

---

## Testing & Debugging

### Local Testing

```bash
# Set environment variables
export BOT_TOKEN="your_token"
export VITE_SUPABASE_URL="your_url"
export VITE_SUPABASE_SUPABASE_ANON_KEY="your_key"

# Run bot
python main.py

# Test in Telegram
/ig sessionid=...; ds_user_id=...; csrftoken=...
```

### Debug Mode

Enable verbose logging:
```python
logging.basicConfig(level=logging.DEBUG)
```

### Screenshot All Steps

Modify to capture on success too:
```python
self.take_screenshot(f"step{X}_success")
```

### Check Specific Step

Comment out early steps, start from specific step:
```python
# Skip to STEP 5
driver.get("https://business.facebook.com/latest/ad_center/")
# Continue from here
```

---

## Performance Optimization

### Selector Optimization

Based on production logs, selectors are ordered by:
1. Success rate (which worked most often)
2. Speed (XPath vs CSS)
3. Reliability (exact match vs contains)

### Wait Strategy

- **Explicit waits**: Used for critical elements (up to 15s)
- **Implicit waits**: None (causes conflicts)
- **Sleep delays**: Fixed 3-5 seconds between major steps

### Resource Usage

- **Memory**: ~500MB (Chrome + Python)
- **CPU**: Low (mostly waiting)
- **Network**: Minimal (only page loads)

Railway free tier is sufficient.

---

## Future Enhancements

### Potential Features

1. **Retry Logic**: Retry failed steps up to 3 times
2. **Multiple Accounts**: Support batch processing
3. **Scheduling**: Run automation at specific times
4. **Session Management**: Save/restore browser sessions
5. **Headful Mode**: Option to see browser (for debugging)
6. **Screenshot Gallery**: Save all screenshots to cloud storage
7. **Analytics Dashboard**: Web UI for session statistics
8. **Custom Workflows**: Allow user-defined automation steps

### Selector Improvements

1. **Machine Learning**: Learn from failures, adapt selectors
2. **DOM Analysis**: Dynamically generate selectors
3. **Image Recognition**: Use CV to find buttons when selectors fail
4. **Accessibility Tree**: Use aria-labels more extensively

---

## Security Considerations

### Cookie Safety

- Cookies transmitted via Telegram (encrypted in transit)
- Not stored permanently (only in memory during execution)
- Not logged to database (privacy)
- Cleared after browser closes

### Rate Limiting

- No current limits (each user can run once)
- Potential future: Max 5 runs per day per user

### Data Privacy

- User IDs logged (for analytics)
- Cookies not stored
- Screenshots deleted after sending
- Database contains no PII

---

## Known Issues & Limitations

### Current Limitations

1. **Single Account**: One automation run at a time per user
2. **No Queue**: Can't handle multiple concurrent users
3. **No Retry**: Fails immediately on any error
4. **Cookie Expiry**: User must provide fresh cookies each time
5. **UI Changes**: Breaks when Facebook changes their UI

### Handling UI Changes

When Facebook updates their interface:
1. Check Railway logs for which step failed
2. Inspect "LISTING BUTTONS" output to see available elements
3. Update selectors in code
4. Test locally first
5. Deploy updated version to Railway

### Browser Compatibility

- Only works with Chrome (not Firefox, Safari, etc.)
- Requires specific Chrome version compatible with undetected-chromedriver
- May break when Chrome updates (auto-updates handled)

---

## Complete Code Prompt for `/ig` Command

```
Create a Telegram bot command `/ig` that accepts Instagram cookies and automates connecting Instagram to Facebook Business Manager.

REQUIREMENTS:

1. Parse cookies from command argument (format: "key1=value1; key2=value2")

2. Initialize headless Chrome with anti-detection:
   - Use undetected-chromedriver
   - Fake Windows user agent
   - No automation flags

3. Execute 9 automation steps with stop-on-failure:
   - STEP 1: Set cookies, verify Instagram login at /accounts/onetap/
   - STEP 2: Go to FB Business login, click "Log in with Instagram"
   - STEP 3: Handle OAuth popup if appears, click "Log in as [user]"
   - STEP 4: Wait for redirect to business.facebook.com with business_id
   - STEP 5: Navigate to ad_center, click "Get started"
   - STEP 6: Click first "Continue" button
   - STEP 7: Click second "Continue" in popup dialog
   - STEP 8: Switch to OIDC tab, click "Continue as [user]", close tab
   - STEP 9: Click third "Continue", wait for final tab to auto-close

4. Button detection with multiple strategies:
   - Try 2-6 XPath/CSS selectors per button
   - Verify text before clicking (prevent wrong button)
   - Highlight with red border (visible in screenshots)
   - Try 3 click methods: element.click(), JS click, ActionChains
   - Check iframes if not found in main page

5. Send real-time updates to Telegram after each step

6. On failure: capture screenshot, send to user, update database

7. Log to Supabase:
   - bot_activity: command executions
   - automation_sessions: track status, step_reached, duration

8. Use optimized selectors (mark with "WORKED" which succeeded in production)

CRITICAL REQUIREMENTS:
- Stop immediately on any failure
- Screenshots only on failures
- Text verification on all buttons
- Detailed logging with selector/click method that worked
- List all buttons before searching (debugging)
```

---

**End of MAKER.md**

This document should be sufficient to recreate the entire project from scratch or modify specific components with full context.
