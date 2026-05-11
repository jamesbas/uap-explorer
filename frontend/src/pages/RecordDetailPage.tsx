import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  fetchDocument,
  fetchDocumentSummary,
  fetchEvidence,
} from "../services/api";
import {
  isInPack,
  onPackChange,
  togglePack,
} from "../services/researchPack";
import type {
  DocumentRecord,
  DocumentSummary,
  EvidenceScoreResponse,
} from "../types/models";
import { Unknown } from "../components/Unknown";

export default function RecordDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [doc, setDoc] = useState<DocumentRecord | null>(null);
  const [summary, setSummary] = useState<DocumentSummary | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<EvidenceScoreResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [inPack, setInPack] = useState(false);

  useEffect(() => {
    if (!id) return;
    setDoc(null);
    setSummary(null);
    setSummaryError(null);
    setEvidence(null);
    setError(null);
    setInPack(isInPack(id));
    fetchDocument(id)
      .then(setDoc)
      .catch((e) => setError(String(e)));
    fetchDocumentSummary(id)
      .then(setSummary)
      .catch((e) => setSummaryError(String(e)));
    fetchEvidence(id)
      .then(setEvidence)
      .catch(() => setEvidence(null));
  }, [id]);

  useEffect(() => {
    if (!id) return;
    return onPackChange(() => setInPack(isInPack(id)));
  }, [id]);

  if (error) return <div className="error">{error}</div>;
  if (!doc) return <p className="muted">Loading record…</p>;

  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        <Link to="/browse">← Back to browse</Link>
      </p>
      <h2 style={{ wordBreak: "break-word" }}>{doc.title}</h2>

      <div className="toolbar">
        <button
          className={`button ${inPack ? "secondary" : ""}`}
          onClick={() => id && togglePack(id)}
        >
          {inPack ? "Remove from research pack" : "Add to research pack"}
        </button>
        <Link to="/compare" className="button secondary">
          Open compare view
        </Link>
      </div>

      <div className="detail-grid">
        <div>
          {doc.thumbnail_url ? (
            <img
              src={doc.thumbnail_url}
              alt={`Thumbnail for ${doc.title}`}
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          ) : (
            <div className="placeholder-box" style={{ marginTop: 0 }}>
              No thumbnail available.
            </div>
          )}
        </div>
        <div>
          <table className="metadata-table">
            <tbody>
              <tr>
                <th>Agency</th>
                <td><Unknown>{doc.agency}</Unknown></td>
              </tr>
              <tr>
                <th>File type</th>
                <td><Unknown>{doc.file_type}</Unknown></td>
              </tr>
              <tr>
                <th>Release date</th>
                <td><Unknown>{doc.release_date}</Unknown></td>
              </tr>
              <tr>
                <th>Incident date</th>
                <td><Unknown>{doc.incident_date}</Unknown></td>
              </tr>
              <tr>
                <th>Incident location</th>
                <td><Unknown>{doc.incident_location}</Unknown></td>
              </tr>
              <tr>
                <th>Redaction</th>
                <td><Unknown>{doc.redaction}</Unknown></td>
              </tr>
              <tr>
                <th>Source file</th>
                <td>
                  {doc.source_url ? (
                    <a href={doc.source_url} target="_blank" rel="noreferrer noopener">
                      Open original source
                    </a>
                  ) : (
                    <span className="unknown">Not available</span>
                  )}
                </td>
              </tr>
              {doc.local_file_path && (
                <tr>
                  <th>Local copy</th>
                  <td>
                    <a href={`/api/documents/${doc.document_id}/file`}>Download</a>
                  </td>
                </tr>
              )}
              {doc.dvids_video_id && (
                <tr>
                  <th>DVIDS video ID</th>
                  <td>{doc.dvids_video_id}</td>
                </tr>
              )}
              {doc.video_title && (
                <tr>
                  <th>Video title</th>
                  <td>{doc.video_title}</td>
                </tr>
              )}
              <tr>
                <th>Document ID</th>
                <td><code>{doc.document_id}</code></td>
              </tr>
            </tbody>
          </table>

          <h3 style={{ marginTop: 24 }}>Description</h3>
          {doc.description ? (
            <p>{doc.description}</p>
          ) : (
            <p className="unknown">No description provided.</p>
          )}

          <h3 style={{ marginTop: 24 }}>AI summary</h3>
          {summary ? (
            <div className="card">
              <p>{summary.summary || <span className="unknown">No summary text.</span>}</p>
              {summary.key_facts.length > 0 && (
                <>
                  <strong>Key facts</strong>
                  <ul>
                    {summary.key_facts.map((f, i) => (
                      <li key={i}>{f}</li>
                    ))}
                  </ul>
                </>
              )}
              <div className="meta" style={{ marginTop: 6 }}>
                {summary.evidence_types.map((e) => (
                  <span key={e} className="tag">{e}</span>
                ))}
              </div>
              {(summary.notable_locations.length > 0 ||
                summary.notable_dates.length > 0) && (
                <p className="muted" style={{ marginTop: 8 }}>
                  {summary.notable_locations.length > 0 && (
                    <>Locations: {summary.notable_locations.join(", ")}. </>
                  )}
                  {summary.notable_dates.length > 0 && (
                    <>Dates: {summary.notable_dates.join(", ")}.</>
                  )}
                </p>
              )}
              {summary.uncertainty_notes && (
                <p className="muted">
                  <em>Uncertainty:</em> {summary.uncertainty_notes}
                </p>
              )}
              <p className="muted" style={{ fontSize: 12 }}>
                AI-generated from indexed source text. Treat as a starting point and
                consult the original document.
              </p>

          <h3 style={{ marginTop: 24 }}>Evidence quality score</h3>
          {evidence ? (
            <div className="card">
              <p style={{ margin: 0 }}>
                <strong style={{ fontSize: 22 }}>
                  {evidence.overall_score}
                </strong>{" "}
                <span className="muted">/ {evidence.max_score}</span>
              </p>
              <p className="muted" style={{ fontSize: 12 }}>
                {evidence.disclaimer}
              </p>
              <table className="metadata-table">
                <tbody>
                  {evidence.dimensions.map((d) => (
                    <tr key={d.name}>
                      <th>{d.label}</th>
                      <td>
                        <strong>{d.score}</strong>{" "}
                        <span className="muted">— {d.rationale}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="muted">Loading evidence score…</p>
          )}
            </div>
          ) : (
            <div className="placeholder-box">
              {summaryError
                ? "No AI summary yet. Run ingestion for this document on the Admin page."
                : "Loading summary…"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
