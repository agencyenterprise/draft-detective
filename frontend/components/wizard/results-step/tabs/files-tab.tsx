'use client';

import { formatFileSize } from '@/components/analysis-form/utils';
import { LabeledValue } from '@/components/labeled-value';
import { Button } from '@/components/ui/button';
import { File, FileRole, listProjectFilesEndpointApiProjectProjectIdFilesGet } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';
import { Download, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';

interface FilesTabProps {
  projectId: string;
}

function FileNameLink({ file }: { file: File }) {
  if (!file.id) {
    return <span>{file.file_name || 'Unknown'}</span>;
  }

  return (
    <Link href={`/api/files/download/${file.id}`} target="_blank" className="text-blue-600 hover:underline">
      {file.file_name || 'Unknown'}
    </Link>
  );
}

export function FilesTab({ projectId }: FilesTabProps) {
  const { data: files } = useQuery({
    queryKey: ['files', projectId],
    queryFn: () => listProjectFilesEndpointApiProjectProjectIdFilesGet({ path: { project_id: projectId } }),
  });

  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId);

  const mainFile = files?.find((file) => file.role === FileRole.Main);
  const otherFiles = files?.filter((file) => file.role !== FileRole.Main) || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Project Files</h2>
        {files && files.length > 0 && (
          <Button onClick={downloadAll} disabled={isDownloading} variant="outline" size="sm">
            {isDownloading ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Downloading...
              </>
            ) : (
              <>
                <Download className="size-4" />
                Download all files (.zip)
              </>
            )}
          </Button>
        )}
      </div>
      <div>
        <h3 className="text-lg font-semibold">Main File</h3>
        {!mainFile && <div className="text-sm text-muted-foreground mt-2">No main file uploaded.</div>}
        {mainFile && (
          <div className="mt-3 border rounded-lg p-4">
            <div className="text-sm space-y-1">
              <LabeledValue label="Name">
                <FileNameLink file={mainFile} />
              </LabeledValue>
              <LabeledValue label="Type">{mainFile.file_type}</LabeledValue>
              <LabeledValue label="Path">{mainFile.file_path}</LabeledValue>
              <LabeledValue label="Size">{formatFileSize(mainFile.file_size)}</LabeledValue>
              {/* <LabeledValue label="Approximate Token Count (in markdown content)">
                {mainFile.markdown_token_count}
              </LabeledValue>
              <div className="mt-3">
                <LabeledValue label="Content converted to markdown">
                  <div className="text-xs whitespace-pre-wrap border rounded-md p-3 max-h-64 overflow-auto bg-muted/30">
                    {mainFile.markdown}
                  </div>
                </LabeledValue>
              </div> */}
            </div>
          </div>
        )}
      </div>

      <div>
        <h3 className="text-lg font-semibold">Supporting Files ({otherFiles.length})</h3>
        {otherFiles.length === 0 ? (
          <p className="text-sm text-muted-foreground mt-2">No supporting files uploaded.</p>
        ) : (
          <div className="mt-3 space-y-4">
            {otherFiles.map((file) => (
              <div key={file.id} className="text-sm space-y-1 border-b pb-4">
                <LabeledValue label="Name">
                  <FileNameLink file={file} />
                </LabeledValue>
                <LabeledValue label="Type">{file.file_type}</LabeledValue>
                <LabeledValue label="Path">{file.file_path}</LabeledValue>
                <LabeledValue label="Size">{formatFileSize(file.file_size)}</LabeledValue>
                {/* <LabeledValue label="Approximate Token Count (in markdown content)">
                  {file.markdown_token_count}
                </LabeledValue>
                <LabeledValue label="Content converted to markdown">
                  <div className="text-xs whitespace-pre-wrap border rounded-md p-3 max-h-64 overflow-auto bg-muted/30">
                    {file.markdown}
                  </div>
                </LabeledValue> */}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
