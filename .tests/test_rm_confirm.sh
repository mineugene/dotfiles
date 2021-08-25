#!/bin/sh

rm_confirm() {
    declare opt_args=()
    declare pos_args=()
    declare -i flag_touch=0

    for i in "$@"; do
        if echo "$i" | grep -qe "^--\?[a-zA-Z]\+"; then
            # optional argument
            opt_args+=("$i")
            if echo "$i" | grep -qe "^-[a-zA-Z]*r"; then
                # recursive flag matched
                flag_touch=1
            fi
        else
            # positional argument
            [ "$i" == "--" ] || pos_args+=("$i")
            if [ -h "$i" ]; then flag_touch=2; fi
        fi
    done
    case "$flag_touch" in
        1) echo "/usr/bin/rm" "${opt_args[@]}" "-I --" "${pos_args[@]}" ;;
        2) echo "/usr/bin/rm" "${opt_args[@]}" "-i --" "${pos_args[@]}" ;;
        *) echo "/usr/bin/rm" "${opt_args[@]}" "--" "${pos_args[@]}" ;;
    esac
}

test_out() {
    if [ "$?" -ne 0 ]; then
        echo -e "\033[0;31m$1 failed...\033[0;0m"
    else
        echo -e "\033[0;32m$1 passed\033[0;0m"
    fi
}

test_expect() {
    if [ "$1" == "$2" ]; then
        return 0;
    fi
    echo
    echo -e "\texpected: $1"
    echo -e "\treceived: $2"
    return 1;
}

test_plain_file() {
    local expected="/usr/bin/rm -- /tmp/test_file1"
    local received="$(rm_confirm /tmp/test_file1)"
    test_expect "$expected" "$received"
}

test_empty_dir () {
    local expected="/usr/bin/rm -d -- /tmp/test_dir1"
    local received="$(rm_confirm -d /tmp/test_dir1)"
    test_expect "$expected" "$received"
}

test_mult_files() {
    local expected="/usr/bin/rm -- /tmp/test_file1 /tmp/test_file2 /tmp/test_file3"
    local received="$(rm_confirm /tmp/test_file1 /tmp/test_file2 /tmp/test_file3)"
    test_expect "$expected" "$received"
}

test_mult_dirs() {
    local expected="/usr/bin/rm -d -- /tmp/test_dir1 /tmp/test_dir2 /tmp/test_dir3"
    local received="$(rm_confirm -d /tmp/test_dir1 /tmp/test_dir2 /tmp/test_dir3)"
    test_expect "$expected" "$received"
}

test_recurive_opt() {
    local expected="/usr/bin/rm -r -I -- /tmp/test_dir1"
    local received="$(rm_confirm -r /tmp/test_dir1)"
    test_expect "$expected" "$received"
}

test_recurive_force_opt() {
    local expected="/usr/bin/rm -rf -I -- /tmp/test_dir1"
    local received="$(rm_confirm -rf /tmp/test_dir1)"
    test_expect "$expected" "$received"
}

test_ignore_posarg_split() {
    local expected="/usr/bin/rm -f -- /tmp/test_file1 /tmp/test_file2"
    local received="$(rm_confirm -f -- /tmp/test_file1 /tmp/test_file2)"
    test_expect "$expected" "$received"
}

test_symlink() {
    local expected="/usr/bin/rm -i -- /tmp/test_link"
    local received="$(rm_confirm /tmp/test_link)"
    test_expect "$expected" "$received"
}

test_run() {
    local test_suite=(
        test_plain_file
        test_empty_dir
        test_mult_files
        test_mult_dirs
        test_recurive_opt
        test_recurive_force_opt
        test_ignore_posarg_split
        test_symlink
    )
    mkdir /tmp/test_dir{1..3}
    touch /tmp/test_file{1..3}.dat
    ln -s /tmp/test_file2 /tmp/test_link
    for t in "${test_suite[@]}"; do
        $t
        test_out "$t"
    done
    rm -r /tmp/test_dir*
    rm /tmp/test_file*.dat
    rm -f /tmp/test_link
}
test_run
