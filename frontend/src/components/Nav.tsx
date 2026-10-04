import type { ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import { useI18n } from "../i18n";

interface NavItem {
  to: string;
  labelKey:
    | "nav.newCheck"
    | "nav.myChecks"
    | "nav.guidance"
    | "nav.team"
    | "nav.settings";
  icon: ReactNode;
}

const ICON_STYLE = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  "aria-hidden": true,
};

const ITEMS: NavItem[] = [
  {
    to: "/",
    labelKey: "nav.newCheck",
    icon: (
      <svg {...ICON_STYLE}>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 8v8M8 12h8" />
      </svg>
    ),
  },
  {
    to: "/results",
    labelKey: "nav.myChecks",
    icon: (
      <svg {...ICON_STYLE}>
        <rect x="5" y="4" width="14" height="17" rx="2" />
        <path d="M9 3h6v3H9zM9 11h6M9 15h4" />
      </svg>
    ),
  },
  {
    to: "/",
    labelKey: "nav.guidance",
    icon: (
      <svg {...ICON_STYLE}>
        <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H12v17H6.5A2.5 2.5 0 0 0 4 22z" />
        <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H12v17h5.5A2.5 2.5 0 0 1 20 22z" />
      </svg>
    ),
  },
  {
    to: "/team",
    labelKey: "nav.team",
    icon: (
      <svg {...ICON_STYLE}>
        <circle cx="9" cy="8" r="3.2" />
        <path d="M3.5 20a5.5 5.5 0 0 1 11 0" />
        <circle cx="17.2" cy="9" r="2.5" />
        <path d="M16.4 14.6A5.4 5.4 0 0 1 21 19.8" />
      </svg>
    ),
  },
  {
    to: "/settings",
    labelKey: "nav.settings",
    icon: (
      <svg {...ICON_STYLE}>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
      </svg>
    ),
  },
];

/**
 * Single nav element: sticky bottom bar on mobile, sidebar on desktop.
 * "My Checks" lands on Results (guarded → farm details when no session);
 * "Guidance" returns to the Welcome how-it-works section.
 */
export function Nav() {
  const { t } = useI18n();
  const location = useLocation();

  function isActive(item: NavItem): boolean {
    if (item.labelKey === "nav.newCheck") {
      return location.pathname === "/" || location.pathname === "/farm-details";
    }
    if (item.labelKey === "nav.guidance") return false;
    return location.pathname.startsWith(item.to);
  }

  return (
    <nav className="app-nav" aria-label={t("nav.main")}>
      <ul>
        {ITEMS.map((item) => (
          <li key={item.labelKey}>
            <Link
              to={item.to}
              className={`app-nav__item${isActive(item) ? " is-active" : ""}`}
              aria-current={isActive(item) ? "page" : undefined}
              onClick={() => {
                if (item.labelKey === "nav.guidance") {
                  // Land on Welcome, then jump to the how-it-works card.
                  window.requestAnimationFrame(() => {
                    document
                      .getElementById("how-it-works")
                      ?.scrollIntoView({ behavior: "smooth" });
                  });
                }
              }}
            >
              {item.icon}
              <span>{t(item.labelKey)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
