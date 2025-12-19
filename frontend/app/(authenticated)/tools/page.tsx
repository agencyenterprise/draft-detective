import { Button } from '@/components/ui/button';
import { FileDownIcon, FileSearchIcon } from 'lucide-react';
import Link from 'next/link';

export default function ToolsPage() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Tools</h1>
        <p className="mt-2 text-sm text-gray-600">
          Standalone tools that can be used without creating a project or submitting a full document. These tools
          perform specific analysis tasks independently.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <Link href="/tools/reference-extractor">
          <div className="group relative overflow-hidden rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-indigo-50 p-2">
                    <FileSearchIcon className="h-5 w-5 text-indigo-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">Reference Extractor</h3>
                </div>
                <p className="mt-2 text-sm text-gray-600">
                  Extract bibliographic references using AI-powered section detection. Handles multiple reference
                  sections.
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Button variant="outline" size="sm" className="w-full">
                Open Tool
              </Button>
            </div>
          </div>
        </Link>

        <Link href="/tools/reference-downloader">
          <div className="group relative overflow-hidden rounded-lg border border-gray-200 bg-white p-6 shadow-sm transition-shadow hover:shadow-md">
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-indigo-50 p-2">
                    <FileDownIcon className="h-5 w-5 text-indigo-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900">Reference Downloader</h3>
                </div>
                <p className="mt-2 text-sm text-gray-600">
                  Fetch and download sources for references. Enter references to check their validity and accessibility
                  online.
                </p>
              </div>
            </div>
            <div className="mt-4">
              <Button variant="outline" size="sm" className="w-full">
                Open Tool
              </Button>
            </div>
          </div>
        </Link>
      </div>
    </div>
  );
}
