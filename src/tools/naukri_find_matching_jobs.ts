import { ToolHandler, McpClient } from "../types.js";

export const naukriFindMatchingJobs: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_find_matching_jobs", {
    resume_path: args.resume_path,
    keywords: args.keywords,
    location: args.location,
    min_match_score: args.min_match_score,
    limit: args.limit
  });

  return result.content[0]?.text ?? "No result returned";
};
