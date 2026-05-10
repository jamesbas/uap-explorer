import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchMap } from "../services/api";
import type { MapMarker, MapResponse } from "../types/models";

const CONFIDENCE_COLORS: Record<string, string> = {
  exact: "#2ecc71",
  approximate: "#4493f8",
  broad: "#d29922",
  "off-earth": "#a371f7",
  unknown: "#8b98a5",
};

const CONFIDENCE_LABELS: Record<string, string> = {
  exact: "Exact (specific place)",
  approximate: "Approximate (state or region)",
  broad: "Broad (country or area)",
  "off-earth": "Off-Earth (Moon / orbit)",
  unknown: "Unknown",
};

export default function MapPage() {
  const [data, setData] = useState<MapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMap().then(setData).catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <h2>Incident map</h2>
      <p className="muted">
        Records grouped by reported incident location. Marker size scales with
        the number of records and color reflects how precisely the location is
        known.
      </p>

      <div className="legend">
        {Object.entries(CONFIDENCE_LABELS).map(([k, label]) => (
          <span key={k} className="legend-item">
            <span
              className="legend-dot"
              style={{ background: CONFIDENCE_COLORS[k] }}
            />
            {label}
          </span>
        ))}
      </div>

      {error && <div className="error">{error}</div>}

      <div className="map-wrap">
        <MapContainer
          center={[25, 30]}
          zoom={2}
          minZoom={2}
          worldCopyJump
          style={{ height: "520px", width: "100%", borderRadius: 8 }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {(data?.markers ?? []).map((m) => (
            <MarkerCircle key={m.location} marker={m} />
          ))}
        </MapContainer>
      </div>

      {data && (
        <div className="map-summary">
          <p className="muted">
            Mapped: {data.markers.reduce((a, m) => a + m.count, 0)} records across{" "}
            {data.markers.length} locations. Unmapped: {data.unmapped_count} records
            {data.unmapped.length > 0 ? ` (${data.unmapped.join(", ")})` : ""}.
          </p>
        </div>
      )}
    </div>
  );
}

function MarkerCircle({ marker }: { marker: MapMarker }) {
  const radius = 6 + Math.min(20, Math.sqrt(marker.count) * 4);
  const color = CONFIDENCE_COLORS[marker.confidence] ?? CONFIDENCE_COLORS.unknown;
  return (
    <CircleMarker
      center={[marker.lat, marker.lon]}
      radius={radius}
      pathOptions={{ color, fillColor: color, fillOpacity: 0.55, weight: 1 }}
    >
      <Popup>
        <strong>{marker.label}</strong>
        <br />
        {marker.count} record{marker.count === 1 ? "" : "s"} · {marker.confidence}
        <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
          {marker.document_ids.slice(0, 8).map((id) => (
            <li key={id}>
              <Link to={`/records/${id}`}>Open record</Link>
            </li>
          ))}
          {marker.document_ids.length > 8 && (
            <li className="muted">
              + {marker.document_ids.length - 8} more
            </li>
          )}
        </ul>
      </Popup>
    </CircleMarker>
  );
}
