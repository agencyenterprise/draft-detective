// Shared setup for the documentation mockups: the app's design tokens (copied from
// frontend/app/globals.css), its fonts, and lucide icons. Each mockup loads the
// Tailwind v4 browser build first, then this file.

const THEME = `
@custom-variant dark (&:is(.dark *));

@theme inline {
  --font-sans: 'Geist', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'Geist Mono', ui-monospace, SFMono-Regular, monospace;
  --color-background: var(--background);
  --color-foreground: var(--foreground);
  --color-card: var(--card);
  --color-card-foreground: var(--card-foreground);
  --color-popover: var(--popover);
  --color-popover-foreground: var(--popover-foreground);
  --color-primary: var(--primary);
  --color-primary-foreground: var(--primary-foreground);
  --color-secondary: var(--secondary);
  --color-secondary-foreground: var(--secondary-foreground);
  --color-muted: var(--muted);
  --color-muted-foreground: var(--muted-foreground);
  --color-accent: var(--accent);
  --color-accent-foreground: var(--accent-foreground);
  --color-destructive: var(--destructive);
  --color-border: var(--border);
  --color-input: var(--input);
  --color-ring: var(--ring);
  --color-sidebar: var(--sidebar);
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
}

:root {
  --radius: 0.625rem;
  --background: oklch(1 0 0);
  --foreground: oklch(0.145 0 0);
  --card: oklch(1 0 0);
  --card-foreground: oklch(0.145 0 0);
  --popover: oklch(1 0 0);
  --popover-foreground: oklch(0.145 0 0);
  --primary: var(--color-indigo-700);
  --primary-foreground: oklch(0.985 0 0);
  --secondary: oklch(0.97 0 0);
  --secondary-foreground: oklch(0.205 0 0);
  --muted: oklch(0.97 0 0);
  --muted-foreground: oklch(0.556 0 0);
  --accent: oklch(0.97 0 0);
  --accent-foreground: oklch(0.205 0 0);
  --destructive: oklch(0.577 0.245 27.325);
  --border: oklch(0.922 0 0);
  --input: oklch(0.922 0 0);
  --ring: oklch(0.708 0 0);
  --sidebar: oklch(0.985 0 0);
}

@layer base {
  * { @apply border-border outline-ring/50; }
  body { @apply bg-background text-foreground font-sans antialiased; }
}
`;

const style = document.createElement('style');
style.type = 'text/tailwindcss';
style.textContent = THEME;
document.head.appendChild(style);

const fonts = document.createElement('link');
fonts.rel = 'stylesheet';
fonts.href =
  'https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500&display=block';
document.head.appendChild(fonts);

const lucideScript = document.createElement('script');
lucideScript.src = 'https://cdn.jsdelivr.net/npm/lucide@0.544.0/dist/umd/lucide.min.js';
lucideScript.onload = () => {
  window.lucide.createIcons();
  if (typeof window.layoutMockup === 'function') window.layoutMockup();
};
document.head.appendChild(lucideScript);
