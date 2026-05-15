'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

type Digest = {
  address: string;
  chains_active: string[];
  chains_dormant: string[];
  balances_by_chain: Record<string, number>;
  txs_by_chain: Record<string, number>;
  total_txs: number;
  error_rate: number;
  first_tx_ts: number | null;
  last_tx_ts: number | null;
  days_active: number;
  days_since_last_tx: number | null;
  activity_categories: Record<string, number>;
  top_contracts: Array<{
    address: string;
    hits: number;
    category: string;
    label: string;
    chains: string[];
  }>;
  recent_actions: string[];
  flags: string[];
};

type Example = {
  label: string;
  hint: string;
  address: string;
};

const EXAMPLES: Example[] = [
  {
    label: 'Vitalik',
    hint: 'OG · multi-chain DeFi',
    address: '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045',
  },
  {
    label: 'Smart money',
    hint: 'Henrik Andersson',
    address: '0x000000000A38444e0a6E37d3b630d7e855a7cb13',
  },
  {
    label: 'CZ',
    hint: 'Binance founder',
    address: '0x8894E0a0c962CB723c1976a4421c95949bE2D4E3',
  },
  {
    label: 'Yarrr',
    hint: 'Try with your own',
    address: '0x85B395f1511d3c14Ad984F02B2C4fbd7E56D0957',
  },
];

const CHAIN_COLORS: Record<string, string> = {
  ethereum: 'text-[#627EEA]',
  polygon:  'text-[#8247E5]',
  arbitrum: 'text-[#28A0F0]',
  base:     'text-[#0052FF]',
  optimism: 'text-[#FF0420]',
};

