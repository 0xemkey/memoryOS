import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Database, Eye, FileUp, Info, MessageSquareQuote, Moon, RefreshCw, Search, Settings, ShieldCheck, Sun, Trash2 } from "lucide-react";
import "./styles.css";

type Conversation = {
  conversation_id: string;
  provider: string;
  title: string;
  updated_at: string;
  summary?: string;
  privacy_level?: string;
  messages?: Message[];
};

type Message = {
  message_id: string;
  role: string;
  content: string;
  created_at: string;
  ordinal: number;
};

type SearchResult = {
  chunk_id: string;
  score: number;
  provider: string;
  conversation_title: string;
  conversation_id: string;
  message_ids: string[];
  created_at: string;
  snippet: string;
  source_type: string;
  privacy_level?: string;
};

type Diagnostics = {
  privacy_vault?: string;
  vault_key_provider?: string;
  normalized_storage?: string;
  sanitized_storage?: string;
  fts_index?: string;
  embedding_model?: string;
  reasoning_model?: string;
  retrieval_mode?: string;
  reasoning_mode?: string;
  container_isolation?: string;
  legacy_mvp_default?: boolean;
};

type AskMeta = {
  citations: string[];
  evidence_sufficient?: boolean;
  retrieval_mode?: string;
  reasoning_mode?: string;
  warnings: string[];
};

type GraphNode = {
  id: string;
  label: string;
  provider: string;
  updated_at?: string;
  message_count: number;
  weight: number;
  keywords: string[];
};

type GraphEdge = {
  source: string;
  target: string;
  weight: number;
  shared_terms: string[];
};

type GraphData = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  generated_at: string;
  node_count: number;
  edge_count: number;
};

const apiFromUrl = new URLSearchParams(window.location.search).get("api");
if (apiFromUrl) {
  window.localStorage.setItem("memoryos_api", apiFromUrl);
}
const configuredApi = import.meta.env.VITE_API_URL as string | undefined;
const API = apiFromUrl || configuredApi || window.localStorage.getItem("memoryos_api") || "http://127.0.0.1:8765";

