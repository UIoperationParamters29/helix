/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
  // Proxy /api and /ws to the Python backend in dev
  async rewrites() {
    const backend = process.env.HELIX_BACKEND || 'http://localhost:8765';
    return [
      { source: '/api/:path*', destination: `${backend}/api/:path*` },
      { source: '/ws/:path*', destination: `${backend}/ws/:path*` },
    ];
  },
};
module.exports = nextConfig;
