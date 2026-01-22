'use client';

import * as React from 'react';
import { Button, buttonVariants } from './button';
import { type VariantProps } from 'class-variance-authority';

export interface UploadButtonProps
  extends Omit<React.ComponentProps<'button'>, 'onChange'>,
    VariantProps<typeof buttonVariants> {
  onFilesSelected: (files: File[]) => void;
  accept?: string;
  multiple?: boolean;
  maxSize?: number; // in MB
}

export function UploadButton({
  onFilesSelected,
  accept = '.pdf,.doc,.docx,.txt,.md',
  multiple = false,
  maxSize = 80,
  children,
  disabled,
  ...buttonProps
}: UploadButtonProps) {
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files) return;

    const files = Array.from(e.target.files);
    const validFiles = files.filter((file) => {
      const sizeMB = file.size / (1024 * 1024);
      return sizeMB <= maxSize;
    });

    onFilesSelected(validFiles);

    setTimeout(() => {
      // Reset input value to allow re-selecting the same file
      e.target.value = '';
    }, 0);
  };

  const openFileDialog = () => {
    if (!disabled) {
      fileInputRef.current?.click();
    }
  };

  return (
    <>
      <Button type="button" disabled={disabled} onClick={openFileDialog} {...buttonProps}>
        {children}
      </Button>
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={handleFileSelect}
        className="hidden"
        disabled={disabled}
      />
    </>
  );
}
