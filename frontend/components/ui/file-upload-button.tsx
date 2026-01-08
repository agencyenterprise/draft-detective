'use client';

import * as React from 'react';
import { Loader2, Upload } from 'lucide-react';
import { Button } from './button';
import { cn } from '@/lib/utils';

export interface FileUploadButtonProps {
  /**
   * Callback when files are selected
   */
  onUpload: (files: FileList) => void;
  /**
   * Whether the upload is in progress
   */
  isUploading?: boolean;
  /**
   * Accepted file types (e.g., '.pdf,.doc,.docx')
   */
  accept?: string;
  /**
   * Whether multiple files can be selected
   */
  multiple?: boolean;
  /**
   * Button variant
   */
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  /**
   * Button size
   */
  size?: 'default' | 'sm' | 'lg' | 'icon' | 'xs';
  /**
   * Button text when not uploading
   */
  children?: React.ReactNode;
  /**
   * Additional className for the button
   */
  className?: string;
  /**
   * Whether the button is disabled
   */
  disabled?: boolean;
}

export function FileUploadButton({
  onUpload,
  isUploading = false,
  accept = '.pdf,.doc,.docx,.txt,.md',
  multiple = true,
  variant = 'default',
  size = 'sm',
  children,
  className,
  disabled = false,
}: FileUploadButtonProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = e.target.files;
    if (selectedFiles && selectedFiles.length > 0) {
      onUpload(selectedFiles);
    }
  };

  const handleUploadClick = () => {
    if (!disabled && !isUploading) {
      fileInputRef.current?.click();
    }
  };

  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        multiple={multiple}
        accept={accept}
        onChange={handleFileSelect}
        className="hidden"
        disabled={disabled || isUploading}
      />
      <Button
        onClick={handleUploadClick}
        disabled={disabled || isUploading}
        variant={variant}
        size={size}
        className={cn(className)}
      >
        {isUploading ? (
          <>
            <Loader2 className="size-4 animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Upload className="size-4" />
            {children || 'Upload Files'}
          </>
        )}
      </Button>
    </>
  );
}
