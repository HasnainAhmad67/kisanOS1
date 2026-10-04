import { useState, type CSSProperties } from "react";
import { useI18n, type DictKey } from "../i18n";

type Member = {
  id: string;
  name: string;
  photo: string;
  accent: string;
  linkedin?: string;
  descKey: DictKey;
  pills: DictKey[];
};

const LEADER_PILLS: DictKey[] = [
  "team.pill.ai",
  "team.pill.fullstack",
  "team.pill.backend",
  "team.pill.frontend",
  "team.pill.deployment",
  "team.pill.workflow",
];

const MEMBERS: Member[] = [
  {
    id: "sharjeel",
    name: "Muhammad Sharjeel",
    photo: "/images/team/muhammad-sharjeel.png",
    accent: "#5B9BD5",
    linkedin: "https://www.linkedin.com/in/sharjeel-sarwar-a18414327",
    descKey: "team.desc.sharjeel",
    pills: ["team.pill.research", "team.pill.coordination", "team.pill.water"],
  },
  {
    id: "minahil",
    name: "Minahil Saleem",
    photo: "/images/team/minahil-saleem.png",
    accent: "#86C5EA",
    linkedin: "https://www.linkedin.com/in/minahil-saleemmm",
    descKey: "team.desc.minahil",
    pills: [
      "team.pill.research",
      "team.pill.coordination",
      "team.pill.weather",
      "team.pill.slides",
    ],
  },
  {
    id: "laraib",
    name: "Laraib Khan",
    photo: "/images/team/laraib-khan.png",
    accent: "#4CAF7D",
    descKey: "team.desc.laraib",
    pills: [
      "team.pill.research",
      "team.pill.coordination",
      "team.pill.crop",
      "team.pill.docs",
    ],
  },
  {
    id: "ghulam",
    name: "Ghulam Ahmed",
    photo: "/images/team/ghulam-ahmed.png",
    accent: "#A78BFA",
    descKey: "team.desc.ghulam",
    pills: ["team.pill.research", "team.pill.coordination", "team.pill.vision"],
  },
  {
    id: "durdana",
    name: "Durdana Rehman",
    photo: "/images/team/durdana-rehman.png",
    accent: "#E8B84B",
    descKey: "team.desc.durdana",
    pills: ["team.pill.research", "team.pill.coordination", "team.pill.market"],
  },
];

/** Photo with graceful initials fallback if the asset ever fails to load. */
function Avatar({
  src,
  name,
  className,
}: {
  src: string;
  name: string;
  className: string;
}) {
  const [ok, setOk] = useState(true);
  if (!ok) {
    const initials = name
      .split(" ")
      .map((w) => w.charAt(0))
      .slice(0, 2)
      .join("");
    return (
      <span
        className={`${className} team-avatar--fallback`}
        aria-hidden="true"
        dir="ltr"
      >
        {initials}
      </span>
    );
  }
  return (
    <img
      className={className}
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setOk(false)}
    />
  );
}

function LinkedInLink({
  href,
  label,
}: {
  href: string;
  label: string;
}) {
  return (
    <a
      className="btn btn--secondary team-link"
      href={href}
      target="_blank"
      rel="noreferrer"
    >
      {label}
    </a>
  );
}

export function TeamPage() {
  const { t } = useI18n();

  return (
    <div className="page page--team stack">
      {/* Hero: subtle wheat-field photography behind the heading */}
      <section className="team-hero">
        <img
          className="team-hero__bg"
          src="/images/hero-wheat-field.jpg"
          alt=""
          loading="lazy"
          decoding="async"
        />
        <span className="team-hero__scrim" aria-hidden="true" />
        <div className="team-hero__copy">
          <h1 className="page-title team-hero__title">{t("team.title")}</h1>
          <p className="team-hero__tag">{t("team.tagline")}</p>
        </div>
      </section>

      {/* Featured leader — premium gradient-border card */}
      <article
        className="team-leader"
        style={{ "--accent": "#4CAF7D" } as CSSProperties}
      >
        <div className="team-leader__photo">
          <Avatar
            src="/images/team/hasnain-ahmad.png"
            name="Hasnain Ahmad"
            className="team-avatar team-avatar--leader"
          />
          <span className="team-gold-badge">{t("team.leader")}</span>
        </div>
        <div className="team-leader__body">
          <h2 className="team-name">Hasnain Ahmad</h2>
          <p className="team-role">{t("team.leader.title")}</p>
          <p className="team-desc">{t("team.leader.desc")}</p>
          <ul className="team-pills">
            {LEADER_PILLS.map((p) => (
              <li key={p} className="team-pill">
                {t(p)}
              </li>
            ))}
          </ul>
          <LinkedInLink
            href="https://www.linkedin.com/in/hasnain-ahmad-047210349/"
            label={t("team.linkedin")}
          />
        </div>
      </article>

      {/* Members — responsive 1 / 2 / 3 column grid */}
      <ul className="team-grid">
        {MEMBERS.map((m) => (
          <li
            key={m.id}
            className="team-card"
            style={{ "--accent": m.accent } as CSSProperties}
          >
            <Avatar
              src={m.photo}
              name={m.name}
              className="team-avatar team-avatar--member"
            />
            <div className="team-card__body">
              <h3 className="team-name">{m.name}</h3>
              <p className="team-desc">{t(m.descKey)}</p>
              <ul className="team-pills">
                {m.pills.map((p) => (
                  <li key={p} className="team-pill">
                    {t(p)}
                  </li>
                ))}
              </ul>
              {m.linkedin ? (
                <LinkedInLink href={m.linkedin} label={t("team.linkedin")} />
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
