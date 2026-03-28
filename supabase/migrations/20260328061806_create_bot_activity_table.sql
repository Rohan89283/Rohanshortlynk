/*
  # Create bot activity logging table

  1. New Tables
    - `bot_activity`
      - `id` (uuid, primary key)
      - `user_id` (bigint) - Telegram user ID
      - `username` (text) - Telegram username
      - `command` (text) - Command executed
      - `message_text` (text) - Full message text
      - `created_at` (timestamptz) - Timestamp of activity

  2. Security
    - Enable RLS on `bot_activity` table
    - Add policy for service role to insert activity logs
    - Add policy for authenticated users to read all logs

  3. Notes
    - This table logs all bot interactions for backup and analytics
    - User ID is stored as bigint to match Telegram's user ID format
*/

CREATE TABLE IF NOT EXISTS bot_activity (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL,
  username text,
  command text,
  message_text text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bot_activity_user_id ON bot_activity(user_id);
CREATE INDEX IF NOT EXISTS idx_bot_activity_created_at ON bot_activity(created_at DESC);

ALTER TABLE bot_activity ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can insert activity logs"
  ON bot_activity
  FOR INSERT
  TO service_role
  WITH CHECK (true);

CREATE POLICY "Service role can read all logs"
  ON bot_activity
  FOR SELECT
  TO service_role
  USING (true);
