# Instagram Business Automation Bot - Deployment Guide

## Overview

This Telegram bot automates the process of connecting Instagram accounts to Facebook Business Manager for advertising purposes. It uses Selenium with Chrome in headless mode and provides real-time updates with screenshots.

## Features

- **4-step automation process** with stop-on-failure logic
- Instagram login verification before starting
- Smart button detection with text verification
- OAuth popup handling with username detection
- Business Manager redirect confirmation
- Screenshots only on failures (not every step)
- Live progress updates via Telegram
- Detailed logging with method tracking
- Database session tracking
- Anti-detection browser automation
- Runs 24/7 on Railway

## Requirements

1. **Telegram Bot Token** - Get from [@BotFather](https://t.me/BotFather)
2. **Supabase Database** - Already configured
3. **Railway Account** - For deployment

## Environment Variables

You need to set these environment variables in Railway:

```bash
BOT_TOKEN=your_telegram_bot_token_here
VITE_SUPABASE_URL=https://iqyskrqtaocyfnusbqah.supabase.co
VITE_SUPABASE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Railway Deployment (Recommended)

### Step 1: Get Telegram Bot Token

1. Open Telegram and search for [@BotFather](https://t.me/BotFather)
2. Send `/newbot` command
3. Follow the prompts to create your bot
4. Copy the bot token (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### Step 2: Push Code to GitHub

1. Create a new GitHub repository
2. Push all project files to the repository:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin YOUR_GITHUB_REPO_URL
   git push -u origin main
   ```

### Step 3: Deploy to Railway

1. Go to [Railway.app](https://railway.app)
2. Click "Start a New Project"
3. Choose "Deploy from GitHub repo"
4. Select your repository
5. Railway will automatically detect the Dockerfile

### Step 4: Configure Environment Variables

In the Railway dashboard:

1. Click on your project
2. Go to "Variables" tab
3. Add these variables:
   - `BOT_TOKEN` = Your Telegram bot token from Step 1
   - `VITE_SUPABASE_URL` = `https://iqyskrqtaocyfnusbqah.supabase.co`
   - `VITE_SUPABASE_SUPABASE_ANON_KEY` = (already in .env file)

### Step 5: Deploy

1. Railway will automatically start building and deploying
2. Monitor the deployment logs
3. Look for "Bot started successfully!" message
4. Your bot is now live!

## Verifying Deployment

1. Open Telegram
2. Search for your bot username
3. Send `/start` command
4. You should receive a welcome message

## Bot Commands

### User Commands

- `/start` - Welcome message and quick start guide
- `/help` - Detailed instructions on getting Instagram cookies
- `/cmds` - List all available commands
- `/ig <cookie>` - Start automation with Instagram cookie string

### Example Usage

```
/ig sessionid=abc123xyz; ds_user_id=456789; csrftoken=token123
```

## How to Get Instagram Cookies

1. Open Instagram in Chrome/Firefox
2. Press F12 to open Developer Tools
3. Go to "Application" (Chrome) or "Storage" (Firefox) tab
4. Expand "Cookies" → Click "https://www.instagram.com"
5. Copy these values:
   - `sessionid`
   - `ds_user_id`
   - `csrftoken`
6. Format as: `sessionid=VALUE1; ds_user_id=VALUE2; csrftoken=VALUE3`

## What the Bot Does

The automation process includes these steps:

1. **Step 1**: Navigate to Facebook Business login page
2. **Step 2**: Click "Log in with Instagram" button (NOT Facebook)
3. **Step 3**: Use cookies to authenticate on Instagram
4. **Step 4**: Verify redirect to Business Manager home
5. **Step 5**: Click "Create ad" button
6. **Step 6**: Process boosted item picker (2 Continue buttons)
7. **Step 7**: Handle Facebook OIDC authorization popup
8. **Step 8**: Repeat Continue clicks to finalize
9. **Final**: Verify completion and send all screenshots

## Database Tables

### bot_activity
Logs all bot interactions:
- User ID and username
- Command executed
- Timestamp

### automation_sessions
Tracks each automation run:
- User information
- Status (running/completed/failed)
- Last step reached
- Error messages
- Screenshot count
- Duration

## Monitoring

### Railway Logs

Access logs in Railway dashboard:
1. Click on your project
2. Go to "Deployments" tab
3. Click on latest deployment
4. View logs in real-time

### What to Look For

Successful startup shows:
```
Chrome driver initialized
Bot started successfully!
```

Automation logs show:
```
STEP 1: Navigating to Facebook Business login page...
STEP 2: Finding and clicking 'Log in with Instagram' button...
STEP 3: Handling Instagram login popup...
...
```

## Troubleshooting

### Bot Not Starting

**Problem**: Bot doesn't respond to commands

**Solution**:
- Check BOT_TOKEN is correct in Railway variables
- Verify bot is not stopped in @BotFather
- Check Railway logs for error messages
- Ensure deployment is "Active"

### Automation Fails

**Problem**: Automation stops at specific step

**Solution**:
- Check screenshots sent by bot to see where it failed
- Review Railway logs for specific error messages
- Verify Instagram cookies are fresh (not expired)
- Try with new cookies from a fresh login

### Chrome Crashes

**Problem**: "Chrome driver failed" error

**Solution**:
- This is handled by Dockerfile automatically
- Railway provides sufficient memory (usually)
- Check if deployment has enough resources
- Restart the deployment in Railway

### Cookie Issues

**Problem**: "Failed to set cookies" or "Not logged in"

**Solution**:
- Get fresh cookies (they expire)
- Ensure cookie format is correct (semicolon-separated)
- Must include: sessionid, ds_user_id, csrftoken
- No extra spaces or quotes

## Architecture

```
main.py                      # Telegram bot entry point
instagram_automation.py       # Selenium automation logic
requirements.txt              # Python dependencies
Dockerfile                    # Docker container config
railway.json                  # Railway deployment config
supabase/migrations/          # Database schema
```

## Security Notes

- Never commit .env file to Git (already in .gitignore)
- Don't share Instagram cookies publicly
- Cookies expire after some time
- Bot logs sessions to database for debugging
- Use at your own risk (may violate Instagram ToS)

## Performance

- Average automation time: 2-5 minutes
- Depends on network speed and page load times
- Screenshots add ~10-20 seconds total
- Railway provides stable uptime

## Updating the Bot

To deploy updates:

1. Make changes to code locally
2. Commit and push to GitHub:
   ```bash
   git add .
   git commit -m "Update description"
   git push
   ```
3. Railway auto-deploys from GitHub
4. Monitor deployment logs
5. Test with /start command

## Cost

- **Railway**: Free tier available (500 hours/month)
- **Supabase**: Free tier (already configured)
- **Telegram**: Free
- **Total**: $0/month on free tiers

## Support

For issues:
1. Check Railway deployment logs first
2. Verify environment variables are set
3. Test with /start command before automation
4. Review screenshots if automation fails
5. Try with fresh Instagram cookies

## Next Steps After Deployment

1. Send `/start` to your bot in Telegram
2. Read `/help` to understand cookie extraction
3. Get Instagram cookies from your browser
4. Test with `/ig <your_cookies>`
5. Watch live updates and screenshots
6. Check database for session logs

## Production Tips

- Keep Railway project active (free tier sleeps after inactivity)
- Monitor usage in Railway dashboard
- Check Supabase logs for database issues
- Update cookies regularly as they expire
- Screenshot analysis helps debug failures

Your bot is now ready to automate Instagram Business Manager connections!
