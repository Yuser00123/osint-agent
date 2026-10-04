import re
import socket
from typing import Dict, Any, List, Set
import httpx

class ReconInfraEngine:
    """
    Passive Infrastructure Reconnaissance Engine.
    Performs DNS resolution via DoH (DNS-over-HTTPS), passive subdomain enumeration via
    Certificate Transparency logs (crt.sh), and HTTP security headers inspection.
    """

    async def get_subdomains_crtsh(self, domain: str, max_subdomains: int = 50) -> Dict[str, Any]:
        """
        Queries Certificate Transparency logs (crt.sh) passively.
        Discovers active & historical subdomains with zero active probing against the target.
        """
        clean_domain = domain.strip().replace("https://", "").replace("http://", "").split("/")[0]
        url = f"https://crt.sh/?q=%25.{clean_domain}&output=json"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Agent/1.0"
        }
        
        try:
            async with httpx.AsyncClient(headers=headers, timeout=25.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return {
                        "domain": clean_domain,
                        "status": "error",
                        "error": f"crt.sh returned status {resp.status_code}",
                        "subdomains": []
                    }

                data = resp.json()
                found: Set[str] = set()

                for entry in data:
                    name_value = entry.get("name_value", "")
                    for sub in name_value.split("\n"):
                        sub = sub.strip().lower()
                        if "*" not in sub and sub.endswith(clean_domain) and len(sub) > len(clean_domain):
                            found.add(sub)
                        if len(found) >= max_subdomains:
                            break
                    if len(found) >= max_subdomains:
                        break

                sorted_subs = sorted(list(found))
                return {
                    "domain": clean_domain,
                    "status": "success",
                    "total_found": len(sorted_subs),
                    "subdomains": sorted_subs
                }
        except Exception as e:
            return {
                "domain": clean_domain,
                "status": "error",
                "error": str(e),
                "subdomains": []
            }

    async def resolve_dns_doh(self, domain: str) -> Dict[str, Any]:
        """
        Resolves DNS records using Cloudflare's DNS-over-HTTPS (DoH).
        Doesn't leak local DNS requests and works in any container environment.
        """
        clean_domain = domain.strip().replace("https://", "").replace("http://", "").split("/")[0]
        record_types = ["A", "AAAA", "MX", "TXT", "NS", "SOA"]
        results: Dict[str, List[str]] = {}

        headers = {"Accept": "application/dns-json"}
        base_url = "https://cloudflare-dns.com/dns-query"

        async with httpx.AsyncClient(headers=headers, timeout=10.0) as client:
            for rtype in record_types:
                try:
                    resp = await client.get(f"{base_url}?name={clean_domain}&type={rtype}")
                    if resp.status_code == 200:
                        data = resp.json()
                        answers = data.get("Answer", [])
                        results[rtype] = [ans.get("data", "") for ans in answers if "data" in ans]
                except Exception:
                    results[rtype] = []

        return {
            "domain": clean_domain,
            "status": "success",
            "dns_records": results
        }

    async def inspect_http_headers(self, url: str) -> Dict[str, Any]:
        """
        Inspects server technology, cookies, and security posture headers.
        """
        if not url.startswith("http://") and not url.startswith("https://"):
            url = f"https://{url}"

        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=12.0) as client:
                resp = await client.get(url)
                
                # Security header audit
                sec_headers = {
                    "strict-transport-security": resp.headers.get("strict-transport-security", "Missing"),
                    "content-security-policy": "Present" if "content-security-policy" in resp.headers else "Missing",
                    "x-frame-options": resp.headers.get("x-frame-options", "Missing"),
                    "x-content-type-options": resp.headers.get("x-content-type-options", "Missing"),
                    "referrer-policy": resp.headers.get("referrer-policy", "Missing"),
                    "server": resp.headers.get("server", "Hidden/Unknown"),
                    "x-powered-by": resp.headers.get("x-powered-by", "None")
                }

                return {
                    "target_url": str(resp.url),
                    "status_code": resp.status_code,
                    "server": resp.headers.get("server", "Unknown"),
                    "security_headers": sec_headers,
                    "all_headers": dict(resp.headers)
                }
        except Exception as e:
            return {
                "target_url": url,
                "status": "error",
                "error": str(e)
            }

recon_infra_engine = ReconInfraEngine()
