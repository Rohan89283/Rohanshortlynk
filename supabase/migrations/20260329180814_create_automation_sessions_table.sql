/*
  # Create automation sessions tracking table

  1. New Tables
    - `automation_sessions`
      - `id` (uuid, primary key)
      - `user_id` (bigint) - Telegram user ID
      - `username` (text) - Telegram username
      - `status` (text) - Session status: running, completed, failed
      - `step_reached` (text) - Last step reached in automation
      - `error_message` (text) - Error message if failed
      - `screenshot_count` (int) - Number of screenshots captured
      - `started_at` (timestamptz) - When session started
      - `completed_at` (timestamptz) - When session completed
      - `duration_seconds` (int) - Duration of session in seconds

  2. Security
    - Enable RLS on `automation_sessions` table
    - Add policies for service role to manage sessions

  3. Notes
    - Tracks each automation run for analytics and debugging
    - Helps identify common failure points
*/

CREATE TABLE IF NOT EXISTS automation_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id bigint NOT NULL,
  username text,
  status text NOT NULL DEFAULT 'running',
  step_reached text,
  error_message text,
  screenshot_count int DEFAULT 0,
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  duration_seconds int
);

CREATE INDEX IF NOT EXISTS idx_automation_sessions_user_id ON automation_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_automation_sessions_status ON automation_sessions(status);
CREATE INDEX IF NOT EXISTS idx_automation_sessions_started_at ON automation_sessions(started_at DESC);

ALTER TABLE automation_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role can manage automation sessions"
  ON automation_sessions
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);
