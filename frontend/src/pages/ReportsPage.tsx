import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchCachedReport,
  fetchReportTemplates,
  generateReport,
  reportMarkdownUrl,
} from "../services/api";
import { getPack } from "../services/researchPack";
import type { Report, ReportTemplate } from "../types/models";

export default function ReportsPage() {
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usePack, setUsePack] = useState(false);

  useEffect(() => {
    fetchReportTemplates()
      .then((r) => setTemplates(r.templates))
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!selected) {
      setReport(null);
      return;
    }
    setReport(null);
    setError(null);
    fetchCachedReport(selected)
      .then(setReport)
      .catch(() => {
        // No cached report yet — that's OK; user can click Generate.
      });
  }, [selected]);

  const pack = useMemo(() => getPack(), [selected, usePack]);

  async function handleGenerate(force = false) {
    if (!selected) return;
    setLoading(true);
    setError(null);
    try {
      const body: { document_ids?: string[]; force?: boolean } = { force };
      if (usePack && pack.length > 0) body.document_ids = pack;
      const r = await generateReport(selected, body);
      setReport(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h2>Reports</h2>
      <p className="muted">
        Citation-backed summaries written from the indexed metadata. Reports do
        not represent determinations about the nature of UAP — they are
        descriptive overviews of the records themselves.
      </p>

      <div className="reports-grid">
        <aside className="reports-sidebar">
          <h3>Templates</h3>
          <ul className="reports-templates">
            {templates.map((t) => (
              <li key={t.slug}>
                <button
                  className={`button ${selected === t.slug ? "" : "secondary"}`}
                  onClick={() => setSelected(t.slug)}
                  style={{ width: "100%", textAlign: "left" }}
                >
                  {t.title}
                </button>
                <p className="muted" style={{ marginTop: 4, fontSize: 12 }}>
                  {t.description}
                </p>
              </li>
            ))}
          </ul>
        </aside>

        <section className="reports-main">
          {!selected && (
            <p className="muted">
              Choose a template on the left to view or generate a report.
            </p>
          )}

          {selected && (
            <>
              <div className="toolbar">
                <button
                  className="button"
                  disabled={loading}
                  onClick={() => handleGenerate(false)}
                >
                  {loading
                    ? "Generating…"
                    : report
                    ? "Regenerate (cached)"
                    : "Generate report"}
                </button>
                <button
                  className="button secondary"
                  disabled={loading}
                  onClick={() => handleGenerate(true)}
                  title="Force regeneration even if cached"
                >
                  Force regenerate
                </button>
                <label
                  className="muted"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 6,
                  }}
                >
                  <input
                    type="checkbox"
                    checked={usePack}
                    onChange={(e) => setUsePack(e.target.checked)}
                  />
                  Restrict to research pack ({pack.length})
                </label>
                {report && (
                  <a
                    className="button secondary"
                    href={reportMarkdownUrl(selected)}
                    target="_blank"
                    rel="noreferrer noopener"
                    download={`${selected}.md`}
                  >
                    Export Markdown
                  </a>
                )}
                {report && (
                  <button
                    className="button secondary"
                    onClick={() => window.print()}
                  >
                    Print / Save PDF
                  </button>
                )}
              </div>

              {error && <div className="error">{error}</div>}

              {report ? (
                <ReportView report={report} />
              ) : (
                <p className="muted">
                  No report generated yet. Click <strong>Generate report</strong>{" "}
                  above.
                </p>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function ReportView({ report }: { report: Report }) {
  return (
    <article className="report-doc">
      <header>
        <h2 style={{ marginBottom: 4 }}>{report.title}</h2>
        <p className="muted">{report.description}</p>
        <p className="muted" style={{ fontSize: 12 }}>
          Generated {new Date(report.generated_at).toLocaleString()}
          {report.usage?.total_tokens
            ? ` · ${report.usage.total_tokens} tokens`
            : ""}
        </p>
      </header>

      <h3>Executive summary</h3>
      <p>{report.executive_summary}</p>

      {report.findings.length > 0 && (
        <>
          <h3>Findings</h3>
          <ul>
            {report.findings.map((f, i) => (
              <li key={i} dangerouslySetInnerHTML={{ __html: linkifyDocs(f) }} />
            ))}
          </ul>
        </>
      )}

      {report.stats && (
        <>
          <h3>Statistics</h3>
          <p>
            <strong>Total records:</strong> {report.stats.total}
          </p>
          <div className="report-stats">
            <StatTable title="By agency" rows={report.stats.by_agency} />
            <StatTable title="By file type" rows={report.stats.by_file_type} />
            <StatTable title="Top locations" rows={report.stats.by_location} />
          </div>
        </>
      )}

      {report.sources.length > 0 && (
        <>
          <h3>Sources ({report.sources.length})</h3>
          <ul className="report-sources">
            {report.sources.map((s) => (
              <li key={s.document_id}>
                <Link to={`/records/${s.document_id}`}>{s.title}</Link>{" "}
                <span className="muted">
                  · {s.agency ?? "Unknown agency"} ·{" "}
                  {s.incident_date ?? "no date"} ·{" "}
                  {s.incident_location ?? "no location"}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}

      {report.caveats.length > 0 && (
        <>
          <h3>Caveats</h3>
          <ul>
            {report.caveats.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </>
      )}
    </article>
  );
}

function StatTable({
  title,
  rows,
}: {
  title: string;
  rows: { value: string; count: number }[];
}) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="report-stat-table">
      <h4>{title}</h4>
      <table>
        <tbody>
          {rows.map((r) => (
            <tr key={r.value}>
              <td>{r.value || "Unknown"}</td>
              <td style={{ textAlign: "right" }}>{r.count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Replace [doc:DOCID] markers with React-Router-style links. */
function linkifyDocs(text: string): string {
  return text.replace(
    /\[doc:([a-z0-9-]+)\]/gi,
    (_m, id) =>
      `<a href="/records/${id}" style="text-decoration:none">[doc:${id.slice(
        0,
        8
      )}]</a>`
  );
}
