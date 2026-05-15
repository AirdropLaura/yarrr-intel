import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Yarrr.Intel — Understand any crypto wallet instantly',
  description:
    'Paste any wallet address. AI reads its on-chain history across 5 EVM chains and tells you what it actually does — airdrop hunter, smart money, dormant whale, NFT trader. Powered by Xiaomi MiMo V2.5.',
  metadataBase: new URL('https://yarrr-node.com'),
  openGraph: {
    title: 'Yarrr.Intel',
    description: 'Paste any wallet. Instantly understand what it actually does.',
    url: 'https://yarrr-node.com',
    siteName: 'Yarrr.Intel',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Yarrr.Intel',
    description: 'AI Wallet Intelligence — paste any wallet, instantly understand what it does.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
