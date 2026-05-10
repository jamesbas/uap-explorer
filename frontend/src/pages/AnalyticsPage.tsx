import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchAnalytics } from "../services/api";
import type {
  AnalyticsBucket,
  AnalyticsResponse,
} from "../types/models";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <p className="muted">Loading analytics…</p>;

  const m = data.media_summary;

  return (
    <div>
      <h2>Analytics dashboard</h2>
      <p className="muted">
        Counts and groupings derived from the raw archive metadata. These are
        record-counting statistics, not interpretive findings.
      </p>

      <div className="stats-grid">
        <Stat label="Total records" value={data.total_records} />
        <Stat label="With image" value={m.with_image} />
        <Stat label="With video" value={m.with_video} />
        <Stat label="Unknown date" value={m.unknown_dates} />
        <Stat label="Unknown location" value={m.unknown_locations} />
      </div>

      <div className="analytics-grid">
        <BarPanel title="Records by agency" data={data.by_agency} />
        <BarPanel title="Records by file type" data={data.by_file_type} />
        <BarPanel title="Records by incident decade" data={data.by_incident_decade} />
        <BarPanel title="Records by release year" data={data.by_release_year} />
        <BarPanel title="Records by location" data={data.by_location.slice(0, 12)} />
        <BarPanel title="Location precision" data={data.location_confidence} />
        <BarPanel title="Redaction level" data={data.by_redaction} />
      </div>

      <h3 style={{ marginTop: 32 }}>Topic distribution</h3>
      <div className="cards">
        {data.topics.map((t) => (
          <Link
            key={t.slug}
            to={`/topics/${t.slug}`}
            className="card"
            style={{ textDecoration: "none" }}
          >
            <h3 style={{ color: "var(--accent)" }}>{t.title}</h3>
            <p className="desc">{t.description}</p>
            <div className="meta">
              <span className="tag">{t.count} records</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}

function BarPanel({ title, data }: { title: string; data: AnalyticsBucket[] }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  return (
    <section className="bar-panel">
      <h3>{title}</h3>
      {data.length === 0 ? (
        <p className="muted">No data.</p>
      ) : (
        <ul className="bar-list">
          {data.map((d) => (
            <li key={d.value}>
              <span className="bar-label">{d.value || "Unknown"}</span>
              <span className="bar-track">
                <span
                  className="bar-fill"
                  style={{ width: `${(d.count / max) * 100}%` }}
                />
              </span>
              <span className="bar-count">{d.count}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
