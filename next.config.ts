import type { NextConfig } from "next";

// Patrón del template nextjs-fastapi de Vercel: en desarrollo /api/* va a uvicorn (puerto 8000);
// en producción Vercel enruta /api/* a la función Python api/index.py (ver vercel.json).
const nextConfig: NextConfig = {
  rewrites: async () => [
    {
      source: "/api/:path*",
      destination:
        process.env.NODE_ENV === "development"
          ? "http://127.0.0.1:8000/api/:path*"
          : "/api/index",
    },
  ],
  // /api/optimizar tarda varios segundos: que el proxy de desarrollo no corte antes
  experimental: { proxyTimeout: 120_000 },
};

export default nextConfig;
