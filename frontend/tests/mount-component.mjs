import { transformSync } from "esbuild";
import { readFileSync } from "node:fs";
import Module from "node:module";
import { resolve } from "node:path";

// Compile the real component while replacing only the external identity boundary.
export async function component(entry) {
  const file = resolve(entry);
  const result = transformSync(readFileSync(file, "utf8"), {
    loader: "tsx", format: "cjs", jsx: "automatic",
    define: { VCT_WEB_ORIGIN: JSON.stringify("https://vct.example"), VCT_CLERK_PUBLISHABLE_KEY: JSON.stringify("test"), VCT_CLERK_SYNC_HOST: JSON.stringify("vct.example") },
  });
  const loaded = new Module(file);
  loaded.filename = file;
  loaded.paths = Module._nodeModulePaths(resolve("."));
  const originalRequire = loaded.require.bind(loaded);
  loaded.require = name => /^@clerk\/(nextjs|chrome-extension)$/.test(name) ? {
    useAuth: () => globalThis.__mountedAuth,
    SignInButton: ({ children }) => children,
    SignUpButton: ({ children }) => children,
    ClerkProvider: ({ children }) => children,
    UserButton: () => originalRequire("react").createElement("span", null, "Account"),
  } : originalRequire(name);
  loaded._compile(result.code, file);
  return loaded.exports;
}

export function text(tree) {
  const value = tree.toJSON();
  return JSON.stringify(value);
}

export function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

export function windowState() {
  const timers = new Map();
  let timerId = 0;
  const state = {
    location: { href: "https://vct.example/", search: "" },
    history: { replaceState(_state, _title, path) {
      state.location.href = new URL(path, state.location.href).href;
      state.location.search = new URL(state.location.href).search;
    } },
    setTimeout(callback, delay) { const id = ++timerId; timers.set(id, { callback, delay }); return id; },
    clearTimeout(id) { timers.delete(id); },
  };
  return { state, tick(delay) {
    const found = [...timers].find(([, timer]) => timer.delay === delay);
    if (!found) throw new Error(`No pending timer for ${delay}`);
    timers.delete(found[0]);
    return found[1].callback();
  } };
}
