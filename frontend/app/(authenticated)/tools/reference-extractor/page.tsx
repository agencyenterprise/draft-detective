import { ReferenceExtractorTool } from './components/reference-extractor-tool';

export default function ReferenceExtractorPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Reference Extractor</h1>
        <p className="mt-2 text-sm text-gray-600">
          Extract bibliographic references from academic documents using AI-powered section detection and windowed
          extraction. Upload a document to automatically identify and extract all bibliography entries.
        </p>
      </div>

      <ReferenceExtractorTool />
    </div>
  );
}
