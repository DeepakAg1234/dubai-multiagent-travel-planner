import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Vercel Services does not expose Next's `/_next/image` optimizer for this
  // project, so production photos 404 and the UI falls back to sand tiles.
  // Files in `public/images` are already resized; serve them as-is.
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
