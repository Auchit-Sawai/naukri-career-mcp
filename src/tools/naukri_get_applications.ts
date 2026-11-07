import { ToolHandler, McpClient } from "../types.js";

export const naukriGetApplications: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_get_applications", {
    status: args.status,
    company: args.company,
    date_from: args.date_from,
    date_to: args.date_to,
    limit: args.limit
  });

  return result.content[0]?.text ?? "No result returned";
};
