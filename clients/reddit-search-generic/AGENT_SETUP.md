# Autonomous setup for a CLI agent

Complete this setup yourself. Do not ask the recipient to run commands or
provide a token. Never print, inspect, summarize, or transmit token contents.

1. From this extracted directory run:

   ```bash
   bash install.sh --non-interactive --verify
   ```

2. Use the installed command by its absolute default path if `~/.local/bin` is
   not yet in the current shell's `PATH`:

   ```bash
   "$HOME/.local/bin/reddit-search" --doctor
   ```

3. Run one live smoke request:

   ```bash
   "$HOME/.local/bin/reddit-search" --json "What are Reddit users saying about CLI coding agents?"
   ```

   `completed` or `abstained` means the integration works. A non-zero exit code
   is a technical failure: diagnose it and retry once without requesting the
   token from the recipient.

4. Read `~/.config/reddit-search/AGENT_INSTRUCTIONS.md` and follow it for this
   and future sessions. If your CLI has a known global instruction file, add a
   short reference to that installed file without copying secrets. If it does
   not, installation is still complete; do not guess or modify unrelated files.

5. Report only: installation path, doctor result, smoke-test status, and whether
   persistent agent routing was added. Do not include credentials or raw debug
   output containing request headers.
