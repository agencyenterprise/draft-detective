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
import { UploadButton } from '@/components/ui/upload-button';
import { CloudDownload, ExternalLink, FileText, FileX, GlobeIcon, Loader2, Trash2, Upload } from 'lucide-react';
import Link from 'next/link';
import { Markdown } from '@/components/markdown';
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip';
import { FetchResultsBox } from './fetch-results-box';
import {
  useUploadFileMutation,
  useRemoveFileMutation,
  useReplaceFileMutation,
  useFetchFromWebMutation,
} from './mutations';
import { ReferenceReviewItem, ReferenceReviewStatus } from './types';

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
}

export function ReferenceCard({ reference, projectId, readOnly }: ReferenceCardProps) {
  const { index, text, status, matchedFile, fetchResult } = reference;

  const uploadFileMutation = useUploadFileMutation(projectId, index);
  const removeFileMutation = useRemoveFileMutation(projectId, matchedFile?.id);
  const replaceFileMutation = useReplaceFileMutation(projectId, index, matchedFile?.id);
  const fetchFromWebMutation = useFetchFromWebMutation(projectId, index, text);

  const isUploading = uploadFileMutation.isPending;
  const isRemoving = removeFileMutation.isPending;
  const isReplacing = replaceFileMutation.isPending;
  const isFetching = fetchFromWebMutation.isPending;
  const isLoading = isUploading || isRemoving || isReplacing || isFetching;

  return (
    <div className="border rounded-lg p-4 bg-white transition-colors border-gray-200">
      <div className="flex gap-3">
        <span className="text-gray-500 font-medium shrink-0 text-sm">#{index + 1}</span>
        <div className="flex-1 min-w-0 space-y-2">
          {/* Status badges and actions */}
          <div className="flex items-center justify-between gap-2">
            <MatchStatusBadge status={status} />
            {status === 'unmatched' && !readOnly && (
              <div className="flex items-center gap-1">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <Button
                        variant="outline"
                        size="xs"
                        disabled={true}
                        onClick={() => console.log('Batch upload not implemented')}
                      >
                        <GlobeIcon className="w-4 h-4" />
                        Fetch from the web
                      </Button>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>Coming soon</TooltipContent>
                </Tooltip>
                <UploadButton
                  variant="outline"
                  size="xs"
                  onFilesSelected={(files) => uploadFileMutation.mutate(files[0])}
                  disabled={isLoading}
                >
                  {isUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {isUploading ? 'Uploading...' : 'Upload supporting document'}
                </UploadButton>
              </div>
            )}
          </div>

          <div className="text-sm leading-relaxed">
            <Markdown>{text}</Markdown>
          </div>

          {matchedFile && (
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded px-2 py-1">
              <Link
                href={matchedFile.url}
                target="_blank"
                className="inline-flex items-center gap-1.5 text-sm group flex-1"
              >
                <FileText className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-primary font-medium truncate max-w-2xl group-hover:underline">
                  {matchedFile.name}
                </span>
                <span className="text-gray-400 text-xs">({matchedFile.size})</span>
                <ExternalLink className="w-3 h-3 text-gray-400" />
              </Link>

              {!readOnly && (
                <div className="flex gap-2 justify-end">
                  <UploadButton
                    variant="outline"
                    size="xs"
                    onFilesSelected={(files) => replaceFileMutation.mutate(files[0])}
                    disabled={isLoading}
                  >
                    {isReplacing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                    {isReplacing ? 'Uploading...' : 'Replace'}
                  </UploadButton>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="outline" size="xs" disabled={isLoading}>
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
        </div>
      </div>
    </div>
  );
}
