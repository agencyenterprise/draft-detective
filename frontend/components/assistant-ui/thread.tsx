import {
  ComposerAddAttachment,
  ComposerAttachments,
  UserMessageAttachments,
} from '@/components/assistant-ui/attachment';
import { MarkdownText } from '@/components/assistant-ui/markdown-text';
import { ChatModelSelector } from '@/components/chat/chat-model-selector';
import { ToolFallback } from '@/components/assistant-ui/tool-fallback';
import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useSkillCommands } from '@/lib/skill-commands';
import {
  ActionBarMorePrimitive,
  ActionBarPrimitive,
  AuiIf,
  BranchPickerPrimitive,
  ComposerPrimitive,
  ErrorPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  unstable_useSlashCommandAdapter,
  useAui,
  useAuiState,
  type ReasoningMessagePartComponent,
  type Unstable_SlashCommand,
} from '@assistant-ui/react';
import {
  ArrowDownIcon,
  ArrowUpIcon,
  CheckIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CopyIcon,
  DownloadIcon,
  MoreHorizontalIcon,
  PencilIcon,
  RefreshCwIcon,
  SquareIcon,
} from 'lucide-react';
import { useMemo, type FC, type PropsWithChildren } from 'react';

export const Thread: FC = () => {
  return (
    <ThreadPrimitive.Root
      className="aui-root aui-thread-root @container flex h-full flex-col bg-background"
      style={{
        ['--thread-max-width' as string]: '56rem',
        ['--composer-radius' as string]: '24px',
        ['--composer-padding' as string]: '10px',
      }}
    >
      <ThreadPrimitive.Viewport
        turnAnchor="top"
        className="aui-thread-viewport relative flex flex-1 flex-col overflow-x-auto overflow-y-scroll scroll-smooth px-4 pt-4"
      >
        <AuiIf condition={(s) => s.thread.isEmpty}>
          <ThreadWelcome />
        </AuiIf>

        <ThreadPrimitive.Messages>{() => <ThreadMessage />}</ThreadPrimitive.Messages>

        <ThreadPrimitive.ViewportFooter className="aui-thread-viewport-footer sticky bottom-0 mx-auto mt-auto flex w-full max-w-(--thread-max-width) flex-col gap-4 overflow-visible rounded-t-(--composer-radius) bg-background pb-4 md:pb-6">
          <ThreadScrollToBottom />
          <Composer />
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  );
};

const ThreadMessage: FC = () => {
  const role = useAuiState((s) => s.message.role);
  const isEditing = useAuiState((s) => s.message.composer.isEditing);
  if (isEditing) return <EditComposer />;
  if (role === 'user') return <UserMessage />;
  return <AssistantMessage />;
};

const ThreadScrollToBottom: FC = () => {
  return (
    <ThreadPrimitive.ScrollToBottom asChild>
      <TooltipIconButton
        tooltip="Scroll to bottom"
        variant="outline"
        className="aui-thread-scroll-to-bottom absolute -top-12 z-10 self-center rounded-full p-4 disabled:invisible dark:border-border dark:bg-background dark:hover:bg-accent"
      >
        <ArrowDownIcon />
      </TooltipIconButton>
    </ThreadPrimitive.ScrollToBottom>
  );
};

const ThreadWelcome: FC = () => {
  return (
    <div className="aui-thread-welcome-root mx-auto my-auto flex w-full max-w-(--thread-max-width) grow flex-col">
      <div className="aui-thread-welcome-center flex w-full grow flex-col items-center justify-center">
        <div className="aui-thread-welcome-message flex size-full flex-col justify-center px-4">
          <h1 className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-1 animate-in fill-mode-both font-semibold text-2xl duration-200">
            Draft Detective, on the case.
          </h1>
          <p className="aui-thread-welcome-message-inner fade-in slide-in-from-bottom-1 animate-in fill-mode-both text-muted-foreground text-xl delay-75 duration-200">
            Your peer review assistant. Paste or upload a draft (or just a section), then ask me to check its claims,
            citations, methodology, structure, and more.
          </p>
        </div>
      </div>
      <ThreadSuggestions />
    </div>
  );
};

// Draft Detective starter prompts shown on the empty thread. Clicking one
// pre-fills the composer (send=false) so the user can attach their document
// (or tweak the wording) before sending; skills prompt for an upload if none
// is attached.
const WELCOME_SUGGESTIONS: { label: string; prompt: string; send: boolean }[] = [
  {
    label: 'What checks can you run?',
    prompt: 'What checks can you run on my document?',
    send: false,
  },
  {
    label: 'Validate the document’s references',
    prompt: 'Validate the references in my document against their real published sources.',
    send: false,
  },
  {
    label: 'Peer-review my draft as “Reviewer 2”',
    prompt: 'Act as Reviewer 2 and give a rigorous peer review of my document.',
    send: false,
  },
  {
    label: 'Check my claims against their citations',
    prompt: 'Check whether the claims in my document are supported by their cited sources.',
    send: false,
  },
];

