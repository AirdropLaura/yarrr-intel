import type { Metadata, Viewport } from 'next';
import { Cormorant_Garamond, Inter } from 'next/font/google';
import './globals.css';
import { LanguageProvider } from './LanguageContext';

// Display font for hero, headings, brand wordmark — chosen for elegant
// editorial feel without being too dramatic. Loaded via next/font so
// it ships with the build and avoids FOUT.
const display = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['500', '600', '700'],
  variable: '--font-display',
  display: 'swap',
});

// Sans serif body — Inter is the de-facto modern UI font. Subtle, premium,
// excellent legibility at small sizes for the analyst content.
const sans = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
  display: 'swap',
});

// Static metadata stays bilingual-friendly: title is brand-led, description
// covers both audiences. Per-page translation of the title would require SSR,
// which we don't have on `output: 'export'`.
export const metadata: Metadata = {
  title: {
    default: 'Yarrr.Tech — AI Wallet Intelligence',
    template: '%s · Yarrr.Tech',
  },
  description:
    'Paste any wallet address. AI reads its on-chain history across 22 mainnets and 15 testnets and tells you what it actually does — airdrop hunter, smart money, dormant whale, NFT trader. Built by Bastiar, powered by Xiaomi MiMo V2.5.',
  metadataBase: new URL('https://yarrr-node.com'),
  applicationName: 'Yarrr.Tech',
  authors: [{ name: 'Bastiar', url: 'https://yarrr-node.com' }],
  keywords: [
    'wallet intelligence',
    'on-chain analytics',
    'EVM',
    'AI',
    'crypto',
    'wallet analyzer',
    'airdrop hunter',
    'smart money',
  ],
  icons: {
    icon: [
      { url: '/icon-192.png', sizes: '192x192', type: 'image/png' },
      { url: '/icon-512.png', sizes: '512x512', type: 'image/png' },
    ],
    apple: '/apple-touch-icon.png',
    shortcut: '/favicon.ico',
  },
  manifest: '/manifest.json',
  openGraph: {
    title: 'Yarrr.Tech — AI Wallet Intelligence',
    description: 'Paste any wallet. Instantly understand what it actually does.',
    url: 'https://yarrr-node.com',
    siteName: 'Yarrr.Tech',
    type: 'website',
    images: [
      {
        url: '/og-image.jpg',
        width: 1200,
        height: 630,
        alt: 'Yarrr.Tech — AI Wallet Intelligence',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Yarrr.Tech — AI Wallet Intelligence',
    description: 'Paste any wallet. Instantly understand what it actually does.',
    images: ['/og-image.jpg'],
  },
  robots: {
    index: true,
    follow: true,
  },
};

// Theme color picks up in mobile browser chrome — darkest ruby tone keeps
// the address bar / status bar visually contiguous with the page.
export const viewport: Viewport = {
  themeColor: '#0a0606',
  width: 'device-width',
  initialScale: 1,
};

// `lang` here is initial value. LanguageProvider updates `document.documentElement.lang`
// on the client based on user preference (default: id).
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="id" className={`${sans.variable} ${display.variable}`}>
      <body className="min-h-screen font-sans">
        <LanguageProvider>{children}</LanguageProvider>
      </body>
    </html>
  );
}
