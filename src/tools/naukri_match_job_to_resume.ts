import { ToolHandler, McpClient } from "../types.js";

export const naukriMatchJobToResume: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_match_job_to_resume", {
    job_url: args.job_url,
    resume_path: args.resume_path,
    job_data: args.job_data
  });

  return result.content[0]?.text ?? "No result returned";
};
