import { ToolHandler, McpClient } from "../types.js";

export const naukriParseResume: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_parse_resume", {
    resume_path: args.resume_path
  });

  return result.content[0]?.text ?? "No result returned";
};
