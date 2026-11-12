'use client';

import { ApiKeyForm } from '@/components/settings/api-key-form';
import { Key } from 'lucide-react';
import { StepHeading, StepLayout } from './step-layout';

export function StepApiKeyConfig() {
  return (
    <StepLayout>
      <div className="space-y-6">
        <StepHeading title="Set up your OpenAI API Key">
          This deployment requires an OpenAI API key to run assessments. Your key is encrypted at rest and never exposed
          in API responses. You can update or remove it at any time from your account settings.
        </StepHeading>

        <div className="rounded-lg border p-6 space-y-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Key className="h-4 w-4" />
            OpenAI API Key
          </div>

          {/* Saving refetches the user. Once has_openai_api_key is true, new/page.tsx moves on to the
              "Your Document" step. */}
          <ApiKeyForm />

          <p className="text-sm text-muted-foreground">
            Once saved, you&apos;ll be taken to the next step automatically.
          </p>
        </div>
      </div>
    </StepLayout>
  );
}
