import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Yarrr.Tech — AI diagnostics for node operators',
  description:
    'Paste a stack trace or log file. Get root cause and exact fix commands. Built for testnet & validator node operators. Powered by Xiaomi MiMo V2.5.',
  metadataBase: new URL('https://yarrr-node.com'),
  openGraph: {
    title: 'Yarrr.Tech',
    description: 'AI-native diagnostics for testnet & validator node operators.',
    url: 'https://yarrr-node.com',
    siteName: 'Yarrr.Tech',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Yarrr.Tech',
    description: 'AI-native diagnostics for testnet & validator node operators.',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
