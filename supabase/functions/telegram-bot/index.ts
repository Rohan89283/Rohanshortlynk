import { createClient } from 'npm:@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Client-Info, Apikey',
};

interface TelegramUpdate {
  message?: {
    chat: {
      id: number;
    };
    text?: string;
    from?: {
      id: number;
      username?: string;
    };
  };
  callback_query?: {
    id: string;
    data?: string;
    message?: {
      chat: {
        id: number;
      };
    };
  };
}

async function sendTelegramMessage(chatId: number, text: string, replyMarkup?: any) {
  const botToken = Deno.env.get('TELEGRAM_BOT_TOKEN');
  if (!botToken) {
    throw new Error('Telegram bot token not configured');
  }

  const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      chat_id: chatId,
      text: text,
      parse_mode: 'HTML',
      reply_markup: replyMarkup,
    }),
  });

  return await response.json();
}

async function answerCallbackQuery(callbackQueryId: string, text?: string) {
  const botToken = Deno.env.get('TELEGRAM_BOT_TOKEN');
  const url = `https://api.telegram.org/bot${botToken}/answerCallbackQuery`;
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      callback_query_id: callbackQueryId,
      text: text || 'Processing...',
    }),
  });
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      status: 200,
      headers: corsHeaders,
    });
  }

  try {
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    );

    const update: TelegramUpdate = await req.json();

    if (update.message) {
      const chatId = update.message.chat.id;
      const text = update.message.text || '';
      const telegramUserId = update.message.from?.id;

      if (text === '/start') {
        const welcomeMessage = `
🎉 <b>Welcome to Instagram Business Manager Bot!</b>

This bot helps you monitor your Instagram business accounts using the official Instagram Graph API.

<b>Available Commands:</b>
/connect - Connect your Instagram Business account
/status - Check all connected accounts status
/help - Show this help message

To get started, use /connect to link your Instagram Business account.
        `.trim();

        await sendTelegramMessage(chatId, welcomeMessage);
      } else if (text === '/connect') {
        const { data: existingMapping } = await supabase
          .from('instagram_accounts')
          .select('user_id')
          .limit(1)
          .maybeSingle();

        const authUrl = `${Deno.env.get('SUPABASE_URL')}/functions/v1/instagram-oauth/auth-url`;
        const authResponse = await fetch(authUrl);
        const authData = await authResponse.json();

        const message = `
🔗 <b>Connect Your Instagram Business Account</b>

Click the button below to authorize this app to access your Instagram Business account.

After authorization, you'll receive a confirmation message here.

<i>Note: Only Instagram Business or Creator accounts are supported.</i>
        `.trim();

        const keyboard = {
          inline_keyboard: [
            [
              {
                text: '🔐 Connect Instagram Account',
                url: authData.auth_url,
              },
            ],
          ],
        };

        await sendTelegramMessage(chatId, message, keyboard);
      } else if (text === '/status') {
        const { data: accounts, error } = await supabase
          .from('instagram_accounts')
          .select('*')
          .eq('is_active', true);

        if (error || !accounts || accounts.length === 0) {
          await sendTelegramMessage(
            chatId,
            '❌ No connected Instagram accounts found.\n\nUse /connect to add your first account.'
          );
          return new Response(JSON.stringify({ ok: true }), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          });
        }

        const keyboard = {
          inline_keyboard: accounts.map((account: any) => [
            {
              text: `📊 ${account.username}`,
              callback_data: `refresh_${account.id}`,
            },
          ]),
        };

        let statusMessage = '<b>📱 Connected Instagram Accounts:</b>\n\n';
        for (const account of accounts) {
          statusMessage += `<b>@${account.username}</b>\n`;
          statusMessage += `👥 Followers: ${account.followers_count || 0}\n`;
          statusMessage += `📸 Posts: ${account.media_count || 0}\n`;
          statusMessage += `🔄 Last synced: ${new Date(account.last_sync_at).toLocaleString()}\n\n`;
        }

        statusMessage += '<i>Click on an account to refresh its status.</i>';

        await sendTelegramMessage(chatId, statusMessage, keyboard);
      } else if (text === '/help') {
        const helpMessage = `
<b>📖 Help - Instagram Business Manager Bot</b>

<b>Commands:</b>
/start - Start the bot and see welcome message
/connect - Connect a new Instagram Business account
/status - View all connected accounts and their metrics
/help - Show this help message

<b>Features:</b>
• Monitor follower count
• Track post count
• View account insights
• Real-time status updates

<b>Requirements:</b>
• Instagram Business or Creator account
• Facebook Page connected to your Instagram account

For support, contact your administrator.
        `.trim();

        await sendTelegramMessage(chatId, helpMessage);
      } else {
        await sendTelegramMessage(
          chatId,
          '❓ Unknown command. Use /help to see available commands.'
        );
      }
    }

    if (update.callback_query) {
      const callbackData = update.callback_query.data || '';
      const chatId = update.callback_query.message?.chat.id!;

      await answerCallbackQuery(update.callback_query.id, 'Refreshing...');

      if (callbackData.startsWith('refresh_')) {
        const accountId = callbackData.replace('refresh_', '');

        const { data: account } = await supabase
          .from('instagram_accounts')
          .select('*')
          .eq('id', accountId)
          .maybeSingle();

        if (!account) {
          await sendTelegramMessage(chatId, '❌ Account not found.');
          return new Response(JSON.stringify({ ok: true }), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          });
        }

        const fields = 'id,username,account_type,followers_count,follows_count,media_count,profile_picture_url';
        const profileUrl = `https://graph.instagram.com/${account.instagram_user_id}?fields=${fields}&access_token=${account.access_token}`;
        const profileResponse = await fetch(profileUrl);

        if (!profileResponse.ok) {
          await sendTelegramMessage(chatId, '❌ Failed to fetch account status. Token may have expired.');
          return new Response(JSON.stringify({ ok: true }), {
            headers: { ...corsHeaders, 'Content-Type': 'application/json' },
          });
        }

        const profileData = await profileResponse.json();

        await supabase
          .from('instagram_accounts')
          .update({
            username: profileData.username,
            followers_count: profileData.followers_count || 0,
            follows_count: profileData.follows_count || 0,
            media_count: profileData.media_count || 0,
            last_sync_at: new Date().toISOString(),
          })
          .eq('id', accountId);

        const statusMessage = `
✅ <b>Account Status Updated</b>

<b>@${profileData.username}</b>
📊 Account Type: ${profileData.account_type}
👥 Followers: ${profileData.followers_count || 0}
👤 Following: ${profileData.follows_count || 0}
📸 Posts: ${profileData.media_count || 0}
🕐 Updated: ${new Date().toLocaleString()}
        `.trim();

        await sendTelegramMessage(chatId, statusMessage);
      }
    }

    return new Response(JSON.stringify({ ok: true }), {
      headers: {
        ...corsHeaders,
        'Content-Type': 'application/json',
      },
    });
  } catch (error) {
    console.error('Error:', error);
    return new Response(
      JSON.stringify({ error: error.message }),
      {
        status: 500,
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json',
        },
      }
    );
  }
});
