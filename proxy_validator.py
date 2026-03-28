import re
import requests
from typing import List, Dict, Optional
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class ProxyValidator:
    """Validate and parse proxy strings in various formats"""

    PROXY_PATTERNS = [
        # IP:Port
        r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$',
        # IP:Port:Username:Password
        r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5}):([^:]+):(.+)$',
        # Username:Password@IP:Port
        r'^([^:@]+):([^@]+)@(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$',
        # Protocol://IP:Port
        r'^(https?|socks[45])://(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$',
        # Protocol://Username:Password@IP:Port
        r'^(https?|socks[45])://([^:@]+):([^@]+)@(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})$',
        # Host:Port (domain)
        r'^([a-zA-Z0-9.-]+):(\d{1,5})$',
        # Protocol://Host:Port
        r'^(https?|socks[45])://([a-zA-Z0-9.-]+):(\d{1,5})$',
    ]

    @staticmethod
    def parse_proxy(proxy_string: str) -> Optional[Dict]:
        """Parse proxy string into components"""
        proxy_string = proxy_string.strip()

        for pattern in ProxyValidator.PROXY_PATTERNS:
            match = re.match(pattern, proxy_string, re.IGNORECASE)
            if match:
                groups = match.groups()

                # Pattern 1: IP:Port
                if len(groups) == 2 and groups[0].replace('.', '').isdigit():
                    return {
                        'host': groups[0],
                        'port': int(groups[1]),
                        'username': None,
                        'password': None,
                        'proxy_type': 'http',
                        'proxy_string': proxy_string
                    }

                # Pattern 2: IP:Port:Username:Password
                elif len(groups) == 4 and groups[0].replace('.', '').isdigit():
                    return {
                        'host': groups[0],
                        'port': int(groups[1]),
                        'username': groups[2],
                        'password': groups[3],
                        'proxy_type': 'http',
                        'proxy_string': proxy_string
                    }

                # Pattern 3: Username:Password@IP:Port
                elif len(groups) == 4 and groups[2].replace('.', '').isdigit():
                    return {
                        'host': groups[2],
                        'port': int(groups[3]),
                        'username': groups[0],
                        'password': groups[1],
                        'proxy_type': 'http',
                        'proxy_string': proxy_string
                    }

                # Pattern 4: Protocol://IP:Port
                elif len(groups) == 3:
                    return {
                        'host': groups[1],
                        'port': int(groups[2]),
                        'username': None,
                        'password': None,
                        'proxy_type': groups[0].lower(),
                        'proxy_string': proxy_string
                    }

                # Pattern 5: Protocol://Username:Password@IP:Port
                elif len(groups) == 5:
                    return {
                        'host': groups[3],
                        'port': int(groups[4]),
                        'username': groups[1],
                        'password': groups[2],
                        'proxy_type': groups[0].lower(),
                        'proxy_string': proxy_string
                    }

        return None

    @staticmethod
    def validate_proxy(proxy_info: Dict, timeout: int = 10) -> bool:
        """Test if proxy is working"""
        try:
            proxy_url = ProxyValidator.build_proxy_url(proxy_info)
            proxies = {
                'http': proxy_url,
                'https': proxy_url
            }

            # Test with a simple request
            response = requests.get(
                'http://httpbin.org/ip',
                proxies=proxies,
                timeout=timeout
            )

            if response.status_code == 200:
                logger.info(f"Proxy {proxy_info['host']}:{proxy_info['port']} is working")
                return True
            else:
                logger.warning(f"Proxy {proxy_info['host']}:{proxy_info['port']} returned status {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Proxy validation failed for {proxy_info['host']}:{proxy_info['port']}: {e}")
            return False

    @staticmethod
    def build_proxy_url(proxy_info: Dict) -> str:
        """Build proxy URL from components"""
        if proxy_info['username'] and proxy_info['password']:
            auth = f"{proxy_info['username']}:{proxy_info['password']}@"
        else:
            auth = ""

        protocol = proxy_info['proxy_type']
        if protocol not in ['http', 'https', 'socks4', 'socks5']:
            protocol = 'http'

        return f"{protocol}://{auth}{proxy_info['host']}:{proxy_info['port']}"

    @staticmethod
    def parse_proxy_list(text: str) -> List[Dict]:
        """Parse multiple proxies from text"""
        lines = text.strip().split('\n')
        proxies = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            proxy_info = ProxyValidator.parse_proxy(line)
            if proxy_info:
                proxies.append(proxy_info)
            else:
                logger.warning(f"Failed to parse proxy: {line}")

        return proxies

    @staticmethod
    def validate_proxies_batch(proxies: List[Dict], max_workers: int = 10) -> List[Dict]:
        """Validate multiple proxies concurrently"""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        valid_proxies = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {
                executor.submit(ProxyValidator.validate_proxy, proxy): proxy
                for proxy in proxies
            }

            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    is_valid = future.result()
                    if is_valid:
                        valid_proxies.append(proxy)
                except Exception as e:
                    logger.error(f"Error validating proxy: {e}")

        return valid_proxies
