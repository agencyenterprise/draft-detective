import { act } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderInto, type Rendered } from '@/lib/test-render';
import { FileUpload } from './file-upload';

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }));

const MB = 1024 * 1024;

function fileOfSize(name: string, bytes: number): File {
  const file = new File(['x'], name);
  Object.defineProperty(file, 'size', { value: bytes });
  return file;
}

async function pick(container: HTMLElement, files: File[]): Promise<void> {
  const input = container.querySelector('input[type="file"]') as HTMLInputElement;
  Object.defineProperty(input, 'files', { value: files, configurable: true });
  await act(async () => {
    input.dispatchEvent(new Event('change', { bubbles: true }));
  });
}

describe('FileUpload size limit', () => {
  let rendered: Rendered;
  const onFilesChange = vi.fn();

  beforeEach(async () => {
    vi.mocked(toast.error).mockClear();
    onFilesChange.mockClear();
    rendered = await renderInto(<FileUpload files={[]} maxSize={80} onFilesChange={onFilesChange} />);
  });

  afterEach(async () => {
    await rendered.unmount();
  });

  it('rejects a file over the limit and tells the user which one and why', async () => {
    await pick(rendered.container, [fileOfSize('big.md', 85 * MB)]);

    expect(onFilesChange).toHaveBeenCalledWith([]);
    expect(toast.error).toHaveBeenCalledOnce();
    expect(vi.mocked(toast.error).mock.calls[0][0]).toContain('big.md');
    expect(vi.mocked(toast.error).mock.calls[0][0]).toContain('80');
  });

  it('passes on the files that fit and rejects only the ones that do not', async () => {
    const small = fileOfSize('small.md', 1 * MB);
    await pick(rendered.container, [small, fileOfSize('big.docx', 85 * MB)]);

    expect(onFilesChange).toHaveBeenCalledWith([small]);
    expect(toast.error).toHaveBeenCalledOnce();
    expect(vi.mocked(toast.error).mock.calls[0][0]).toContain('big.docx');
    expect(vi.mocked(toast.error).mock.calls[0][0]).not.toContain('small.md');
  });

  it('passes on a file that fits without any notice', async () => {
    const small = fileOfSize('small.md', 80 * MB);
    await pick(rendered.container, [small]);

    expect(onFilesChange).toHaveBeenCalledWith([small]);
    expect(toast.error).not.toHaveBeenCalled();
  });
});
