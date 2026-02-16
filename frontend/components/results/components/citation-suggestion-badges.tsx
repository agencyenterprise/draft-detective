import * as React from 'react';
import { PublicationQuality, ConfidenceInRecommendation, RecommendedAction, ReferenceType } from '@/lib/generated-api';
import { snakeCaseToTitleCase } from '@/lib/utils';

interface BadgeProps {
  className?: string;
}

export function PublicationQualityBadge({ quality, className }: BadgeProps & { quality: PublicationQuality }) {
  const getClasses = (quality: PublicationQuality): string => {
    switch (quality) {
      case PublicationQuality.HighImpactPublication:
        return 'bg-emerald-100 text-emerald-800';
      case PublicationQuality.MediumImpactPublication:
        return 'bg-teal-100 text-teal-800';
      case PublicationQuality.LowImpactPublication:
        return 'bg-slate-100 text-slate-700';
      case PublicationQuality.NotAPublication:
        return 'bg-neutral-100 text-neutral-800';
      default:
        return 'bg-neutral-100 text-neutral-800';
    }
  };

  return (
    <span className={`px-2 py-1 rounded text-xs ${getClasses(quality)} ${className || ''}`}>
      {snakeCaseToTitleCase(quality)}
    </span>
  );
}

export function ConfidenceBadge({ confidence, className }: BadgeProps & { confidence: ConfidenceInRecommendation }) {
  const getClasses = (confidence: ConfidenceInRecommendation): string => {
    switch (confidence) {
      case ConfidenceInRecommendation.High:
        return 'bg-green-100 text-green-800';
      case ConfidenceInRecommendation.Medium:
        return 'bg-yellow-100 text-yellow-800';
      case ConfidenceInRecommendation.Low:
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <span className={`px-2 py-1 rounded text-xs ${getClasses(confidence)} ${className || ''}`}>
      {snakeCaseToTitleCase(confidence)} Confidence
    </span>
  );
}

export function RecommendedActionBadge({ action, className }: BadgeProps & { action: RecommendedAction }) {
  const getClasses = (action: RecommendedAction): string => {
    switch (action) {
      case RecommendedAction.AddNewCitation:
      case RecommendedAction.CiteExistingReferenceInNewPlace:
        return 'bg-green-100 text-green-800';
      case RecommendedAction.ReplaceExistingReference:
        return 'bg-yellow-100 text-yellow-800';
      case RecommendedAction.DiscussReference:
        return 'bg-blue-100 text-blue-800';
      case RecommendedAction.NoAction:
        return 'bg-gray-100 text-gray-800';
      case RecommendedAction.Other:
      default:
        return 'bg-orange-100 text-orange-800';
    }
  };

  return (
    <span className={`px-2 py-1 rounded text-xs ${getClasses(action)} ${className || ''}`}>
      {snakeCaseToTitleCase(action)}
    </span>
  );
}

export function ReferenceTypeBadge({ type, className }: BadgeProps & { type: ReferenceType }) {
  const getClasses = (type: ReferenceType): string => {
    switch (type) {
      case ReferenceType.PeerReviewedPublication:
        return 'bg-indigo-100 text-indigo-800';
      case ReferenceType.Preprint:
        return 'bg-amber-100 text-amber-800';
      case ReferenceType.Book:
        return 'bg-green-100 text-green-800';
      case ReferenceType.GovernmentNgoReport:
        return 'bg-teal-100 text-teal-800';
      case ReferenceType.DataSoftware:
        return 'bg-cyan-100 text-cyan-800';
      case ReferenceType.NewsMedia:
        return 'bg-red-100 text-red-800';
      case ReferenceType.Reference:
        return 'bg-slate-100 text-slate-800';
      case ReferenceType.Webpage:
        return 'bg-purple-100 text-purple-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <span className={`px-2 py-1 rounded text-xs ${getClasses(type)} ${className || ''}`}>
      {snakeCaseToTitleCase(type)}
    </span>
  );
}
