import { ReferenceDownloaderTool } from './components/reference-downloader-tool';

export default function ReferenceDownloaderPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Reference Downloader</h1>
        <p className="mt-2 text-sm text-gray-600">
          Search the web for each reference and download the related full-text when available (PDF or Markdown).
        </p>
      </div>

      <ReferenceDownloaderTool />
    </div>
  );
}
