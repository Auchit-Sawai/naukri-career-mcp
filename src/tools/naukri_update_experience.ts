import { ToolHandler, McpClient } from "../types.js";

export const naukriUpdateExperience: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_update_experience", {
    experience: args.experience,
    confirm: args.confirm
  });

  return result.content[0]?.text ?? "No result returned";
};
