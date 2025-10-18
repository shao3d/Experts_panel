#!/bin/bash

# Claude Code VSCode Status Monitor (No-Flicker Version)
# Uses the existing statusline-script.sh from CC_sessions
# Updates in place without screen clearing

PROJECT_DIR="/Users/andreysazonov/Documents/Projects/Experts_panel"
STATUSLINE_SCRIPT="$HOME/.claude/statusline-script.sh"
SESSION_START=$(date +%s)  # Track session start time for token estimation

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
RESET='\033[0m'
BOLD='\033[1m'
DIM='\033[2m'

# Function to generate JSON for CCstatusline
generate_claude_json() {
    # Generate JSON with token usage data for CCstatusline
    # Estimate tokens based on session time and activity
    session_start=${SESSION_START:-$(date +%s)}
    current_time=$(date +%s)
    session_duration=$((current_time - session_start))

    # Rough token estimation (grows over time)
    estimated_tokens=$((session_duration * 50 + 20000))  # ~50 tokens/sec + base

    cat <<EOF
{
    "model": {"display_name": "Opus 4.1"},
    "workspace": {
        "current_dir": "$PROJECT_DIR",
        "project_dir": "$PROJECT_DIR"
    },
    "usage": {
        "input_tokens": $estimated_tokens,
        "output_tokens": $((estimated_tokens / 10)),
        "total_tokens": $((estimated_tokens + estimated_tokens / 10)),
        "cache_read_tokens": $((estimated_tokens / 5))
    }
}
EOF
}

# Move cursor to specific position
move_cursor() {
    printf "\033[%d;%dH" "$1" "$2"
}

# Clear from cursor to end of line
clear_to_eol() {
    printf "\033[K"
}

# Initialize the static layout once
init_display() {
    clear
    echo -e "${CYAN}╔════════════════════════════════════════════════════════╗${RESET}"
    echo -e "${CYAN}║${RESET}  ${BOLD}${WHITE}🤖 CLAUDE CODE STATUS MONITOR${RESET}  ${CYAN}║${RESET}"
    echo -e "${CYAN}║${RESET}     ${WHITE}Powered by CC_sessions statusline${RESET}     ${CYAN}║${RESET}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════╝${RESET}"
    echo ""
    echo -e "${WHITE}Mode:${RESET}"
    echo -e "${WHITE}Model:${RESET}"
    echo -e "${WHITE}Task:${RESET}"
    echo -e "${WHITE}Branch:${RESET}"
    echo -e "${WHITE}Git:${RESET}"
    echo ""
    echo -e "${CYAN}────────────────────────────────────────────────────────${RESET}"
    echo -e "${WHITE}Updated:${RESET}"
    echo -e "${DIM}Press Ctrl+C to exit${RESET}"
}

# Update only the changing values
update_display() {
    local status_line="$1"

    # Remove ANSI codes from original statusline output
    clean_status=$(echo "$status_line" | sed 's/\x1b\[[0-9;]*m//g')

    # Parse the status line (format: MODE | Model | Project:Task* | User | Host)
    IFS='|' read -ra PARTS <<< "$clean_status"

    if [ ${#PARTS[@]} -ge 5 ]; then
        mode=$(echo "${PARTS[0]}" | xargs)
        model=$(echo "${PARTS[1]}" | xargs)
        project_task=$(echo "${PARTS[2]}" | xargs)

        # Extract task and project from combined field
        project_name=$(echo "$project_task" | cut -d':' -f1)
        task_name=$(echo "$project_task" | cut -d':' -f2 | sed 's/\*$//')
        has_changes=""
        if [[ "$project_task" == *"*" ]]; then
            has_changes="*"
        fi

        # Get current branch
        cd "$PROJECT_DIR" 2>/dev/null
        branch=$(git branch --show-current 2>/dev/null || echo "none")
        modified_files=$(git status --porcelain 2>/dev/null | wc -l | xargs)

        # Color the mode based on value
        case "$mode" in
            "PLAN")
                mode_display="${GREEN}${BOLD}$mode${RESET} - Planning Mode    "
                ;;
            "IMPL")
                mode_display="${BLUE}${BOLD}$mode${RESET} - Implementation    "
                ;;
            "DEV")
                mode_display="${YELLOW}${BOLD}$mode${RESET} - Development      "
                ;;
            *)
                mode_display="${WHITE}${BOLD}$mode${RESET}                   "
                ;;
        esac

        # Update Mode (line 6, column 11)
        move_cursor 6 11
        clear_to_eol
        echo -en "$mode_display"

        # Update Model (line 7, column 11)
        move_cursor 7 11
        clear_to_eol
        echo -en "${PURPLE}$model${RESET}"

        # Update Task (line 8, column 11)
        move_cursor 8 11
        clear_to_eol
        echo -en "${CYAN}$task_name${RESET}${RED}$has_changes${RESET}"

        # Update Branch (line 9, column 11)
        move_cursor 9 11
        clear_to_eol
        echo -en "${YELLOW}$branch${RESET}"

        # Update Git status (line 10, column 11)
        move_cursor 10 11
        clear_to_eol
        if [ "$modified_files" -gt 0 ]; then
            echo -en "${RED}$modified_files files changed${RESET}"
        else
            echo -en "${GREEN}Working tree clean${RESET}"
        fi

        # Update timestamp (line 13, column 11)
        move_cursor 13 11
        clear_to_eol
        echo -en "$(date '+%H:%M:%S') ${DIM}(updates every 5s)${RESET}"
    fi

    # Move cursor to bottom for clean look
    move_cursor 15 1
}

# Main loop
main() {
    # Check if statusline script exists
    if [ ! -f "$STATUSLINE_SCRIPT" ]; then
        echo -e "${RED}Error: statusline-script.sh not found at $STATUSLINE_SCRIPT${RESET}"
        echo "Please ensure CC_sessions is properly installed."
        exit 1
    fi

    # Initialize display once
    init_display

    # Main update loop
    while true; do
        # Generate JSON and get status from CCstatusline
        json_input=$(generate_claude_json)
        status_output=$(echo "$json_input" | npx ccstatusline@latest 2>/dev/null)

        if [ -n "$status_output" ]; then
            update_display "$status_output"
        fi

        # Wait 5 seconds before next update
        sleep 5
    done
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${GREEN}Status monitor stopped.${RESET}"; exit 0' INT

# Hide cursor for cleaner display
tput civis

# Show cursor on exit
trap 'tput cnorm; echo -e "\n${GREEN}Status monitor stopped.${RESET}"; exit 0' INT EXIT

# Run the monitor
main