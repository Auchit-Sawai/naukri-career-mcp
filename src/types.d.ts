// Type definitions for DSH plugin development
// These types mirror the DSH SDK interfaces that will be provided at runtime

export interface ToolHandler {
  (args: Record<string, unknown>, context: ToolContext): Promise<string>;
}

export interface ToolContext {
  mcp?: Record<string, McpClient>;
  [key: string]: unknown;
}

export interface McpClient {
  callTool(name: string, args: Record<string, unknown>): Promise<McpCallResult>;
}

export interface McpCallResult {
  content: Array<McpContent>;
  isError?: boolean;
}

export interface McpContent {
  type: "text" | "image" | "resource";
  text: string;
  data?: string;
  mimeType?: string;
  uri?: string;
}

// Re-export zod for schema validation
export { z } from "zod";
