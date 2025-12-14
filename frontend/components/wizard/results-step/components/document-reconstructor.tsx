import { Markdown } from '@/components/markdown';
import type { ClaimSubstantiatorStateOutput, DocumentChunkOutput, DocumentIssue } from '@/lib/generated-api';
import { getMaxChunkSeverity } from '@/lib/severity';
import { cn } from '@/lib/utils';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useEffect, useMemo, useRef } from 'react';
import rehypeRaw from 'rehype-raw';
import { detectBlockSyntax, extractChunkContent } from '../document-reconstruction-utils';

interface DocumentReconstructorProps {
  results: ClaimSubstantiatorStateOutput;
  issues: DocumentIssue[];
  selectedChunkIndex: number | null;
  onChunkSelect: (chunkIndex: number | null) => void;
}

export function DocumentReconstructor({
  results,
  issues,
  selectedChunkIndex,
  onChunkSelect,
}: DocumentReconstructorProps) {
  const parentRef = useRef<HTMLDivElement>(null);
  const chunks = useMemo(() => results.chunks || [], [results.chunks]);

  // Group chunks by paragraph
  const chunksGroupedByParagraphIndex = useMemo(() => {
    return chunks.reduce(
      (acc, chunk) => {
        acc[chunk.paragraph_index] = acc[chunk.paragraph_index] || [];
        acc[chunk.paragraph_index].push(chunk);
        return acc;
      },
      {} as Record<number, DocumentChunkOutput[]>,
    );
  }, [chunks]);

  // Create ordered array of paragraph entries for virtual list
  const paragraphEntries = useMemo(() => {
    return Object.entries(chunksGroupedByParagraphIndex).sort(([aIndex], [bIndex]) => Number(aIndex) - Number(bIndex));
  }, [chunksGroupedByParagraphIndex]);

  // Calculate overscan based on viewport height for better UX
  // More items will be rendered to fill the viewport + buffer
  const estimatedParagraphHeight = 150;
  const viewportBasedOverscan = useMemo(() => {
    if (typeof window !== 'undefined') {
      const viewportHeight = window.innerHeight;
      // Render enough to fill 2x viewport (1x above + 1x below visible area)
      return Math.ceil(viewportHeight / estimatedParagraphHeight);
    }
    return 10; // Default fallback
  }, []);

  // Create virtualizer for paragraphs
  const rowVirtualizer = useVirtualizer({
    count: paragraphEntries.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => estimatedParagraphHeight,
    overscan: viewportBasedOverscan,
  });

  // Scroll to selected chunk when selection changes
  useEffect(() => {
    if (selectedChunkIndex !== null) {
      // Find which paragraph contains the selected chunk
      const chunk = chunks.find((c) => c.chunk_index === selectedChunkIndex);
      if (chunk) {
        const paragraphRowIndex = paragraphEntries.findIndex(([pIndex]) => Number(pIndex) === chunk.paragraph_index);
        if (paragraphRowIndex !== -1) {
          rowVirtualizer.scrollToIndex(paragraphRowIndex, {
            align: 'center',
            behavior: 'smooth',
          });
        }
      }
    }
  }, [selectedChunkIndex, chunks, paragraphEntries, rowVirtualizer]);

  return (
    <div ref={parentRef} className="h-full overflow-y-auto">
      <div
        style={{
          height: `${rowVirtualizer.getTotalSize()}px`,
          width: '100%',
          position: 'relative',
          paddingTop: '1rem',
          paddingBottom: '4rem',
        }}
      >
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const [, paragraphChunks] = paragraphEntries[virtualRow.index];

          return (
            <div
              key={virtualRow.key}
              data-index={virtualRow.index}
              ref={rowVirtualizer.measureElement}
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                width: '100%',
                transform: `translateY(${virtualRow.start}px)`,
              }}
            >
              <div className="pb-2">
                <DocumentReconstructorChunkGroup
                  chunks={paragraphChunks}
                  issues={issues}
                  selectedChunkIndex={selectedChunkIndex}
                  onChunkSelect={onChunkSelect}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function DocumentReconstructorChunkGroup({
  chunks,
  issues,
  selectedChunkIndex,
  onChunkSelect,
}: {
  chunks: DocumentChunkOutput[];
  issues: DocumentIssue[];
  selectedChunkIndex: number | null;
  onChunkSelect: (chunkIndex: number | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const combinedContent = useMemo(() => {
    if (chunks.length === 0) {
      return null;
    }

    // Detect block-level syntax from the first chunk
    const firstChunk = chunks[0];
    const blockPrefix = detectBlockSyntax(firstChunk.content);

    // Extract content from all chunks and wrap in spans
    const wrappedChunks = chunks
      .map((chunk) => {
        const content = extractChunkContent(chunk.content, blockPrefix);
        const severity = getMaxChunkSeverity(issues, chunk);
        return `<span data-chunk-index="${chunk.chunk_index}" data-severity="${severity}">${content}</span>`;
      })
      .join(' ');

    // Reconstruct markdown with block-level syntax from first chunk
    return blockPrefix ? `${blockPrefix}${wrappedChunks}` : wrappedChunks;
  }, [chunks, issues]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }
    const targets = containerRef.current.querySelectorAll('[data-chunk-index]');
    targets.forEach((target: Element) => {
      if (selectedChunkIndex !== null) {
        target.setAttribute(
          'data-chunk-selected',
          selectedChunkIndex === parseInt(target.getAttribute('data-chunk-index') || '0') ? 'true' : 'false',
        );
      } else {
        target.removeAttribute('data-chunk-selected');
      }
    });
  }, [selectedChunkIndex]);

  useEffect(() => {
    if (!containerRef.current) {
      return;
    }

    const handleClick = (event: Event) => {
      const target = event.currentTarget as HTMLElement;
      const chunkIndex = target.getAttribute('data-chunk-index');
      if (chunkIndex && onChunkSelect) {
        onChunkSelect(parseInt(chunkIndex));
      }
    };

    const targets = containerRef.current.querySelectorAll('[data-chunk-index]');
    targets.forEach((target: Element) => {
      target.addEventListener('click', handleClick);
    });
    return () => {
      targets.forEach((target: Element) => {
        target.removeEventListener('click', handleClick);
      });
    };
  }, [combinedContent, onChunkSelect]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "[&_[data-severity='high']]:bg-red-100",
        "[&_[data-severity='medium']]:bg-yellow-100",
        "[&_[data-severity='low']]:bg-blue-100",
        '[&_[data-severity]]:hover:bg-gray-300/50 [&_[data-severity]]:cursor-pointer',
        '[&_[data-chunk-selected="true"]]:shadow-lg',
        '[&_[data-chunk-selected="false"]]:opacity-50',
      )}
    >
      <Markdown rehypePlugins={[[rehypeRaw, { tagfilter: true }]]}>{combinedContent}</Markdown>
    </div>
  );
}
