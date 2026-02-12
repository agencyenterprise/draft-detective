import Script from 'next/script';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'AI Reviewer Add-in',
  description: 'Word Add-in for AI Reviewer',
};

export default function AddinLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Script src="https://appsforoffice.microsoft.com/lib/1/hosted/office.js" strategy="afterInteractive" />
      {children}
    </>
  );
}
