/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  trailingSlash: true,
  images: { unoptimized: true },
  reactStrictMode: true,
  // Static export with dynamic [id] segment requires falling through to a
  // single index.html and resolving the id client-side. We rewrite 404 to
  // index so deep links like /a/abc123/ work after a full page load.
  // (Nginx still serves /a/<id>/index.html -> we generate that below.)
};
module.exports = nextConfig;
