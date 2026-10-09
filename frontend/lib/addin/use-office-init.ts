import { useQuery } from '@tanstack/react-query';

/** Resolves once office.js, which the add-in layout loads after hydration, is ready. */
export async function officeReady(): Promise<Office.HostType | null> {
  for (let attempt = 0; typeof Office === 'undefined' && attempt < 50; attempt++) {
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  if (typeof Office === 'undefined') throw new Error('Office did not load');
  const info = await Office.onReady();
  return info.host;
}

/**
 * Keep the add-in loaded with its document, and its pane open.
 *
 * Both calls are best-effort: older Word builds do not have them, and the pane works
 * without either.
 */
async function configureStartup(): Promise<void> {
  try {
    await Office.addin?.setStartupBehavior?.(Office.StartupBehavior.load);
    await Office.addin?.showAsTaskpane?.();
  } catch (error) {
    console.error('Error configuring the add-in startup:', error);
  }
}

async function initializeOffice(): Promise<boolean> {
  const host = await officeReady();
  if (host === Office.HostType.Word) await configureStartup();
  else console.warn('Add-in is not running in Word');
  return true;
}

/** Whether Office has finished loading. Outside Word it settles too, so the page can render. */
export function useOfficeInit(): { isInitialized: boolean } {
  const { isPending } = useQuery({
    queryKey: ['office-init'],
    queryFn: initializeOffice,
    staleTime: Infinity,
    retry: false,
  });
  return { isInitialized: !isPending };
}
