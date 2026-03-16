import { auth } from '@/auth';
import { ApiConfig } from '@/components/api-config';
import { DesignToggle } from '@/components/design-toggle';
import { ApplicationShell } from '@/components/layout/application-shell';
import { MotionProvider } from '@/components/motion-provider';
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
    'AI-powered document review and analysis platform for accurate citations, fact-checking, and quality assessment',
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
                <MotionProvider>
                  <ApplicationShell>{children}</ApplicationShell>
                  <DesignToggle />
                </MotionProvider>
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
