import os
import json
from pathlib import Path
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.config import settings, BASE_DIR
from app.agent.llm_router import llm_router
from app.agent.orchestrator import osint_orchestrator
from app.skills.google_dorks import google_dorks_engine
from app.skills.recon_infra import recon_infra_engine
from app.skills.identity_intel import identity_intel_engine
from app.skills.web_archive import web_archive_engine
from app.skills.sandbox_browser import sandbox_browser_engine
from app.storage.supabase_client import supabase_storage
from app.mcp.server import mcp_router

app = FastAPI(
    title="Super OSINT AI Agent API",
    description="Autonomous Open-Source Intelligence research agent with multi-LLM routing, Google dorks, stealth browser, and MCP support.",
    version="1.0.0"
)

# Enable CORS for web UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount MCP endpoints
app.include_router(mcp_router)

# Request schemas
class InvestigationRequest(BaseModel):
    target: str
    investigation_type: str = "domain" # domain, username, email, keyword
    provider: Optional[str] = None
    max_steps: int = 5

class DorkGenerateRequest(BaseModel):
    target: str
    category: Optional[str] = None

class DorkSearchRequest(BaseModel):
    query: str

class BrowseRequest(BaseModel):
    url: str

# --- HEALTH & STATUS ---
@app.get("/api/status")
async def get_system_status():
    """Returns the operational status and list of configured AI LLM providers."""
    available_providers = llm_router.get_available_providers()
    return {
        "status": "online",
        "system": "Super OSINT AI Agent",
        "available_llm_providers": available_providers,
        "default_provider": settings.DEFAULT_LLM_PROVIDER,
        "storage": "Supabase" if supabase_storage.is_configured else "Local Storage Fallback",
        "sandbox_ready": bool(settings.E2B_API_KEY)
    }

# --- AGENT STREAMING ENDPOINT ---
@app.post("/api/investigate/stream")
async def start_investigation(req: InvestigationRequest):
    """
    Server-Sent Events (SSE) streaming endpoint for live agent thoughts, tool calls, and reports.
    """
    async def event_generator():
        async for chunk in osint_orchestrator.run_investigation_stream(
            target=req.target,
            investigation_type=req.investigation_type,
            max_steps=req.max_steps,
            provider=req.provider
        ):
            yield {"data": chunk}

    return EventSourceResponse(event_generator())

# --- DIRECT SKILL APIS ---
@app.post("/api/dorks/generate")
async def generate_dorks(req: DorkGenerateRequest):
    return {"target": req.target, "dorks": google_dorks_engine.generate_dorks(req.target, req.category)}

@app.post("/api/dorks/search")
async def search_dork(req: DorkSearchRequest):
    return await google_dorks_engine.execute_dork_search(req.query)

@app.get("/api/recon/subdomains")
async def get_subdomains(domain: str = Query(..., description="Root domain to scan")):
    return await recon_infra_engine.get_subdomains_crtsh(domain)

@app.get("/api/recon/dns")
async def get_dns(domain: str = Query(..., description="Domain to resolve")):
    return await recon_infra_engine.resolve_dns_doh(domain)

@app.get("/api/recon/headers")
async def get_headers(url: str = Query(..., description="URL to inspect")):
    return await recon_infra_engine.inspect_http_headers(url)

@app.get("/api/recon/username")
async def get_username_footprint(username: str = Query(..., description="Username to scan")):
    return await identity_intel_engine.check_username_footprint(username)

@app.get("/api/recon/archive")
async def get_archive(target_url: str = Query(..., description="Target domain or URL")):
    return await web_archive_engine.get_snapshot_history(target_url)

@app.post("/api/browser/browse")
async def browse(req: BrowseRequest):
    return await sandbox_browser_engine.browse_url(req.url)

@app.get("/api/reports")
async def list_reports():
    return {"reports": await supabase_storage.list_reports()}

# --- FRONTEND STATIC MOUNT ---
frontend_path = BASE_DIR / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

@app.get("/")
async def serve_index():
    index_file = frontend_path / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {"message": "Super OSINT AI Agent API is running. Frontend static directory not found."}
