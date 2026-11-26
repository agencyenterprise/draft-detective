import { act, type ComponentProps } from 'react';
import { toast } from 'sonner';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { EditProjectFormValues } from '@/components/projects/edit-project-dialog';
import type { ShareWarningDialog } from '@/components/share/share-warning-dialog';
import { ApiError } from '@/lib/api-error';
import type { Project, ProjectOverview } from '@/lib/generated-api';
import { PROJECT_LIST_QUERY_KEY, projectQueryKeys } from '@/lib/hooks/use-project-data';
import { flush, renderInto, testQueryClient, withQueryClient, type Rendered } from '@/lib/test-render';
import { AnalysisOptionsMenu } from './analysis-options-menu';

const mocks = vi.hoisted(() => ({
  patch: vi.fn(),
  editDialog: null as null | { onConfirm: (values: EditProjectFormValues) => void },
  warningDialog: null as null | Pick<ComponentProps<typeof ShareWarningDialog>, 'onDownload'>,
  enableShare: vi.fn(),
  downloadDocxFile: vi.fn(),
}));
vi.mock('@/lib/generated-api', async (original) => ({
  ...(await original<typeof import('@/lib/generated-api')>()),
  updateProjectEndpointApiProjectProjectIdPatch: mocks.patch,
}));
vi.mock('@/lib/hooks/use-project-data', async (original) => ({
  ...(await original<typeof import('@/lib/hooks/use-project-data')>()),
  useProjectIssues: () => ({ data: undefined, isError: false }),
}));
vi.mock('@/hooks/use-share-status', () => ({
  useShareStatus: () => ({ isEnabled: false, shareStatus: null, setIsDialogOpen: vi.fn(), enable: mocks.enableShare }),
}));
vi.mock('@/context/share-context', () => ({ useShare: () => ({ shareToken: null }) }));
vi.mock('./use-download-docx', async (original) => ({
  ...(await original<typeof import('./use-download-docx')>()),
  useDownloadDocx: () => ({ download: vi.fn(), isDownloading: false }),
  downloadDocxFile: mocks.downloadDocxFile,
}));
// The dialogs have their own tests; here they only hand the menu what the user chose.
vi.mock('@/components/projects/edit-project-dialog', () => ({
  EditProjectDialog: (props: NonNullable<typeof mocks.editDialog>) => {
    mocks.editDialog = props;
    return null;
  },
}));
vi.mock('@/components/share/share-dialog', () => ({ ShareDialog: () => null }));
vi.mock('@/components/share/share-warning-dialog', () => ({
  ShareWarningDialog: (props: NonNullable<typeof mocks.warningDialog>) => {
    mocks.warningDialog = props;
    return null;
  },
}));
vi.mock('./replace-main-document-dialog', () => ({ ReplaceMainDocumentDialog: () => null }));
vi.mock('sonner', () => ({ toast: { success: vi.fn(), error: vi.fn(), loading: vi.fn() } }));

const project = (title: string) => ({ id: 'p', title }) as Project;
const overview = { project: project('Old'), revision: 1 } as ProjectOverview;
const edit: EditProjectFormValues = {
  title: 'New',
  publication_date: '',
  feedback_visibility: null,
  group_by_severity: true,
};

let view: Rendered | undefined;
beforeEach(() => vi.clearAllMocks());
afterEach(async () => {
  await view?.unmount();
  view = undefined;
});

describe('AnalysisOptionsMenu, Edit project details', () => {
  it('refreshes the project list, so going back to it shows the new title', async () => {
    mocks.patch.mockResolvedValue(project('New'));
    const client = testQueryClient();
    client.setQueryData(projectQueryKeys.overview('p', null), overview);
    // The list is a page away, cached: it shows that cache again when the user goes back, unless it is stale.
    client.setQueryData([...PROJECT_LIST_QUERY_KEY, ''], []);

    view = await renderInto(withQueryClient(client, <AnalysisOptionsMenu overview={overview} readOnly={false} />));
    await act(async () => mocks.editDialog?.onConfirm(edit));
    await flush();

    expect(mocks.patch).toHaveBeenCalledWith({
      path: { project_id: 'p' },
      body: { title: 'New', publication_date: null, feedback_visibility: undefined, group_by_severity: true },
    });
    expect(client.getQueryState([...PROJECT_LIST_QUERY_KEY, ''])?.isInvalidated).toBe(true);
  });
});

describe('AnalysisOptionsMenu, Export with share links on an unshared project', () => {
  async function exportWithLinks() {
    view = await renderInto(
      withQueryClient(testQueryClient(), <AnalysisOptionsMenu overview={overview} readOnly={false} />),
    );
    await act(async () => mocks.warningDialog?.onDownload('comments-with-links', { includeEdits: true }));
    await flush();
  }

  it('enables sharing, exports with the new token, and drops the wait notice from the result toast', async () => {
    mocks.enableShare.mockResolvedValue({ share_link: { token: 'tok' } });
    mocks.downloadDocxFile.mockResolvedValue(undefined);

    await exportWithLinks();

    expect(mocks.downloadDocxFile).toHaveBeenCalledWith(
      expect.objectContaining({
        projectId: 'p',
        shareToken: 'tok',
        docxType: 'comments-with-links',
        includeEdits: true,
      }),
    );
    // Sonner merges an update into the loading toast, so its "This may take a few moments" stays unless cleared.
    expect(toast.success).toHaveBeenCalledWith(
      'DOCX file downloaded successfully',
      expect.objectContaining({ description: null }),
    );
  });

  it("shows the server's reason when the export fails", async () => {
    mocks.enableShare.mockResolvedValue({ share_link: { token: 'tok' } });
    mocks.downloadDocxFile.mockRejectedValue(new ApiError(400, 'Revision 3 does not exist'));
    vi.spyOn(console, 'error').mockImplementation(() => {});

    await exportWithLinks();

    expect(toast.error).toHaveBeenCalledWith(
      'Revision 3 does not exist',
      expect.objectContaining({ description: null }),
    );
  });
});
