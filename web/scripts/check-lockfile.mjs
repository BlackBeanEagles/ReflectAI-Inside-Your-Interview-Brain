// Fail fast when package-lock.json references a package it does not contain.
//
// This has now broken CI twice, identically and for the same reason. npm
// drops optional dependencies it does not need on the platform that
// writes the lock, so a lockfile generated on Windows can omit the
// top-level @emnapi/core and @emnapi/runtime entries that
// @img/sharp-wasm32 and @tailwindcss/oxide-wasm32-wasi require. Install
// works on the machine that wrote it and fails everywhere else with
// "npm ci can only install packages when your package.json and
// package-lock.json are in sync -- Missing: X from lock file".
//
// It is genuinely hard to catch by hand: nothing local reproduces it,
// npm ci passes, the app builds, and the failure only appears on another
// platform. Worse, GitHub gates Actions logs behind a sign-in on this
// repo, so the remote failure arrives with no readable message at all.
//
// Regenerating the lockfile from scratch fixes it; this exists so the
// need to do that is discovered here, in a second, rather than after a
// push. Pure Node, no dependencies, so it can run before npm ci.

import { readFileSync } from "node:fs";

const lock = JSON.parse(readFileSync(new URL("../package-lock.json", import.meta.url), "utf8"));
const packages = lock.packages ?? {};
const paths = new Set(Object.keys(packages));

// npm resolves a dependency by walking up the node_modules chain: from
// node_modules/a/b it tries node_modules/a/b/node_modules/<dep>, then
// node_modules/a/node_modules/<dep>, then node_modules/<dep>.
function resolves(fromPath, dep) {
  let prefix = fromPath;
  for (;;) {
    const candidate = prefix ? `${prefix}/node_modules/${dep}` : `node_modules/${dep}`;
    if (paths.has(candidate)) return true;
    if (!prefix) return false;
    const idx = prefix.lastIndexOf("/node_modules/");
    prefix = idx === -1 ? "" : prefix.slice(0, idx);
  }
}

const missing = new Map();
for (const [path, meta] of Object.entries(packages)) {
  for (const field of ["dependencies", "optionalDependencies"]) {
    for (const dep of Object.keys(meta?.[field] ?? {})) {
      if (!resolves(path, dep) && !missing.has(dep)) {
        missing.set(dep, `${path || "<root>"} (${field})`);
      }
    }
  }
}

if (missing.size > 0) {
  console.error("package-lock.json references packages it does not contain:\n");
  for (const [dep, needer] of missing) {
    console.error(`  ${dep}  — required by ${needer}`);
  }
  console.error(
    "\nnpm ci will fail on any platform that needs these, even though it" +
      "\nsucceeds here. Fix it by regenerating the lockfile completely:" +
      "\n\n  rm -rf node_modules package-lock.json && npm install" +
      "\n\nDeleting node_modules matters -- npm reuses the existing tree" +
      "\notherwise and writes the same incomplete lockfile back out.\n",
  );
  process.exit(1);
}

console.log(`package-lock.json is complete (${paths.size} entries).`);
