#!/bin/bash

PATH="$HOME/.local/bin:$PATH"

declare -i polybar_id=0             # polybar process id

process_stop() {
    # @param process_name - name of process to stop
    declare process_name="$1"
    declare -i i=0              # number of attempts to stop process

    while pgrep -x "$process_name"; do
        pkill "$process_name" --signal TERM &>/dev/null
        sleep 5e-2
        [ "$((i++))" -gt 10 ] && return 1
    done
    return 0
}

if process_stop "polybar"; then
    polybar -q -c "$HOME/.config/polybar/config.ini" main -r &
    polybar_id="$!"
fi

# polybar-winlist is a symbolic link from $PATH that points to
#   ./scripts/window-list.sh
if process_stop "polybar-winlist"; then
    polybar-winlist --start "$polybar_id" &
fi
