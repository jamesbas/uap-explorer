import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStats } from "../services/api";
import type { StatsResponse } from "../types/models";

export default function HomePage() {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchStats().then(setStats).catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <h2>Archive overview</h2>
      <p className="muted">
        Browse, search, and review government-released UAP records from the public
        archive. All records link to their original source files.
      </p>

      {error && <div className="error">{error}</div>}

      {stats && (
        <>
          <div className="stats-grid">
            <StatCard label="Total records" value={stats.total_records} />
            <StatCard label="PDFs" value={stats.pdfs} />
            <StatCard label="Images" value={stats.images} />
            <StatCard label="Videos" value={stats.videos} />
            <StatCard label="Agencies" value={stats.agencies} />
            <StatCard label="Known locations" value={stats.known_locations} />
            <StatCard label="Known incident dates" value={stats.known_incident_dates} />
            <StatCard
              label="Release date range"
              value={
                stats.release_date_min
                  ? `${stats.release_date_min} – ${stats.release_date_max}`
                  : "Unknown"
              }
            />
          </div>

          <div className="toolbar">
            <Link to="/browse" className="button">
              Browse all records
            </Link>
            <Link to="/search" className="button secondary">
              Search the archive
            </Link>
          </div>
        </>
      )}

      <div className="placeholder-box">
        <strong>Coming soon:</strong> AI-grounded Q&amp;A (Phase 2), maps and timelines
        (Phase 3), and citation-backed reports (Phase 4).
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="stat-card">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
    </div>
  );
}
