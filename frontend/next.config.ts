import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
};

module.exports = {
  experimental: {
    turbo: false, // Désactive Turbopack
  },
};

export default nextConfig;
