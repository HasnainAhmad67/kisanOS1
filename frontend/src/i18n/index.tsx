import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { en, type DictKey } from "./en";
import { ur } from "./ur";

export type Locale = "en" | "ur";
export type { DictKey };

const STORAGE_KEY = "kisanos.locale";
const DIRECTIONS: Record<Locale, "ltr" | "rtl"> = { en: "ltr", ur: "rtl" };

function readStored(): Locale {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "ur" || raw === "en") return raw;
  } catch {
    /* storage unavailable */
  }
  return "en";
}

interface I18nValue {
  locale: Locale;
  dir: "ltr" | "rtl";
  /** Translate a known UI key (English ↔ Urdu). */
  t: (key: DictKey) => string;
  /**
   * Translate a dynamic key (backend phase/status names) with a graceful
   * fallback — used for strings that are not statically known.
   */
  tx: (key: string, fallback: string) => string;
  setLocale: (next: Locale) => void;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readStored);

  // Apply lang/dir to <html> whenever the locale changes (including on load).
  useEffect(() => {
    document.documentElement.lang = locale;
    document.documentElement.dir = DIRECTIONS[locale];
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* storage unavailable — locale still applies for this session */
    }
  }, []);

  const value = useMemo<I18nValue>(() => {
    const dict = locale === "ur" ? ur : en;
    return {
      locale,
      dir: DIRECTIONS[locale],
      t: (key) => dict[key],
      tx: (key, fallback) => {
        const typed = key as DictKey;
        const translated = (dict as Record<string, string>)[typed];
        return translated ?? fallback;
      },
      setLocale,
    };
  }, [locale, setLocale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const value = useContext(I18nContext);
  if (!value) {
    throw new Error("useI18n must be used inside <I18nProvider>");
  }
  return value;
}

/** Dynamic dictionary lookup outside React (e.g. plain helpers). */
export function translate(locale: Locale, key: DictKey): string {
  return (locale === "ur" ? ur : en)[key];
}
