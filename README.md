# Instagram Business Automation Bot

A powerful Telegram bot that automates the complete process of connecting Instagram accounts to Facebook Business Manager for advertising purposes. Features intelligent button detection, real-time updates, and comprehensive error handling.

## Features

- **Complete Automation**: 9-step automated flow from Instagram login to Business Manager connection
- **Smart Button Detection**: Multiple selector strategies (XPath, CSS, role-based) with text verification
- **Real-time Updates**: Live progress notifications via Telegram
- **Visual Debugging**: Screenshots on failures with highlighted elements
- **Robust Click Methods**: 3 different click strategies (standard, JavaScript, ActionChains)
- **Iframe Support**: Automatically searches within iframes for nested elements
- **Anti-Detection**: Uses undetected-chromedriver with fake user agents
- **Database Logging**: Tracks all sessions in Supabase for analytics
- **Error Recovery**: Stop-on-failure with detailed error messages

## Quick Start

### Commands

- `/start` - Welcome message and bot introduction
- `/help` - Detailed usage instructions
- `/cmds` - List all available commands
- `/ig <cookie>` - Start automation with Instagram cookies

### Example Usage

```
/ig sessionid=abc123xyz; ds_user_id=456789; csrftoken=token123
```

## Complete Automation Flow (9 Steps)

### STEP 1: Instagram Login Verification
- Navigates to Instagram with your cookies
- Sets all cookies and refreshes page
- Verifies login at `/accounts/onetap/` URL
- **Stops if**: Cookies invalid or redirected to login page

### STEP 2: Click "Log in with Instagram"
- Opens Facebook Business login page
- Lists all clickable elements for debugging
- Finds and clicks "Log in with Instagram" button
- Uses 3 optimized selectors with text verification
- **Stops if**: Button not found after all attempts

### STEP 3: Handle OAuth Popup (if needed)
- Detects if Instagram OAuth popup opens
- Clicks "Log in as [username]" if popup appears
- Skips if already authenticated (no popup)
- **Stops if**: Popup appears but button not found

### STEP 4: Wait for Business Manager Redirect
- Waits for redirect to Business home page
- Verifies URL contains `business_id=` parameter
- Confirms successful login transition
- **Stops if**: Redirect fails or wrong URL

### STEP 5: Navigate to Ads Center
- Goes to Facebook Ads Center URL
- Waits for page load
- Finds and clicks "Get started" button
- Uses 2 optimized selectors
- **Stops if**: Button not found or page doesn't load

### STEP 6: Click First "Continue" Button
- Detects boosted item picker page
- Lists all available buttons
- Finds and clicks first "Continue" button
- Uses 3 optimized selectors
- **Stops if**: Continue button not found

### STEP 7: Click Second "Continue" in Popup
- Waits for popup dialog to appear
- Finds "Continue" button inside dialog
- Clicks second Continue button
- Uses dialog-specific selectors
- **Stops if**: Popup doesn't appear or button not found

### STEP 8: Authorization - Continue As [username]
- Switches to new authorization tab (OIDC page)
- Finds "Continue as [username]" button
- Clicks authorization button
- Waits for authorization to complete
- Closes auth tab and switches back to main window
- **Stops if**: Auth tab doesn't open or button not found

### STEP 9: Click Third "Continue" Button
- Back on main window after authorization
- Finds and clicks third "Continue" button
- New tab may open and auto-close
- Waits up to 10 seconds for auto-close
- Manually closes tab if it doesn't auto-close
- **Stops if**: Final Continue button not found

### Final Verification
- Confirms all 9 steps completed successfully
- Reports final URL
- Sends completion message to user
- Logs session data to database

## Prerequisites

