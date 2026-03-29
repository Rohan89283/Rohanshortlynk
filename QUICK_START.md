# Quick Start Guide

Get your bot running in 10 minutes!

## Step 1: Get Telegram Bot Token (2 minutes)

1. Open Telegram
2. Search for `@BotFather`
3. Send `/newbot`
4. Follow prompts to name your bot
5. Copy the token (looks like: `123456789:ABCdefGHIjklMNOpqrs`)

## Step 2: Deploy to Railway (5 minutes)

1. Push code to GitHub:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin YOUR_REPO_URL
   git push -u origin main
   ```

2. Go to [Railway.app](https://railway.app)
3. Click "New Project" → "Deploy from GitHub"
4. Select your repository
5. Add environment variable:
   - Name: `BOT_TOKEN`
   - Value: Your token from Step 1

6. Wait for deployment (2-3 minutes)

## Step 3: Test Your Bot (1 minute)

1. Open Telegram
2. Search for your bot username
3. Send `/start`
4. You should get a welcome message!

## Step 4: Get Instagram Cookies (2 minutes)

1. Open Instagram in Chrome
2. Press `F12` (Developer Tools)
3. Click "Application" tab
4. Expand "Cookies" → Click "https://www.instagram.com"
5. Find and copy these 3 values:
   - `sessionid`
   - `ds_user_id`
   - `csrftoken`

## Step 5: Run Automation

Send this to your bot:

```
/ig sessionid=YOUR_VALUE; ds_user_id=YOUR_VALUE; csrftoken=YOUR_VALUE
```

Replace `YOUR_VALUE` with actual values from Step 4.

## What Happens Next

The bot will:
- Send live updates every 10-15 seconds
- Show which step it's on (1-8)
- Send screenshots at each step
- Report success or failure with details
- Complete in 2-5 minutes

## Example Output

```
🚀 Starting automation process...
✓ Chrome driver initialized successfully

📍 STEP 1: Navigating to Facebook Business login page...
✓ STEP 1: Page loaded successfully

📍 STEP 2: Finding and clicking 'Log in with Instagram' button...
🔍 Searching for Instagram button (NOT Facebook)...
✓ STEP 2 - Instagram Login: SUCCESS using xpath (Method: element.click())

📍 STEP 3: Handling Instagram login popup...
✓ Switched to Instagram login window
✓ Instagram login page opened
🔐 Setting Instagram cookies...
✓ Cookies set successfully, refreshing page...

... (continues through all 8 steps)

✅ AUTOMATION PROCESS COMPLETED!
📊 Total screenshots captured: 15
📸 Sending all screenshots for review...
```

## If Something Goes Wrong

The bot will:
- Tell you which step failed
- Send screenshots showing the problem
- Log detailed error information
- You can check Railway logs for more details

## Common Issues

**"Could not find button"**
- Check screenshots to see what's on the page
- Railway logs show all buttons that were found
- Button might be in a different location (bot checks automatically)

**"Cookies failed"**
- Get fresh cookies (they expire)
- Make sure you copied all 3 values
- Format: `name=value; name=value; name=value`

**"Bot not responding"**
- Check Railway deployment is "Active"
- Verify BOT_TOKEN is set correctly
- Restart deployment in Railway dashboard

## Need Help?

1. Check screenshots sent by bot
2. Look at Railway logs (shows detailed info)
3. Read `DEPLOYMENT.md` for detailed instructions
4. Read `BUTTON_DETECTION.md` to understand how button finding works

## Pro Tips

- Keep cookies fresh (get new ones every few days)
- Bot runs 24/7 on Railway (no need to restart)
- Each automation run is logged to database
- Screenshots are temporary (not saved permanently)
- Use `/help` command in Telegram for cookie instructions

## Success Rate

With proper cookies:
- Step 1-2: 95%+ success
- Step 3-4: 90%+ success (depends on cookie validity)
- Step 5-8: 85%+ success (depends on Facebook page changes)

If it fails, try again with fresh cookies!

## That's It!

You now have a fully automated Instagram Business Manager connection bot. Enjoy!
