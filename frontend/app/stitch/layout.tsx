import { Metadata } from 'next';
import { Inter, Manrope, Newsreader } from 'next/font/google';

const manrope = Manrope({
  subsets: ['latin'],
  variable: '--font-manrope',
});

const newsreader = Newsreader({
  subsets: ['latin'],
  variable: '--font-newsreader',
});

const inter = Inter({
  subsets: ['latin'],
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'AI Reviewer — Design Prototype',
  description: 'Stitch-inspired design prototype for the AI Reviewer project detail page',
};

export default function StitchLayout({ children }: { children: React.ReactNode }) {
  return <div className={`${manrope.variable} ${newsreader.variable} ${inter.variable} min-h-full`}>{children}</div>;
}
