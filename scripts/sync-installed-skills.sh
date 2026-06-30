#!/bin/sh
set -eu

action="install"
mode="link"
targets="codex,claude"
codex_home="${CODEX_HOME:-}"
claude_home="${CLAUDE_HOME:-}"
apply=0
replace_unmanaged=0

manifest_name=".ai-skill-lab-install.manifest"
marker_name=".ai-skill-lab-managed"
managed_by_line="managed-by=ai-skill-lab"

usage() {
  cat <<'EOF'
Usage:
  sh scripts/sync-installed-skills.sh [options]

Options:
  --action install|remove       Install or remove managed skills. Default: install.
  --remove                      Shortcut for --action remove.
  --mode link|copy              Install by symlink or by managed copy. Default: link.
  --targets codex,claude        Comma-separated targets. Default: codex,claude.
  --codex-home PATH             Override Codex home. Default: $CODEX_HOME or ~/.codex.
  --claude-home PATH            Override Claude home. Default: $CLAUDE_HOME or ~/.claude.
  --apply                       Modify target directories. Without this, the script is a dry run.
  --replace-unmanaged           Move conflicting unmanaged paths aside before installing.
  -h, --help                    Show this help.
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
    --codex-home)
      codex_home="$2"
      shift 2
      ;;
    --claude-home)
      claude_home="$2"
      shift 2
      ;;
    --apply)
      apply=1
      shift
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

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd -P)
skills_root="$repo_root/skills"
vendor_tools_root="$repo_root/vendor-tools"

if [ ! -d "$skills_root" ]; then
  echo "Missing source skills directory: $skills_root" >&2
  exit 1
fi
if [ ! -d "$vendor_tools_root" ]; then
  echo "Missing source vendor-tools directory: $vendor_tools_root" >&2
  exit 1
fi

if [ "$apply" -eq 0 ]; then
  echo "Dry run only. Re-run with --apply to modify target directories."
fi

run_action() {
  message=$1
  shift
  if [ "$apply" -eq 1 ]; then
    echo "APPLY: $message"
    "$@"
  else
    echo "DRY-RUN: $message"
  fi
}

ensure_dir() {
  path=$1
  if [ -d "$path" ]; then
    return 0
  fi
  run_action "create directory $path" mkdir -p "$path"
}

