import json
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from app.skills.google_dorks import google_dorks_engine
from app.skills.recon_infra import recon_infra_engine
from app.skills.identity_intel import identity_intel_engine
from app.skills.web_archive import web_archive_engine
from app.skills.sandbox_browser import sandbox_browser_engine

logger = logging.getLogger("osint.mcp")

mcp_router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP)"])

# Standard MCP Tool Definitions
MCP_TOOLS_MANIFEST = [
    {
        "name": "google_dorks",
        "description": "Generates categorized Google dorks for sensitive files, directories, admin portals, and exposed buckets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "Target domain or brand name (e.g. example.com)"},
                "category": {"type": "string", "description": "Optional category filter: sensitive_files, exposed_directories, admin_portals, cloud_buckets_storage, subdomain_recon, confidential_documents, debug_errors"}
            },
            "required": ["target"]
        }
    },
    {
        "name": "search_dork",
        "description": "Executes a Google dork query and returns live stealth search results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The exact Google dork query string to execute"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "recon_subdomains",
        "description": "Passive subdomain enumeration using public Certificate Transparency logs (crt.sh). Zero probe footprint on target.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Root domain (e.g. target.com)"}
            },
            "required": ["domain"]
        }
    },
    {
        "name": "recon_dns",
        "description": "Resolves DNS records (A, AAAA, MX, TXT, NS, SOA) via DNS-over-HTTPS without leaking local queries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "description": "Domain name to resolve"}
            },
            "required": ["domain"]
        }
    },
    {
        "name": "browse_url",
        "description": "Navigates to a webpage, extracts cleaned body text, outbound links, and screenshot preview.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to browse"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "check_username",
        "description": "Scans 14+ public platforms (GitHub, Reddit, Twitter, Telegram, etc.) for a handle.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Username or handle to investigate"}
            },
            "required": ["username"]
        }
    },
    {
        "name": "wayback_history",
        "description": "Pulls historical snapshots and CDX timeline from the Wayback Machine for a domain/URL.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "target_url": {"type": "string", "description": "Domain or URL to check history for"}
            },
            "required": ["target_url"]
        }
    }
]

@mcp_router.get("/tools")
async def list_tools():
    """Returns the list of available OSINT tools adhering to the MCP schema."""
    return {"tools": MCP_TOOLS_MANIFEST}

@mcp_router.post("/call")
async def call_tool(payload: Dict[str, Any]):
    """
    Direct MCP Tool Call endpoint (JSON-RPC 2.0 compatible).
    Format: {"name": "recon_subdomains", "arguments": {"domain": "example.com"}}
    """
    name = payload.get("name")
    args = payload.get("arguments", {})

    try:
        if name == "google_dorks":
            res = google_dorks_engine.generate_dorks(args.get("target", ""), args.get("category"))
            return {"content": [{"type": "text", "text": json.dumps(res)}]}
        elif name == "search_dork":
            res = await google_dorks_engine.execute_dork_search(args.get("query", ""))
            return {"content": [{"type": "text", "text": json.dumps(res)}]}
        elif name == "recon_subdomains":
            res = await recon_infra_engine.get_subdomains_crtsh(args.get("domain", ""))
            return {"content": [{"type": "text", "text": json.dumps(res)}]}
        elif name == "recon_dns":
            res = await recon_infra_engine.resolve_dns_doh(args.get("domain", ""))
            return {"content": [{"type": "text", "text": json.dumps(res)}]}
        elif name == "browse_url":
            res = await sandbox_browser_engine.browse_url(args.get("url", ""))
            return {"content": [{"type": "text", "text": json.dumps(res)}]}
        elif name == "check_username":
            res = await identity_intel_engine.check_username_footprint(args.get("username", ""))
            return {"content": [{"type": "text", "text": json.dumps(res)}]}
        elif name == "wayback_history":
            res = await web_archive_engine.get_snapshot_history(args.get("target_url", ""))
            return {"content": [{"type": "text", "text": json.dumps(res)}]}
        else:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool '{name}' not found"}]}
    except Exception as e:
        return {"isError": True, "content": [{"type": "text", "text": str(e)}]}

@mcp_router.get("/sse")
async def mcp_sse(request: Request):
    """
    MCP Server-Sent Events (SSE) endpoint for connecting Claude Desktop or Cursor over HTTP/SSE.
    """
    async def event_generator():
        # First event informs client of the endpoint for message submission
        yield {
            "event": "endpoint",
            "data": "/mcp/messages"
        }
    return EventSourceResponse(event_generator())
