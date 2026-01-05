'use client';

import { formatFileSize } from '@/components/analysis-form/utils';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { File, FileRole, listProjectFilesEndpointApiProjectProjectIdFilesGet } from '@/lib/generated-api';
import { useQuery } from '@tanstack/react-query';
import { Download, FileText, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';

interface FilesTabProps {
  projectId: string;
}

function FileTypeIcon({ fileType }: { fileType?: string | null }) {
  const normalizedType = fileType?.toLowerCase() || '';

  if (normalizedType.includes('pdf') || normalizedType === 'application/pdf') {
    return <FileText className="size-4 text-red-700" />;
  }

  if (
    normalizedType.includes('docx') ||
    normalizedType.includes('doc') ||
    normalizedType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    normalizedType === 'application/msword'
  ) {
    return <FileText className="size-4 text-blue-700" />;
  }

  return <FileText className="size-4 text-muted-foreground" />;
}

function FileNameLink({ file }: { file: File }) {
  if (!file.id) {
    return (
      <div className="flex items-center gap-2">
        <FileTypeIcon fileType={file.file_type} />
        <span>{file.file_name || 'Unknown'}</span>
      </div>
    );
  }

  return (
    <Link
      href={`/api/files/download/${file.id}`}
      target="_blank"
      className="text-blue-600 hover:underline flex items-center gap-2"
    >
      <FileTypeIcon fileType={file.file_type} />
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

  const allFiles = files || [];
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

      {allFiles.length === 0 ? (
        <div className="text-sm text-muted-foreground">No files uploaded.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Description</TableHead>
              <TableHead className="text-right">Size</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {mainFile && (
              <TableRow>
                <TableCell>
                  <FileNameLink file={mainFile} />
                </TableCell>
                <TableCell>
                  <span className="inline-flex items-center rounded-full bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                    Main
                  </span>
                </TableCell>
                <TableCell>{mainFile.file_type}</TableCell>
                <TableCell className="font-mono text-xs">{mainFile.description || '-'}</TableCell>
                <TableCell className="text-right">{formatFileSize(mainFile.file_size)}</TableCell>
              </TableRow>
            )}
            {otherFiles.map((file) => (
              <TableRow key={file.id}>
                <TableCell>
                  <FileNameLink file={file} />
                </TableCell>
                <TableCell>
                  <span className="inline-flex items-center rounded-full bg-secondary px-2 py-1 text-xs font-medium">
                    Supporting
                  </span>
                </TableCell>
                <TableCell>{file.file_type}</TableCell>
                <TableCell className="font-mono text-xs">{file.description || '-'}</TableCell>
                <TableCell className="text-right">{formatFileSize(file.file_size)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </div>
  );
}
