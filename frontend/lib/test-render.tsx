import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, ReactNode } from 'react';
import { createRoot, Root } from 'react-dom/client';

// Tells React the tests drive updates through act().
(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

export interface Rendered {
  container: HTMLElement;
  rerender: (ui: ReactNode) => Promise<void>;
  unmount: () => Promise<void>;
}

/** Mounts `ui` into a detached div inside act(), for tests that need effects, refs and state to run. */
export async function renderInto(ui: ReactNode): Promise<Rendered> {
  const container = document.createElement('div');
  document.body.appendChild(container);
  const root: Root = createRoot(container);
  await act(async () => root.render(ui));
  return {
    container,
    rerender: async (next) => act(async () => root.render(next)),
    unmount: async () => {
      await act(async () => root.unmount());
      container.remove();
    },
  };
}

/** A client that never retries, so a rejected request fails the test step at once. */
export function testQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

export function withQueryClient(client: QueryClient, ui: ReactNode): ReactNode {
  return <QueryClientProvider client={client}>{ui}</QueryClientProvider>;
}

/** Lets pending promises and zero-delay timers settle. */
export async function flush(): Promise<void> {
  await act(async () => new Promise((resolve) => setTimeout(resolve, 0)));
}
