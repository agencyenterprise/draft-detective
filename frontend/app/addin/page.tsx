'use client';

import { HandoffPanel } from '@/components/addin/handoff-panel';
import { useOfficeInit } from '@/lib/addin/use-office-init';

export default function AddinPage() {
  const { isInitialized } = useOfficeInit();

  if (!isInitialized) return <div className="p-4 text-center">Loading Add-in...</div>;

  return (
    <div className="flex flex-col h-screen bg-card">
      <HandoffPanel />
    </div>
  );
}
