import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderInto, type Rendered } from '@/lib/test-render';
import { UnmatchedReferencesApproveDialog } from '@/components/results/references/unmatched-references-approve-dialog';

let rendered: Rendered | undefined;

afterEach(async () => {
  await rendered?.unmount();
  rendered = undefined;
  vi.restoreAllMocks();
});

describe('UnmatchedReferencesApproveDialog', () => {
  it('renders valid DOM, with no paragraph nested in another', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});

    rendered = await renderInto(
      <UnmatchedReferencesApproveDialog open onOpenChange={() => {}} unmatchedCount={2} onConfirmApprove={() => {}} />,
    );

    expect(document.body.querySelector('[role="alertdialog"]')).not.toBeNull();
    expect(document.body.querySelectorAll('p p')).toHaveLength(0);
    const nestingErrors = consoleError.mock.calls.filter((args) => String(args[0]).includes('cannot be a descendant'));
    expect(nestingErrors).toEqual([]);
  });
});
