import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchTimeline } from "../services/api";
import type { TimelineEntry, TimelineResponse } from "../types/models";

type View = "incident" | "release";

function yearOf(date: string): string {
  const m = date.match(/\b(19|20)\d{2}\b/);
  return m ? m[0] : "Unknown";
}

function decadeOf(year: string): string {
  if (year === "Unknown") return "Unknown";
  return `${year.substring(0, 3)}0s`;
}

export default function TimelinePage() {
  const [data, setData] = useState<TimelineResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("incident");

  useEffect(() => {
    fetchTimeline().then(setData).catch((e) => setError(String(e)));
  }, []);

  const entries = view === "incident" ? data?.incident_timeline : data?.release_timeline;

  const grouped = useMemo(() => {
    if (!entries) return [] as { decade: string; year: string; items: TimelineEntry[] }[];
    const map = new Map<string, TimelineEntry[]>();
    entries.forEach((e) => {
      const y = yearOf(e.date);
      const arr = map.get(y) ?? [];
      arr.push(e);
      map.set(y, arr);
    });
    return Array.from(map.entries())
      .sort(([a], [b]) => (a === "Unknown" ? 1 : b === "Unknown" ? -1 : a.localeCompare(b)))
      .map(([year, items]) => ({ year, decade: decadeOf(year), items }));
  }, [entries]);

  return (
    <div>
      <h2>Timeline</h2>
      <p className="muted">
        Two views of the archive: when the incidents reportedly happened, and
        when the records were released to the public.
      </p>

      <div className="toolbar">
        <button
          className={`button ${view === "incident" ? "" : "secondary"}`}
          onClick={() => setView("incident")}
        >
          Incident timeline ({data?.incident_timeline.length ?? 0})
        </button>
        <button
          className={`button ${view === "release" ? "" : "secondary"}`}
          onClick={() => setView("release")}
        >
          Release timeline ({data?.release_timeline.length ?? 0})
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {!data ? (
        <p className="muted">Loading…</p>
      ) : (
        <div className="timeline">
          {grouped.map((g) => (
            <section key={g.year} className="timeline-year">
              <header>
                <span className="timeline-year-label">{g.year}</span>
                <span className="muted"> · {g.items.length} record{g.items.length === 1 ? "" : "s"}</span>
              </header>
              <ul className="timeline-list">
                {g.items.map((e) => (
                  <li key={`${e.document_id}-${e.date}`}>
                    <span className="timeline-date">{e.date}</span>
                    <Link to={`/records/${e.document_id}`}>{e.title}</Link>
                    <span className="muted">
                      {" "}— {e.agency ?? "Unknown agency"}
                      {e.incident_location ? ` · ${e.incident_location}` : ""}
                      {e.file_type ? ` · ${e.file_type}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
