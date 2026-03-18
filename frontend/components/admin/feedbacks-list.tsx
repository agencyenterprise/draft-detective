'use client';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { DocumentIssueCard } from '@/components/results/components/document-issue-card';
import {
  AdminFeedbackItem,
  exportAdminFeedbacksCsvApiAdminFeedbacksExportGet,
  FeedbackType,
  FeedbackVisibility,
  getAdminFeedbacksApiAdminFeedbacksGet,
  Issue,
  listUsersApiUsersGet,
  UserResponse,
  WorkflowRunType,
} from '@/lib/generated-api';
import { downloadFile } from '@/lib/file-download';
import { useWorkflowTypes } from '@/lib/hooks/use-workflow-types';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { ChevronDown, Download, ExternalLinkIcon, Loader2, ThumbsDown, ThumbsUp } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

const VISIBILITY_LABELS: Record<FeedbackVisibility, string> = {
  [FeedbackVisibility.Private]: 'Private',
  [FeedbackVisibility.IssueOnly]: 'Issue Only',
  [FeedbackVisibility.FullProject]: 'Full Project',
};

const ALL_VALUE = '__all__';
const PAGE_SIZE = 25;

function VisibilityBadge({ visibility }: { visibility: FeedbackVisibility }) {
  if (visibility === FeedbackVisibility.FullProject) {
    return <Badge variant="default">{VISIBILITY_LABELS[visibility]}</Badge>;
  }
  return <Badge variant="secondary">{VISIBILITY_LABELS[visibility]}</Badge>;
}

