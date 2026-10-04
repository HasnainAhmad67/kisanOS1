import type { ReactNode } from "react";
import {
  BrowserRouter,
  Link,
  Navigate,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { I18nProvider, useI18n } from "./i18n";
import { AssessmentProvider, useAssessment } from "./hooks/useAssessment";
import { Nav } from "./components/Nav";
import { WelcomePage } from "./pages/WelcomePage";
import { FarmDetailsPage } from "./pages/FarmDetailsPage";
import { PhotoUploadPage } from "./pages/PhotoUploadPage";
import { AnalysisProgressPage } from "./pages/AnalysisProgressPage";
import { ResultsPage } from "./pages/ResultsPage";
import { FollowupPage } from "./pages/FollowupPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TeamPage } from "./pages/TeamPage";

/** Route guard: assessment session required, else back to the form. */
function RequireAssessment({ children }: { children: ReactNode }) {
  const { assessment } = useAssessment();
  if (!assessment) {
    return <Navigate to="/farm-details" replace />;
  }
  return <>{children}</>;
}

function LocaleToggle() {
  const { locale, setLocale, t } = useI18n();
  return (
    <div className="locale-toggle" role="group" aria-label={t("app.langLabel")}>
      <button
        type="button"
        lang="en"
        aria-pressed={locale === "en"}
        onClick={() => setLocale("en")}
      >
        EN
      </button>
      <button
        type="button"
        lang="ur"
        aria-pressed={locale === "ur"}
        onClick={() => setLocale("ur")}
      >
        اردو
      </button>
    </div>
  );
}

function Shell() {
  const { t } = useI18n();
  const location = useLocation();

  return (
    <>
      <a className="skip-link" href="#main">
        {t("app.skip")}
      </a>
      <div className="app-shell">
        <header className="app-header glass">
          <Link to="/" className="app-brand">
            <img src="/icon.svg" alt="" width={28} height={28} />
            KisanOS
          </Link>
          <LocaleToggle />
        </header>

        <Nav />

        <main id="main" className="app-main">
          {/* CSS route transition: subtle fade + slide, keyed per path */}
          <div key={location.pathname} className="page-enter">
            <Routes location={location}>
              <Route path="/" element={<WelcomePage />} />
              <Route path="/farm-details" element={<FarmDetailsPage />} />
              <Route
                path="/photos"
                element={
                  <RequireAssessment>
                    <PhotoUploadPage />
                  </RequireAssessment>
                }
              />
              <Route
                path="/analysis"
                element={
                  <RequireAssessment>
                    <AnalysisProgressPage />
                  </RequireAssessment>
                }
              />
              <Route
                path="/results"
                element={
                  <RequireAssessment>
                    <ResultsPage />
                  </RequireAssessment>
                }
              />
              <Route
                path="/followup"
                element={
                  <RequireAssessment>
                    <FollowupPage />
                  </RequireAssessment>
                }
              />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/team" element={<TeamPage />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </div>
        </main>

        <footer className="app-footer">{t("app.footer")}</footer>
      </div>
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <I18nProvider>
        <AssessmentProvider>
          <Shell />
        </AssessmentProvider>
      </I18nProvider>
    </BrowserRouter>
  );
}
