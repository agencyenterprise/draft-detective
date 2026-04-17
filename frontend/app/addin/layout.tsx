import Script from 'next/script';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Draft Detective Add-in',
  description: 'Word Add-in for Draft Detective',
};

export default function AddinLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Script src="https://appsforoffice.microsoft.com/lib/1/hosted/office.js" strategy="afterInteractive" />
      {children}
    </>
  );
}
