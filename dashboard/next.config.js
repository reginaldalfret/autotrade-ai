/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  async rewrites() {
    const backendUrl = process.env.INTERNAL_BACKEND_URL || 'http://127.0.0.1:8008';
    return [
      {
        source: '/runtime/:path*',
        destination: `${backendUrl}/runtime/:path*`,
      },
      {
        source: '/activity/:path*',
        destination: `${backendUrl}/activity/:path*`,
      },
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
      {
        source: '/models',
        destination: `${backendUrl}/models`,
      },
      {
        source: '/portfolio',
        destination: `${backendUrl}/portfolio`,
      },
      {
        source: '/positions',
        destination: `${backendUrl}/positions`,
      },
      {
        source: '/trades',
        destination: `${backendUrl}/trades`,
      },
      {
        source: '/risk',
        destination: `${backendUrl}/risk`,
      },
      {
        source: '/analytics',
        destination: `${backendUrl}/analytics`,
      },
      {
        source: '/audit/:path*',
        destination: `${backendUrl}/audit/:path*`,
      },
      {
        source: '/reports/:path*',
        destination: `${backendUrl}/reports/:path*`,
      },
      {
        source: '/learning/:path*',
        destination: `${backendUrl}/learning/:path*`,
      },
      {
        source: '/session/:path*',
        destination: `${backendUrl}/session/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
