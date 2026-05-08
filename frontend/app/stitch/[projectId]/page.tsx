'use client';

import {
  categoryLabels,
  getScenario,
  scenarioOptions,
  severityLabels,
  severityLabelsPlural,
  StitchHeaderStatus,
  StitchHighlight,
  StitchIssue,
  workflowLabels,
} from '@/lib/stitch-mock-data';
import { useParams, useRouter } from 'next/navigation';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

/* ── Stitch design tokens (seed — expand as the palette formalizes) ── */

const S = {
  primary: '#002045',
  primaryContainer: '#1a365d',
  primaryFixed: '#d6e3ff',
  primaryFixedDim: '#adc7f7',
  surface: '#f7fafc',
  surfaceLow: '#f1f4f6',
  surfaceContainer: '#ebeef0',
  surfaceHigh: '#e5e9eb',
  surfaceLowest: '#ffffff',
  onSurface: '#181c1e',
  onSurfaceVariant: '#43474e',
  secondary: '#545f72',
} as const;

/* ── Toast (ephemeral feedback) ── */

function AcceptedToast({ text, onDone }: { text: string; onDone: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDone, 2200);
    return () => clearTimeout(t);
  }, [onDone]);
  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 animate-[fadeInUp_300ms_ease-out]"
      style={{
        backgroundColor: S.primaryContainer,
        color: S.primaryFixed,
        fontFamily: "'Inter', sans-serif",
        fontSize: '0.8125rem',
        fontWeight: 600,
        padding: '0.625rem 1.25rem',
        borderRadius: '6px',
        boxShadow: '0 8px 32px rgba(0,32,69,0.15)',
      }}
    >
      ✓ {text}
    </div>
  );
}

/* ── Severity → color map ── */

const SEVERITY_COLOR: Record<StitchIssue['severity'], string> = {
  critical: '#f43f5e',
  warning: '#f59e0b',
  suggestion: '#60a5fa',
};

const SEVERITY_RANK: Record<StitchIssue['severity'], number> = {
  critical: 3,
  warning: 2,
  suggestion: 1,
};

function maxSeverity(issues: StitchIssue[]): StitchIssue['severity'] | null {
  if (issues.length === 0) return null;
  return issues.reduce<StitchIssue['severity']>(
    (acc, i) => (SEVERITY_RANK[i.severity] > SEVERITY_RANK[acc] ? i.severity : acc),
    issues[0].severity,
  );
}

/* ── Severity dot ── */

