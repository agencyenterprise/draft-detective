import type { Element, Root } from 'hast';
import { describe, expect, it } from 'vitest';
import { rehypeHighlightAnchor, renderedAnchor } from './annotation-highlight';

function paragraph(...children: Element['children']): Element {
  return { type: 'element', tagName: 'p', properties: {}, children };
}

function highlight(tree: Root, anchor: string): Root {
  rehypeHighlightAnchor({ anchor })(tree);
  return tree;
}

describe('rehypeHighlightAnchor', () => {
  it('wraps the exact words in a mark', () => {
    const tree = highlight(
      { type: 'root', children: [paragraph({ type: 'text', value: 'We began. Data were collected. Then we left.' })] },
      'Data were collected',
    );
    const [p] = tree.children as Element[];
    expect(p.children.map((c) => (c.type === 'text' ? c.value : (c as Element).tagName))).toEqual([
      'We began. ',
      'mark',
      '. Then we left.',
    ]);
    expect((p.children[1] as Element).properties.dataAnnotationAnchor).toBe(true);
  });

  it('highlights the paragraph when the anchor spans inline markup', () => {
    const emphasis: Element = {
      type: 'element',
      tagName: 'em',
      properties: {},
      children: [{ type: 'text', value: 'were' }],
    };
    const tree = highlight(
      {
        type: 'root',
        children: [
          paragraph({ type: 'text', value: 'Unrelated.' }),
          paragraph({ type: 'text', value: 'Data ' }, emphasis, { type: 'text', value: ' collected.' }),
        ],
      },
      'Data were collected',
    );
    const [first, second] = tree.children as Element[];
    expect(first.properties.dataAnnotationAnchor).toBeUndefined();
    expect(second.properties.dataAnnotationAnchor).toBe(true);
  });

  it('leaves the tree alone when the anchor is absent', () => {
    const tree = highlight(
      { type: 'root', children: [paragraph({ type: 'text', value: 'Nothing here.' })] },
      'missing',
    );
    expect(JSON.stringify(tree)).not.toContain('dataAnnotationAnchor');
  });

  it('matches an anchor quoted with markdown footnote links as the rendered text', () => {
    const link: Element = {
      type: 'element',
      tagName: 'a',
      properties: { href: '#footnote-10' },
      children: [{ type: 'text', value: '[9]' }],
    };
    const tree = highlight(
      {
        type: 'root',
        children: [
          paragraph({ type: 'text', value: 'Off-grid approaches, sometimes called bridge power,' }, link, {
            type: 'text',
            value: ' were not considered.',
          }),
        ],
      },
      'Off-grid approaches, sometimes called bridge power,[[9]](#footnote-10) were not considered',
    );
    expect((tree.children[0] as Element).properties.dataAnnotationAnchor).toBe(true);
  });
});

describe('renderedAnchor', () => {
  it('keeps only the text of markdown links', () => {
    expect(renderedAnchor('bridge power,[[26]](#footnote-27) were not')).toBe('bridge power,[26] were not');
    expect(renderedAnchor('see [the report](https://example.org/a) here')).toBe('see the report here');
    expect(renderedAnchor('no links [here]')).toBe('no links [here]');
  });
});
