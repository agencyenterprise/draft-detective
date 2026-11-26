'use client';

import { LiveReportsView } from '@/components/live-reports/live-reports-view';
import { useParams } from 'next/navigation';

/**
 * The live-reports view lives in the layout, not the pages, so it stays mounted
 * between /live-reports and /live-reports/<id>: starting a report navigates to
 * its URL mid-turn, and the turn in flight must survive that. The pages only
 * name the routes.
 */
export default function LiveReportsLayout() {
  const { id } = useParams<{ id?: string }>();
  return <LiveReportsView threadId={id ?? null} />;
}
