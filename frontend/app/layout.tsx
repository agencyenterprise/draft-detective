import { ApiConfig } from '@/components/api-config';
import { ApplicationShell } from '@/components/application-shell';
import QueryProvider from '@/components/providers';
import { Toaster } from '@/components/ui/sonner';
import { VersionBadge } from '@/components/version-badge';
import { PostHogProvider } from '@/lib/posthog';
import type { Metadata } from 'next';
import { SessionProvider } from 'next-auth/react';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

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
    <html lang="en" className="h-full">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased h-full`}>
        <PostHogProvider>
          <SessionProvider>
            <QueryProvider>
              <ApiConfig />
              <ApplicationShell>{children}</ApplicationShell>
              <Toaster />
              <VersionBadge />
            </QueryProvider>
          </SessionProvider>
        </PostHogProvider>
      </body>
    </html>
  );
}
