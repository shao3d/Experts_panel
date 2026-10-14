import { execFile } from "node:child_process"
import path from "node:path"
import { promisify } from "node:util"
import { Plugin } from "@opencode/plugin"

const execFileAsync = promisify(execFile)

const SCOUT_AGENT = "expert-scout"

interface ScoutArgs {
  command: "experts" | "videos" | "search" | "lesson_search" | "digest" | "show"
  query?: string
  experts?: string
  group?: string
  recent_days?: number
  limit?: number
  diversity?: boolean
  freshness?: "tool" | "craft" | "any"
  no_vector?: boolean
  json?: boolean
  source_keys?: string[]
  video_id?: string
  cursor?: number
  content_offset?: number
  max_chars?: number
  window?: number
  page?: number
  expand?: number
  comments_limit?: number
}

// Registers the read-only `scout` tool for the Expert Scout contour (OpenCode 2
// plugin API). The helper is spawned with an argv array (no shell), so quotes
// and $() / backtick substitutions inside arguments stay inert — corpus
// content cannot pivot into command execution. Bash is denied for the agent,
// so this tool is its only way to touch the corpus.
export default Plugin.define({
  id: "expert-scout-tools",
  async setup(ctx) {
    // OpenCode 2 tool executors no longer receive the session directory, so
    // capture the project location once at plugin load.
    const directory = ctx.location.directory
    await ctx.tool.transform((editor) => {
      editor.add({
        name: "scout",
        description:
          "Read-only corpus: experts and VideoHub; private owner lessons via lesson_search; show source text with explicit continuation. Owner lessons are separate from expert claims.",
        // Code Mode wraps calls in a generic `execute` part, which hides the
        // scout inputs from the integrity checker. Call the tool directly.
        options: { codemode: false },
        input: {
          type: "object",
          properties: {
            command: {
              type: "string",
              enum: ["experts", "videos", "search", "lesson_search", "digest", "show"],
              description:
                "experts = roster; videos = VideoHub catalog; search = expert hybrid search; lesson_search = owner lesson text search; digest = previews; show = full source",
            },
            query: {
              type: "string",
              description: "Search query; required for search and lesson_search",
            },
            experts: {
              type: "string",
              description: "Comma-separated expert_id subset for search",
            },
            group: {
              type: "string",
              description:
                "Canonical group name for search (tech, tech_business, visual); mutually exclusive with experts and resolved from the backend group map",
            },
            recent_days: {
              type: "integer",
              exclusiveMinimum: 0,
              description: "Only posts newer than N days",
            },
            limit: {
              type: "integer",
              minimum: 1,
              maximum: 40,
              description: "Max search results (default 20, max 40)",
            },
            diversity: {
              type: "boolean",
              description:
                "search: opt-in per-expert cap in the top window (avoids single-author monoculture)",
            },
            freshness: {
              type: "string",
              enum: ["tool", "craft", "any"],
              description:
                "search: age-penalty profile; tool = default soft decay (fast-moving tooling), craft/any = no age penalty (durable craft knowledge)",
            },
            no_vector: {
              type: "boolean",
              description: "FTS5 only: skip the vector search and its embedding API call",
            },
            json: {
              type: "boolean",
              description: "Machine-readable JSON output",
            },
            source_keys: {
              type: "array",
              items: { type: "string" },
              maxItems: 3,
              description: "show: 1-3 source_key values like expert:123; split larger lists into batches",
            },
            video_id: {
              type: "string",
              description: "videos/digest: exact YouTube id; digest requires experts=video_hub",
            },
            cursor: {
              type: "integer",
              minimum: 0,
              description:
                "search/videos/digest: next_cursor from previous result; search requires the same query and scope",
            },
            content_offset: {
              type: "integer",
              minimum: 0,
              description: "show: next_content_offset from previous result; default 0",
            },
            max_chars: {
              type: "integer",
              minimum: 1,
              maximum: 8000,
              description: "show: source text characters per key, default/max 8000",
            },
            window: {
              type: "integer",
              minimum: 1,
              maximum: 30,
              description: "digest: posts per page (default 15, max 30)",
            },
            page: {
              type: "integer",
              minimum: 0,
              description: "digest: 0-based page number",
            },
            expand: {
              type: "integer",
              minimum: 1,
              maximum: 5,
              description: "show: also fetch up to N adjacent posts per source (same expert, +/- in time)",
            },
            comments_limit: {
              type: "integer",
              minimum: 0,
              maximum: 100,
              description:
                "Max comments per window per source for show: author and community windows are capped separately (default 20 each)",
            },
          },
          required: ["command"],
          additionalProperties: false,
        },
        async execute(rawArgs, context) {
          if (context.agent !== SCOUT_AGENT) {
            throw new Error("scout tool is only available to the expert-scout agent")
          }
          const args = rawArgs as ScoutArgs
          const python = path.join(directory, "backend/.venv/bin/python")
          const helper = path.join(directory, "backend/scripts/expert_scout.py")
          const argv: string[] = [helper, args.command]
          if (args.experts && args.group) throw new Error("experts and group are mutually exclusive")
          if (args.video_id && !["videos", "digest"].includes(args.command))
            throw new Error("video_id is supported by videos and digest")
          if (args.command === "search" || args.command === "lesson_search") {
            if (!args.query || !args.query.trim()) {
              throw new Error("search requires a non-empty query")
            }
            argv.push(args.query)
            if (args.command === "lesson_search") {
              if (args.limit) argv.push("--limit", String(args.limit))
              if (args.cursor !== undefined) argv.push("--cursor", String(args.cursor))
            } else {
              if (args.experts) argv.push("--experts", args.experts)
              if (args.group) argv.push("--group", args.group)
              if (args.recent_days) argv.push("--recent-days", String(args.recent_days))
              if (args.limit) argv.push("--limit", String(args.limit))
              if (args.no_vector) argv.push("--no-vector")
              if (args.diversity) argv.push("--diversity")
              if (args.freshness) argv.push("--freshness", String(args.freshness))
              if (args.cursor !== undefined) argv.push("--cursor", String(args.cursor))
            }
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
              cwd: directory,
              timeout: 120_000,
              maxBuffer: 16 * 1024 * 1024,
            })
            return { content: stdout }
          } catch (err: any) {
            // A failure is never an empty search result. Do not include raw
            // exception output, which may contain infrastructure details.
            return {
              content: JSON.stringify({
                status: "error",
                error: "helper_failed",
                exit_code: err?.code ?? null,
                message:
                  "Scout helper failed; retry or report an operational failure. This does not prove absence of sources.",
              }),
            }
          }
        },
      })
    })
  },
})
