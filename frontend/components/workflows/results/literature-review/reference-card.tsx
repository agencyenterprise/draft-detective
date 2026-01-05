'use client';

import * as React from 'react';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ExternalLink, FileText, Quote, ChevronDown, ChevronUp } from 'lucide-react';
import { DocumentReferenceFactors } from '@/lib/generated-api';
import {
  formatQuality,
  formatReferenceDirection,
  formatReferenceType,
  formatRecommendedAction,
  formatPoliticalBias,
} from './utils';
import { Button } from '@/components/ui/button';

interface ReferenceCardProps {
  reference: DocumentReferenceFactors;
  index: number;
}

export function ReferenceCard({ reference, index }: ReferenceCardProps) {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const quality = formatQuality(reference.quality);
  const direction = formatReferenceDirection(reference.reference_direction);
  const action = formatRecommendedAction(reference.recommended_action);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="space-y-2">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-muted-foreground">#{index + 1}</span>
                <h3 className="font-semibold text-base leading-tight">{reference.title}</h3>
              </div>
              <p className="text-sm text-muted-foreground">
                {reference.authors} ({reference.publication_year})
              </p>
            </div>
            {reference.link && (
              <Button variant="ghost" size="sm" asChild className="shrink-0">
                <a href={reference.link} target="_blank" rel="noopener noreferrer" className="gap-1">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className={`${direction.className} border font-medium`}>
              <span className="mr-1">{direction.icon}</span>
              {direction.label}
            </Badge>
            <Badge variant="outline" className={`${quality.className} border font-medium`}>
              {quality.label}
            </Badge>
            <Badge variant="outline" className={`${action.className} border font-medium`}>
              {action.label}
            </Badge>
            <Badge variant="outline" className="text-muted-foreground">
              {formatReferenceType(reference.reference_type)}
            </Badge>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-2">
          <div className="text-sm font-medium text-muted-foreground">Rationale</div>
          <p className="text-sm leading-relaxed">{reference.rationale}</p>
        </div>

        <div className="space-y-2">
          <div className="text-sm font-medium text-muted-foreground">Recommended Action</div>
          <p className="text-sm leading-relaxed bg-muted/50 p-3 rounded-md">
            {reference.explanation_for_recommended_action}
          </p>
        </div>

        <Button variant="outline" size="sm" className="w-full gap-2" onClick={() => setIsExpanded(!isExpanded)}>
          {isExpanded ? (
            <>
              <ChevronUp className="h-4 w-4" />
              Hide Details
            </>
          ) : (
            <>
              <ChevronDown className="h-4 w-4" />
              Show Details
            </>
          )}
        </Button>

        {isExpanded && (
          <div className="mt-4 space-y-4 pt-4 border-t">
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <Quote className="h-4 w-4" />
                Reference Excerpt
              </div>
              <blockquote className="border-l-4 border-blue-200 bg-blue-50/50 pl-4 py-3 text-sm italic leading-relaxed">
                {reference.reference_excerpt}
              </blockquote>
            </div>

            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                <FileText className="h-4 w-4" />
                Related Excerpt from Document
              </div>
              <blockquote className="border-l-4 border-gray-200 bg-gray-50/50 pl-4 py-3 text-sm leading-relaxed">
                {reference.main_document_excerpt}
              </blockquote>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2 border-t">
              <div>
                <div className="text-xs font-medium text-muted-foreground mb-1">Bibliography</div>
                <p className="text-xs leading-relaxed">{reference.bibliography_info}</p>
              </div>
              <div>
                <div className="text-xs font-medium text-muted-foreground mb-1">Political Bias</div>
                <p className="text-xs">{formatPoliticalBias(reference.political_bias)}</p>
              </div>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
