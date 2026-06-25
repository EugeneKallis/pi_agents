/**
 * One-time setup: install any npm packages, verify structure
 *
 * Run: bun run setup
 */

import { execSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { dirname } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

console.log("🔧 Pi Multi-Agent Setup\n");

const agents = ["coder", "qa-engineer"];

for (const agent of agents) {
  const agentDir = resolve(ROOT, "agents", agent);
  const settingsPath = resolve(agentDir, ".pi", "settings.json");

  console.log(`\n--- ${agent} ---`);

  if (!existsSync(agentDir)) {
    console.log(`  ❌ Missing: ${agentDir}`);
    continue;
  }

  const settings = existsSync(settingsPath)
    ? JSON.parse(readFileSync(settingsPath, "utf-8"))
    : {};
  const packages = settings.packages ?? [];
  if (packages.length > 0) {
    console.log(`  Installing packages: ${packages.join(", ")}`);
    for (const pkg of packages) {
      execSync(`pi install ${pkg}`, { cwd: agentDir, stdio: "inherit" });
    }
  }

  console.log(`  ✅ Ready`);
}

console.log("\n✅ Setup complete!");
console.log("\nQuick start:");
console.log("  bun run start   — launch all agents");
console.log("Or run individually:");
console.log("  PI_CODING_AGENT_DIR=$(pwd)/agents/coder/.pi pi");
console.log("  PI_CODING_AGENT_DIR=$(pwd)/agents/qa-engineer/.pi pi");