function SeverityDot({ severity, size = 'sm' }: { severity: StitchIssue['severity']; size?: 'sm' | 'md' }) {
  const bg = { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[severity];
  const cls = size === 'md' ? 'w-2.5 h-2.5' : 'w-2 h-2';
  return (
    <span
      className={`${cls} rounded-full shrink-0 inline-block`}
      style={{ backgroundColor: bg }}
      role="img"
      aria-label={`${severity} severity`}
    />
  );
}

/* ── Issue Card ── */

function IssueCard({
  issue,
  isActive,
  status,
  onClick,
  onAccept,
  onDismiss,
  onUndo,
}: {
  issue: StitchIssue;
  isActive: boolean;
  status?: 'accepted';
  onClick: () => void;
  onAccept: () => void;
  onDismiss: () => void;
  onUndo: () => void;
}) {
  const severityColor = { critical: '#f43f5e', warning: '#f59e0b', suggestion: '#60a5fa' }[issue.severity];
  const isAccepted = status === 'accepted';
  const isResolved = !!issue.resolved;
  const isAddressed = isAccepted || isResolved;

  return (
    <div
      id={`issue-card-${issue.id}`}
      role="button"
      tabIndex={0}
      onClick={onClick}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
      aria-pressed={isActive}
      className="w-full text-left rounded-[4px] p-4 cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
      style={{
        backgroundColor: isActive ? '#fafbfc' : '#ffffff',
        boxShadow: isActive ? '0 4px 20px rgba(24,28,30,0.08)' : '0 1px 3px rgba(24,28,30,0.04)',
        borderLeft: `3px solid ${isActive ? severityColor : 'transparent'}`,
        borderTop: '1px solid #e5e9eb',
        borderRight: '1px solid #e5e9eb',
        borderBottom: '1px solid #e5e9eb',
        opacity: isAddressed ? 0.65 : 1,
        transition: 'background-color 150ms, box-shadow 150ms, opacity 200ms',
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = '#f7fafc';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = isActive ? '#fafbfc' : '#ffffff';
      }}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <SeverityDot severity={issue.severity} />
          <span
            className="text-[11px] font-semibold truncate"
            style={{ fontFamily: "'Manrope', sans-serif", color: '#43474e' }}
          >
            {categoryLabels[issue.category]}
          </span>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className="text-[10px] px-1.5 py-0.5 rounded-[3px] font-semibold"
            style={{
              backgroundColor:
                issue.severity === 'critical' ? '#fef2f2' : issue.severity === 'warning' ? '#fffbeb' : '#eff6ff',
              color: severityColor,
            }}
          >
            {severityLabels[issue.severity]}
          </span>
          <span className="text-[10px]" style={{ color: '#545f72' }}>
            ¶{issue.paragraph}
          </span>
        </div>
      </div>

      {/* Title */}
      <p
        className="text-[13px] font-semibold mb-0.5"
        style={{ fontFamily: "'Manrope', sans-serif", color: '#181c1e', overflowWrap: 'break-word' }}
      >
        {issue.title}
      </p>

      {/* Workflow subtitle */}
      <p
        className="text-[10px] mb-1.5"
        style={{ fontFamily: "'Inter', sans-serif", color: '#6b7280', letterSpacing: '0.01em' }}
      >
        via {workflowLabels[issue.category]}
      </p>

      {/* Description */}
      <p
        className="italic text-[13px] leading-relaxed"
        style={{ fontFamily: "'Newsreader', serif", color: '#43474e', overflowWrap: 'break-word' }}
      >
        {issue.description}
      </p>

      {/* Proposed change */}
      {issue.proposedChange && (
        <div className="mt-3 p-3 rounded-[3px]" style={{ backgroundColor: '#f7fafc' }}>
          <p className="text-[10px] font-semibold mb-1" style={{ fontFamily: "'Inter', sans-serif", color: '#545f72' }}>
            Proposed change
          </p>
          <p
            className="text-[13px]"
            style={{ fontFamily: "'Newsreader', serif", color: '#002045', overflowWrap: 'break-word' }}
          >
            {issue.proposedChange}
          </p>
        </div>
      )}

      {/* Actions */}
      {isResolved ? (
        <div className="mt-3">
          <span
            className="flex items-center gap-1 text-[11px] font-semibold"
            style={{ fontFamily: "'Inter', sans-serif", color: '#6b7280' }}
          >
            <span aria-hidden>✓</span> Resolved
          </span>
        </div>
      ) : isAccepted ? (
        <div className="flex items-center justify-between mt-3">
          <span
            className="flex items-center gap-1 text-[11px] font-semibold"
            style={{ fontFamily: "'Inter', sans-serif", color: '#047857' }}
          >
            <span aria-hidden>✓</span> Accepted
          </span>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onUndo();
            }}
            className="text-[11px] font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{ fontFamily: "'Inter', sans-serif", color: '#545f72' }}
          >
            Undo
          </button>
        </div>
      ) : (
        <div className="flex gap-2 mt-3">
          {issue.proposedChange && (
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onAccept();
              }}
              className="flex-1 py-1.5 text-[11px] font-bold rounded-[3px] text-center hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
              style={{
                background: 'linear-gradient(135deg, #002045, #1a365d)',
                color: '#fff',
                transition: 'opacity 150ms',
              }}
            >
              Accept
            </button>
          )}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss();
            }}
            className="flex-1 py-1.5 text-[11px] font-bold rounded-[3px] text-center focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
            style={{ backgroundColor: '#e5e9eb', color: '#181c1e', transition: 'background-color 150ms' }}
            onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = '#e0e3e5')}
            onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = '#e5e9eb')}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}

