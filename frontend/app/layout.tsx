import type { Metadata } from 'next';
import './globals.css';
import { LanguageProvider } from './LanguageContext';

// Static metadata stays bilingual-friendly: title is brand-led, description
// covers both audiences. Per-page translation of the title would require SSR,
// which we don't have on `output: 'export'`.
export const metadata: Metadata = {
  title: 'Yarrr.Tech — Understand any crypto wallet instantly',
  description:
    'Paste any wallet address. AI reads its on-chain history across 5 EVM chains and tells you what it actually does — airdrop hunter, smart money, dormant whale, NFT trader. Built by Bastiar, powered by Xiaomi MiMo V2.5.',
  metadataBase: new URL('https://yarrr-node.com'),
  openGraph: {
    title: 'Yarrr.Tech',
    description: 'Paste any wallet. Instantly understand what it actually does.',
    url: 'https://yarrr-node.com',
    siteName: 'Yarrr.Tech',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Yarrr.Tech',
    description: 'AI Wallet Intelligence — paste any wallet, instantly understand what it does.',
  },
};

// `lang` here is initial value. LanguageProvider updates `document.documentElement.lang`
// on the client based on user preference (default: id).
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id">
      <body className="min-h-screen">
        <LanguageProvider>{children}</LanguageProvider>
      </body>
    </html>
  );
}
