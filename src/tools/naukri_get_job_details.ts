import { ToolHandler, McpClient } from "../types.js";

export const naukriGetJobDetails: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_get_job_details", {
    job_url: args.job_url
  });

  return result.content[0]?.text ?? "No result returned";
};
