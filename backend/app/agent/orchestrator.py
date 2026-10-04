import re
import json
import time
import asyncio
from typing import Dict, Any, List, AsyncGenerator
from app.agent.llm_router import llm_router
from app.skills.google_dorks import google_dorks_engine
from app.skills.recon_infra import recon_infra_engine
from app.skills.identity_intel import identity_intel_engine
from app.skills.web_archive import web_archive_engine
from app.skills.sandbox_browser import sandbox_browser_engine
from app.storage.supabase_client import supabase_storage

SYSTEM_ORCHESTRATOR_PROMPT = """
You are the **Super OSINT AI Agent**, an elite autonomous intelligence analyst and reconnaissance engine.
Your purpose is to conduct ethical, passive, and in-depth Open-Source Intelligence investigations.

You have access to the following tools:
1. `google_dorks(target: str, category: Optional[str])`: Generates tailored Google dorks and searches for exposed files, directories, admin portals, or cloud leaks.
2. `search_dork(query: str)`: Executes a specific Google Dork query and returns live results.
3. `recon_subdomains(domain: str)`: Discovers subdomains passively via Certificate Transparency logs (crt.sh).
4. `recon_dns(domain: str)`: Resolves A, AAAA, MX, TXT, NS records via DNS-over-HTTPS.
5. `inspect_headers(url: str)`: Audits server technology and HTTP security headers.
6. `browse_url(url: str)`: Fetches webpage content, meta descriptions, outbound links, and screenshot preview.
7. `check_username(username: str)`: Checks for profile presence across 14+ major public platforms.
8. `wayback_history(target_url: str)`: Pulls historical snapshots and CDX timeline from the Wayback Machine.

When given an objective, formulate a multi-step investigation plan.
Work step by step using the ReAct framework:
Thought: Describe your analytical reasoning and next investigation step.
Action: {"tool": "tool_name", "args": {...}}
Observation: (The environment will provide this)
... (Repeat until sufficient intelligence is collected)
Final Answer: Provide an extensive, well-structured Open Source Intelligence Dossier summarizing findings, infrastructure, exposed assets, risk analysis, and actionable defensive recommendations.
"""

