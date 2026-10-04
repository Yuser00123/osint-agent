// Super OSINT AI Agent Frontend Logic

let networkGraph = null;
let graphNodes = null;
let graphEdges = null;
let abortController = null;
let lastFinalReportText = "";

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initGraph();
  checkSystemStatus();
  initFormListeners();
});

// Check backend status
async function checkSystemStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    
    const statusText = document.getElementById("system-status-text");
    const providerText = document.getElementById("active-provider-text");
    const storageText = document.getElementById("storage-text");

    if (data.status === "online") {
      statusText.textContent = "ONLINE // READY";
      statusText.parentElement.style.borderColor = "var(--accent-emerald)";
      
      const providers = data.available_llm_providers || [];
      if (providers.length > 0) {
        providerText.textContent = `LLM: ${providers.join("/")}`;
      } else {
        providerText.textContent = "LLM: Keys Needed in .env";
        providerText.style.color = "var(--accent-amber)";
      }

      storageText.textContent = data.storage;
    }
  } catch (e) {
    document.getElementById("system-status-text").textContent = "OFFLINE";
    document.getElementById("system-status-pill").style.borderColor = "var(--accent-coral)";
  }
}

// Tab navigation
function initTabs() {
  const tabs = document.querySelectorAll(".tab-btn");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      tab.classList.add("active");
      const targetId = tab.dataset.tab;
      const targetEl = document.getElementById(targetId);
      if (targetEl) targetEl.classList.add("active");

      if (targetId === "tab-graph" && networkGraph) {
        setTimeout(() => networkGraph.fit(), 150);
      }
    });
  });

  // Slider change
  const slider = document.getElementById("max-steps-input");
  const stepVal = document.getElementById("steps-val");
  slider.addEventListener("input", (e) => {
    stepVal.textContent = e.target.value;
  });

  // Clear terminal
  document.getElementById("clear-stream-btn").addEventListener("click", () => {
    document.getElementById("stream-output").innerHTML = '<div class="terminal-welcome"><p>Terminal cleared. Ready for next reconnaissance task.</p></div>';
  });

  // Export report
  document.getElementById("export-dossier-btn").addEventListener("click", exportDossier);

  // Generate dorks button
  document.getElementById("generate-dorks-btn").addEventListener("click", handleGenerateDorks);

  // Browser snapshot button
  document.getElementById("browser-go-btn").addEventListener("click", handleBrowseUrl);
}

// Initialize Vis-Network Intelligence Graph
function initGraph() {
  const container = document.getElementById("network-graph-container");
  if (!container || typeof vis === "undefined") return;

  graphNodes = new vis.DataSet([
    { id: "ROOT", label: "TARGET", color: { background: "#00f0ff", border: "#fff" }, font: { color: "#fff", face: "Fira Code" } }
  ]);
  graphEdges = new vis.DataSet([]);

  const data = { nodes: graphNodes, edges: graphEdges };
  const options = {
    nodes: {
      shape: "dot",
      size: 20,
      font: { size: 12, color: "#fff" },
      borderWidth: 2
    },
    edges: {
      color: { color: "rgba(0, 240, 255, 0.4)", highlight: "#00f0ff" },
      font: { size: 10, color: "#94a3b8", align: "top" },
      arrows: { to: { enabled: true, scaleFactor: 0.6 } }
    },
    physics: {
      stabilization: false,
      barnesHut: { gravitationalConstant: -2500, springLength: 95 }
    }
  };

  networkGraph = new vis.Network(container, data, options);
}

function updateGraph(target, type, label) {
  if (!graphNodes) return;
  
  let color = "#00f0ff";
  if (type === "subdomain") color = "#10b981";
  if (type === "ip_address") color = "#f59e0b";
  if (type === "social_profile") color = "#a855f7";

  if (!graphNodes.get(label)) {
    graphNodes.add({
      id: label,
      label: label,
      color: { background: color, border: "#fff" },
      font: { color: "#fff", face: "Fira Code" }
    });
    graphEdges.add({
      from: target,
      to: label,
      label: type
    });
  }
}

