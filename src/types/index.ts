export interface InstagramAccount {
  id: string;
  user_id: string;
  instagram_user_id: string;
  username: string;
  account_type: string;
  profile_picture_url?: string;
  followers_count: number;
  follows_count: number;
  media_count: number;
  is_active: boolean;
  last_sync_at: string;
  created_at: string;
  updated_at: string;
}

export interface InstagramInsight {
  id: string;
  account_id: string;
  metric_name: string;
  metric_value: number;
  period: string;
  end_time: string;
  created_at: string;
}

export interface AccountStatus {
  status: {
    username: string;
    account_type: string;
    followers_count: number;
    follows_count: number;
    media_count: number;
    profile_picture_url?: string;
    is_active: boolean;
    last_sync_at: string;
  };
  insights: Array<{
    name: string;
    period: string;
    values: Array<{
      value: number;
      end_time: string;
    }>;
  }>;
}
