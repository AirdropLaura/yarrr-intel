'use client';

import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useLang } from './LanguageContext';
import { LanguageSwitcher } from './LanguageSwitcher';
import { Dict } from './i18n';

type ArchetypeOut = {
  name: string;
  confidence: number;
  bucket: 'strong' | 'moderate' | 'tentative' | 'weak';
  evidence: string[];
};

type TokenHolding = {
  chain: string;
  contract: string;
  symbol: string;
  name: string;
  decimals: number;
  amount: number;
  is_stablecoin: boolean;
  is_lp: boolean;
  is_lst: boolean;
  is_spam: boolean;
  // Trust verdict (Phase 4)
  trust_tier?: 'trusted' | 'uncertain' | 'spam';
  trust_score?: number;       // 0-100
  trust_summary?: string;
  trust_reasons?: string[];
};

type HoldingsTrust = {
  trusted_count: number;
  uncertain_count: number;
  spam_count: number;
  real_token_count: number;
  spam_ratio: number;
  headline: string;
};

type TokenSignals = {
  stablecoin_volume_usd: number;
  stablecoin_chains: string[];
  distinct_stablecoins: string[];
  distinct_erc20: number;
  holds_lp_tokens: boolean;
  holds_lst_tokens: boolean;
  distinct_nft_collections: number;
  spam_nft_count: number;
  spam_nft_examples: string[];
  holdings?: TokenHolding[];
  holdings_trust?: HoldingsTrust;
};

type FailedTxCluster = {
  chain: string;
  target: string;
  method: string | null;
  count: number;
};

type ReputationContrib = {
  label: string;
  delta: number;
  detail: string;
};

type Reputation = {
  score: number;
  bucket: 'high' | 'good' | 'neutral' | 'low' | 'poor';
  raw_score: number;
  contributions: ReputationContrib[];
};

type TimelinePeriod = {
  start_ts: number;
  end_ts: number;
  tx_count: number;
  chains: string[];
  dominant_category: string | null;
  error_rate: number;
};

type Digest = {
  address: string;
  name: string | null;
  chains_active: string[];
  chains_dormant: string[];
  mainnet_chains_active: string[];
  testnet_chains_active: string[];
  balances_by_chain: Record<string, number>;
  txs_by_chain: Record<string, number>;
  total_txs: number;
  total_internal_txs?: number;
  partial_chains?: string[];
  total_balance_native: number;
  error_rate: number;
  first_tx_ts: number | null;
  last_tx_ts: number | null;
  days_active: number;
  days_since_last_tx: number | null;
  wallet_age_days: number;
  activity_categories: Record<string, number>;
  top_contracts: Array<{
    address: string;
    hits: number;
    category: string;
    label: string;
    chains: string[];
  }>;
  recent_actions: string[];
  funding_source: 'cex_deposit' | 'bridge' | 'airdrop_claim' | null;
  funding_evidence: string[];
  tokens: TokenSignals;
  failed_tx_clusters: FailedTxCluster[];
  timeline: TimelinePeriod[];
  archetypes: ArchetypeOut[];
  reputation: Reputation | null;
  flags: string[];
};

type Example = {
  hintKey: 'exVitalik' | 'exSmart' | 'exCZ' | 'exYarrr';
  label: string;
  address: string;
};

const EXAMPLES: Example[] = [
  { label: 'Vitalik',      hintKey: 'exVitalik', address: '0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045' },
  { label: 'Smart money',  hintKey: 'exSmart',   address: '0x000000000A38444e0a6E37d3b630d7e855a7cb13' },
  { label: 'CZ',           hintKey: 'exCZ',      address: '0x8894E0a0c962CB723c1976a4421c95949bE2D4E3' },
  { label: 'Yarrr',        hintKey: 'exYarrr',   address: '0x85B395f1511d3c14Ad984F02B2C4fbd7E56D0957' },
];

// Brand colors per chain. Non-listed chains get a neutral ink tone.
const CHAIN_COLORS: Record<string, string> = {
  ethereum: 'text-[#627EEA]',
  polygon:  'text-[#8247E5]',
  arbitrum: 'text-[#28A0F0]',
  base:     'text-[#0052FF]',
  optimism: 'text-[#FF0420]',
  bsc:      'text-[#F0B90B]',
  avalanche:'text-[#E84142]',
  linea:    'text-[#61DFFF]',
  scroll:   'text-[#FFEEDA]',
  blast:    'text-[#FCFC03]',
  mantle:   'text-[#A1AEC0]',
  worldchain:'text-[#F0F0F0]',
  opbnb:    'text-[#FCD035]',
  gnosis:   'text-[#04795B]',
  celo:     'text-[#FBCC5C]',
  zksync:   'text-[#8C8DFC]',
};

// Confidence bucket → border + text styles for archetype cards.
const BUCKET_STYLES: Record<ArchetypeOut['bucket'], string> = {
  strong:    'border-ruby-400/60 bg-ruby-400/10 text-ruby-400',
  moderate:  'border-ruby-400/30 bg-ruby-400/5 text-ruby-400/90',
  tentative: 'border-ink-700 bg-ink-800/60 text-ink-200',
  weak:      'border-ink-700/50 bg-ink-800/40 text-ink-400',
};

