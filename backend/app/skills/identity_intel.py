import asyncio
import re
from typing import Dict, Any, List
import httpx

# List of major public social, professional & developer platforms for OSINT username footprinting
PLATFORMS = {
    "GitHub": {"url": "https://github.com/{}", "check": 200, "not_found": "404"},
    "Instagram": {"url": "https://www.instagram.com/{}/", "check": 200, "not_found": "Page Not Found"},
    "Facebook": {"url": "https://www.facebook.com/{}/", "check": 200, "not_found": "isn't available"},
    "LinkedIn": {"url": "https://www.linkedin.com/in/{}/", "check": 200, "not_found": "Page not found"},
    "Twitter/X": {"url": "https://x.com/{}", "check": 200, "not_found": "This account doesn't exist"},
    "Reddit": {"url": "https://www.reddit.com/user/{}", "check": 200, "not_found": "nobody on Reddit goes by that name"},
    "YouTube": {"url": "https://www.youtube.com/@{}", "check": 200, "not_found": "404 Not Found"},
    "TikTok": {"url": "https://www.tiktok.com/@{}", "check": 200, "not_found": "Couldn't find this account"},
    "Twitch": {"url": "https://www.twitch.tv/{}", "check": 200, "not_found": "content is unavailable"},
    "Telegram": {"url": "https://t.me/{}", "check": 200, "not_found": "tgme_page_extra"},
    "GitLab": {"url": "https://gitlab.com/{}", "check": 200, "not_found": "404"},
    "Medium": {"url": "https://medium.com/@{}", "check": 200, "not_found": "404"},
    "HackerNews": {"url": "https://news.ycombinator.com/user?id={}", "check": 200, "not_found": "No such user"},
    "Keybase": {"url": "https://keybase.io/{}", "check": 200, "not_found": "404"},
    "Dev.to": {"url": "https://dev.to/{}", "check": 200, "not_found": "404"},
    "Pinterest": {"url": "https://www.pinterest.com/{}/", "check": 200, "not_found": "404"},
    "DockerHub": {"url": "https://hub.docker.com/u/{}", "check": 200, "not_found": "404"},
    "Pastebin": {"url": "https://pastebin.com/u/{}", "check": 200, "not_found": "Not Found"},
    "Substack": {"url": "https://{}.substack.com", "check": 200, "not_found": "404"},
    "Gravatar": {"url": "https://en.gravatar.com/{}", "check": 200, "not_found": "404"}
}

class IdentityIntelEngine:
    """
    Open Source Intelligence engine for usernames, emails, and entity extraction.
    """

    async def check_username_footprint(self, username: str) -> Dict[str, Any]:
        """
        Asynchronously scans 14+ public platforms to discover active profiles matching a handle.
        """
        clean_user = username.strip().lstrip("@")
        results = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        }

        async def _probe(name: str, config: dict, client: httpx.AsyncClient):
            target_url = config["url"].format(clean_user)
            try:
                resp = await client.get(target_url, timeout=8.0)
                not_found_cue = config.get("not_found", "")
                
                # Check for false positives or explicit not found text
                if not_found_cue and not_found_cue.lower() in resp.text.lower():
                    return None
                
                # Check status code
                if resp.status_code == 200:
                    return {
                        "platform": name,
                        "url": target_url,
                        "status": "Found",
                        "status_code": resp.status_code
                    }
                # Some platforms like Instagram / Facebook redirect anonymous traffic with 301/302 when user exists
                elif resp.status_code in (301, 302, 307) and name in ("Instagram", "Facebook", "LinkedIn"):
                    return {
                        "platform": name,
                        "url": target_url,
                        "status": "Likely Active (Login Required)",
                        "status_code": resp.status_code
                    }
            except Exception:
                pass
            return None

        async with httpx.AsyncClient(headers=headers, follow_redirects=False) as client:
            tasks = [_probe(name, conf, client) for name, conf in PLATFORMS.items()]
            probe_results = await asyncio.gather(*tasks)

        for res in probe_results:
            if res:
                results.append(res)

        return {
            "username": clean_user,
            "total_matches": len(results),
            "profiles": results
        }

    def extract_entities_from_text(self, text: str) -> Dict[str, List[str]]:
        """
        Extracts structured intelligence artifacts from raw scraped text or HTML:
        - Emails
        - IPv4 Addresses
        - Bitcoin (BTC) & Ethereum (ETH) wallet addresses
        - Social handles
        """
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        ipv4_pattern = r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        btc_pattern = r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b'
        eth_pattern = r'\b0x[a-fA-F0-9]{40}\b'

        emails = list(set(re.findall(email_pattern, text)))
        ips = list(set([ip for ip in re.findall(ipv4_pattern, text) if not ip.startswith("127.") and not ip.startswith("0.")]))
        btc = list(set(re.findall(btc_pattern, text)))
        eth = list(set(re.findall(eth_pattern, text)))

        return {
            "emails": emails[:30],
            "ip_addresses": ips[:30],
            "crypto_wallets": {
                "bitcoin": btc[:15],
                "ethereum": eth[:15]
            }
        }

identity_intel_engine = IdentityIntelEngine()
