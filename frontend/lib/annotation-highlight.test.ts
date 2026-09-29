import type { Element, Root } from 'hast';
import { describe, expect, it } from 'vitest';
import { rehypeHighlightAnchor } from './annotation-highlight';

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
});
