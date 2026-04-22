import { Badge } from '@/components/ui/badge';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { ClaimCategory } from '@/lib/generated-api';
import { cn } from '@/lib/utils';

const claimCategoryConfig: Record<
  ClaimCategory,
  {
    title: string;
    description: React.ReactNode;
  }
> = {
  [ClaimCategory.EstablishedReportedKnowledge]: {
    title: 'Established Reported Knowledge',
    description: (
      <div className="space-y-1">
        <p>
          <strong>Purpose:</strong> to describe how something was done — datasets, methods, variables, preprocessing,
          analytic choices, and limitations.
        </p>
        <p>
          <strong>Typical content:</strong> description of algorithms, methods, instruments, model architectures, or
          data sources. Contains phrases like &quot;used&quot;, &quot;followed&quot;, &quot;took&quot;,
          &quot;collected&quot;, &quot;preprocessed&quot;, &quot;analyzed&quot;, &quot;validated.&quot; Includes
          adjustments, control variables, data processing, and validation steps.
        </p>
      </div>
    ),
  },
  [ClaimCategory.MethodologyProcedural]: {
    title: 'Methodology and Procedural',
    description: (
      <div className="space-y-1">
        <p>
          <strong>Purpose:</strong> to describe how something was done — datasets, methods, variables, preprocessing,
          analytic choices, and limitations.
        </p>
        <p>
          <strong>Typical content:</strong> description of algorithms, methods, instruments, model architectures, or
          data sources. Contains phrases like &quot;used&quot; &quot;followed&quot; &quot;took&quot;
          &quot;collected&quot;, &quot;preprocessed&quot;, &quot;analyzed&quot;, &quot;validated.&quot; Includes
          adjustments, control variables, data processing, and validation steps.
        </p>
      </div>
    ),
  },
  [ClaimCategory.EmpiricalAnalyticalResults]: {
    title: 'Empirical and Analytical Results',
    description: (
      <div className="space-y-1">
        <p>
          <strong>Purpose:</strong> to present new findings or quantitative results generated within the current work.
        </p>
        <p>
          <strong>Typical content:</strong> measured values, error rates, or discovered patterns. Contains phrases like
          &quot;improved by&quot; &quot;reached equilibrium in&quot; &quot;found a strong correlation between&quot;.
        </p>
      </div>
    ),
  },
  [ClaimCategory.InferentialInterpretiveClaims]: {
    title: 'Interpretive and Inferential Claims',
    description: (
      <div className="space-y-1">
        <p>
          <strong>Purpose:</strong> To draw conclusions, interpretations, or hypotheses from the results of the current
          work, prior theory, and references
        </p>
        <p>
          <strong>Typical content:</strong> Causality, mechanism, theoretical explanation, or significance
          interpretation. Contains phrases like &quot;suggests&quot;, &quot;implies&quot;, &quot;may indicate&quot;,
          &quot;supports&quot;, &quot;implies&quot;, &quot;suggests&quot;, &quot;may indicate&quot;,
          &quot;supports&quot;.
        </p>
      </div>
    ),
  },
  [ClaimCategory.MetaStructuralEvaluative]: {
    title: 'Meta, Structural, and Evaluative',
    description: (
      <div className="space-y-1">
        <p>
          <strong>Purpose:</strong> to manage discourse, describe organization, express novelty or significance.
        </p>
        <p>
          <strong>Typical content:</strong> section transitions, claims of contribution, limitation statements. Contains
          phrases like &quot;in the next section&quot;, &quot;in the following section&quot;.
        </p>
      </div>
    ),
  },
  [ClaimCategory.Other]: {
    title: 'Other',
    description: (
      <div className="space-y-1">
        <p>Other claims that do not fit into the other categories.</p>
      </div>
    ),
  },
};
export interface ClaimCategoryBadgeProps {
  claimCategory: ClaimCategory;
  className?: string;
}

export function ClaimCategoryBadge({ claimCategory, className }: ClaimCategoryBadgeProps) {
  const { title, description } = claimCategoryConfig[claimCategory];

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Badge variant="outline" className={cn(className)}>
          {title}
        </Badge>
      </TooltipTrigger>
      <TooltipContent className="max-w-md py-3 px-4">{description}</TooltipContent>
    </Tooltip>
  );
}
