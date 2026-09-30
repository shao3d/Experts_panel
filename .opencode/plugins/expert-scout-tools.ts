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
          "Read-only corpus: experts roster; videos catalog; search hybrid FTS5+vector; digest paged source previews (not full reading); show source text with explicit continuation and comments. Video keyframes are navigation points, not segment boundaries.",
        args: {
          command: tool.schema
            .enum(["experts", "videos", "search", "digest", "show"])
            .describe(
              "experts = roster; videos = VideoHub catalog; search = hybrid search; digest = previews with next_cursor; show = source text with next_content_offset",
            ),
          query: tool.schema
            .string()
            .optional()
            .describe("Search query; required when command=search"),
          experts: tool.schema
            .string()
            .optional()
            .describe("Comma-separated expert_id subset for search"),
          group: tool.schema
            .string()
            .optional()
            .describe(
              "Canonical group name for search (tech, tech_business, visual); mutually exclusive with experts and resolved from the backend group map",
            ),
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
            .max(40)
            .optional()
            .describe("Max search results (default 20, max 40)"),
          diversity: tool.schema
            .boolean()
            .optional()
            .describe("search: opt-in per-expert cap in the top window (avoids single-author monoculture)"),
          freshness: tool.schema
            .enum(["tool", "craft", "any"])
            .optional()
            .describe(
              "search: age-penalty profile; tool = default soft decay (fast-moving tooling), craft/any = no age penalty (durable craft knowledge)",
            ),
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
            .max(3)
            .optional()
            .describe("show: 1-3 source_key values like expert:123; split larger lists into batches"),
          video_id: tool.schema.string().optional().describe("videos/digest: exact YouTube id; digest requires experts=video_hub"),
          cursor: tool.schema.number().int().min(0).optional().describe("search/videos/digest: next_cursor from previous result; search requires the same query and scope"),
          content_offset: tool.schema.number().int().min(0).optional().describe("show: next_content_offset from previous result; default 0"),
          max_chars: tool.schema.number().int().positive().max(8000).optional().describe("show: source text characters per key, default/max 8000"),
          window: tool.schema
            .number()
            .int()
            .positive()
            .max(30)
            .optional()
            .describe("digest: posts per page (default 15, max 30)"),
          page: tool.schema
            .number()
            .int()
            .min(0)
            .optional()
            .describe("digest: 0-based page number"),
          expand: tool.schema
            .number()
            .int()
            .positive()
            .max(5)
            .optional()
            .describe("show: also fetch up to N adjacent posts per source (same expert, +/- in time)"),
          comments_limit: tool.schema
            .number()
            .int()
            .min(0)
            .max(100)
            .optional()
            .describe(
              "Max comments per window per source for show: author and community windows are capped separately (default 20 each)",
            ),
        },
        async execute(args, context) {
          if (context.agent !== SCOUT_AGENT) {
            throw new Error("scout tool is only available to the expert-scout agent")
          }
          const python = path.join(context.directory, "backend/.venv/bin/python")
          const helper = path.join(context.directory, "backend/scripts/expert_scout.py")
          const argv: string[] = [helper, args.command]
          if (args.experts && args.group) throw new Error("experts and group are mutually exclusive")
          if (args.video_id && !["videos", "digest"].includes(args.command)) throw new Error("video_id is supported by videos and digest")
          if (args.command === "search") {
            if (!args.query || !args.query.trim()) {
              throw new Error("command=search requires a non-empty query")
            }
            argv.push(args.query)
            if (args.experts) argv.push("--experts", args.experts)
            if (args.group) argv.push("--group", args.group)
            if (args.recent_days) argv.push("--recent-days", String(args.recent_days))
            if (args.limit) argv.push("--limit", String(args.limit))
            if (args.no_vector) argv.push("--no-vector")
            if (args.diversity) argv.push("--diversity")
            if (args.freshness) argv.push("--freshness", String(args.freshness))
            if (args.cursor !== undefined) argv.push("--cursor", String(args.cursor))
          } else if (args.command === "digest") {
            if (!args.experts && !args.group) {
              throw new Error("command=digest requires --experts or --group scope")
            }
            if (args.experts) argv.push("--experts", args.experts)
            if (args.group) argv.push("--group", args.group)
            if (args.recent_days) argv.push("--recent-days", String(args.recent_days))
            if (args.window) argv.push("--window", String(args.window))
            if (args.page !== undefined) argv.push("--page", String(args.page))
            if (args.cursor !== undefined) argv.push("--cursor", String(args.cursor))
            if (args.video_id) argv.push("--video-id", args.video_id)
          } else if (args.command === "videos") {
            if (args.video_id) argv.push("--video-id", args.video_id)
            if (args.cursor !== undefined) argv.push("--cursor", String(args.cursor))
          } else if (args.command === "show") {
            if (!args.source_keys || args.source_keys.length === 0) {
              throw new Error("command=show requires at least one source_key (expert:123)")
            }
            argv.push(...args.source_keys)
            if (args.comments_limit !== undefined) argv.push("--comments-limit", String(args.comments_limit))
            if (args.expand) argv.push("--expand", String(args.expand))
            if (args.content_offset !== undefined) argv.push("--content-offset", String(args.content_offset))
            if (args.max_chars !== undefined) argv.push("--max-chars", String(args.max_chars))
          }
          if (args.json !== false) argv.push("--json")
          try {
            const { stdout } = await execFileAsync(python, argv, {
              cwd: context.directory,
              timeout: 120_000,
              maxBuffer: 16 * 1024 * 1024,
            })
            return stdout
          } catch (err: any) {
            // A failure is never an empty search result. Do not include raw
            // exception output, which may contain infrastructure details.
            return JSON.stringify({ status: "error", error: "helper_failed",
              exit_code: err?.code ?? null, message: "Scout helper failed; retry or report an operational failure. This does not prove absence of sources." })
          }
        },
      }),
    },
  }
}
