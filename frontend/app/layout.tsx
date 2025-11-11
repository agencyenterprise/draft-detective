import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import QueryProvider from '@/components/providers';
import { Toaster } from '@/components/ui/sonner';
import { VersionBadge } from '@/components/version-badge';
import { SessionProvider } from 'next-auth/react';

const geistSans = Geist({
  variable: '--font-geist-sans',
  subsets: ['latin'],
});

const geistMono = Geist_Mono({
  variable: '--font-geist-mono',
  subsets: ['latin'],
});

export const metadata: Metadata = {
  title: 'AI Reviewer',
  description:
    'AI-powered document review and analysis platform for accurate citations, fact-checking, and quality assessment',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <SessionProvider>
          <QueryProvider>
            {children}
            <Toaster />
            <VersionBadge />
          </QueryProvider>
        </SessionProvider>
      </body>
    </html>
  );
}
