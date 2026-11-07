import { ToolHandler, McpClient } from "../types.js";

export const naukriProposeProfileChanges: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_propose_profile_changes", {
    resume_path: args.resume_path,
    target_roles: args.target_roles,
    target_industries: args.target_industries
  });

  return result.content[0]?.text ?? "No result returned";
};
