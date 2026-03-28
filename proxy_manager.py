import os
import logging
from typing import List, Dict, Optional
from datetime import datetime
from supabase import create_client, Client
from proxy_validator import ProxyValidator

logger = logging.getLogger(__name__)

class ProxyManager:
    """Manage proxies in Supabase database"""

    def __init__(self):
        supabase_url = os.getenv('VITE_SUPABASE_URL')
        supabase_key = os.getenv('VITE_SUPABASE_ANON_KEY')

        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found in environment")

        self.supabase: Client = create_client(supabase_url, supabase_key)

    def add_proxies(self, user_id: int, proxies: List[Dict]) -> Dict:
        """Add validated proxies to database"""
        added = 0
        failed = 0
        duplicates = 0

        for proxy in proxies:
            try:
                # Check if proxy already exists
                existing = self.supabase.table('proxies').select('id').eq('user_id', user_id).eq('host', proxy['host']).eq('port', proxy['port']).maybeSingle().execute()

                if existing.data:
                    duplicates += 1
                    continue

                # Insert proxy
                self.supabase.table('proxies').insert({
                    'user_id': user_id,
                    'proxy_string': proxy['proxy_string'],
                    'proxy_type': proxy['proxy_type'],
                    'host': proxy['host'],
                    'port': proxy['port'],
                    'username': proxy.get('username'),
                    'password': proxy.get('password'),
                    'is_active': True,
                    'last_validated': datetime.utcnow().isoformat()
                }).execute()

                added += 1
                logger.info(f"Added proxy {proxy['host']}:{proxy['port']} for user {user_id}")

            except Exception as e:
                logger.error(f"Failed to add proxy {proxy['host']}:{proxy['port']}: {e}")
                failed += 1

        return {
            'added': added,
            'failed': failed,
            'duplicates': duplicates
        }

    def get_active_proxies(self, user_id: int) -> List[Dict]:
        """Get all active proxies for a user"""
        try:
            result = self.supabase.table('proxies').select('*').eq('user_id', user_id).eq('is_active', True).order('last_used', desc=False).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Failed to get proxies for user {user_id}: {e}")
            return []

    def get_next_proxy(self, user_id: int) -> Optional[Dict]:
        """Get next proxy for rotation (least recently used)"""
        proxies = self.get_active_proxies(user_id)

        if not proxies:
            return None

        # Return the first proxy (least recently used or never used)
        return proxies[0]

    def update_proxy_usage(self, proxy_id: str, success: bool):
        """Update proxy usage statistics"""
        try:
            if success:
                self.supabase.table('proxies').update({
                    'last_used': datetime.utcnow().isoformat(),
                    'success_count': self.supabase.rpc('increment', {'row_id': proxy_id, 'column_name': 'success_count'})
                }).eq('id', proxy_id).execute()
            else:
                result = self.supabase.table('proxies').select('fail_count').eq('id', proxy_id).maybeSingle().execute()

                if result.data:
                    fail_count = result.data.get('fail_count', 0) + 1

                    # Deactivate if too many failures
                    updates = {
                        'fail_count': fail_count,
                        'last_used': datetime.utcnow().isoformat()
                    }

                    if fail_count >= 3:
                        updates['is_active'] = False
                        logger.warning(f"Deactivated proxy {proxy_id} due to {fail_count} failures")

                    self.supabase.table('proxies').update(updates).eq('id', proxy_id).execute()

        except Exception as e:
            logger.error(f"Failed to update proxy usage: {e}")

    def get_all_proxies(self, user_id: int) -> List[Dict]:
        """Get all proxies for a user (active and inactive)"""
        try:
            result = self.supabase.table('proxies').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()

            return result.data if result.data else []

        except Exception as e:
            logger.error(f"Failed to get all proxies: {e}")
            return []

    def delete_proxy(self, user_id: int, proxy_id: str) -> bool:
        """Delete a proxy"""
        try:
            self.supabase.table('proxies').delete().eq('id', proxy_id).eq('user_id', user_id).execute()
            logger.info(f"Deleted proxy {proxy_id} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete proxy: {e}")
            return False

    def delete_all_proxies(self, user_id: int) -> bool:
        """Delete all proxies for a user"""
        try:
            self.supabase.table('proxies').delete().eq('user_id', user_id).execute()
            logger.info(f"Deleted all proxies for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete all proxies: {e}")
            return False

    def reactivate_proxy(self, proxy_id: str) -> bool:
        """Reactivate an inactive proxy"""
        try:
            self.supabase.table('proxies').update({
                'is_active': True,
                'fail_count': 0
            }).eq('id', proxy_id).execute()

            return True

        except Exception as e:
            logger.error(f"Failed to reactivate proxy: {e}")
            return False
