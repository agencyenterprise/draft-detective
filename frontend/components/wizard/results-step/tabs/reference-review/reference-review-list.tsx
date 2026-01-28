import { CopyReferencesDialog } from '@/components/references/copy-references-dialog';
import { Button } from '@/components/ui/button';
import { Callout } from '@/components/ui/callout';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { useDownloadAllProjectFiles } from '@/hooks/use-download-all-project-files';
import { FileRole } from '@/lib/generated-api';
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Download,
  Globe,
  HelpCircle,
  Loader2,
  MoreVerticalIcon,
  Search,
  Upload,
  XCircle,
} from 'lucide-react';
import { useMemo, useState } from 'react';
import { ReferenceCard } from './reference-card';
import { ReferenceReviewItem, ReferenceReviewStatus } from './types';

type StatusFilter = 'all' | ReferenceReviewStatus;

interface ReferenceReviewListProps {
  references: ReferenceReviewItem[];
  projectId: string;
  readOnly: boolean;
  isFetchingAllFromWeb: boolean;
  onFetchAll: () => void;
  isBatchUploading: boolean;
  isProcessingFiles: boolean;
  disableActions: boolean;
  disableIndividualCards: boolean;
  onBatchUpload: () => void;
}

export function ReferenceReviewList({
  references,
  projectId,
  readOnly,
  isFetchingAllFromWeb,
  onFetchAll,
  isBatchUploading,
  isProcessingFiles,
  disableActions,
  disableIndividualCards,
  onBatchUpload,
}: ReferenceReviewListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [copyDialogOpen, setCopyDialogOpen] = useState(false);
  const { downloadAll, isDownloading } = useDownloadAllProjectFiles(projectId, [FileRole.Support]);

  const stats = useMemo(() => {
    const total = references.length;
    const matched = references.filter((ref) => ref.status === 'matched').length;
    const unmatched = references.filter((ref) => ref.status === 'unmatched').length;
    const fetching = references.filter((ref) => ref.status === 'fetching').length;
    const matchedFilesCount = references.filter((ref) => ref.matchedFile).length;

    return { total, matched, unmatched, fetching, matchedFilesCount };
  }, [references]);

  // Filter references based on search query and status filter
  const filteredReferences = useMemo(() => {
    let result = references;

    // Filter by status
    if (statusFilter !== 'all') {
      result = result.filter((ref) => ref.status === statusFilter);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      result = result.filter((reference) => {
        // Search in reference text
        if (reference.text?.toLowerCase().includes(query)) return true;

        // Search in matched document name
        if (reference.matchedFile?.name?.toLowerCase().includes(query)) return true;

        return false;
      });
    }

    return result;
  }, [references, searchQuery, statusFilter]);

  const allReferenceTexts = useMemo(() => references.map((ref) => ref.text), [references]);
  const hasActiveFilters = searchQuery.trim() !== '' || statusFilter !== 'all';

  return (
    <div>
      {/* Header Row */}
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h1 className="text-xl font-semibold text-gray-900 flex items-center gap-2">
            <span>
              References ({filteredReferences.length}
              {hasActiveFilters ? ` of ${stats.total}` : ''})
            </span>
            <Tooltip>
              <TooltipTrigger asChild>
                <HelpCircle className="w-4 h-4 text-muted-foreground cursor-help" />
              </TooltipTrigger>
              <TooltipContent side="right" className="max-w-xs">
                <p>
                  These are the citations we found in your document. Upload the original source PDFs to enable deeper
                  analysis and claim verification.
                </p>
              </TooltipContent>
            </Tooltip>
          </h1>
          {/* Stats */}
          <div className="flex flex-wrap items-center gap-4 mt-2 text-sm">
            <button
              className="inline-flex items-center gap-1.5 text-green-700 hover:underline cursor-pointer"
              onClick={() => setStatusFilter(statusFilter === 'matched' ? 'all' : 'matched')}
            >
              <CheckCircle2 className="w-4 h-4" />
              {stats.matched} matched
            </button>
            <button
              className="inline-flex items-center gap-1.5 text-gray-500 hover:underline cursor-pointer"
              onClick={() => setStatusFilter(statusFilter === 'unmatched' ? 'all' : 'unmatched')}
            >
              <XCircle className="w-4 h-4" />
              {stats.unmatched} need sources
            </button>
            {stats.fetching > 0 && (
              <button
                className="inline-flex items-center gap-1.5 text-blue-600 hover:underline cursor-pointer"
                onClick={() => setStatusFilter(statusFilter === 'fetching' ? 'all' : 'fetching')}
              >
                <Loader2 className="w-4 h-4 animate-spin" />
                {stats.fetching} fetching
              </button>
            )}
          </div>
        </div>
        {!readOnly && (
          <div className="flex flex-wrap items-center gap-2">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" disabled={isFetchingAllFromWeb || disableActions} onClick={onFetchAll}>
                  {isFetchingAllFromWeb ? <Loader2 className="w-4 h-4 animate-spin" /> : <Globe className="w-4 h-4" />}
                  Fetch from web
                </Button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                We&apos;ll try to download the source PDFs automatically using DOIs and URLs found in your references.
              </TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="outline" disabled={isBatchUploading || disableActions} onClick={onBatchUpload}>
                  {isBatchUploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                  {isBatchUploading ? 'Uploading...' : 'Upload PDFs'}
                </Button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                Have the source PDFs on your computer? Upload them and we&apos;ll match them to references
                automatically.
              </TooltipContent>
            </Tooltip>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" size="icon">
                  <MoreVerticalIcon className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onSelect={() => setCopyDialogOpen(true)}>
                  <Copy className="w-4 h-4" />
                  Copy all references
                </DropdownMenuItem>
                <DropdownMenuItem
                  onSelect={() => downloadAll()}
                  disabled={stats.matchedFilesCount === 0 || isDownloading}
                >
                  {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                  {isDownloading
                    ? `Downloading ${stats.matchedFilesCount} files (.zip)...`
                    : `Download all ${stats.matchedFilesCount} files (.zip)`}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
            <CopyReferencesDialog
              references={allReferenceTexts}
              open={copyDialogOpen}
              onOpenChange={setCopyDialogOpen}
            />
          </div>
        )}
      </div>

      {/* Search and filter inputs */}
      {references.length > 0 && (
        <div className="flex gap-3 mb-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
            <Input
              type="search"
              placeholder="Search by reference text or matched file name..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as StatusFilter)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All ({stats.total})</SelectItem>
              <SelectItem value="matched">Matched ({stats.matched})</SelectItem>
              <SelectItem value="unmatched">Unmatched ({stats.unmatched})</SelectItem>
              <SelectItem value="fetching">Fetching ({stats.fetching})</SelectItem>
            </SelectContent>
          </Select>
        </div>
      )}

      {isProcessingFiles && (
        <div className="flex items-center gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg mb-4">
          <Loader2 className="w-5 h-5 animate-spin text-blue-600 shrink-0" />
          <div>
            <p className="font-medium text-blue-900">Processing your files...</p>
            <p className="text-sm text-blue-700">
              We&apos;re indexing and matching documents to references. This usually takes a minute or two.
            </p>
          </div>
        </div>
      )}

      {/* Unmatched References Warning */}
      {stats.unmatched > 0 && !isProcessingFiles && (
        <Callout variant="warning" icon={AlertTriangle} title="Some references need source documents" className="mb-4">
          <button className="text-primary cursor-pointer hover:underline" onClick={() => setStatusFilter('unmatched')}>
            {stats.unmatched} reference{stats.unmatched === 1 ? '' : 's'}
          </button>
          {stats.unmatched === 1 ? " doesn't " : " don't "}
          have source PDFs yet. Upload them or click &quot;Fetch from web&quot; to download automatically.
        </Callout>
      )}

      {/* References List */}
      <div className="space-y-3">
        {filteredReferences.map((reference) => (
          <ReferenceCard
            key={reference.id}
            reference={reference}
            projectId={projectId}
            readOnly={readOnly}
            disabled={disableIndividualCards}
          />
        ))}
        {filteredReferences.length === 0 && hasActiveFilters && (
          <div className="text-center py-8 text-muted-foreground">
            No references found
            {searchQuery && <> matching &quot;{searchQuery}&quot;</>}
            {statusFilter !== 'all' && <> with status &quot;{statusFilter}&quot;</>}
            <p className="mt-2 text-sm">
              <button
                className="text-primary cursor-pointer hover:underline"
                onClick={() => {
                  setStatusFilter('all');
                  setSearchQuery('');
                }}
              >
                Clear filters
              </button>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
