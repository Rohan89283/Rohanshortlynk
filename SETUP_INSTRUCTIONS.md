# Instagram Business Manager - Setup Instructions

This application monitors Instagram Business accounts using the official Instagram Graph API and provides both a web dashboard and Telegram bot interface.

## Prerequisites

1. **Instagram Business Account**: You need an Instagram Business or Creator account
2. **Facebook Developer Account**: Required to create the Instagram app
3. **Facebook Page**: Your Instagram account must be connected to a Facebook Page
4. **Telegram Bot**: Optional, for Telegram notifications

## Setup Steps

### 1. Create Facebook/Instagram App

1. Go to [Facebook Developers](https://developers.facebook.com/)
2. Click "My Apps" > "Create App"
3. Select "Business" as app type
4. Fill in app details and create the app
5. In your app dashboard, add "Instagram Basic Display" product
6. Configure Instagram Basic Display:
   - Go to Basic Display settings
   - Add a redirect URI: `http://localhost:5173/auth/callback` (for local) or your production URL
   - Save changes
7. Get your credentials:
   - **App ID**: Found in Settings > Basic
   - **App Secret**: Found in Settings > Basic (click "Show")

### 2. Configure Environment Variables

The following environment variables need to be configured for your Edge Functions:

- `INSTAGRAM_APP_ID`: Your Facebook/Instagram App ID
- `INSTAGRAM_APP_SECRET`: Your Facebook/Instagram App Secret
- `INSTAGRAM_REDIRECT_URI`: The redirect URI configured in your app
- `TELEGRAM_BOT_TOKEN`: (Optional) Your Telegram bot token from @BotFather

### 3. Set Up Telegram Bot (Optional)

1. Open Telegram and search for @BotFather
2. Send `/newbot` and follow the instructions
3. Save the bot token provided
4. Set the webhook URL to: `https://your-project.supabase.co/functions/v1/telegram-bot`

   Use this command:
   ```bash
   curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-project.supabase.co/functions/v1/telegram-bot"
   ```

### 4. Using the Web Dashboard

1. Open the application in your browser
2. Sign up for an account
3. Click "Connect Account" to link your Instagram Business account
4. Authorize the app when redirected to Instagram
5. View your account metrics on the dashboard
6. Click "Refresh Status" to update account data

### 5. Using the Telegram Bot

Once configured, you can use these commands:

- `/start` - Start the bot and see welcome message
- `/connect` - Connect your Instagram Business account
- `/status` - View all connected accounts
- `/help` - Show help message

## Features

### Web Dashboard
- User authentication
- Connect multiple Instagram Business accounts
- View account metrics (followers, following, posts)
- Real-time status updates
- Automatic token refresh

### Telegram Bot
- Check account status on-the-go
- Receive account updates
- Quick refresh capabilities
- Easy account management

### API Endpoints

**Instagram OAuth**: `/functions/v1/instagram-oauth`
- `GET /auth-url` - Get Instagram authorization URL
- `POST /callback` - Handle OAuth callback

**Instagram Status**: `/functions/v1/instagram-status`
- `GET` - List all connected accounts
- `POST` - Refresh specific account status

**Telegram Bot**: `/functions/v1/telegram-bot`
- `POST` - Webhook endpoint for Telegram updates

## Database Schema

### `instagram_accounts`
Stores Instagram business account information and OAuth tokens

### `instagram_insights`
Stores historical metrics for accounts (impressions, reach, profile views)

## Security

- Row Level Security (RLS) enabled on all tables
- Users can only access their own data
- OAuth tokens are securely stored
- All API calls use HTTPS

## Troubleshooting

**Token Expired**: If you see authentication errors, the access token may have expired. Long-lived tokens last 60 days. Click "Refresh Status" to renew.

**Account Not Found**: Ensure your Instagram account is a Business or Creator account and is connected to a Facebook Page.

**Telegram Bot Not Responding**: Verify the webhook is set correctly and the bot token is configured.

## Notes

- Instagram Graph API has rate limits. Avoid excessive refreshes.
- Insights data is only available for Business and Creator accounts.
- Some metrics may not be available depending on account type and permissions.
