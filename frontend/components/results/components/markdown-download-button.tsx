'use client';

import { Markdown } from '@/components/shared/markdown';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ChevronDown, Download, FileText, Loader2, Printer } from 'lucide-react';
import { useRef, useState } from 'react';
import { toast } from 'sonner';

interface MarkdownDownloadButtonProps {
  /** Markdown source to export. */
  markdown: string;
  /** Base file name (without extension) used for the downloaded files. */
  fileName: string;
}

/**
 * A "Download" dropdown that exports the given markdown as DOCX or PDF, entirely
 * client-side. DOCX conversion uses `@mohtasham/md-to-docx`, loaded on demand; PDF uses a print
 * window populated with the rendered markdown and the current page styles.
 */
export function MarkdownDownloadButton({ markdown, fileName }: MarkdownDownloadButtonProps) {
  const [isConverting, setIsConverting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const handleDownloadDocx = async () => {
    setIsConverting(true);
    try {
      // Loaded on click: the DOCX libraries are large and most visits never export.
      const { downloadMarkdownAsDocx } = await import('@/lib/markdown-docx');
      await downloadMarkdownAsDocx(markdown, fileName);
    } catch (error) {
      console.error('Failed to convert markdown to DOCX:', error);
      toast.error('Failed to generate DOCX file');
    } finally {
      setIsConverting(false);
    }
  };

  const handleDownloadPdf = () => {
    if (!contentRef.current) return;
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      toast.error('Please allow pop-ups to download PDF');
      return;
    }

    const styles = Array.from(document.styleSheets)
      .map((sheet) => {
        try {
          return Array.from(sheet.cssRules)
            .map((rule) => rule.cssText)
            .join('\n');
        } catch {
          return '';
        }
      })
      .join('\n');

    // Build the print document via the DOM rather than an interpolated HTML
    // string, so neither `fileName` nor the rendered content can inject markup.
    const printDoc = printWindow.document;
    printDoc.title = fileName;

    const styleEl = printDoc.createElement('style');
    styleEl.textContent = styles;
    printDoc.head.appendChild(styleEl);

    printDoc.body.className = 'p-8 text-sm';
    // Clone the rendered markdown nodes (dropping the off-screen wrapper).
    for (const child of Array.from(contentRef.current.childNodes)) {
      printDoc.body.appendChild(printDoc.importNode(child, true));
    }

    printWindow.addEventListener('afterprint', () => printWindow.close());
    printWindow.print();
  };

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" disabled={isConverting}>
            {isConverting ? <Loader2 className="animate-spin" /> : <Download />}
            {isConverting ? 'Generating...' : 'Download'}
            <ChevronDown />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onClick={handleDownloadDocx} disabled={isConverting}>
            <FileText />
            Download as DOCX
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleDownloadPdf}>
            <Printer />
            Download as PDF
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {/* Off-screen render used solely as the source HTML for the PDF export. */}
      <div ref={contentRef} className="hidden">
        <Markdown>{markdown}</Markdown>
      </div>
    </>
  );
}
