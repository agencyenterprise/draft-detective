import type { NextConfig } from 'next';

const apiUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/+$/, '');

const nextConfig: NextConfig = {
  output: 'standalone',
  // MCP clients are often configured with `<origin>/mcp` (no trailing slash). When the
  // frontend and API share an origin, the proxy can send that path here, where the auth
  // middleware would answer with the sign-in page (issue #774). A 307 keeps the method
  // and body, and redirects run before the middleware.
  redirects: async () => [{ source: '/mcp', destination: `${apiUrl}/mcp/`, permanent: false }],
  // Increase body size limit for file uploads (default is 1MB)
  serverActions: {
    bodySizeLimit: '100mb', // Allow up to 100MB for document uploads
  },
  // Enable reliable hot reload when using the webpack dev server (non-Turbopack dev).
  // Ignored when running with Turbopack.
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: 1000,
        aggregateTimeout: 300,
      };
    }
    return config;
  },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: 'ui-avatars.com' },
      { protocol: 'https', hostname: 'lh3.googleusercontent.com' },
    ],
  },
};

export default nextConfig;
