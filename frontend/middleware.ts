export { auth as middleware } from '@/auth';

export const config = {
  matcher: ['/((?!stitch|_next/static|_next/image|favicon.ico).*)'],
};
