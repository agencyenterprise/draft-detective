import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
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
