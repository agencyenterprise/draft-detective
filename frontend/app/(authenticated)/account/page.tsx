'use client';

import { ApiKeySettings } from '@/components/settings/api-key-settings';
import { Settings } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
          <Settings className="h-6 w-6" />
          Settings
        </h1>
        <p className="text-muted-foreground mt-1">Manage your account settings and API keys.</p>
      </div>

      <ApiKeySettings />
    </div>
  );
}