path_under_repo() {
  path=$1
  case "$path" in
    "$repo_root"|"$repo_root"/*) return 0 ;;
    *) return 1 ;;
  esac
}

same_path() {
  [ "$1" = "$2" ]
}

absolute_link_target() {
  link_path=$1
  target=$(readlink "$link_path")
  case "$target" in
    /*) printf '%s\n' "$target" ;;
    *) printf '%s\n' "$(CDPATH= cd -- "$(dirname -- "$link_path")" && pwd -P)/$target" ;;
  esac
}

is_managed_copy() {
  path=$1
  marker="$path/$marker_name"
  [ -f "$marker" ] || return 1
  grep -qx "$managed_by_line" "$marker" || return 1
  repo_line=$(grep '^repo_root=' "$marker" | sed '1q' || true)
  [ "$repo_line" = "repo_root=$repo_root" ]
}

write_marker() {
  path=$1
  {
    echo "$managed_by_line"
    echo "repo_root=$repo_root"
    echo "updated_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  } > "$path/$marker_name"
}

remove_managed_path_apply() {
  path=$1
  if [ -L "$path" ]; then
    rm -- "$path"
  else
    rm -rf -- "$path"
  fi
}

remove_managed_path() {
  path=$1
  skip_unmanaged=${2:-0}
  [ -e "$path" ] || [ -L "$path" ] || return 0
  if [ -L "$path" ]; then
    target=$(absolute_link_target "$path")
    if ! path_under_repo "$target"; then
      if [ "$skip_unmanaged" -eq 1 ]; then
        echo "SKIP: unmanaged link $path -> $target"
        return 0
      fi
      echo "Refusing to remove link outside this repo: $path -> $target" >&2
      exit 1
    fi
    run_action "remove managed link $path" remove_managed_path_apply "$path"
    return 0
  fi
  if is_managed_copy "$path"; then
    run_action "remove managed copy $path" remove_managed_path_apply "$path"
    return 0
  fi
  if [ "$skip_unmanaged" -eq 1 ]; then
    echo "SKIP: unmanaged path $path"
    return 0
  fi
  echo "Refusing to remove unmanaged path: $path" >&2
  exit 1
}

move_unmanaged_aside_apply() {
  src=$1
  dst=$2
  mv -- "$src" "$dst"
}

move_unmanaged_aside() {
  path=$1
  stamp=$(date -u '+%Y%m%d-%H%M%S')
  backup="$path.unmanaged-backup-$stamp"
  index=1
  while [ -e "$backup" ] || [ -L "$backup" ]; do
    backup="$path.unmanaged-backup-$stamp-$index"
    index=$((index + 1))
  done
  run_action "move unmanaged path $path to $backup" move_unmanaged_aside_apply "$path" "$backup"
}

create_link_apply() {
  src=$1
  dst=$2
  ln -s "$src" "$dst"
}

copy_managed_apply() {
  src=$1
  dst=$2
  cp -R "$src" "$dst"
  write_marker "$dst"
}

ensure_managed_entry() {
  src=$1
  dst=$2
  ensure_dir "$(dirname -- "$dst")"

  if [ -e "$dst" ] || [ -L "$dst" ]; then
    if [ -L "$dst" ]; then
      target=$(absolute_link_target "$dst")
      if same_path "$target" "$src"; then
        echo "OK: $dst already points to $src"
        return 0
      fi
      if path_under_repo "$target"; then
        remove_managed_path "$dst"
      elif [ "$replace_unmanaged" -eq 1 ]; then
        move_unmanaged_aside "$dst"
      else
        echo "Refusing to replace unmanaged link: $dst -> $target" >&2
        exit 1
      fi
    elif is_managed_copy "$dst"; then
      remove_managed_path "$dst"
    elif [ "$replace_unmanaged" -eq 1 ]; then
      move_unmanaged_aside "$dst"
    else
      echo "Destination exists and is not managed by ai-skill-lab: $dst" >&2
      exit 1
    fi
  fi

  if [ "$mode" = "link" ]; then
    run_action "create symlink $dst -> $src" create_link_apply "$src" "$dst"
  else
    run_action "copy $src to $dst" copy_managed_apply "$src" "$dst"
  fi
}

manifest_repo_root() {
  manifest_path=$1
  [ -f "$manifest_path" ] || return 0
  grep '^repo_root=' "$manifest_path" | sed -n '1s/^repo_root=//p;1q'
}

manifest_skills() {
  manifest_path=$1
  [ -f "$manifest_path" ] || return 0
  sed -n 's/^skill=//p' "$manifest_path"
}

write_manifest_apply() {
  home=$1
  manifest_path="$home/$manifest_name"
  {
    echo "# ai-skill-lab managed install manifest v1"
    echo "repo_root=$repo_root"
    echo "mode=$mode"
    echo "updated_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    for skill_name in $skill_names; do
      echo "skill=$skill_name"
    done
    echo "vendor_tools=vendor-tools"
  } > "$manifest_path"
}

write_manifest() {
  home=$1
  run_action "write manifest $home/$manifest_name" write_manifest_apply "$home"
}

remove_manifest_apply() {
  manifest_path=$1
  rm -f -- "$manifest_path"
}

remove_manifest() {
  home=$1
  manifest_path="$home/$manifest_name"
  [ -f "$manifest_path" ] || return 0
  old_repo_root=$(manifest_repo_root "$manifest_path" || true)
  if [ "$old_repo_root" != "$repo_root" ]; then
    echo "SKIP: manifest is not managed by this repo: $manifest_path"
    return 0
  fi
  run_action "remove manifest $manifest_path" remove_manifest_apply "$manifest_path"
}

target_home() {
  target=$1
  case "$target" in
    codex)
      if [ -n "$codex_home" ]; then
        printf '%s\n' "$codex_home"
      else
        printf '%s\n' "$HOME/.codex"
      fi
      ;;
    claude)
      if [ -n "$claude_home" ]; then
        printf '%s\n' "$claude_home"
      else
        printf '%s\n' "$HOME/.claude"
      fi
      ;;
    *)
      echo "Unknown target '$target'. Use codex, claude, or both." >&2
      exit 2
      ;;
  esac
}

skill_names=""
for skill_dir in "$skills_root"/*; do
  [ -d "$skill_dir" ] || continue
  [ -f "$skill_dir/SKILL.md" ] || continue
  skill_name=$(basename -- "$skill_dir")
  skill_names="$skill_names $skill_name"
done

if [ -z "$skill_names" ]; then
  if [ "$action" = "install" ]; then
    echo "No skills found under $skills_root" >&2
    exit 1
  fi
fi

IFS_SAVE=$IFS
IFS=,
for target in $targets; do
  IFS=$IFS_SAVE
  target=$(printf '%s' "$target" | tr '[:upper:]' '[:lower:]' | sed 's/^ *//;s/ *$//')
  [ -n "$target" ] || continue

  home=$(target_home "$target")
  skills_home="$home/skills"
  vendor_home="$home/vendor-tools"
  manifest_path="$home/$manifest_name"

  echo
  echo "Target: $target"
  echo "Home:   $home"
  echo "Action: $action"
  echo "Mode:   $mode"

  if [ "$action" = "remove" ]; then
    remove_skill_names="$skill_names"
    old_repo_root=$(manifest_repo_root "$manifest_path" || true)
    if [ -n "$old_repo_root" ] && [ "$old_repo_root" = "$repo_root" ]; then
      remove_skill_names="$remove_skill_names $(manifest_skills "$manifest_path")"
    elif [ -n "$old_repo_root" ]; then
      echo "Warning: existing manifest belongs to another repo; uninstall will only remove links/copies that point to this repo: $old_repo_root" >&2
    fi
    for skill_name in $remove_skill_names; do
      remove_managed_path "$skills_home/$skill_name" 1
    done
    remove_managed_path "$vendor_home" 1
    remove_manifest "$home"
    IFS=,
    continue
  fi

  ensure_dir "$home"
  ensure_dir "$skills_home"

  old_repo_root=$(manifest_repo_root "$manifest_path" || true)
  if [ -n "$old_repo_root" ] && [ "$old_repo_root" = "$repo_root" ]; then
    for old_skill_name in $(manifest_skills "$manifest_path"); do
      found=0
      for skill_name in $skill_names; do
        if [ "$old_skill_name" = "$skill_name" ]; then
          found=1
          break
        fi
      done
      if [ "$found" -eq 0 ]; then
        remove_managed_path "$skills_home/$old_skill_name"
      fi
    done
  elif [ -n "$old_repo_root" ]; then
    echo "Warning: existing manifest belongs to another repo; stale cleanup is skipped: $old_repo_root" >&2
  fi

  for skill_name in $skill_names; do
    ensure_managed_entry "$skills_root/$skill_name" "$skills_home/$skill_name"
  done

  ensure_managed_entry "$vendor_tools_root" "$vendor_home"
  write_manifest "$home"

  IFS=,
done
IFS=$IFS_SAVE
