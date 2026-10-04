import { useCallback, useState } from "react";
import type { Locale } from "../types/backend";

export type Direction = "ltr" | "rtl";

const DIRECTIONS: Record<Locale, Direction> = {
  en: "ltr",
  ur: "rtl",
  roman_ur: "ltr",
};

/**
 * Locale hook — Urdu RTL support ready.
 * Setting the locale updates <html lang> and <html dir>; styles rely on
 * logical properties, so flipping `dir` mirrors the whole layout.
 */
export function useLocale() {
  const [locale, setLocaleState] = useState<Locale>(() => {
    const current = document.documentElement.lang as Locale;
    return current === "ur" || current === "roman_ur" ? current : "en";
  });

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    document.documentElement.lang = next;
    document.documentElement.dir = DIRECTIONS[next];
  }, []);

  return {
    locale,
    direction: DIRECTIONS[locale],
    setLocale,
    isRTL: DIRECTIONS[locale] === "rtl",
  };
}