function App() {
  const [view, setView] = useState("home");
  const [theme, setTheme] = useState(() => window.localStorage.getItem("memoryos_theme") || "dark");

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem("memoryos_theme", theme);
  }, [theme]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [query, setQuery] = useState("reinforcement learning robot decision");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [answer, setAnswer] = useState("");
  const [askMeta, setAskMeta] = useState<AskMeta>({ citations: [], warnings: [] });
  const [revealedAnswer, setRevealedAnswer] = useState("");
  const [importPath, setImportPath] = useState("");
  const [provider, setProvider] = useState("auto");
  const [status, setStatus] = useState("API not checked");
  const [error, setError] = useState("");
  const [settings, setSettings] = useState<Record<string, unknown>>({});
  const [diagnostics, setDiagnostics] = useState<Diagnostics>({});
  const [importStats, setImportStats] = useState<Record<string, unknown> | null>(null);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    try {
      setError("");
      const health = await fetch(`${API}/health`).then((r) => r.json());
      setStatus(`${health.memory_path}: ${health.privacy}`);
      setConversations(await fetch(`${API}/conversations`).then((r) => r.json()));
      setSettings((await fetch(`${API}/settings`).then((r) => r.json())).settings);
      setDiagnostics(await fetch(`${API}/diagnostics`).then((r) => r.json()));
    } catch {
      setStatus("Start the local API on http://127.0.0.1:8765");
    }
  }

  async function importFile() {
    try {
      setError("");
      const response = await fetch(`${API}/imports`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: importPath, provider }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(JSON.stringify(data.detail || data));
      }
      setImportStats(data);
      setStatus(`Imported ${data.imported}, sanitized ${data.sanitized_messages}, chunks ${data.chunks_indexed}`);
      await refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Import failed");
    }
  }

  async function runSearch() {
    const data = await fetch(`${API}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 8 }),
    }).then((r) => r.json());
    setResults(data.results);
    setStatus(`Search mode: ${data.retrieval_mode || "unknown"}${data.warnings?.length ? ` (${data.warnings[0]})` : ""}`);
    setView("search");
  }

  async function askMemory() {
    const data = await fetch(`${API}/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 6 }),
    }).then((r) => r.json());
    setAnswer(data.answer);
    setRevealedAnswer("");
    setAskMeta({
      citations: data.citations || [],
      evidence_sufficient: data.evidence_sufficient,
      retrieval_mode: data.retrieval_mode,
      reasoning_mode: data.reasoning_mode,
      warnings: data.warnings || [],
    });
    setResults(data.retrieved_context);
    setView("ask");
  }

  async function revealAnswer() {
    const data = await fetch(`${API}/answers/reveal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sanitized_answer: answer, mode: "full" }),
    }).then((r) => r.json());
    setRevealedAnswer(data.revealed_answer || "");
  }

  async function openConversation(id: string) {
    const data = await fetch(`${API}/conversations/${id}`).then((r) => r.json());
    setSelected(data);
    setView("conversation");
  }

  async function deleteData() {
    await fetch(`${API}/data`, { method: "DELETE" });
    setSelected(null);
    setResults([]);
    setAnswer("");
    setAskMeta({ citations: [], warnings: [] });
    setRevealedAnswer("");
    await refresh();
  }

  async function fetchGraph() {
    try {
      setGraphLoading(true);
      const data = await fetch(`${API}/graph?min_edge_weight=2&limit=150`).then((r) => r.json());
      setGraph(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
    } finally {
      setGraphLoading(false);
    }
  }

  return (
    <main>
      <aside>
        <div className="brand"><Database size={22} /> MemoryOS</div>
        <button className={view === "home" ? "active" : ""} onClick={() => setView("home")}><Search size={18} /> Home</button>
        <button className={view === "imports" ? "active" : ""} onClick={() => setView("imports")}><FileUp size={18} /> Imports</button>
        <button className={view === "brain" ? "active" : ""} onClick={() => { setView("brain"); fetchGraph(); }}><Database size={18} /> Brain</button>
        <button className={view === "ask" ? "active" : ""} onClick={() => setView("ask")}><MessageSquareQuote size={18} /> Ask</button>
        <button className={view === "settings" ? "active" : ""} onClick={() => setView("settings")}><Settings size={18} /> Settings</button>
        <button className={view === "about" ? "active" : ""} onClick={() => setView("about")}><Info size={18} /> About</button>
        <button onClick={refresh}><RefreshCw size={18} /> Refresh</button>
        <button className="theme-toggle" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
          {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />} {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
      </aside>
      <section className="workspace">
        <header>
          <div className="privacy">{status}</div>
          {error && <div className="error">{error}</div>}
          <div className="searchbar">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search or ask your memory" />
            <button className="btn-primary" onClick={runSearch}><Search size={17} /> Search</button>
            <button className="btn-primary" onClick={askMemory}><MessageSquareQuote size={17} /> Ask</button>
          </div>
        </header>

        {view === "home" && (
          <div className="grid two">
            <section>
              <h1>Recent Conversations</h1>
              <div className="list">
                {conversations.map((conversation) => (
                  <button className="row" key={conversation.conversation_id} onClick={() => openConversation(conversation.conversation_id)}>
                    <span>{conversation.title}</span>
                    <small>{conversation.provider} · {new Date(conversation.updated_at).toLocaleDateString()}</small>
                  </button>
                ))}
              </div>
            </section>
            <section>
              <h1>Indexing Status</h1>
              <p>{conversations.length} conversations indexed locally.</p>
              <StatusGrid diagnostics={diagnostics} />
            </section>
          </div>
        )}

        {view === "imports" && (
          <section>
            <h1>Imports</h1>
            <div className="formline">
              <input value={importPath} onChange={(e) => setImportPath(e.target.value)} placeholder="Absolute path to export file" />
              <select value={provider} onChange={(e) => setProvider(e.target.value)}>
                <option value="auto">Auto</option>
                <option value="chatgpt">ChatGPT</option>
                <option value="claude">Claude</option>
                <option value="gemini">Gemini</option>
                <option value="generic_json">Generic JSON</option>
                <option value="markdown">Markdown</option>
                <option value="plain_text">Plain text</option>
              </select>
              <button className="btn-primary" onClick={importFile}><FileUp size={17} /> Import</button>
            </div>
            {importStats && (
              <dl className="compact">
                {["stages", "privacy_findings", "sanitized_messages", "quarantined_messages", "chunks_indexed"].map((key) => (
                  <div key={key}><dt>{key}</dt><dd>{JSON.stringify(importStats[key])}</dd></div>
                ))}
              </dl>
            )}
          </section>
        )}

        {view === "search" && <Results results={results} openConversation={openConversation} />}

        {view === "ask" && (
          <section>
            <h1>Ask Memory</h1>
            <pre className="answer">{answer || "Ask a question to see a cited local answer."}</pre>
            {answer && (
              <div className="toolbar">
                <span><ShieldCheck size={16} /> {askMeta.retrieval_mode || "retrieval unknown"}</span>
                <span>{askMeta.reasoning_mode || "reasoning unknown"}</span>
                <span>{askMeta.citations.length} citations</span>
                <button onClick={revealAnswer}><Eye size={17} /> Reveal</button>
              </div>
            )}
            {askMeta.warnings.length > 0 && <p className="warning">{askMeta.warnings.join(" ")}</p>}
            {revealedAnswer && <pre className="answer revealed">{revealedAnswer}</pre>}
            <Results results={results} openConversation={openConversation} />
          </section>
        )}

        {view === "conversation" && selected && (
          <section>
            <h1>{selected.title}</h1>
            <p>{selected.provider} · {new Date(selected.updated_at).toLocaleString()}</p>
            <div className="messages">
              {selected.messages?.map((message) => (
                <article key={message.message_id} className={`message ${message.role}`}>
                  <strong>{message.ordinal}. {message.role}</strong>
                  <p>{message.content}</p>
                </article>
              ))}
            </div>
          </section>
        )}

        {view === "brain" && (
          <section style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <h1>Brain: Chat Connections</h1>
            <p style={{ fontSize: "14px", color: "var(--muted-foreground)", margin: "-8px 0 12px" }}>
              Every node is one of your chats. Two chats are linked only when they share distinctive
              vocabulary, computed locally with tokenization and TF-IDF-style statistics — nothing is sent
              to a model to decide these connections.
            </p>
            {graphLoading && (
              <div style={{ padding: "20px", textAlign: "center" }}>
                <p>Loading graph...</p>
              </div>
            )}
            {!graphLoading && graph && (
              <>
                <div style={{ fontSize: "14px", marginBottom: "10px", color: "var(--muted-foreground)" }}>
                  {graph.node_count} chats, {graph.edge_count} connections
                </div>
                {graph.node_count === 0 ? (
                  <div style={{ padding: "20px", textAlign: "center", color: "var(--muted-foreground)" }}>
                    <p>Import some conversations to see your chat graph</p>
                  </div>
                ) : (
                  <BrainGraph graph={graph} openConversation={openConversation} />
                )}
              </>
            )}
          </section>
        )}

        {view === "about" && (
          <section>
            <h1>About MemoryOS</h1>
            <p>
              MemoryOS is a local-first personal memory system. It imports your conversation exports
              (ChatGPT, Claude, Gemini, and more), makes them searchable, and lets you ask questions that
              are answered only from your own history — all on this device. There is no server, no
              account, and no cloud sync: everything below runs against the SQLite files on your disk.
            </p>

            <h1 style={{ marginTop: 22 }}>Live snapshot</h1>
            <dl className="compact">
              <div><dt>Conversations indexed</dt><dd>{conversations.length}</dd></div>
              <div><dt>Providers seen</dt><dd>{Array.from(new Set(conversations.map((c) => c.provider))).join(", ") || "none yet"}</dd></div>
              <div><dt>Vault</dt><dd>{diagnostics.privacy_vault || "unknown"} ({diagnostics.vault_key_provider || "unknown key"})</dd></div>
              <div><dt>Retrieval mode</dt><dd>{diagnostics.retrieval_mode || "unknown"}</dd></div>
              <div><dt>Reasoning mode</dt><dd>{diagnostics.reasoning_mode || "unknown"}</dd></div>
              <div><dt>Container isolation</dt><dd>{diagnostics.container_isolation || "unknown"}</dd></div>
            </dl>

            <h1 style={{ marginTop: 22 }}>Why local-first</h1>
            <p>
              Your raw conversations never leave this machine and are never sent to an external AI
              provider — not for search, not for answering questions, and not for building the Brain
              graph. Sensitive entities (names, emails, phone numbers, etc.) are detected and
              pseudonymized into an encrypted vault before anything is indexed. Answers are generated by
              evidence-only reasoning over your own retrieved text, and every claim traces back to a
              specific chunk of a specific conversation — the model can't assert something that isn't
              in your retrieved evidence.
            </p>

            <h1 style={{ marginTop: 22 }}>How the pipeline works</h1>
            <dl className="compact">
              <div><dt>1. Import</dt><dd>Provider export files are parsed by isolated per-provider adapters into normalized conversations and messages. Adapters are isolated because real export formats drift between provider updates.</dd></div>
              <div><dt>2. Sanitize</dt><dd>Detected personal entities are replaced with stable pseudonym tokens and the real values are stored only in an encrypted vault, separate from the searchable text.</dd></div>
              <div><dt>3. Chunk &amp; index</dt><dd>Sanitized text is split into conversation-aware chunks (preserving message order and IDs) and indexed for hybrid keyword + semantic search: SQLite FTS5 for keyword matching, local embeddings for semantic similarity.</dd></div>
              <div><dt>4. Ask</dt><dd>A question is embedded and matched against your chunk index; only the retrieved chunks are shown to the local reasoner, which must cite them — it cannot fall back on unconstrained model knowledge.</dd></div>
              <div><dt>5. Brain</dt><dd>The chat graph groups conversations by shared, statistically distinctive vocabulary. No model reads your chats to "understand" them — it's tokenization plus arithmetic (see below).</dd></div>
            </dl>

            <h1 style={{ marginTop: 22 }}>How the Brain graph actually works</h1>
            <p>
              Each conversation's sanitized text is tokenized locally into words and capitalized phrases,
              with common stopwords and generic technical noise removed. For every term, MemoryOS computes
              a TF-IDF-style score: how often the term appears in that conversation, scaled down by how
              many other conversations also use it. A term that appears in every chat (like "code" or
              "error") scores near zero and can never form a connection; a term that's concentrated in
              only a couple of chats (like <em>IsaacLab</em>, <em>tetrahedral mesh</em>, or{" "}
              <em>URDF</em>) scores highly.
            </p>
            <p>
              Each conversation keeps its top ~25 highest-scoring terms as candidate keywords. Two
              conversations are connected only if they share at least one of those keywords, and the edge
              weight is the strength of that shared vocabulary. To keep the graph readable, every node
              keeps only its 6 strongest connections — so one generic overlap can't turn the whole graph
              into a hairball. All of this is deterministic local computation: same data in, same graph
              out, every time, with nothing sent anywhere.
            </p>

            <h1 style={{ marginTop: 22 }}>Tech stack</h1>
            <dl className="compact">
              <div><dt>API</dt><dd>FastAPI (Python), local SQLite storage, no external DB server.</dd></div>
              <div><dt>Search</dt><dd>SQLite FTS5 (keyword) + local sentence-embedding model (semantic).</dd></div>
              <div><dt>Reasoning</dt><dd>Local Ollama-backed chat model, constrained to retrieved evidence.</dd></div>
              <div><dt>Privacy</dt><dd>Pseudonymization + an encrypted vault keyed via the OS keyring.</dd></div>
              <div><dt>Desktop UI</dt><dd>React + TypeScript, Vite dev server, Tauri shell for packaging.</dd></div>
            </dl>

            <h1 style={{ marginTop: 22 }}>Tabs</h1>
            <dl className="compact">
              <div><dt>Home</dt><dd>Recent conversations and local indexing status.</dd></div>
              <div><dt>Imports</dt><dd>Load a provider export file into your local store.</dd></div>
              <div><dt>Brain</dt><dd>Visualize how your chats relate to each other by shared topics.</dd></div>
              <div><dt>Ask</dt><dd>Ask a question and get a cited answer drawn only from your imported history.</dd></div>
              <div><dt>Settings</dt><dd>Review diagnostics and permanently delete local data.</dd></div>
            </dl>
          </section>
        )}

        {view === "settings" && (
          <section>
            <h1>Settings</h1>
            <dl>
              {Object.entries(settings).map(([key, value]) => (
                <div key={key}><dt>{key}</dt><dd>{JSON.stringify(value)}</dd></div>
              ))}
            </dl>
            <h1>Private Brain Diagnostics</h1>
            <StatusGrid diagnostics={diagnostics} />
            <button className="danger" onClick={deleteData}><Trash2 size={17} /> Delete Local Data</button>
          </section>
        )}
      </section>
    </main>
  );
}

function Results({ results, openConversation }: { results: SearchResult[]; openConversation: (id: string) => void }) {
  return (
    <section>
      <h1>Search Results</h1>
      <div className="list">
        {results.map((result) => (
          <article className="result" key={result.chunk_id}>
            <div className="resulthead">
              <strong>{result.conversation_title}</strong>
              <span>{result.score.toFixed(3)}</span>
            </div>
            <small>{result.provider} · {result.privacy_level || "sanitized"}</small>
            <p>{result.snippet}</p>
            <button onClick={() => openConversation(result.conversation_id)}>Open original conversation</button>
          </article>
        ))}
      </div>
    </section>
  );
}

function StatusGrid({ diagnostics }: { diagnostics: Diagnostics }) {
  const items = [
    ["Vault", `${diagnostics.privacy_vault || "unknown"} (${diagnostics.vault_key_provider || "unknown key"})`],
    ["Normalized", diagnostics.normalized_storage || "unknown"],
    ["Sanitized", diagnostics.sanitized_storage || "unknown"],
    ["Retrieval", diagnostics.retrieval_mode || "unknown"],
    ["Reasoning", diagnostics.reasoning_mode || "unknown"],
    ["Container isolation", diagnostics.container_isolation || "unknown"],
    ["Legacy MVP", diagnostics.legacy_mvp_default ? "enabled" : "disabled"],
  ];
  return (
    <dl className="compact">
      {items.map(([key, value]) => (
        <div key={key}><dt>{key}</dt><dd>{value}</dd></div>
      ))}
    </dl>
  );
}

const CYBER_MONO = "'JetBrains Mono', 'Fira Code', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace";
const NEON_GREEN = "#39ff9c";
const NEON_CYAN = "#2be8ff";
const NEON_MAGENTA = "#ff2ea6";
const NEON_YELLOW = "#f4ff4d";

function BrainGraph({ graph, openConversation }: { graph: GraphData; openConversation: (id: string) => void }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [command, setCommand] = useState("");
  const [cmdHistory, setCmdHistory] = useState<string[]>([]);
  const [historyPos, setHistoryPos] = useState<number | null>(null);
  const [cmdError, setCmdError] = useState("");
  const dragState = React.useRef<{ dragging: boolean; startX: number; startY: number; moved: boolean }>({
    dragging: false,
    startX: 0,
    startY: 0,
    moved: false,
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedId(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!graph.nodes || graph.nodes.length === 0) {
    return <div style={{ padding: "20px" }}>No data to visualize</div>;
  }

  const selectedNode = graph.nodes.find((n) => n.id === selectedId) || null;

  const neighborEdges = selectedId ? graph.edges.filter((e) => e.source === selectedId || e.target === selectedId) : [];
  const neighborIds = new Set(neighborEdges.map((e) => (e.source === selectedId ? e.target : e.source)));

  // Live keyword search: "find <term>" (or a bare term) highlights matching
  // chats by title/keyword; "open <term>" jumps straight into a unique match.
  const trimmed = command.trim();
  const isOpenCmd = /^open\s+/i.test(trimmed);
  const isFindCmd = /^find\s+/i.test(trimmed);
  const searchTerm = (isOpenCmd ? trimmed.replace(/^open\s+/i, "") : isFindCmd ? trimmed.replace(/^find\s+/i, "") : trimmed)
    .trim()
    .toLowerCase();
  const searchMatches =
    searchTerm.length > 0
      ? graph.nodes.filter(
          (n) => n.label.toLowerCase().includes(searchTerm) || n.keywords.some((k) => k.toLowerCase().includes(searchTerm))
        )
      : [];
  const matchedIds = new Set(searchMatches.map((n) => n.id));

  function runCommand() {
    const value = command.trim();
    if (!value) return;
    setCmdHistory((h) => [...h, value].slice(-30));
    setHistoryPos(null);
    setCmdError("");

    if (/^clear$/i.test(value)) {
      setCommand("");
      setSelectedId(null);
      return;
    }
    if (/^help$/i.test(value)) {
      setCmdError('commands: find <keyword> · open <keyword> · clear · esc to deselect');
      return;
    }
    if (isOpenCmd) {
      if (searchMatches.length === 1) {
        openConversation(searchMatches[0].id);
        setCommand("");
      } else if (searchMatches.length === 0) {
        setCmdError(`no chat matches "${searchTerm}"`);
      } else {
        setCmdError(`${searchMatches.length} matches — refine the keyword or click one below`);
      }
      return;
    }
    // bare term or "find <term>": select if unique, otherwise leave highlighted for browsing.
    if (searchMatches.length === 1) {
      setSelectedId(searchMatches[0].id);
    } else if (searchMatches.length === 0) {
      setCmdError(`no chat matches "${searchTerm}"`);
    }
  }

  const width = typeof window !== "undefined" ? Math.max(window.innerWidth - 340, 400) : 800;
  const height = typeof window !== "undefined" ? Math.max(window.innerHeight - 260, 400) : 600;

  // Order nodes by connectivity (BFS from the most-connected node in each
  // component) so linked chats land near each other on the rings instead of
  // in whatever order the API happened to return them.
  const adjacency = new Map<string, string[]>();
  graph.nodes.forEach((n) => adjacency.set(n.id, []));
  graph.edges.forEach((e) => {
    adjacency.get(e.source)?.push(e.target);
    adjacency.get(e.target)?.push(e.source);
  });
  const visited = new Set<string>();
  const ordered: GraphNode[] = [];
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const remaining = [...graph.nodes].sort((a, b) => (adjacency.get(b.id)?.length || 0) - (adjacency.get(a.id)?.length || 0));
  for (const start of remaining) {
    if (visited.has(start.id)) continue;
    const queue = [start.id];
    visited.add(start.id);
    while (queue.length) {
      const current = queue.shift()!;
      const node = byId.get(current);
      if (node) ordered.push(node);
      for (const neighbor of adjacency.get(current) || []) {
        if (!visited.has(neighbor)) {
          visited.add(neighbor);
          queue.push(neighbor);
        }
      }
    }
  }

  // Multi-ring layout: too many nodes on one ring makes labels overlap, so
  // spread them across concentric rings sized to keep each ring's arc-length
  // per node roughly constant.
  const nodesPerRing = 14;
  const ringCount = Math.max(1, Math.ceil(ordered.length / nodesPerRing));
  const rings: GraphNode[][] = Array.from({ length: ringCount }, () => []);
  ordered.forEach((node, idx) => rings[idx % ringCount].push(node));

  const baseRadius = Math.min(width, height) * 0.16;
  const ringGap = Math.min(width, height) * 0.11;

  const positions: { [key: string]: { x: number; y: number } } = {};
  rings.forEach((ringNodes, ringIdx) => {
    const radius = baseRadius + ringIdx * ringGap;
    const angleOffset = ringIdx * 0.35;
    ringNodes.forEach((node, i) => {
      const angle = angleOffset + (i / ringNodes.length) * Math.PI * 2;
      positions[node.id] = {
        x: width / 2 + Math.cos(angle) * radius,
        y: height / 2 + Math.sin(angle) * radius,
      };
    });
  });

  const maxWeight = Math.max(...graph.nodes.map((n) => n.weight), 1);
  const minNodeSize = 8;
  const maxNodeSize = 26;
  const gridSize = 32;

  const handleZoom = (delta: number) => setZoom((z) => Math.max(0.5, Math.min(5, z + delta)));
  const handleReset = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  return (
    <div style={{ display: "flex", flex: 1, gap: "16px", minHeight: 0 }}>
      <div style={{ display: "flex", flex: 1, flexDirection: "column", minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "0 0 8px", fontFamily: CYBER_MONO }}>
          <button onClick={() => handleZoom(0.2)} style={{ padding: "4px 8px", fontSize: "12px" }}>zoom+</button>
          <button onClick={() => handleZoom(-0.2)} style={{ padding: "4px 8px", fontSize: "12px" }}>zoom-</button>
          <button onClick={handleReset} style={{ padding: "4px 8px", fontSize: "12px" }}>reset</button>
          {selectedId && (
            <button
              onClick={() => setSelectedId(null)}
              style={{ padding: "4px 8px", fontSize: "12px", borderColor: NEON_GREEN, color: NEON_GREEN }}
            >
              ← back to full graph
            </button>
          )}
          <span style={{ fontSize: "12px", color: NEON_GREEN, marginLeft: "auto", paddingTop: "4px", opacity: 0.8 }}>
            zoom {zoom.toFixed(1)}x
          </span>
        </div>
        <svg
          width="100%"
          height="100%"
          viewBox={`0 0 ${width} ${height}`}
          style={{
            border: `1px solid ${NEON_GREEN}55`,
            borderRadius: "var(--radius)",
            backgroundColor: "#050708",
            boxShadow: `0 0 24px ${NEON_GREEN}22 inset`,
            cursor: dragState.current.dragging ? "grabbing" : "grab",
            flex: 1,
            touchAction: "none",
          }}
          onClick={() => {
            if (!dragState.current.moved) setSelectedId(null);
          }}
          onWheel={(e) => {
            e.preventDefault();
            handleZoom(e.deltaY > 0 ? -0.1 : 0.1);
          }}
          onMouseDown={(e) => {
            dragState.current = { dragging: true, startX: e.clientX - pan.x, startY: e.clientY - pan.y, moved: false };
          }}
          onMouseMove={(e) => {
            if (!dragState.current.dragging) return;
            const nextX = e.clientX - dragState.current.startX;
            const nextY = e.clientY - dragState.current.startY;
            if (Math.abs(nextX - pan.x) > 2 || Math.abs(nextY - pan.y) > 2) dragState.current.moved = true;
            setPan({ x: nextX, y: nextY });
          }}
          onMouseUp={() => {
            dragState.current.dragging = false;
          }}
          onMouseLeave={() => {
            dragState.current.dragging = false;
          }}
        >
          <defs>
            <pattern id="cyber-grid" width={gridSize} height={gridSize} patternUnits="userSpaceOnUse">
              <path d={`M ${gridSize} 0 L 0 0 0 ${gridSize}`} fill="none" stroke={NEON_GREEN} strokeOpacity="0.06" strokeWidth="1" />
            </pattern>
            <filter id="node-glow" x="-100%" y="-100%" width="300%" height="300%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="node-glow-strong" x="-150%" y="-150%" width="400%" height="400%">
              <feGaussianBlur stdDeviation="7" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="blur" />
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <rect x="0" y="0" width={width} height={height} fill="url(#cyber-grid)" pointerEvents="none" />

          <g transform={`translate(${pan.x}, ${pan.y}) translate(${width / 2}, ${height / 2}) scale(${zoom}) translate(${-width / 2}, ${-height / 2})`}>
            {graph.edges.map((edge, idx) => {
              const source = positions[edge.source];
              const target = positions[edge.target];
              if (!source || !target) return null;

              const isActive = !selectedId || edge.source === selectedId || edge.target === selectedId;
              const strokeWidth = Math.min(1 + edge.weight / 2, 6);

              return (
                <line
                  key={idx}
                  x1={source.x}
                  y1={source.y}
                  x2={target.x}
                  y2={target.y}
                  stroke={isActive ? NEON_CYAN : "#2a3a3a"}
                  strokeWidth={strokeWidth}
                  opacity={isActive ? (selectedId ? 0.85 : 0.4) : 0.06}
                  filter={isActive && selectedId ? "url(#node-glow)" : undefined}
                />
              );
            })}

            {graph.nodes.map((node) => {
              const pos = positions[node.id];
              if (!pos) return null;

              const size = minNodeSize + (node.weight / maxWeight) * (maxNodeSize - minNodeSize);
              const isSelected = selectedId === node.id;
              const isNeighbor = neighborIds.has(node.id);
              const isHovered = hoveredId === node.id;
              const isSearching = searchMatches.length > 0 && !selectedId;
              const isMatched = matchedIds.has(node.id);
              const isDimmed = selectedId ? !isSelected && !isNeighbor : isSearching && !isMatched;
              const fill = isSelected
                ? NEON_MAGENTA
                : isNeighbor
                ? NEON_CYAN
                : isSearching && isMatched
                ? NEON_YELLOW
                : NEON_GREEN;
              const showLabel = isSelected || isNeighbor || isHovered || (isSearching && isMatched);

              return (
                <g
                  key={node.id}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (dragState.current.moved) return;
                    setSelectedId(node.id);
                  }}
                  onMouseEnter={() => setHoveredId(node.id)}
                  onMouseLeave={() => setHoveredId((id) => (id === node.id ? null : id))}
                  style={{ pointerEvents: "auto", cursor: "pointer" }}
                >
                  {isSelected && (
                    <circle cx={pos.x} cy={pos.y} r={size + 6} fill="none" stroke={NEON_MAGENTA} strokeWidth={1.5} opacity={0.5}>
                      <animate attributeName="r" values={`${size + 4};${size + 12};${size + 4}`} dur="2s" repeatCount="indefinite" />
                      <animate attributeName="opacity" values="0.6;0.1;0.6" dur="2s" repeatCount="indefinite" />
                    </circle>
                  )}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={size}
                    fill={fill}
                    opacity={isDimmed ? 0.15 : 0.9}
                    filter={isDimmed ? undefined : isSelected || (isSearching && isMatched) ? "url(#node-glow-strong)" : "url(#node-glow)"}
                  />
                  <circle cx={pos.x} cy={pos.y} r={Math.max(size * 0.35, 2)} fill="#050708" opacity={isDimmed ? 0.15 : 0.8} />
                  {showLabel && (
                    <text
                      x={pos.x}
                      y={pos.y + size + 13}
                      textAnchor="middle"
                      fontSize="11"
                      fontFamily={CYBER_MONO}
                      fill={isSelected ? NEON_MAGENTA : isSearching && isMatched ? NEON_YELLOW : NEON_GREEN}
                      pointerEvents="none"
                      style={{ paintOrder: "stroke", stroke: "#050708", strokeWidth: 3 }}
                    >
                      {node.label.length > 34 ? node.label.slice(0, 34) + "…" : node.label}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>
      </div>

      {/* Info + connections + command panel */}
      <div
        style={{
          width: "290px",
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          fontFamily: CYBER_MONO,
          background: "#050708",
          border: `1px solid ${NEON_GREEN}55`,
          borderRadius: "var(--radius)",
          overflow: "hidden",
        }}
      >
        <div style={{ padding: "10px 12px", borderBottom: `1px solid ${NEON_GREEN}33` }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ color: NEON_GREEN, fontSize: "12px", opacity: 0.8 }}>guest@brain:~$</span>
            <input
              value={command}
              onChange={(e) => {
                setCommand(e.target.value);
                setCmdError("");
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") runCommand();
                if (e.key === "ArrowUp") {
                  e.preventDefault();
                  if (cmdHistory.length === 0) return;
                  const nextPos = historyPos === null ? cmdHistory.length - 1 : Math.max(0, historyPos - 1);
                  setHistoryPos(nextPos);
                  setCommand(cmdHistory[nextPos]);
                }
                if (e.key === "ArrowDown") {
                  e.preventDefault();
                  if (historyPos === null) return;
                  const nextPos = historyPos + 1;
                  if (nextPos >= cmdHistory.length) {
                    setHistoryPos(null);
                    setCommand("");
                  } else {
                    setHistoryPos(nextPos);
                    setCommand(cmdHistory[nextPos]);
                  }
                }
              }}
              placeholder="find isaaclab / open urdf / clear"
              spellCheck={false}
              className="brain-cmd-input"
              style={{
                flex: 1,
                minHeight: "auto",
                background: "transparent",
                border: "none",
                color: NEON_GREEN,
                fontFamily: CYBER_MONO,
                fontSize: "12px",
                padding: "2px 0",
                caretColor: NEON_GREEN,
              }}
            />
          </div>
          {cmdError && <div style={{ color: NEON_MAGENTA, fontSize: "11px", marginTop: 4 }}>{cmdError}</div>}
          {!cmdError && searchTerm && (
            <div style={{ color: NEON_YELLOW, fontSize: "11px", marginTop: 4, opacity: 0.85 }}>
              {searchMatches.length} match{searchMatches.length === 1 ? "" : "es"} highlighted
            </div>
          )}
        </div>

        <div style={{ padding: "14px", overflow: "auto", flex: 1 }}>
        {!selectedNode && searchTerm && (
          <div style={{ display: "grid", gap: 8 }}>
            {searchMatches.length === 0 && (
              <div style={{ color: NEON_GREEN, opacity: 0.5, fontSize: "12px" }}>no matches.</div>
            )}
            {searchMatches.map((node) => (
              <button
                key={node.id}
                style={{
                  padding: "10px",
                  textAlign: "left",
                  display: "grid",
                  gap: 2,
                  background: "#0a0f0e",
                  border: `1px solid ${NEON_YELLOW}55`,
                }}
                onClick={() => setSelectedId(node.id)}
              >
                <span style={{ fontSize: "13px", fontWeight: 600, color: NEON_YELLOW }}>{node.label}</span>
                <small style={{ color: NEON_GREEN, opacity: 0.6 }}>
                  {node.provider} · {node.message_count} msgs
                </small>
              </button>
            ))}
          </div>
        )}
        {!selectedNode && !searchTerm && (
          <div style={{ color: NEON_GREEN, opacity: 0.6, fontSize: "12px" }}>
            &gt; type a keyword to highlight matching chats<br />
            &gt; "open &lt;keyword&gt;" jumps straight to a unique match<br />
            &gt; click a node to inspect chat_history[]<br />
            &gt; esc or "back" clears selection
          </div>
        )}
        {selectedNode && (
          <div style={{ display: "grid", gap: 10 }}>
            <button
              onClick={() => setSelectedId(null)}
              style={{
                justifySelf: "start",
                background: "transparent",
                border: `1px solid ${NEON_GREEN}`,
                color: NEON_GREEN,
                fontSize: "11px",
                padding: "3px 8px",
              }}
            >
              ← back
            </button>

            <div>
              <strong style={{ color: NEON_MAGENTA }}>{selectedNode.label}</strong>
              <div style={{ fontSize: "12px", color: NEON_GREEN, opacity: 0.7 }}>
                {selectedNode.provider} · {selectedNode.message_count} msgs
                {selectedNode.updated_at ? ` · ${new Date(selectedNode.updated_at).toLocaleDateString()}` : ""}
              </div>
            </div>

            {selectedNode.keywords.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {selectedNode.keywords.map((kw) => (
                  <span
                    key={kw}
                    style={{
                      fontSize: "11px",
                      padding: "2px 8px",
                      borderRadius: 3,
                      border: `1px solid ${NEON_CYAN}66`,
                      color: NEON_CYAN,
                    }}
                  >
                    {kw}
                  </span>
                ))}
              </div>
            )}

            <button className="btn-primary" onClick={() => openConversation(selectedNode.id)}>
              open full conversation →
            </button>

            <div>
              <div style={{ fontSize: "12px", fontWeight: 600, margin: "8px 0 6px", color: NEON_GREEN, opacity: 0.8 }}>
                connections [{neighborEdges.length}]
              </div>
              {neighborEdges.length === 0 && (
                <div style={{ fontSize: "12px", color: NEON_GREEN, opacity: 0.5 }}>no strong shared-topic links yet.</div>
              )}
              <div style={{ display: "grid", gap: 8 }}>
                {neighborEdges
                  .sort((a, b) => b.weight - a.weight)
                  .map((edge) => {
                    const otherId = edge.source === selectedNode.id ? edge.target : edge.source;
                    const other = graph.nodes.find((n) => n.id === otherId);
                    if (!other) return null;
                    return (
                      <button
                        key={otherId}
                        style={{
                          padding: "10px",
                          textAlign: "left",
                          display: "grid",
                          gap: 2,
                          background: "#0a0f0e",
                          border: `1px solid ${NEON_CYAN}33`,
                        }}
                        onClick={() => setSelectedId(otherId)}
                      >
                        <span style={{ fontSize: "13px", fontWeight: 600, color: NEON_CYAN }}>{other.label}</span>
                        <small style={{ color: NEON_GREEN, opacity: 0.6 }}>
                          shared: {edge.shared_terms.join(", ")}
                        </small>
                        <span
                          role="button"
                          tabIndex={0}
                          onClick={(e) => {
                            e.stopPropagation();
                            openConversation(otherId);
                          }}
                          style={{ fontSize: "11px", color: NEON_MAGENTA, marginTop: 2 }}
                        >
                          open this chat →
                        </span>
                      </button>
                    );
                  })}
              </div>
            </div>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
