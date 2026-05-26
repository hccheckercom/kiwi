#!/bin/bash
# WSL deployment wrapper for Windows
# Usage: bash deploy_wsl.sh <command>

# Convert Windows paths to WSL paths
convert_path() {
    echo "$1" | sed -E 's|C:/|/mnt/c/|g; s|D:/|/mnt/d/|g; s|\\|/|g'
}

# Execute command with path conversion
cmd="$@"
cmd=$(convert_path "$cmd")
eval "$cmd"