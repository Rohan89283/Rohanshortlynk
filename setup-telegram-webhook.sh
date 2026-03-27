#!/bin/bash

BOT_TOKEN="8693694700:AAHATnxSJedwCbit88jw44oexVpwzOnXMJw"
WEBHOOK_URL="https://pjgtnzgugrvtbdmqmvmf.supabase.co/functions/v1/telegram-bot"

echo "Setting up Telegram webhook..."
echo "Bot Token: $BOT_TOKEN"
echo "Webhook URL: $WEBHOOK_URL"
echo ""

curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook?url=${WEBHOOK_URL}"

echo ""
echo ""
echo "Verifying webhook..."
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"

echo ""
echo ""
echo "Done! Your Telegram bot is now connected to your Edge Function."
echo "Try messaging your bot on Telegram with /start"
