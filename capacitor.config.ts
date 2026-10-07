import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.cherrybomb.app',
  appName: 'Cherry-Bomb',
  webDir: 'dist',
  server: { androidScheme: 'http' }
};

export default config;
