import { describe, expect, it } from 'vitest';
import { renderInto } from '@/lib/test-render';
import { ExportCounts } from '@/lib/export-scope';
import { ExportScope } from './active-filters-summary';

const NONE = { severity: [], workflowType: [], showPassing: false };

async function scopeText(counts: ExportCounts | null, countsFailed = false) {
  const view = await renderInto(
    <ExportScope filters={NONE} counts={counts} countsFailed={countsFailed} includeEdits />,
  );
  const text = view.container.textContent ?? '';
  await view.unmount();
  return text;
}

describe('ExportScope', () => {
  it('says it is counting, not "0 issues", while the issues load', async () => {
    const text = await scopeText(null);

    expect(text).toContain('Counting issues');
    expect(text).not.toContain('0 issues');
  });

  it('says the count is unavailable when the issues failed to load', async () => {
    const text = await scopeText(null, true);

    expect(text).toContain("Couldn't count the issues");
    expect(text).not.toContain('0 issues');
  });

  it('shows the counts once they are known', async () => {
    expect(await scopeText({ issues: 3, edits: 1 })).toContain('3 issues');
  });
});
