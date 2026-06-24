// =============================================================
// FILE: frontend/next.config.mjs
// PURPOSE: Next.js configuration.
//          Exposes the backend API base URL to all components.
//
// NOTE: Next.js 14 requires .js/.mjs config (TypeScript config files
//       are only supported from Next.js 15+).
// =============================================================

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Expose backend API URL to client-side code via NEXT_PUBLIC_ prefix
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  },
};

export default nextConfig;
