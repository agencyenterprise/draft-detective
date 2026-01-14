'use client';

import { FileUpload } from '@/components/ui/file-upload';
import { FileListItem } from './file-list-item';

export interface UploadSectionProps {
  title: string;
  description: string;
  onFilesChange: (files: File[]) => void;
  multiple: boolean;
  files: File[];
  fileType: 'main' | 'supporting';
  required: boolean;
  onRemoveFile: (index?: number) => void;
}

export const UploadSection = ({
  title,
  description,
  required,
  onFilesChange,
  multiple,
  files,
  fileType,
  onRemoveFile,
}: UploadSectionProps) => (
  <div className="space-y-4">
    <div className="space-y-1">
      <div className="flex items-center gap-3">
        <h3 className="text-lg font-semibold">
          {title} {required && <span className="text-destructive">*</span>}
          {!required && <span className="text-muted-foreground text-sm font-normal">(Optional)</span>}
        </h3>
      </div>
      <p className="text-sm text-muted-foreground">{description}</p>
    </div>

    <FileUpload
      onFilesChange={onFilesChange}
      accept=".pdf,.doc,.docx,.txt,.md"
      multiple={multiple}
      maxSize={80}
      className="h-36 transition-all duration-200"
      compact
    />

    {files.length > 0 && (
      <div className="space-y-1 overflow-y-auto max-h-54">
        {files.map((file, index) => (
          <FileListItem
            key={multiple ? index : 'single'}
            file={file}
            type={fileType}
            onRemove={() => onRemoveFile(multiple ? index : undefined)}
          />
        ))}
      </div>
    )}
  </div>
);
