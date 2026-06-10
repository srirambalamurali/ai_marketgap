import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");
const standaloneRoot = resolve(root, ".next/standalone");
const srcStatic = resolve(root, ".next/static");
const dstStatic = resolve(standaloneRoot, ".next/static");

async function ensureStaticAssets() {
  await rm(dstStatic, { recursive: true, force: true });
  await mkdir(dirname(dstStatic), { recursive: true });
  await cp(srcStatic, dstStatic, { recursive: true });
}

async function main() {
  await ensureStaticAssets();

  const child = spawn(process.execPath, [resolve(standaloneRoot, "server.js")], {
    cwd: root,
    stdio: "inherit",
    env: process.env,
  });

  child.on("exit", (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }
    process.exit(code ?? 0);
  });

  process.on("SIGINT", () => child.kill("SIGINT"));
  process.on("SIGTERM", () => child.kill("SIGTERM"));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
