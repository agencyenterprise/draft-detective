'use client';

import { initialize, type InitializeResult } from '@open-iframe-resizer/core';
import DOMPurify from 'dompurify';
import { Ref, useCallback, useImperativeHandle, useMemo, useRef } from 'react';

// The report HTML is authored by an LLM and is untrusted. It is rendered inside
// a sandboxed iframe (no allow-scripts, no allow-same-origin) so nothing in it
// can execute or reach the app, plus an injected CSP that blocks any external
// resource load, plus DOMPurify as defense in depth.
const REPORT_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:;";

// The report's own CSS is LLM-authored and unpredictable, and a handful of
// common patterns make the frame scroll sideways: `width: 100%` plus padding
// under default content-box sizing, `width: 100%` on <body> fighting its default
// margin, fixed pixel widths, wide tables, oversized images, and long
// unbreakable strings (URLs, DOIs, point IDs). These rules keep content within
// the frame by wrapping it rather than clipping it, so nothing becomes
// unreachable.
//
// `max-width` is deliberately not marked !important: it caps a fixed `width`
// regardless of specificity (they are different properties), while still losing
// to an author's own, smaller `max-width` — which is what keeps a centered
// `max-width: 800px` layout intact instead of full-bleeding it.
//
// `height: auto` / `min-height: 0` on the root exist for the auto-sizing below:
// a report styled `html, body { height: 100% }` (or `min-height: 100vh`) reports
// the height of the frame's viewport rather than of its content, so the frame
// would never grow past its initial size and the content would spill out behind
// a scrollbar.
const REPORT_CONTAINMENT_CSS = `
*, *::before, *::after { box-sizing: border-box; }
html, body { width: auto !important; height: auto !important; min-height: 0 !important; }
/* The frame is sized to its content, so the report never needs to scroll
   itself, and on screen it must not be able to: a frame that can scroll even
   one pixel captures the wheel, and the browser keeps the whole gesture latched
   to it, so the page stops scrolling under the cursor until a new gesture
   starts. \`overflow: hidden\` on the root makes the frame a non-scroller, and
   the wheel then goes straight to the page. Screen only, so printing is never
   clipped to what the root shows; the frame's own sizing (see the border note
   on the iframe) is what keeps the content from being cut off on screen. */
html, body { overflow: visible !important; }
@media screen {
  html, body { overflow: hidden !important; }
}
body { overflow-wrap: break-word; }
body * { max-width: 100%; }
img, svg, video, canvas { height: auto; }
pre { overflow-x: auto; white-space: pre-wrap; }
th, td { overflow-wrap: anywhere; }
`;

function injectIntoHead(doc: string): string {
  const meta = `<meta http-equiv="Content-Security-Policy" content="${REPORT_CSP}">`;
  const style = `<style>${REPORT_CONTAINMENT_CSS}</style>`;

  // The CSP meta goes first in <head> so it is in force before any element that
  // could load a resource. The containment CSS goes last, after the document's
  // own <style>, so it wins ties in source order. Inline <style> is permitted by
  // the CSP above.
  if (/<\/head>/i.test(doc)) {
    return doc.replace(/<head[^>]*>/i, (m) => `${m}${meta}`).replace(/<\/head>/i, `${style}</head>`);
  }
  if (/<head[^>]*>/i.test(doc)) return doc.replace(/<head[^>]*>/i, (m) => `${m}${meta}${style}`);
  if (/<html[^>]*>/i.test(doc)) return doc.replace(/<html[^>]*>/i, (m) => `${m}<head>${meta}${style}</head>`);
  return `<!doctype html><html><head>${meta}${style}</head><body>${doc}</body></html>`;
}

function buildSrcDoc(html: string): string {
  // DOMPurify needs a DOM; skip on the server (the iframe renders client-side).
  if (typeof window === 'undefined') return '';
  const clean = DOMPurify.sanitize(html, {
    WHOLE_DOCUMENT: true,
    FORBID_TAGS: ['script'],
    ADD_ATTR: ['target'],
  });
  return injectIntoHead(clean);
}

