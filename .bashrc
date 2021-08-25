#
# ~/.bashrc
#

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# [[ PROMPT COLOUR ]]
# 24b RGB-colour for prompt; foreground & background
PS1_FG_COLOR="232;233;236"
PS1_BG_COLOR="051;055;076"

# escape codes for prompt colours
PS1_CCODE_MAIN_FG="\x1b[38;2;${PS1_FG_COLOR}m"
PS1_CCODE_MAIN_BG="\x1b[48;2;${PS1_BG_COLOR}m"
# reset code
PS1_CCODE_RSET="\x1b[0m"

# CMAIN: specified colour codes from above variables
CMAIN="$(printf "\\[%b\\]\[%b\\]" "${PS1_CCODE_MAIN_FG}" "${PS1_CCODE_MAIN_BG}")"
CRSET="$(printf "\\[%b\\]" "${PS1_CCODE_RSET}")"

PS1="${CMAIN} \D{%Y-%m-%d} \A [\u] ${CRSET} \$ "
PS2="${CMAIN}    ${CRSET} ▶ "

# [[ PATH ]]
PATH="/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl:/home/mineugene/.cargo/bin:$PYENV_ROOT/bin"

# [[ PYENV CONFIG ]]
# installed with pyenv/pyenv-installer
# enable shims
eval "$(pyenv init --path)"
# virtualenv plugin
eval "$(pyenv virtualenv-init -)"

# [[ ALIASES ]]
alias cp='rsync --info=progress2'
alias df='/usr/bin/df -hx tmpfs'
alias dot='git --git-dir="$HOME/repos/dotfiles" --work-tree="$HOME"'
alias sup='sudo pacman'
alias supc='sup -Scc'
alias supi='sup -S'
alias supr='sup -Rsn'
alias supu='sup -Syu'
alias supy='sup -Syy'
alias vim='nvim'

cd_format() {
    declare curr_dir=""
    declare next_dir=""

    curr_dir="$(pwd)"
    if [ "$#" -eq 0 ]; then echo "$curr_dir" && return 0; fi
    for i in "$@"; do
        if [ -d "$i" ]; then
            next_dir="$(realpath "$i")"
            break
        fi
    done
    if builtin cd "$@"; then
        echo "$next_dir ◀ $curr_dir"
    fi
}

ls_format() {
    declare default_args=()
    declare list_pattern=""
    declare -i flag_touch=0

    default_args=(
        "-lXh"
        "--color=auto"
        "--group-directories-first"
    )
    # shellcheck disable=SC2016
    # variables in list_pattern pertains to awk syntax: do not escape
    list_pattern='
        /^d(...){3}/ {print "\033[0;94m" $0 "\033[0;39m"}
        /^l(...){3}/ {print "\033[5;96m" $0 "\033[0;39m"}
        /^[^dl]/ {print $0}
    '
    if [ $# -eq 0 ]; then
        pwd &&
        /usr/bin/ls "${default_args[@]}" | tail -fn +2 | awk "${list_pattern}"
        return "$?"
    fi

    for i in "$@"; do
        if echo "$i" | grep -qe "^-[a-zA-Z]*l"; then
            flag_touch=1; break
        fi
    done
    if [ "$flag_touch" -eq 1 ]; then
        pwd &&
        /usr/bin/ls -h "${default_args[@]:1}" "$@"| tail -fn +2 | awk "${list_pattern}"
    else
        /usr/bin/ls -h "${default_args[@]:1}" "$@"
    fi
}

rm_confirm() {
    declare opt_args=()
    declare pos_args=()
    declare -i flag_touch=0

    for i in "$@"; do
        if echo "$i" | grep -qe "^--\?[a-zA-Z]\+"; then
            opt_args+=("$i")
            if echo "$i" | grep -qe "^-[a-zA-Z]*r"; then
                flag_touch=1
            fi
        else
            [ "$i" == "--" ] || pos_args+=("$i")
            if [ -h "$i" ]; then flag_touch=2; fi
        fi
    done
    case "$flag_touch" in
        1) /usr/bin/rm "${opt_args[@]}" -I -- "${pos_args[@]}" ;;
        2) /usr/bin/rm "${opt_args[@]}" -i -- "${pos_args[@]}" ;;
        *) /usr/bin/rm "${opt_args[@]}" -- "${pos_args[@]}" ;;
    esac
}

tree_format() {
    declare ignore_pattern=""
    declare head=""
    declare default_args=()
    declare -i flag_touch=0

    ignore_pattern="|venv|__pycache__|node_modules|.git"
    default_args=(
        "--dirsfirst"
        "--filelimit" "32"
        "-I" "'$ignore_pattern'"
        "-L" "2"
    )
    if ! which /usr/bin/tree &>/dev/null; then
        /usr/bin/tree && return 1
    fi

    for i in "$@"; do
        if [ -d "$i" ]; then
            flag_touch=1
            realpath "$i"; break
        fi
    done
    if [ "$flag_touch" -ne 1 ]; then pwd; fi

    head="$(/usr/bin/tree "${default_args[@]}" "$@" | head -n 1)"
    if [ -d "$head" ]
    then
        /usr/bin/tree "${default_args[@]}" "$@" | tail -n +2 | head -n -2
    else
        echo "${head/+([![])/}"
    fi
}

alias cd='cd_format'
alias ls='ls_format'
alias rm='rm_confirm'
alias tree='tree_format'

alias luamake=/home/mineugene/.local/share/nvim/site/pack/packer/opt/lua-language-server/3rd/luamake/luamake
