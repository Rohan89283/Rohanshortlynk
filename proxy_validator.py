import re
import socket
import requests
from typing import List, Dict, Optional
import logging
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)

class ProxyValidator:
    """Validate and parse proxy strings in various formats"""

    PROXY_PATTERNS = [
        # Host:Port:Username:Password (supports domains, IPs, special chars in password)
        # This pattern splits on first 3 colons, everything after is password
        r'^([a-zA-Z0-9._-]+):(\d{1,5}):([^:]+):(.+)$',
        # Username:Password@Host:Port (password can contain special chars before @)
        r'^([^:@]+):(.+)@([a-zA-Z0-9._-]+):(\d{1,5})$',
        # Protocol://Username:Password@Host:Port
        r'^(https?|socks[45])://([^:@]+):(.+)@([a-zA-Z0-9._-]+):(\d{1,5})$',
        # Protocol://Host:Port (no auth)
        r'^(https?|socks[45])://([a-zA-Z0-9._-]+):(\d{1,5})$',
        # Host:Port (domain or IP, no auth)
        r'^([a-zA-Z0-9._-]+):(\d{1,5})$',
    ]

    @staticmethod
    def parse_proxy(proxy_string: str) -> Optional[Dict]:
        """Parse proxy string into components"""
        proxy_string = proxy_string.strip()

        for pattern in ProxyValidator.PROXY_PATTERNS:
            match = re.match(pattern, proxy_string, re.IGNORECASE)
            if match:
                groups = match.groups()

                # Pattern 1: Host:Port:Username:Password (4 groups)
                if len(groups) == 4 and groups[1].isdigit():
                    return {
                        'host': groups[0],
                        'port': int(groups[1]),
                        'username': groups[2],
                        'password': groups[3],
                        'proxy_type': 'http',
                        'proxy_string': proxy_string
                    }

                # Pattern 2: Username:Password@Host:Port (4 groups)
                elif len(groups) == 4 and groups[3].isdigit():
                    return {
                        'host': groups[2],
                        'port': int(groups[3]),
                        'username': groups[0],
                        'password': groups[1],
                        'proxy_type': 'http',
                        'proxy_string': proxy_string
                    }

                # Pattern 3: Protocol://Username:Password@Host:Port (5 groups)
                elif len(groups) == 5:
                    return {
                        'host': groups[3],
                        'port': int(groups[4]),
                        'username': groups[1],
                        'password': groups[2],
                        'proxy_type': groups[0].lower(),
                        'proxy_string': proxy_string
                    }

                # Pattern 4: Host:Port (2 groups)
                elif len(groups) == 2 and groups[1].isdigit():
                    return {
                        'host': groups[0],
                        'port': int(groups[1]),
                        'username': None,
                        'password': None,
                        'proxy_type': 'http',
                        'proxy_string': proxy_string
                    }

                # Pattern 5: Protocol://Host:Port (3 groups)
                elif len(groups) == 3 and groups[2].isdigit():
                    return {
                        'host': groups[1],
                        'port': int(groups[2]),
                        'username': None,
                        'password': None,
                        'proxy_type': groups[0].lower(),
                        'proxy_string': proxy_string
                    }

        return None

    @staticmethod
    def validate_proxy_fast(proxy_info: Dict, timeout: float = 3.0) -> bool:
        """Fast TCP connection test to check if proxy is reachable"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            result = sock.connect_ex((proxy_info['host'], proxy_info['port']))
            sock.close()

            if result == 0:
                logger.info(f"Proxy {proxy_info['host']}:{proxy_info['port']} is reachable")
                return True
            else:
                logger.warning(f"Proxy {proxy_info['host']}:{proxy_info['port']} connection failed")
                return False

        except socket.gaierror:
            logger.error(f"Proxy {proxy_info['host']}:{proxy_info['port']} - DNS resolution failed")
            return False
        except Exception as e:
            logger.error(f"Proxy validation failed for {proxy_info['host']}:{proxy_info['port']}: {e}")
            return False

    @staticmethod
    def validate_proxy(proxy_info: Dict, timeout: int = 10) -> bool:
        """Test if proxy is working with HTTP request (slower but more accurate)"""
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
    def validate_proxies_batch(proxies: List[Dict], max_workers: int = 50, fast_mode: bool = True) -> List[Dict]:
        """
        Validate multiple proxies concurrently

        Args:
            proxies: List of proxy dictionaries
            max_workers: Number of concurrent validation threads
            fast_mode: If True, use fast TCP check; if False, use HTTP request
        """
        valid_proxies = []
        validation_func = ProxyValidator.validate_proxy_fast if fast_mode else ProxyValidator.validate_proxy

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_proxy = {
                executor.submit(validation_func, proxy): proxy
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
