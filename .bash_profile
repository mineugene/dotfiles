#
# ~/.bash_profile
#

if [ -z "${DISPLAY}" ] && [ "${XDG_VTNR}" -eq 1 ]; then
  exec startx
fi

# GPG and SSH
export GPG_TTY=$(tty)
export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"

# pyenv root
export PYENV_ROOT="$HOME/.pyenv"

[[ -f ~/.bashrc ]] && . ~/.bashrc
