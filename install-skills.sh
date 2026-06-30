#!/bin/sh
set -eu

action="install"
mode="link"
targets="codex,claude"
replace_unmanaged=0

usage() {
  cat <<'EOF'
Usage:
  sh install-skills.sh [options]

Options:
  --action install|remove  Install or remove managed skills. Default: install.
  --remove                 Shortcut for --action remove.
  --mode link|copy       Install by symlink or managed copy. Default: link.
  --targets LIST         Comma-separated targets. Default: codex,claude.
  --replace-unmanaged    Move same-name unmanaged target paths aside before installing.
  -h, --help             Show this help.
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --action)
      action="$2"
      shift 2
      ;;
    --remove)
      action="remove"
      shift
      ;;
    --mode)
      mode="$2"
      shift 2
      ;;
    --targets)
      targets="$2"
      shift 2
      ;;
    --replace-unmanaged)
      replace_unmanaged=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$action" in
  install|remove) ;;
  *)
    echo "Invalid --action: $action" >&2
    exit 2
    ;;
esac

case "$mode" in
  link|copy) ;;
  *)
    echo "Invalid --mode: $mode" >&2
    exit 2
    ;;
esac

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
sync_script="$repo_root/scripts/sync-installed-skills.sh"

if [ ! -f "$sync_script" ]; then
  echo "Missing sync script: $sync_script" >&2
  exit 1
fi

if [ "$action" = "remove" ]; then
  echo "Removing ai-skill-lab skills"
else
  echo "Installing ai-skill-lab skills"
fi
echo "Repo:    $repo_root"
echo "Action:  $action"
echo "Mode:    $mode"
echo "Targets: $targets"
echo

if [ "$replace_unmanaged" -eq 1 ]; then
  sh "$sync_script" --action "$action" --mode "$mode" --targets "$targets" --replace-unmanaged --apply
else
  sh "$sync_script" --action "$action" --mode "$mode" --targets "$targets" --apply
fi

echo
if [ "$action" = "remove" ]; then
  echo "Remove complete. Restart Codex and start a new Claude Code session to reload skills."
else
  echo "Install complete. Restart Codex and start a new Claude Code session to reload skills."
fi
