#!/bin/bash

PATH="$PATH:$HOME/.local/bin"

declare -i polybar_id=0  # polybar process id

process_stop() {
    # @param grep_arg - pgrep arg to match process
    declare grep_arg="$1"
    # @param process_name - name of process to stop
    declare process_name="$2"
    declare -i i=0  # number of attempts to stop process

    while pgrep "${grep_arg}" "$process_name" 1>/dev/null; do
        pkill "$process_name" --signal TERM 1>/dev/null
        sleep 5e-2
        [ "$((i++))" -gt 10 ] && return 1
    done
    return 0
}

echo -n "Restarting polybar..."
if process_stop -x "polybar"; then
    polybar -q -c "$HOME/.config/polybar/config.ini" main -r &
    polybar_id="$!"
    echo "DONE"
else
    echo -e "\n\t$0: failed to restart polybar"
fi

# polybar-winlist is a symbolic link from $PATH that points to
#   ./scripts/window-list.sh
echo -n "Restarting window-list module..."
if process_stop -f "polybar-winlist"; then
    polybar-winlist --start "$polybar_id" &
    echo "DONE"
else
    echo -e "\n\t$0: failed to restart window-list module"
fi
