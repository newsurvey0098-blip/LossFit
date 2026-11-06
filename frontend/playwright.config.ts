import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir:'./e2e',
  testMatch:'**/*.pw.ts',
  fullyParallel:true,
  workers:process.platform==='win32'?1:2,
  reporter:'list',
  use:{baseURL:'http://127.0.0.1:4173',browserName:'chromium',channel:process.platform==='win32'?'chrome':undefined,trace:'retain-on-failure'},
  webServer:{command:'npm run dev -- --host 127.0.0.1 --port 4173 --strictPort',url:'http://127.0.0.1:4173',reuseExistingServer:false,timeout:30_000},
});
