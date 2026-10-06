import type { ReactNode } from "react";
import { useI18n, type DictKey } from "../i18n";
import type { AmisQuote, QuoteFreshness } from "../types/backend";

const FRESHNESS_KEY: Record<QuoteFreshness, DictKey> = {
  fresh: "market.freshness.fresh",
  stale: "market.freshness.stale",
  unknown: "market.freshness.unknown",
};

/**
 * Structural guard for `AgentResult.data.quote`: only the official AMIS shape
 * is rendered here. Farmer-entered quotes keep their existing presentation.
 */
export function isAmisQuote(value: unknown): value is AmisQuote {
  if (typeof value !== "object" || value === null) return false;
  const quote = value as Partial<AmisQuote>;
  return (
    quote.source === "AMIS" &&
    typeof quote.market === "string" &&
    typeof quote.unit === "string" &&
    typeof quote.source_url === "string" &&
    typeof quote.freshness === "string"
  );
}

/** Source numbers, grouped for reading only — never rounded or converted. */
function price(value: number): string {
  return Number.isInteger(value) ? value.toLocaleString("en-US") : String(value);
}

/**
 * One label/value pair. Values are source data (market names, units, dates,
 * prices, URLs) so they stay LTR inside the RTL Urdu layout.
 */
function Row({
  label,
  value,
  ltr = true,
}: {
  label: string;
  value: ReactNode;
  /** false for values rendered in the UI language (e.g. a localized fallback). */
  ltr?: boolean;
}) {
  return (
    <div className="market-quote__row">
      <dt>{label}</dt>
      <dd
        className={ltr ? "num" : undefined}
        dir={ltr ? "ltr" : undefined}
        lang={ltr ? "en" : undefined}
      >
        {value}
      </dd>
    </div>
  );
}

/**
 * Live mandi quote panel: market, commodity, min/max/average (only the fields
 * AMIS actually returned), the exact source unit, quote + retrieval times, the
 * source link and a freshness badge. `null` fields are omitted — a missing
 * price is never shown as 0 or as a placeholder.
 */
export function MarketQuote({ quote }: { quote: AmisQuote }) {
  const { t } = useI18n();

  return (
    <section className="market-quote" aria-label={t("market.quote.heading")}>
      <div className="market-quote__head">
        <p className="market-quote__title">{t("market.quote.heading")}</p>
        <span className={`badge market-quote__badge market-quote__badge--${quote.freshness}`}>
          {t(FRESHNESS_KEY[quote.freshness])}
        </span>
      </div>
      <dl className="market-quote__grid">
        <Row label={t("market.quote.market")} value={quote.market} />
        <Row label={t("market.quote.commodity")} value={quote.commodity} />
        {quote.min_price !== null ? (
          <Row label={t("market.quote.min")} value={price(quote.min_price)} />
        ) : null}
        {quote.max_price !== null ? (
          <Row label={t("market.quote.max")} value={price(quote.max_price)} />
        ) : null}
        {quote.average_price !== null ? (
          <Row label={t("market.quote.average")} value={price(quote.average_price)} />
        ) : null}
        <Row label={t("market.quote.unit")} value={quote.unit} />
        <Row
          label={t("market.quote.quoteDate")}
          value={quote.source_date ?? t("market.quote.dateUnavailable")}
          ltr={quote.source_date !== null}
        />
        <Row
          label={t("market.quote.retrieved")}
          value={new Date(quote.retrieved_at).toLocaleString()}
        />
        <Row
          label={t("market.quote.source")}
          value={
            quote.source_url ? (
              <a href={quote.source_url} target="_blank" rel="noreferrer noopener">
                {t("market.quote.sourceName")}
              </a>
            ) : (
              t("market.quote.sourceName")
            )
          }
        />
      </dl>
    </section>
  );
}
