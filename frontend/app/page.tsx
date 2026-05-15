'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

const PRESET_NETWORKS = [
  // Categories
  'Cosmos SDK / CometBFT',
  'EVM (geth / erigon / reth)',
  'Substrate',
  'Foundry / Hardhat',
  'MetaMask / Playwright',
  'Docker / systemd',
  'npm / pnpm / yarn',
  'Python / pip',
  // Networks the user often interacts with
  'nesa-node',
  'tempo-node',
  'inri-installer',
  'Other',
];

const EXAMPLES: { label: string; category: string; text: string }[] = [
  {
    label: 'Node panic',
    category: 'node',
    text: `nesa-node[12345]: 2026-05-15 19:42:11 ERROR: failed to connect to peer: dial tcp 35.x.x.x:26656: i/o timeout
nesa-node[12345]: 2026-05-15 19:42:14 ERROR: consensus state not initialized
nesa-node[12345]: 2026-05-15 19:42:14 panic: runtime error: invalid memory address or nil pointer dereference`,
  },
  {
    label: 'Tx revert',
    category: 'tx',
    text: `Error: cannot estimate gas; transaction may fail or may require manual gas limit
   reason: execution reverted: ERC20: transfer amount exceeds allowance
   method: claim(uint256,bytes32[])
   from: 0x85B395f1...0957
   to: 0x000000000022D473030F116dDEE9F6B43aC78BA3 (Permit2)
   value: 0`,
  },
  {
    label: 'Mint revert',
    category: 'mint',
    text: `Error: execution reverted (unknown custom error)
selector: 0x82b42900   // SaleNotActive()
chain: Base Sepolia
contract: 0x4f...e91 (PixelPunk NFT)
caller: 0x85B395f1...0957
attempted call: mint(uint256 quantity = 1) value = 0.001 ETH`,
  },
  {
    label: 'Faucet stuck',
    category: 'faucet',
    text: `POST https://faucet.example.io/api/claim
{"error":"rate_limit_exceeded","detail":"Address 0x85B3... has claimed within the last 24h. Try again in 19h 22m."}

Note: I switched IP via VPN but the cooldown is still being applied.`,
  },
  {
    label: 'MetaMask popup',
    category: 'wallet',
    text: `playwright._impl._errors.TimeoutError: locator.click: Timeout 30000ms exceeded.
Call log:
  - waiting for locator('button:has-text("Confirm")')
  - locator resolved to <button data-testid="page-container-footer-next">…</button>
  - element is not visible
URL: chrome-extension://nkbihfbeogaeaoehlefnkodbefgpgknn/popup.html
Action: signing eth_sendTransaction on Base Sepolia`,
  },
  {
    label: 'Docker',
    category: 'docker',
    text: `nesa-validator | Error response from daemon: driver failed programming external connectivity on endpoint nesa-validator
nesa-validator | (a3b…ed4): Bind for 0.0.0.0:26656 failed: port is already allocated
docker compose up: exit status 1`,
  },
];

const PLACEHOLDER = `Paste any failure: panic trace, revert reason, RPC error, faucet response, MetaMask timeout, Docker log, dependency conflict, smart contract error...

Don't worry about formatting. We read messy paste fine.`;

