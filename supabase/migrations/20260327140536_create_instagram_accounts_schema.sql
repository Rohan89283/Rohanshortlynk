-- Instagram Business Accounts Schema
--
-- Overview:
-- Creates the database structure for managing Instagram business account integrations
-- via the Instagram Graph API, including OAuth tokens and account metadata.
--
-- New Tables:
-- 1. instagram_accounts - Stores Instagram business account information
-- 2. instagram_insights - Stores historical insights/metrics
--
-- Security:
-- - RLS enabled on all tables
-- - Users can only access their own data

-- Create instagram_accounts table
CREATE TABLE IF NOT EXISTS instagram_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
  instagram_user_id text UNIQUE NOT NULL,
  username text NOT NULL,
  account_type text DEFAULT 'BUSINESS',
  profile_picture_url text,
  followers_count integer DEFAULT 0,
  follows_count integer DEFAULT 0,
  media_count integer DEFAULT 0,
  access_token text NOT NULL,
  token_expires_at timestamptz,
  is_active boolean DEFAULT true,
  last_sync_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Create instagram_insights table
CREATE TABLE IF NOT EXISTS instagram_insights (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id uuid REFERENCES instagram_accounts(id) ON DELETE CASCADE NOT NULL,
  metric_name text NOT NULL,
  metric_value integer DEFAULT 0,
  period text DEFAULT 'day',
  end_time timestamptz NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_instagram_accounts_user_id ON instagram_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_instagram_accounts_instagram_user_id ON instagram_accounts(instagram_user_id);
CREATE INDEX IF NOT EXISTS idx_instagram_insights_account_id ON instagram_insights(account_id);
CREATE INDEX IF NOT EXISTS idx_instagram_insights_metric_name ON instagram_insights(metric_name);

-- Enable RLS
ALTER TABLE instagram_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE instagram_insights ENABLE ROW LEVEL SECURITY;

-- RLS Policies for instagram_accounts
CREATE POLICY "Users can view own Instagram accounts"
  ON instagram_accounts FOR SELECT
  TO authenticated
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own Instagram accounts"
  ON instagram_accounts FOR INSERT
  TO authenticated
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own Instagram accounts"
  ON instagram_accounts FOR UPDATE
  TO authenticated
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete own Instagram accounts"
  ON instagram_accounts FOR DELETE
  TO authenticated
  USING (auth.uid() = user_id);

-- RLS Policies for instagram_insights
CREATE POLICY "Users can view own Instagram insights"
  ON instagram_insights FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM instagram_accounts
      WHERE instagram_accounts.id = instagram_insights.account_id
      AND instagram_accounts.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can insert own Instagram insights"
  ON instagram_insights FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM instagram_accounts
      WHERE instagram_accounts.id = instagram_insights.account_id
      AND instagram_accounts.user_id = auth.uid()
    )
  );

CREATE POLICY "Users can delete own Instagram insights"
  ON instagram_insights FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM instagram_accounts
      WHERE instagram_accounts.id = instagram_insights.account_id
      AND instagram_accounts.user_id = auth.uid()
    )
  );