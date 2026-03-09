import { Markdown } from '@/components/markdown';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Reviewer2State, WorkflowRunDetail } from '@/lib/generated-api';
import { convertMarkdownToDocx, downloadDocx } from '@mohtasham/md-to-docx';
import { ChevronDown, Download, FileText, Loader2, Printer } from 'lucide-react';
import { useRef, useState } from 'react';
import { toast } from 'sonner';

interface Reviewer2ResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function Reviewer2Results({ workflowDetail }: Reviewer2ResultsProps) {
  const state = workflowDetail.state as Reviewer2State;
  const [activeTab, setActiveTab] = useState('peer-review');
  const [isConverting, setIsConverting] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  if (!state?.peer_review_markdown && !state?.rebuttal_markdown) {
    return <div className="p-4 text-center text-muted-foreground">No review available</div>;
  }

  const activeMarkdown = activeTab === 'peer-review' ? state.peer_review_markdown : state.rebuttal_markdown;

  const handleDownloadDocx = async () => {
    if (!activeMarkdown) return;
    setIsConverting(true);
    try {
      const blob = await convertMarkdownToDocx(activeMarkdown, {
        style: {
          fontFamily: 'Georgia',
        },
      });
      downloadDocx(blob, `${activeTab}.docx`);
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

    printWindow.document.write(`<!DOCTYPE html>
<html><head><title>${activeTab}</title><style>${styles}</style></head>
<body class="p-8 text-sm">${contentRef.current.innerHTML}</body></html>`);
    printWindow.document.close();
    printWindow.addEventListener('afterprint', () => printWindow.close());
    printWindow.print();
  };

  return (
    <Tabs value={activeTab} onValueChange={setActiveTab}>
      <div className="flex items-center justify-between">
        <TabsList>
          <TabsTrigger value="peer-review">Peer Review</TabsTrigger>
          <TabsTrigger value="rebuttal">Rebuttal</TabsTrigger>
        </TabsList>

        {activeMarkdown && (
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
        )}
      </div>

      <TabsContent value="peer-review" className="text-sm p-2">
        {state.peer_review_markdown ? (
          <div ref={activeTab === 'peer-review' ? contentRef : undefined}>
            <Markdown>{state.peer_review_markdown}</Markdown>
          </div>
        ) : (
          <div className="p-4 text-center text-muted-foreground">No peer review available</div>
        )}
      </TabsContent>

      <TabsContent value="rebuttal" className="text-sm p-2">
        {state.rebuttal_markdown ? (
          <div ref={activeTab === 'rebuttal' ? contentRef : undefined}>
            <Markdown>{state.rebuttal_markdown}</Markdown>
          </div>
        ) : (
          <div className="p-4 text-center text-muted-foreground">No rebuttal available</div>
        )}
      </TabsContent>
    </Tabs>
  );
}
