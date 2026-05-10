import DonateBlock from "../components/DonateBlock";

export default function AboutPage() {
  return (
    <div>
      <h2>About UAP Explorer</h2>
      <p>
        <strong>UAP Explorer</strong> is a source-grounded research portal for
        government-released records on{" "}
        <em>Unidentified Anomalous Phenomena (UAP)</em>. It pairs the original
        documents with modern search, visualization, and AI so you can actually
        explore the archive instead of just downloading PDFs from it.
      </p>

      <h3>Why this exists</h3>
      <p>
        I built this because the possibility of life beyond Earth is genuinely
        fascinating to me — and because the public release of the underlying
        records, while a real step forward, stops at "here are the files."
        There's no way to ask a question, cross-reference incidents, see where
        sightings clustered, or get a citation-backed summary across hundreds
        of pages. UAP Explorer fills that gap: it indexes every released
        document, lets you ask natural-language questions, and grounds every AI
        answer in links back to the source pages so nothing is taken on faith.
      </p>

      <h3>What you can do here</h3>
      <ul>
        <li>
          <strong>Browse and search</strong> the full archive of released
          records, with every file linking back to its original source.
        </li>
        <li>
          <strong>Ask the archive in plain English</strong> — "What happened
          over Oak Ridge in the late 1940s?" — and get a citation-backed answer
          drawn from the indexed documents.
        </li>
        <li>
          <strong>Visualize the data</strong> on maps, timelines, topic
          clusters, and analytics charts.
        </li>
        <li>
          <strong>Generate research reports</strong> on themes like sightings
          by location or best-documented cases — each finding cites the
          underlying records.
        </li>
        <li>
          <strong>Compare records side-by-side</strong>, build a personal
          research pack, and export findings as Markdown or PDF.
        </li>
      </ul>

      <h3>What this is not</h3>
      <ul>
        <li>This site does not claim that UAP are extraterrestrial.</li>
        <li>
          It does not speculate beyond what the released documents actually
          say. AI summaries are deliberately neutral and always cite their
          sources.
        </li>
        <li>
          Missing data is shown as <em>Unknown</em> or <em>Not available</em>{" "}
          rather than guessed at.
        </li>
      </ul>

      <h3>How it's built</h3>
      <p className="muted">
        FastAPI + Python on the backend, React + TypeScript on the frontend,
        with Azure AI Search (hybrid keyword + vector retrieval), Azure
        OpenAI for embeddings and answer synthesis, Azure Document Intelligence
        for PDF text extraction, and Azure Blob Storage for the originals.
        The whole thing runs on Azure Container Apps and is open-source on{" "}
        <a
          href="https://github.com/jamesbas/uap-explorer"
          target="_blank"
          rel="noreferrer noopener"
        >
          GitHub
        </a>
        .
      </p>

      <DonateBlock />
    </div>
  );
}
