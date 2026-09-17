import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AutoTrade AI — Local Monitoring Dashboard',
  description: 'Real-time multi-model local AI algorithmic trading monitor & execution console',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-trade-bg text-gray-100 flex flex-col antialiased">
        {children}
      </body>
    </html>
  );
}
