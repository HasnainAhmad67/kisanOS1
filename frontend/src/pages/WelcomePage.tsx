import { useEffect, useRef } from "react";
import { LinkButton } from "../components/Button";
import { Card } from "../components/Card";
import { WheatEar } from "../components/WheatEar";
import { useConfig } from "../hooks/useConfig";
import { translate, useI18n } from "../i18n";

export function WelcomePage() {
  const { t, locale } = useI18n();
  const { config, error, loading } = useConfig();
  const heroRef = useRef<HTMLElement>(null);

  // Cinematic hero: subtle scroll parallax + pointer tilt (illustration layer
  // only — copy stays flat for readability). Skipped for reduced-motion.
  useEffect(() => {
    const hero = heroRef.current;
    if (!hero) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      return;
    }
    let raf = 0;
    const onScroll = () => {
      if (raf) return;
      raf = window.requestAnimationFrame(() => {
        const y = Math.min(window.scrollY, hero.offsetHeight);
        hero.style.setProperty("--parallax-y", `${(y * 0.18).toFixed(1)}px`);
        raf = 0;
      });
    };
    const onMove = (e: PointerEvent) => {
      const r = hero.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width - 0.5;
      const py = (e.clientY - r.top) / r.height - 0.5;
      hero.style.setProperty("--tilt-x", `${(-py * 2.4).toFixed(2)}deg`);
      hero.style.setProperty("--tilt-y", `${(px * 3).toFixed(2)}deg`);
    };
    const resetTilt = () => {
      hero.style.setProperty("--tilt-x", "0deg");
      hero.style.setProperty("--tilt-y", "0deg");
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    hero.addEventListener("pointermove", onMove);
    hero.addEventListener("pointerleave", resetTilt);
    return () => {
      window.removeEventListener("scroll", onScroll);
      hero.removeEventListener("pointermove", onMove);
      hero.removeEventListener("pointerleave", resetTilt);
      if (raf) window.cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div className="page page--welcome stack">
      {/* Cinematic hero: real wheat-field photography + glass copy */}
      <section className="hero hero--cinematic" ref={heroRef}>
        <div className="hero__bg" aria-hidden="true">
          <img
            src="/images/hero-wheat-field.jpg"
            alt=""
            decoding="async"
          />
        </div>
        <div className="hero__scrim" aria-hidden="true" />
        <WheatEar className="wheat-float wheat-float--1" />
        <WheatEar className="wheat-float wheat-float--2" />
        <WheatEar className="wheat-float wheat-float--3" />
        <div className="hero__copy">
          <p className="hero__greeting">{t("welcome.greeting")}</p>
          <h1 className="hero__title">
            {t("welcome.title")}
            {locale === "ur" ? (
              <span className="label-en" dir="ltr">
                {translate("en", "welcome.title")}
              </span>
            ) : null}
          </h1>
          <div className="hero__glass">
            <p className="hero__tagline">{t("welcome.tagline")}</p>
          </div>
          <div className="hero__cta">
            <LinkButton to="/farm-details">{t("welcome.cta")}</LinkButton>
          </div>
        </div>
      </section>

      <p className="page-intro">{t("welcome.intro")}</p>

      <Card title={t("welcome.howTitle")}>
        <div id="how-it-works">
          <ol className="agent-card__list how-list">
            <li>{t("welcome.how1")}</li>
            <li>{t("welcome.how2")}</li>
            <li>{t("welcome.how3")}</li>
          </ol>
        </div>
      </Card>

      <Card tone="safety" title={t("welcome.safetyTitle")}>
        {config ? (
          <p style={{ margin: 0 }} dir="auto">
            {config.safety_notice}
          </p>
        ) : loading ? (
          <p className="empty-note">{t("welcome.configLoading")}</p>
        ) : (
          <p className="empty-note">
            {t("welcome.configUnavailable")}
            {error ? ` (${error})` : ""}.
          </p>
        )}
      </Card>

      {config ? (
        <p className="card__meta">
          {t("welcome.crop")} {config.supported_crop} · {t("welcome.areas")}{" "}
          {config.supported_areas.map((area) => area.name).join(", ")}
        </p>
      ) : null}

      <div className="row">
        <LinkButton to="/farm-details" block>
          {t("welcome.cta")}
        </LinkButton>
      </div>
    </div>
  );
}
