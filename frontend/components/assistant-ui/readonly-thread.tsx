import { MarkdownText } from '@/components/assistant-ui/markdown-text';
import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';
import type { ReasoningMessagePartProps } from '@assistant-ui/react';
import { ErrorPrimitive, MessagePrimitive, ThreadPrimitive } from '@assistant-ui/react';
import { ArrowDownIcon, BrainIcon, ChevronDownIcon } from 'lucide-react';
import type { FC } from 'react';

/**
 * A readonly version of the Thread component that displays messages
 * without any interactive features (no composer, no edit, no reload).
 * Useful for displaying conversation history from external sources.
 */
export const ReadonlyThread: FC = () => {
  return (
    <ThreadPrimitive.Root
      className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
      style={{
        ['--thread-max-width' as string]: '44rem',
      }}
    >
      <ThreadPrimitive.Viewport
        turnAnchor="top"
        className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll scroll-smooth px-4 pt-4"
      >
        <ThreadPrimitive.Messages
          components={{
            SystemMessage: ReadonlySystemMessage,
            UserMessage: ReadonlyUserMessage,
            AssistantMessage: ReadonlyAssistantMessage,
          }}
        />

        <ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer sticky bottom-0 mx-auto mt-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible rounded-t-3xl pb-4 md:pb-6">
          <ThreadScrollToBottom />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

const ThreadScrollToBottom: FC = () => {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton
        tooltip="Scroll to bottom"
        variant="outline"
        className="aui-thread-scroll-to-bottom absolute -top-12 z-10 self-center rounded-full p-4 disabled:invisible dark:bg-background dark:hover:bg-accent"
      >
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  );
};

const MessageError: FC = () => {
  return (
    <MessagePrimitive.Error>
      <ErrorPrimitive.Root className="aui-message-error-root mt-2 rounded-md border border-destructive bg-destructive/10 p-3 text-destructive text-sm dark:bg-destructive/5 dark:text-red-200">
        <ErrorPrimitive.Message className="aui-message-error-message line-clamp-2" />
      </ErrorPrimitive.Root>
    </MessagePrimitive.Error>
  );
};

const ReasoningText: FC<ReasoningMessagePartProps> = ({ text }) => {
  if (!text) return null;

  return (
    <Collapsible className="w-full rounded-lg border py-3">
      <CollapsibleTrigger className="group/trigger flex w-full items-center gap-2 px-4 text-sm transition-colors">
        <BrainIcon className="size-4 shrink-0 text-muted-foreground" />
        <span className="grow text-left leading-none">Reasoning</span>
        <ChevronDownIcon
          className={cn(
            'size-4 shrink-0 transition-transform duration-200 ease-out',
            'group-data-[state=closed]/trigger:-rotate-90',
            'group-data-[state=open]/trigger:rotate-0',
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent
        className={cn(
          'overflow-hidden text-sm',
          'data-[state=closed]:animate-collapsible-up',
          'data-[state=open]:animate-collapsible-down',
          'data-[state=closed]:fill-mode-forwards',
          'data-[state=closed]:pointer-events-none',
          'data-[state=open]:duration-200',
          'data-[state=closed]:duration-200',
        )}
      >
        <div className="mt-3 border-t px-4 pt-2">
          <pre className="whitespace-pre-wrap text-muted-foreground">{text}</pre>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

const ReadonlySystemMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="aui-system-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
      data-role="system"
    >
      <div className="wrap-break-word rounded-lg border border-dashed bg-muted/40 px-4 py-3 text-sm leading-relaxed">
        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
      </div>
    </MessagePrimitive.Root>
  );
};

const ReadonlyAssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="aui-assistant-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
      data-role="assistant"
    >
      <div className="aui-assistant-message-content wrap-break-word px-2 text-foreground leading-relaxed">
        <MessagePrimitive.Parts
          components={{
            Text: MarkdownText,
            Reasoning: ReasoningText,
            tools: { Fallback: ToolFallback },
          }}
        />
        <MessageError />
      </div>
    </MessagePrimitive.Root>
  );
};

const ReadonlyUserMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto grid w-full max-w-(--thread-max-width) animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 py-3 duration-150 [&:where(>*)]:col-start-2"
      data-role="user"
    >
      <div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
        <div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground">
          <MessagePrimitive.Parts />
        </div>
      </div>
    </MessagePrimitive.Root>
  );
};
