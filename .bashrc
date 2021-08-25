#
# ~/.bashrc
#

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# [[ PROMPT COLOUR ]]
# 24b RGB-colour for prompt {foreground,background}
PS1_FG_COLOR="232;233;236"
PS1_BG_COLOR="051;055;076"

# escape codes for prompt colours
PS1_CCODE_MAIN_FG="\x1b[38;2;${PS1_FG_COLOR}m"
PS1_CCODE_MAIN_BG="\x1b[48;2;${PS1_BG_COLOR}m"
# reset code
PS1_CCODE_RSET="\x1b[0m"

# CMAIN: specified colour codes from above variables
CMAIN=$(printf "\\[${PS1_CCODE_MAIN_FG}\\]\\[${PS1_CCODE_MAIN_BG}\\]")
CRSET=$(printf "\\[${PS1_CCODE_RSET}\\]")

PS1="${CMAIN} \D{"%Y-%m-%d"} \A [\u] ${CRSET} \$ "
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
alias df='df -hx tmpfs'
alias dot='git --git-dir="$HOME/repos/dotfiles" --work-tree="$HOME"'
alias sup='sudo pacman'
alias supc='sup -Scc'
alias supi='sup -S'
alias supr='sup -Rsn'
alias supu='sup -Syu'
alias supy='sup -Syy'
alias vim='nvim'

ls_format() {
    local default_args=(
        "-lXh"
        "--color=auto"
        "--group-directories-first"
    )
    local list_pattern='
        /^d(...){3}/ {print "\033[0;94m" $0 "\033[0;39m"}
        /^l(...){3}/ {print "\033[5;96m" $0 "\033[0;39m"}
        /^[^dl]/ {print $0}
    '
    local flag_touch=0
    if [ $# -eq 0 ]; then
        pwd &&
        ls "${default_args[@]}" | tail -fn +2 | awk "${list_pattern}"
        return "$?"
    fi

    for i in "$@"; do
        if echo "$i" | grep -qe "^-[a-zA-Z]*l"; then
            flag_touch=1; break
        fi
    done
    if [ "$flag_touch" -eq 1 ]; then
        pwd &&
        ls -h "${default_args[@]:1}" "$@"| tail -fn +2 | awk "${list_pattern}"
    else
        ls -h ${default_args[@]:1} "$@"
    fi
}

rm_confirm() {
    local opt_args=()
    local pos_args=()
    local flag_touch=0

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
        1) rm "${opt_args[@]}" -I -- "${pos_args[@]}" ;;
        2) rm "${opt_args[@]}" -i -- "${pos_args[@]}" ;;
        *) rm "${opt_args[@]}" -- "${pos_args[@]}" ;;
    esac
}

tree_format() {
    local ignore_pattern="venv|__pycache__|node_modules|.git"
    local flag_touch=0

    which tree &>/dev/null
    [ $? -eq 0 ] || "$(tree && return 1)"

    for i in "$@"; do
        if [ -d "$i" ]; then
            flag_touch=1
            echo "$(pwd)/$i"; break
        fi
    done
    if [ "$flag_touch" -ne 1 ]; then pwd; fi
    tree --dirsfirst -I "$ignore_pattern" -L 2 "$@" | tail -n +2 | head -n -2
}

alias ls='ls_format'
alias rm='rm_confirm'
alias tree='tree_format'

alias luamake=/home/mineugene/.local/share/nvim/site/pack/packer/opt/lua-language-server/3rd/luamake/luamake
