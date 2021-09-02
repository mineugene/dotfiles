#!/bin/bash

PATH="$HOME/.local/bin:$PATH"

declare polybar_id              # polybar process id
declare polybar_winlist_id      # polybar-winlist process id

process_stop() {
    # @param process_name - name of process to stop
    declare process_name="$1"
    declare process_id          # process id (pid)
    declare -i i=0              # number of attempts to stop process

    while process_id="$(pgrep -x "$process_name")"; do
        pkill "$process_name" --signal TERM &>/dev/null
        sleep 5e-2
        [ "$((i++))" -gt 10 ] && break
    done
    echo "$process_id"
}

polybar_id="$(process_stop "polybar")"
if [ -z "$polybar_id" ]; then
    polybar -q -c "$HOME/.config/polybar/config.ini" main -r &
fi

# polybar-winlist is a symbolic link from $PATH that points to
#     ./scripts/window-list.sh
polybar_winlist_id="$(process_stop "polybar-winlist")"
if [ -z "$polybar_winlist_id" ]; then
    polybar-winlist &
fi

# misc: bar-to-window space gap adjustment
sleep 5e-1; bspc config -m focused top_padding 0