1. **Telegram Bot Token**
   - Get from [@BotFather](https://t.me/botfather)
   - Send `/newbot` and follow instructions

2. **Instagram Account Cookies**
   - Must be logged into Instagram
   - Need valid session cookies (see below)

3. **Supabase Account**
   - Free tier available at [supabase.com](https://supabase.com)
   - Used for logging and analytics

## Environment Variables

Create a `.env` file in project root:

```env
BOT_TOKEN=your_telegram_bot_token_here
VITE_SUPABASE_URL=your_supabase_project_url
VITE_SUPABASE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

## Getting Instagram Cookies

1. Open Instagram in your browser and log in
2. Open Developer Tools (F12)
3. Go to **Application** (Chrome) or **Storage** (Firefox)
4. Navigate to **Cookies** > `https://www.instagram.com`
5. Find these cookies and copy their values:
   - `sessionid`
   - `ds_user_id`
   - `csrftoken`

6. Format as: `sessionid=VALUE1; ds_user_id=VALUE2; csrftoken=VALUE3`

**Important**:
- Cookies expire after some time
- Never share your cookies with anyone
- Use fresh cookies for each automation run

## Local Development

### Installation

```bash
# Clone the repository
git clone <your-repo-url>
cd instagram-automation-bot

# Install Python dependencies
pip install -r requirements.txt

# Install Google Chrome (required for Selenium)
# On Ubuntu/Debian:
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# On macOS:
brew install --cask google-chrome
```

### Setup Supabase Database

1. Create a Supabase project
2. The migrations will run automatically on first connection
3. Two tables will be created:
   - `bot_activity` - Command logs
   - `automation_sessions` - Session tracking

### Run the Bot

```bash
python main.py
```

You should see:
```
2026-03-29 21:15:04,060 - __main__ - INFO - Bot started successfully!
```

## Railway Deployment (Recommended)

### Why Railway?

- Runs 24/7 automatically
- Handles Chrome installation
- Free tier available
- Simple deployment process
- Built-in logging

### Deployment Steps

#### 1. Prepare Repository

```bash
# Ensure all files are committed
git add .
git commit -m "Ready for deployment"
git push origin main

# Verify .env is in .gitignore
echo ".env" >> .gitignore
```

#### 2. Deploy to Railway

1. Go to [railway.app](https://railway.app)
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Choose your repository
6. Railway will detect the Dockerfile automatically

#### 3. Add Environment Variables

In Railway dashboard:
1. Click on your project
2. Go to **Variables** tab
3. Add each variable:

```
BOT_TOKEN = <your_telegram_bot_token>
VITE_SUPABASE_URL = <your_supabase_url>
VITE_SUPABASE_SUPABASE_ANON_KEY = <your_supabase_anon_key>
```

#### 4. Verify Deployment

- Check **Deployments** tab for build status
- View **Logs** to see bot startup
- Look for "Bot started successfully!" message

#### 5. Monitor

- Real-time logs available in Railway dashboard
- Check Supabase for session data
- Screenshots sent via Telegram on failures

### Railway Configuration Files

The project includes:
- `Dockerfile` - Container setup with Chrome
- `railway.json` - Build and start configuration
- `requirements.txt` - Python dependencies

No additional configuration needed!

## Database Schema

### bot_activity Table

Logs all user commands and interactions:

```sql
CREATE TABLE bot_activity (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id BIGINT NOT NULL,
  username TEXT,
  command TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### automation_sessions Table

Tracks each automation run:

```sql
CREATE TABLE automation_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id BIGINT NOT NULL,
  status TEXT NOT NULL,
  step_reached INTEGER,
  screenshot_count INTEGER DEFAULT 0,
  error_message TEXT,
  duration_seconds INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);
```

Status values: `running`, `completed`, `failed`

## Advanced Button Detection

The bot uses **intelligent multi-strategy button detection**:

### Text Verification
- Confirms button contains expected text
- Example: Verifies "Instagram" NOT "Facebook"
- Prevents clicking wrong buttons

### Multiple Selectors
Each button has 2-6 optimized selectors:
- XPath with exact classes (most reliable)
- XPath with text matching
- XPath with role attributes
- CSS selectors (fallback)

### Selector Optimization
Based on production logs:
- Selectors ordered by success rate
- Fastest working selectors tried first
- Marked with "(WORKED)" in code

### Click Methods
Three strategies attempted in order:
1. **element.click()** - Standard Selenium click
2. **JavaScript click** - Bypasses overlay issues
3. **ActionChains** - Moves mouse and clicks

### Visual Debugging
- Highlights elements with red border before clicking
- Screenshots show exact element being clicked
- Visible in failure screenshots

### Iframe Support
- Automatically searches main page first
- Switches to iframes if element not found
- Searches all iframes systematically

### Debug Logging

Before each button search:
```
============================================================
STEP X - LISTING ALL BUTTONS:
Found 26 clickable elements on page
  ✓ Match 1: <div> role='button' text='Get started'
  ✓ Match 2: <div> role='button' text='Continue'
Found 2 elements matching 'keyword'
============================================================
```

After successful click:
```
🎉🎉🎉 SUCCESS SUMMARY FOR STEP X 🎉🎉🎉
   ✓ Found with: xpath
   ✓ Selector: //div[text()='Continue']
   ✓ Description: XPath - Any div with Continue text
   ✓ Clicked with: element.click()
   ✓ Attempt number: 1/6
```

## Troubleshooting

### Bot Not Responding

**Problem**: Bot doesn't reply to commands

**Solutions**:
- Verify `BOT_TOKEN` is correct in Railway variables
- Check Railway logs for "Bot started successfully!"
- Ensure bot is not stopped in @BotFather
- Check `/cmds` to verify bot is active

### Invalid Cookies Error

**Problem**: "Instagram login failed" message

**Solutions**:
- Get fresh cookies from browser
- Ensure cookies are formatted correctly
- Check if Instagram session expired
- Try logging out and back into Instagram

### Button Not Found

**Problem**: Automation stops with "Button not found"

**Solutions**:
- Check Railway logs for "LISTING BUTTONS" section
- See which buttons were available on page
- Screenshots show page state (sent via Telegram)
- Facebook may have changed their UI

### Automation Stops at Specific Step

**Problem**: Fails consistently at same step

**Solutions**:
1. Check Railway logs for that step number
2. Look for selector attempts and which failed
3. Review screenshot sent by bot (button highlighted)
4. Check if Facebook UI changed
5. Try with fresh Instagram cookies

### Chrome Crashes

**Problem**: "Chrome driver failed" error

**Solutions**:
- Railway Dockerfile handles Chrome installation
- Check Railway logs for Chrome version
- Restart deployment in Railway
- Verify sufficient resources allocated

### Screenshots Not Sending

**Problem**: No screenshots received on failure

**Solutions**:
- Screenshots only sent on failures (by design)
- Check Telegram file size limits
- Verify bot has permission to send photos
- Check Railway logs for screenshot errors

### Database Connection Failed

**Problem**: Supabase connection errors in logs

**Solutions**:
- Verify `VITE_SUPABASE_URL` is correct
- Check `VITE_SUPABASE_SUPABASE_ANON_KEY` is valid
- Ensure Supabase project is active (not paused)
- Check Supabase project API settings

## Logging and Monitoring

### Railway Logs

View in real-time:
1. Go to Railway dashboard
2. Click on your project
3. Select **Deployments** > **View Logs**

Key log sections:
- `Bot started successfully!` - Startup confirmation
- `STEP X - LISTING ALL BUTTONS` - Button detection
- `SUCCESS SUMMARY` - Successful clicks
- `TIMEOUT: Element not found` - Failed attempts

### Supabase Logs

Query session history:
```sql
SELECT * FROM automation_sessions
ORDER BY created_at DESC
LIMIT 10;
```

Check command usage:
```sql
SELECT command, COUNT(*) as count
FROM bot_activity
GROUP BY command
ORDER BY count DESC;
```

## Security & Privacy

### Important Notes

- **Never share your cookies** - They provide full account access
- **Cookies expire** - Get fresh ones for each use
- **Use at own risk** - Automation may violate Instagram/Facebook ToS
- **Data logging** - All sessions logged to Supabase
- **Anti-detection** - Uses undetected-chromedriver but not foolproof

### Best Practices

1. Use a test Instagram account first
2. Don't run automation too frequently
3. Monitor for any account warnings
4. Keep Supabase data secure
5. Rotate cookies regularly

## Tech Stack

- **Python 3.11** - Core language
- **python-telegram-bot** - Telegram Bot API
- **Selenium 4.x** - Browser automation
- **undetected-chromedriver** - Anti-detection
- **Supabase** - PostgreSQL database
- **Docker** - Containerization
- **Railway** - Cloud deployment
- **Google Chrome** - Headless browser

## File Structure

```
instagram-automation-bot/
├── main.py                     # Bot entry point
├── instagram_automation.py     # Automation logic
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Docker container setup
├── railway.json                # Railway configuration
├── .env                        # Environment variables (local)
├── .gitignore                  # Git ignore rules
├── README.md                   # This file
├── MAKER.md                    # Development prompts
└── supabase/
    └── migrations/
        ├── 20260328061806_create_bot_activity_table.sql
        └── 20260329180814_create_automation_sessions_table.sql
```

## Contributing

This is a personal automation project. If you want to use it:

1. Fork the repository
2. Customize for your needs
3. Deploy to your own Railway account
4. Use responsibly

## Support

For issues or questions:
- Check Railway logs first
- Review Troubleshooting section
- Check Supabase for session errors
- Review screenshots sent by bot

## Disclaimer

This project is for **educational purposes only**.

- Automating Instagram/Facebook may violate their Terms of Service
- Use at your own risk
- No warranty or guarantee provided
- Author not responsible for account bans or issues
- Respect platform guidelines and rate limits

## License

MIT License - Use at your own risk

---

**Made with ❤️ for automation enthusiasts**
