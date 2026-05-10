import { useState } from "react";
import { Link } from "react-router-dom";
import { ask } from "../services/api";
import type { AskResponse } from "../types/models";

const SAMPLE_QUESTIONS = [
  "Which records mention radar?",
  "What cases mention Oak Ridge?",
  "Which documents include photos or video?",
  "What object shapes are described?",
  "Which records are from the 1940s?",
];

function renderAnswerWithCitations(answer: string, citations: AskResponse["citations"]) {
  // Convert [#] markers into superscript links to citation list below.
  const parts = answer.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
    const m = part.match(/^\[(\d+)\]$/);
    if (m) {
      const idx = parseInt(m[1], 10);
      const cite = citations.find((c) => c.index === idx);
      if (cite) {
        return (
          <sup key={i}>
            <a href={`#cite-${idx}`} title={cite.title}>
              [{idx}]
            </a>
          </sup>
        );
      }
    }
    return <span key={i}>{part}</span>;
  });
}

export default function AskPage() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<AskResponse | null>(null);

  async function submit(q: string) {
    if (!q.trim()) return;
    setLoading(true);
    setError(null);
    setResponse(null);
    try {
      const r = await ask(q.trim());
      setResponse(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Ask the archive</h2>
      <p className="muted">
        Ask natural-language questions. Answers come from indexed source documents and
        include inline citations. Records must be ingested first (see the Admin page).
      </p>

      <form
        className="toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          submit(question);
        }}
      >
        <input
          className="input"
          placeholder="e.g. Which records mention radar?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          autoFocus
        />
        <button className="button" type="submit" disabled={loading}>
          {loading ? "Searching…" : "Ask"}
        </button>
      </form>

      <div className="toolbar" style={{ gap: 6 }}>
        {SAMPLE_QUESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            className="button secondary"
            style={{ fontSize: 12, padding: "4px 10px" }}
            onClick={() => {
              setQuestion(s);
              submit(s);
            }}
          >
            {s}
          </button>
        ))}
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">Querying the archive…</p>}

      {response && (
        <div className="answer-block">
          <div className="card" style={{ marginBottom: 18 }}>
            <div className="meta">
              <span className="tag">Confidence: {response.confidence}</span>
              {response.usage?.total_tokens !== undefined && (
                <span className="muted">
                  {response.usage.total_tokens} tokens
                </span>
              )}
            </div>
            <div style={{ whiteSpace: "pre-wrap", lineHeight: 1.6 }}>
              {renderAnswerWithCitations(response.answer, response.citations)}
            </div>
          </div>

          {response.citations.length > 0 && (
            <>
              <h3>Sources</h3>
              <ol className="citation-list">
                {response.citations.map((c) => (
                  <li key={c.chunk_id} id={`cite-${c.index}`}>
                    <Link to={`/records/${c.document_id}`}>{c.title}</Link>
                    {c.page_number != null && <> &middot; page {c.page_number}</>}
                    {c.agency && <> &middot; {c.agency}</>}
                    {c.snippet && (
                      <div className="muted" style={{ fontSize: 13, marginTop: 4 }}>
                        “{c.snippet}…”
                      </div>
                    )}
                  </li>
                ))}
              </ol>
            </>
          )}

          {response.followups.length > 0 && (
            <>
              <h3 style={{ marginTop: 18 }}>Suggested follow-ups</h3>
              <div className="toolbar" style={{ gap: 6 }}>
                {response.followups.map((f) => (
                  <button
                    key={f}
                    type="button"
                    className="button secondary"
                    style={{ fontSize: 12, padding: "4px 10px" }}
                    onClick={() => {
                      setQuestion(f);
                      submit(f);
                    }}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