function formatBalance(n: number) {
  if (n === 0) return '0';
  if (n < 0.0001) return '< 0.0001';
  if (n < 1) return n.toFixed(4);
  if (n < 1000) return n.toFixed(2);
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function formatTokenAmount(n: number) {
  if (n === 0) return '0';
  if (n < 0.0001) return '< 0.0001';
  if (n < 1) return n.toFixed(4);
  if (n < 1_000) return n.toFixed(2);
  if (n < 1_000_000) return `${(n / 1_000).toFixed(1)}K`;
  if (n < 1_000_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  return `${(n / 1_000_000_000).toFixed(2)}B`;
}

function shortAddr(a: string) {
  return `${a.slice(0, 6)}…${a.slice(-4)}`;
}

function formatAge(days: number, t: Dict) {
  if (days < 30) return `${days}${t.ageDay}`;
  if (days < 365) return `${Math.floor(days / 30)}${t.ageMonth}`;
  return `${Math.floor(days / 365)}${t.ageYear}`;
}

function ageString(ts: number | null, t: Dict) {
  if (!ts) return '—';
  const secs = Math.max(Math.floor(Date.now() / 1000) - ts, 0);
  if (secs < 86400)         return `${Math.floor(secs / 3600)}${t.ageHour}`;
  if (secs < 30 * 86400)    return `${Math.floor(secs / 86400)}${t.ageDay}`;
  if (secs < 365 * 86400)   return `${Math.floor(secs / (30 * 86400))}${t.ageMonth}`;
  return `${Math.floor(secs / (365 * 86400))}${t.ageYear}`;
}

function bucketLabel(bucket: ArchetypeOut['bucket'], t: Dict) {
  if (bucket === 'strong')    return t.confStrong;
  if (bucket === 'moderate')  return t.confModerate;
  if (bucket === 'tentative') return t.confTentative;
  return bucket;
}

function fundingLabel(src: Digest['funding_source'], t: Dict) {
  switch (src) {
    case 'cex_deposit':  return t.fundingCex;
    case 'bridge':       return t.fundingBridge;
    case 'airdrop_claim': return t.fundingClaim;
    default: return null;
  }
}

export default function Home() {
  const { lang, t } = useLang();

  const [address, setAddress] = useState('');
  const [multiAddresses, setMultiAddresses] = useState('');
  const [mode, setMode] = useState<'single' | 'multi'>('single');
  const [output, setOutput] = useState('');
  const [digest, setDigest] = useState<Digest | null>(null);
  const [multiDigests, setMultiDigests] = useState<Digest[] | null>(null);
  const [phase, setPhase] = useState<'idle' | 'fetching' | 'analyzing' | 'done'>('idle');
  const [error, setError] = useState<string | null>(null);

  // Track which lang the current output was rendered in. When user toggles
  // language while we have a result on screen, re-run the analyze in the new
  // language so the report stays aligned with the UI.
  const [outputLang, setOutputLang] = useState<string | null>(null);
  const langSwitchInFlight = useRef(false);

  // Auto re-analyze when the user switches language mid-session. Only fires
  // when we already have a finished output in a different language and we're
  // not in the middle of another request.
  useEffect(() => {
    if (phase !== 'done') return;
    if (!output) return;
    if (!outputLang || outputLang === lang) return;
    if (langSwitchInFlight.current) return;
    langSwitchInFlight.current = true;
    (async () => {
      try {
        if (mode === 'multi' && multiDigests && multiDigests.length > 0) {
          await analyzeMulti();
        } else if (address) {
          await analyze(address);
        }
      } finally {
        langSwitchInFlight.current = false;
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);

  function isValidAddress(s: string) {
    return /^0x[a-fA-F0-9]{40}$/.test(s.trim());
  }

  function parseMultiAddresses(raw: string): string[] {
    // Accept newline / comma / space separated; trim each; dedupe lower
    const parts = raw.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean);
    const seen = new Set<string>();
    const out: string[] = [];
    for (const p of parts) {
      const k = p.toLowerCase();
      if (!seen.has(k)) {
        seen.add(k);
        out.push(p);
      }
    }
    return out;
  }

  async function analyzeMulti() {
    const addrs = parseMultiAddresses(multiAddresses);
    if (addrs.length < 2) {
      setError(t.multiMinAddrs);
      return;
    }
    if (addrs.length > 10) {
      setError(t.multiMaxAddrs);
      return;
    }
    for (const a of addrs) {
      if (!isValidAddress(a)) {
        setError(`${t.invalidAddress}: ${a.slice(0, 14)}…`);
        return;
      }
    }
    setError(null);
    setOutput('');
    setDigest(null);
    setMultiDigests(null);
    setPhase('fetching');

    try {
      const res = await fetch('/api/analyze/multi', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ addresses: addrs, lang }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }
      const data = await res.json();
      setOutput(data.content || '');
      setMultiDigests(data.digests || []);
      setOutputLang(lang);
      setPhase('done');
    } catch (e: any) {
      setError(e.message || 'request failed');
      setPhase('idle');
    }
  }

  async function analyze(addr?: string) {
    const a = (addr ?? address).trim();
    if (!isValidAddress(a)) {
      setError(t.invalidAddress);
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
        body: JSON.stringify({ address: a, lang }),
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
      setOutputLang(lang);
      setPhase('done');
    } catch (e: any) {
      setError(e?.message ?? String(e));
      setPhase('idle');
    }
  }

  const loading = phase === 'fetching' || phase === 'analyzing';

  return (
    <main className="relative">
      {/* Subtle ruby grid background — scrolls with content for cohesion */}
      <div className="grid-bg fixed inset-0 pointer-events-none opacity-30" />

      <header className="relative max-w-6xl mx-auto px-6 pt-10 pb-8 flex items-center justify-between animate-fade-in">
        <div className="flex items-center gap-3">
          {/* Brand mark — small ruby gem with avatar */}
          <div className="relative w-10 h-10 rounded-xl overflow-hidden border border-ruby-700/60 shadow-ruby-glow">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/bastiar-avatar.jpg" alt="" className="w-full h-full object-cover" />
            <div className="absolute inset-0 ring-1 ring-inset ring-ruby-400/20 rounded-xl pointer-events-none" />
          </div>
          <div>
            <h1 className="font-display text-lg font-semibold tracking-wide leading-none">
              <span className="text-ink-50">Yarrr</span>
              <span className="text-ruby-400">.</span>
              <span className="text-ink-50">Tech</span>
            </h1>
            <p className="text-[10px] text-ink-500 font-mono uppercase tracking-[0.18em] mt-1">{t.taglineVersion}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher />
          <a href="https://github.com/AirdropLaura/yarrr-intel" target="_blank" rel="noreferrer" className="btn-ghost">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2.18c-3.2.7-3.87-1.36-3.87-1.36-.52-1.31-1.27-1.66-1.27-1.66-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.24 3.34.95.1-.74.4-1.24.72-1.53-2.55-.29-5.24-1.27-5.24-5.66 0-1.25.45-2.27 1.18-3.07-.12-.29-.51-1.45.11-3.02 0 0 .96-.31 3.16 1.17a10.97 10.97 0 0 1 5.74 0c2.2-1.48 3.16-1.17 3.16-1.17.62 1.57.23 2.73.11 3.02.74.8 1.18 1.82 1.18 3.07 0 4.4-2.69 5.36-5.25 5.65.41.36.78 1.07.78 2.16v3.21c0 .31.21.67.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z"/></svg>
            {t.github}
          </a>
        </div>
      </header>

      <section className="relative max-w-3xl mx-auto px-6 pt-8 pb-12 text-center">
        {/* Soft hero glow behind title — adds depth without being loud */}
        <div className="absolute inset-x-0 top-0 h-72 hero-glow pointer-events-none" />

        <span className="ruby-chip animate-fade-in">
          <span className="w-1.5 h-1.5 rounded-full bg-ruby-400 animate-subtle-pulse" />
          {t.betaBadge}
        </span>

        <h2 className="relative mt-6 text-4xl sm:text-5xl md:text-6xl font-display font-semibold leading-[1.05] tracking-tight gradient-text-ruby animate-fade-in-up">
          {t.heroTitleA}<br className="hidden sm:block" /> {t.heroTitleB}
        </h2>

        <p className="relative mt-5 text-ink-300 max-w-xl mx-auto leading-relaxed animate-fade-in-up-d2">
          {t.heroSub}
        </p>
      </section>

      {/* About / intro — short positioning + builder credit */}
      <section className="relative max-w-3xl mx-auto px-6 mb-10">
        <div className="glass rounded-2xl p-5 sm:p-6 flex flex-col sm:flex-row gap-4 items-start">
          <div className="shrink-0 w-14 h-14 rounded-xl overflow-hidden border-2 border-ruby-400/40 ring-2 ring-ruby-400/10 shadow-lg shadow-ruby-400/10">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src="/bastiar-avatar.jpg"
              alt="Bastiar — yarrr-node.com"
              width={56}
              height={56}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-mono uppercase tracking-wider text-ruby-400">
              {t.introHeading}
            </h3>
            <p className="mt-2 text-sm text-ink-200 leading-relaxed">
              {t.introBody}
            </p>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-mono text-ink-400">
              <span>{t.builtBy}</span>
              <span className="px-2 py-0.5 rounded-full bg-ruby-500/10 border border-ruby-500/30 text-ruby-300 font-semibold">
                {t.builtByName}
              </span>
              <span className="text-ink-500">· {t.builtByRole}</span>
              <a
                href="https://t.me/yarrr23"
                target="_blank"
                rel="noopener noreferrer"
                className="group inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-ruby-950/40 border border-ruby-800/50 text-ruby-300 hover:text-ruby-200 hover:bg-ruby-900/50 hover:border-ruby-600/60 transition-all duration-300"
                aria-label="Contact via Telegram @yarrr23"
                title="Telegram @yarrr23"
              >
                <svg className="w-3 h-3 transition-transform duration-300 group-hover:scale-110" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/>
                </svg>
                <span>Telegram</span>
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="relative max-w-3xl mx-auto px-6">
        <div className="glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-ruby-400/5">
          {/* Mode toggle: single vs multi-address */}
          <div className="mb-3 inline-flex rounded-full border border-ink-700/60 bg-ink-800/40 p-1">
            <button
              type="button"
              onClick={() => { setMode('single'); setError(null); }}
              className={`px-3 py-1 rounded-full text-xs font-mono uppercase tracking-wider transition-colors ${
                mode === 'single'
                  ? 'bg-ruby-400/20 text-ruby-400'
                  : 'text-ink-400 hover:text-ink-200'
              }`}
            >
              {t.modeSingle}
            </button>
            <button
              type="button"
              onClick={() => { setMode('multi'); setError(null); }}
              className={`px-3 py-1 rounded-full text-xs font-mono uppercase tracking-wider transition-colors ${
                mode === 'multi'
                  ? 'bg-ruby-400/20 text-ruby-400'
                  : 'text-ink-400 hover:text-ink-200'
              }`}
            >
              {t.modeMulti}
            </button>
          </div>

          {mode === 'single' ? (
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              className="input-base font-mono text-sm sm:text-base px-4 py-3 flex-1"
              placeholder={t.placeholder}
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
              {loading ? t.analyzing : t.analyze}
            </button>
          </div>
          ) : (
          <div className="flex flex-col gap-3">
            <textarea
              className="input-base font-mono text-sm px-4 py-3 min-h-[120px] resize-y"
              placeholder={t.multiPlaceholder}
              value={multiAddresses}
              onChange={(e) => setMultiAddresses(e.target.value)}
              spellCheck={false}
              autoComplete="off"
            />
            <div className="flex flex-col sm:flex-row gap-3 sm:items-center sm:justify-between">
              <span className="text-[11px] font-mono text-ink-500">
                {t.multiHint}
              </span>
              <button
                className="btn-primary px-6 py-3 whitespace-nowrap"
                onClick={() => analyzeMulti()}
                disabled={loading || !multiAddresses.trim()}
              >
                {loading ? t.analyzing : t.multiAnalyze}
              </button>
            </div>
          </div>
          )}

          <div className="mt-3 flex flex-wrap gap-2 items-center">
            <span className="text-[11px] font-mono uppercase tracking-wider text-ink-500 mr-1">{t.tryLabel}</span>
            {EXAMPLES.map((ex) => (
              <button
                key={ex.label}
                type="button"
                onClick={() => analyze(ex.address)}
                disabled={loading}
                className="group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-ink-800/60 border border-ink-700/60 text-xs font-mono hover:border-ruby-400/40 hover:text-ruby-400 transition-colors disabled:opacity-50"
              >
                <span className="font-semibold">{ex.label}</span>
                <span className="text-ink-500 group-hover:text-ruby-400/70">· {t[ex.hintKey]}</span>
              </button>
            ))}
          </div>

          {phase === 'fetching' && (
            <div className="mt-4 flex items-center gap-2 text-xs font-mono text-ink-400">
              <span className="w-1.5 h-1.5 rounded-full bg-ruby-400 animate-pulse" />
              {t.scanning}
            </div>
          )}
          {phase === 'analyzing' && (
            <div className="mt-4 flex items-center gap-2 text-xs font-mono text-ruby-400">
              <span className="w-1.5 h-1.5 rounded-full bg-ruby-400 animate-glow" />
              {t.interpreting}
            </div>
          )}
        </div>

        {error && (
          <div className="mt-5 glass rounded-xl p-4 border-red-500/30 text-red-300 text-sm">
            <strong className="font-semibold">{t.errorPrefix}</strong> {error}
          </div>
        )}

        {digest && <ReputationPanel digest={digest} />}
        {digest && address && <ClusterPanel address={address} />}
        {digest && <ArchetypePanel digest={digest} />}
        {digest && <TimelinePanel digest={digest} />}
        {digest && <TokensPanel digest={digest} />}
        {digest && <DigestPanel digest={digest} />}

        {(output || phase === 'analyzing') && (
          <article className="mt-6 glass rounded-2xl p-6 sm:p-8 shadow-2xl shadow-ruby-400/5">
            <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60 gap-3">
              <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.walletIntel}</h3>
              {phase === 'done' && address && output && (
                <ShareButton address={address} lang={lang} model="mimo-v2.5" analysis={output} />
              )}
            </header>
            <div className="prose-yarrr">
              {output ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{output}</ReactMarkdown>
              ) : (
                <div className="flex items-center gap-2 text-ink-400 text-sm">
                  <span className="w-2 h-2 rounded-full bg-ruby-400 animate-glow" />
                  {t.reasoning}
                </div>
              )}
            </div>
          </article>
        )}
      </section>

      <section className="relative max-w-3xl mx-auto px-6 mt-20">
        <h3 className="text-center font-mono text-xs uppercase tracking-wider text-ink-400 mb-6">
          {t.featuresHeading}
        </h3>
        <div className="grid sm:grid-cols-2 gap-3">
          {[
            [t.feat1Title, t.feat1Desc],
            [t.feat2Title, t.feat2Desc],
            [t.feat3Title, t.feat3Desc],
            [t.feat4Title, t.feat4Desc],
            [t.feat5Title, t.feat5Desc],
            [t.feat6Title, t.feat6Desc],
          ].map(([title, desc]) => (
            <div key={title} className="glass rounded-xl p-4">
              <div className="text-sm font-semibold text-ink-50">{title}</div>
              <div className="text-xs text-ink-400 mt-1 leading-relaxed">{desc}</div>
            </div>
          ))}
        </div>
      </section>

      <footer className="relative max-w-6xl mx-auto px-6 pt-24 pb-12">
        {/* Subtle hairline divider with center fade */}
        <div className="mb-8 h-px w-full bg-gradient-to-r from-transparent via-ruby-800/40 to-transparent" />

        <div className="flex flex-col items-center gap-3 text-center">
          {/* Wordmark */}
          <div className="flex items-baseline gap-1.5 font-display text-base tracking-wide">
            <span className="text-ink-200">yarrr</span>
            <span className="text-ruby-400">.</span>
            <span className="text-ink-200">tech</span>
          </div>

          {/* Tagline + builder credit */}
          <div className="text-[11px] font-mono uppercase tracking-[0.2em] text-ink-500">
            <span>{t.builtBy}</span>{' '}
            <span className="text-ruby-300">{t.builtByName}</span>
          </div>

          {/* Telegram contact — single, clean, premium */}
          <a
            href="https://t.me/yarrr23"
            target="_blank"
            rel="noopener noreferrer"
            className="group mt-1 inline-flex items-center gap-2 rounded-full px-3 py-1.5
                       bg-ruby-950/50 border border-ruby-800/40
                       text-[11px] font-mono text-ruby-300
                       hover:text-ruby-200 hover:border-ruby-600/60 hover:bg-ruby-900/50
                       transition-all duration-300"
            aria-label="Contact via Telegram @yarrr23"
            title="Telegram @yarrr23"
          >
            <svg className="w-3 h-3 transition-transform duration-300 group-hover:scale-110"
                 viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <path d="M9.78 18.65l.28-4.23 7.68-6.92c.34-.31-.07-.46-.52-.19L7.74 13.3 3.64 12c-.88-.25-.89-.86.2-1.3l15.97-6.16c.73-.33 1.43.18 1.15 1.3l-2.72 12.81c-.19.91-.74 1.13-1.5.71L12.6 16.3l-1.99 1.93c-.23.23-.42.42-.83.42z"/>
            </svg>
            <span>Telegram · @yarrr23</span>
          </a>

          {/* Powered by MiMo — model attribution */}
          <a
            href="https://mimo.xiaomi.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="group mt-2 inline-flex items-center gap-2 rounded-full px-3 py-1.5
                       bg-ink-950/40 border border-ink-700/40
                       text-[10px] font-mono uppercase tracking-[0.18em] text-ink-400
                       hover:text-ink-200 hover:border-ruby-700/40 hover:bg-ink-900/60
                       transition-all duration-300"
            aria-label="Powered by Xiaomi MiMo V2.5"
            title="Reasoning by Xiaomi MiMo V2.5"
          >
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-ruby-400/80 group-hover:bg-ruby-300 transition-colors" />
            <span>{t.poweredBy}</span>
            <span className="text-ruby-300">MiMo V2.5</span>
          </a>
        </div>
      </footer>
    </main>
  );
}

function TimelinePanel({ digest }: { digest: Digest }) {
  const { t } = useLang();
  const tl = digest.timeline;
  if (!tl || tl.length < 2) return null;

  // Normalize tx_count → 0..1 for bar height. Use log-scale because activity
  // bursts can be 100x quieter periods, and linear scaling makes the quiet
  // periods invisible.
  const maxCount = Math.max(...tl.map((p) => p.tx_count));
  const minHeight = 18;   // px — even quietest bucket should show something
  const maxHeight = 88;   // px

  const totalSpan = tl[tl.length - 1].end_ts - tl[0].start_ts;
  const t0 = tl[0].start_ts;

  function fmtDate(ts: number) {
    return new Date(ts * 1000).toLocaleDateString(undefined, { year: 'numeric', month: 'short' });
  }

  return (
    <article className="mt-6 glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-ruby-400/5">
      <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60 gap-3">
        <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.timelineTitle}</h3>
        <span className="text-[10px] font-mono text-ink-500">
          {fmtDate(tl[0].start_ts)} → {fmtDate(tl[tl.length - 1].end_ts)}
        </span>
      </header>

      <div className="relative">
        {/* Horizontal time axis with bars positioned by relative time. */}
        <div className="relative w-full" style={{ height: `${maxHeight + 24}px` }}>
          {tl.map((p, i) => {
            const heightFrac = maxCount > 0
              ? Math.max(Math.log(1 + p.tx_count) / Math.log(1 + maxCount), 0.18)
              : 0;
            const heightPx = Math.round(minHeight + heightFrac * (maxHeight - minHeight));
            const leftPct = ((p.start_ts - t0) / totalSpan) * 100;
            const widthPct = Math.max(((p.end_ts - p.start_ts) / totalSpan) * 100 - 0.4, 4);
            const tone =
              p.error_rate >= 0.2
                ? 'bg-red-400/40 border-red-400/60 hover:bg-red-400/60'
                : p.dominant_category === 'bridge'
                ? 'bg-ruby-400/40 border-ruby-400/70 hover:bg-ruby-400/70'
                : p.dominant_category === 'swap' || p.dominant_category === 'dex'
                ? 'bg-ruby-400/30 border-ruby-400/50 hover:bg-ruby-400/50'
                : 'bg-ink-500/40 border-ink-500/60 hover:bg-ink-500/60';
            return (
              <div
                key={i}
                title={`${fmtDate(p.start_ts)} → ${fmtDate(p.end_ts)} · ${p.tx_count} tx · ${p.chains.join(', ')}${p.dominant_category ? ' · ' + p.dominant_category : ''}`}
                className={`absolute bottom-6 rounded-md border transition-colors cursor-help ${tone}`}
                style={{
                  left: `${leftPct}%`,
                  width: `${widthPct}%`,
                  height: `${heightPx}px`,
                }}
              />
            );
          })}
          {/* Time axis ticks: first, middle, last */}
          <div className="absolute left-0 bottom-0 text-[10px] font-mono text-ink-500">
            {fmtDate(tl[0].start_ts)}
          </div>
          <div className="absolute left-1/2 -translate-x-1/2 bottom-0 text-[10px] font-mono text-ink-500">
            {fmtDate(t0 + Math.floor(totalSpan / 2))}
          </div>
          <div className="absolute right-0 bottom-0 text-[10px] font-mono text-ink-500">
            {fmtDate(tl[tl.length - 1].end_ts)}
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-3 mt-3 text-[10px] font-mono text-ink-400">
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-ruby-400/40 border border-ruby-400/70" />
          {t.timelineLegendBridge}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-ruby-400/30 border border-ruby-400/50" />
          {t.timelineLegendDex}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-ink-500/40 border border-ink-500/60" />
          {t.timelineLegendOther}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-3 h-3 rounded-sm bg-red-400/40 border border-red-400/60" />
          {t.timelineLegendError}
        </span>
      </div>
    </article>
  );
}

function TokensPanel({ digest }: { digest: Digest }) {
  const { t } = useLang();
  const tk = digest.tokens;
  const fc = digest.failed_tx_clusters;

  // Skip rendering if there's literally nothing to show — keeps the UI focused
  // on archetype + analyst output for wallets without token activity.
  const hasTokenSignal =
    tk.stablecoin_volume_usd > 0 ||
    tk.distinct_erc20 > 0 ||
    tk.distinct_nft_collections > 0 ||
    tk.spam_nft_count > 0 ||
    tk.holds_lp_tokens ||
    tk.holds_lst_tokens;

  if (!hasTokenSignal && fc.length === 0) return null;

  return (
    <article className="mt-6 glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-ruby-400/5 space-y-5">
      {hasTokenSignal && (
        <section>
          <header className="flex items-center justify-between mb-3 pb-2 border-b border-ink-700/60">
            <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.tokensTitle}</h3>
          </header>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 mb-3">
            {tk.stablecoin_volume_usd > 0 && (
              <TokenStat
                label={t.tokensStable}
                value={`$${formatBalance(tk.stablecoin_volume_usd)}`}
                hint={tk.distinct_stablecoins.join(' · ') || '—'}
              />
            )}
            {tk.distinct_erc20 > 0 && (
              <TokenStat label={t.tokensERC20} value={tk.distinct_erc20.toString()} hint="" />
            )}
            {tk.distinct_nft_collections > 0 && (
              <TokenStat label={t.tokensNFT} value={tk.distinct_nft_collections.toString()} hint="" />
            )}
            {tk.spam_nft_count > 0 && (
              <TokenStat
                label={t.tokensSpam}
                value={tk.spam_nft_count.toString()}
                hint=""
                tone="warn"
              />
            )}
          </div>

          {(tk.holds_lp_tokens || tk.holds_lst_tokens) && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {tk.holds_lp_tokens && (
                <span className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-ruby-400/10 border border-ruby-400/30 text-ruby-400">
                  {t.tokensLP}
                </span>
              )}
              {tk.holds_lst_tokens && (
                <span className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-ruby-400/10 border border-ruby-400/30 text-ruby-400">
                  {t.tokensLST}
                </span>
              )}
            </div>
          )}

          {tk.spam_nft_examples.length > 0 && (
            <div>
              <SectionLabel>{t.tokensSpam}</SectionLabel>
              <ul className="space-y-0.5">
                {tk.spam_nft_examples.slice(0, 5).map((e, i) => (
                  <li key={i} className="text-[12px] font-mono text-ink-300 truncate">
                    <span className="text-ink-500">·</span> {e}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {fc.length > 0 && (
        <section>
          <header className="flex items-center justify-between mb-2 pb-2 border-b border-ink-700/60">
            <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.failedClustersTitle}</h3>
            <span className="text-[10px] font-mono text-ink-500">{fc.length}</span>
          </header>
          <p className="text-[11px] text-ink-400 mb-3 leading-relaxed">{t.failedClustersHint}</p>
          <ul className="space-y-1.5">
            {fc.map((c, i) => (
              <li
                key={i}
                className="flex items-center justify-between gap-2 px-3 py-1.5 rounded-lg bg-red-500/5 border border-red-500/20"
              >
                <div className="min-w-0">
                  <div className="text-xs font-semibold text-red-300">
                    {c.method ? <code className="font-mono">{c.method}</code> : '(transfer)'}
                    <span className="ml-2 text-ink-400 font-normal">on {c.chain}</span>
                  </div>
                  <div className="text-[10px] font-mono text-ink-500 truncate">
                    → {c.target.slice(0, 10)}…{c.target.slice(-6)}
                  </div>
                </div>
                <span className="text-xs font-mono text-red-300 shrink-0">{c.count}× revert</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </article>
  );
}

function TokenStat({
  label,
  value,
  hint,
  tone = 'normal',
}: {
  label: string;
  value: string;
  hint: string;
  tone?: 'normal' | 'warn';
}) {
  return (
    <div className="px-3 py-2 rounded-lg bg-ink-800/60 border border-ink-700/60">
      <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500">{label}</div>
      <div className={`text-sm font-mono mt-0.5 ${tone === 'warn' ? 'text-red-300' : 'text-ruby-400'}`}>{value}</div>
      {hint && <div className="text-[10px] font-mono text-ink-500 mt-0.5 truncate">{hint}</div>}
    </div>
  );
}

function ClusterPanel({ address }: { address: string }) {
  const { t } = useLang();
  const [report, setReport] = useState<{
    has_cluster: boolean;
    distinct_wallets: number;
    distinct_sources: number;
    matches: Array<{
      wallet: string;
      source_addr: string;
      source_type: string;
      chain: string;
      ts: number;
      delta_seconds: number;
    }>;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/cluster/${address}`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => { if (!cancelled && data) setReport(data); })
      .catch(() => { /* silent — cluster is supplementary */ });
    return () => { cancelled = true; };
  }, [address]);

  // Hide entirely until we have a real cluster — first-time wallets shouldn't
  // see an empty "no cluster" panel cluttering the UI.
  if (!report || !report.has_cluster) return null;

  function fmtDelta(secs: number): string {
    if (secs < 60) return `${secs}s`;
    if (secs < 3600) return `${Math.round(secs / 60)}m`;
    return `${Math.round(secs / 3600)}h`;
  }
  function shortAddr(a: string) { return `${a.slice(0, 6)}…${a.slice(-4)}`; }

  return (
    <article className="mt-6 glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-ruby-400/5">
      <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60 gap-3">
        <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.clusterTitle}</h3>
        <span className="text-[10px] font-mono text-ink-500">{t.clusterSubtitle}</span>
      </header>

      <div className="flex flex-wrap gap-4 mb-4 text-xs">
        <div>
          <SectionLabel>{t.clusterSiblings}</SectionLabel>
          <div className="font-mono text-2xl text-ruby-400 font-bold">{report.distinct_wallets}</div>
        </div>
        <div>
          <SectionLabel>{t.clusterSources}</SectionLabel>
          <div className="font-mono text-2xl text-ink-200">{report.distinct_sources}</div>
        </div>
      </div>

      <SectionLabel>{t.clusterMatches}</SectionLabel>
      <ul className="space-y-1.5">
        {report.matches.slice(0, 8).map((m, i) => (
          <li
            key={i}
            className="flex items-center justify-between gap-3 text-xs px-3 py-2 rounded-md bg-ink-800/40 border border-ink-700/40"
          >
            <code className="font-mono text-ink-200 truncate">{shortAddr(m.wallet)}</code>
            <div className="flex items-center gap-2 shrink-0 text-[10px] font-mono">
              <span className={`px-2 py-0.5 rounded-full ${
                m.source_type === 'cex'
                  ? 'bg-ruby-400/10 text-ruby-400 border border-ruby-400/30'
                  : 'bg-ink-700/40 text-ink-300 border border-ink-600/40'
              }`}>
                {m.source_type}
              </span>
              <span className="text-ink-500">{m.chain}</span>
              <span className="text-ink-500">±{fmtDelta(m.delta_seconds)}</span>
            </div>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-[10px] font-mono text-ink-500 italic">
        {t.clusterDisclaimer}
      </p>
    </article>
  );
}

function ReputationPanel({ digest }: { digest: Digest }) {
  const { t } = useLang();
  const rep = digest.reputation;
  if (!rep) return null;

  // Bucket → color + label localization
  const bucketColors: Record<Reputation['bucket'], string> = {
    high: 'text-ruby-400 border-ruby-400/60 bg-ruby-400/10',
    good: 'text-ruby-500 border-ruby-500/50 bg-ruby-500/10',
    neutral: 'text-ink-200 border-ink-500/50 bg-ink-700/40',
    low: 'text-ink-400 border-ink-500/40 bg-ink-800/40',
    poor: 'text-red-400 border-red-400/40 bg-red-400/10',
  };
  const bucketLabel: Record<Reputation['bucket'], string> = {
    high: t.repBucketHigh,
    good: t.repBucketGood,
    neutral: t.repBucketNeutral,
    low: t.repBucketLow,
    poor: t.repBucketPoor,
  };

  // Top 5 contributions sorted by absolute magnitude (most influential first)
  const contribs = [...rep.contributions]
    .filter((c) => c.label !== 'baseline' && c.delta !== 0)
    .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
    .slice(0, 6);

  // Score arc — semicircle gauge
  const radius = 70;
  const circumference = Math.PI * radius;
  const arcLen = (rep.score / 100) * circumference;

  const arcColor =
    rep.bucket === 'high'
      ? '#fbbf24'
      : rep.bucket === 'good'
      ? '#f59e0b'
      : rep.bucket === 'neutral'
      ? '#9ca3af'
      : rep.bucket === 'low'
      ? '#6b7280'
      : '#f87171';

  return (
    <article className="mt-6 glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-ruby-400/5">
      <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60 gap-3">
        <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.reputationTitle}</h3>
        <span className="text-[10px] font-mono text-ink-500">{t.reputationSubtitle}</span>
      </header>

      <div className="flex flex-col sm:flex-row gap-6 items-start">
        {/* Score gauge */}
        <div className="flex-shrink-0 mx-auto sm:mx-0">
          <svg width="170" height="100" viewBox="0 0 170 100">
            {/* Track */}
            <path
              d={`M 15 85 A ${radius} ${radius} 0 0 1 155 85`}
              fill="none"
              stroke="#202430"
              strokeWidth="10"
              strokeLinecap="round"
            />
            {/* Filled arc */}
            <path
              d={`M 15 85 A ${radius} ${radius} 0 0 1 155 85`}
              fill="none"
              stroke={arcColor}
              strokeWidth="10"
              strokeLinecap="round"
              strokeDasharray={`${arcLen} ${circumference}`}
            />
            <text
              x="85"
              y="68"
              textAnchor="middle"
              fontFamily="monospace"
              fontWeight="700"
              fontSize="36"
              fill={arcColor}
            >
              {rep.score}
            </text>
            <text
              x="85"
              y="86"
              textAnchor="middle"
              fontFamily="monospace"
              fontSize="10"
              fill="#6e7387"
            >
              / 100
            </text>
          </svg>
          <div className="text-center mt-1">
            <span
              className={`inline-block px-3 py-1 rounded-full text-[10px] font-mono uppercase tracking-wider border ${bucketColors[rep.bucket]}`}
            >
              {bucketLabel[rep.bucket]}
            </span>
          </div>
        </div>

        {/* Contributions */}
        <div className="flex-1 min-w-0 w-full">
          <SectionLabel>{t.repContribTitle}</SectionLabel>
          {contribs.length === 0 ? (
            <p className="text-xs text-ink-500 italic">{t.repNoContribs}</p>
          ) : (
            <ul className="space-y-1.5">
              {contribs.map((c, i) => (
                <li
                  key={i}
                  className="flex items-baseline justify-between gap-3 text-xs px-3 py-1.5 rounded-md bg-ink-800/40 border border-ink-700/40"
                >
                  <span className="font-mono text-ink-300 truncate">{c.label}</span>
                  <span className="flex items-baseline gap-2 shrink-0">
                    <span className="text-ink-500 hidden sm:inline truncate max-w-[200px]">
                      {c.detail}
                    </span>
                    <span
                      className={`font-mono font-semibold ${
                        c.delta > 0 ? 'text-ruby-400' : 'text-red-400'
                      }`}
                    >
                      {c.delta > 0 ? '+' : ''}
                      {c.delta}
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </article>
  );
}

function ArchetypePanel({ digest }: { digest: Digest }) {
  const { t } = useLang();
  return (
    <article className="mt-6 glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-ruby-400/5">
      <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60 gap-3">
        <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.archetypeTitle}</h3>
        <div className="flex flex-col items-end min-w-0">
          {digest.name && (
            <span className="text-sm font-semibold text-ink-50 truncate max-w-[14rem]">
              {digest.name}
            </span>
          )}
          <code className="text-[10px] text-ink-500 font-mono">{shortAddr(digest.address)}</code>
        </div>
      </header>

      {digest.archetypes.length === 0 ? (
        <p className="text-sm text-ink-400 leading-relaxed">{t.archetypeNone}</p>
      ) : (
        <div className="space-y-3">
          {digest.archetypes.map((a) => (
            <div
              key={a.name}
              className={`rounded-xl border p-3.5 ${BUCKET_STYLES[a.bucket]}`}
            >
              <div className="flex items-center justify-between gap-3 mb-1.5">
                <code className="font-mono font-semibold text-sm">{a.name}</code>
                <div className="flex items-center gap-2 text-[11px] font-mono">
                  <span className="uppercase tracking-wider opacity-80">{bucketLabel(a.bucket, t)}</span>
                  <span className="px-2 py-0.5 rounded-full bg-ink-900/60 border border-ink-700">
                    {a.confidence.toFixed(2)}
                  </span>
                </div>
              </div>
              {a.evidence.length > 0 && (
                <ul className="text-[12px] text-ink-200/90 space-y-0.5 mt-1.5">
                  {a.evidence.map((e, i) => (
                    <li key={i} className="flex gap-1.5">
                      <span className="text-ink-500">·</span>
                      <span>{e}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {digest.funding_source && (
        <div className="mt-5 pt-4 border-t border-ink-700/60">
          <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500 mb-2">
            {t.fundingTitle}
          </div>
          <div className="flex items-start gap-2">
            <span className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-ruby-400/10 border border-ruby-400/30 text-ruby-400 shrink-0">
              {fundingLabel(digest.funding_source, t)}
            </span>
            {digest.funding_evidence.length > 0 && (
              <span className="text-[12px] text-ink-300 leading-relaxed">
                {digest.funding_evidence.join(' · ')}
              </span>
            )}
          </div>
        </div>
      )}
    </article>
  );
}

function HoldingCard({ h, tier }: { h: TokenHolding; tier: 'trusted' | 'uncertain' }) {
  // Visual treatment per tier — green for trusted, amber for uncertain.
  const isTrusted = tier === 'trusted';
  const tierBorder = isTrusted ? 'border-emerald-800/40' : 'border-amber-800/40';
  const tierBg = isTrusted ? 'bg-emerald-950/20' : 'bg-amber-950/15';
  const scoreColor = isTrusted ? 'text-emerald-300' : 'text-amber-300';
  const score = h.trust_score ?? (isTrusted ? 90 : 50);

  return (
    <details
      className={`group rounded-lg border ${tierBorder} ${tierBg} transition-colors`}
    >
      <summary className="cursor-pointer select-none px-3 py-2 list-none flex items-center justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-sm font-mono font-semibold truncate">
              {h.symbol || '???'}
            </span>
            {h.is_stablecoin && (
              <span className="px-1 py-px rounded bg-emerald-900/40 border border-emerald-700/40 text-[9px] font-mono text-emerald-300 uppercase">
                stable
              </span>
            )}
            {h.is_lp && (
              <span className="px-1 py-px rounded bg-blue-900/40 border border-blue-700/40 text-[9px] font-mono text-blue-300 uppercase">
                LP
              </span>
            )}
            {h.is_lst && (
              <span className="px-1 py-px rounded bg-purple-900/40 border border-purple-700/40 text-[9px] font-mono text-purple-300 uppercase">
                LST
              </span>
            )}
          </div>
          <div className={`text-[10px] font-mono uppercase tracking-wider ${CHAIN_COLORS[h.chain] ?? 'text-ink-400'}`}>
            {h.chain}
          </div>
        </div>
        <div className="text-right shrink-0">
          <div className="text-sm font-mono">{formatTokenAmount(h.amount)}</div>
          <div className={`text-[10px] font-mono ${scoreColor} mt-0.5`}>
            {score}/100
          </div>
        </div>
      </summary>

      {/* Verdict + reasons reveal */}
      {(h.trust_summary || (h.trust_reasons && h.trust_reasons.length > 0)) && (
        <div className="px-3 pb-3 pt-1 border-t border-ink-700/40 mt-1">
          {h.trust_summary && (
            <div className="text-[12px] text-ink-200 leading-relaxed mb-1.5">
              {h.trust_summary}
            </div>
          )}
          {h.trust_reasons && h.trust_reasons.length > 0 && (
            <ul className="text-[11px] text-ink-400 space-y-0.5 ml-3 list-disc">
              {h.trust_reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </details>
  );
}

function DigestPanel({ digest }: { digest: Digest }) {
  const { t } = useLang();
  // Show balances for ALL active chains (mainnet + testnet) — testnet wallets
  // need to see their faucet balance just like mainnet wallets need to see ETH.
  const mainnetBalances = digest.mainnet_chains_active
    .map((c) => [c, digest.balances_by_chain[c] || 0] as const)
    .filter(([, bal]) => bal > 0);
  const testnetBalances = digest.testnet_chains_active
    .map((c) => [c, digest.balances_by_chain[c] || 0] as const)
    .filter(([, bal]) => bal > 0);

  const holdings = digest.tokens?.holdings || [];
  // Three-tier classification from backend trust engine. Falls back to
  // legacy is_spam flag if trust_tier is missing (older API responses).
  const trustedHoldings = holdings.filter((h) => h.trust_tier === 'trusted');
  const uncertainHoldings = holdings.filter(
    (h) => h.trust_tier === 'uncertain' || (!h.trust_tier && !h.is_spam),
  );
  const spamHoldings = holdings.filter(
    (h) => h.trust_tier === 'spam' || (!h.trust_tier && h.is_spam),
  );
  const trustSummary = digest.tokens?.holdings_trust;

  return (
    <article className="mt-6 glass rounded-2xl p-5 sm:p-6 shadow-2xl shadow-ruby-400/5">
      <header className="flex items-center justify-between mb-4 pb-3 border-b border-ink-700/60">
        <h3 className="font-mono text-sm uppercase tracking-wider text-ruby-400">{t.digestTitle}</h3>
        <code className="text-[11px] text-ink-500 font-mono truncate max-w-[60%]">
          {digest.address}
        </code>
      </header>

      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-4">
        <Stat
          label={t.statTotalTx}
          value={
            digest.total_internal_txs && digest.total_internal_txs > 0
              ? `${digest.total_txs} + ${digest.total_internal_txs}i`
              : digest.total_txs.toString()
          }
        />
        <Stat label={t.statErrorRate}  value={`${(digest.error_rate * 100).toFixed(1)}%`} tone={digest.error_rate > 0.15 ? 'warn' : 'normal'} />
        <Stat label={t.statAge}        value={digest.wallet_age_days ? formatAge(digest.wallet_age_days, t) : '—'} />
        <Stat label={t.statFirstSeen}  value={digest.first_tx_ts ? new Date(digest.first_tx_ts * 1000).toLocaleDateString() : '—'} />
        <Stat label={t.statLastSeen}   value={ageString(digest.last_tx_ts, t)} />
      </div>

      {digest.partial_chains && digest.partial_chains.length > 0 && (
        <div className="mb-4 rounded border border-amber-700/50 bg-amber-950/30 px-3 py-2 text-[11px] text-amber-200/90 font-mono">
          <span className="text-amber-400 mr-2">⚠</span>
          {t.partialWarning.replace('{n}', digest.partial_chains.length.toString())}
          <span className="text-ink-500"> ({digest.partial_chains.slice(0, 6).join(', ')}{digest.partial_chains.length > 6 ? '…' : ''})</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
        <ChainList
          label={`${t.chainsMainnet} (${digest.mainnet_chains_active.length})`}
          chains={digest.mainnet_chains_active}
          accent="gold"
        />
        {digest.testnet_chains_active.length > 0 && (
          <ChainList
            label={`${t.chainsTestnet} (${digest.testnet_chains_active.length})`}
            chains={digest.testnet_chains_active}
            accent="ink"
          />
        )}
      </div>

      {(mainnetBalances.length > 0 || testnetBalances.length > 0) && (
        <div className="mb-4">
          <SectionLabel>{t.nativeBalances}</SectionLabel>
          {mainnetBalances.length > 0 && (
            <div className="mb-3">
              <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500 mb-1.5">
                {t.chainsMainnet}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {mainnetBalances.map(([chain, bal]) => (
                  <div key={chain} className="px-3 py-2 rounded-lg bg-ink-800/60 border border-ink-700/60">
                    <div className={`text-[11px] font-mono uppercase tracking-wider ${CHAIN_COLORS[chain] ?? 'text-ink-300'}`}>{chain}</div>
                    <div className="text-sm font-mono mt-0.5">{formatBalance(bal)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
          {testnetBalances.length > 0 && (
            <div>
              <div className="text-[10px] font-mono uppercase tracking-wider text-ink-500 mb-1.5">
                {t.chainsTestnet}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                {testnetBalances.map(([chain, bal]) => (
                  <div key={chain} className="px-3 py-2 rounded-lg bg-ink-800/40 border border-ink-700/40">
                    <div className="text-[11px] font-mono uppercase tracking-wider text-ink-400">{chain}</div>
                    <div className="text-sm font-mono mt-0.5 text-ink-200">{formatBalance(bal)}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* === Asset trust & holdings (Phase 4) ============================
           Three sections: Trusted / Low Confidence / Hidden Spam.
           Each token reveals its plain-English verdict + reasons on click. */}
      {(trustedHoldings.length + uncertainHoldings.length + spamHoldings.length) > 0 && (
        <div className="mb-5">
          <SectionLabel>
            {t.assetTrustTitle}
            <span className="text-ink-500 font-normal text-[10px] ml-1.5 normal-case tracking-normal">
              {t.assetTrustHint}
            </span>
          </SectionLabel>

          {/* Trust headline — one-line investigator verdict */}
          {trustSummary?.headline && (
            <div className="mb-3 px-3 py-2 rounded-lg bg-ink-800/40 border border-ruby-900/30 text-[12px] text-ink-200 leading-relaxed italic">
              {trustSummary.headline}
            </div>
          )}

          {/* Trusted Assets — verified blue chips, real economic value */}
          {trustedHoldings.length > 0 && (
            <div className="mb-3">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-emerald-400">
                  {t.trustedAssets}
                </span>
                <span className="text-[10px] font-mono text-ink-500">
                  {trustedHoldings.length}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {trustedHoldings.map((h, i) => (
                  <HoldingCard key={`tr-${h.chain}-${h.contract}-${i}`} h={h} tier="trusted" />
                ))}
              </div>
            </div>
          )}

          {/* Low Confidence — uncertain, value cannot be confirmed */}
          {uncertainHoldings.length > 0 && (
            <div className="mb-3">
              <div className="flex items-center gap-2 mb-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
                <span className="text-[10px] font-mono uppercase tracking-[0.18em] text-amber-300">
                  {t.uncertainAssets}
                </span>
                <span className="text-[10px] font-mono text-ink-500">
                  {uncertainHoldings.length}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {uncertainHoldings.map((h, i) => (
                  <HoldingCard key={`un-${h.chain}-${h.contract}-${i}`} h={h} tier="uncertain" />
                ))}
              </div>
            </div>
          )}

          {/* Hidden Spam — collapsed by default */}
          {spamHoldings.length > 0 && (
            <details className="rounded-lg border border-ink-700/40 bg-ink-900/30">
              <summary className="cursor-pointer select-none px-3 py-2 text-[11px] font-mono text-ink-400 hover:text-ink-200 transition-colors flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-ink-500" />
                <span className="uppercase tracking-[0.18em]">{t.spamAssets}</span>
                <span className="text-ink-500">{spamHoldings.length}</span>
                <span className="text-ink-600 ml-auto text-[10px] normal-case">
                  {t.spamHint}
                </span>
              </summary>
              <div className="px-3 pb-3 pt-1 grid grid-cols-1 sm:grid-cols-2 gap-1.5">
                {spamHoldings.map((h, i) => (
                  <div
                    key={`sp-${h.chain}-${h.contract}-${i}`}
                    className="text-[11px] font-mono text-ink-500 truncate"
                    title={h.trust_summary || `${h.symbol} on ${h.chain}`}
                  >
                    <span className={`uppercase tracking-wider ${CHAIN_COLORS[h.chain] ?? 'text-ink-600'}`}>
                      {h.chain}
                    </span>
                    {' · '}
                    <span className="text-ink-400">{h.symbol || '???'}</span>
                    {' '}
                    <span className="text-ink-600">{formatTokenAmount(h.amount)}</span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}

      {Object.keys(digest.activity_categories).length > 0 && (
        <div className="mb-4">
          <SectionLabel>{t.activityCategories}</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(digest.activity_categories).map(([cat, n]) => (
              <span key={cat} className="px-2 py-0.5 rounded-full bg-ink-800/60 border border-ink-700/60 text-[11px] font-mono">
                {cat} <span className="text-ruby-400 font-semibold">{n}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {digest.flags.length > 0 && (
        <div className="mb-4">
          <SectionLabel>{t.heuristicFlags}</SectionLabel>
          <div className="flex flex-wrap gap-1.5">
            {digest.flags.map((f) => (
              <span key={f} className="px-2 py-0.5 rounded-full text-[11px] font-mono bg-ruby-400/10 border border-ruby-400/30 text-ruby-400">
                {f}
              </span>
            ))}
          </div>
        </div>
      )}

      {digest.top_contracts.length > 0 && (
        <div>
          <SectionLabel>{t.topContracts}</SectionLabel>
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
                <span className="text-xs font-mono text-ruby-400 shrink-0">{c.hits}×</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function ChainList({ label, chains, accent }: { label: string; chains: string[]; accent: 'gold' | 'ink' }) {
  if (chains.length === 0) return null;
  return (
    <div>
      <SectionLabel>{label}</SectionLabel>
      <div className="flex flex-wrap gap-1.5">
        {chains.map((c) => (
          <span
            key={c}
            className={`px-2 py-0.5 rounded-full text-[11px] font-mono border ${
              accent === 'gold'
                ? `bg-ruby-400/5 border-ruby-400/20 ${CHAIN_COLORS[c] ?? 'text-ruby-400'}`
                : 'bg-ink-800/60 border-ink-700 text-ink-300'
            }`}
          >
            {c}
          </span>
        ))}
      </div>
    </div>
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

function ShareButton({
  address,
  lang,
  model,
  analysis,
}: {
  address: string;
  lang: string;
  model: string;
  analysis: string;
}) {
  const { t } = useLang();
  const [state, setState] = useState<'idle' | 'sharing' | 'copied' | 'error'>('idle');

  async function share() {
    if (state === 'sharing') return;
    setState('sharing');
    try {
      const res = await fetch('/api/share', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ address, lang, model, analysis }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      // The share URL we hand to the user goes through the backend HTML route
      // so social previews work. The local URL bar update stays on /a/?sid=
      // because that's the SPA-friendly path; navigating to /a/<id>/ would
      // hit the backend and force a full reload.
      const url = `${window.location.origin}/a/${data.id}/`;
      try {
        await navigator.clipboard.writeText(url);
      } catch {
        // Some browsers block clipboard in non-https contexts. We still
        // surface the URL via the shareCopied state.
      }
      setState('copied');
      window.history.pushState({}, '', `/a/?sid=${data.id}`);
      setTimeout(() => setState('idle'), 2500);
    } catch (e) {
      setState('error');
      setTimeout(() => setState('idle'), 2500);
    }
  }

  return (
    <button
      type="button"
      onClick={share}
      disabled={state === 'sharing'}
      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-mono transition-colors disabled:opacity-50 ${
        state === 'copied'
          ? 'bg-ruby-400 text-ink-900 border border-ruby-400'
          : 'bg-ruby-400/10 text-ruby-400 border border-ruby-400/30 hover:bg-ruby-400/20'
      }`}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="18" cy="5" r="3" />
        <circle cx="6" cy="12" r="3" />
        <circle cx="18" cy="19" r="3" />
        <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
        <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
      </svg>
      {state === 'copied' ? t.shareCopied : state === 'error' ? t.shareError : t.shareBtn}
    </button>
  );
}
