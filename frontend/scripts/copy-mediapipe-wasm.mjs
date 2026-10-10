// Copies the MediaPipe WASM runtime into public/ so the landmarkers load offline (venue Wi-Fi risk).
import { cpSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const src = join(root, "node_modules", "@mediapipe", "tasks-vision", "wasm");
const dest = join(root, "public", "mediapipe-wasm");

if (!existsSync(src)) {
  console.error("copy-mediapipe-wasm: @mediapipe/tasks-vision is not installed; run npm install first.");
  process.exit(1);
}
mkdirSync(dest, { recursive: true });
cpSync(src, dest, { recursive: true });
