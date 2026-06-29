/**
 * Auto-connect the Telegram bridge on session startup.
 *
 * Drops a `/telegram-connect` follow-up user message into the TUI right after
 * session_start. The command is the same one `pi-telegram` registers
 * normally — it silently re-acquires a stale lock (the common case when the
 * service restarts), or prompts for takeover if another live π instance
 * already holds the lock.
 *
 * Triggers ONLY on `reason: "startup"` (cold boot). `/new`, `/resume`,
 * `/fork`, and `/reload` all keep the existing polling alive in the same
 * `pi` instance, so re-running the command would be redundant and could
 * spuriously re-prompt.
 *
 * Disable with `AUTO_TELEGRAM_CONNECT=0` in the agent `.env` or the service
 * environment — useful when iterating on the bot itself.
 */

import { existsSync } from "node:fs";
import { join } from "node:path";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

function telegramConfigPath(cwd: string): string {
	// Mirrors pi-telegram's getAgentDir(): prefer PI_CODING_AGENT_DIR, else
	// ~/.pi/agent. The agent launcher (launch-agent.sh / justfile) sets
	// PI_CODING_AGENT_DIR to <agent>/.pi, which is where telegram.json
	// actually lives for this agent.
	const agentDir = process.env.PI_CODING_AGENT_DIR
		? process.env.PI_CODING_AGENT_DIR
		: join(process.env.HOME ?? "/", ".pi", "agent");
	return join(agentDir, "telegram.json");
}

export default function (pi: ExtensionAPI) {
	pi.on("session_start", async (event, ctx) => {
		// Only act on a cold boot. Other reasons preserve the running
		// session's polling state.
		if (event.reason !== "startup") return;

		// Honour an opt-out for bot development / debugging.
		if (process.env.AUTO_TELEGRAM_CONNECT === "0") return;

		// `/telegram-connect` is a TUI slash command (it can prompt for
		// bot-token setup or takeover confirmation). In RPC/print mode it
		// would either no-op or block on a UI confirm — skip there.
		if (!ctx.hasUI) return;

		// Don't queue the command if the bot isn't configured yet. The
		// user has to run /telegram-setup interactively the first time;
		// auto-running /telegram-connect in that state would just prompt
		// for a token and block the service.
		if (!existsSync(telegramConfigPath(ctx.cwd))) {
			ctx.ui.notify(
				"Auto Telegram-connect skipped: telegram.json not found (run /telegram-setup once).",
				"info",
			);
			return;
		}

		ctx.ui.notify("Auto-connecting Telegram bridge…", "info");
		// `deliverAs: "followUp"` queues the slash command for delivery
		// after the session finishes bootstrapping. pi parses it as a
		// slash command (not a user message) and dispatches to the
		// registered `telegram-connect` handler.
		pi.sendUserMessage("/telegram-connect", { deliverAs: "followUp" });
	});
}
