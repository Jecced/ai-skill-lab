#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
install_script="$repo_root/install-skills.sh"

if [ ! -f "$install_script" ]; then
  echo "Missing install script: $install_script" >&2
  exit 1
fi

sh "$install_script" --remove "$@"
