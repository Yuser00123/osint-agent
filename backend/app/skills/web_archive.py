from typing import Dict, Any, List
import httpx

class WebArchiveEngine:
    """
    Wayback Machine (web.archive.org) historical discovery engine.
    Used for inspecting past snapshots of websites, identifying deleted pages,
    historical contact details, and architectural changes.
    """

    async def get_snapshot_history(self, target_url: str, limit: int = 15) -> Dict[str, Any]:
        """
        Retrieves snapshot history and available archived timestamps from the Wayback CDX API.
        """
        clean_url = target_url.strip().replace("https://", "").replace("http://", "").split("/")[0]
        cdx_url = f"https://web.archive.org/cdx/search/cdx?url={clean_url}&output=json&fl=timestamp,original,statuscode,mimetype&filter=statuscode:200&collapse=timestamp:6&limit={limit}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) OSINT-Agent/1.0"
        }

        try:
            async with httpx.AsyncClient(headers=headers, timeout=20.0) as client:
                resp = await client.get(cdx_url)
                if resp.status_code != 200:
                    return {
                        "target": clean_url,
                        "status": "error",
                        "error": f"Wayback CDX returned status {resp.status_code}",
                        "snapshots": []
                    }

                data = resp.json()
                if not data or len(data) <= 1:
                    return {
                        "target": clean_url,
                        "status": "success",
                        "count": 0,
                        "snapshots": []
                    }

                # First row is headers: ["timestamp", "original", "statuscode", "mimetype"]
                snapshots = []
                for row in data[1:]:
                    ts, orig, status, mime = row
                    # Format timestamp YYYYMMDDhhmmss -> readable
                    formatted_date = f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"
                    archive_link = f"https://web.archive.org/web/{ts}/{orig}"
                    snapshots.append({
                        "timestamp": ts,
                        "date": formatted_date,
                        "original_url": orig,
                        "status": status,
                        "mimetype": mime,
                        "archive_url": archive_link
                    })

                return {
                    "target": clean_url,
                    "status": "success",
                    "count": len(snapshots),
                    "snapshots": snapshots
                }

        except Exception as e:
            return {
                "target": clean_url,
                "status": "error",
                "error": str(e),
                "snapshots": []
            }

web_archive_engine = WebArchiveEngine()
