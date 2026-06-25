/**
 * REPO-LEVEL SHARED EXTENSION: File Guard
 *
 * Blocks dangerous write operations. Shared by all agents in this repo.
 * Can read per-agent config from agent.yaml for allowed paths.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { isToolCallEventType } from "@earendil-works/pi-coding-agent";

const BLOCKED_PATTERNS = [".env", "id_rsa", "credentials", "*.pem"];

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event) => {
    if (isToolCallEventType("write", event)) {
      const path = event.input.path;
      for (const pattern of BLOCKED_PATTERNS) {
        if (path.includes(pattern)) {
          return { block: true, reason: `File Guard blocked write to ${path} (matches ${pattern})` };
        }
      }
    }
    if (isToolCallEventType("edit", event)) {
      const path = event.input.path;
      for (const pattern of BLOCKED_PATTERNS) {
        if (path.includes(pattern)) {
          return { block: true, reason: `File Guard blocked edit to ${path} (matches ${pattern})` };
        }
      }
    }
  });
}
