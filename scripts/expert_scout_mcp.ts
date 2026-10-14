/** Stdio MCP adapter for the existing no-shell Scout tool.
 * The schema and execution are reused verbatim from the OpenCode plugin so
 * model comparisons do not introduce a second retrieval implementation.
 * OpenCode 2 plugin shape: the plugin registers via ctx.tool.transform, the
 * tool input is already JSON Schema, and execute(input, context) returns
 * { content } instead of a bare string.
 */
import readline from "node:readline"
import path from "node:path"
import { fileURLToPath } from "node:url"
import pluginModule from "../.opencode/plugins/expert-scout-tools.ts"

const directory = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")

const registered: any[] = []
const editor = {
  add: (tool: any) => registered.push(tool),
  namespace: () => {},
  update: () => {},
  remove: () => {},
}
const pluginContext = {
  location: { directory },
  tool: {
    transform: async (callback: (editor: any) => void) => {
      callback(editor)
      return { dispose: async () => {} }
    },
  },
}
await (pluginModule as any).setup(pluginContext)
const scout = registered.find((tool) => tool.name === "scout")
if (!scout) throw new Error("scout tool not registered by the plugin")
const inputSchema = scout.input
const commandEnum: string[] = scout.input?.properties?.command?.enum ?? []

function reply(id: unknown, result: unknown) {
  process.stdout.write(JSON.stringify({ jsonrpc: "2.0", id, result }) + "\n")
}

async function handle(message: any) {
  if (message.id === undefined) return
  if (message.method === "initialize") {
    reply(message.id, {
      protocolVersion: "2024-11-05",
      capabilities: { tools: {} },
      serverInfo: { name: "expert-scout", version: "0.2.0" },
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
      const args = message.params.arguments ?? {}
      if (!commandEnum.includes(args?.command)) throw new Error("Unknown scout command")
      const result = await scout.execute(args, { agent: "expert-scout" })
      const text = typeof result === "string" ? result : String(result?.content ?? result)
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
