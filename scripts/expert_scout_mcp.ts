/** Stdio MCP adapter for the existing no-shell Scout tool.
 * The schema and execution are reused verbatim from the OpenCode plugin so
 * model comparisons do not introduce a second retrieval implementation.
 */
import readline from "node:readline"
import path from "node:path"
import { fileURLToPath } from "node:url"
import { z } from "../.opencode/node_modules/zod/index.js"
import { ExpertScoutTools } from "../.opencode/plugins/expert-scout-tools.ts"

const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")
const plugin = await ExpertScoutTools({} as any)
const scout = plugin.tool!.scout
const schema = z.object(scout.args).strict()
const inputSchema = z.toJSONSchema(schema)

function reply(id: unknown, result: unknown) {
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, result }) + "\n")
}

async function handle(message: any) {
  if (message.id === undefined) return
  if (message.method === "initialize") {
    reply(message.id, {
      protocolVersion: "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "expert-scout", version: "0.1.0" },
    })
  } else if (message.method === "ping") {
    reply(message.id, {})
  } else if (message.method === "tools/list") {
    reply(message.id, { tools: [{
      name: "scout",
      description: scout.description,
      inputSchema,
      annotations: { readOnlyHint: true, destructiveHint: false, openWorldHint: false },
    }] })
  } else if (message.method === "tools/call") {
    try {
      if (message.params?.name !== "scout") throw new Error("Unknown tool")
      const args = schema.parse(message.params.arguments ?? {})
      const text = await scout.execute(args, {
        agent: "expert-scout", directory, worktree: directory,
        sessionID: "headless-scout", messageID: String(message.id),
        abort: new AbortController().signal,
        metadata() {},
        async ask() { throw new Error("Scout does not request permissions") },
      } as any)
      let isError = false
      try { isError = JSON.parse(text).status === "error" } catch {}
      reply(message.id, { content: [{ type: "text", text }], ...(isError ? { isError: true } : {}) })
    } catch (error: any) {
      reply(message.id, {
        isError: true,
        content: [{ type: "text", text: `scout failed: ${error?.message ?? error}` }],
      })
    }
  } else {
    process.stdout.write(JSON.stringify({
      jsonrpc: "2.0", id: message.id,
      error: { code: -32601, message: "Method not found" },
    }) + "\n")
  }
}

const lines = readline.createInterface({ input: process.stdin })
for await (const line of lines) {
  if (!line.trim()) continue
  try {
    await handle(JSON.parse(line))
  } catch {
    process.stdout.write(JSON.stringify({
      jsonrpc: "2.0", id: null,
      error: { code: -32700, message: "Invalid JSON request" },
    }) + "\n")
  }
}
