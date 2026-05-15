import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Yarrr.Tech — AI co-pilot for Web3 operators',
  description:
    'Paste any Web3 ops failure — node logs, RPC errors, tx reverts, MetaMask timeouts, faucet issues, bridge/mint errors, Docker, npm, smart contracts. Get root cause and exact fix. Powered by Xiaomi MiMo V2.5.',
  metadataBase: new URL('https://yarrr-node.com'),
  openGraph: {
    title: 'Yarrr.Tech',
    description:
      'AI co-pilot for Web3 testnet operators, node runners, and airdrop builders.',
    url: 'https://yarrr-node.com',
    siteName: 'Yarrr.Tech',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Yarrr.Tech',
    description:
      'AI co-pilot for Web3 testnet operators, node runners, and airdrop builders.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
