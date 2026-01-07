import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';

/**
 * Proxy endpoint for authenticated file download requests.
 *
 * This route runs server-side and forwards file download requests to the backend API
 * with proper authentication headers. This allows file downloads without exposing
 * tokens in URLs or client-side code.
 *
 * Architecture:
 * 1. Frontend requests: /api/files/download/{file_id}
 * 2. This route validates session and adds Authorization header
 * 3. Proxies to backend: /api/files/download/{file_id}
 * 4. Backend verifies access and serves file
 * 5. Returns file to frontend with proper headers
 */
export async function GET(request: NextRequest, { params }: { params: Promise<{ file_id: string }> }) {
  try {
    const session = await auth();

    if (!session?.accessToken) {
      return NextResponse.json({ detail: 'Not authenticated' }, { status: 401 });
    }

    const { file_id } = await params;

    if (!file_id) {
      return NextResponse.json({ detail: 'File ID is required' }, { status: 400 });
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const backendUrl = `${apiUrl}/api/files/download/${file_id}`;

    const response = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json({ detail: errorText || 'Failed to fetch file' }, { status: response.status });
    }

    // Preserve backend headers so browsers handle the file correctly (e.g., trigger download vs. display)
    const contentType = response.headers.get('content-type') || 'application/octet-stream';
    const contentDisposition = response.headers.get('content-disposition');

    // Read as ArrayBuffer to prevent Next.js from truncating large files or corrupting binary data
    // Streaming directly can cause issues with text files like markdown that need complete content
    const arrayBuffer = await response.arrayBuffer();

    // Reconstruct headers to ensure browser receives correct metadata for file handling
    // Content-Type is critical for proper rendering/display behavior
    const headers = new Headers();
    headers.set('Content-Type', contentType);
    if (contentDisposition) {
      headers.set('Content-Disposition', contentDisposition);
    }
    // Use actual buffer size to prevent client-side issues with incorrect Content-Length
    headers.set('Content-Length', arrayBuffer.byteLength.toString());
    // Disable caching since files may be updated and we want fresh content on each request
    headers.set('Cache-Control', 'private, no-cache');

    // Return complete buffer to ensure file integrity (no partial transfers)
    return new NextResponse(arrayBuffer, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  } catch (error) {
    console.error('Error proxying file request:', error);
    return NextResponse.json({ detail: 'Internal server error' }, { status: 500 });
  }
}
