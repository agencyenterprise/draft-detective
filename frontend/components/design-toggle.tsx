'use client';

import { PROTOTYPE_MODE } from '@/lib/prototype-mode';
import { motion, useReducedMotion } from 'motion/react';
import { usePathname, useRouter } from 'next/navigation';

export function DesignToggle() {
  const pathname = usePathname();
  const router = useRouter();
  const shouldReduceMotion = useReducedMotion();

  if (!PROTOTYPE_MODE) return null;

  const isOriginal = pathname.startsWith('/original');

  const handleToggle = () => {
    if (isOriginal) {
      if (pathname.startsWith('/original/demo-')) {
        const id = pathname.split('/').pop();
        router.push(`/prototype/${id}`);
      } else {
        router.push('/');
      }
      return;
    }

    if (pathname.startsWith('/prototype/demo-')) {
      const id = pathname.split('/').pop();
      router.push(`/original/${id}`);
    } else {
      router.push('/original');
    }
  };

  return (
    <div className="fixed bottom-6 left-6 z-50 flex max-w-[calc(100vw-3rem)] items-center gap-2 rounded-[1.4rem] border border-border/80 bg-white/92 p-2 shadow-[0_20px_60px_-28px_rgba(15,23,42,0.35)] backdrop-blur-md">
      <div className="flex items-center gap-3 rounded-full bg-muted/70 px-3 py-1.5">
        <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">Design</span>
        <button
          onClick={handleToggle}
          className="relative flex h-8 w-[138px] items-center rounded-full bg-background p-0.5 shadow-inner"
          aria-label="Toggle between current and idea designs"
        >
          <motion.span
            layout={!shouldReduceMotion}
            className="absolute h-7 w-[67px] rounded-full bg-primary shadow-sm"
            animate={{ x: isOriginal ? 0 : 67 }}
            transition={{ type: 'spring', stiffness: 380, damping: 30, mass: 0.85 }}
          />
          <span
            className={`relative z-10 flex-1 text-center text-xs font-medium ${isOriginal ? 'text-primary-foreground' : 'text-muted-foreground'}`}
          >
            Current
          </span>
          <span
            className={`relative z-10 flex-1 text-center text-xs font-medium ${!isOriginal ? 'text-primary-foreground' : 'text-muted-foreground'}`}
          >
            Idea
          </span>
        </button>
      </div>
    </div>
  );
}