export default function Home() {
  const [text, setText] = useState('');
  const [network, setNetwork] = useState('');
  const [osName, setOsName] = useState('Ubuntu 24.04');
  const [extra, setExtra] = useState('');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [usage, setUsage] = useState<{ total_tokens?: number; reasoning_tokens?: number; latency_seconds?: number } | null>(null);

  function loadExample(idx: number) {
    setText(EXAMPLES[idx].text);
    setOutput('');
    setError(null);
  }

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
            <p className="text-xs text-ink-400 font-mono">v0.2 · powered by MiMo V2.5</p>
          </div>
        </div>
        <a href="https://github.com/AirdropLaura/yarrr-tech" target="_blank" rel="noreferrer" className="btn-ghost">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .5C5.65.5.5 5.65.5 12c0 5.08 3.29 9.39 7.86 10.91.58.1.79-.25.79-.56v-2.18c-3.2.7-3.87-1.36-3.87-1.36-.52-1.31-1.27-1.66-1.27-1.66-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.18 1.76 1.18 1.02 1.75 2.69 1.24 3.34.95.1-.74.4-1.24.72-1.53-2.55-.29-5.24-1.27-5.24-5.66 0-1.25.45-2.27 1.18-3.07-.12-.29-.51-1.45.11-3.02 0 0 .96-.31 3.16 1.17a10.97 10.97 0 0 1 5.74 0c2.2-1.48 3.16-1.17 3.16-1.17.62 1.57.23 2.73.11 3.02.74.8 1.18 1.82 1.18 3.07 0 4.4-2.69 5.36-5.25 5.65.41.36.78 1.07.78 2.16v3.21c0 .31.21.67.8.56C20.21 21.39 23.5 17.08 23.5 12 23.5 5.65 18.35.5 12 .5z"/></svg>
          GitHub
        </a>
      </header>

      <section className="relative max-w-3xl mx-auto px-6 pt-8 pb-10 text-center">
        <span className="inline-block px-3 py-1 text-[11px] font-mono font-semibold uppercase tracking-wider text-gold-400 border border-gold-400/30 rounded-full bg-gold-400/5">
          Free during beta
        </span>
        <h2 className="mt-5 text-4xl sm:text-5xl font-bold leading-tight tracking-tight bg-gradient-to-br from-ink-50 to-gold-400 bg-clip-text text-transparent">
          AI co-pilot for<br className="hidden sm:block" /> Web3 operators.
        </h2>
        <p className="mt-4 text-ink-300 max-w-xl mx-auto">
          Testnet runners, validators, and airdrop builders — paste any failure and get the root cause and exact fix.
        </p>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-1.5 text-[11px] font-mono text-ink-400">
          {[
            'node logs',
            'RPC errors',
            'tx reverts',
            'MetaMask',
            'faucets',
            'bridge / swap / mint',
            'Docker',
            'npm / pip',
            'smart contracts',
            'airdrop flows',
          ].map((t) => (
            <span key={t} className="px-2 py-0.5 rounded-full bg-ink-800/60 border border-ink-700/60">
              {t}
            </span>
          ))}
        </div>
      </section>

      <section className="relative max-w-3xl mx-auto px-6">
        <div className="glass rounded-2xl p-6 sm:p-7 shadow-2xl shadow-gold-400/5">
          <div className="flex items-center justify-between mb-2">
            <label className="block text-xs font-mono uppercase tracking-wider text-ink-400">
              Failure / log / error
            </label>
            <div className="flex gap-1.5 text-[11px] font-mono text-ink-400">
              <span className="hidden sm:inline mr-1 text-ink-500">try:</span>
              {EXAMPLES.map((ex, i) => (
                <button
                  key={ex.label}
                  type="button"
                  onClick={() => loadExample(i)}
                  className="px-2 py-0.5 rounded-full bg-ink-800/60 border border-ink-700/60 hover:border-gold-400/40 hover:text-gold-400 transition-colors"
                >
                  {ex.label}
                </button>
              ))}
            </div>
          </div>

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
                Stack / network <span className="text-ink-500">(optional)</span>
              </label>
              <input
                className="input-base px-3 py-2 text-sm"
                list="networks"
                placeholder="e.g. Foundry · MetaMask · nesa-node"
                value={network}
                onChange={(e) => setNetwork(e.target.value)}
              />
              <datalist id="networks">
                {PRESET_NETWORKS.map((n) => <option key={n} value={n} />)}
              </datalist>
            </div>
            <div>
              <label className="block text-xs font-mono uppercase tracking-wider text-ink-400 mb-1.5">
                OS / environment <span className="text-ink-500">(optional)</span>
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
              placeholder="What were you doing when this happened? Recent changes, restart, upgrade, chain switch, etc."
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

      <section className="relative max-w-3xl mx-auto px-6 mt-16">
        <h3 className="text-center font-mono text-xs uppercase tracking-wider text-ink-400 mb-6">
          What we troubleshoot
        </h3>
        <div className="grid sm:grid-cols-2 gap-3">
          {[
            ['Node & validator logs', 'Cosmos SDK, CometBFT, Substrate, EVM clients — panics, peer timeouts, state corruption.'],
            ['RPC & transport errors', '429 / 502 / timeouts, malformed JSON-RPC, provider drift, eth_call failures.'],
            ['Failed testnet transactions', 'Reverts, nonce mismatch, replacement underpriced, gas estimation failures.'],
            ['MetaMask & wallet automation', 'Playwright/Puppeteer popup races, chain id mismatch, "user rejected request".'],
            ['Faucets', 'Rate limits, captcha failures, IP bans, drip queues, eligibility errors.'],
            ['Bridges, swaps, mints', 'LayerZero/Wormhole/Hop, Uniswap/1inch slippage, NFT mint reverts, allowance issues.'],
            ['Docker & Linux services', 'Restart loops, port conflicts, OOMKilled, journalctl traces, permission denied.'],
            ['npm / pnpm / pip', 'Peer-dep conflicts, ENOENT, module not found, Python resolver failures.'],
            ['Smart contracts', 'Decoded revert reasons, ABI mismatches, Foundry/Hardhat errors, Solidity compiler.'],
            ['Airdrop workflows', 'Eligibility checks, claim transactions, proof generation, missed snapshots.'],
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