class OSINTOrchestrator:
    """
    Autonomous ReAct OSINT agent orchestrator with real-time SSE event streaming.
    """

    async def execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Any:
        try:
            if tool_name == "google_dorks":
                target = args.get("target", "")
                cat = args.get("category")
                dorks = google_dorks_engine.generate_dorks(target, cat)
                # Auto-run the top dork for immediate reconnaissance
                top_query = dorks[0]["query"] if dorks else ""
                sample_results = await google_dorks_engine.execute_dork_search(top_query) if top_query else {}
                return {"generated_dorks": dorks[:6], "sample_execution": sample_results}

            elif tool_name == "search_dork":
                query = args.get("query", "")
                return await google_dorks_engine.execute_dork_search(query)

            elif tool_name == "recon_subdomains":
                domain = args.get("domain", "")
                return await recon_infra_engine.get_subdomains_crtsh(domain)

            elif tool_name == "recon_dns":
                domain = args.get("domain", "")
                return await recon_infra_engine.resolve_dns_doh(domain)

            elif tool_name == "inspect_headers":
                url = args.get("url", "")
                return await recon_infra_engine.inspect_http_headers(url)

            elif tool_name == "browse_url":
                url = args.get("url", "")
                return await sandbox_browser_engine.browse_url(url)

            elif tool_name == "check_username":
                username = args.get("username", "")
                return await identity_intel_engine.check_username_footprint(username)

            elif tool_name == "wayback_history":
                target_url = args.get("target_url", "")
                return await web_archive_engine.get_snapshot_history(target_url)

            else:
                return {"error": f"Unknown tool '{tool_name}'"}
        except Exception as e:
            return {"error": str(e)}

    async def run_investigation_stream(
        self,
        target: str,
        investigation_type: str = "domain",
        max_steps: int = 5,
        provider: str = None
    ) -> AsyncGenerator[str, None]:
        """
        Runs an autonomous investigation loop and yields Server-Sent Events (SSE) JSON strings.
        """
        start_time = time.strftime("%Y%m%d_%H%M%S")
        yield json.dumps({
            "type": "status",
            "message": f"Initializing Super OSINT Agent for target: {target} (Type: {investigation_type})"
        })

        # Initial prompt tailoring
        user_prompt = f"Target: {target}\nType: {investigation_type}\nConduct an in-depth OSINT investigation. Start by mapping passive assets, dorking for exposed assets, and inspecting infrastructure."
        
        conversation_history = [{"role": "user", "content": user_prompt}]
        collected_data = {
            "target": target,
            "investigation_type": investigation_type,
            "timestamp": start_time,
            "steps": [],
            "graph_nodes": [{"id": target, "label": target, "type": "target"}],
            "graph_edges": []
        }

        step_count = 0
        while step_count < max_steps:
            step_count += 1
            yield json.dumps({"type": "step", "step": step_count, "max_steps": max_steps})

            # Call Multi-LLM provider
            try:
                llm_response = await llm_router.generate(
                    messages=conversation_history,
                    system_prompt=SYSTEM_ORCHESTRATOR_PROMPT,
                    provider=provider
                )
            except Exception as e:
                yield json.dumps({"type": "error", "message": f"LLM Generation Error: {str(e)}"})
                break

            response_text = llm_response.get("text", "")
            provider_used = llm_response.get("provider_used", "unknown")
            model_used = llm_response.get("model_used", "unknown")

            yield json.dumps({
                "type": "llm_meta",
                "provider": provider_used,
                "model": model_used
            })

            # Parse Thought and Action from response
            thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", response_text, re.DOTALL | re.IGNORECASE)
            thought = thought_match.group(1).strip() if thought_match else response_text

            if thought:
                yield json.dumps({"type": "thought", "content": thought})

            # Check for Final Answer
            if "Final Answer:" in response_text:
                final_answer = response_text.split("Final Answer:", 1)[1].strip()
                collected_data["final_report"] = final_answer
                saved_url = await supabase_storage.save_report(target, collected_data)
                
                yield json.dumps({
                    "type": "final_report",
                    "content": final_answer,
                    "report_location": saved_url
                })
                break

            # Check for Action
            action_match = re.search(r"Action:\s*(\{.*?\})", response_text, re.DOTALL)
            if action_match:
                try:
                    action_json = json.loads(action_match.group(1))
                    tool_name = action_json.get("tool")
                    args = action_json.get("args", {})

                    yield json.dumps({"type": "action", "tool": tool_name, "args": args})

                    # Execute tool
                    observation = await self.execute_tool(tool_name, args)
                    yield json.dumps({"type": "observation", "tool": tool_name, "data": observation})

                    # Extract graph relationships for visualization
                    self._update_graph_from_observation(target, tool_name, observation, collected_data, yield_hook=None)

                    # Update conversation history
                    conversation_history.append({"role": "assistant", "content": response_text})
                    conversation_history.append({
                        "role": "user",
                        "content": f"Observation: {json.dumps(observation)[:3000]}\nProvide your next Thought and Action, or 'Final Answer:' if sufficient."
                    })
                    collected_data["steps"].append({
                        "thought": thought,
                        "action": action_json,
                        "observation": observation
                    })
                except Exception as ex:
                    yield json.dumps({"type": "action_error", "message": f"Failed to parse action: {str(ex)}"})
                    break
            else:
                # No action matched, treat as final synthesis
                collected_data["final_report"] = response_text
                saved_url = await supabase_storage.save_report(target, collected_data)
                yield json.dumps({
                    "type": "final_report",
                    "content": response_text,
                    "report_location": saved_url
                })
                break

        yield json.dumps({"type": "complete", "message": "OSINT investigation completed successfully."})

    def _update_graph_from_observation(self, target: str, tool_name: str, obs: Dict[str, Any], collected_data: Dict[str, Any], yield_hook=None):
        """Builds relationship nodes (subdomains, emails, IP addresses) for graph rendering."""
        if tool_name == "recon_subdomains" and "subdomains" in obs:
            for sub in obs["subdomains"][:15]:
                if not any(n["id"] == sub for n in collected_data["graph_nodes"]):
                    collected_data["graph_nodes"].append({"id": sub, "label": sub, "type": "subdomain"})
                    collected_data["graph_edges"].append({"from": target, "to": sub, "label": "has_subdomain"})

        elif tool_name == "recon_dns" and "dns_records" in obs:
            for ip in obs["dns_records"].get("A", [])[:5]:
                if not any(n["id"] == ip for n in collected_data["graph_nodes"]):
                    collected_data["graph_nodes"].append({"id": ip, "label": ip, "type": "ip_address"})
                    collected_data["graph_edges"].append({"from": target, "to": ip, "label": "resolves_to"})

        elif tool_name == "check_username" and "profiles" in obs:
            for p in obs.get("profiles", []):
                platform_id = f"{p['platform']}:{p['url']}"
                collected_data["graph_nodes"].append({"id": platform_id, "label": p['platform'], "type": "social_profile"})
                collected_data["graph_edges"].append({"from": target, "to": platform_id, "label": "active_on"})

osint_orchestrator = OSINTOrchestrator()
