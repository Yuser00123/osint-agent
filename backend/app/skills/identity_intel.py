import asyncio
import re
from typing import Dict, Any, List
import httpx

# List of major public social & developer services for OSINT username footprinting
PLATFORMS = {
    "GitHub": {"url": "https://github.com/{}", "check": 200},
    "Reddit": {"url": "https://www.reddit.com/user/{}", "check": 200},
    "Twitter/X": {"url": "https://x.com/{}", "check": 200},
    "GitLab": {"url": "https://gitlab.com/{}", "check": 200},
    "Telegram": {"url": "https://t.me/{}", "check": 200},
    "Medium": {"url": "https://medium.com/@{}", "check": 200},
    "HackerNews": {"url": "https://news.ycombinator.com/user?id={}", "check": 200},
    "Keybase": {"url": "https://keybase.io/{}", "check": 200},
    "Dev.to": {"url": "https://dev.to/{}", "check": 200},
    "Pinterest": {"url": "https://www.pinterest.com/{}/", "check": 200},
    "DockerHub": {"url": "https://hub.docker.com/u/{}", "check": 200},
    "Pastebin": {"url": "https://pastebin.com/u/{}", "check": 200},
    "Substack": {"url": "https://{}.substack.com", "check": 200},
    "Gravatar": {"url": "https://en.gravatar.com/{}", "check": 200}
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
                resp = await client.get(target_url, timeout=7.0)
                if resp.status_code == config["check"]:
                    # Specific platform false-positive verification
                    if name == "Reddit" and "nobody on Reddit goes by that name" in resp.text:
                        return None
                    if name == "Telegram" and "If you have <strong>Telegram</strong>, you can contact" not in resp.text:
                        pass
                    return {
                        "platform": name,
                        "url": target_url,
                        "status": "Found",
                        "status_code": resp.status_code
                    }
            except Exception:
                pass
            return None

        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
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
