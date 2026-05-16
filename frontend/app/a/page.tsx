'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLang } from '../LanguageContext';

type Snapshot = {
  id: string;
  address: string;
  name: string | null;
  lang: string;
  model: string;
  digest: any;
  content: string;
  created_at: number;
};

// We can't have `/a/[id]/page.tsx` with Next's static export — dynamic
// routes need `generateStaticParams`, which we can't provide for unknown
// runtime ids. Instead this single page reads the id from the URL path
// (`/a/<id>/`) on the client and fetches the snapshot. Nginx is configured
// to fall through `/a/*` to this page (via try_files in the rewrite block).

function readIdFromUrl(): string | null {
  // We accept either:
  //   /a/<id>/ — backend serves this directly with OG meta + meta-refresh
  //   /a/?sid=<id> — landed via SPA fallback after the redirect
  // Whichever path we end up on, recover the id.
  try {
    const params = new URLSearchParams(window.location.search);
    const fromQuery = params.get('sid');
    if (fromQuery && /^[A-Za-z0-9_-]+$/.test(fromQuery)) return fromQuery;
  } catch {
    /* noop */
  }
  const m = window.location.pathname.match(/\/a\/([A-Za-z0-9_-]+)\/?$/);
  return m ? m[1] : null;
}

export default function SharedAnalysis() {
  const { t } = useLang();

  const [id, setId] = useState<string | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const sid = readIdFromUrl();
    setId(sid);
    if (!sid) {
      setError('Missing snapshot id in URL.');
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/share/${encodeURIComponent(sid)}`);
        if (!res.ok) {
          throw new Error(res.status === 404 ? 'Snapshot not found' : `HTTP ${res.status}`);
        }
        const data = (await res.json()) as Snapshot;
        if (!cancelled) {
          setSnap(data);
          setLoading(false);
        }
      } catch (e: any) {
        if (!cancelled) {
          setError(e?.message ?? String(e));
          setLoading(false);
        }
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <main className="relative">
      <div className="grid-bg fixed inset-0 pointer-events-none opacity-40" />

      <header className="relative max-w-3xl mx-auto px-6 pt-12 pb-8 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-ruby-400 to-ruby-600 grid place-items-center font-bold text-ink-900 text-lg shadow-lg shadow-ruby-400/20 group-hover:shadow-ruby-400/40 transition-shadow">
            Y
          </div>
          <div>
            <h1 className="font-bold tracking-tight">Yarrr<span className="text-ruby-400">.</span>Tech</h1>
            <p className="text-[10px] text-ink-500 font-mono uppercase tracking-wider">
              shared analysis{id ? ` · ${id}` : ''}
            </p>
          </div>
        </Link>
        <Link href="/" className="btn-ghost">← analyze another</Link>
      </header>

      <section className="relative max-w-3xl mx-auto px-6">
        {loading && (
          <div className="glass rounded-2xl p-6 text-sm text-ink-300">{t.reasoning}</div>
        )}

        {error && !loading && (
          <div className="glass rounded-xl p-6 border-red-500/30 text-red-300 text-sm">
            <strong className="font-semibold">{t.errorPrefix}</strong> {error}
          </div>
        )}

        {snap && (
          <>
            <div className="glass rounded-2xl p-5 sm:p-6 mb-6">
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div className="min-w-0">
                  {snap.name && (
                    <div className="text-lg font-semibold text-ink-50 truncate">{snap.name}</div>
                  )}
                  <code className="text-[11px] text-ink-500 font-mono break-all">{snap.address}</code>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500">{t.taglineVersion}</div>
                  <div className="text-[11px] font-mono text-ink-400 mt-0.5">
                    {new Date(snap.created_at * 1000).toLocaleString()}
                  </div>
                </div>
              </div>
            </div>

            {snap.digest?.archetypes?.length > 0 && (
              <div className="glass rounded-2xl p-5 sm:p-6 mb-6">
                <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400 mb-3 pb-2 border-b border-ink-700/60">
                  {t.archetypeTitle}
                </h3>
                <div className="space-y-2">
                  {snap.digest.archetypes.map((a: any) => (
                    <div key={a.name} className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-ink-800/60 border border-ink-700/60">
                      <code className="font-mono font-semibold text-sm text-ruby-400">{a.name}</code>
                      <div className="flex items-center gap-2 text-[11px] font-mono text-ink-300">
                        <span className="uppercase tracking-wider">{a.bucket}</span>
                        <span className="px-2 py-0.5 rounded-full bg-ink-900/60 border border-ink-700">
                          {a.confidence?.toFixed?.(2)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <article className="glass rounded-2xl p-6 sm:p-8 shadow-2xl shadow-ruby-400/5">
              <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60">
                <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.walletIntel}</h3>
                <span className="text-xs text-ink-500 font-mono">{t.analysisComplete}</span>
              </header>
              <div className="prose-yarrr">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{snap.content}</ReactMarkdown>
              </div>
            </article>
          </>
        )}
      </section>

      <footer className="relative max-w-6xl mx-auto px-6 pt-20 pb-10 text-center">
        <div className="text-xs text-ink-500 font-mono">
          yarrr-node.com · {t.builtBy}{' '}
          <span className="text-ruby-400/80">{t.builtByName}</span>
          {' · '}{t.footerBuilt}
        </div>
      </footer>
    </main>
  );
}
