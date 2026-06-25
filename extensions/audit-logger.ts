/**
 * REPO-LEVEL SHARED EXTENSION: Audit Logger
 *
 * Logs all tool calls with timestamps. Active for every agent in this repo.
 * Placed in pi_agents/extensions/ and referenced from each agent's settings.json.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

export default function (pi: ExtensionAPI) {
  pi.on("tool_execution_start", async (event) => {
    const ts = new Date().toISOString();
    console.log(`[AUDIT ${ts}] tool=${event.toolName} args=${JSON.stringify(event.args).slice(0, 200)}`);
  });
}
