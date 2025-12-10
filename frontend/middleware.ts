export { auth as default } from '@/auth';

export const config = {
  // Exclude: API routes, static files, and public share pages
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|share/).*)'],
};