/* ── Inline highlight renderer ── */

const HIGHLIGHT_STYLE: Record<StitchIssue['severity'], { bg: string; border: string; borderWidth: string }> = {
  critical: { bg: 'rgba(244, 63, 94, 0.18)', border: '#f43f5e', borderWidth: '2.5px' },
  warning: { bg: 'rgba(245, 158, 11, 0.16)', border: '#f59e0b', borderWidth: '2px' },
  suggestion: { bg: 'rgba(96, 165, 250, 0.12)', border: '#60a5fa', borderWidth: '1.5px' },
};

function HighlightedText({
  text,
  highlights,
  issues,
  activeIssueId,
}: {
  text: string;
  highlights?: StitchHighlight[];
  issues: StitchIssue[];
  activeIssueId: string | null;
}) {
  if (!highlights || highlights.length === 0) return <>{text}</>;

  const sorted = [...highlights].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;

  sorted.forEach((h, i) => {
    if (h.start > cursor) parts.push(<span key={`t-${i}`}>{text.slice(cursor, h.start)}</span>);
    const issue = issues.find((iss) => iss.id === h.issueId);
    const severity = issue?.severity ?? 'warning';
    const style = HIGHLIGHT_STYLE[severity];
    const isActive = activeIssueId === h.issueId;
    parts.push(
      <span
        key={`h-${i}`}
        style={{
          backgroundColor: isActive
            ? style.bg.replace(/[\d.]+\)$/, (m) => `${Math.min(parseFloat(m) * 1.6, 0.32)})`)
            : style.bg,
          borderBottom: `${style.borderWidth} solid ${style.border}`,
          padding: '1px 2px',
          borderRadius: '2px',
          transition: 'background-color 150ms',
        }}
      >
        {text.slice(h.start, h.end)}
      </span>,
    );
    cursor = h.end;
  });
  if (cursor < text.length) parts.push(<span key="end">{text.slice(cursor)}</span>);
  return <>{parts}</>;
}

/* ── Scenario picker ── */

function ScenarioPicker({ current }: { current: string }) {
  const router = useRouter();
  return (
    <label className="flex items-center gap-1.5 shrink-0" style={{ fontFamily: "'Inter', sans-serif" }}>
      <span className="text-[10px] uppercase tracking-wide hidden md:inline" style={{ color: '#545f72' }}>
        Scenario
      </span>
      <select
        value={current}
        onChange={(e) => router.push(`/stitch/${e.target.value}`)}
        className="text-[11px] font-semibold rounded-[3px] px-2 py-1 border focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#002045]"
        style={{ backgroundColor: '#f7fafc', color: '#002045', borderColor: '#e5e9eb' }}
        aria-label="Switch demo scenario"
      >
        {scenarioOptions.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/* ── Header status badge ── */

function HeaderStatusBadge({ status }: { status: StitchHeaderStatus }) {
  const tones = {
    neutral: { bg: '#e5e9eb', fg: '#43474e' },
    info: { bg: '#e0edff', fg: '#1e4894' },
    success: { bg: '#dcfce7', fg: '#047857' },
    warning: { bg: '#fef3c7', fg: '#92400e' },
  } as const;
  const t = tones[status.tone];
  return (
    <span
      className="text-[11px] px-2 py-0.5 rounded-[3px] shrink-0 font-semibold"
      style={{ fontFamily: "'Inter', sans-serif", backgroundColor: t.bg, color: t.fg }}
    >
      {status.label}
    </span>
  );
}

/* ── Loading skeleton ── */

function LoadingSkeleton() {
  return (
    <div className="h-screen flex" style={{ backgroundColor: '#f7fafc' }}>
      <div className="w-[65%] p-10" style={{ backgroundColor: '#ffffff' }}>
        <div className="max-w-3xl mx-auto space-y-6 animate-pulse">
          <div className="h-10 w-3/4 rounded-[3px]" style={{ backgroundColor: '#e5e9eb' }} />
          <div className="h-4 w-1/3 rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
          <div className="space-y-4 mt-8">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="space-y-2">
                <div className="h-4 w-full rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
                <div className="h-4 w-5/6 rounded-[3px]" style={{ backgroundColor: '#ebeef0' }} />
              </div>
            ))}
          </div>
        </div>
      </div>
      <div className="w-[35%] p-5 space-y-4" style={{ backgroundColor: '#f1f4f6' }}>
        <div className="h-5 w-1/2 rounded-[3px] animate-pulse" style={{ backgroundColor: '#e5e9eb' }} />
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-32 rounded-[4px] animate-pulse" style={{ backgroundColor: '#e5e9eb' }} />
        ))}
      </div>
    </div>
  );
}

