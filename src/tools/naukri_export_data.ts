import { ToolHandler, McpClient } from "../types.js";

export const naukriExportData: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_export_data", {
    format: args.format,
    output_dir: args.output_dir,
    data_types: args.data_types
  });

  return result.content[0]?.text ?? "No result returned";
};