const ThreadSuggestions: FC = () => {
  return (
    <div className="aui-thread-welcome-suggestions grid w-full @md:grid-cols-2 gap-2 pb-4">
      {WELCOME_SUGGESTIONS.map((suggestion) => (
        <ThreadPrimitive.Suggestion key={suggestion.label} prompt={suggestion.prompt} send={suggestion.send} asChild>
          <Button
            variant="ghost"
            className="aui-thread-welcome-suggestion fade-in slide-in-from-bottom-2 animate-in fill-mode-both h-auto w-full flex-wrap items-start justify-start gap-1 rounded-3xl border bg-background px-4 py-3 text-left text-sm transition-colors duration-200 hover:bg-muted"
          >
            <span className="aui-thread-welcome-suggestion-text-1 font-medium">{suggestion.label}</span>
          </Button>
        </ThreadPrimitive.Suggestion>
      ))}
    </div>
  );
};

const Composer: FC = () => {
  const aui = useAui();

  // One slash command per skill. `execute` pre-fills the composer with an
  // explicit instruction so the agent reads and runs that skill (from the
  // skills mounted in its filesystem); the user can then paste the document
  // and send.
  const skillCommands = useSkillCommands();
  const commands = useMemo<Unstable_SlashCommand[]>(
    () =>
      skillCommands.map((command) => ({
        id: command.id,
        description: command.description,
        execute: () => {
          // Replace the composer with an explicit skill instruction. We set it
          // unconditionally (rather than appending to the current text) because
          // the trigger-strip runs in the same tick and reading it back races.
          aui.composer().setText(`Please run the "${command.id}" skill.\n\n`);
        },
      })),
    [aui, skillCommands],
  );

  const slash = unstable_useSlashCommandAdapter({ commands, removeOnExecute: true });

  return (
    <ComposerPrimitive.Unstable_TriggerPopoverRoot>
      <ComposerPrimitive.Root className="aui-composer-root relative flex w-full flex-col">
        <ComposerPrimitive.AttachmentDropzone asChild>
          <div
            data-slot="composer-shell"
            className="flex w-full flex-col gap-2 rounded-(--composer-radius) border bg-background p-(--composer-padding) transition-shadow focus-within:border-ring/75 focus-within:ring-2 focus-within:ring-ring/20 data-[dragging=true]:border-ring data-[dragging=true]:border-dashed data-[dragging=true]:bg-accent/50"
          >
            <ComposerAttachments />
            <ComposerPrimitive.Input
              placeholder="Ask about your draft, or type / for skills"
              className="aui-composer-input max-h-32 min-h-10 w-full resize-none bg-transparent px-1.75 py-1 text-sm outline-none placeholder:text-muted-foreground/80"
              rows={1}
              autoFocus
              aria-label="Message input"
            />
            <ComposerPrimitive.Unstable_TriggerPopover
              char="/"
              adapter={slash.adapter}
              className="absolute bottom-full left-0 z-50 mb-2 max-h-72 w-full overflow-y-auto rounded-xl border bg-popover p-1 text-popover-foreground shadow-md"
            >
              <ComposerPrimitive.Unstable_TriggerPopover.Action {...slash.action} />
              <ComposerPrimitive.Unstable_TriggerPopoverItems>
                {(items) =>
                  items.map((item, index) => (
                    <ComposerPrimitive.Unstable_TriggerPopoverItem key={item.id} item={item} index={index} asChild>
                      <button
                        type="button"
                        className="flex w-full flex-col items-start gap-0.5 rounded-lg px-3 py-2 text-left text-sm outline-none data-[highlighted=true]:bg-accent"
                      >
                        <span className="font-medium">{item.label}</span>
                        {item.description && (
                          <span className="line-clamp-2 text-muted-foreground text-xs">{item.description}</span>
                        )}
                      </button>
                    </ComposerPrimitive.Unstable_TriggerPopoverItem>
                  ))
                }
              </ComposerPrimitive.Unstable_TriggerPopoverItems>
            </ComposerPrimitive.Unstable_TriggerPopover>
            <ComposerAction />
          </div>
        </ComposerPrimitive.AttachmentDropzone>
      </ComposerPrimitive.Root>
    </ComposerPrimitive.Unstable_TriggerPopoverRoot>
  );
};

