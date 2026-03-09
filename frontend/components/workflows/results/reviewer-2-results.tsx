import { Markdown } from '@/components/markdown';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Reviewer2State, WorkflowRunDetail } from '@/lib/generated-api';

interface Reviewer2ResultsProps {
  workflowDetail: WorkflowRunDetail;
}

export function Reviewer2Results({ workflowDetail }: Reviewer2ResultsProps) {
  const state = workflowDetail.state as Reviewer2State;

  if (!state?.peer_review_markdown && !state?.rebuttal_markdown) {
    return <div className="p-4 text-center text-muted-foreground">No review available</div>;
  }

  return (
    <Tabs defaultValue="peer-review">
      <TabsList>
        <TabsTrigger value="peer-review">Peer Review</TabsTrigger>
        <TabsTrigger value="rebuttal">Rebuttal</TabsTrigger>
      </TabsList>

      <TabsContent value="peer-review" className="text-sm p-2">
        {state.peer_review_markdown ? (
          <Markdown>{state.peer_review_markdown}</Markdown>
        ) : (
          <div className="p-4 text-center text-muted-foreground">No peer review available</div>
        )}
      </TabsContent>

      <TabsContent value="rebuttal" className="text-sm p-2">
        {state.rebuttal_markdown ? (
          <Markdown>{state.rebuttal_markdown}</Markdown>
        ) : (
          <div className="p-4 text-center text-muted-foreground">No rebuttal available</div>
        )}
      </TabsContent>
    </Tabs>
  );
}
