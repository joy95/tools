import os from "node:os";

import { defineConfig } from "vite";
import uniPlugin from "@dcloudio/vite-plugin-uni";

const uni = (uniPlugin as unknown as { default?: typeof uniPlugin }).default ?? uniPlugin;
const API_PORT = 8082;

// 取这台电脑的局域网地址。手机预览访问不了 127.0.0.1。
function lanHost(): string {
  const nets = os.networkInterfaces();
  for (const name of ["en0", "en1"]) {
    const address = firstUsefulAddress(nets[name]);
    if (address) {
      return address;
    }
  }
  for (const entries of Object.values(nets)) {
    const address = firstUsefulAddress(entries);
    if (address) {
      return address;
    }
  }
  return "127.0.0.1";
}

// 从一块网卡里挑本机的 IPv4。
function firstUsefulAddress(entries: os.NetworkInterfaceInfo[] | undefined): string {
  for (const entry of entries ?? []) {
    const family = entry.family as string | number;
    const ipv4 = family === "IPv4" || family === 4;
    if (ipv4 && !entry.internal) {
      return entry.address;
    }
  }
  return "";
}

export default defineConfig(({ mode }) => ({
  plugins: [uni()],
  define: {
    __API_BASE_URL__: JSON.stringify(
      mode === "development" ? `http://${lanHost()}:${API_PORT}` : `http://127.0.0.1:${API_PORT}`,
    ),
  },
}));
