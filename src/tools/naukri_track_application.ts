import { ToolHandler, McpClient } from "../types.js";

export const naukriTrackApplication: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_track_application", {
    job_url: args.job_url,
    job_title: args.job_title,
    company: args.company,
    location: args.location,
    applied_date: args.applied_date,
    status: args.status,
    match_score: args.match_score,
    notes: args.notes
  });

  return result.content[0]?.text ?? "No result returned";
};
