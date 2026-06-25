/**
 * Coder-specific tools: code review, project scanning
 */
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

export default function (pi: ExtensionAPI) {
  pi.registerTool({
    name: "scan_project_structure",
    label: "Scan Project",
    description: "Quickly scan the top-level structure of a project directory",
    parameters: Type.Object({
      path: Type.String({ description: "Path to the project root" }),
      depth: Type.Optional(Type.Number({ description: "Max depth (default: 2)" })),
    }),
    async execute(_id, params, _signal, _onUpdate, _ctx) {
      // Implementation would scan the directory
      return {
        content: [{ type: "text", text: `Scanned ${params.path} at depth ${params.depth ?? 2}` }],
        details: {},
      };
    },
  });
}
