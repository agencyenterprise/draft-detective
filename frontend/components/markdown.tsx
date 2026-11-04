import { cn } from '@/lib/utils';
import React, { JSX } from 'react';
import ReactMarkdown, { ExtraProps } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeMathML from '@daiji256/rehype-mathml';
import { Table, TableBody, TableCell, TableRow, TableHeader, TableHead } from './ui/table';

type MarkdownComponentProps<Key extends keyof JSX.IntrinsicElements> = JSX.IntrinsicElements[Key] & ExtraProps;

const componentFactory = (tagOrComponent: React.ElementType, className: string) => {
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const Component = ({ node, children, ...rest }: ExtraProps & { children?: React.ReactNode; className?: string }) => {
    const Tag = tagOrComponent;

    return (
      <Tag {...rest} className={cn(className, rest.className)}>
        {children}
      </Tag>
    );
  };

  const name = typeof tagOrComponent === 'string' ? tagOrComponent : tagOrComponent.displayName || 'Component';
  Component.displayName = `Markdown-${name}`;
  return Component;
};

const components = {
  p: componentFactory('p', 'mb-2'),
  h1: componentFactory('h1', 'mb-2 text-xl font-semibold'),
  h2: componentFactory('h2', 'mb-2 text-lg font-semibold'),
  h3: componentFactory('h3', 'mb-2 text-base font-semibold'),
  h4: componentFactory('h4', 'mb-2 text-base font-semibold'),
  h5: componentFactory('h5', 'mb-2 text-base font-medium'),
  h6: componentFactory('h6', 'mb-2 text-base font-medium'),
  ul: componentFactory('ul', 'mb-2 list-disc'),
  ol: componentFactory('ol', 'mb-2 list-decimal'),
  li: componentFactory('li', 'mb-2 ml-4'),
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  a: ({ node, ...rest }: MarkdownComponentProps<'a'>) => {
    const isInternalAnchor = rest.href?.startsWith('#');
    return (
      <a
        {...rest}
        className={cn('text-blue-600 hover:underline break-all', rest.className)}
        {...(!isInternalAnchor && {
          target: '_blank',
          rel: 'noopener noreferrer',
        })}
      />
    );
  },
  img: componentFactory('img', 'mb-2 w-full'),
  blockquote: componentFactory('blockquote', 'mb-2 border-l-4 border-border pl-4'),
  code: componentFactory('code', 'bg-muted px-1 py-0.5 rounded'),
  pre: componentFactory('pre', 'mb-2 bg-muted px-1 py-0.5 rounded'),
  table: componentFactory(Table, 'mb-2'),
  thead: componentFactory(TableHeader, ''),
  tbody: componentFactory(TableBody, ''),
  tr: componentFactory(TableRow, ''),
  th: componentFactory(TableHead, ''),
  td: componentFactory(TableCell, 'whitespace-normal'),
  hr: componentFactory('hr', 'my-4'),
  br: componentFactory('br', ''),
  em: componentFactory('em', 'italic'),
  strong: componentFactory('strong', 'font-semibold'),
  del: componentFactory('del', 'line-through'),
  ins: componentFactory('ins', 'underline'),
  sup: componentFactory('sup', 'text-sm'),
  sub: componentFactory('sub', 'text-sm'),
};

export type MarkdownProps = React.ComponentProps<typeof ReactMarkdown>;

export function Markdown(props: MarkdownProps) {
  return (
    <ReactMarkdown
      components={components}
      {...props}
      // Single-dollar math is off, as in the document view: issue text and
      // reports quote dollar amounts far more often than they carry inline
      // TeX, and a pair of amounts would otherwise render as a formula.
      // Math still renders with $$...$$.
      remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: false }], ...(props.remarkPlugins || [])]}
      rehypePlugins={[rehypeMathML, ...(props.rehypePlugins || [])]}
    />
  );
}
