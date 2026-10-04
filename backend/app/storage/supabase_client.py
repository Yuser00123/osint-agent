import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
import httpx
from app.config import settings, BASE_DIR

logger = logging.getLogger("osint.storage")

LOCAL_STORAGE_DIR = BASE_DIR / "local_storage"
LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class SupabaseStorageManager:
    """
    Cloud Storage & Database manager using Supabase Free Tier.
    Provides S3-compatible file storage for dossiers/screenshots and table sync,
    with an automatic fallback to local directory persistence.
    """

    def __init__(self):
        self.url = settings.SUPABASE_URL.rstrip("/")
        self.key = settings.SUPABASE_KEY
        self.bucket = settings.SUPABASE_BUCKET
        self.is_configured = bool(self.url and self.key)

    async def save_report(self, target: str, report_data: Dict[str, Any]) -> str:
        """
        Saves an OSINT investigation report to Supabase Storage or local disk.
        Returns the accessible path or URL.
        """
        filename = f"report_{target.replace('.', '_')}_{report_data.get('timestamp', 'latest')}.json"
        content = json.dumps(report_data, indent=2)

        if self.is_configured:
            try:
                storage_url = f"{self.url}/storage/v1/object/{self.bucket}/{filename}"
                headers = {
                    "Authorization": f"Bearer {self.key}",
                    "Content-Type": "application/json",
                    "x-upsert": "true"
                }
                async with httpx.AsyncClient(timeout=20.0) as client:
                    resp = await client.post(storage_url, headers=headers, content=content.encode("utf-8"))
                    if resp.status_code in (200, 201):
                        return f"{self.url}/storage/v1/object/public/{self.bucket}/{filename}"
            except Exception as e:
                logger.error(f"Failed to upload report to Supabase: {e}")

        # Local Fallback
        local_file = LOCAL_STORAGE_DIR / filename
        with open(local_file, "w", encoding="utf-8") as f:
            f.write(content)
        return str(local_file)

    async def list_reports(self) -> List[Dict[str, Any]]:
        """
        Lists stored intelligence reports.
        """
        reports = []
        # Check local storage directory
        for p in LOCAL_STORAGE_DIR.glob("report_*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    reports.append({
                        "name": p.name,
                        "target": data.get("target", "Unknown"),
                        "timestamp": data.get("timestamp", ""),
                        "findings_count": len(data.get("findings", [])),
                        "local_path": str(p)
                    })
            except Exception:
                continue
        return reports

supabase_storage = SupabaseStorageManager()
