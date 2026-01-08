'use client';

import { DeleteFileDialog } from '@/components/delete-file-dialog';
import { formatFileSize } from '@/components/analysis-form/utils';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { FileUploadButton } from '@/components/ui/file-upload-button';
import { Input } from '@/components/ui/input';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';
import {
  BibliographyItem,
  File as ApiFile,
  FileRole,
  listProjectFilesEndpointApiProjectProjectIdFilesGet,
  uploadProjectFilesEndpointApiProjectProjectIdFilesPost,
  WorkflowRunDetail,
  WorkflowRunType,
} from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import { getWorkflowRunByType } from '@/lib/workflow-state';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Download, FileText, HelpCircle, Loader2, MoreVerticalIcon, Pencil, Search, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

interface FilesTabProps {
  projectId: string;
  allWorkflowDetails: WorkflowRunDetail[];
}

function FileTypeIcon({ fileType }: { fileType?: string | null }) {
  const normalizedType = fileType?.toLowerCase() || '';

  if (normalizedType.includes('pdf') || normalizedType === 'application/pdf') {
    return <FileText className="flex-shrink-0 size-4 text-red-700" />;
  }

  if (
    normalizedType.includes('docx') ||
    normalizedType.includes('doc') ||
    normalizedType === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    normalizedType === 'application/msword'
  ) {
    return <FileText className="flex-shrink-0 size-4 text-blue-700" />;
  }

  return <FileText className="flex-shrink-0 size-4 text-muted-foreground" />;
}

function ExpandableCell({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className="relative">
      <div
        className={cn(
          'line-clamp-2',
          'hover:absolute hover:z-10 hover:line-clamp-none hover:bg-background hover:shadow-lg hover:rounded-lg hover:p-3 hover:-my-7 hover:-mx-3 hover:min-w-full hover:w-max hover:max-w-xl',
          className,
        )}
      >
        {children}
      </div>
    </div>
  );
}

function FileNameLink({ file }: { file: ApiFile }) {
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

export function FilesTab({ projectId, allWorkflowDetails }: FilesTabProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [fileToDelete, setFileToDelete] = useState<ApiFile | null>(null);
  const queryClient = useQueryClient();

  const referenceExtraction = getWorkflowRunByType(allWorkflowDetails, WorkflowRunType.ReferenceExtraction);
  const references = useMemo(
    () => referenceExtraction?.state?.references || [],
    [referenceExtraction?.state?.references],
  );

  const { data: files } = useQuery({
    queryKey: ['files', projectId],
    queryFn: () => listProjectFilesEndpointApiProjectProjectIdFilesGet({ path: { project_id: projectId } }),
  });

  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId);

  const uploadFilesMutation = useMutation<ApiFile[], Error, FileList>({
    mutationFn: async (filesToUpload: FileList) => {
      const filesArray = Array.from(filesToUpload);
      if (filesArray.length === 0) {
        throw new Error('No files selected');
      }

      return await uploadProjectFilesEndpointApiProjectProjectIdFilesPost({
        path: { project_id: projectId },
        body: {
          files: filesArray,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['files', projectId] });
      toast.success('Files uploaded successfully');
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : 'Failed to upload files');
    },
  });

  // Build a map of file names to matched references once
  const matchedReferencesMap = useMemo(() => {
    const map = new Map<string, BibliographyItem>();
    if (references) {
      for (const ref of references) {
        if (ref.name_of_associated_supporting_document) {
          map.set(ref.name_of_associated_supporting_document, ref);
        }
      }
    }
    return map;
  }, [references]);

  // Sort files: main file first, then other files sorted alphabetically by name
  const sortedFiles = useMemo(
    () =>
      [...(files || [])].sort((a, b) => {
        if (a.role === FileRole.Main) return -1;
        if (b.role === FileRole.Main) return 1;
        return (a.file_name || '').localeCompare(b.file_name || '');
      }),
    [files],
  );

  // Filter files based on search query
  const filteredFiles = useMemo(() => {
    if (!searchQuery.trim()) return sortedFiles;
    const query = searchQuery.toLowerCase();
    return sortedFiles.filter((file) => {
      const matchedReference = file.file_name ? matchedReferencesMap.get(file.file_name) : undefined;
      return (
        file.file_name?.toLowerCase().includes(query) ||
        file.description?.toLowerCase().includes(query) ||
        matchedReference?.text?.toLowerCase().includes(query)
      );
    });
  }, [sortedFiles, searchQuery, matchedReferencesMap]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Project Files ({filteredFiles.length}
          {searchQuery ? ` of ${sortedFiles.length}` : ''})
        </h2>
        <div className="flex items-center gap-2">
          <FileUploadButton
            onUpload={uploadFilesMutation.mutate}
            isUploading={uploadFilesMutation.isPending}
            variant="default"
            size="sm"
          >
            Upload Files
          </FileUploadButton>
          {sortedFiles.length > 0 && (
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
      </div>

      {sortedFiles.length > 0 && (
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            placeholder="Search by file name, description, or matched reference..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-9"
          />
        </div>
      )}

      {sortedFiles.length === 0 ? (
        <div className="text-sm text-muted-foreground">No files uploaded.</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Description</TableHead>
              <TableHead>
                <div className="flex items-center gap-1">
                  Matched reference
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <HelpCircle className="size-3.5 text-muted-foreground cursor-help" />
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      The reference item from the main document that was matched to this supporting file.
                    </TooltipContent>
                  </Tooltip>
                </div>
              </TableHead>
              <TableHead className="text-right">Size</TableHead>
              <TableHead className="w-8"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredFiles.map((file) => {
              const isMain = file.role === FileRole.Main;
              const matchedReference = file.file_name ? matchedReferencesMap.get(file.file_name) : undefined;
              return (
                <TableRow key={file.id}>
                  <TableCell className="whitespace-normal break-all max-w-md">
                    <FileNameLink file={file} />
                  </TableCell>
                  <TableCell>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                        isMain ? 'bg-primary/10 text-primary' : 'bg-secondary'
                      }`}
                    >
                      {isMain ? 'Main' : 'Supporting'}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs whitespace-normal">{file.file_type}</TableCell>
                  <TableCell className="text-xs whitespace-normal max-w-sm">
                    {file.description ? (
                      <ExpandableCell>{file.description}</ExpandableCell>
                    ) : (
                      <span className="text-muted-foreground/60">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs whitespace-normal max-w-sm">
                    {matchedReference ? (
                      <ExpandableCell className="italic">{matchedReference.text}</ExpandableCell>
                    ) : (
                      <span className="text-muted-foreground/60">-</span>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-right">{formatFileSize(file.file_size)}</TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="size-8">
                          <MoreVerticalIcon className="size-4" />
                          <span className="sr-only">Open menu</span>
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem disabled={isMain || true} onClick={() => {}}>
                          <Pencil className="size-4" />
                          Change matched reference
                        </DropdownMenuItem>
                        <DropdownMenuItem disabled={isMain} variant="destructive" onClick={() => setFileToDelete(file)}>
                          <Trash2 className="size-4" />
                          Remove file
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}

      {fileToDelete && (
        <DeleteFileDialog
          projectId={projectId}
          file={fileToDelete}
          open={!!fileToDelete}
          onOpenChange={(open) => {
            if (!open) {
              setFileToDelete(null);
            }
          }}
        />
      )}
    </div>
  );
}
