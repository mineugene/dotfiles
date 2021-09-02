#!/bin/bash

declare -r FG_DIM_COLOR="#8389a3"
declare -r BG_FOCUS_COLOR="#33374c"
declare -r FG_FOCUS_COLOR="#e8e9ec"

main() {
    if [ "$#" -eq 0 ]; then listen_events; fi

    declare polybar_cache
    declare -i polybar_pid

    polybar_pid="$(pgrep -x polybar)"
    polybar_cache="$(set_cache_path)/window-list.$polybar_pid" || exit "$?"
    while [ "$#" -gt 0 ]; do
        case "$1" in
        -t|--tail)
            tail "$polybar_cache"
            shift;;
        -*)
            echo "Unknown argument: \"$1\""
            exit 1;;
        *)
            echo "What are thoooose~"
            break;;
        esac
    done
}

set_foreground_color() {
    declare -r label="$1"
    declare -r color="$2"
    printf "%%{F%s}%s%%{F-}" "$color" "$label"
}

set_background_color() {
    declare -r label="$1"
    declare -r color="$2"
    printf "%%{B%s}%s%%{B-}" "$color" "$label"
}

set_cache_path() {
    declare -r polybar_cache="$HOME/.cache/polybar"

    mkdir "$polybar_cache" &>/dev/null
    if [ -d "$polybar_cache" ]; then
        echo "$polybar_cache"
        return 0
    else
        printf "ERROR: %s(): failed to open %s" "${FUNCNAME[0]}" "$polybar_cache"
        return 1
    fi
}

get_node_id_list() {
    declare -l desktop_active   # active desktop in focused monitor
    declare -la node_win_id     # node id of nodes containing windows

    desktop_active="$(bspc query -D -d focused.active)"
    readarray -t node_win_id <<< \
        "$(bspc query -N -n .window -d "$desktop_active")"
    echo "${node_win_id[@]}"
}

get_node_list() {
    declare -a node_win_id         # node id of nodes containing windows

    read -ra node_win_id <<<"$(get_node_id_list)"
    for id in "${node_win_id[@]}"; do
        # format with single-space delimiter
        wmctrl -pxl | grep "$id" | tr -s "[:blank:]"
    done
}

get_wminfo_property() {
    # (1)window id (2)desktop id (3)pid (4)class name (5)hostname (6)long name
    # @param wminfo - line from wmctrl output
    declare wminfo="$1"
    # @param column - see column id representations above
    declare column="$2"

    echo "$wminfo" | cut -d " " -f"$column"
}

get_formatted_window_name() {
    # @param wminfo - line from wmctrl output
    declare wminfo="$1"
    # length at which window name is clamped
    declare -ir label_size=20
    declare -l node_focused     # focused node
    declare name                # window or class name

    node_focused="$(bspc query -N -n focused)"
    name="$(get_wminfo_property "$wminfo" 6-)"
    if [ "${#name}" -gt "$label_size" ]; then
        # name length exceeds label size
        name="${name::((label_size-2))}.."
    else
        # left justify; pad right
        name=$(printf "%-${label_size}s" "$name")
    fi
    # set polybar formatting
    if [ "$(get_wminfo_property "$wminfo" 1)" == "$node_focused" ]; then
        # highlight focused window label
        name="$(set_background_color " $name " "$BG_FOCUS_COLOR")"
        name="$(set_foreground_color "$name" "$FG_FOCUS_COLOR")"
    else
        # dim local unfocused window label
        name="$(set_foreground_color " $name " "$FG_DIM_COLOR")"
    fi
    echo "$name"
}

get_formatted_window_list() {
    # @param node_list - full output of wmctrl
    declare -a node_list=()
    declare shortname       # formatted window name
    # declare -i i=0          # number of rows in wmctrl

    readarray -t node_list <<<"$1"
    for wminfo in "${node_list[@]}"; do
        if [ -z "$wminfo" ]; then echo && continue; fi
        shortname="$(get_formatted_window_name "$wminfo")"
        # # separator
        # if [ $((i++)) -ne 0 ]; then echo -n " "; fi
        echo -n "$shortname"
    done
}

listen_events() {
    declare polybar_cache
    declare -i polybar_pid
    declare -a events

    polybar_pid="$(pgrep -x polybar)"
    polybar_cache="$(set_cache_path)/window-list.$polybar_pid" || exit "$?"
    trap 'rm -f "$polybar_cache"' 0 2 3 15

    events=(
        "desktop_focus"
        "node_focus"
        "node_remove"
    )
    bspc subscribe "${events[@]}" | while
        get_formatted_window_list "$(get_node_list)" >"$polybar_cache"
        echo hook:module/window-list1 >>"/tmp/polybar_mqueue.$polybar_pid"
        read -r _ && [ "$(pgrep -x polybar)" == "$polybar_pid" ]
    do true; done
}

main "$@"
