import { useEffect, useState } from 'react';
import { debounce } from 'lodash';
import { getCurrentParagraphIndex, loadSettings } from '@/lib/addin/office-utils';

// Office onReady check to prevent double initialization issues
let isOfficeReady = false;
const OFFICE_POLL_INTERVAL_MS = 200;
const OFFICE_POLL_MAX_ATTEMPTS = 50;

type UseOfficeInitResult = {
  token: string | null;
  currentParagraphIndex: number | null;
  isInitialized: boolean;
};

type MountCheck = () => boolean;

type OfficeInitHandlers = {
  isMounted: MountCheck;
  setToken: (token: string | null) => void;
  setIsInitialized: (initialized: boolean) => void;
  updateCurrentParagraph: () => Promise<void>;
  onSelectionChanged: () => void;
};

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForOfficeAvailability(isMounted: MountCheck): Promise<boolean> {
  if (typeof Office !== 'undefined') return true;

  let attempts = 0;
  while (typeof Office === 'undefined' && attempts < OFFICE_POLL_MAX_ATTEMPTS && isMounted()) {
    await sleep(OFFICE_POLL_INTERVAL_MS);
    attempts++;
  }

  return typeof Office !== 'undefined';
}

async function configureStartupBehavior(): Promise<void> {
  try {
    if (Office.addin && Office.addin.setStartupBehavior) {
      await Office.addin.setStartupBehavior(Office.StartupBehavior.load);
    }
  } catch (error) {
    console.error('Error setting startup behavior:', error);
  }
}

async function showTaskpaneIfAvailable(): Promise<void> {
  try {
    if (Office.addin && Office.addin.showAsTaskpane) {
      await Office.addin.showAsTaskpane();
    }
  } catch (error) {
    console.error('Error showing taskpane:', error);
  }
}

function registerSelectionHandler(onSelectionChanged: () => void): void {
  if (!Office.context?.document) return;

  Office.context.document.addHandlerAsync(Office.EventType.DocumentSelectionChanged, onSelectionChanged, (result) => {
    if (result.status === Office.AsyncResultStatus.Failed) {
      console.error('Failed to add handler', result.error);
    }
  });
}

async function hydrateToken(setToken: (token: string | null) => void, isMounted: MountCheck): Promise<void> {
  const { authToken } = await loadSettings();
  if (isMounted()) {
    setToken(authToken);
  }
}

async function initializeOffice(handlers: OfficeInitHandlers): Promise<void> {
  const { isMounted, setToken, setIsInitialized, updateCurrentParagraph, onSelectionChanged } = handlers;

  const officeAvailable = await waitForOfficeAvailability(isMounted);
  if (!officeAvailable) {
    console.warn('Office.js not available, running in browser mode');
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const debugToken = params.get('token');
      if (debugToken && isMounted()) {
        setToken(debugToken);
      }
    }
    await updateCurrentParagraph();
    if (isMounted()) {
      setIsInitialized(true);
    }
    return;
  }

  const info = await Office.onReady();
  if (!isMounted()) return;

  if (info.host !== Office.HostType.Word) {
    console.warn('Add-in is not running in Word');
    setIsInitialized(true);
    return;
  }

  if (isOfficeReady) {
    await hydrateToken(setToken, isMounted);
    await updateCurrentParagraph();
    if (isMounted()) {
      setIsInitialized(true);
    }
    return;
  }

  isOfficeReady = true;

  await hydrateToken(setToken, isMounted);
  await configureStartupBehavior();
  await showTaskpaneIfAvailable();
  registerSelectionHandler(onSelectionChanged);
  await updateCurrentParagraph();

  if (isMounted()) {
    setIsInitialized(true);
  }
}

function createParagraphUpdater(
  setCurrentParagraphIndex: (index: number) => void,
  isMounted: MountCheck,
): () => Promise<void> {
  return async () => {
    if (typeof Word === 'undefined') return;

    try {
      const index = await getCurrentParagraphIndex();
      if (isMounted()) {
        setCurrentParagraphIndex(index);
      }
    } catch (error) {
      console.error('Error getting paragraph index:', error);
    }
  };
}

export function useOfficeInit(): UseOfficeInitResult {
  const [token, setToken] = useState<string | null>(null);
  const [currentParagraphIndex, setCurrentParagraphIndex] = useState<number | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    let mounted = true;
    const isMounted = () => mounted;
    const updateCurrentParagraph = createParagraphUpdater((index) => setCurrentParagraphIndex(index), isMounted);

    const debouncedUpdate = debounce(updateCurrentParagraph, 300);
    void initializeOffice({
      isMounted,
      setToken,
      setIsInitialized,
      updateCurrentParagraph,
      onSelectionChanged: debouncedUpdate,
    }).catch((error) => {
      console.error('Failed to initialize Office', error);
      if (isMounted()) {
        setIsInitialized(true);
      }
    });

    return () => {
      mounted = false;
      debouncedUpdate.cancel();
    };
  }, []);

  return { token, currentParagraphIndex, isInitialized };
}
