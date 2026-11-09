import { ToolHandler, McpClient } from "../types.js";

// Phone-number + OTP login. Only the phone number is passed through the tool;
// the user types the OTP directly in the visible Naukri browser window.
export const naukriLoginWithOtp: ToolHandler = async (args, context) => {
  const mcp = context.mcp?.["naukri-career"] as McpClient;
  if (!mcp) {
    throw new Error("MCP client not available. Ensure the naukri-career MCP server is running.");
  }

  const result = await mcp.callTool("naukri_login_with_otp", {
    phone: args.phone
  });

  return result.content[0]?.text ?? "No result returned";
};
