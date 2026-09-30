import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act } from 'react';
import { submitAnnotationApiAnnotationsItemsItemIdPut, type AnnotationQuestion } from '@/lib/generated-api';
import { flush, renderInto, Rendered, testQueryClient, withQueryClient } from '@/lib/test-render';
import { QuestionPane } from './question-pane';

vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  submitAnnotationApiAnnotationsItemsItemIdPut: vi.fn(),
}));
vi.mock('sonner', () => ({ toast: { error: vi.fn() } }));

const submit = vi.mocked(submitAnnotationApiAnnotationsItemsItemIdPut);

const QUESTION: AnnotationQuestion = {
  key: 'should_flag',
  prompt: 'Should Draft Detective flag the highlighted passage according to the rules below?',
  options: [
    { value: 'yes', label: 'Yes, flag it', shortcut: '1' },
    { value: 'no', label: 'No, leave it', shortcut: '2' },
  ],
  abstain_value: null,
};

let rendered: Rendered;
let onNext: ReturnType<typeof vi.fn<() => void>>;

beforeEach(async () => {
  submit.mockReset();
  onNext = vi.fn<() => void>();
  rendered = await renderInto(
    withQueryClient(
      testQueryClient(),
      <QuestionPane
        itemId="item-1"
        passage={{ document: 'Doc.', anchor: 'Doc', line: 1 }}
        questions={[QUESTION]}
        guidance="Rules."
        shownAt={Date.now()}
        onNext={onNext}
        onSkip={vi.fn()}
      />,
    ),
  );
});
afterEach(async () => rendered.unmount());

function option(label: string): HTMLButtonElement {
  const button = [...rendered.container.querySelectorAll<HTMLButtonElement>('[role="radio"]')].find((b) =>
    b.textContent?.includes(label),
  );
  if (!button) throw new Error(`no option ${label}`);
  return button;
}

async function choose(label: string) {
  await act(async () => option(label).click());
  await flush();
}

function nextButton(): HTMLButtonElement {
  const button = [...rendered.container.querySelectorAll('button')].find((b) =>
    b.textContent?.includes('Next example'),
  );
  if (!button) throw new Error('no next button');
  return button;
}

describe('QuestionPane', () => {
  it('falls back to the saved answer when a change fails to save', async () => {
    submit.mockResolvedValueOnce({ item_id: 'item-1', answered_by_me: 1 });
    await choose('Yes, flag it');
    expect(option('Yes, flag it').getAttribute('aria-checked')).toBe('true');

    submit.mockRejectedValueOnce(new Error('network down'));
    await choose('No, leave it');

    expect(option('Yes, flag it').getAttribute('aria-checked')).toBe('true');
    expect(option('No, leave it').getAttribute('aria-checked')).toBe('false');
    expect(rendered.container.textContent).toContain('Answer saved');
  });

  it('keeps Next disabled when the first answer fails to save', async () => {
    submit.mockRejectedValueOnce(new Error('network down'));
    await choose('Yes, flag it');

    expect(option('Yes, flag it').getAttribute('aria-checked')).toBe('false');
    expect(rendered.container.textContent).not.toContain('Answer saved');
    expect(nextButton().disabled).toBe(true);
  });

  it('does not advance on Enter while a changed answer is still saving', async () => {
    submit.mockResolvedValueOnce({ item_id: 'item-1', answered_by_me: 1 });
    await choose('Yes, flag it');

    let finishChange: (value: { item_id: string; answered_by_me: number }) => void = () => {};
    submit.mockReturnValueOnce(new Promise((resolve) => (finishChange = resolve)));
    await choose('No, leave it');

    await pressEnter(window);
    await pressEnter(textarea(), { metaKey: true });
    expect(onNext).not.toHaveBeenCalled();

    await act(async () => finishChange({ item_id: 'item-1', answered_by_me: 1 }));
    await flush();
    await pressEnter(window);
    expect(onNext).toHaveBeenCalledTimes(1);
  });
});

function textarea(): HTMLTextAreaElement {
  const element = rendered.container.querySelector('textarea');
  if (!element) throw new Error('no comment box');
  return element;
}

async function pressEnter(target: EventTarget, modifiers: KeyboardEventInit = {}) {
  await act(async () => {
    target.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, ...modifiers }));
  });
  await flush();
}
