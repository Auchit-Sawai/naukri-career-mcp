import { ToolHandler, McpClient } from "../types.js";

export const naukriGenerateCoverLetter: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_generate_cover_letter", {
    resume_path: args.resume_path,
    job_url: args.job_url,
    job_data: args.job_data,
    output_path: args.output_path,
    tone: args.tone
  });

  return result.content[0]?.text ?? "No result returned";
};
