'use client';

import { FileUpload } from '@/components/ui/file-upload';
import { FileListItem } from './file-list-item';
import { FileRole } from '@/lib/generated-api';

export interface UploadSectionProps {
  title: string;
  description: string;
  onFilesChange: (files: File[]) => void;
  files: File[];
  fileType: FileRole;
  onRemoveFile: () => void;
}

export const UploadSection = ({
  title,
  description,
  onFilesChange,
  files,
  fileType,
  onRemoveFile,
}: UploadSectionProps) => (
  <div className="space-y-4">
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <h3 className="text-lg font-semibold">
          {title} <span className="text-destructive">*</span>
        </h3>
      </div>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>

    <FileUpload
      files={files}
      onFilesChange={onFilesChange}
      accept=".pdf,.doc,.docx,.txt,.md"
      multiple={false}
      maxSize={80}
      className="h-36 transition-all duration-200"
      compact
    />

    {files[0] && (
      <div className="space-y-1 overflow-y-auto max-h-54">
        <FileListItem file={files[0]} type={fileType} onRemove={onRemoveFile} />
      </div>
    )}
  </div>
);
