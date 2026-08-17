import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'CourtEdge — Basketball Gear',
  description:
    'Shop basketballs, hoops, and footwear with an AI assistant that can only act with your permission.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-display text-net-white antialiased">{children}</body>
    </html>
  );
}
