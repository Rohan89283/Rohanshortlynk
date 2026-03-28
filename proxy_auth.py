import os
import zipfile
from typing import Dict

def create_proxy_auth_extension(proxy_info: Dict) -> str:
    """
    Create a Chrome extension for proxy authentication

    Args:
        proxy_info: Dict with 'host', 'port', 'username', 'password'

    Returns:
        Path to the extension zip file
    """
    manifest_json = """
{
    "version": "1.0.0",
    "manifest_version": 2,
    "name": "Chrome Proxy",
    "permissions": [
        "proxy",
        "tabs",
        "unlimitedStorage",
        "storage",
        "<all_urls>",
        "webRequest",
        "webRequestBlocking"
    ],
    "background": {
        "scripts": ["background.js"]
    },
    "minimum_chrome_version":"22.0.0"
}
"""

    background_js = """
var config = {
        mode: "fixed_servers",
        rules: {
          singleProxy: {
            scheme: "http",
            host: "%s",
            port: parseInt(%s)
          },
          bypassList: ["localhost"]
        }
      };

chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

function callbackFn(details) {
    return {
        authCredentials: {
            username: "%s",
            password: "%s"
        }
    };
}

chrome.webRequest.onAuthRequired.addListener(
            callbackFn,
            {urls: ["<all_urls>"]},
            ['blocking']
);
""" % (proxy_info['host'], proxy_info['port'],
       proxy_info.get('username', ''),
       proxy_info.get('password', ''))

    # Create extension directory
    plugin_dir = '/tmp/proxy_auth_extension'
    os.makedirs(plugin_dir, exist_ok=True)

    # Write manifest
    with open(os.path.join(plugin_dir, 'manifest.json'), 'w') as f:
        f.write(manifest_json)

    # Write background script
    with open(os.path.join(plugin_dir, 'background.js'), 'w') as f:
        f.write(background_js)

    # Create zip file
    plugin_path = '/tmp/proxy_auth_plugin.zip'
    with zipfile.ZipFile(plugin_path, 'w') as zp:
        zp.write(os.path.join(plugin_dir, 'manifest.json'), 'manifest.json')
        zp.write(os.path.join(plugin_dir, 'background.js'), 'background.js')

    return plugin_path
