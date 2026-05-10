import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchMedia } from "../services/api";
import type { MediaItem } from "../types/models";
import { Unknown } from "../components/Unknown";

type Filter = "" | "image" | "video";

export default function MediaPage() {
  const [items, setItems] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("");

  useEffect(() => {
    setLoading(true);
    fetchMedia(filter ? { media_type: filter } : {})
      .then((r) => {
        setItems(r.items);
        setError(null);
      })
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [filter]);

  const counts = useMemo(() => {
    const c = { image: 0, video: 0 };
    items.forEach((i) => {
      c[i.media_type] = (c[i.media_type] ?? 0) + 1;
    });
    return c;
  }, [items]);

  return (
    <div>
      <h2>Media gallery</h2>
      <p className="muted">
        Visual evidence linked to source records: photographs and DVIDS video
        cards. Captions are taken directly from the released metadata.
      </p>

      <div className="toolbar">
        <button
          className={`button ${filter === "" ? "" : "secondary"}`}
          onClick={() => setFilter("")}
        >
          All ({items.length})
        </button>
        <button
          className={`button ${filter === "image" ? "" : "secondary"}`}
          onClick={() => setFilter("image")}
        >
          Images ({counts.image})
        </button>
        <button
          className={`button ${filter === "video" ? "" : "secondary"}`}
          onClick={() => setFilter("video")}
        >
          Videos ({counts.video})
        </button>
      </div>

      {error && <div className="error">{error}</div>}
      {loading ? (
        <p className="muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="muted">No media items match this filter.</p>
      ) : (
        <div className="media-grid">
          {items.map((m) => (
            <MediaCard key={m.media_id} item={m} />
          ))}
        </div>
      )}
    </div>
  );
}

function MediaCard({ item }: { item: MediaItem }) {
  const dvidsLink = item.dvids_video_id
    ? `https://www.dvidshub.net/video/${item.dvids_video_id}`
    : null;
  return (
    <article className="media-card">
      <div className="media-thumb">
        {item.thumbnail_url ? (
          <img
            src={item.thumbnail_url}
            alt={item.title}
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="media-placeholder">
            {item.media_type === "video" ? "▶" : "🖼"}
          </div>
        )}
        <span className={`media-badge ${item.media_type}`}>
          {item.media_type}
        </span>
      </div>
      <div className="media-body">
        <h3>
          <Link to={`/records/${item.document_id}`}>{item.title}</Link>
        </h3>
        <div className="meta">
          <span>
            <strong>Agency:</strong> <Unknown>{item.agency}</Unknown>
          </span>
          <span>
            <strong>Date:</strong> <Unknown>{item.incident_date}</Unknown>
          </span>
          <span>
            <strong>Location:</strong> <Unknown>{item.incident_location}</Unknown>
          </span>
        </div>
        {item.caption && <p className="desc">{item.caption}</p>}
        <div className="actions">
          <Link
            to={`/records/${item.document_id}`}
            className="button secondary"
          >
            View record
          </Link>
          {dvidsLink && (
            <a
              href={dvidsLink}
              target="_blank"
              rel="noreferrer noopener"
              className="button secondary"
            >
              Open on DVIDS
            </a>
          )}
          {item.source_url && !dvidsLink && (
            <a
              href={item.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="button secondary"
            >
              Open source
            </a>
          )}
        </div>
      </div>
    </article>
  );
}
