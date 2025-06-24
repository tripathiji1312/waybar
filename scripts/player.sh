#!/bin/bash

# First, check if a player is running at all.
if ! playerctl status >/dev/null 2>&1; then
  echo "{}"
  exit 0
fi

# Get the raw metadata from playerctl.
# This might sometimes output multiple JSON objects on one line (e.g., "{}{}")
# which is why previous attempts failed.
raw_metadata=$(playerctl metadata --format '{
    "text": "{{ markup_escape(artist) }} - {{ markup_escape(title) }}",
    "tooltip": "{{ playerName }}: {{ markup_escape(artist) }} - {{ markup_escape(title) }}",
    "alt": "{{status}}",
    "class": "{{status}}"
}')

# Check if the output is empty before processing.
if [ -z "$raw_metadata" ]; then
    echo "{}"
    exit 0
fi

# The magic step: Use `jq` to fix the output.
# `jq -sc '.[0]'` does the following:
# -s (slurp): Reads all JSON objects from the input into a single array. `{}{}` becomes `[{}, {}]`
# .[0]: Selects only the first element from that array. `[{}, {}]` becomes `{}`
# -c (compact): Ensures the output is a single, clean line.
# This guarantees we only ever output ONE valid JSON object.
echo "$raw_metadata" | jq -sc '.[0]'