/* ── Error state ── */

function ErrorState({ message }: { message: string }) {
  return (
    <div className="h-screen flex items-center justify-center" style={{ backgroundColor: '#f7fafc' }}>
      <div className="text-center max-w-md px-8">
        <div
          className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4"
          style={{ backgroundColor: '#fef2f2' }}
        >
          <span className="text-lg" style={{ color: '#f43f5e' }}>
            !
          </span>
        </div>
        <h2 className="text-lg font-semibold mb-2" style={{ fontFamily: "'Manrope', sans-serif", color: '#181c1e' }}>
          Unable to load review
        </h2>
        <p className="text-sm mb-6" style={{ fontFamily: "'Newsreader', serif", color: '#545f72' }}>
          {message}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="px-4 py-2 rounded-[3px] text-sm font-semibold hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
          style={{
            background: 'linear-gradient(135deg, #002045, #1a365d)',
            color: '#fff',
            fontFamily: "'Inter', sans-serif",
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}

/* ── Main Page ── */

export default function StitchPrototypePage() {
  const params = useParams<{ projectId: string }>();
  const projectId = params?.projectId ?? 'demo-1';
  const scenario = useMemo(() => getScenario(projectId), [projectId]);
  const { document: scenarioDoc, issues: scenarioIssues } = scenario;

  const [activeIssueId, setActiveIssueId] = useState<string | null>(null);
  const [filter, setFilter] = useState<StitchIssue['category'] | 'all'>('all');
  const [isLoading, setIsLoading] = useState(true);
  const [error] = useState<string | null>(null);
  const [issueStatus, setIssueStatus] = useState<Record<string, 'accepted' | 'dismissed'>>(
    () => scenario.initialStatus ?? {},
  );
  const [toast, setToast] = useState<string | null>(null);

  const issuesPanelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 600);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    setIssueStatus(scenario.initialStatus ?? {});
    setActiveIssueId(null);
    setFilter('all');
  }, [scenario]);

  const setStatus = useCallback(
    (id: string, next: 'accepted' | 'dismissed' | null) => {
      setIssueStatus((prev) => {
        const copy = { ...prev };
        if (next === null) delete copy[id];
        else copy[id] = next;
        return copy;
      });
      if (next === 'dismissed') setActiveIssueId((curr) => (curr === id ? null : curr));
      if (next === 'accepted' || next === 'dismissed') {
        const issue = scenarioIssues.find((i) => i.id === id);
        const title = issue?.title ?? 'change';
        setToast(`${next === 'accepted' ? 'Applied' : 'Dismissed'}: ${title}`);
      }
    },
    [scenarioIssues],
  );

  const reanalyze = useCallback(() => {
    setIssueStatus(scenario.initialStatus ?? {});
    setActiveIssueId(null);
    setIsLoading(true);
    setTimeout(() => setIsLoading(false), 600);
  }, [scenario]);

  const visibleIssues = scenarioIssues.filter((i) => issueStatus[i.id] !== 'dismissed');
  const filteredIssues = filter === 'all' ? visibleIssues : visibleIssues.filter((i) => i.category === filter);
  const criticalCount = visibleIssues.filter((i) => i.severity === 'critical').length;
  const warningCount = visibleIssues.filter((i) => i.severity === 'warning').length;
  const suggestionCount = visibleIssues.filter((i) => i.severity === 'suggestion').length;
  const categories = [...new Set(scenarioIssues.map((i) => i.category))];
  const addressedCount = scenarioIssues.filter(
    (i) => i.resolved || issueStatus[i.id] === 'accepted' || issueStatus[i.id] === 'dismissed',
  ).length;
  const totalCount = scenarioIssues.length;
  const addressedPct = totalCount === 0 ? 0 : Math.round((addressedCount / totalCount) * 100);

  const selectIssue = useCallback(
    (issueId: string | null) => {
      setActiveIssueId(issueId);
      if (!issueId) return;
      requestAnimationFrame(() => {
        document.getElementById(`issue-card-${issueId}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      });
      const issue = scenarioIssues.find((i) => i.id === issueId);
      if (issue) {
        requestAnimationFrame(() => {
          document.getElementById(`para-${issue.paragraph}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
      }
    },
    [scenarioIssues],
  );

  if (error) return <ErrorState message={error} />;
  if (isLoading) return <LoadingSkeleton />;

  return (
    <div className="min-h-screen md:h-screen flex flex-col md:overflow-hidden" style={{ backgroundColor: '#f7fafc' }}>
      {toast && <AcceptedToast text={toast} onDone={() => setToast(null)} />}
      <style>{`@keyframes fadeInUp { from { opacity: 0; transform: translate(-50%, 12px); } to { opacity: 1; transform: translate(-50%, 0); } }`}</style>
      {/* ── Top Bar ── */}
      <header
        className="flex items-center justify-between px-4 md:px-6 shrink-0 gap-2"
        style={{
          height: '52px',
          backgroundColor: '#ffffff',
          borderBottom: '1px solid rgba(196, 198, 207, 0.15)',
        }}
      >
        <div className="flex items-center gap-3 min-w-0 mr-4">
          <h1
            className="font-bold text-[15px] tracking-tight truncate"
            style={{ fontFamily: "'Manrope', sans-serif", color: '#002045' }}
            title={scenarioDoc.title}
          >
            {scenarioDoc.title}
          </h1>
          <HeaderStatusBadge status={scenario.headerStatus} />
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <ScenarioPicker current={scenario.id} />
          <button
            disabled
            title="Not wired in prototype"
            className="hidden sm:inline-flex text-[13px] font-semibold px-2.5 py-1 rounded-[3px] cursor-not-allowed"
            style={{ fontFamily: "'Inter', sans-serif", color: '#002045', opacity: 0.35 }}
          >
            Share
          </button>
          <button
            disabled
            title="Not wired in prototype"
            className="hidden sm:inline-flex text-[13px] font-semibold px-2.5 py-1 rounded-[3px] cursor-not-allowed"
            style={{ fontFamily: "'Inter', sans-serif", color: '#002045', opacity: 0.35 }}
          >
            Export
          </button>
          <button
            onClick={reanalyze}
            className="px-3 py-1.5 rounded-[3px] text-[11px] font-bold tracking-wide hover:opacity-90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
            style={{
              background: 'linear-gradient(135deg, #002045, #1a365d)',
              color: '#fff',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            Re-analyze
          </button>
        </div>
      </header>

      {/* ── Two-Column Layout ── */}
      <div className="flex flex-col md:flex-row md:flex-1 md:min-h-0">
        {/* ── Document Panel (65% on desktop, full width stacked on mobile) ── */}
        <section
          className="w-full md:w-[65%] md:overflow-y-auto pl-9 pr-5 py-6 md:pl-12 md:pr-8 md:py-10"
          style={{ backgroundColor: '#ffffff' }}
        >
          <div style={{ maxWidth: '680px', margin: '0 auto' }}>
            {/* Document Header */}
            <div style={{ marginBottom: '2rem' }}>
              <h2
                style={{
                  fontFamily: "'Manrope', sans-serif",
                  color: '#002045',
                  fontSize: '1.75rem',
                  fontWeight: 800,
                  letterSpacing: '-0.02em',
                  lineHeight: 1.2,
                  marginBottom: '0.5rem',
                }}
              >
                {scenarioDoc.title}
              </h2>
              <p
                style={{
                  fontFamily: "'Newsreader', serif",
                  color: '#545f72',
                  fontSize: '0.9375rem',
                  fontStyle: 'italic',
                }}
              >
                {scenarioDoc.authors}
              </p>
              <p
                style={{
                  fontFamily: "'Inter', sans-serif",
                  color: '#43474e',
                  fontSize: '0.8125rem',
                  marginTop: '0.25rem',
                }}
              >
                {scenarioDoc.date}
              </p>
            </div>

            {/* Document Body */}
            <div>
              {scenarioDoc.paragraphs.map((para) => {
                const paragraphIssues = scenarioIssues.filter((i) => i.paragraph === para.id);
                const unresolvedIssues = paragraphIssues.filter(
                  (i) => !i.resolved && issueStatus[i.id] !== 'accepted' && issueStatus[i.id] !== 'dismissed',
                );
                const isHighlighted = activeIssueId ? paragraphIssues.some((i) => i.id === activeIssueId) : false;
                const activeIssue = activeIssueId ? paragraphIssues.find((i) => i.id === activeIssueId) : null;
                const baselineSeverity = maxSeverity(unresolvedIssues);
                const activeSeverityColor = activeIssue ? SEVERITY_COLOR[activeIssue.severity] : null;
                const baselineColor = baselineSeverity ? SEVERITY_COLOR[baselineSeverity] : null;
                const bgTint = isHighlighted
                  ? activeIssue?.severity === 'critical'
                    ? 'rgba(244, 63, 94, 0.07)'
                    : activeIssue?.severity === 'suggestion'
                      ? 'rgba(96, 165, 250, 0.07)'
                      : 'rgba(251, 191, 36, 0.08)'
                  : 'transparent';

                const borderColor = isHighlighted
                  ? (activeSeverityColor ?? 'transparent')
                  : baselineColor
                    ? `${baselineColor}33`
                    : 'transparent';

                return (
                  <div
                    key={para.id}
                    id={`para-${para.id}`}
                    className="relative"
                    style={{
                      backgroundColor: bgTint,
                      padding: isHighlighted ? '0.625rem 0.75rem' : '0.375rem 0.75rem',
                      marginBottom: '0.375rem',
                      borderRadius: '4px',
                      borderLeft: `3px solid ${borderColor}`,
                      transition: 'background-color 200ms, border-color 200ms',
                    }}
                  >
                    {/* Issue dots in margin */}
                    {paragraphIssues.length > 0 && (
                      <div
                        style={{
                          position: 'absolute',
                          left: '-1.75rem',
                          top: '0.5rem',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '4px',
                        }}
                      >
                        {paragraphIssues.map((issue) => (
                          <button
                            key={issue.id}
                            onClick={() => selectIssue(issue.id === activeIssueId ? null : issue.id)}
                            style={{
                              opacity: activeIssueId === issue.id ? 1 : 0.6,
                              transition: 'opacity 150ms, transform 150ms',
                            }}
                            className="hover:opacity-100 hover:scale-125 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                            title={issue.title}
                            aria-label={`${issue.title} — ${severityLabels[issue.severity]}`}
                          >
                            <SeverityDot severity={issue.severity} size="md" />
                          </button>
                        ))}
                      </div>
                    )}

                    <p
                      style={{
                        fontFamily: "'Newsreader', serif",
                        fontSize: '1rem',
                        lineHeight: 1.8,
                        color: '#181c1e',
                        overflowWrap: 'break-word',
                      }}
                    >
                      <HighlightedText
                        text={para.text}
                        highlights={para.highlights}
                        issues={scenarioIssues}
                        activeIssueId={activeIssueId}
                      />
                    </p>
                  </div>
                );
              })}
            </div>

            <div className="mt-16 flex justify-center opacity-20" aria-hidden>
              <div className="w-16 h-1 rounded-full" style={{ backgroundColor: S.primaryContainer }} />
            </div>
          </div>
        </section>

        {/* ── Issues Panel (35% on desktop, full width stacked on mobile) ── */}
        <aside
          className="w-full md:w-[35%] flex flex-col md:overflow-hidden border-t md:border-t-0 border-[#e5e9eb]"
          style={{ backgroundColor: '#f1f4f6' }}
        >
          {/* Panel Header — compact */}
          <div className="shrink-0" style={{ padding: '1rem 1rem 0.75rem' }}>
            {/* Title row */}
            <div className="flex items-center justify-between" style={{ marginBottom: '0.5rem' }}>
              <h3
                style={{
                  fontFamily: "'Manrope', sans-serif",
                  color: '#002045',
                  fontSize: '0.8125rem',
                  fontWeight: 700,
                }}
              >
                Review Findings
              </h3>
              <span
                style={{
                  fontFamily: "'Inter', sans-serif",
                  backgroundColor: '#e5e9eb',
                  color: '#43474e',
                  fontSize: '0.6875rem',
                  padding: '2px 8px',
                  borderRadius: '10px',
                }}
              >
                {filter === 'all'
                  ? `${visibleIssues.length} issue${visibleIssues.length === 1 ? '' : 's'}`
                  : `${filteredIssues.length} of ${visibleIssues.length}`}
              </span>
            </div>

            {/* Severity counts with labels */}
            <div
              className="flex items-center gap-3 flex-wrap"
              style={{ marginBottom: '0.375rem', fontSize: '0.6875rem', fontFamily: "'Inter', sans-serif" }}
            >
              {[
                { sev: 'critical' as const, count: criticalCount },
                { sev: 'warning' as const, count: warningCount },
                { sev: 'suggestion' as const, count: suggestionCount },
              ]
                .filter(({ count }) => count > 0)
                .map(({ sev, count }) => (
                  <span key={sev} className="flex items-center gap-1" role="status">
                    <SeverityDot severity={sev} />
                    <span style={{ color: '#43474e' }}>
                      {count} {count === 1 ? severityLabels[sev].toLowerCase() : severityLabelsPlural[sev]}
                    </span>
                  </span>
                ))}
              {visibleIssues.length === 0 && <span style={{ color: '#6b7280' }}>No active findings</span>}
            </div>

            {/* Progress */}
            <div style={{ marginBottom: '0.5rem' }}>
              <div
                className="flex items-center justify-between"
                style={{
                  fontSize: '0.625rem',
                  fontFamily: "'Inter', sans-serif",
                  color: '#545f72',
                  marginBottom: '3px',
                }}
              >
                <span>
                  {addressedCount} of {totalCount} addressed
                </span>
                <span>{addressedPct}%</span>
              </div>
              <div
                style={{
                  height: '3px',
                  borderRadius: '3px',
                  backgroundColor: '#e5e9eb',
                  overflow: 'hidden',
                }}
                role="progressbar"
                aria-valuenow={addressedPct}
                aria-valuemin={0}
                aria-valuemax={100}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${addressedPct}%`,
                    backgroundColor: '#10b981',
                    transition: 'width 250ms',
                  }}
                />
              </div>
            </div>

            {/* Category Filter — compact pills */}
            <div className="flex flex-wrap gap-1" role="group" aria-label="Filter by category">
              <button
                onClick={() => setFilter('all')}
                className="focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#002045]"
                style={{
                  fontFamily: "'Inter', sans-serif",
                  fontSize: '0.625rem',
                  fontWeight: 500,
                  padding: '3px 8px',
                  borderRadius: '3px',
                  backgroundColor: filter === 'all' ? '#002045' : '#e5e9eb',
                  color: filter === 'all' ? '#fff' : '#43474e',
                  transition: 'background-color 150ms',
                  whiteSpace: 'nowrap',
                }}
                aria-pressed={filter === 'all'}
              >
                All
              </button>
              {categories.map((cat) => {
                const count = visibleIssues.filter((i) => i.category === cat).length;
                if (count === 0 && filter !== cat) return null;
                return (
                  <button
                    key={cat}
                    onClick={() => setFilter(cat === filter ? 'all' : cat)}
                    className="focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-[#002045]"
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      fontSize: '0.625rem',
                      fontWeight: 500,
                      padding: '3px 8px',
                      borderRadius: '3px',
                      backgroundColor: filter === cat ? '#002045' : '#e5e9eb',
                      color: filter === cat ? '#fff' : '#43474e',
                      transition: 'background-color 150ms',
                      whiteSpace: 'nowrap',
                    }}
                    aria-pressed={filter === cat}
                  >
                    {categoryLabels[cat]} ({count})
                  </button>
                );
              })}
            </div>
          </div>

          {/* Issue Cards — scrollable on desktop; page-scrolls on mobile */}
          <div
            ref={issuesPanelRef}
            className="md:flex-1 md:overflow-y-auto overflow-x-hidden"
            style={{ padding: '0 1rem 1rem' }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {filteredIssues.length === 0 && (
                <div style={{ padding: '2rem 0', textAlign: 'center' }}>
                  {totalCount === 0 ? (
                    <>
                      <p
                        style={{
                          fontFamily: "'Newsreader', serif",
                          color: '#047857',
                          fontSize: '0.875rem',
                          fontWeight: 600,
                        }}
                      >
                        ✓ No issues found in this review
                      </p>
                      <p
                        style={{
                          fontFamily: "'Newsreader', serif",
                          color: '#545f72',
                          fontSize: '0.75rem',
                          fontStyle: 'italic',
                          marginTop: '0.25rem',
                        }}
                      >
                        The document passed all enabled checks.
                      </p>
                    </>
                  ) : visibleIssues.length === 0 ? (
                    <>
                      <p
                        style={{
                          fontFamily: "'Newsreader', serif",
                          color: '#047857',
                          fontSize: '0.875rem',
                          fontWeight: 600,
                        }}
                      >
                        ✓ All {totalCount} findings addressed
                      </p>
                      <button
                        onClick={reanalyze}
                        style={{
                          fontFamily: "'Inter', sans-serif",
                          color: '#002045',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          marginTop: '0.5rem',
                        }}
                        className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                      >
                        Reset
                      </button>
                    </>
                  ) : (
                    <>
                      <p style={{ fontFamily: "'Newsreader', serif", color: '#545f72', fontSize: '0.875rem' }}>
                        No issues match the selected filter.
                      </p>
                      <button
                        onClick={() => setFilter('all')}
                        style={{
                          fontFamily: "'Inter', sans-serif",
                          color: '#002045',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          marginTop: '0.5rem',
                        }}
                        className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#002045]"
                      >
                        Clear filter
                      </button>
                    </>
                  )}
                </div>
              )}
              {filteredIssues.map((issue) => (
                <IssueCard
                  key={issue.id}
                  issue={issue}
                  isActive={activeIssueId === issue.id}
                  status={issueStatus[issue.id] === 'accepted' ? 'accepted' : undefined}
                  onClick={() => selectIssue(issue.id === activeIssueId ? null : issue.id)}
                  onAccept={() => setStatus(issue.id, 'accepted')}
                  onDismiss={() => setStatus(issue.id, 'dismissed')}
                  onUndo={() => setStatus(issue.id, null)}
                />
              ))}
            </div>
          </div>

          {/* AI footer — minimal */}
          <div className="shrink-0" style={{ padding: '0.5rem 1rem 1rem' }}>
            <div
              style={{
                backgroundColor: '#1a365d',
                borderRadius: '3px',
                padding: '0.5rem 0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span
                style={{ color: '#d6e3ff', fontSize: '0.625rem', fontFamily: "'Inter', sans-serif", fontWeight: 600 }}
              >
                AI Review Engine
              </span>
              <span style={{ color: '#adc7f7', fontSize: '0.625rem', fontFamily: "'Inter', sans-serif" }}>
                · {visibleIssues.length} of {scenarioIssues.length} findings
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}