function formatBalance(n: number) {
  if (n === 0) return '0';
  if (n < 0.0001) return '< 0.0001';
  if (n < 1) return n.toFixed(4);
  if (n < 1000) return n.toFixed(2);
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function ageString(ts: number | null) {
  if (!ts) return '—';
  const secs = Math.max(Math.floor(Date.now() / 1000) - ts, 0);
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  if (secs < 30 * 86400) return `${Math.floor(secs / 86400)}d ago`;
  if (secs < 365 * 86400) return `${Math.floor(secs / (30 * 86400))}mo ago`;
  return `${Math.floor(secs / (365 * 86400))}y ago`;
}

export default function Home() {
  const [address, setAddress] = useState('');
  const [output, setOutput] = useState('');
  const [digest, setDigest] = useState<Digest | null>(null);
  const [phase, setPhase] = useState<'idle' | 'fetching' | 'analyzing' | 'done'>('idle');
  const [error, setError] = useState<string | null>(null);

  function isValidAddress(s: string) {
    return /^0x[a-fA-F0-9]{40}$/.test(s.trim());
  }

  async function analyze(addr?: string) {
    const a = (addr ?? address).trim();
    if (!isValidAddress(a)) {
      setError('Please paste a valid 0x… EVM address.');
      return;
    }
    setAddress(a);
    setError(null);
    setOutput('');
    setDigest(null);
    setPhase('fetching');

    try {
      const res = await fetch('/api/analyze/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address: a }),
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
            if (payload.phase === 'fetching') setPhase('fetching');
            if (payload.phase === 'digest' && payload.digest) setDigest(payload.digest as Digest);
            if (payload.phase === 'analyzing') setPhase('analyzing');
            if (payload.delta) setOutput((p) => p + payload.delta);
            if (payload.done) setPhase('done');
            if (payload.error) {
              setError(payload.error);
              setPhase('idle');
            }
          } catch { /* ignore */ }
        }
      }
      setPhase('done');
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setPhase('idle');
    }
  }

  const loading = phase === 'fetching' || phase === 'analyzing';

  return (
    <main className="relative">
      <div className="grid-bg fixed inset-0 pointer-events-none opacity-40" />

      <header className="relative max-w-6xl mx-auto px-6 pt-12 pb-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-gold-400 to-gold-600 grid place-items-center font-bold text-ink-900 text-lg shadow-lg shadow-gold-400/20">
            Y
          </div>
          <div>
            <h1 className="font-bold tracking-tight">Yarrr<span className="text-gold-400">.</span>Intel</h1>
            <p className="text-xs text-ink-400 font-mono">v0.3 · powered by MiMo V2.5</p>
          </div>
        </div>
        <a href="https://github.com/AirdropLaura/yarrr-intel" target="_blank" rel="noreferrer" className="btn-ghost">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2.18c-3.2.7-3.87-1.36-3.87-1.36-.52-1.31-1.27-1.66-1.27-1.66-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.24 3.34.95.1-.74.4-1.24.72-1.53-2.55-.29-5.24-1.27-5.24-5.66 0-1.25.45-2.27 1.18-3.07-.12-.29-.51-1.45.11-3.02 0 0 .96-.31 3.16 1.17a10.97 10.97 0 0 1 5.74 0c2.2-1.48 3.16-1.17 3.16-1.17.62 1.57.23 2.73.11 3.02.74.8 1.18 1.82 1.18 3.07 0 4.4-2.69 5.36-5.25 5.65.41.36.78 1.07.78 2.16v3.21c0 .31.21.67.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z"/></svg>
          GitHub
        </a>
      </header>

      <section className="relative max-w-3xl mx-auto px-6 pt-8 pb-10 text-center">
        <span className="inline-block px-3 py-1 text-[11px] font-mono font-semibold uppercase tracking-wider text-gold-400 border border-gold-400/30 rounded-full bg-gold-400/5">
          Free during beta
        </span>
        <h2 className="mt-5 text-4xl sm:text-5xl font-bold leading-tight tracking-tight bg-gradient-to-br from-ink-50 to-gold-400 bg-clip-text text-transparent">
          Understand any wallet<br className="hidden sm:block" /> instantly.
        </h2>
        <p className="mt-4 text-ink-300 max-w-xl mx-auto">
          Paste any EVM wallet. AI reads its on-chain history across 5 chains and tells you what it actually does — not just balances.
        </p>
      </section>

      <section className="relative max-w-3xl mx-auto px-6">
        <div className="glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-gold-400/5">
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              className="input-base font-mono text-sm sm:text-base px-4 py-3 flex-1"
              placeholder="0x... wallet address"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') analyze(); }}
              spellCheck={false}
              autoComplete="off"
            />
            <button
              className="btn-primary px-6 py-3 whitespace-nowrap"
              onClick={() => analyze()}
              disabled={loading || !address.trim()}
            >
              {loading ? 'Analyzing…' : 'Analyze →'}
            </button>
          </div>

          <div className="mt-3 flex flex-wrap gap-2 items-center">
            <span className="text-[11px] font-mono uppercase tracking-wider text-ink-500 mr-1">Try:</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => analyze(ex.address)}
                disabled={loading}
                className="group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-ink-800/60 border border-ink-700/60 text-xs font-mono hover:border-gold-400/40 hover:text-gold-400 transition-colors disabled:opacity-50"
              >
                <span className="font-semibold">{ex.label}</span>
                <span className="text-ink-500 group-hover:text-gold-400/70">· {ex.hint}</span>
              </button>
            ))}
          </div>

          {phase === 'fetching' && (
            <div className="mt-4 flex items-center gap-2 text-xs font-mono text-ink-400">
              <span className="w-1.5 h-1.5 rounded-full bg-gold-400 animate-pulse" />
              Scanning Ethereum, Polygon, Arbitrum, Base, Optimism…
            </div>
          )}
          {phase === 'analyzing' && (
            <div className="mt-4 flex items-center gap-2 text-xs font-mono text-gold-400">
              <span className="w-1.5 h-1.5 rounded-full bg-gold-400 animate-glow" />
              AI is interpreting the wallet…
            </div>
          )}
        </div>

        {error && (
          <div className="mt-5 glass rounded-xl p-4 border-red-500/30 text-red-300 text-sm">
            <strong className="font-semibold">Error:</strong> {error}
          </div>
        )}

        {digest && (
          <DigestPanel digest={digest} />
        )}

        {(output || phase === 'analyzing') && (
          <article className="mt-6 glass rounded-2xl p-6 sm:p-8 shadow-2xl shadow-gold-400/5">
            <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60">
              <h3 className="font-mono text-sm uppercase tracking-wider text-gold-400">Wallet Intel</h3>
              {phase === 'done' && (
                <span className="text-xs text-ink-500 font-mono">analysis complete</span>
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

      <section className="relative max-w-3xl mx-auto px-6 mt-20">
        <h3 className="text-center font-mono text-xs uppercase tracking-wider text-ink-400 mb-6">
          What we tell you about a wallet
        </h3>
        <div className="grid sm:grid-cols-2 gap-3">
          {[
            ['Behavioral profile',  'Smart money, airdrop hunter, dormant whale, NFT trader, MEV searcher — what kind of operator runs this wallet.'],
            ['Chain footprint',     'Where the activity actually lives. Primary hub vs. peripheral chains. Bridge entry points.'],
            ['Notable findings',    'Unusual recent moves, repeated targets, dormant→active shifts, large flows worth attention.'],
            ['Risk signals',        'High error rate, repeated reverts, unverified counterparties, suspicious patterns.'],
            ['Activity categories', 'DEX swaps, NFT mints, bridges, lending, governance, claims — counted and classified.'],
            ['Bottom-line summary', 'One paragraph you could send to a friend so they actually understand the wallet.'],
          ].map(([t, d]) => (
            <div key={t} className="glass rounded-xl p-4">
              <div className="text-sm font-semibold text-ink-50">{t}</div>
              <div className="text-xs text-ink-400 mt-1 leading-relaxed">{d}</div>
            </div>
          ))}
        </div>
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

function DigestPanel({ digest }: { digest: Digest }) {
  return (
    <article className="mt-6 glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-gold-400/5">
      <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60">
        <h3 className="font-mono text-sm uppercase tracking-wider text-gold-400">On-chain digest</h3>
        <code className="text-[11px] text-ink-500 font-mono truncate max-w-[60%]">
          {digest.address}
        </code>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <Stat label="Total tx" value={digest.total_txs.toString()} />
        <Stat label="Error rate" value={`${(digest.error_rate * 100).toFixed(1)}%`} tone={digest.error_rate > 0.15 ? 'warn' : 'normal'} />
        <Stat label="First seen" value={digest.first_tx_ts ? new Date(digest.first_tx_ts * 1000).toLocaleDateString() : '—'} />
        <Stat label="Last seen" value={ageString(digest.last_tx_ts)} />
      </div>

      <div className="mb-4">
        <SectionLabel>Native balances</SectionLabel>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {Object.entries(digest.balances_by_chain).map(([chain, bal]) => (
            <div key={chain} className="px-3 py-2 rounded-lg bg-ink-800/60 border border-ink-700/60">
              <div className={`text-[11px] font-mono uppercase tracking-wider ${CHAIN_COLORS[chain] ?? 'text-ink-300'}`}>{chain}</div>
              <div className="text-sm font-mono mt-0.5">{formatBalance(bal)}</div>
            </div>
          ))}
        </div>
      </div>

      {Object.keys(digest.activity_categories).length > 0 && (
        <div className="mb-4">
          <SectionLabel>Activity categories</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(digest.activity_categories).map(([cat, n]) => (
              <span key={cat} className="px-2 py-0.5 rounded-full bg-ink-800/60 border border-ink-700/60 text-[11px] font-mono">
                {cat} <span className="text-gold-400 font-semibold">{n}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {digest.flags.length > 0 && (
        <div className="mb-4">
          <SectionLabel>Heuristic flags</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {digest.flags.map((f) => (
              <span key={f} className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-gold-400/10 border border-gold-400/30 text-gold-400">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {digest.top_contracts.length > 0 && (
        <div>
          <SectionLabel>Top counterparty contracts</SectionLabel>
          <ul className="space-y-1.5">
            {digest.top_contracts.slice(0, 5).map((c) => (
              <li key={c.address} className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-ink-800/40 border border-ink-700/40">
                <div className="min-w-0">
                  <div className="text-xs font-semibold truncate">
                    {c.label}
                    <span className="ml-1 text-ink-500 font-normal">· {c.category}</span>
                  </div>
                  <div className="text-[10px] font-mono text-ink-500 truncate">
                    {c.address.slice(0, 10)}…{c.address.slice(-6)} · {c.chains.join(', ')}
                  </div>
                </div>
                <span className="text-xs font-mono text-gold-400 shrink-0">{c.hits}×</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function Stat({ label, value, tone = 'normal' }: { label: string; value: string; tone?: 'normal' | 'warn' }) {
  return (
    <div className="px-3 py-2 rounded-lg bg-ink-800/60 border border-ink-700/60">
      <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500">{label}</div>
      <div className={`text-sm font-mono mt-0.5 ${tone === 'warn' ? 'text-red-300' : 'text-ink-50'}`}>{value}</div>
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500 mb-2">{children}</div>;
}
