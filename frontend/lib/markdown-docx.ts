import { convertMarkdownToDocx, downloadDocx } from '@mohtasham/md-to-docx';

/**
 * Markdown to DOCX export. The converter pulls in `docx`, highlight.js, JSZip and an XML
 * parser (about 235 KB gzipped), so callers load this module with `import()` when the user asks for a
 * DOCX, never with a static import (the lint config enforces it).
 */

/** Converts markdown to a DOCX blob in the house style used for exports. */
export function markdownToDocx(markdown: string): Promise<Blob> {
  return convertMarkdownToDocx(markdown, {
    style: {
      fontFamily: 'Georgia',
    },
  });
}

/** Converts markdown to DOCX and hands it to the browser as `<fileName>.docx`. */
export async function downloadMarkdownAsDocx(markdown: string, fileName: string): Promise<void> {
  await downloadDocx(await markdownToDocx(markdown), `${fileName}.docx`);
}
