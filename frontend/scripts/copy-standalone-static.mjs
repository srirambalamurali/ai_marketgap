import { cp, rm, mkdir } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");
const srcStatic = resolve(root, ".next/static");
const dstStatic = resolve(root, ".next/standalone/.next/static");

async function main() {
  await rm(dstStatic, { recursive: true, force: true });
  await mkdir(dirname(dstStatic), { recursive: true });
  await cp(srcStatic, dstStatic, { recursive: true });
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
