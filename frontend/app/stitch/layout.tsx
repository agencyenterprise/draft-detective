import { Metadata } from 'next';
import { Inter, Manrope, Newsreader } from 'next/font/google';

const manrope = Manrope({
  subsets: ['latin'],
  variable: '--stitch-font-headline',
});

const newsreader = Newsreader({
  subsets: ['latin'],
  variable: '--stitch-font-body',
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--stitch-font-label',
});

export const metadata: Metadata = {
  title: 'AI Reviewer — Design Prototype',
  description: 'Stitch-inspired design prototype for the AI Reviewer project detail page',
};

export default function StitchLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className={`${manrope.variable} ${newsreader.variable} ${inter.variable} stitch-theme min-h-full`}>
      <style>{`
        .stitch-theme {
          --stitch-primary: #002045;
          --stitch-primary-container: #1a365d;
          --stitch-on-primary: #ffffff;
          --stitch-on-primary-container: #86a0cd;
          --stitch-surface: #f7fafc;
          --stitch-surface-low: #f1f4f6;
          --stitch-surface-container: #ebeef0;
          --stitch-surface-high: #e5e9eb;
          --stitch-surface-highest: #e0e3e5;
          --stitch-surface-lowest: #ffffff;
          --stitch-on-surface: #181c1e;
          --stitch-on-surface-variant: #43474e;
          --stitch-secondary: #545f72;
          --stitch-outline-variant: #c4c6cf;
          --stitch-error: #ba1a1a;
        }
      `}</style>
      {children}
    </div>
  );
}