function FeedbackDetailSheet({ item, onClose }: { item: AdminFeedbackItem | null; onClose: () => void }) {
  return (
    <Sheet open={item !== null} onOpenChange={(open) => !open && onClose()}>
      <SheetContent className="w-full sm:max-w-xl flex flex-col p-0 overflow-hidden">
        {item && (
          <>
            {/* Header */}
            <SheetHeader className="px-6 pt-6 pb-4 border-b shrink-0">
              <div className="flex items-start justify-between pr-8">
                <div>
                  <SheetTitle className="text-base">
                    {item.feedback_type === FeedbackType.ThumbsUp ? (
                      <span className="inline-flex items-center gap-2">
                        <ThumbsUp className="h-4 w-4 text-green-600" />
                        Thumbs Up
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2">
                        <ThumbsDown className="h-4 w-4 text-destructive" />
                        Thumbs Down
                      </span>
                    )}
                  </SheetTitle>
                  <SheetDescription className="mt-1">
                    {format(new Date(item.created_at), 'MMM d, yyyy')}
                  </SheetDescription>
                </div>
                <VisibilityBadge visibility={item.visibility} />
              </div>
            </SheetHeader>

            {/* Scrollable body */}
            <div className="flex-1 overflow-y-auto px-6 py-2 space-y-4">
              {/* Project */}
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Project</h3>
                <div className="flex items-center gap-1.5">
                  <span className="text-sm font-medium">{item.project_title}</span>
                  {item.visibility === FeedbackVisibility.FullProject && (
                    <Link href={`/projects/${item.project_id}`} target="_blank">
                      <ExternalLinkIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                    </Link>
                  )}
                </div>
              </section>

              {/* User */}
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">User</h3>
                <div>
                  <p className="text-sm font-medium">{item.user_name}</p>
                  <p className="text-xs text-muted-foreground">{item.user_email}</p>
                </div>
              </section>

              {/* Feedback text */}
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Feedback</h3>
                {item.feedback_text ? (
                  <p className="text-sm italic text-muted-foreground border-l-2 pl-3">{item.feedback_text}</p>
                ) : (
                  <p className="text-sm text-muted-foreground">No additional text provided.</p>
                )}
              </section>

              {/* Issue */}
              <section className="space-y-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Issue</h3>
                <DocumentIssueCard
                  issue={item.issue as Issue}
                  readOnly={true}
                  hideJumpToChunk={true}
                  onSelect={() => {}}
                />
              </section>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}

export function FeedbacksList() {
  const [selectedUserId, setSelectedUserId] = useState<string>(ALL_VALUE);
  const [selectedProjectId, setSelectedProjectId] = useState<string>(ALL_VALUE);
  const [selectedWorkflowType, setSelectedWorkflowType] = useState<string>(ALL_VALUE);
  const [selectedFeedbackType, setSelectedFeedbackType] = useState<string>(ALL_VALUE);
  const [selectedItem, setSelectedItem] = useState<AdminFeedbackItem | null>(null);
  const [isExporting, setIsExporting] = useState(false);

  const { data: workflowTypes, getWorkflowTypeName } = useWorkflowTypes();

  const { data: users } = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => listUsersApiUsersGet(),
  });

  const {
    data: feedbacksData,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey: ['admin', 'feedbacks', selectedUserId, selectedProjectId, selectedWorkflowType, selectedFeedbackType],
    queryFn: ({ pageParam }) =>
      getAdminFeedbacksApiAdminFeedbacksGet({
        query: {
          user_id: selectedUserId !== ALL_VALUE ? selectedUserId : undefined,
          project_id: selectedProjectId !== ALL_VALUE ? selectedProjectId : undefined,
          workflow_type: selectedWorkflowType !== ALL_VALUE ? (selectedWorkflowType as WorkflowRunType) : undefined,
          feedback_type: selectedFeedbackType !== ALL_VALUE ? (selectedFeedbackType as FeedbackType) : undefined,
          limit: PAGE_SIZE,
          offset: pageParam,
        },
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage || lastPage.length < PAGE_SIZE) return undefined;
      return allPages.reduce((acc, page) => acc + page.length, 0);
    },
  });

  const feedbacks = feedbacksData?.pages.flat() ?? [];

  const uniqueProjects = feedbacks
    ? Array.from(new Map(feedbacks.map((f) => [f.project_id, { id: f.project_id, title: f.project_title }])).values())
    : [];

  const clearFilters = () => {
    setSelectedUserId(ALL_VALUE);
    setSelectedProjectId(ALL_VALUE);
    setSelectedWorkflowType(ALL_VALUE);
    setSelectedFeedbackType(ALL_VALUE);
  };

  const hasActiveFilters =
    selectedUserId !== ALL_VALUE ||
    selectedProjectId !== ALL_VALUE ||
    selectedWorkflowType !== ALL_VALUE ||
    selectedFeedbackType !== ALL_VALUE;

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const csv = (await exportAdminFeedbacksCsvApiAdminFeedbacksExportGet({
        query: {
          user_id: selectedUserId !== ALL_VALUE ? selectedUserId : undefined,
          project_id: selectedProjectId !== ALL_VALUE ? selectedProjectId : undefined,
          workflow_type: selectedWorkflowType !== ALL_VALUE ? (selectedWorkflowType as WorkflowRunType) : undefined,
          feedback_type: selectedFeedbackType !== ALL_VALUE ? (selectedFeedbackType as FeedbackType) : undefined,
        },
      })) as string;

      downloadFile({ blob: new Blob([csv]), filename: 'feedbacks.csv' });
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <>
      <Card>
        <CardHeader>
          <div className="flex items-start justify-between">
            <div>
              <CardTitle>User Feedback</CardTitle>
              <CardDescription className="mt-1">
                Feedback shared by users. Click a row to see full details. Only feedback where users have opted to share
                is shown.
              </CardDescription>
            </div>
            <Button variant="outline" size="sm" onClick={handleExport} disabled={isExporting}>
              {isExporting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Download className="h-4 w-4 mr-2" />}
              Export to CSV
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-2 items-center">
            <Select value={selectedFeedbackType} onValueChange={setSelectedFeedbackType}>
              <SelectTrigger className="w-[160px]">
                <SelectValue placeholder="Feedback type" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_VALUE}>All feedback</SelectItem>
                <SelectItem value={FeedbackType.ThumbsUp}>Thumbs Up</SelectItem>
                <SelectItem value={FeedbackType.ThumbsDown}>Thumbs Down</SelectItem>
              </SelectContent>
            </Select>

            <Select value={selectedUserId} onValueChange={setSelectedUserId}>
              <SelectTrigger className="w-[200px]">
                <SelectValue placeholder="All users" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_VALUE}>All users</SelectItem>
                {users?.map((u: UserResponse) => (
                  <SelectItem key={u.id} value={u.id}>
                    {u.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="All projects" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_VALUE}>All projects</SelectItem>
                {uniqueProjects.map((p) => (
                  <SelectItem key={p.id} value={p.id}>
                    {p.title}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={selectedWorkflowType} onValueChange={setSelectedWorkflowType}>
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="All analysis types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_VALUE}>All analysis types</SelectItem>
                {workflowTypes?.map((wt) => (
                  <SelectItem key={wt.type} value={wt.type}>
                    {wt.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {hasActiveFilters && (
              <Button variant="ghost" size="sm" onClick={clearFilters}>
                Clear filters
              </Button>
            )}
          </div>

          {/* Table */}
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-destructive">{error instanceof Error ? error.message : 'Failed to load feedback'}</p>
            </div>
          ) : !feedbacks || feedbacks.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              No shared feedback found{hasActiveFilters && ' for the selected filters'}.
            </div>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                {feedbacks.length} result{feedbacks.length !== 1 ? 's' : ''} &mdash; click a row to view details
              </p>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-8"></TableHead>
                    <TableHead>
                      User <span className="text-xs text-muted-foreground"> (Name / Email)</span>
                    </TableHead>
                    <TableHead>
                      Project <span className="text-xs text-muted-foreground"> (Title / Visibility)</span>
                    </TableHead>
                    <TableHead>
                      Issue <span className="text-xs text-muted-foreground"> (Title / Workflow type)</span>
                    </TableHead>
                    <TableHead>User feedback</TableHead>
                    <TableHead>Feedback Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {feedbacks.map((item: AdminFeedbackItem) => (
                    <TableRow key={item.id} className="cursor-pointer" onClick={() => setSelectedItem(item)}>
                      <TableCell>
                        {item.feedback_type === FeedbackType.ThumbsUp ? (
                          <ThumbsUp className="h-4 w-4 text-green-600" />
                        ) : (
                          <ThumbsDown className="h-4 w-4 text-destructive" />
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="font-medium text-sm">{item.user_name}</div>
                        <div className="text-xs text-muted-foreground">{item.user_email}</div>
                      </TableCell>
                      <TableCell className="max-w-[180px]">
                        <div className="flex items-center gap-1 min-w-0">
                          <span className="text-sm truncate">{item.project_title}</span>
                          {item.visibility === FeedbackVisibility.FullProject && (
                            <Link
                              href={`/projects/${item.project_id}`}
                              target="_blank"
                              className="shrink-0"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ExternalLinkIcon className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                            </Link>
                          )}
                        </div>
                        <div className="mt-0.5">
                          <VisibilityBadge visibility={item.visibility} />
                        </div>
                      </TableCell>
                      <TableCell className="max-w-[220px]">
                        <p className="text-sm truncate">{item.issue.title}</p>
                        <p className="text-xs text-muted-foreground">
                          {getWorkflowTypeName(item.issue.workflow_type as WorkflowRunType)}
                        </p>
                      </TableCell>
                      <TableCell className="max-w-[200px]">
                        {item.feedback_text ? (
                          <p className="text-sm text-muted-foreground italic truncate">
                            &ldquo;{item.feedback_text}&rdquo;
                          </p>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                        {format(new Date(item.created_at), 'MMM d, yyyy')}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              {hasNextPage && (
                <div className="flex justify-center pt-2">
                  <Button variant="outline" size="sm" onClick={() => fetchNextPage()} disabled={isFetchingNextPage}>
                    {isFetchingNextPage ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <ChevronDown className="h-4 w-4 mr-2" />
                    )}
                    Load more
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <FeedbackDetailSheet item={selectedItem} onClose={() => setSelectedItem(null)} />
    </>
  );
}
