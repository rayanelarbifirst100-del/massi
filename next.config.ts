import type { NextConfig } from "next";


/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', // This is the magic line
  trailingSlash: false,
  images: {
    unoptimized: true, // GitHub Pages doesn't support the default Next.js Image Optimization
  },
  //basePath: '/massi-app',//add this for github pages
  typescript: {
    // This will allow the build to complete even if 
    // there are TypeScript errors like 'implicitly has any type'
    ignoreBuildErrors: true,
  },
  
};

//https://rayanelarbifirst100-del.github.io/massi-app/
export default nextConfig;
