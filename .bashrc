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
PATH="/usr/local/sbin:/usr/local/bin:/usr/bin:/usr/bin/site_perl:/usr/bin/vendor_perl:/usr/bin/core_perl:$PYENV_ROOT/bin"


# [[ PYENV CONFIG ]]
# installed with pyenv/pyenv-installer
# enable shims
eval "$(pyenv init --path)"
# virtualenv plugin
eval "$(pyenv virtualenv-init -)"

# [[ ALIASES ]]
[[ -f ~/.bash_aliases ]] && . ~/.bash_aliases
