'use client';

import * as React from 'react';
import { Upload } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from './card';

export interface FileUploadProps {
  files: File[];
  accept?: string;
  acceptLabel?: string;
  multiple?: boolean;
  maxSize?: number; // in MB
  onFilesChange: (files: File[]) => void;
  className?: string;
  disabled?: boolean;
  compact?: boolean;
}

export function FileUpload({
  files,
  accept = '.pdf,.doc,.docx,.txt,.md',
  acceptLabel = 'PDF, DOC, DOCX, TXT, MD',
  multiple = true,
  maxSize = 80,
  onFilesChange,
  className,
  disabled = false,
  compact = false,
}: FileUploadProps) {
  const [isDragOver, setIsDragOver] = React.useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);

    if (disabled) return;

    const files = Array.from(e.dataTransfer.files);
    handleFiles(files);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;

    const files = Array.from(e.target.files);
    handleFiles(files);

    setTimeout(() => {
      // Reset input value to allow re-selecting the same file
      // It needs to be done in a separate tick otherwise the file is lost before consumers are able to access it
      e.target.value = '';
    }, 0);
  };

  const handleFiles = (newFiles: File[]) => {
    const validFiles = newFiles.filter((file) => {
      const sizeMB = file.size / (1024 * 1024);
      return sizeMB <= maxSize;
    });

    const updatedFiles = multiple ? [...files, ...validFiles] : validFiles;
    onFilesChange(updatedFiles);
  };

  const openFileDialog = () => {
    if (!disabled) {
      fileInputRef.current?.click();
    }
  };

  return (
    <div className={cn('w-full group', className)}>
      <Card
        className={cn(
          'border-2 border-dashed transition-all duration-200 cursor-pointer overflow-hidden',
          'hover:border-primary/40 hover:bg-primary/5 hover:shadow-sm',
          isDragOver && !disabled && 'border-primary bg-primary/10 shadow-md scale-[1.02]',
          disabled && 'opacity-50 cursor-not-allowed hover:border-dashed hover:bg-transparent hover:shadow-none',
          compact && 'h-full',
        )}
      >
        <CardContent
          className={cn(
            'flex flex-col items-center justify-center h-full relative',
            compact ? 'py-8 px-6' : 'py-10 px-8',
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={openFileDialog}
        >
          <div className="flex flex-col items-center justify-center space-y-2">
            <div
              className={cn(
                'rounded-full p-3 transition-all duration-200',
                'bg-muted/50 group-hover:bg-primary/10 group-hover:scale-110',
                isDragOver && !disabled && 'bg-primary/15 scale-110',
              )}
            >
              <Upload
                className={cn(
                  'transition-all duration-200',
                  compact ? 'w-6 h-6' : 'w-8 h-8',
                  'text-muted-foreground group-hover:text-primary',
                  isDragOver && !disabled && 'text-primary scale-110',
                )}
              />
            </div>
            <div className="text-center space-y-1">
              <p
                className={cn(
                  'font-medium transition-colors duration-200',
                  compact ? 'text-sm' : 'text-base',
                  'text-foreground group-hover:text-primary',
                )}
              >
                {isDragOver && !disabled ? 'Release to upload' : 'Drop or click to upload'}
              </p>
              {compact && (
                <p className="text-xs text-muted-foreground">
                  {acceptLabel} • Max {maxSize}MB
                </p>
              )}
              {!compact && (
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Supports: {acceptLabel}</p>
                  <p className="text-xs text-muted-foreground font-medium">Maximum {maxSize}MB per file</p>
                </div>
              )}
            </div>
          </div>

          {/* Subtle visual feedback overlay */}
          <div
            className={cn(
              'absolute inset-0 bg-gradient-to-t from-primary/5 to-transparent opacity-0 transition-opacity duration-200',
              'group-hover:opacity-100',
            )}
          />
        </CardContent>
      </Card>

      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleFileSelect}
        className="hidden"
        disabled={disabled}
      />
    </div>
  );
}
