import { execFile } from "node:child_process"
import path from "node:path"
import { promisify } from "node:util"
import { tool, type Plugin } from "@opencode-ai/plugin"

const execFileAsync = promisify(execFile)

const SCOUT_AGENT = "expert-scout"

// Registers the read-only `scout` tool for the Expert Scout contour. The
// helper is spawned with an argv array (no shell), so quotes and $() /
// backtick substitutions inside arguments stay inert — corpus content cannot
// pivot into command execution. Bash is denied for the agent, so this tool is
// its only way to touch the corpus.
export const ExpertScoutTools: Plugin = async () => {
  return {
    tool: {
      scout: tool({
        description:
          "Read-only access to the Experts Panel Telegram corpus: expert roster (experts), hybrid FTS5+vector post search (search), full source with author/community comments and linked context (show).",
        args: {
          command: tool.schema
            .enum(["experts", "search", "show"])
            .describe(
              "experts = roster and volumes; search = hybrid post search; show = full source lookup",
            ),
          query: tool.schema
            .string()
            .optional()
            .describe("Search query; required when command=search"),
          experts: tool.schema
            .string()
            .optional()
            .describe("Comma-separated expert_id subset for search"),
          recent_days: tool.schema
            .number()
            .int()
            .positive()
            .optional()
            .describe("Only posts newer than N days"),
          limit: tool.schema
            .number()
            .int()
            .positive()
            .max(30)
            .optional()
            .describe("Max search results (default 10, max 30)"),
          no_vector: tool.schema
            .boolean()
            .optional()
            .describe("FTS5 only: skip the vector search and its embedding API call"),
          json: tool.schema
            .boolean()
            .optional()
            .describe("Machine-readable JSON output"),
          source_keys: tool.schema
            .array(tool.schema.string())
            .optional()
            .describe("source_key values like expert:123; required when command=show"),
          comments_limit: tool.schema
            .number()
            .int()
            .positive()
            .max(100)
            .optional()
            .describe("Max comments per source for show (default 20)"),
        },
        async execute(args, context) {
          if (context.agent !== SCOUT_AGENT) {
            throw new Error("scout tool is only available to the expert-scout agent")
          }
          const python = path.join(context.directory, "backend/.venv/bin/python")
          const helper = path.join(context.directory, "backend/scripts/expert_scout.py")
          const argv: string[] = [helper, args.command]
          if (args.command === "search") {
            if (!args.query || !args.query.trim()) {
              throw new Error("command=search requires a non-empty query")
            }
            argv.push(args.query)
            if (args.experts) argv.push("--experts", args.experts)
            if (args.recent_days) argv.push("--recent-days", String(args.recent_days))
            if (args.limit) argv.push("--limit", String(args.limit))
            if (args.no_vector) argv.push("--no-vector")
          } else if (args.command === "show") {
            if (!args.source_keys || args.source_keys.length === 0) {
              throw new Error("command=show requires at least one source_key (expert:123)")
            }
            argv.push(...args.source_keys)
            if (args.comments_limit) argv.push("--comments-limit", String(args.comments_limit))
          }
          if (args.json) argv.push("--json")
          try {
            const { stdout } = await execFileAsync(python, argv, {
              cwd: context.directory,
              timeout: 120_000,
              maxBuffer: 16 * 1024 * 1024,
            })
            return stdout
          } catch (err: any) {
            // Surface helper failures to the model instead of raising, so it
            // can adjust the query; schema mistakes above still throw.
            return [
              `scout failed: ${err?.message ?? err}`,
              err?.stderr ?? "",
              err?.stdout ?? "",
            ]
              .filter(Boolean)
              .join("\n")
          }
        },
      }),
    },
  }
}
