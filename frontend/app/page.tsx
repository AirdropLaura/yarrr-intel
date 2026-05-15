'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const PRESET_NETWORKS = [
  'Cosmos SDK',
  'CometBFT / Tendermint',
  'Substrate',
  'EVM (geth/erigon)',
  'nesa-node',
  'tempo-node',
  'inri-installer',
  'Other',
];

const PLACEHOLDER = `Paste your error log, panic trace, RPC response, or config snippet here.

Example:
nesa-node[12345]: 2026-05-15 ERROR: failed to connect to peer
nesa-node[12345]: panic: runtime error: invalid memory address or nil pointer dereference`;

export default function Home() {
  const [text, setText] = useState('');
  const [network, setNetwork] = useState('');
  const [osName, setOsName] = useState('Ubuntu 24.04');
  const [extra, setExtra] = useState('');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<{ total_tokens?: number; reasoning_tokens?: number; latency_seconds?: number } | null>(null);

  async function diagnose() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    setOutput('');
    setUsage(null);
    try {
      const res = await fetch('/api/diagnose/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text,
          network: network || null,
          os_name: osName || null,
          context: extra || null,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = '';
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) {
          if (!line.startsWith('data:')) continue;
          try {
            const payload = JSON.parse(line.slice(5).trim());
            if (payload.delta) setOutput(prev => prev + payload.delta);
            if (payload.error) setError(payload.error);
          } catch { /* ignore */ }
        }
      }
    } catch (e: any) {
      setError(e?.message ?? String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative">
      <div className="grid-bg fixed inset-0 pointer-events-none opacity-40" />

      <header className="relative max-w-6xl mx-auto px-6 pt-12 pb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-gold-400 to-gold-600 grid place-items-center font-bold text-ink-900 text-lg shadow-lg shadow-gold-400/20">
            Y
          </div>
          <div>
            <h1 className="font-bold tracking-tight">Yarrr<span className="text-gold-400">.</span>Tech</h1>
            <p className="text-xs text-ink-400 font-mono">v0.1 · powered by MiMo V2.5</p>
          </div>
        </div>
        <a href="https://github.com/AirdropLaura/yarrr-tech" target="_blank" rel="noreferrer" className="btn-ghost">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2.18c-3.2.7-3.87-1.36-3.87-1.36-.52-1.31-1.27-1.66-1.27-1.66-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.24 3.34.95.1-.74.4-1.24.72-1.53-2.55-.29-5.24-1.27-5.24-5.66 0-1.25.45-2.27 1.18-3.07-.12-.29-.51-1.45.11-3.02 0 0 .96-.31 3.16 1.17a10.97 10.97 0 0 1 5.74 0c2.2-1.48 3.16-1.17 3.16-1.17.62 1.57.23 2.73.11 3.02.74.8 1.18 1.82 1.18 3.07 0 4.4-2.69 5.36-5.25 5.65.41.36.78 1.07.78 2.16v3.21c0 .31.21.67.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z"/></svg>
          GitHub
        </a>
      </header>

      <section className="relative max-w-3xl mx-auto px-6 pt-8 pb-12 text-center">
        <span className="inline-block px-3 py-1 text-[11px] font-mono font-semibold uppercase tracking-wider text-gold-400 border border-gold-400/30 rounded-full bg-gold-400/5">
          Free during beta
        </span>
        <h2 className="mt-5 text-4xl sm:text-5xl font-bold leading-tight tracking-tight bg-gradient-to-br from-ink-50 to-gold-400 bg-clip-text text-transparent">
          Diagnose node failures<br className="hidden sm:block" /> in seconds, not hours.
        </h2>
        <p className="mt-4 text-ink-300 max-w-xl mx-auto">
          Paste a panic trace, peer timeout, or broken config. Get the root cause and the exact commands to fix it.
        </p>
      </section>

      <section className="relative max-w-3xl mx-auto px-6">
        <div className="glass rounded-2xl p-6 sm:p-7 shadow-2xl shadow-gold-400/5">
          <label className="block text-xs font-mono uppercase tracking-wider text-ink-400 mb-2">
            Log / error / config
          </label>
          <textarea
            className="input-base font-mono text-sm leading-relaxed p-4 resize-y min-h-[200px]"
            placeholder={PLACEHOLDER}
            value={text}
            onChange={(e) => setText(e.target.value)}
            spellCheck={false}
          />

          <div className="mt-4 grid sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-400 mb-1.5">
                Network <span className="text-ink-500">(optional)</span>
              </label>
              <input
                className="input-base px-3 py-2 text-sm"
                list="networks"
                placeholder="e.g. nesa-node"
                value={network}
                onChange={(e) => setNetwork(e.target.value)}
              />
              <datalist id="networks">
                {PRESET_NETWORKS.map((n) => <option key={n} value={n} />)}
              </datalist>
            </div>
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-400 mb-1.5">
                OS <span className="text-ink-500">(optional)</span>
              </label>
              <input
                className="input-base px-3 py-2 text-sm"
                placeholder="Ubuntu 24.04"
                value={osName}
                onChange={(e) => setOsName(e.target.value)}
              />
            </div>
          </div>

          <details className="mt-4 group">
            <summary className="text-xs font-mono uppercase tracking-wider text-ink-400 cursor-pointer hover:text-ink-200 select-none">
              + Add extra context
            </summary>
            <textarea
              className="mt-2 input-base text-sm p-3 resize-y min-h-[80px]"
              placeholder="What were you doing when this happened? Recent changes, restart, upgrade, etc."
              value={extra}
              onChange={(e) => setExtra(e.target.value)}
            />
          </details>

          <div className="mt-5 flex items-center justify-between gap-3">
            <p className="text-xs text-ink-500 font-mono">
              {text.length.toLocaleString()} chars · runs on MiMo V2.5
            </p>
            <button
              className="btn-primary"
              onClick={diagnose}
              disabled={loading || !text.trim()}
            >
              {loading ? (
                <>
                  <span className="inline-block w-2 h-2 rounded-full bg-ink-900 animate-pulse" />
                  Diagnosing…
                </>
              ) : (
                <>Diagnose <span aria-hidden>→</span></>
              )}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-5 glass rounded-xl p-4 border-red-500/30 text-red-300 text-sm">
            <strong className="font-semibold">Error:</strong> {error}
          </div>
        )}

        {(output || loading) && (
          <article className="mt-6 glass rounded-2xl p-6 sm:p-8 shadow-2xl shadow-gold-400/5">
            <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60">
              <h3 className="font-mono text-sm uppercase tracking-wider text-gold-400">Diagnosis</h3>
              {usage?.total_tokens && (
                <span className="text-xs text-ink-500 font-mono">
                  {usage.total_tokens} tokens · {usage.latency_seconds}s
                </span>
              )}
            </header>
            <div className="prose-yarrr">
              {output ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{output}</ReactMarkdown>
              ) : (
                <div className="flex items-center gap-2 text-ink-400 text-sm">
                  <span className="w-2 h-2 rounded-full bg-gold-400 animate-glow" />
                  Reasoning…
                </div>
              )}
            </div>
          </article>
        )}
      </section>

      <footer className="relative max-w-6xl mx-auto px-6 pt-20 pb-10 text-center">
        <div className="text-xs text-ink-500 font-mono">
          yarrr-node.com · operated by{' '}
          <a href="https://github.com/AirdropLaura" className="text-gold-400/80 hover:text-gold-400">@AirdropLaura</a>
          {' · '}built on a single VPS, with care
        </div>
      </footer>
    </main>
  );
}
