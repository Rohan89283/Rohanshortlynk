# Deployment Guide

## Overview

This is a Telegram bot with Instagram cookie checker and advanced proxy management system.

## Features

- Instagram cookie validation with screenshots
- Comprehensive proxy management
- Proxy validation and rotation
- Database storage (Supabase)
- Docker containerized with Selenium + Chrome

## Requirements

1. **Telegram Bot Token** - Get from [@BotFather](https://t.me/BotFather)
2. **Supabase Database** - Already configured
3. **Docker Environment** - Railway, Render, etc.

## Environment Variables

Set these in your deployment platform:

```bash
BOT_TOKEN=your_telegram_bot_token_here
VITE_SUPABASE_URL=https://ariexvjylsclqrbwrzby.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key_here
```

## Deployment Steps

### Railway Deployment

1. Connect your GitHub repository to Railway
2. Railway will auto-detect the Dockerfile
3. Set environment variables in Railway dashboard:
   - `BOT_TOKEN` - Your Telegram bot token
4. Deploy!

The Dockerfile automatically:
- Installs Chrome and ChromeDriver
- Sets up Python environment
- Installs all dependencies
- Runs the bot

### Database Setup

The database is already configured with Supabase. Tables are created via migrations:

- `bot_activity` - Tracks bot usage
- `proxies` - Stores user proxies with rotation logic

## Bot Commands

### Basic Commands
- `/start` - Welcome message
- `/cmds` - List all commands
- `/help` - Detailed help

### Instagram Commands
- `/ig [cookies]` - Check Instagram cookie validity

### Proxy Commands
- `/addproxy` - Add proxies (text or file)
- `/listproxy` - List all proxies
- `/deleteproxy [id]` - Delete specific proxy
- `/clearproxy` - Delete all proxies

## Technical Details

### Architecture

```
main.py                 # Bot entry point, command handlers
instagram_checker.py    # Instagram automation with Selenium
proxy_validator.py      # Proxy parsing and validation
proxy_manager.py        # Database operations for proxies
```

### Proxy System

- **Validation**: Each proxy is tested before adding
- **Rotation**: Least-recently-used algorithm
- **Health Tracking**: Success/failure counts
- **Auto-disable**: After 3 consecutive failures
- **Format Support**: Multiple proxy formats accepted

### Selenium Setup

- Headless Chrome in Docker
- ChromeDriver automatically matched to Chrome version
- Proxy support built-in
- Screenshot capability

## Monitoring

Check logs for:
- Bot startup confirmation
- Proxy validation results
- Instagram check results
- Database operations

## Troubleshooting

**Bot not starting:**
- Check BOT_TOKEN is set correctly
- Verify Supabase credentials

**Proxies not working:**
- Free proxies often fail validation
- Use premium/paid proxies for better results
- Check proxy format

**Instagram checks failing:**
- Cookie format incorrect
- Instagram may require additional auth
- Try with different proxy

## Next Steps

After deployment:
1. Start bot with `/start` command in Telegram
2. Add proxies with `/addproxy`
3. Test Instagram cookie checking with `/ig`
4. Monitor proxy performance with `/listproxy`

## Support

For issues:
1. Check deployment logs
2. Verify environment variables
3. Test with simple commands first
4. Review PROXY_GUIDE.md for proxy help