const ComposerAction: FC = () => {
  return (
    <div className="aui-composer-action-wrapper relative flex items-center justify-between gap-2">
      <div className="flex items-center gap-1">
        <ComposerAddAttachment />
        <ChatModelSelector />
      </div>
      <AuiIf condition={(s) => !s.thread.isRunning}>
        <ComposerPrimitive.Send asChild>
          <TooltipIconButton
            tooltip="Send message"
            side="bottom"
            type="button"
            variant="default"
            size="icon"
            className="aui-composer-send size-8 rounded-full"
            aria-label="Send message"
          >
            <ArrowUpIcon className="aui-composer-send-icon size-4" />
          </TooltipIconButton>
        </ComposerPrimitive.Send>
      </AuiIf>
      <AuiIf condition={(s) => s.thread.isRunning}>
        <ComposerPrimitive.Cancel asChild>
          <Button
            type="button"
            variant="default"
            size="icon"
            className="aui-composer-cancel size-8 rounded-full"
            aria-label="Stop generating"
          >
            <SquareIcon className="aui-composer-cancel-icon size-3 fill-current" />
          </Button>
        </ComposerPrimitive.Cancel>
      </AuiIf>
    </div>
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

// Reasoning summaries emitted by the model, shown inside the chain-of-thought group.
const ReasoningPart: ReasoningMessagePartComponent = ({ text }) => {
  if (!text) return null;
  return <div className="aui-reasoning whitespace-pre-wrap text-muted-foreground text-xs italic">{text}</div>;
};

// Cluster consecutive reasoning + tool-call parts into one "chain of thought"
// group; text parts (the final answer) are left ungrouped.
const CHAIN_OF_THOUGHT_TYPES = new Set(['reasoning', 'tool-call']);
function groupChainOfThought(parts: readonly { type: string }[]) {
  const groups: { groupKey: string | undefined; indices: number[] }[] = [];
  let current: { groupKey: string | undefined; indices: number[] } | null = null;
  parts.forEach((part, index) => {
    if (CHAIN_OF_THOUGHT_TYPES.has(part.type)) {
      if (!current) {
        current = { groupKey: 'chain-of-thought', indices: [] };
        groups.push(current);
      }
      current.indices.push(index);
    } else {
      current = null;
      groups.push({ groupKey: undefined, indices: [index] });
    }
  });
  return groups;
}

const ChainOfThoughtGroup: FC<PropsWithChildren<{ groupKey: string | undefined }>> = ({ groupKey, children }) => {
  if (groupKey !== 'chain-of-thought') return <>{children}</>;
  return (
    <details className="aui-cot group my-2 rounded-lg border bg-muted/30 px-3 py-2">
      <summary className="flex cursor-pointer select-none list-none items-center gap-1 text-muted-foreground text-sm font-medium">
        <ChevronRightIcon className="size-3.5 transition-transform group-open:rotate-90" />
        Chain of thought
      </summary>
      <div className="mt-2 space-y-2 border-l pl-3">{children}</div>
    </details>
  );
};

const AssistantMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="aui-assistant-message-root fade-in slide-in-from-bottom-1 relative mx-auto w-full max-w-(--thread-max-width) animate-in py-3 duration-150"
      data-role="assistant"
    >
      <div className="aui-assistant-message-content wrap-break-word px-2 text-foreground text-sm leading-relaxed">
        <MessagePrimitive.Unstable_PartsGrouped
          groupingFunction={groupChainOfThought}
          components={{
            Text: MarkdownText,
            Reasoning: ReasoningPart,
            tools: { Fallback: ToolFallback },
            Group: ChainOfThoughtGroup,
          }}
        />
        <MessageError />
      </div>

      <div className="aui-assistant-message-footer mt-1 ml-2 flex min-h-6 items-center">
        <BranchPicker />
        <AssistantActionBar />
      </div>
    </MessagePrimitive.Root>
  );
};

const AssistantActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="aui-assistant-action-bar-root col-start-3 row-start-2 -ml-1 flex gap-1 text-muted-foreground"
    >
      <ActionBarPrimitive.Copy asChild>
        <TooltipIconButton tooltip="Copy">
          <AuiIf condition={(s) => s.message.isCopied}>
            <CheckIcon />
          </AuiIf>
          <AuiIf condition={(s) => !s.message.isCopied}>
            <CopyIcon />
          </AuiIf>
        </TooltipIconButton>
      </ActionBarPrimitive.Copy>
      <ActionBarPrimitive.Reload asChild>
        <TooltipIconButton tooltip="Refresh">
          <RefreshCwIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Reload>
      <ActionBarMorePrimitive.Root>
        <ActionBarMorePrimitive.Trigger asChild>
          <TooltipIconButton tooltip="More" className="data-[state=open]:bg-accent">
            <MoreHorizontalIcon />
          </TooltipIconButton>
        </ActionBarMorePrimitive.Trigger>
        <ActionBarMorePrimitive.Content
          side="bottom"
          align="start"
          className="aui-action-bar-more-content z-50 min-w-32 overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
        >
          <ActionBarPrimitive.ExportMarkdown asChild>
            <ActionBarMorePrimitive.Item className="aui-action-bar-more-item flex cursor-pointer select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground">
              <DownloadIcon className="size-4" />
              Export as Markdown
            </ActionBarMorePrimitive.Item>
          </ActionBarPrimitive.ExportMarkdown>
        </ActionBarMorePrimitive.Content>
      </ActionBarMorePrimitive.Root>
    </ActionBarPrimitive.Root>
  );
};

const UserMessage: FC = () => {
  return (
    <MessagePrimitive.Root
      className="aui-user-message-root fade-in slide-in-from-bottom-1 mx-auto grid w-full max-w-(--thread-max-width) animate-in auto-rows-auto grid-cols-[minmax(72px,1fr)_auto] content-start gap-y-2 px-2 py-3 duration-150 [&:where(>*)]:col-start-2"
      data-role="user"
    >
      <UserMessageAttachments />

      <div className="aui-user-message-content-wrapper relative col-start-2 min-w-0">
        <div className="aui-user-message-content wrap-break-word rounded-2xl bg-muted px-4 py-2.5 text-foreground text-sm">
          <MessagePrimitive.Parts />
        </div>
        <div className="aui-user-action-bar-wrapper absolute top-1/2 left-0 -translate-x-full -translate-y-1/2 pr-2">
          <UserActionBar />
        </div>
      </div>

      <BranchPicker className="aui-user-branch-picker col-span-full col-start-1 row-start-3 -mr-1 justify-end" />
    </MessagePrimitive.Root>
  );
};

const UserActionBar: FC = () => {
  return (
    <ActionBarPrimitive.Root
      hideWhenRunning
      autohide="not-last"
      className="aui-user-action-bar-root flex flex-col items-end"
    >
      <ActionBarPrimitive.Edit asChild>
        <TooltipIconButton tooltip="Edit" className="aui-user-action-edit p-4">
          <PencilIcon />
        </TooltipIconButton>
      </ActionBarPrimitive.Edit>
    </ActionBarPrimitive.Root>
  );
};

const EditComposer: FC = () => {
  return (
    <MessagePrimitive.Root className="aui-edit-composer-wrapper mx-auto flex w-full max-w-(--thread-max-width) flex-col px-2 py-3">
      <ComposerPrimitive.Root className="aui-edit-composer-root ml-auto flex w-full max-w-[85%] flex-col rounded-2xl bg-muted">
        <ComposerPrimitive.Input
          className="aui-edit-composer-input min-h-14 w-full resize-none bg-transparent p-4 text-foreground text-sm outline-none"
          autoFocus
        />
        <div className="aui-edit-composer-footer mx-3 mb-3 flex items-center gap-2 self-end">
          <ComposerPrimitive.Cancel asChild>
            <Button variant="ghost" size="sm">
              Cancel
            </Button>
          </ComposerPrimitive.Cancel>
          <ComposerPrimitive.Send asChild>
            <Button size="sm">Update</Button>
          </ComposerPrimitive.Send>
        </div>
      </ComposerPrimitive.Root>
    </MessagePrimitive.Root>
  );
};

const BranchPicker: FC<BranchPickerPrimitive.Root.Props> = ({ className, ...rest }) => {
  return (
    <BranchPickerPrimitive.Root
      hideWhenSingleBranch
      className={cn(
        'aui-branch-picker-root mr-2 -ml-2 inline-flex items-center text-muted-foreground text-xs',
        className,
      )}
      {...rest}
    >
      <BranchPickerPrimitive.Previous asChild>
        <TooltipIconButton tooltip="Previous">
          <ChevronLeftIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Previous>
      <span className="aui-branch-picker-state font-medium">
        <BranchPickerPrimitive.Number /> / <BranchPickerPrimitive.Count />
      </span>
      <BranchPickerPrimitive.Next asChild>
        <TooltipIconButton tooltip="Next">
          <ChevronRightIcon />
        </TooltipIconButton>
      </BranchPickerPrimitive.Next>
    </BranchPickerPrimitive.Root>
  );
};
