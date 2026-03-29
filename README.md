# Instagram Business Automation Bot

A Telegram bot that automates the process of connecting Instagram accounts to Facebook Business Manager for advertising purposes.

## Features

- Automated Instagram to Facebook Business Manager connection
- Real-time progress updates via Telegram
- Screenshot capture at each step for debugging
- **Smart button detection with text verification**
- **Multiple selector strategies (XPath, CSS, role-based)**
- **Iframe support for nested elements**
- **Visual highlighting before clicking**
- **3 different click methods (standard, JS, ActionChains)**
- Detailed logging for troubleshooting with method tracking
- Database logging for session tracking
- Anti-detection measures using undetected-chromedriver
- Fake user agents and anti-bot protection

## Commands

- `/start` - Welcome message and quick start guide
- `/help` - Detailed help and usage instructions
- `/cmds` - List all available commands
- `/ig <cookie>` - Start Instagram automation with your cookie string

## How It Works

The bot automates **4 simple steps** with stop-on-failure logic:

### Step 1: Instagram Login Verification
- Goes to Instagram with your cookies
- Verifies login at `/accounts/onetap/` URL
- Confirms you're logged in (not redirected to login page)
- **Stops if**: Cookies invalid or login fails

### Step 2: Click "Log in with Instagram"
- Navigates to Facebook Business login page
- Lists all buttons for debugging
- Finds "Log in with Instagram" button (NOT Facebook)
- Uses 6 selector strategies + text verification
- **Stops if**: Button not found

### Step 3: OAuth Popup Authorization
- Detects Instagram OAuth popup window
- Lists all "Log in" buttons
- Clicks "Log in as [username]" button
- Verifies button text before clicking
- **Stops if**: Popup doesn't open or button not found

### Step 4: Verify Business Home
- Switches back to main window
- Checks URL contains `business_id=` parameter
- Confirms redirect to Business Manager home
- **Stops if**: Wrong URL or redirect failed

**Key Features:**
- Stop immediately on any failure
- Screenshots only taken on failures
- Button text verified before clicking
- 4-8 selector attempts per button
- Logs which method worked/failed

## Prerequisites

- Telegram Bot Token (get from [@BotFather](https://t.me/botfather))
- Instagram account cookies
- Supabase account (for database logging)

## Environment Variables

Create a `.env` file with:

```env
BOT_TOKEN=your_telegram_bot_token_here
VITE_SUPABASE_URL=your_supabase_url
VITE_SUPABASE_SUPABASE_ANON_KEY=your_supabase_anon_key
```

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Install Google Chrome (required for Selenium):
```bash
# On Ubuntu/Debian
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

3. Set up environment variables in `.env`

4. Run the bot:
```bash
python main.py
```

## Railway Deployment

### Step 1: Prepare Your Repository

1. Make sure all files are committed to your Git repository
2. Ensure `.env` is in `.gitignore` (secrets should not be committed)

### Step 2: Create Railway Project

1. Go to [Railway.app](https://railway.app)
2. Sign up or log in
3. Click "New Project"
4. Select "Deploy from GitHub repo"
5. Choose your repository

### Step 3: Configure Environment Variables

In Railway dashboard, add these environment variables:

```
BOT_TOKEN=<your_telegram_bot_token>
VITE_SUPABASE_URL=<your_supabase_url>
VITE_SUPABASE_SUPABASE_ANON_KEY=<your_supabase_anon_key>
```

### Step 4: Deploy

Railway will automatically:
- Detect the Dockerfile
- Build the Docker image
- Install Chrome and dependencies
- Deploy your bot

The bot will start automatically and run 24/7.

### Step 5: Monitor Logs

- View logs in Railway dashboard under "Deployments" > "View Logs"
- Check for any errors or successful startup messages

## Getting Instagram Cookies

1. Log into Instagram in your browser
2. Open Developer Tools (F12)
3. Go to Application/Storage > Cookies
4. Copy the cookie string in this format:
   ```
   sessionid=abc123; ds_user_id=456789; csrftoken=xyz789
   ```

## Usage Example

```
/ig sessionid=abc123xyz; ds_user_id=456789; csrftoken=token123
```

The bot will:
- Start the automation process
- Send live updates for each step
- Send screenshots at each stage
- Notify you when complete or if any errors occur

## Database Schema

### bot_activity
Logs all bot commands and interactions:
- `user_id` - Telegram user ID
- `username` - Telegram username
- `command` - Command executed
- `created_at` - Timestamp

### automation_sessions
Tracks automation runs:
- `user_id` - Telegram user ID
- `status` - running/completed/failed
- `step_reached` - Last successful step
- `screenshot_count` - Number of screenshots
- `error_message` - Error details if failed
- `duration_seconds` - Total duration

## Advanced Button Detection

The bot uses **intelligent button detection** to ensure it clicks the RIGHT button:

- **Text Verification**: Confirms button contains expected text (e.g., "Instagram" NOT "Facebook")
- **Multiple Selectors**: Tries 6-8 different ways to find each button
- **Iframe Support**: Automatically checks inside iframes if button not found in main page
- **Visual Highlighting**: Highlights button with red border before clicking (visible in screenshots)
- **Triple Click Methods**: Tries standard click, JavaScript click, and ActionChains
- **Debug Logging**: Lists all buttons on page before searching, logs which method worked

See `BUTTON_DETECTION.md` for complete technical details.

## Troubleshooting

### Bot not responding
- Check if BOT_TOKEN is correct
- Verify bot is running in Railway logs
- Ensure bot is not stopped in BotFather

### Automation fails at specific step
- Check screenshots sent by bot (button will be highlighted in red)
- Review Railway logs - they show which selectors were tried
- Look for "LISTING BUTTONS" sections in logs to see what was available
- Verify Instagram cookies are valid and not expired
- Logs show exact selector and click method that worked/failed

### Button not found errors
- Bot automatically lists all buttons on page
- Check logs for "Found X elements matching 'keyword'"
- Button might be in iframe (bot checks automatically)
- Screenshots show page state when button search happened

### Chrome crashes
- This is handled by the Dockerfile with proper dependencies
- Railway provides enough resources for Chrome to run

## Security Notes

- Never share your Instagram cookies
- Cookies expire after some time, you'll need fresh ones
- Bot uses anti-detection measures but use at your own risk
- All data is logged to Supabase for debugging purposes

## Tech Stack

- Python 3.11
- python-telegram-bot (Telegram integration)
- Selenium + undetected-chromedriver (Browser automation)
- Supabase (Database)
- Docker (Containerization)
- Railway (Deployment platform)

## License

This project is for educational purposes only.
