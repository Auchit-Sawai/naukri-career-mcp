import { ToolHandler, McpClient } from "../types.js";

export const naukriUpdateSummary: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_update_summary", {
    new_summary: args.new_summary,
    confirm: args.confirm
  });

  return result.content[0]?.text ?? "No result returned";
};
