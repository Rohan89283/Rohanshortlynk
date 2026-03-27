import { createClient } from 'npm:@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Client-Info, Apikey',
};

interface OAuthCallbackRequest {
  code: string;
  user_id: string;
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

    const url = new URL(req.url);
    const path = url.pathname;

    if (path.includes('/callback') && req.method === 'POST') {
      const { code, user_id }: OAuthCallbackRequest = await req.json();

      const appId = Deno.env.get('INSTAGRAM_APP_ID');
      const appSecret = Deno.env.get('INSTAGRAM_APP_SECRET');
      const redirectUri = Deno.env.get('INSTAGRAM_REDIRECT_URI');

      if (!appId || !appSecret || !redirectUri) {
        throw new Error('Instagram credentials not configured');
      }

      const tokenUrl = `https://api.instagram.com/oauth/access_token`;
      const tokenResponse = await fetch(tokenUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: appId,
          client_secret: appSecret,
          grant_type: 'authorization_code',
          redirect_uri: redirectUri,
          code: code,
        }),
      });

      if (!tokenResponse.ok) {
        const error = await tokenResponse.text();
        throw new Error(`Token exchange failed: ${error}`);
      }

      const tokenData = await tokenResponse.json();
      const shortLivedToken = tokenData.access_token;
      const instagramUserId = tokenData.user_id;

      const longLivedTokenUrl = `https://graph.instagram.com/access_token?grant_type=ig_exchange_token&client_secret=${appSecret}&access_token=${shortLivedToken}`;
      const longLivedResponse = await fetch(longLivedTokenUrl);

      if (!longLivedResponse.ok) {
        throw new Error('Failed to get long-lived token');
      }

      const longLivedData = await longLivedResponse.json();
      const accessToken = longLivedData.access_token;
      const expiresIn = longLivedData.expires_in;
      const expiresAt = new Date(Date.now() + expiresIn * 1000);

      const profileUrl = `https://graph.instagram.com/${instagramUserId}?fields=id,username,account_type,media_count&access_token=${accessToken}`;
      const profileResponse = await fetch(profileUrl);

      if (!profileResponse.ok) {
        throw new Error('Failed to fetch Instagram profile');
      }

      const profileData = await profileResponse.json();

      const { error: dbError } = await supabase
        .from('instagram_accounts')
        .upsert({
          user_id,
          instagram_user_id: instagramUserId,
          username: profileData.username,
          account_type: profileData.account_type,
          media_count: profileData.media_count || 0,
          access_token: accessToken,
          token_expires_at: expiresAt.toISOString(),
          is_active: true,
          last_sync_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }, {
          onConflict: 'instagram_user_id',
        });

      if (dbError) {
        throw dbError;
      }

      return new Response(
        JSON.stringify({
          success: true,
          message: 'Instagram account connected successfully',
          account: {
            username: profileData.username,
            account_type: profileData.account_type,
          },
        }),
        {
          headers: {
            ...corsHeaders,
            'Content-Type': 'application/json',
          },
        }
      );
    }

    if (path.includes('/auth-url') && req.method === 'GET') {
      const appId = Deno.env.get('INSTAGRAM_APP_ID');
      const redirectUri = Deno.env.get('INSTAGRAM_REDIRECT_URI');

      if (!appId || !redirectUri) {
        throw new Error('Instagram credentials not configured');
      }

      const authUrl = `https://api.instagram.com/oauth/authorize?client_id=${appId}&redirect_uri=${encodeURIComponent(redirectUri)}&scope=user_profile,user_media&response_type=code`;

      return new Response(
        JSON.stringify({ auth_url: authUrl }),
        {
          headers: {
            ...corsHeaders,
            'Content-Type': 'application/json',
          },
        }
      );
    }

    return new Response(
      JSON.stringify({ error: 'Invalid endpoint' }),
      {
        status: 404,
        headers: {
          ...corsHeaders,
          'Content-Type': 'application/json',
        },
      }
    );
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
