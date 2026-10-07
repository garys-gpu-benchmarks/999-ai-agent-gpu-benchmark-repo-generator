#!/usr/bin/env bash
# File: scripts/lib/noninteractive_root.sh
# Description: run_noninteractive_root -- run a privileged command (apt-get,
#              amdgpu-install, tee, usermod, make install, reboot, ...) so it can
#              never stop on a terminal it does not own.
# Execution: source scripts/lib/noninteractive_root.sh; run_noninteractive_root apt-get install -y pkg
#
# Why: Ubuntu's sudoers sets "Defaults use_pty". When stdin is still a terminal
# but stdout is redirected (for example a benchmark loop that appends to a log),
# sudo runs the command on a new pseudo-terminal. apt-get restores that
# terminal's settings when it finishes, the kernel stops it with SIGTTOU, and
# the non-interactive caller waits forever (seen on Ubuntu 26.04 in setup step 6,
# sudo amdgpu-install -> apt-get). Ctrl-C does not reach it.
#
# What it does:
#   * root: runs the command directly (no sudo, so no extra pty);
#   * not root: runs it through sudo (a password prompt still works on /dev/tty);
#   * a terminal on stdin is replaced with /dev/null; a pipe or heredoc is kept,
#     so "curl ... | run_noninteractive_root tee FILE" still works;
#   * SIGTTOU/SIGTTIN are ignored in the command, so a terminal restore cannot
#     stop it even if sudo still allocates a pty;
#   * DEBIAN_FRONTEND defaults to noninteractive. Leading VAR=value arguments
#     are accepted, as with sudo ("run_noninteractive_root FOO=1 cmd args").

[[ -n "${_NONINTERACTIVE_ROOT_SH:-}" ]] && return 0
_NONINTERACTIVE_ROOT_SH=1

run_noninteractive_root() {
  local -a cmd=(
    bash -c 'trap "" TTOU TTIN; exec env "$@"' _
    "DEBIAN_FRONTEND=${DEBIAN_FRONTEND:-noninteractive}" "$@"
  )
  if [[ "$(id -u)" -ne 0 ]]; then
    if ! command -v sudo >/dev/null 2>&1; then
      printf '[ERROR] %s needs root or sudo.\n' "$1" >&2
      return 1
    fi
    cmd=(sudo "${cmd[@]}")
  fi
  if [[ -t 0 ]]; then
    "${cmd[@]}" </dev/null
  else
    "${cmd[@]}"
  fi
}