export interface HtmlReportFrameHandle {
  /** Open the browser print dialog scoped to the report (Save as PDF). */
  print: () => void;
}

interface HtmlReportFrameProps {
  html: string;
  title?: string;
  className?: string;
  ref?: Ref<HtmlReportFrameHandle>;
}

export function HtmlReportFrame({ html, title = 'Report', className, ref }: HtmlReportFrameProps) {
  const srcDoc = useMemo(() => buildSrcDoc(html), [html]);
  const iframeRef = useRef<HTMLIFrameElement>(null);

  useImperativeHandle(ref, () => ({
    print: () => {
      const win = iframeRef.current?.contentWindow;
      if (!win) return;
      win.focus();
      win.print();
    },
  }));

  // Ref callback with cleanup (React 19) rather than an effect: the resizer is
  // an external subscription tied to the element's lifetime, not to a render.
  const attachResizer = useCallback((el: HTMLIFrameElement) => {
    iframeRef.current = el;

    // open-iframe-resizer grows the frame to its content height so the report
    // scrolls with the page instead of in a nested scroll area. For a
    // same-origin frame it measures contentDocument from this side and never
    // injects a script into the report, which is what makes it usable under a
    // sandbox that withholds allow-scripts.
    let handles: InitializeResult[] = [];
    let disposed = false;

    // Coalesced so a resize drag re-measures once per frame, not per event.
    let queued = 0;
    const remeasure = () => {
      if (queued) return;
      queued = requestAnimationFrame(() => {
        queued = 0;
        handles.forEach((handle) => handle.resize());
      });
    };

    // offsetSize adds a pixel of slack to the measured height. Content heights
    // are fractional (a report measuring 286.88px is normal), and if the frame
    // lands even a rounding error short, the report gets a scrollbar with
    // almost no travel — a scrollbar that appears to do nothing. One extra pixel
    // is invisible and removes the whole class of problem.
    initialize({ offsetSize: 1 }, el).then((results) => {
      if (disposed) return results.forEach((r) => r.unsubscribe());
      handles = results;
      remeasure();
    });

    // The library tracks the report with a ResizeObserver on its document. We
    // additionally re-measure on the signals this side owns, because a document
    // that cannot run scripts is an unusual target for that observer and we do
    // not want correct height to depend on it: `load` covers a swapped report
    // and late-decoding images, and a width change (window resize, sidebar
    // toggle) means the text re-wrapped and the height moved with it. Measuring
    // when nothing changed just rewrites the same height, so extra calls are
    // harmless. Width only — height changes are our own writes coming back.
    let lastWidth = el.getBoundingClientRect().width;
    const observer = new ResizeObserver(() => {
      const width = el.getBoundingClientRect().width;
      if (width === lastWidth) return;
      lastWidth = width;
      remeasure();
    });
    observer.observe(el);
    el.addEventListener('load', remeasure);

    return () => {
      disposed = true;
      if (queued) cancelAnimationFrame(queued);
      observer.disconnect();
      el.removeEventListener('load', remeasure);
      handles.forEach((handle) => handle.unsubscribe());
      iframeRef.current = null;
    };
  }, []);

  return (
    <iframe
      ref={attachResizer}
      title={title}
      // No allow-scripts: nothing in the (untrusted, LLM-authored) document can
      // execute — enforced alongside the injected CSP and DOMPurify. allow-same-origin
      // lets the app invoke print() on the frame; allow-modals lets the print
      // dialog open. Neither enables script execution without allow-scripts.
      sandbox="allow-same-origin allow-modals"
      srcDoc={srcDoc}
      className={className ?? 'block w-full rounded-lg border bg-white'}
      // The resizer writes the content height to style.height. Under the app's
      // border-box default the frame's border came out of that height, leaving
      // the report a couple of pixels short of its own content; content-box
      // puts the border outside it.
      style={{ boxSizing: 'content-box' }}
    />
  );
}
