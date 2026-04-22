import type { Issue } from '@/lib/generated-api';
import { SeverityEnum } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import type { Element } from 'hast';
import React, { Ref, useEffect, useImperativeHandle, useMemo, useRef } from 'react';
import ReactMarkdown, { type ExtraProps } from 'react-markdown';
import type { PluggableList } from 'unified';
import rehypeRaw from 'rehype-raw';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeMathML from '@daiji256/rehype-mathml';

interface IssueWithLines extends Issue {
  start_line?: number | null;
  end_line?: number | null;
}

export interface DocumentMarkdownRendererHandle {
  scrollToLineRange: (range: [number, number]) => void;
}

interface DocumentMarkdownRendererProps {
  ref?: Ref<DocumentMarkdownRendererHandle>;
  markdown: string;
  issues: Issue[];
  selectedLineRange: [number, number] | null;
  onIssueSelect: (issue: Issue | null) => void;
}

const SEVERITY_BG: Record<string, string> = {
  [SeverityEnum.High]: 'bg-red-100',
  [SeverityEnum.Medium]: 'bg-yellow-100',
  [SeverityEnum.Low]: 'bg-blue-100',
  [SeverityEnum.None]: 'bg-green-100',
};

const SEVERITY_RANK: Record<string, number> = {
  [SeverityEnum.None]: 0,
  [SeverityEnum.Low]: 1,
  [SeverityEnum.Medium]: 2,
  [SeverityEnum.High]: 3,
};

function hasLineRange(issue: Issue): issue is IssueWithLines & { start_line: number; end_line: number } {
  const start = (issue as IssueWithLines).start_line;
  const end = (issue as IssueWithLines).end_line;
  return typeof start === 'number' && typeof end === 'number';
}

function pickTopSeverityIssue(issues: IssueWithLines[], lineStart: number, lineEnd: number) {
  let best: IssueWithLines | null = null;
  for (const issue of issues) {
    if (!hasLineRange(issue)) continue;
    const overlaps = issue.start_line! <= lineEnd && issue.end_line! >= lineStart;
    if (!overlaps) continue;
    if (!best || SEVERITY_RANK[issue.severity] > SEVERITY_RANK[best.severity]) {
      best = issue;
    }
  }
  return best;
}

const LINE_NUMBER_CLASSES =
  'before:absolute before:left-0 before:w-8 before:text-right before:pr-1 before:text-[10px] before:leading-5 before:text-gray-400 before:content-[attr(data-line-start)] before:select-none before:pointer-events-none';

function blockFactory(Tag: string, className: string) {
  function Block({ node, children, ...rest }: React.HTMLAttributes<HTMLElement> & ExtraProps) {
    const position = (node as Element | undefined)?.position;
    const dataLineStart = position?.start.line;
    const dataLineEnd = position?.end.line;
    const dataProps: Record<string, string | number> = {};
    if (dataLineStart !== undefined) dataProps['data-line-start'] = dataLineStart;
    if (dataLineEnd !== undefined) dataProps['data-line-end'] = dataLineEnd;

    return React.createElement(
      Tag,
      {
        ...rest,
        ...dataProps,
        className: cn(className, dataLineStart !== undefined && LINE_NUMBER_CLASSES, rest.className),
      },
      children,
    );
  }
  Block.displayName = `MarkdownBlock-${Tag}`;
  return Block;
}

const REMARK_PLUGINS: PluggableList = [remarkGfm, remarkMath];
const REHYPE_PLUGINS: PluggableList = [rehypeMathML, [rehypeRaw, { tagfilter: true }]];

