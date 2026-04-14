import { auth } from '@/auth';
import { ApiConfig } from '@/components/api-config';
import { ApplicationShell } from '@/components/layout/application-shell';
import QueryProvider from '@/components/providers';
import { Toaster } from '@/components/ui/sonner';
import { VersionBadge } from '@/components/version-badge';
import { ExperimentalFeaturesProvider } from '@/context/experimental-features-context';
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
    'AI-powered document review and assessment platform for accurate citations, fact-checking, and quality assessment',
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = await auth();

  return (
    <html lang="en" className="h-full">
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased h-full`}>
        <PostHogProvider>
          <SessionProvider session={session}>
            <QueryProvider>
              <ExperimentalFeaturesProvider>
                <ApiConfig />
                <ApplicationShell>{children}</ApplicationShell>
                <Toaster />
                <VersionBadge />
              </ExperimentalFeaturesProvider>
            </QueryProvider>
          </SessionProvider>
        </PostHogProvider>
      </body>
    </html>
  );
}
