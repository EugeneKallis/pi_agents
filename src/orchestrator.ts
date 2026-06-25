/**
 * Pi Multi-Agent Orchestrator
 *
 * Launches each agent as a separate Pi process with its own
 * PI_CODING_AGENT_DIR — isolated config, sessions, extensions.
 *
 * Run: bun run start
 * PM2:  pm2 start src/orchestrator.ts --interpreter bun --name pi-agents
 */

import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn, type ChildProcess } from "node:child_process";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

interface AgentConfig {
  id: string;
  dir: string;
  color: string; // just for display
}

const agents: AgentConfig[] = [
  {
    id: "coder",
    dir: resolve(ROOT, "agents/coder"),
    color: "\x1b[34m", // blue
  },
  {
    id: "qa-engineer",
    dir: resolve(ROOT, "agents/qa-engineer"),
    color: "\x1b[32m", // green
  },
];

const processes: ChildProcess[] = [];

for (const agent of agents) {
  const piAgentDir = resolve(agent.dir, ".pi");
  const reset = "\x1b[0m";

  console.log(`${agent.color}[${agent.id}]${reset} Launching...`);
  console.log(`${agent.color}[${agent.id}]${reset}   Dir: ${agent.dir}`);
  console.log(`${agent.color}[${agent.id}]${reset}   PI_CODING_AGENT_DIR=${piAgentDir}`);

  const proc = spawn("pi", [], {
    cwd: agent.dir,
    env: {
      ...process.env as Record<string, string>,
      PI_CODING_AGENT_DIR: piAgentDir,
    },
    stdio: ["pipe", "inherit", "inherit"],
  });

  proc.on("exit", (code, signal) => {
    console.log(`${agent.color}[${agent.id}]${reset} Exited (code=${code}, signal=${signal})`);
  });

  proc.on("error", (err) => {
    console.error(`${agent.color}[${agent.id}]${reset} Error: ${err.message}`);
  });

  processes.push(proc);
}

process.on("SIGINT", () => {
  console.log("\nShutting down all agents...");
  for (const proc of processes) proc.kill("SIGTERM");
  process.exit(0);
});

process.on("SIGTERM", () => {
  for (const proc of processes) proc.kill("SIGTERM");
  process.exit(0);
});

console.log(`\nLaunched ${agents.length} agents. Ctrl+C to stop all.`);