// Investigation form handling
function initFormListeners() {
  const form = document.getElementById("investigation-form");
  const startBtn = document.getElementById("start-btn");
  const stopBtn = document.getElementById("stop-btn");

  stopBtn.addEventListener("click", () => {
    if (abortController) {
      abortController.abort();
      addTerminalCard("status", "Reconnaissance aborted by user.", "SYSTEM");
      resetButtons();
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const target = document.getElementById("target-input").value.trim();
    if (!target) return;

    const invType = document.getElementById("investigation-type").value;
    const provider = document.getElementById("llm-provider-select").value || null;
    const maxSteps = parseInt(document.getElementById("max-steps-input").value);

    // Switch to Terminal tab
    document.querySelector('.tab-btn[data-tab="tab-stream"]').click();

    // Prepare UI
    startBtn.classList.add("hidden");
    stopBtn.classList.remove("hidden");
    
    const terminal = document.getElementById("stream-output");
    terminal.innerHTML = "";

    // Reset graph
    if (graphNodes) {
      graphNodes.clear();
      graphEdges.clear();
      graphNodes.add({ id: target, label: target, color: { background: "#00f0ff", border: "#fff" }, font: { color: "#fff", face: "Fira Code" } });
    }

    abortController = new AbortController();

    try {
      const response = await fetch("/api/investigate/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          target: target,
          investigation_type: invType,
          provider: provider,
          max_steps: maxSteps
        }),
        signal: abortController.signal
      });

      if (!response.ok) {
        addTerminalCard("error", `Server returned error ${response.status}: ${response.statusText}`, "ERROR");
        resetButtons();
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop(); // keep remainder

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const rawJson = line.slice(6).trim();
            if (rawJson) {
              try {
                const event = JSON.parse(rawJson);
                handleAgentEvent(target, event);
              } catch (err) {
                console.error("JSON parse error:", err, rawJson);
              }
            }
          }
        }
      }
    } catch (err) {
      if (err.name !== "AbortError") {
        addTerminalCard("error", `Network or streaming error: ${err.message}`, "EXCEPTION");
      }
    } finally {
      resetButtons();
    }
  });
}

function resetButtons() {
  document.getElementById("start-btn").classList.remove("hidden");
  document.getElementById("stop-btn").classList.add("hidden");
}

function handleAgentEvent(target, event) {
  if (event.type === "status") {
    addTerminalCard("status", event.message, "SYSTEM");
  } else if (event.type === "step") {
    addTerminalCard("status", `Step ${event.step} of ${event.max_steps} in progress...`, "REASONING CYCLE");
  } else if (event.type === "llm_meta") {
    addTerminalCard("status", `Using LLM Provider: [${event.provider.toUpperCase()}] Model: ${event.model}`, "ROUTER");
  } else if (event.type === "thought") {
    addTerminalCard("thought", event.content, "AI REASONING THOUGHT");
  } else if (event.type === "action") {
    addTerminalCard("action", `Executing Tool: ${event.tool}\nArguments: ${JSON.stringify(event.args, null, 2)}`, "TOOL INVOCATION");
  } else if (event.type === "observation") {
    addTerminalCard("observation", JSON.stringify(event.data, null, 2), `OBSERVATION // ${event.tool.toUpperCase()}`);
    // Populate graph from observation
    if (event.tool === "recon_subdomains" && event.data.subdomains) {
      event.data.subdomains.slice(0, 15).forEach(sub => updateGraph(target, "subdomain", sub));
    } else if (event.tool === "recon_dns" && event.data.dns_records) {
      (event.data.dns_records.A || []).forEach(ip => updateGraph(target, "ip_address", ip));
    } else if (event.tool === "check_username" && event.data.profiles) {
      event.data.profiles.forEach(p => updateGraph(target, "social_profile", p.platform));
    }
  } else if (event.type === "final_report") {
    lastFinalReportText = event.content;
    const extra = event.report_location ? `\n\n[Persistent Storage Dossier]: ${event.report_location}` : "";
    addTerminalCard("final_report", event.content + extra, "INTELLIGENCE DOSSIER // SYNTHESIS");
  } else if (event.type === "error") {
    addTerminalCard("error", event.message, "AGENT ERROR");
  }
}

function addTerminalCard(type, content, headerText) {
  const terminal = document.getElementById("stream-output");
  const card = document.createElement("div");
  card.className = `event-card ${type}`;

  const header = document.createElement("div");
  header.className = "event-header";
  header.textContent = headerText;

  const body = document.createElement("div");
  body.className = "event-content";
  body.textContent = content;

  card.appendChild(header);
  card.appendChild(body);
  terminal.appendChild(card);
  terminal.scrollTop = terminal.scrollHeight;
}

