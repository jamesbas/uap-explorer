import { Link, NavLink, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import BrowsePage from "./pages/BrowsePage";
import SearchPage from "./pages/SearchPage";
import RecordDetailPage from "./pages/RecordDetailPage";
import AboutPage from "./pages/AboutPage";
import HelpPage from "./pages/HelpPage";
import AskPage from "./pages/AskPage";
import AdminPage from "./pages/AdminPage";
import MediaPage from "./pages/MediaPage";
import MapPage from "./pages/MapPage";
import TimelinePage from "./pages/TimelinePage";
import AnalyticsPage from "./pages/AnalyticsPage";
import { TopicDetailPage, TopicsIndexPage } from "./pages/TopicsPage";
import ReportsPage from "./pages/ReportsPage";
import EntitiesPage from "./pages/EntitiesPage";
import ComparePage from "./pages/ComparePage";
import { isAdmin } from "./services/api";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div>
          <h1>
            <Link to="/" style={{ color: "inherit" }}>
              UAP Explorer
            </Link>
          </h1>
          <div className="subtitle">
            A source-grounded archive of government-released Unidentified Anomalous
            Phenomena records.
          </div>
        </div>
        <nav className="nav">
          <NavLink to="/" end>
            Home
          </NavLink>
          <NavLink to="/browse">Browse</NavLink>
          <NavLink to="/search">Search</NavLink>
          <NavLink to="/ask">Ask</NavLink>
          <NavLink to="/map">Map</NavLink>
          <NavLink to="/timeline">Timeline</NavLink>
          <NavLink to="/media">Media</NavLink>
          <NavLink to="/topics">Topics</NavLink>
          <NavLink to="/analytics">Analytics</NavLink>
          <NavLink to="/entities">Entities</NavLink>
          <NavLink to="/reports">Reports</NavLink>
          <NavLink to="/compare">Compare</NavLink>
          <NavLink to="/help">Help</NavLink>
          <NavLink to="/about">About</NavLink>
          <NavLink to="/admin">{isAdmin() ? "Admin" : "Admin login"}</NavLink>
        </nav>
      </header>

      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/browse" element={<BrowsePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/ask" element={<AskPage />} />
          <Route path="/map" element={<MapPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/media" element={<MediaPage />} />
          <Route path="/entities" element={<EntitiesPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/compare" element={<ComparePage />} />
          <Route path="/topics" element={<TopicsIndexPage />} />
          <Route path="/topics/:slug" element={<TopicDetailPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/records/:id" element={<RecordDetailPage />} />
          <Route path="/help" element={<HelpPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/admin" element={<AdminPage />} />
          <Route
            path="*"
            element={
              <div>
                <h2>Page not found</h2>
                <p>
                  <Link to="/">Return home</Link>
                </p>
              </div>
            }
          />
        </Routes>
      </main>
    </div>
  );
}
