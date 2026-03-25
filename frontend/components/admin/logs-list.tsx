'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { downloadLogApiAdminLogsDownloadFilenameGet, listLogsApiAdminLogsGet, LogFileInfo } from '@/lib/generated-api';
import { downloadFile } from '@/lib/file-download';
import { formatBytes } from '@/lib/utils';
import { useQuery } from '@tanstack/react-query';
import { format } from 'date-fns';
import { Download, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

export function LogsList() {
  const [downloading, setDownloading] = useState<string | null>(null);

  const {
    data: logFiles,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['admin', 'logs'],
    queryFn: () => listLogsApiAdminLogsGet(),
  });

  const handleDownload = async (file: LogFileInfo) => {
    setDownloading(file.filename);
    try {
      const content = (await downloadLogApiAdminLogsDownloadFilenameGet({
        path: { filename: file.filename },
      })) as string;
      downloadFile({ blob: new Blob([content], { type: 'text/plain' }), filename: file.filename });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to download log file');
    } finally {
      setDownloading(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Application Logs</CardTitle>
        <CardDescription className="mt-1">
          Daily rotating log files. The current day&apos;s log is <code>app.log</code>; older logs are suffixed with
          their date.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <p className="text-destructive">{error instanceof Error ? error.message : 'Failed to load log files'}</p>
          </div>
        ) : !logFiles || logFiles.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">No log files found.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Filename</TableHead>
                <TableHead>Size</TableHead>
                <TableHead>Last Modified</TableHead>
                <TableHead className="text-right">Download</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {logFiles.map((file: LogFileInfo) => (
                <TableRow key={file.filename}>
                  <TableCell className="font-mono text-sm">{file.filename}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">{formatBytes(file.size_bytes)}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">
                    {format(file.modified_at, 'MMM d, yyyy HH:mm')}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDownload(file)}
                      disabled={downloading === file.filename}
                    >
                      {downloading === file.filename ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Download className="h-4 w-4" />
                      )}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
