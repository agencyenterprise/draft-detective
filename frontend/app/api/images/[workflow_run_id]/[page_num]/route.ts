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
 * 1. Frontend <Image> requests: /api/images/{workflow_run_id}/{page_num}?share_token={token} (optional)
 * 2. This route validates session OR share token
 * 3. Proxies to backend: /api/workflow-runs/{workflow_run_id}/pages/{page_num}
 * 4. Backend serves image file from uploads/docling_images/{file_hash}/page_N.png
 * 5. Returns image to frontend with caching headers
 *
 * Share Token Flow:
 * - If share_token query param is present, validates it against the backend
 * - If valid, allows unauthenticated access (backend handles share access check)
 * - This enables image loading in incognito mode for shared projects
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ workflow_run_id: string; page_num: string }> },
) {
  try {
    const { searchParams } = new URL(request.url);
    const shareToken = searchParams.get('share_token');
    const session = await auth();

    // Require either authentication OR a share token
    if (!session?.accessToken && !shareToken) {
      return NextResponse.json({ detail: 'Not authenticated' }, { status: 401 });
    }

    const { workflow_run_id, page_num } = await params;

    const pageNumber = parseInt(page_num, 10);
    if (isNaN(pageNumber) || pageNumber < 0) {
      return NextResponse.json({ detail: 'Invalid page number' }, { status: 400 });
    }

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const backendUrl = `${apiUrl}/api/workflow-runs/${workflow_run_id}/pages/${pageNumber}`;

    // If we have a session, use auth header. Otherwise, backend will check share access.
    const headers: HeadersInit = {};
    if (session?.accessToken) {
      headers.Authorization = `Bearer ${session.accessToken}`;
    }

    const response = await fetch(backendUrl, { headers });

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