const BLOCK_COMPONENTS = {
  p: blockFactory('p', 'mb-2'),
  h1: blockFactory('h1', 'mb-2 text-xl font-semibold'),
  h2: blockFactory('h2', 'mb-2 text-lg font-semibold'),
  h3: blockFactory('h3', 'mb-2 text-base font-semibold'),
  h4: blockFactory('h4', 'mb-2 text-base font-semibold'),
  h5: blockFactory('h5', 'mb-2 text-base font-medium'),
  h6: blockFactory('h6', 'mb-2 text-base font-medium'),
  ul: blockFactory('ul', 'mb-2 list-disc ml-6'),
  ol: blockFactory('ol', 'mb-2 list-decimal ml-6'),
  li: blockFactory('li', 'mb-1'),
  blockquote: blockFactory('blockquote', 'mb-2 border-l-4 border-gray-300 pl-4'),
  pre: blockFactory('pre', 'mb-2 bg-gray-100 px-2 py-1 rounded overflow-x-auto max-w-full'),
  table: blockFactory('table', 'mb-2 border-collapse block overflow-x-auto max-w-full'),
  hr: blockFactory('hr', 'my-4'),
};

function rangesOverlap(a: [number, number], b: [number, number]): boolean {
  return a[0] <= b[1] && a[1] >= b[0];
}

export function DocumentMarkdownRenderer({
  ref,
  markdown,
  issues,
  selectedLineRange,
  onIssueSelect,
}: DocumentMarkdownRendererProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    scrollToLineRange: (range: [number, number]) => {
      requestAnimationFrame(() => {
        const container = containerRef.current;
        if (!container) return;
        const blocks = container.querySelectorAll<HTMLElement>('[data-line-start][data-line-end]');
        for (const block of blocks) {
          const start = Number(block.getAttribute('data-line-start'));
          const end = Number(block.getAttribute('data-line-end'));
          if (Number.isFinite(start) && Number.isFinite(end) && rangesOverlap([start, end], range)) {
            block.scrollIntoView({ behavior: 'smooth', block: 'center' });
            return;
          }
        }
      });
    },
  }));

  const lineIssues = useMemo(() => issues.filter(hasLineRange) as IssueWithLines[], [issues]);

  // Apply highlights, click handlers, and selection state to annotated blocks.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const blocks = container.querySelectorAll<HTMLElement>('[data-line-start][data-line-end]');
    const cleanups: Array<() => void> = [];

    blocks.forEach((block) => {
      const lineStart = Number(block.getAttribute('data-line-start'));
      const lineEnd = Number(block.getAttribute('data-line-end'));
      if (!Number.isFinite(lineStart) || !Number.isFinite(lineEnd)) return;

      // Clear prior state.
      for (const cls of Object.values(SEVERITY_BG)) block.classList.remove(cls);
      block.classList.remove('cursor-pointer', 'shadow-lg', 'opacity-50');
      block.removeAttribute('data-issue-id');
      block.removeAttribute('data-issue-selected');

      const issue = pickTopSeverityIssue(lineIssues, lineStart, lineEnd);
      if (!issue) return;

      const bg = SEVERITY_BG[issue.severity];
      if (bg) block.classList.add(bg);
      block.classList.add('cursor-pointer');
      block.setAttribute('data-issue-id', issue.id);

      const issueRange: [number, number] = [issue.start_line!, issue.end_line!];

      if (selectedLineRange) {
        const isSelected = rangesOverlap(issueRange, selectedLineRange);
        block.setAttribute('data-issue-selected', String(isSelected));
        block.classList.add(isSelected ? 'shadow-lg' : 'opacity-50');
      }

      const handler = (event: Event) => {
        event.stopPropagation();
        const isCurrentlySelected = selectedLineRange !== null && rangesOverlap(issueRange, selectedLineRange);
        onIssueSelect(isCurrentlySelected ? null : issue);
      };
      block.addEventListener('click', handler);
      cleanups.push(() => block.removeEventListener('click', handler));
    });

    return () => {
      for (const cleanup of cleanups) cleanup();
    };
  }, [markdown, lineIssues, selectedLineRange, onIssueSelect]);

  return (
    <div
      ref={containerRef}
      className="relative h-full overflow-y-auto overflow-x-hidden break-words py-4 pl-10 pr-4 leading-relaxed text-sm"
    >
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} rehypePlugins={REHYPE_PLUGINS} components={BLOCK_COMPONENTS}>
        {markdown}
      </ReactMarkdown>
    </div>
  );
}
