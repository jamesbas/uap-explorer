import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchCompare } from "../services/api";
import {
  clearPack,
  getPack,
  onPackChange,
  removeFromPack,
} from "../services/researchPack";
import type { CompareResponse } from "../types/models";
import { Unknown } from "../components/Unknown";

export default function ComparePage() {
  const [pack, setPack] = useState<string[]>(getPack());
  const [data, setData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => onPackChange(() => setPack(getPack())), []);

  useEffect(() => {
    setData(null);
    setError(null);
    if (pack.length < 2) return;
    fetchCompare(pack)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [pack]);

  return (
    <div>
      <h2>Compare records</h2>
      <p className="muted">
        Build a research pack from any record's detail page (use{" "}
        <em>Add to research pack</em>), then return here to view the records
        side-by-side with their AI summaries and evidence scores.
      </p>

      <div className="toolbar">
        <span className="muted">Research pack: {pack.length} record(s)</span>
        {pack.length > 0 && (
          <button className="button secondary" onClick={() => clearPack()}>
            Clear pack
          </button>
        )}
        <button
          className="button secondary"
          onClick={() => window.print()}
          disabled={pack.length < 2}
        >
          Print / Save PDF
        </button>
      </div>

      {pack.length < 2 && (
        <p className="muted">
          Add at least two records to your research pack to compare them.
        </p>
      )}

      {error && <div className="error">{error}</div>}

      {data && <CompareGrid data={data} />}
    </div>
  );
}

function CompareGrid({ data }: { data: CompareResponse }) {
  const cols = data.documents.length;
  const cells = useMemo(
    () =>
      data.documents.map((d, i) => ({
        doc: d,
        summary: data.summaries[i],
        score: data.evidence_scores[i],
      })),
    [data]
  );

  return (
    <div
      className="compare-grid"
      style={{
        gridTemplateColumns: `180px repeat(${cols}, minmax(240px, 1fr))`,
      }}
    >
      <Row label="" cells={cells.map((c) => (
        <div key={c.doc.document_id} className="compare-header">
          <h3>
            <Link to={`/records/${c.doc.document_id}`}>{c.doc.title}</Link>
          </h3>
          <button
            className="button secondary"
            onClick={() => removeFromPack(c.doc.document_id)}
          >
            Remove from pack
          </button>
        </div>
      ))} />
      <Row label="Agency" cells={cells.map((c) => <Unknown key={c.doc.document_id}>{c.doc.agency}</Unknown>)} />
      <Row label="Incident date" cells={cells.map((c) => <Unknown key={c.doc.document_id}>{c.doc.incident_date}</Unknown>)} />
      <Row label="Incident location" cells={cells.map((c) => <Unknown key={c.doc.document_id}>{c.doc.incident_location}</Unknown>)} />
      <Row label="Release date" cells={cells.map((c) => <Unknown key={c.doc.document_id}>{c.doc.release_date}</Unknown>)} />
      <Row label="File type" cells={cells.map((c) => <Unknown key={c.doc.document_id}>{c.doc.file_type}</Unknown>)} />
      <Row label="Description" cells={cells.map((c) => (
        <span key={c.doc.document_id} className="compare-desc">
          {c.doc.description ?? <span className="unknown">No description.</span>}
        </span>
      ))} />
      <Row
        label="Evidence score"
        cells={cells.map((c) => (
          <div key={c.doc.document_id}>
            <strong>{c.score.overall_score}</strong> / {c.score.max_score}
            <ul className="dim-mini">
              {c.score.dimensions.slice(0, 4).map((d) => (
                <li key={d.name}>
                  {d.label}: {d.score}
                </li>
              ))}
            </ul>
          </div>
        ))}
      />
      <Row
        label="AI summary"
        cells={cells.map((c) => (
          <div key={c.doc.document_id}>
            {c.summary?.summary ? (
              c.summary.summary
            ) : (
              <span className="unknown">No summary cached. Run ingestion.</span>
            )}
          </div>
        ))}
      />
      <Row
        label="Key facts"
        cells={cells.map((c) => (
          <ul key={c.doc.document_id} className="kf-list">
            {(c.summary?.key_facts ?? []).slice(0, 5).map((k, i) => (
              <li key={i}>{k}</li>
            ))}
            {!c.summary?.key_facts?.length && (
              <li className="unknown">None.</li>
            )}
          </ul>
        ))}
      />
    </div>
  );
}

function Row({ label, cells }: { label: string; cells: React.ReactNode[] }) {
  return (
    <>
      <div className="compare-rowlabel">{label}</div>
      {cells.map((c, i) => (
        <div key={i} className="compare-cell">
          {c}
        </div>
      ))}
    </>
  );
}
