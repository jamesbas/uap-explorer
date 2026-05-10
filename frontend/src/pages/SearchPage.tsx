import { useState } from "react";
import DocumentCard from "../components/DocumentCard";
import { searchDocuments } from "../services/api";
import type { DocumentListResponse } from "../types/models";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setSubmitted(true);
    try {
      const result = await searchDocuments(query.trim());
      setData(result);
      setError(null);
    } catch (err) {
      setError(String(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Search the archive</h2>
      <p className="muted">
        Search across record titles, descriptions, agencies, locations, and dates.
      </p>

      <form className="toolbar" onSubmit={onSubmit}>
        <input
          className="input"
          placeholder="Try: radar, Oak Ridge, Apollo, FBI..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <button className="button" type="submit">
          Search
        </button>
      </form>

      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">Searching…</p>}

      {data && (
        <>
          <p className="muted">
            {data.total} match{data.total === 1 ? "" : "es"} for{" "}
            <strong>"{query}"</strong>
          </p>
          <div className="cards">
            {data.items.map((doc) => (
              <DocumentCard key={doc.document_id} doc={doc} />
            ))}
          </div>
          {data.items.length === 0 && submitted && (
            <p className="muted">No records found.</p>
          )}
        </>
      )}
    </div>
  );
}
