import { readFile, mkdir, writeFile } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createZip } from "./zip.mjs";

const directory = dirname(fileURLToPath(import.meta.url));
const origin = new URL(process.env.VCT_EXTENSION_WEB_ORIGIN || "https://vct-connect-dev-web.blackdesert-0144dda1.southeastasia.azurecontainerapps.io");
if (origin.protocol !== "https:" || origin.username || origin.password || /^(localhost|127\.|\[::1\])/.test(origin.hostname)) {
  throw new Error("The downloadable extension requires a deployed HTTPS web origin");
}
const output = resolve(directory, "../web/private/extension");
const build = spawnSync(process.execPath, [resolve(directory, "build.mjs")], {
  env: { ...process.env, VCT_WEB_ORIGIN: origin.origin, VCT_EXTENSION_OUTPUT: output }, stdio: "inherit",
});
if (build.error) throw build.error;
if (build.status !== 0) process.exit(build.status ?? 1);
const files = await Promise.all(["manifest.json", "popup.html", "popup.css", "icon.png", "popup.js", "background.js"].map(async name => ({ name, data: await readFile(resolve(output, name)) })));
await mkdir(resolve(directory, "../web/private"), { recursive: true });
await writeFile(resolve(directory, "../web/private/vct-connect-extension.zip"), createZip(files));
console.log("Packaged private extension download from source.");
