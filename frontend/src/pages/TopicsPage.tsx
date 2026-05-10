import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import DocumentCard from "../components/DocumentCard";
import {
  fetchTopicDetail,
  fetchTopics,
} from "../services/api";
import type {
  TopicDetailResponse,
  TopicSummary,
} from "../types/models";

export function TopicsIndexPage() {
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTopics()
      .then((r) => setTopics(r.topics))
      .catch((e) => setError(String(e)));
  }, []);

  return (
    <div>
      <h2>Topic pages</h2>
      <p className="muted">
        Curated lenses on the archive. Topic membership is derived by matching
        keywords against record metadata and any AI-generated summaries.
      </p>
      {error && <div className="error">{error}</div>}
      <div className="cards">
        {topics.map((t) => (
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

export function TopicDetailPage() {
  const { slug = "" } = useParams();
  const [data, setData] = useState<TopicDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    fetchTopicDetail(slug)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [slug]);

  if (error) return <div className="error">{error}</div>;
  if (!data) return <p className="muted">Loading…</p>;

  return (
    <div>
      <p className="muted">
        <Link to="/topics">← All topics</Link>
      </p>
      <h2>{data.topic.title}</h2>
      <p className="muted">{data.topic.description}</p>
      <p className="muted">{data.documents.length} matching records.</p>

      {data.documents.length === 0 ? (
        <p className="muted">No matching records.</p>
      ) : (
        <div className="cards">
          {data.documents.map((d) => (
            <DocumentCard key={d.document_id} doc={d} />
          ))}
        </div>
      )}
    </div>
  );
}
