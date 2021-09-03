#!/bin/bash

# [[ constants ]]
# colours
declare -r FG_DIM_COLOR="#8389a3"
declare -r BG_FOCUS_COLOR="#33374c"
declare -r FG_FOCUS_COLOR="#e8e9ec"
# process id
declare -i POLYBAR_ID=0
# output options
declare -i SIG_START=0      # start signal (0)exit (1)normal (2)test
declare POLYBAR_CACHE       # absolute path to formatted window-list cache
declare -ri LABEL_SIZE=20   # max length of window name
declare -r SEPARATOR=""     # separator between window names

print_usage() {
    echo "Usage: $0 [OPTION ...]"
}

print_help() {
    echo "A window module for polybar."
    echo
    echo "Display open windows for a focused desktop. The module updates through"
    echo "  inter-process messaging."
    echo
    echo "Options:"
    echo "  -h, --help          print more infomation"
    echo "  -f, --fetch <pid>   print the last cached window list for the given pid"
    echo "  -s, --start <pid>   listen to bspc events and print window list to polybar;"
    echo "                        breaks out of event loop when polybar pid is killed"
    echo "  -t, --test          listen to bspc events and print window list to stdout"
}

main() {
    if [ "$#" -eq 0 ]; then
        print_usage
        echo "Try '$0 --help' for more information"
    fi

    while [ "$#" -gt 0 ]; do
        case "$1" in
        -h|--help)
            print_usage; print_help
            shift
            ;;
        -f|--fetch)
            if set_pid "$2" && set_cache "$2"; then
                tail "$POLYBAR_CACHE"
            else
                echo "$0: $1: failed to fetch from '$POLYBAR_CACHE'"
            fi
            shift 2
            ;;
        -s|--start)
            if set_pid "$2" && set_cache "$2"; then
                SIG_START=1
            else
                echo "$0: $1: ($2) - invalid process id"
            fi
            shift 2
            ;;
        -t|--test)
            SIG_START=2
            shift
            ;;
        *)
            echo "$0: $1: invaild option"
            break
            ;;
        esac
    done
    if [ "$#" -eq 0 ] && [ "$SIG_START" -gt 0 ]; then
        if [ "$POLYBAR_ID" -eq 0 ] || [ -z "$POLYBAR_CACHE" ]; then
            echo "$0: $POLYBAR_CACHE: (test) cache was not created"
        fi
        listen_events  # start event loop
    fi
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

set_cache() {
    # @param pid - polybar process id
    declare -r pid="$1"
    declare -r polybar_cache_dir="$HOME/.cache/polybar"

    mkdir "$polybar_cache_dir" &>/dev/null
    if [ -d "$polybar_cache_dir" ]; then
        POLYBAR_CACHE="$polybar_cache_dir/window-list.$pid"
        if touch "$POLYBAR_CACHE"; then
            return 0
        fi
    else
        echo "$0: ${FUNCNAME[0]}: failed to open $polybar_cache_dir"
    fi
    return 1
}

set_pid() {
    # @param pid - polybar process id
    declare -r pid="$1"

    if ps -p "$pid" 1>/dev/null && [ "$(ps -p "$pid" -o comm=)" = "polybar" ]
    then
        POLYBAR_ID="$pid"
        return 0
    fi
    return 1
}

get_node_id_list() {
    # node id of nodes containing windows in the active desktop
    declare -la node_win_id

    readarray -t node_win_id <<< \
        "$(bspc query -N -n .window -d focused.active)"
    echo "${node_win_id[@]}"
}

get_node_list() {
    # node id of nodes containing windows in the active desktop
    declare -a node_win_id

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
    declare -l node_focused     # focused node
    declare name                # window or class name

    node_focused="$(bspc query -N -n focused)"
    name="$(get_wminfo_property "$wminfo" 6-)"
    if [ "${#name}" -gt "$LABEL_SIZE" ]; then
        # name length exceeds label size
        name="${name::((LABEL_SIZE-2))}.."
    else
        # left justify; pad right
        name=$(printf "%-${LABEL_SIZE}s" "$name")
    fi
    # set polybar formatting
    if [ "$(get_wminfo_property "$wminfo" 1)" = "$node_focused" ]; then
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
    declare -i i=0          # number of rows in wmctrl

    readarray -t node_list <<<"$1"
    for wminfo in "${node_list[@]}"; do
        # no windows present
        if [ -z "$wminfo" ]; then echo && continue; fi

        shortname="$(get_formatted_window_name "$wminfo")"
        # separator
        if [ $((i++)) -ne 0 ]; then echo -n "$SEPARATOR"; fi
        echo -n "$shortname"
    done
}

listen_events() {
    declare -a events   # events to listen for

    trap 'rm -f "$POLYBAR_CACHE"' 0 2 3 15
    events=(
        "desktop_focus"
        "desktop_layout"
        "node_focus"
        "node_remove"
    )
    case "$SIG_START" in
    1)  # normal mode
        bspc subscribe "${events[@]}"| while
            get_formatted_window_list "$(get_node_list)" >"$POLYBAR_CACHE"
            echo hook:module/window-list1 >>"/tmp/polybar_mqueue.$POLYBAR_ID"
            read -r _
        do continue; done
        ;;
    2)  # test mode
        bspc subscribe "${events[@]}" | while
            get_formatted_window_list "$(get_node_list)"
            echo ""
            read -r _
        do continue; done
        ;;
    *)  ;;
    esac
}

main "$@"