// Google Dorks Studio Generation
async function handleGenerateDorks() {
  const target = document.getElementById("target-input").value.trim() || "example.com";
  const cat = document.getElementById("dork-category-select").value || null;
  const container = document.getElementById("dorks-container");
  
  container.innerHTML = '<div class="empty-state">Synthesizing Google Dorks...</div>';

  try {
    const res = await fetch("/api/dorks/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target: target, category: cat })
    });
    const data = await res.json();
    const dorks = data.dorks || [];

    if (dorks.length === 0) {
      container.innerHTML = '<div class="empty-state">No dorks found for this category.</div>';
      return;
    }

    container.innerHTML = "";
    dorks.forEach(d => {
      const card = document.createElement("div");
      card.className = "dork-card";
      card.innerHTML = `
        <div>
          <span class="dork-tag">${d.category.replace('_', ' ')}</span>
          <div class="dork-query">${escapeHtml(d.query)}</div>
        </div>
        <div class="dork-links">
          <a href="${d.google_search_url}" target="_blank" class="dork-btn">Open Google</a>
          <a href="${d.duckduckgo_url}" target="_blank" class="dork-btn">Open DuckDuckGo</a>
          <button class="dork-btn" onclick="executeDorkDirect('${escapeHtml(d.query)}')">Run via Agent</button>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = `<div class="empty-state">Error generating dorks: ${e.message}</div>`;
  }
}

async function executeDorkDirect(query) {
  document.querySelector('.tab-btn[data-tab="tab-stream"]').click();
  addTerminalCard("action", `Executing direct dork query: ${query}`, "STEALTH DORK ENGINE");
  try {
    const res = await fetch("/api/dorks/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: query })
    });
    const data = await res.json();
    addTerminalCard("observation", JSON.stringify(data, null, 2), "DORK SEARCH RESULTS");
  } catch (e) {
    addTerminalCard("error", e.message, "SEARCH ERROR");
  }
}

// Stealth Browser Handler
async function handleBrowseUrl() {
  const url = document.getElementById("browser-url-input").value.trim();
  if (!url) return;

  const viewer = document.getElementById("screenshot-viewer");
  const textBox = document.getElementById("browser-extracted-text");

  viewer.innerHTML = '<p class="placeholder-text">Rendering snapshot...</p>';
  textBox.innerHTML = '<p class="placeholder-text">Extracting DOM content...</p>';

  try {
    const res = await fetch("/api/browser/browse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();

    if (data.screenshot_url) {
      viewer.innerHTML = `<img src="${data.screenshot_url}" alt="Screenshot" onerror="this.parentElement.innerHTML='<p class=placeholder-text>Snapshot unavailable</p>'">`;
    }

    textBox.innerHTML = `
      <p><strong>Title:</strong> ${escapeHtml(data.title || "")}</p>
      <p><strong>Status:</strong> ${data.status_code}</p>
      <p><strong>Meta:</strong> ${escapeHtml(data.meta_description || "None")}</p>
      <hr style="border-color:var(--border-subtle); margin:0.8rem 0;">
      <p><strong>Outbound Links (${(data.links_found || []).length}):</strong></p>
      <ul>${(data.links_found || []).slice(0, 10).map(l => `<li><a href="${l}" target="_blank" class="glow-link">${escapeHtml(l)}</a></li>`).join('')}</ul>
      <hr style="border-color:var(--border-subtle); margin:0.8rem 0;">
      <p><strong>Cleaned Content:</strong></p>
      <div>${escapeHtml(data.content_preview || "")}</div>
    `;
  } catch (e) {
    textBox.innerHTML = `<p class="placeholder-text">Error browsing URL: ${e.message}</p>`;
  }
}

// Quick Run Tools
async function quickRun(tool) {
  const target = document.getElementById("target-input").value.trim();
  if (!target) {
    alert("Please enter a target domain or username first.");
    return;
  }

  document.querySelector('.tab-btn[data-tab="tab-stream"]').click();
  addTerminalCard("action", `Triggering quick tool: ${tool} on target: ${target}`, "DIRECT TOOL DISPATCH");

  try {
    let endpoint = "";
    if (tool === "subdomains") endpoint = `/api/recon/subdomains?domain=${encodeURIComponent(target)}`;
    else if (tool === "dns") endpoint = `/api/recon/dns?domain=${encodeURIComponent(target)}`;
    else if (tool === "headers") endpoint = `/api/recon/headers?url=${encodeURIComponent(target)}`;
    else if (tool === "archive") endpoint = `/api/recon/archive?target_url=${encodeURIComponent(target)}`;
    else if (tool === "username") endpoint = `/api/recon/username?username=${encodeURIComponent(target)}`;
    else if (tool === "browse") {
      document.querySelector('.tab-btn[data-tab="tab-browser"]').click();
      document.getElementById("browser-url-input").value = target.startsWith("http") ? target : `https://${target}`;
      handleBrowseUrl();
      return;
    }

    const res = await fetch(endpoint);
    const data = await res.json();
    addTerminalCard("observation", JSON.stringify(data, null, 2), `QUICK OSINT RESULT // ${tool.toUpperCase()}`);

    // Update graph
    if (tool === "subdomains" && data.subdomains) {
      data.subdomains.slice(0, 15).forEach(s => updateGraph(target, "subdomain", s));
    } else if (tool === "dns" && data.dns_records) {
      (data.dns_records.A || []).forEach(ip => updateGraph(target, "ip_address", ip));
    } else if (tool === "username" && data.profiles) {
      data.profiles.forEach(p => updateGraph(target, "social_profile", p.platform));
    }
  } catch (e) {
    addTerminalCard("error", e.message, "QUICK TOOL ERROR");
  }
}

// Export Dossier
function exportDossier() {
  if (!lastFinalReportText) {
    alert("No completed dossier available to export yet. Run an investigation first.");
    return;
  }
  const blob = new Blob([lastFinalReportText], { type: "text/markdown" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `OSINT_DOSSIER_${new Date().toISOString().slice(0,10)}.md`;
  a.click();
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
