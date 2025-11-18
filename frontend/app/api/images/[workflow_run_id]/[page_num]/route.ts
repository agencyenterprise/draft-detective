import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@/auth';

/**
 * Proxy endpoint for authenticated image requests.
 *
 * This route runs server-side and forwards image requests to the backend API
 * with proper authentication headers. This allows <Image> components to load
 * authenticated images without exposing tokens in URLs or client-side code.
 *
 * Architecture:
 * 1. Frontend <Image> requests: /api/images/{workflow_run_id}/{page_num}
 * 2. This route validates session and adds Authorization header
 * 3. Proxies to backend: /api/workflow-runs/{workflow_run_id}/pages/{page_num}
 * 4. Backend serves image file from uploads/docling_images/{file_hash}/page_N.png
 * 5. Returns image to frontend with caching headers
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ workflow_run_id: string; page_num: string }> },
) {
  try {
    const session = await auth();

    if (!session?.accessToken) {
      return NextResponse.json({ detail: 'Not authenticated' }, { status: 401 });
    }

    const { workflow_run_id, page_num } = await params;

    const pageNumber = parseInt(page_num, 10);
    if (isNaN(pageNumber) || pageNumber < 0) {
      return NextResponse.json({ detail: 'Invalid page number' }, { status: 400 });
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const backendUrl = `${apiUrl}/api/workflow-runs/${workflow_run_id}/pages/${pageNumber}`;

    const response = await fetch(backendUrl, {
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
      },
    });

    if (!response.ok) {
      const errorText = await response.text();
      return NextResponse.json({ detail: errorText || 'Failed to fetch image' }, { status: response.status });
    }

    const imageBuffer = await response.arrayBuffer();
    const contentType = response.headers.get('content-type') || 'image/png';

    return new NextResponse(imageBuffer, {
      headers: {
        'Content-Type': contentType,
        'Cache-Control': 'public, max-age=3600',
      },
    });
  } catch (error) {
    console.error('Error proxying image request:', error);
    return NextResponse.json({ detail: 'Internal server error' }, { status: 500 });
  }
}
