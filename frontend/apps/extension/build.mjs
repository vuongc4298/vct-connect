import { build } from "esbuild";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const directory = dirname(fileURLToPath(import.meta.url));
const output = resolve(directory, "build");
const publicKey = "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAoUaC/KOFnMHvtio6BDO/2AEQviTOcoZKitGBfufE1mjiovFHr4GWtak7z21SX1WL9HCQHMJBoFDfK6NGqqzYwshiZZpTSHA3tJepiwMd1QT53G6LaveS7173/ibdpRcL/V9vt1HyF8ZBoFNj5pjV3pykRyB2XAWKv6i0X4T/ZLNFaTCv00tUBOBmv60n/idZ2MkNlSk3mkm6DTjWWYuMHLcF1iuwv0i3JMK1mxt905v7ZIEqeAtJ0vDHYfKVvCOp2XZ2oF1khKfn5b1a6gio1VarT+G3Ap8CQkLzKcltY9sLxHe7VqPZmO8aYehcWel0bW/Zzc8JWo18cpjdT1OUcQIDAQAB";

function localPublishableKey(text) {
  const line = text.split(/\r?\n/).find(value => value.startsWith("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY="));
  return line?.slice("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=".length).replace(/^['"]|['"]$/g, "");
}

const localEnv = await readFile(resolve(directory, "../web/.env.local"), "utf8").catch(() => "");
const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY || localPublishableKey(localEnv);
if (!publishableKey || !/^pk_(test|live)_[A-Za-z0-9_-]+$/.test(publishableKey)) {
  throw new Error("Set NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY to build the extension");
}
const encodedHost = publishableKey.split("_").slice(2).join("_");
const clerkHost = Buffer.from(encodedHost, "base64url").toString("utf8").replace(/\$$/, "");
if (!/^[a-z0-9.-]+$/i.test(clerkHost) || !clerkHost.includes(".")) {
  throw new Error("Invalid Clerk publishable key host");
}
const webOrigin = new URL(process.env.VCT_WEB_ORIGIN || "http://127.0.0.1:3000").origin;
if (!/^https?:\/\//.test(webOrigin)) throw new Error("VCT_WEB_ORIGIN must be HTTP(S)");
// Development Clerk cookies live on the web host; production client cookies
// live on the Clerk Frontend API host (Clerk's Sync Host integration).
const syncHost = publishableKey.startsWith("pk_test_") ? webOrigin : `https://${clerkHost}`;
await mkdir(output, { recursive: true });
const manifest = {
  manifest_version: 3,
  name: "VCT Connect Source Evidence",
  version: "0.1.0",
  description: "Capture selected visible 1688 and Taobao evidence on request.",
  key: publicKey,
  permissions: ["activeTab", "scripting", "cookies", "storage"],
  host_permissions: [`${webOrigin}/*`, `https://${clerkHost}/*`],
  action: { default_popup: "popup.html", default_title: "Capture source evidence" },
};
await writeFile(resolve(output, "manifest.json"), JSON.stringify(manifest, null, 2));
await Promise.all(["popup.html", "popup.css"].map(async name =>
  writeFile(resolve(output, name), await readFile(resolve(directory, name)))));
await build({
  absWorkingDir: directory,
  entryPoints: ["src/popup.tsx"],
  bundle: true,
  outfile: "build/popup.js",
  format: "iife",
  platform: "browser",
  target: "chrome120",
  define: {
    VCT_CLERK_PUBLISHABLE_KEY: JSON.stringify(publishableKey),
    VCT_WEB_ORIGIN: JSON.stringify(webOrigin),
    VCT_CLERK_SYNC_HOST: JSON.stringify(syncHost),
  },
});
console.log(`Built extension for ${webOrigin}; load ${output}`);
