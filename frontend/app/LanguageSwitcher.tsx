'use client';

import { useState, useRef, useEffect } from 'react';
import { useLang } from './LanguageContext';
import { Lang } from './i18n';

// Inline SVG flags. Keeping these in JSX (not <img>) means no extra requests
// and they inherit border-radius / sizing from their wrapper cleanly.

function FlagID({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 60 40" className={className} aria-hidden="true">
      <rect width="60" height="20" fill="#E70011" />
      <rect y="20" width="60" height="20" fill="#FFFFFF" />
    </svg>
  );
}

function FlagGB({ className = '' }: { className?: string }) {
  return (
    <svg viewBox="0 0 60 40" className={className} aria-hidden="true">
      <clipPath id="gbclip"><rect width="60" height="40" /></clipPath>
      <g clipPath="url(#gbclip)">
        <rect width="60" height="40" fill="#012169" />
        <path d="M0,0 L60,40 M60,0 L0,40" stroke="#FFFFFF" strokeWidth="6" />
        <path d="M0,0 L60,40 M60,0 L0,40" stroke="#C8102E" strokeWidth="3" />
        <path d="M30,0 V40 M0,20 H60" stroke="#FFFFFF" strokeWidth="10" />
        <path d="M30,0 V40 M0,20 H60" stroke="#C8102E" strokeWidth="6" />
      </g>
    </svg>
  );
}

const FLAG_BY_LANG = {
  id: { Flag: FlagID, short: 'ID' },
  en: { Flag: FlagGB, short: 'EN' },
} as const;

export function LanguageSwitcher() {
  const { lang, setLang, t } = useLang();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click — small detail that makes the dropdown feel like
  // every other native menu rather than a sticky overlay.
  useEffect(() => {
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [open]);

  const Current = FLAG_BY_LANG[lang];

  function pick(l: Lang) {
    setLang(l);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-label={t.langLabel}
        aria-expanded={open}
        className="inline-flex items-center gap-2 rounded-lg border border-ink-700 px-3 py-2 text-sm text-ink-300 hover:text-ink-50 hover:border-ruby-400/40 transition-colors"
      >
        <Current.Flag className="w-5 h-[14px] rounded-sm overflow-hidden ring-1 ring-ink-700/60" />
        <span className="font-mono font-semibold">{Current.short}</span>
        <svg
          width="10" height="10" viewBox="0 0 10 10"
          className={`transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden="true"
        >
          <path d="M1 3l4 4 4-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 mt-2 w-44 rounded-lg border border-ink-700 bg-ink-800/95 backdrop-blur-xl shadow-xl shadow-black/40 overflow-hidden z-20">
          {(['id', 'en'] as Lang[]).map((l) => {
            const active = l === lang;
            const { Flag } = FLAG_BY_LANG[l];
            const label = l === 'id' ? t.langID : t.langEN;
            return (
              <button
                key={l}
                type="button"
                onClick={() => pick(l)}
                className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm text-left transition-colors ${
                  active
                    ? 'bg-ruby-400/10 text-ruby-400'
                    : 'text-ink-200 hover:bg-ink-700/60 hover:text-ink-50'
                }`}
              >
                <Flag className="w-6 h-[18px] rounded-sm overflow-hidden ring-1 ring-ink-700/60 shrink-0" />
                <span className="flex-1">{label}</span>
                {active && (
                  <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
                    <path d="M2 6l3 3 5-6" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
