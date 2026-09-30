import type { Element, Root, RootContent } from 'hast';

/** Set on the highlighted element so the view can scroll it into place. */
export const ANCHOR_SELECTOR = '[data-annotation-anchor]';

const MARK_CLASSES = ['rounded-[2px]', 'bg-amber-200/80', 'text-inherit', 'dark:bg-amber-500/35'];
const BLOCK_TAGS = new Set(['p', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td', 'th', 'blockquote']);

type Parent = Root | Element;

function normalize(text: string): string {
  return text.replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/\s+/g, ' ').trim().toLowerCase();
}

// A markdown link, text allowed one level of brackets so `[[26]](#footnote-27)` matches.
const MARKDOWN_LINK = /\[((?:[^[\]]|\[[^[\]]*\])*)\]\([^)\s]*\)/g;

/**
 * The anchor as the reader sees it. Anchors are quoted from the markdown
 * source, so a footnote marker arrives as `[[26]](#footnote-27)` while the
 * rendered text says `[26]`; only the link text survives rendering.
 */
export function renderedAnchor(anchor: string): string {
  return anchor.replace(MARKDOWN_LINK, '$1');
}

function textOf(node: RootContent): string {
  if (node.type === 'text') return node.value;
  if (node.type === 'element') return node.children.map(textOf).join('');
  return '';
}

/** Wraps the first verbatim occurrence of `anchor` inside a single text node in a <mark>. */
function markInText(parent: Parent, anchor: string): boolean {
  for (let index = 0; index < parent.children.length; index++) {
    const child = parent.children[index];
    if (child.type === 'element' && markInText(child, anchor)) return true;
    if (child.type !== 'text') continue;
    const at = child.value.indexOf(anchor);
    if (at < 0) continue;
    const mark: Element = {
      type: 'element',
      tagName: 'mark',
      properties: { dataAnnotationAnchor: true, className: MARK_CLASSES },
      children: [{ type: 'text', value: anchor }],
    };
    const before = child.value.slice(0, at);
    const after = child.value.slice(at + anchor.length);
    parent.children.splice(
      index,
      1,
      ...(before ? [{ type: 'text' as const, value: before }] : []),
      mark,
      ...(after ? [{ type: 'text' as const, value: after }] : []),
    );
    return true;
  }
  return false;
}

/** Highlights the innermost block whose text contains the anchor, for anchors split across inline markup. */
function markBlock(parent: Parent, target: string): boolean {
  for (const child of parent.children) {
    if (child.type !== 'element' || !normalize(textOf(child)).includes(target)) continue;
    if (markBlock(child, target)) return true;
    if (!BLOCK_TAGS.has(child.tagName)) continue;
    // The view washes the block's row; the attribute only tells it which row.
    child.properties = { ...child.properties, dataAnnotationAnchor: true };
    return true;
  }
  return false;
}

/**
 * Rehype plugin that highlights the passage being annotated: the exact words
 * when they sit in one run of text, otherwise the paragraph that holds them.
 */
export function rehypeHighlightAnchor(options: { anchor: string }) {
  return (tree: Root) => {
    const anchor = renderedAnchor(options.anchor);
    if (!anchor.trim()) return;
    if (!markInText(tree, anchor)) markBlock(tree, normalize(anchor));
  };
}
