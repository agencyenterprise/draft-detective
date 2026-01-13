import { ToolsSidebar } from './components/tools-sidebar';

export default function ToolsLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-[calc(100vh-4rem)] -mx-4 -my-6 sm:-mx-6 lg:-mx-8">
      <ToolsSidebar />
      <div className="flex-1 overflow-y-auto">
        <div className="h-full px-4 py-6 sm:px-6 lg:px-8">{children}</div>
      </div>
    </div>
  );
}
