import type { Element } from 'hast';
import React from 'react';
import type { ExtraProps } from 'react-markdown';

/**
 * A table row that carries its source lines.
 *
 * The table is the block the gutter numbers, so rows are never rows of the
 * document grid themselves. But a proposed edit is anchored to one source line,
 * and a table's rows are one line each, so without these attributes the edit
 * highlight could only search the whole table and would settle on the first
 * cell that happened to repeat the quoted phrase.
 */
export function TableRow({ node, children, ...rest }: React.HTMLAttributes<HTMLTableRowElement> & ExtraProps) {
  const position = (node as Element | undefined)?.position;
  const dataProps: Record<string, number> = {};
  if (position?.start.line !== undefined) dataProps['data-line-start'] = position.start.line;
  if (position?.end.line !== undefined) dataProps['data-line-end'] = position.end.line;
  return (
    <tr {...rest} {...dataProps}>
      {children}
    </tr>
  );
}
