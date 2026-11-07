import { ToolHandler, McpClient } from "../types.js";

export const naukriGetApplicationStats: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_get_application_stats", {
    date_from: args.date_from,
    date_to: args.date_to
  });

  return result.content[0]?.text ?? "No result returned";
};
