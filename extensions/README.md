# Repo-Shared Extensions

Extensions in this directory are loaded by ALL agents in this repo.

They're referenced via relative paths in each agent's `.pi/settings.json`:

```json
{
  "extensions": [
    "../../../extensions/audit-logger.ts",
    "../../../extensions/file-guard.ts"
  ]
}
```

## How it works

Each agent has its own `PI_CODING_AGENT_DIR` pointing to its `.pi/` folder.
Extensions inside `.pi/extensions/` are auto-discovered (agent-specific).
Extensions in `pi_agents/extensions/` are explicitly referenced via settings.json (shared).

## Adding a shared extension

1. Drop a `.ts` file here
2. Add it to each agent's `.pi/settings.json` under `"extensions": [...]`
3. `/reload` in that agent session
