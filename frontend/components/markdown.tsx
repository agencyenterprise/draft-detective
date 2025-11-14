import { cn } from '@/lib/utils';
import { ComponentType, JSX } from 'react';
import ReactMarkdown, { ExtraProps } from 'react-markdown';
import remarkGfm from 'remark-gfm';

type MarkdownComponentProps<Key extends keyof JSX.IntrinsicElements> = JSX.IntrinsicElements[Key] & ExtraProps;

const componentFactory = (
  tag: keyof JSX.IntrinsicElements,
  className: string,
  highlight?: 'red' | 'yellow' | 'blue' | 'green' | 'none',
) => {
  const highlightClass = highlight
    ? {
        none: '',
        red: 'bg-red-100',
        yellow: 'bg-yellow-100',
        blue: 'bg-blue-50',
        green: 'bg-green-100',
      }[highlight]
    : '';

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const Component = ({ node, children, ...rest }: MarkdownComponentProps<typeof tag>) => {
    const Component = tag as unknown as ComponentType<MarkdownComponentProps<typeof tag>>;

    if (highlight && highlight !== 'none') {
      return (
        <Component {...rest} className={cn(className, rest.className)}>
          <mark className={highlightClass}>{children}</mark>
        </Component>
      );
    }

    return (
      <Component {...rest} className={cn(className, rest.className)}>
        {children}
      </Component>
    );
  };

  Component.displayName = `Markdown-${tag}`;
  return Component;
};

const createComponents = (highlight: 'red' | 'yellow' | 'blue' | 'green' | 'none') => {
  return {
    p: componentFactory('p', '', highlight),
    h1: componentFactory('h1', 'text-2xl font-bold', highlight),
    h2: componentFactory('h2', 'text-xl font-bold', highlight),
    h3: componentFactory('h3', 'text-lg font-bold', highlight),
    h4: componentFactory('h4', 'text-base font-bold', highlight),
    h5: componentFactory('h5', 'text-sm font-bold', highlight),
    h6: componentFactory('h6', 'text-xs font-bold', highlight),
    ul: componentFactory('ul', 'list-disc'),
    ol: componentFactory('ol', 'list-decimal'),
    li: componentFactory('li', 'ml-4', highlight),
    a: ({ node, ...rest }: MarkdownComponentProps<'a'>) => (
      <a
        {...rest}
        className={cn('text-blue-600 hover:underline', rest.className)}
        target="_blank"
        rel="noopener noreferrer"
      />
    ),
    img: componentFactory('img', 'w-full'),
    blockquote: componentFactory('blockquote', 'border-l-4 border-gray-300 pl-4'),
    code: componentFactory('code', 'bg-gray-100 px-1 py-0.5 rounded'),
    pre: componentFactory('pre', 'bg-gray-100 px-1 py-0.5 rounded'),
    table: componentFactory('table', 'w-full'),
    thead: componentFactory('thead', 'bg-gray-100'),
    tbody: componentFactory('tbody', 'bg-gray-100'),
    tr: componentFactory('tr', 'bg-gray-100'),
    th: componentFactory('th', 'bg-gray-100'),
    td: componentFactory('td', 'bg-gray-100'),
    hr: componentFactory('hr', 'my-4'),
    br: componentFactory('br', ''),
    em: componentFactory('em', 'italic'),
    strong: componentFactory('strong', 'font-bold'),
    del: componentFactory('del', 'line-through'),
    ins: componentFactory('ins', 'underline'),
    sup: componentFactory('sup', 'text-sm'),
    sub: componentFactory('sub', 'text-sm'),
  };
};

export interface MarkdownProps extends React.ComponentProps<typeof ReactMarkdown> {
  highlight?: 'red' | 'yellow' | 'blue' | 'green' | 'none';
}

const componentsByHighlight = {
  none: createComponents('none'),
  red: createComponents('red'),
  yellow: createComponents('yellow'),
  blue: createComponents('blue'),
  green: createComponents('green'),
};

export function Markdown(props: MarkdownProps) {
  const { highlight = 'none', ...rest } = props;
  return (
    <ReactMarkdown
      components={componentsByHighlight[highlight]}
      {...rest}
      remarkPlugins={[remarkGfm, ...(rest.remarkPlugins || [])]}
    />
  );
}
