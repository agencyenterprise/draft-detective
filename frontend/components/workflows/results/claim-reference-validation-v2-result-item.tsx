'use client';

import { Markdown } from '@/components/markdown';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ClaimReferenceValidationV2Item, ClaimReferenceValidationV2ItemSource } from '@/lib/generated-api';
import { cn } from '@/lib/utils';
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  FileText,
  Globe,
  ShieldAlert,
  ShieldCheck,
} from 'lucide-react';
import { useState } from 'react';

interface ClaimResultItemProps {
  item: ClaimReferenceValidationV2Item;
  index: number;
}

const alignmentConfig = {
  supported: {
    label: 'Supported',
    icon: ShieldCheck,
    badgeClass: 'border-green-300 bg-green-50 text-green-700',
  },
  partially_supported: {
    label: 'Partially Supported',
    icon: CheckCircle2,
    badgeClass: 'border-yellow-300 bg-yellow-50 text-yellow-700',
  },
  unsupported: {
    label: 'Unsupported',
    icon: ShieldAlert,
    badgeClass: 'border-red-300 bg-red-50 text-red-700',
  },
  unverifiable: {
    label: 'Unverifiable',
    icon: CircleHelp,
    badgeClass: 'border-gray-300 bg-gray-50 text-gray-700',
  },
} as const;

export function ClaimResultItem({ item, index }: ClaimResultItemProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const config = alignmentConfig[item.evidence_alignment] ?? alignmentConfig.unverifiable;
  const AlignmentIcon = config.icon;

  return (
    <div className="rounded-lg border bg-card">
      <div className="p-4 bg-gray-50 rounded-t-lg space-y-2">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium text-muted-foreground">#{index + 1}</span>
            <Badge variant="outline" className={cn('text-xs', config.badgeClass)}>
              <AlignmentIcon className="mr-1 h-3 w-3" />
              {config.label}
            </Badge>
            <span className="text-xs text-muted-foreground">
              Lines {item.line_start}–{item.line_end}
            </span>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="shrink-0 text-gray-600 hover:text-gray-900"
          >
            {isExpanded ? (
              <>
                <ChevronDown className="h-4 w-4 mr-1" />
                Hide Details
              </>
            ) : (
              <>
                <ChevronRight className="h-4 w-4 mr-1" />
                View Details
              </>
            )}
          </Button>
        </div>

        <blockquote className="border-l-2 border-muted-foreground/30 pl-3 text-sm italic text-muted-foreground">
          &ldquo;{item.key_sentence}&rdquo;
        </blockquote>

        <p className="text-sm">{item.rationale}</p>
      </div>

      {isExpanded && (
        <div className="p-4 space-y-4 border-t">
          <div>
            <h4 className="text-sm font-semibold mb-2">Detailed Rationale</h4>
            <div className="text-sm prose prose-sm max-w-none">
              <Markdown>{item.long_rationale}</Markdown>
            </div>
          </div>

          <div>
            <h4 className="text-sm font-semibold mb-2">Feedback</h4>
            <p className="text-sm text-muted-foreground">{item.feedback}</p>
          </div>

          {item.evidence_sources.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold mb-2">Evidence Sources ({item.evidence_sources.length})</h4>
              <div className="space-y-2">
                {item.evidence_sources.map((source, sourceIndex) => (
                  <EvidenceSourceCard key={sourceIndex} source={source} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function EvidenceSourceCard({ source }: { source: ClaimReferenceValidationV2ItemSource }) {
  const isWeb = source.type === 'web';

  return (
    <div className="rounded-md border bg-muted/30 p-3 space-y-1.5">
      <div className="flex items-center gap-2">
        {isWeb ? (
          <Globe className="h-3.5 w-3.5 text-blue-600 shrink-0" />
        ) : (
          <FileText className="h-3.5 w-3.5 text-gray-600 shrink-0" />
        )}
        <span className="text-sm font-medium truncate">{source.title}</span>
        <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">
          {isWeb ? 'Web' : 'File'}
        </Badge>
      </div>
      <p className="text-xs text-muted-foreground">{source.location}</p>
      <blockquote className="border-l-2 border-muted-foreground/20 pl-2 text-xs italic text-muted-foreground">
        {source.snippet}
      </blockquote>
      <p className="text-xs text-muted-foreground/70 truncate">{source.source_reference}</p>
    </div>
  );
}
