import { createClient } from 'npm:@supabase/supabase-js@2';

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Client-Info, Apikey',
};

interface AccountStatus {
  username: string;
  account_type: string;
  followers_count: number;
  follows_count: number;
  media_count: number;
  profile_picture_url?: string;
  is_active: boolean;
  last_sync_at: string;
}

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, {
      status: 200,
      headers: corsHeaders,
    });
  }

  try {
    const authHeader = req.headers.get('Authorization');
    if (!authHeader) {
      throw new Error('Missing authorization header');
    }

    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
      {
        global: {
          headers: { Authorization: authHeader },
        },
      }
    );

    const { data: { user }, error: userError } = await supabase.auth.getUser(
      authHeader.replace('Bearer ', '')
    );

    if (userError || !user) {
      throw new Error('Unauthorized');
    }

    const url = new URL(req.url);
    const accountId = url.searchParams.get('account_id');

    if (req.method === 'GET' && !accountId) {
      const { data: accounts, error: accountsError } = await supabase
        .from('instagram_accounts')
        .select('*')
        .eq('user_id', user.id)
        .eq('is_active', true);

      if (accountsError) {
        throw accountsError;
      }

      return new Response(
        JSON.stringify({ accounts }),
        {
          headers: {
            ...corsHeaders,
            'Content-Type': 'application/json',
          },
        }
      );
    }

    if (req.method === 'POST' || (req.method === 'GET' && accountId)) {
      const targetAccountId = accountId || (await req.json()).account_id;

      const { data: account, error: accountError } = await supabase
        .from('instagram_accounts')
        .select('*')
        .eq('id', targetAccountId)
        .eq('user_id', user.id)
        .maybeSingle();

      if (accountError || !account) {
        throw new Error('Account not found');
      }

      const fields = [
        'id',
        'username',
        'account_type',
        'followers_count',
        'follows_count',
        'media_count',
        'profile_picture_url',
      ];

      const profileUrl = `https://graph.instagram.com/${account.instagram_user_id}?fields=${fields.join(',')}&access_token=${account.access_token}`;
      const profileResponse = await fetch(profileUrl);

      if (!profileResponse.ok) {
        const errorData = await profileResponse.json();
        throw new Error(`Instagram API error: ${errorData.error?.message || 'Unknown error'}`);
      }

      const profileData = await profileResponse.json();

      const insightsUrl = `https://graph.instagram.com/${account.instagram_user_id}/insights?metric=impressions,reach,profile_views&period=day&access_token=${account.access_token}`;
      let insightsData = null;

      try {
        const insightsResponse = await fetch(insightsUrl);
        if (insightsResponse.ok) {
          insightsData = await insightsResponse.json();
        }
      } catch (error) {
        console.log('Insights fetch failed (might not be available for this account type):', error);
      }

      const { error: updateError } = await supabase
        .from('instagram_accounts')
        .update({
          username: profileData.username,
          account_type: profileData.account_type,
          followers_count: profileData.followers_count || 0,
          follows_count: profileData.follows_count || 0,
          media_count: profileData.media_count || 0,
          profile_picture_url: profileData.profile_picture_url,
          last_sync_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .eq('id', targetAccountId);

      if (updateError) {
        throw updateError;
      }

      if (insightsData && insightsData.data) {
        for (const metric of insightsData.data) {
          if (metric.values && metric.values.length > 0) {
            const latestValue = metric.values[metric.values.length - 1];
            await supabase
              .from('instagram_insights')
              .insert({
                account_id: targetAccountId,
                metric_name: metric.name,
                metric_value: latestValue.value,
                period: metric.period,
                end_time: latestValue.end_time,
              });
          }
        }
      }

      const status: AccountStatus = {
        username: profileData.username,
        account_type: profileData.account_type,
        followers_count: profileData.followers_count || 0,
        follows_count: profileData.follows_count || 0,
        media_count: profileData.media_count || 0,
        profile_picture_url: profileData.profile_picture_url,
        is_active: true,
        last_sync_at: new Date().toISOString(),
      };

      return new Response(
        JSON.stringify({
          status,
          insights: insightsData?.data || [],
        }),
        {
          headers: {
            ...corsHeaders,
            'Content-Type': 'application/json',
          },
        }
      );
    }

    return new Response(
      JSON.stringify({ error: 'Invalid request' }),
      {
        status: 400,
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
