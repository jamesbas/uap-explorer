import { Link } from "react-router-dom";
import type { DocumentRecord } from "../types/models";
import { Unknown } from "./Unknown";

export default function DocumentCard({ doc }: { doc: DocumentRecord }) {
  return (
    <article className="card">
      <h3>
        <Link to={`/records/${doc.document_id}`}>{doc.title}</Link>
      </h3>
      <div className="meta">
        {doc.file_type && <span className="tag">{doc.file_type}</span>}
        <span>
          <strong>Agency:</strong> <Unknown>{doc.agency}</Unknown>
        </span>
        <span>
          <strong>Released:</strong> <Unknown>{doc.release_date}</Unknown>
        </span>
        <span>
          <strong>Incident:</strong> <Unknown>{doc.incident_date}</Unknown>
        </span>
        <span>
          <strong>Location:</strong> <Unknown>{doc.incident_location}</Unknown>
        </span>
      </div>
      {doc.description ? (
        <p className="desc">{doc.description}</p>
      ) : (
        <p className="desc unknown">No description provided.</p>
      )}
      <div className="actions">
        <Link to={`/records/${doc.document_id}`} className="button secondary">
          View details
        </Link>
        {doc.source_url && (
          <a
            href={doc.source_url}
            target="_blank"
            rel="noreferrer noopener"
            className="button secondary"
          >
            Open source
          </a>
        )}
      </div>
    </article>
  );
}
