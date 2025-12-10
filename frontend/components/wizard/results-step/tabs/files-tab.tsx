'use client';

import { LabeledValue } from '@/components/labeled-value';
import { ClaimSubstantiationWorkflowDetail, FileDocumentOutput } from '@/lib/generated-api';
import Link from 'next/link';

interface FilesTabProps {
  workflowDetail: ClaimSubstantiationWorkflowDetail | undefined;
}

function FileNameLink({ file }: { file: FileDocumentOutput }) {
  if (!file.fileId) {
    return <span>{file.fileName || 'Unknown'}</span>;
  }

  return (
    <Link href={`/api/files/download/${file.fileId}`} target="_blank" className="text-blue-600 hover:underline">
      {file.fileName || 'Unknown'}
    </Link>
  );
}

export function FilesTab({ workflowDetail }: FilesTabProps) {
  const results = workflowDetail?.state;

  if (!results) {
    return null;
  }

  const mainFile = results.file;
  const supportingFiles = results.supportingFiles || [];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold">Main File</h3>
        <div className="mt-3 border rounded-lg p-4">
          <div className="text-sm space-y-1">
            <LabeledValue label="Name">
              <FileNameLink file={mainFile} />
            </LabeledValue>
            <LabeledValue label="Type">{mainFile.fileType}</LabeledValue>
            <LabeledValue label="Path">{mainFile.filePath}</LabeledValue>
            <LabeledValue label="Approximate Token Count (in markdown content)">
              {mainFile.markdownTokenCount}
            </LabeledValue>
            <div className="mt-3">
              <LabeledValue label="Content converted to markdown">
                <div className="text-xs whitespace-pre-wrap border rounded-md p-3 max-h-64 overflow-auto bg-muted/30">
                  {mainFile.markdown}
                </div>
              </LabeledValue>
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-lg font-semibold">Supporting Files</h3>
        {supportingFiles.length === 0 ? (
          <p className="text-sm text-muted-foreground mt-2">No supporting files uploaded.</p>
        ) : (
          <div className="mt-3 space-y-4">
            {supportingFiles.map((file, index) => (
              <div key={index} className="text-sm space-y-1 border-b pb-4">
                <LabeledValue label="Name">
                  <FileNameLink file={file} />
                </LabeledValue>
                <LabeledValue label="Type">{file.fileType}</LabeledValue>
                <LabeledValue label="Path">{file.filePath}</LabeledValue>
                <LabeledValue label="Approximate Token Count (in markdown content)">
                  {file.markdownTokenCount}
                </LabeledValue>
                <LabeledValue label="Content converted to markdown">
                  <div className="text-xs whitespace-pre-wrap border rounded-md p-3 max-h-64 overflow-auto bg-muted/30">
                    {file.markdown}
                  </div>
                </LabeledValue>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
