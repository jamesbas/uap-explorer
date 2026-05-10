import { Link } from "react-router-dom";

export default function HelpPage() {
  return (
    <div className="help-page">
      <h2>How to use UAP Explorer</h2>
      <p className="muted">
        UAP Explorer is a research portal for government-released Unidentified
        Anomalous Phenomena records. Everything you see is grounded in the
        original documents and links back to the source.
      </p>

      <h3>The basics</h3>
      <ul>
        <li>
          <strong>Home</strong> – overview counts for the archive (records by
          file type, agencies, location coverage, release date range).
        </li>
        <li>
          <strong>Browse</strong> – paginated list of every record with filters
          for agency, file type, location, and release date.
        </li>
        <li>
          <strong>Search</strong> – keyword search across record metadata
          (title, description, video title, etc.).
        </li>
        <li>
          <strong>Record detail</strong> – click any record to see its
          metadata, original-source link, AI summary, evidence quality score,
          and a button to add it to your <em>research pack</em>.
        </li>
      </ul>

      <h3>Asking questions (Ask)</h3>
      <p>
        The <Link to="/ask">Ask</Link> page is grounded Q&amp;A backed by Azure
        AI Search and Azure OpenAI. Type a question and the system retrieves
        the most relevant document chunks, asks GPT to answer using only that
        evidence, and returns the answer with <code>[doc:ID]</code> citations
        you can click through to the source. Every answer also includes
        suggested follow-up questions.
      </p>
      <p>
        Try things like <em>"What does the FBI archive say about the Roswell
        incident?"</em> or <em>"Summarize radar-related encounters."</em>
      </p>

      <h3>Visual exploration</h3>
      <ul>
        <li>
          <strong><Link to="/map">Map</Link></strong> – Leaflet markers for
          geocoded incident locations. Marker color reflects the location
          confidence tier (exact / approximate / broad / off-earth / unknown).
        </li>
        <li>
          <strong><Link to="/timeline">Timeline</Link></strong> – histogram of
          records bucketed by decade, with a count of records that have no
          known incident date.
        </li>
        <li>
          <strong><Link to="/media">Media</Link></strong> – gallery of the
          images and DVIDS videos in the archive.
        </li>
        <li>
          <strong><Link to="/topics">Topics</Link></strong> – curated lenses
          (e.g. <em>Radar cases</em>, <em>Modern military sensor</em>,{" "}
          <em>Historical FBI</em>). Click a topic to see the records that fit.
        </li>
        <li>
          <strong><Link to="/analytics">Analytics</Link></strong> – breakdowns
          by agency, file type, location, decade, redaction level, and
          location-confidence.
        </li>
      </ul>

      <h3>Entities, reports, and compare</h3>
      <ul>
        <li>
          <strong><Link to="/entities">Entities</Link></strong> – every agency,
          location, date, aircraft, spacecraft, sensor, base, project, object
          shape, and event mentioned in the archive, with counts and links to
          the records that reference each one.
        </li>
        <li>
          <strong><Link to="/reports">Reports</Link></strong> – pick one of
          eight prebuilt templates (e.g. <em>Best Documented Cases</em>,{" "}
          <em>Radar-related Reports</em>) and click <strong>Generate</strong>.
          The model writes an executive summary, findings with{" "}
          <code>[doc:ID]</code> citations, statistics, and a sources list.
          Each report can be downloaded as Markdown or printed/saved to PDF.
        </li>
        <li>
          <strong><Link to="/compare">Compare</Link></strong> – side-by-side
          view of any records you've added to your research pack, with
          metadata, AI summaries, and evidence-score dimensions aligned in a
          grid.
        </li>
      </ul>

      <h3>The research pack</h3>
      <p>
        On any record page, click <strong>Add to research pack</strong> to
        save it. The pack is stored in your browser's local storage (no
        account required). When you have at least two records in the pack,
        the <Link to="/compare">Compare</Link> page renders them side by
        side. You can also tell the <Link to="/reports">Reports</Link> page
        to restrict generation to just the records in your pack.
      </p>

      <h3>Evidence quality score</h3>
      <p>
        Every record gets a deterministic 0–10 score across eight dimensions:
        date quality, location quality, source quality, media support,
        witness support, redaction level, corroboration, and resolution.
        It's shown on each record's detail page and in the Compare view.
      </p>
      <div className="callout">
        <strong>Important neutrality note:</strong> the score reflects{" "}
        <em>record completeness only</em>. It is <strong>not</strong> a
        measure of whether an event was extraterrestrial. UAP Explorer makes
        no claims about the nature or origin of any record in the archive.
      </div>

      <h3>Citations</h3>
      <p>
        Anywhere you see a <code>[doc:abc123…]</code> marker — in an Ask
        answer or a generated report — it's a clickable link to the
        underlying record's detail page. From there you can open the
        original government PDF or image. UAP Explorer never makes a claim
        without showing you the source.
      </p>

      <h3>Admin</h3>
      <p>
        The <Link to="/admin">Admin</Link> page is password-protected and
        only used to run ingestion and manage the AI Search index. End users
        do not need to touch it.
      </p>

      <h3>Tips</h3>
      <ul>
        <li>
          Use <strong>Browse</strong> for structured filtering;{" "}
          <strong>Search</strong> for free-text keywords;{" "}
          <strong>Ask</strong> for natural-language questions.
        </li>
        <li>
          Reports are cached after generation. Re-opening the same template
          loads instantly. Use <strong>Force regenerate</strong> if you want
          a fresh draft.
        </li>
        <li>
          <strong>Print / Save PDF</strong> on a report or compare view uses
          your browser's print dialog with a clean black-on-white stylesheet.
        </li>
      </ul>
    </div>
  );
}
