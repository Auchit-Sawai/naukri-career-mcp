import { ToolHandler, McpClient } from "../types.js";

export const naukriSearchJobs: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_search_jobs", {
    keywords: args.keywords,
    location: args.location,
    experience_min: args.experience_min,
    experience_max: args.experience_max,
    salary_min: args.salary_min,
    job_types: args.job_types,
    companies: args.companies,
    posted_within_days: args.posted_within_days,
    limit: args.limit
  });

  return result.content[0]?.text ?? "No result returned";
};
