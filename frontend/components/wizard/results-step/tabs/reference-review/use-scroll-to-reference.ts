import { useEffect, useRef } from 'react';

/**
 * Hook that scrolls to and highlights a reference element based on URL hash.
 * Listens for hash changes and scrolls to elements with id matching `reference-{index}`.
 */
export function useScrollToReference() {
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const scrollToHash = () => {
      const hash = window.location.hash;
      if (!hash.startsWith('#reference-')) return;

      const element = document.getElementById(hash.slice(1));
      if (!element) return;

      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
      element.classList.add('ring-2', 'ring-primary', 'ring-offset-2');

      // Clear any existing timeout before setting a new one
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }

      timeoutRef.current = setTimeout(() => {
        element.classList.remove('ring-2', 'ring-primary', 'ring-offset-2');
        timeoutRef.current = null;
      }, 2000);
    };

    // Scroll on mount and hash changes
    scrollToHash();
    window.addEventListener('hashchange', scrollToHash);

    return () => {
      window.removeEventListener('hashchange', scrollToHash);
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);
}
