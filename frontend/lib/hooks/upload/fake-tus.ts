/**
 * Test stand-in for `@uppy/tus`. The real Uppy core still runs (restrictions,
 * duplicates, the `complete` result); only the network step is replaced by
 * uploads a test settles by hand. Use it with
 * `vi.mock('@uppy/tus', async () => ({ default: (await import('@/lib/hooks/upload/fake-tus')).FakeTus }))`.
 */

import { BasePlugin, type Meta, type PluginOpts, type Uppy, type UppyFile } from '@uppy/core';

type Body = Record<string, never>;

/** The part of the TUS options the tests call. */
export interface TusOpts extends PluginOpts {
  onBeforeRequest: (req: { setHeader: (key: string, value: string) => void }) => Promise<void>;
}

/** One file the fake uploader holds until the test settles it. */
export interface HeldUpload {
  name: string;
  meta: Meta;
  progress: (bytesUploaded: number, bytesTotal: number) => void;
  succeed: () => void;
  fail: (error: Error) => void;
  /** Whether Uppy itself holds the file paused, not just the hook's status. */
  isPaused: () => boolean;
  /** Whether Uppy has dropped the file, as cancelling does. */
  isGone: () => boolean;
}

/** What the fake has seen since the last `resetFakeTus()`. */
export const fakeTus = { held: [] as HeldUpload[], options: undefined as TusOpts | undefined };

export function resetFakeTus(): void {
  fakeTus.held = [];
  fakeTus.options = undefined;
}

/** The upload of the file called `name`; throws when it never reached the uploader. */
export function heldUpload(name: string): HeldUpload {
  const upload = fakeTus.held.find((h) => h.name === name);
  if (!upload) throw new Error(`${name} never reached the uploader`);
  return upload;
}

export class FakeTus extends BasePlugin<TusOpts, Meta, Body> {
  constructor(uppy: Uppy<Meta, Body>, opts: TusOpts) {
    super(uppy, opts);
    this.id = 'Tus';
    this.type = 'uploader';
    fakeTus.options = opts;
  }

  install() {
    const { capabilities } = this.uppy.getState();
    this.uppy.setState({ capabilities: { ...capabilities, resumableUploads: true } });
    this.uppy.addUploader(this.upload);
  }

  upload = async (fileIDs: string[]) => {
    const files = fileIDs.map((id) => this.uppy.getFile(id));
    this.uppy.emit('upload-start', files);
    await Promise.all(files.map((file) => this.hold(file)));
  };

  private hold(file: UppyFile<Meta, Body>) {
    const current = () => this.uppy.getFile(file.id);
    return new Promise<void>((resolve) => {
      fakeTus.held.push({
        name: file.name ?? '',
        meta: file.meta,
        progress: (bytesUploaded, bytesTotal) =>
          this.uppy.emit('upload-progress', current(), { uploadStarted: Date.now(), bytesUploaded, bytesTotal }),
        succeed: () => {
          this.uppy.emit('upload-success', current(), { uploadURL: `tus/${file.id}`, status: 204 });
          resolve();
        },
        fail: (error) => {
          this.uppy.emit('upload-error', current(), error);
          resolve();
        },
        isPaused: () => current()?.isPaused ?? false,
        isGone: () => !current(),
      });
    });
  }
}
