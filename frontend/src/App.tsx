import type { ReactNode } from "react";
import { BrowserRouter, Link, Navigate, Route, Routes } from "react-router-dom";
import { useLocale } from "./hooks/useLocale";
import { AssessmentProvider, useAssessment } from "./hooks/useAssessment";
import { WelcomePage } from "./pages/WelcomePage";
import { FarmDetailsPage } from "./pages/FarmDetailsPage";
import { PhotoUploadPage } from "./pages/PhotoUploadPage";
import { AnalysisProgressPage } from "./pages/AnalysisProgressPage";
import { ResultsPage } from "./pages/ResultsPage";
import { FollowupPage } from "./pages/FollowupPage";

/** Route guard: assessment session required, else back to the form. */
function RequireAssessment({ children }: { children: ReactNode }) {
  const { assessment } = useAssessment();
  if (!assessment) {
    return <Navigate to="/farm-details" replace />;
  }
  return <>{children}</>;
}

export default function App() {
  const { locale, setLocale } = useLocale();

  return (
    <BrowserRouter>
      <AssessmentProvider>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <div className="app-shell">
          <header className="app-header">
            <Link to="/" className="app-brand">
              <img src="/icon.svg" alt="" width={28} height={28} />
              KisanOS
            </Link>
            <div className="locale-toggle" role="group" aria-label="Language">
              <button
                type="button"
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
          </header>

          <main id="main" className="app-main">
            <Routes>
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
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>

          <footer className="app-footer">
            KisanOS · Bahawalpur wheat pilot — screening support only, not a
            confirmed diagnosis.
          </footer>
        </div>
      </AssessmentProvider>
    </BrowserRouter>
  );
}
