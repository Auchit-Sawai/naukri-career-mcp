import { ToolHandler, McpClient } from "../types.js";

export const naukriUpdateApplicationStatus: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_update_application_status", {
    application_id: args.application_id,
    status: args.status,
    interview_round: args.interview_round,
    interview_date: args.interview_date,
    interview_type: args.interview_type,
    recruiter_name: args.recruiter_name,
    recruiter_contact: args.recruiter_contact,
    notes: args.notes
  });

  return result.content[0]?.text ?? "No result returned";
};
