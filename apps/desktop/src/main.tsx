import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { Database, Eye, FileUp, MessageSquareQuote, RefreshCw, Search, Settings, ShieldCheck, Trash2 } from "lucide-react";
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

const apiFromUrl = new URLSearchParams(window.location.search).get("api");
if (apiFromUrl) {
  window.localStorage.setItem("memoryos_api", apiFromUrl);
}
const API = apiFromUrl || window.localStorage.getItem("memoryos_api") || "http://127.0.0.1:8765";

function App() {
  const [view, setView] = useState("home");
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

  return (
    <main>
      <aside>
        <div className="brand"><Database size={22} /> MemoryOS</div>
        <button onClick={() => setView("home")}><Search size={18} /> Home</button>
        <button onClick={() => setView("imports")}><FileUp size={18} /> Imports</button>
        <button onClick={() => setView("ask")}><MessageSquareQuote size={18} /> Ask</button>
        <button onClick={() => setView("settings")}><Settings size={18} /> Settings</button>
        <button onClick={refresh}><RefreshCw size={18} /> Refresh</button>
      </aside>
      <section className="workspace">
        <header>
          <div className="privacy">{status}</div>
          {error && <div className="error">{error}</div>}
          <div className="searchbar">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search or ask your memory" />
            <button onClick={runSearch}><Search size={17} /> Search</button>
            <button onClick={askMemory}><MessageSquareQuote size={17} /> Ask</button>
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
              <button onClick={importFile}><FileUp size={17} /> Import</button>
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

createRoot(document.getElementById("root")!).render(<App />);
