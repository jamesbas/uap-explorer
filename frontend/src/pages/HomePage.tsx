import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchStats } from "../services/api";
import type { StatsResponse } from "../types/models";
import DonateBlock from "../components/DonateBlock";

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
            <Link to="/help" className="button secondary">
              How to use this site
            </Link>
          </div>

          <section className="ask-cta">
            <div className="ask-cta-body">
              <span className="ask-cta-badge">AI · Grounded Q&amp;A</span>
              <h2 className="ask-cta-title">Ask the archive a question</h2>
              <p className="ask-cta-text">
                Try natural language. <em>"Which UAP incidents involved the Navy
                in the 1950s?"</em> <em>"Show me cases reported over Oak Ridge."</em>{" "}
                The app retrieves matching records from the indexed archive and
                writes a citation-backed answer that links straight back to the
                source PDFs. No speculation — just what the released documents
                actually say.
              </p>
              <Link to="/ask" className="button ask-cta-button">
                Ask a question →
              </Link>
            </div>
          </section>

          <DonateBlock />
        </>
      )}
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
