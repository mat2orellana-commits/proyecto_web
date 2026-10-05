import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';
/// <reference types="node" />

import fs from 'fs';
import path from 'path';
import process from 'process';
import { Buffer } from 'buffer';
import { createHash } from 'crypto';

// Plugin to handle base64 images in HTML
function base64ImagesPlugin() {
  return {
    name: 'base64-images',
    transformIndexHtml(html: string): string {
      // Replace base64 data URLs with placeholder comments
      // The actual images will be copied to dist/assets and referenced
      const base64Regex = /<img\s+src="data:image\/([^;]+);base64,([^"]+)"([^>]*)>/g;
      
      return html.replace(base64Regex, (match, mimeType, base64Data, rest) => {
        // Generate a unique filename based on the base64 content hash
        const hash = createHash('md5').update(base64Data).digest('hex').substring(0, 8);
        const ext = mimeType.split('/')[1] || 'png';
        const filename = `base64-img-${hash}.${ext}`;
        
        // Save the base64 image to public/base64-images/
        const publicDir = path.join(process.cwd(), 'public', 'base64-images');
        if (!fs.existsSync(publicDir)) {
          fs.mkdirSync(publicDir, { recursive: true });
        }
        
        const buffer = Buffer.from(base64Data, 'base64');
        fs.writeFileSync(path.join(publicDir, filename), buffer);
        
        // Return img tag with reference to the saved file
        return `<img src="base64-images/${filename}"${rest}>`;
      });
    }
  };
}

export default defineConfig({
  base: './',
  root: '.',
  publicDir: 'public',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: true,
    rollupOptions: {
      input: {
        main: 'index.html',
      },
    },
  },
  server: {
    port: 5173,
    open: true,
  },
  plugins: [
    base64ImagesPlugin(),
    VitePWA({
      registerType: 'autoUpdate',
      cleanupOutdatedCaches: true,
      includeAssets: ['icon.svg', 'favicon-32.png', 'apple-touch-icon.png', 'robots.txt'],
      manifest: {
        name: 'Cherry-Bomb - Plataforma Educativa',
        short_name: 'Cherry-Bomb',
        description: 'Plataforma educativa institucional',
        theme_color: '#250a26',
        background_color: '#12030f',
        display: 'standalone',
        start_url: './',
        scope: './',
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any maskable' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2,woff,ttf,otf}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'gstatic-fonts-cache',
              expiration: { maxEntries: 10, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
});