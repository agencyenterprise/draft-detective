import { useState, useEffect } from 'react';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { CloudDownload, ExternalLink, FileText, FileX, GlobeIcon, Loader2, Trash2, Upload } from 'lucide-react';
import Link from 'next/link';
import { Markdown } from '@/components/markdown';
import { WorkflowConfigDialog, WorkflowConfigFormValues } from '@/components/workflows/workflow-config-dialog';
import { WorkflowRunType } from '@/lib/generated-api';
import { FetchResultsBox } from './fetch-results-box';
import { FileUploadDialog } from './file-upload-dialog';
import {
  useUploadFileMutation,
  useRemoveFileMutation,
  useReplaceFileMutation,
  useFetchFromWebMutation,
} from './mutations';
import { ReferenceReviewItem, ReferenceReviewStatus } from './types';
import { ValidationResultsBox } from './validation-results-box';
import { FileDownloadLink } from '@/components/ui/file-download-link';

function MatchStatusBadge({ status }: { status: ReferenceReviewStatus }) {
  const statusConfig = {
    unmatched: {
      label: 'No matched document',
      icon: FileX,
      className: 'bg-gray-100 text-gray-600 border-gray-200',
      spin: false,
    },
    fetching: {
      label: 'Fetching from web...',
      icon: Loader2,
      className: 'bg-blue-50 text-blue-700 border-blue-200',
      spin: true,
    },
    matched: {
      label: 'Matched',
      icon: CloudDownload,
      className: 'bg-green-50 text-green-700 border-green-200',
      spin: false,
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-xs rounded-full border ${config.className}`}>
      <Icon className={`w-3.5 h-3.5 ${config.spin ? 'animate-spin' : ''}`} />
      {config.label}
    </span>
  );
}

export interface ReferenceCardProps {
  reference: ReferenceReviewItem;
  projectId: string;
  readOnly: boolean;
  disabled?: boolean;
}

type DialogMode = 'upload' | 'replace' | null;

export function ReferenceCard({ reference, projectId, readOnly, disabled = false }: ReferenceCardProps) {
  const { id, index, text, status, matchedFile, fetchResult, validation } = reference;
  const [dialogMode, setDialogMode] = useState<DialogMode>(null);
  const [isFetchDialogOpen, setIsFetchDialogOpen] = useState(false);
  // Track when fetch was initiated locally (optimistic UI)
  const [fetchInitiated, setFetchInitiated] = useState(false);

  const uploadFileMutation = useUploadFileMutation(projectId, id);
  const removeFileMutation = useRemoveFileMutation(projectId, matchedFile?.id);
  const replaceFileMutation = useReplaceFileMutation(projectId, id, matchedFile?.id);
  const fetchFromWebMutation = useFetchFromWebMutation(projectId, id, text);

  const isUploading = uploadFileMutation.isPending;
  const isRemoving = removeFileMutation.isPending;
  const isReplacing = replaceFileMutation.isPending;
  // Show fetching state: during API call OR after success until backend confirms
  const isFetching = fetchFromWebMutation.isPending || (fetchInitiated && status !== 'fetching');
  const isLoading = isUploading || isRemoving || isReplacing || isFetching;
  // Card is disabled when:
  // 1. Local mutation in progress (isLoading)
  // 2. Backend reports this reference is being fetched (status === 'fetching')
  // 3. Global file processing is happening (disabled prop from parent)
  const isDisabled = isLoading || status === 'fetching' || disabled;

  // Clear optimistic state once backend confirms or reference is matched
  useEffect(() => {
    if (fetchInitiated && (status === 'fetching' || status === 'matched')) {
      setFetchInitiated(false);
    }
  }, [fetchInitiated, status]);

  // Effective status for display: show 'fetching' during optimistic period
  const displayStatus = isFetching ? 'fetching' : status;

  const handleDialogConfirm = (files: File[], openaiApiKey: string) => {
    const file = files[0];
    if (!file) return;

    const onSuccess = () => setDialogMode(null);

    if (dialogMode === 'upload') {
      uploadFileMutation.mutate({ file, openaiApiKey }, { onSuccess });
    } else if (dialogMode === 'replace') {
      replaceFileMutation.mutate({ file, openaiApiKey }, { onSuccess });
    }
  };

  const handleFetchFromWebConfirm = (values: WorkflowConfigFormValues) => {
    fetchFromWebMutation.mutate(
      { openaiApiKey: values.openaiApiKey },
      {
        onSuccess: () => {
          setIsFetchDialogOpen(false);
          setFetchInitiated(true); // Optimistic UI: show fetching immediately
        },
      },
    );
  };

  const dialogConfig = {
    upload: {
      title: 'Upload Supporting Document',
      description:
        'Upload a supporting document for this reference. The file will be processed and matched automatically.',
    },
    replace: {
      title: 'Replace Supporting Document',
      description:
        'Upload a new supporting document to replace the current one. The file will be processed and matched automatically.',
    },
  };

  return (
    <div className={cn('border rounded-lg p-4 bg-white transition-all border-gray-200', disabled && 'opacity-60')}>
      <FileUploadDialog
        isOpen={dialogMode !== null}
        isUploading={isUploading || isReplacing}
        title={dialogMode ? dialogConfig[dialogMode].title : ''}
        description={dialogMode ? dialogConfig[dialogMode].description : ''}
        multiple={false}
        onConfirm={handleDialogConfirm}
        onCancel={() => setDialogMode(null)}
      />

      <WorkflowConfigDialog
        isOpen={isFetchDialogOpen}
        type={WorkflowRunType.ReferenceDownloader}
        onConfirm={handleFetchFromWebConfirm}
        onCancel={() => setIsFetchDialogOpen(false)}
      />

      <div className="flex gap-3">
        <span className="text-gray-500 font-medium shrink-0 text-sm">#{index + 1}</span>
        <div className="flex-1 min-w-0 space-y-2">
          {/* Status badges and actions */}
          <div className="flex items-center justify-between gap-2">
            <MatchStatusBadge status={displayStatus} />
            {displayStatus === 'unmatched' && !readOnly && (
              <div className="flex items-center gap-1">
                <Button variant="outline" size="xs" disabled={isDisabled} onClick={() => setIsFetchDialogOpen(true)}>
                  {isFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : <GlobeIcon className="w-4 h-4" />}
                  {isFetching ? 'Fetching...' : 'Fetch from the web'}
                </Button>
                <Button variant="outline" size="xs" onClick={() => setDialogMode('upload')} disabled={isDisabled}>
                  {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {isUploading ? 'Uploading...' : 'Upload supporting document'}
                </Button>
              </div>
            )}
          </div>

          <div className="text-sm leading-relaxed">
            <Markdown>{text}</Markdown>
          </div>

          {matchedFile && (
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded px-2 py-1">
              <FileDownloadLink
                fileId={matchedFile.id}
                className="inline-flex items-center gap-1.5 text-sm group flex-1"
              >
                <FileText className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-primary font-medium truncate max-w-2xl group-hover:underline">
                  {matchedFile.name}
                </span>
                <span className="text-gray-400 text-xs">({matchedFile.size})</span>
                <ExternalLink className="w-3 h-3 text-gray-400" />
              </FileDownloadLink>

              {!readOnly && (
                <div className="flex gap-2 justify-end">
                  <Button variant="outline" size="xs" onClick={() => setDialogMode('replace')} disabled={isDisabled}>
                    {isReplacing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    {isReplacing ? 'Uploading...' : 'Replace'}
                  </Button>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" size="xs" disabled={isDisabled}>
                        {isRemoving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                        {isRemoving ? 'Removing...' : 'Remove'}
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Remove file?</AlertDialogTitle>
                        <AlertDialogDescription className="break-all">
                          Are you sure you want to remove the matched file &quot;{matchedFile?.name}&quot; from this
                          reference?
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                        <AlertDialogAction onClick={() => removeFileMutation.mutate()}>Remove</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>
              )}
            </div>
          )}

          {/* Fetch Results Box */}
          {fetchResult && <FetchResultsBox fetchResult={fetchResult} />}

          {/* Validation Results Box */}
          {validation && <ValidationResultsBox validation={validation} />}
        </div>
      </div>
    </div>
  );
}
