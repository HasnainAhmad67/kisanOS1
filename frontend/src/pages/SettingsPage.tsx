import { Alert } from "../components/Alert";
import { Card } from "../components/Card";
import { useConfig } from "../hooks/useConfig";
import { translate, useI18n } from "../i18n";

/**
 * Settings — language toggle plus honest runtime information read live
 * from GET /config (no fabricated values).
 */
export function SettingsPage() {
  const { t, locale, setLocale } = useI18n();
  const { config, error, loading } = useConfig();

  return (
    <div className="page page--settings stack">
      <h1 className="page-title">
        {t("set.title")}
        {locale === "ur" ? (
          <span className="label-en" dir="ltr">
            {translate("en", "set.title")}
          </span>
        ) : null}
      </h1>
      <p className="page-intro">{t("set.intro")}</p>

      <Card title={t("set.language")}>
        <div className="locale-toggle locale-toggle--lg" role="group" aria-label={t("app.langLabel")}>
          <button
            type="button"
            lang="en"
            aria-pressed={locale === "en"}
            onClick={() => setLocale("en")}
          >
            English
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
      </Card>

      <Card tone="safety" title={t("set.safetyTitle")}>
        {config ? (
          <p style={{ margin: 0 }} dir="auto">
            {config.safety_notice}
          </p>
        ) : loading ? (
          <p className="empty-note">{t("welcome.configLoading")}</p>
        ) : (
          <Alert>
            {t("welcome.configUnavailable")}
            {error ? ` (${error})` : ""}.
          </Alert>
        )}
      </Card>

      <Card title={t("set.aboutTitle")}>
        {config ? (
          <dl className="meta-list">
            <div>
              <dt>{t("set.retention")}</dt>
              <dd className="num">
                {config.retention_hours} {t("set.hours")}
              </dd>
            </div>
            <div>
              <dt>{t("set.visionMode")}</dt>
              <dd className="num">{config.vision_mode}</dd>
            </div>
            <div>
              <dt>{t("set.policy")}</dt>
              <dd className="num">{config.policy_version}</dd>
            </div>
            <div>
              <dt>{t("set.api")}</dt>
              <dd className="num">{config.api_version}</dd>
            </div>
            <div>
              <dt>{t("welcome.crop")}</dt>
              <dd>{config.supported_crop}</dd>
            </div>
          </dl>
        ) : loading ? (
          <p className="empty-note">{t("welcome.configLoading")}</p>
        ) : (
          <p className="empty-note">
            {t("welcome.configUnavailable")}
            {error ? ` (${error})` : ""}.
          </p>
        )}
      </Card>
    </div>
  );
}
