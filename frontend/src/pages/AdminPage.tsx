import { useEffect, useState } from "react";
import {
  adminWhoami,
  createIndex,
  fetchIndexInfo,
  fetchIngestionStatus,
  isAdmin,
  login,
  logout,
  recreateIndex,
  setAdminToken,
  startIngestion,
} from "../services/api";
import type { IndexStats, IngestionStatus } from "../types/models";

function LoginForm({ onSuccess }: { onSuccess: () => void }) {
  const [pwd, setPwd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { token } = await login(pwd);
      setAdminToken(token);
      onSuccess();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>Admin login</h2>
      <p className="muted">
        Admin access is required to run ingestion and manage the search index. The
        public site does not require login.
      </p>
      <form className="toolbar" onSubmit={submit}>
        <input
          className="input"
          type="password"
          placeholder="Admin password"
          value={pwd}
          onChange={(e) => setPwd(e.target.value)}
          autoFocus
        />
        <button className="button" type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
      {error && <div className="error">{error}</div>}
    </div>
  );
}

function AdminConsole({ onLogout }: { onLogout: () => void }) {
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [indexInfo, setIndexInfo] = useState<IndexStats | null>(null);
  const [maxDocs, setMaxDocs] = useState<number>(30);
  const [ensureIndex, setEnsureIndex] = useState(true);
  const [regenerateSummaries, setRegenerateSummaries] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  async function refresh() {
    try {
      const [s, idx] = await Promise.all([
        fetchIngestionStatus(),
        fetchIndexInfo().catch(() => null),
      ]);
      setStatus(s);
      if (idx) setIndexInfo(idx);
      setError(null);
    } catch (e) {
      setError(String(e));
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, []);

  async function handleStart(opts: { full?: boolean; summariesOnly?: boolean } = {}) {
    setActionMsg(null);
    try {
      const r = await startIngestion({
        max_docs: opts.full ? 10000 : maxDocs,
        ensure_index: ensureIndex,
        summaries_only: opts.summariesOnly === true,
        regenerate_summaries: opts.summariesOnly === true ? regenerateSummaries : false,
      });
      if (!r.started) {
        setActionMsg(`Not started: ${r.reason || "unknown"}`);
      } else {
        setActionMsg(
          opts.summariesOnly
            ? "Summaries-only run started. Watching status…"
            : "Ingestion started. Watching status…",
        );
      }
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleCreateIndex() {
    setActionMsg(null);
    try {
      await createIndex();
      setActionMsg("Index created/updated.");
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  async function handleRecreateIndex() {
    if (!confirm("Recreate the index? All indexed chunks will be deleted.")) return;
    setActionMsg(null);
    try {
      await recreateIndex();
      setActionMsg("Index dropped and recreated. Re-ingest to populate it.");
      refresh();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2>Admin console</h2>
        <button className="button secondary" onClick={onLogout}>
          Sign out
        </button>
      </div>

      {error && <div className="error">{error}</div>}
      {actionMsg && <p className="muted">{actionMsg}</p>}

      <h3 style={{ marginTop: 24 }}>Search index</h3>
      <div className="card">
        <div className="meta">
          <span><strong>Index:</strong> {indexInfo?.index_name || "—"}</span>
          <span><strong>Exists:</strong> {indexInfo?.exists ? "yes" : "no"}</span>
          <span><strong>Chunks:</strong> {indexInfo?.chunk_count ?? "—"}</span>
        </div>
        <div className="actions">
          <button className="button secondary" onClick={handleCreateIndex}>
            Create / update index
          </button>
          <button className="button secondary" onClick={handleRecreateIndex}>
            Drop &amp; recreate
          </button>
        </div>
      </div>

      <h3 style={{ marginTop: 24 }}>Ingestion</h3>
      <div className="card">
        <div className="toolbar" style={{ marginBottom: 8 }}>
          <label className="muted">
            Max docs:&nbsp;
            <input
              className="input"
              style={{ width: 90, flex: "0 0 auto" }}
              type="number"
              min={1}
              value={maxDocs}
              onChange={(e) => setMaxDocs(parseInt(e.target.value || "0", 10))}
            />
          </label>
          <label className="muted" style={{ alignSelf: "center" }}>
            <input
              type="checkbox"
              checked={ensureIndex}
              onChange={(e) => setEnsureIndex(e.target.checked)}
            />
            &nbsp;Ensure index exists first
          </label>
          <label className="muted" style={{ alignSelf: "center" }}>
            <input
              type="checkbox"
              checked={regenerateSummaries}
              onChange={(e) => setRegenerateSummaries(e.target.checked)}
            />
            &nbsp;Regenerate existing summaries (summaries-only mode)
          </label>
        </div>
        <div className="actions">
          <button
            className="button"
            disabled={status?.running}
            onClick={() => handleStart({ full: false })}
          >
            Run ingestion (test batch)
          </button>
          <button
            className="button secondary"
            disabled={status?.running}
            onClick={() => handleStart({ full: true })}
          >
            Run ingestion (all docs)
          </button>
          <button
            className="button secondary"
            disabled={status?.running}
            title="Skip extraction/chunking/embedding/indexing; only (re)generate AI summary JSON files. Useful after switching LLM models."
            onClick={() => handleStart({ full: true, summariesOnly: true })}
          >
            Generate summaries only (all docs)
          </button>
        </div>
      </div>

      {status && (
        <>
          <h3 style={{ marginTop: 24 }}>Run status</h3>
          <div className="card">
            <div className="meta">
              <span className="tag">{status.running ? "running" : "idle"}</span>
              <span><strong>Started:</strong> {status.started_at || "—"}</span>
              <span><strong>Finished:</strong> {status.finished_at || "—"}</span>
            </div>
            <div className="meta">
              <span><strong>Target:</strong> {status.total_target}</span>
              <span><strong>Done:</strong> {status.completed}</span>
              <span><strong>Failed:</strong> {status.failed}</span>
              <span><strong>Skipped:</strong> {status.skipped}</span>
            </div>
            <div className="meta">
              <span><strong>Tokens — prompt:</strong> {status.tokens.prompt}</span>
              <span><strong>completion:</strong> {status.tokens.completion}</span>
              <span><strong>embedding:</strong> {status.tokens.embedding}</span>
              <span><strong>total:</strong> {status.tokens.total}</span>
            </div>
            {status.current_document && (
              <p>
                <strong>Currently:</strong> {status.current_document}
              </p>
            )}
            {status.last_run_summary && (
              <p className="muted">{status.last_run_summary}</p>
            )}
          </div>

          {status.errors.length > 0 && (
            <>
              <h3 style={{ marginTop: 18 }}>Errors</h3>
              <ul>
                {status.errors.slice(-20).map((e, i) => (
                  <li key={i}>
                    <strong>{e.title}:</strong> {e.error}
                  </li>
                ))}
              </ul>
            </>
          )}

          <h3 style={{ marginTop: 18 }}>Log (last 30)</h3>
          <pre
            style={{
              background: "var(--surface)",
              border: "1px solid var(--border)",
              padding: 12,
              borderRadius: 6,
              maxHeight: 320,
              overflow: "auto",
              fontSize: 12,
            }}
          >
            {status.log.slice(-30).join("\n")}
          </pre>
        </>
      )}
    </div>
  );
}

export default function AdminPage() {
  const [authed, setAuthed] = useState(isAdmin());

  useEffect(() => {
    if (!authed) return;
    // Verify token still valid; if not, drop it.
    adminWhoami().catch(() => {
      setAdminToken(null);
      setAuthed(false);
    });
  }, [authed]);

  return authed ? (
    <AdminConsole
      onLogout={() => {
        logout();
        setAuthed(false);
      }}
    />
  ) : (
    <LoginForm onSuccess={() => setAuthed(true)} />
  );
}
