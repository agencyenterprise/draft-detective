'use client';

import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button';
import { Button } from '@/components/ui/button';
import { ThreadListItemPrimitive, ThreadListPrimitive } from '@assistant-ui/react';
import { ArchiveIcon, PlusIcon, Trash2Icon } from 'lucide-react';
import type { FC } from 'react';

export const ThreadList: FC = () => {
  return (
    <div className="aui-thread-list flex h-full flex-col gap-1.5 overflow-y-auto">
      <ThreadListNew />
      <ThreadListItems />
    </div>
  );
};

const ThreadListNew: FC = () => {
  return (
    <ThreadListPrimitive.New asChild>
      <Button
        variant="ghost"
        className="aui-thread-list-new flex items-center justify-start gap-2 rounded-lg px-2.5 py-2 text-sm font-medium"
      >
        <PlusIcon className="size-4" />
        New chat
      </Button>
    </ThreadListPrimitive.New>
  );
};

const ThreadListItems: FC = () => {
  return <ThreadListPrimitive.Items>{() => <ThreadListItem />}</ThreadListPrimitive.Items>;
};

const ThreadListItem: FC = () => {
  return (
    <ThreadListItemPrimitive.Root className="aui-thread-list-item group flex items-center gap-1 rounded-lg transition-colors hover:bg-muted data-[active]:bg-muted">
      <ThreadListItemPrimitive.Trigger className="aui-thread-list-item-trigger min-w-0 flex-1 truncate px-2.5 py-2 text-left text-sm">
        <ThreadListItemPrimitive.Title fallback="New chat" />
      </ThreadListItemPrimitive.Trigger>
      {/* Hidden rather than transparent, so the title gets the full width until the row is hovered (or reached by keyboard). */}
      <div className="aui-thread-list-item-actions hidden shrink-0 items-center pr-1 group-hover:flex group-focus-within:flex">
        <ThreadListItemPrimitive.Archive asChild>
          <TooltipIconButton tooltip="Archive" variant="ghost" className="size-7 p-0 text-muted-foreground">
            <ArchiveIcon className="size-4" />
          </TooltipIconButton>
        </ThreadListItemPrimitive.Archive>
        <ThreadListItemPrimitive.Delete asChild>
          <TooltipIconButton
            tooltip="Delete"
            variant="ghost"
            className="size-7 p-0 text-muted-foreground hover:text-destructive"
          >
            <Trash2Icon className="size-4" />
          </TooltipIconButton>
        </ThreadListItemPrimitive.Delete>
      </div>
    </ThreadListItemPrimitive.Root>
  );
};
