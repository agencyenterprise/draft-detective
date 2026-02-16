'use client';

import * as React from 'react';
import { FileText, BookOpen, AlertTriangle, Loader2, LucideIcon } from 'lucide-react';
import { Card, CardContent } from '../../ui/card';
import { AnimatedNumber } from '../../ui/animated-number';

interface SummaryCardProps {
  icon: LucideIcon;
  iconColor: string;
  value: number;
  label: string;
  isLoading: boolean;
}

function SummaryCard({ icon: Icon, iconColor, value, label, isLoading }: SummaryCardProps) {
  return (
    <Card className={isLoading ? 'border-primary/20' : ''}>
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-2">
            <Icon className={`h-8 w-8 ${iconColor}`} />
            <div>
              {isLoading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                  <div className="text-2xl font-bold text-muted-foreground">—</div>
                </div>
              ) : (
                <div className="text-2xl font-bold">
                  <AnimatedNumber value={value} />
                </div>
              )}
              <p className="text-xs text-muted-foreground">{label}</p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

interface SummaryCardsProps {
  totalClaims: number;
  totalCitations: number;
  totalUnsubstantiated: number;
  isProcessing?: boolean;
}

export function SummaryCards({
  totalClaims,
  totalCitations,
  totalUnsubstantiated,
  isProcessing = false,
}: SummaryCardsProps) {
  const cards = [
    {
      icon: FileText,
      iconColor: 'text-blue-500',
      value: totalClaims,
      label: 'Claims Extracted',
      isLoading: totalClaims === 0 && isProcessing,
    },
    {
      icon: BookOpen,
      iconColor: 'text-green-500',
      value: totalCitations,
      label: 'Citations Found',
      isLoading: totalCitations === 0 && isProcessing,
    },
    {
      icon: AlertTriangle,
      iconColor: 'text-orange-500',
      value: totalUnsubstantiated,
      label: 'Unsubstantiated',
      // Never show loading for unsubstantiated - zero is a valid final state
      isLoading: false,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {cards.map((card) => (
        <SummaryCard key={card.label} {...card} />
      ))}
    </div>
  );
}
