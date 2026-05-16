'use client';

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { DEFAULT_LANG, Lang, T, Dict } from './i18n';

type Ctx = {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: Dict;
};

const LangContext = createContext<Ctx | null>(null);

const LS_KEY = 'yarrr.lang';

export function LanguageProvider({ children }: { children: ReactNode }) {
  // SSR/static-export safe: start with default, hydrate from localStorage on mount.
  const [lang, setLangState] = useState<Lang>(DEFAULT_LANG);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(LS_KEY);
      if (stored === 'id' || stored === 'en') {
        setLangState(stored);
      }
    } catch { /* ignore */ }
  }, []);

  // Reflect language on the <html lang> attribute for a11y / SEO crawlers.
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = lang;
    }
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { window.localStorage.setItem(LS_KEY, l); } catch { /* ignore */ }
  }, []);

  return (
    <LangContext.Provider value={{ lang, setLang, t: T[lang] }}>
      {children}
    </LangContext.Provider>
  );
}

export function useLang(): Ctx {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error('useLang must be used inside LanguageProvider');
  return ctx;
}
