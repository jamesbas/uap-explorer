import { useEffect, useMemo, useState } from "react";
import DocumentCard from "../components/DocumentCard";
import { fetchDocuments, fetchFacets } from "../services/api";
import type {
  DocumentListResponse,
  FacetsResponse,
} from "../types/models";

const PAGE_SIZE = 24;

export default function BrowsePage() {
  const [facets, setFacets] = useState<FacetsResponse | null>(null);
  const [data, setData] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [query, setQuery] = useState("");
  const [agency, setAgency] = useState("");
  const [fileType, setFileType] = useState("");
  const [location, setLocation] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    fetchFacets().then(setFacets).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchDocuments({
      query,
      agency,
      file_type: fileType,
      incident_location: location,
      offset,
      limit: PAGE_SIZE,
    })
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [query, agency, fileType, location, offset]);

  const total = data?.total ?? 0;
  const pageEnd = useMemo(() => Math.min(offset + PAGE_SIZE, total), [offset, total]);

  const resetOffset = () => setOffset(0);

  return (
    <div>
      <h2>Browse the archive</h2>

      <div className="toolbar">
        <input
          className="input"
          placeholder="Filter by keyword..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            resetOffset();
          }}
        />
        <select
          className="select"
          value={agency}
          onChange={(e) => {
            setAgency(e.target.value);
            resetOffset();
          }}
        >
          <option value="">All agencies</option>
          {facets?.agency.map((f) => (
            <option key={f.value} value={f.value}>
              {f.value} ({f.count})
            </option>
          ))}
        </select>
        <select
          className="select"
          value={fileType}
          onChange={(e) => {
            setFileType(e.target.value);
            resetOffset();
          }}
        >
          <option value="">All types</option>
          {facets?.file_type.map((f) => (
            <option key={f.value} value={f.value}>
              {f.value} ({f.count})
            </option>
          ))}
        </select>
        <select
          className="select"
          value={location}
          onChange={(e) => {
            setLocation(e.target.value);
            resetOffset();
          }}
        >
          <option value="">All locations</option>
          {facets?.incident_location.map((f) => (
            <option key={f.value} value={f.value}>
              {f.value} ({f.count})
            </option>
          ))}
        </select>
        {(query || agency || fileType || location) && (
          <button
            className="button secondary"
            onClick={() => {
              setQuery("");
              setAgency("");
              setFileType("");
              setLocation("");
              resetOffset();
            }}
          >
            Clear filters
          </button>
        )}
      </div>

      {error && <div className="error">{error}</div>}
      {loading && <p className="muted">Loading…</p>}

      {data && (
        <>
          <p className="muted">
            Showing {data.items.length === 0 ? 0 : offset + 1}–{pageEnd} of {total}
          </p>
          <div className="cards">
            {data.items.map((doc) => (
              <DocumentCard key={doc.document_id} doc={doc} />
            ))}
          </div>
          {data.items.length === 0 && !loading && (
            <p className="muted">No records match the current filters.</p>
          )}
          <div className="pagination">
            <button
              className="button secondary"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
            >
              Previous
            </button>
            <span>
              Page {Math.floor(offset / PAGE_SIZE) + 1} of{" "}
              {Math.max(1, Math.ceil(total / PAGE_SIZE))}
            </span>
            <button
              className="button secondary"
              disabled={offset + PAGE_SIZE >= total}
              onClick={() => setOffset(offset + PAGE_SIZE)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </div>
  );
}
