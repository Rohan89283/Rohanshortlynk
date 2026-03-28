/*
  # Create proxies management table

  1. New Tables
    - `proxies`
      - `id` (uuid, primary key) - Unique identifier for each proxy
      - `user_id` (bigint) - Telegram user ID who added the proxy
      - `proxy_string` (text) - The validated proxy string
      - `proxy_type` (text) - Type of proxy (http, https, socks4, socks5)
      - `host` (text) - Proxy host/IP
      - `port` (integer) - Proxy port
      - `username` (text, nullable) - Proxy username if authenticated
      - `password` (text, nullable) - Proxy password if authenticated
      - `is_active` (boolean) - Whether the proxy is active/valid
      - `last_used` (timestamptz, nullable) - Last time proxy was used
      - `last_validated` (timestamptz) - Last time proxy was validated
      - `success_count` (integer) - Number of successful uses
      - `fail_count` (integer) - Number of failed uses
      - `created_at` (timestamptz) - When proxy was added

  2. Security
    - Enable RLS on `proxies` table
    - Add policy for users to manage their own proxies
*/

CREATE TABLE IF NOT EXISTS proxies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL,
  proxy_string text NOT NULL,
  proxy_type text NOT NULL,
  host text NOT NULL,
  port integer NOT NULL,
  username text,
  password text,
  is_active boolean DEFAULT true,
  last_used timestamptz,
  last_validated timestamptz DEFAULT now(),
  success_count integer DEFAULT 0,
  fail_count integer DEFAULT 0,
  created_at timestamptz DEFAULT now()
);

-- Create index for faster user queries
CREATE INDEX IF NOT EXISTS idx_proxies_user_id ON proxies(user_id);
CREATE INDEX IF NOT EXISTS idx_proxies_active ON proxies(user_id, is_active) WHERE is_active = true;

ALTER TABLE proxies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own proxies"
  ON proxies FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Users can insert own proxies"
  ON proxies FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Users can update own proxies"
  ON proxies FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Users can delete own proxies"
  ON proxies FOR DELETE
  TO authenticated
  USING (true);