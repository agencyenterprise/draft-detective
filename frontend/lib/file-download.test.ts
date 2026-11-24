import { afterEach, describe, expect, it, vi } from 'vitest';
import { filenameFromContentDisposition, saveFileResponse } from './file-download';

describe('filenameFromContentDisposition', () => {
  it('reads a quoted filename', () => {
    expect(filenameFromContentDisposition('attachment; filename="Report v3_comments.docx"')).toBe(
      'Report v3_comments.docx',
    );
  });

  it('reads an unquoted filename', () => {
    expect(filenameFromContentDisposition('attachment; filename=report.docx')).toBe('report.docx');
  });

  it('prefers the encoded form, which carries non-ASCII names', () => {
    // What Starlette's FileResponse sends for a name it cannot put in plain ASCII.
    const header = "attachment; filename*=utf-8''Relat%C3%B3rio_comments.docx";
    expect(filenameFromContentDisposition(header)).toBe('Relatório_comments.docx');
  });

  it('falls back to the plain form when the encoded one is malformed', () => {
    const header = `attachment; filename="fallback.docx"; filename*=utf-8''%E0%A4%A.docx`;
    expect(filenameFromContentDisposition(header)).toBe('fallback.docx');
  });

  it('returns null when there is no filename', () => {
    expect(filenameFromContentDisposition(null)).toBeNull();
    expect(filenameFromContentDisposition('attachment')).toBeNull();
  });
});

describe('saveFileResponse', () => {
  afterEach(() => vi.restoreAllMocks());

  function savedName(headers: HeadersInit): string {
    vi.spyOn(URL, 'createObjectURL').mockReturnValue('blob:x');
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    saveFileResponse({ data: new Blob(['x']), response: new Response(null, { headers }) }, 'fallback.zip');
    return (click.mock.contexts[0] as HTMLAnchorElement).download;
  }

  it('saves the file under the name the server gives', () => {
    expect(savedName({ 'content-disposition': 'attachment; filename="Report_files.zip"' })).toBe('Report_files.zip');
  });

  it('falls back to the given name when the server gives none', () => {
    expect(savedName({})).toBe('fallback.zip');
  });

  it('refuses a body that is not a file', () => {
    expect(() => saveFileResponse({ data: { detail: 'x' }, response: new Response() }, 'f.zip')).toThrow();
  });
});
