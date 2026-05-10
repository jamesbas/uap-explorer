import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchEntities } from "../services/api";
import type { EntitiesResponse, EntityTypeGroup } from "../types/models";

const TYPE_LABELS: Record<string, string> = {
  agency: "Agencies",
  location: "Locations",
  date: "Dates",
  aircraft: "Aircraft",
  spacecraft: "Spacecraft",
  sensor: "Sensor systems",
  base: "Bases",
  project: "Projects",
  object_shape: "Object descriptions",
  event: "Events",
  person: "People",
};

export default function EntitiesPage() {
  const [data, setData] = useState<EntitiesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [activeType, setActiveType] = useState<string | null>(null);

  useEffect(() => {
    fetchEntities().then(setData).catch((e) => setError(String(e)));
  }, []);

  const visibleTypes: EntityTypeGroup[] = useMemo(() => {
    if (!data) return [];
    return data.types
      .filter((g) => !activeType || g.type === activeType)
      .map((g) => ({
        ...g,
        entities: g.entities.filter((e) =>
          filter ? e.label.toLowerCase().includes(filter.toLowerCase()) : true
        ),
      }))
      .filter((g) => g.entities.length > 0);
  }, [data, filter, activeType]);

  return (
    <div>
      <h2>Entity explorer</h2>
      <p className="muted">
        Entities extracted from the archive metadata. Counts show how many
        records reference each entity. Click an entity to see its records.
      </p>

      {error && <div className="error">{error}</div>}

      <div className="toolbar">
        <input
          className="input"
          placeholder="Filter entities…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <select
          className="select"
          value={activeType ?? ""}
          onChange={(e) => setActiveType(e.target.value || null)}
        >
          <option value="">All types</option>
          {data?.types.map((g) => (
            <option key={g.type} value={g.type}>
              {TYPE_LABELS[g.type] ?? g.type} ({g.entities.length})
            </option>
          ))}
        </select>
      </div>

      {!data ? (
        <p className="muted">Loading entities…</p>
      ) : (
        visibleTypes.map((g) => (
          <section key={g.type} style={{ marginTop: 24 }}>
            <h3>{TYPE_LABELS[g.type] ?? g.type}</h3>
            <ul className="entity-list">
              {g.entities.map((e) => (
                <li key={`${g.type}-${e.canonical}`}>
                  <details>
                    <summary>
                      <span className="entity-label">{e.label}</span>
                      <span className="tag">{e.count}</span>
                    </summary>
                    <ul className="entity-doclist">
                      {e.document_ids.slice(0, 50).map((id) => (
                        <li key={id}>
                          <Link to={`/records/${id}`}>Record {id.slice(0, 8)}</Link>
                        </li>
                      ))}
                      {e.document_ids.length > 50 && (
                        <li className="muted">
                          + {e.document_ids.length - 50} more
                        </li>
                      )}
                    </ul>
                  </details>
                </li>
              ))}
            </ul>
          </section>
        ))
      )}
    </div>
  );
}
