# Proxy Management Guide

This bot includes comprehensive proxy support with automatic validation, rotation, and database storage.

## Features

- **Multiple Format Support**: Accepts proxies in various formats
- **Automatic Validation**: Tests proxies before adding them
- **Smart Rotation**: Uses least-recently-used proxy for each request
- **Database Storage**: All proxies stored securely in Supabase
- **Health Tracking**: Monitors success/failure rates
- **Auto-Deactivation**: Disables proxies after 3 consecutive failures

## Supported Proxy Formats

```
# IP:Port
1.2.3.4:8080

# IP:Port:Username:Password
1.2.3.4:8080:myuser:mypass

# Username:Password@IP:Port
myuser:mypass@1.2.3.4:8080

# With Protocol
http://1.2.3.4:8080
https://1.2.3.4:8080
socks4://1.2.3.4:1080
socks5://1.2.3.4:1080

# With Protocol and Auth
http://user:pass@1.2.3.4:8080
socks5://user:pass@1.2.3.4:1080
```

## Commands

### /addproxy - Add Proxies

**Text Input (single or multiple):**
```
/addproxy 1.2.3.4:8080

/addproxy 1.2.3.4:8080 5.6.7.8:3128 9.10.11.12:8888
```

**File Upload:**
Upload a .txt file with one proxy per line:
```
1.2.3.4:8080
5.6.7.8:3128:user:pass
user:pass@9.10.11.12:8888
http://1.2.3.4:8080
```

The bot will:
1. Parse all proxies
2. Validate each one (checks if working)
3. Save only valid proxies
4. Report results

### /listproxy - View Your Proxies

Shows all your proxies with:
- Active/Inactive status
- Success/Failure counts
- Proxy type and authentication status
- Unique ID for deletion

### /deleteproxy - Remove Specific Proxy

```
/deleteproxy [proxy_id]
```

Get the ID from `/listproxy` output.

### /clearproxy - Remove All Proxies

Deletes all your proxies at once.

## How Proxy Rotation Works

1. When you run `/ig` command, the bot checks if you have any active proxies
2. If proxies exist, it uses the least-recently-used proxy
3. After the request, it updates the proxy's usage statistics
4. Next request will use a different proxy (rotation)
5. If a proxy fails 3 times, it's automatically deactivated

## Example Workflow

```bash
# Step 1: Add proxies
/addproxy 1.2.3.4:8080 5.6.7.8:3128

# Bot validates and saves working proxies
# Output: "Added 2 proxies"

# Step 2: Check your proxies
/listproxy

# Output shows:
# 1. ✅ 🔓 1.2.3.4:8080
#    Type: http | Success: 0 | Fails: 0
# 2. ✅ 🔓 5.6.7.8:3128
#    Type: http | Success: 0 | Fails: 0

# Step 3: Use /ig command - automatically uses proxy
/ig datr=xxx; sessionid=yyy

# Bot automatically rotates through proxies
# Shows which proxy was used in response
```

## Database Schema

Proxies are stored with these fields:
- `user_id`: Your Telegram ID
- `host`, `port`: Proxy connection details
- `username`, `password`: Auth credentials (if any)
- `proxy_type`: http, https, socks4, or socks5
- `is_active`: Whether proxy is working
- `success_count`: Number of successful uses
- `fail_count`: Number of failures
- `last_used`: When last used (for rotation)
- `last_validated`: When validated

## Tips

1. **Bulk Import**: Upload a .txt file with hundreds of proxies - bot validates all
2. **Free Proxies**: Free proxies often fail validation - expect low success rate
3. **Private Proxies**: Premium proxies with authentication work best
4. **Monitoring**: Check `/listproxy` regularly to see proxy health
5. **Re-validation**: If proxies become inactive, delete and re-add them

## Troubleshooting

**No proxies added after upload:**
- Check proxy format
- Proxies might not be working (validation failed)
- Try with known working proxies first

**All proxies inactive:**
- Proxies failed 3+ times
- Use `/clearproxy` and add fresh proxies
- Consider using paid/premium proxies

**Request still failing with proxies:**
- Target might be blocking proxy IPs
- Try different proxy type (socks5 vs http)
- Check proxy authentication credentials
