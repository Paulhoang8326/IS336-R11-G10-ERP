#!/usr/bin/env bash
# Restore a backup made by backup.sh into a target database.
# Usage: scripts/restore.sh <backup_dir> <target_database>
set -euo pipefail

if [ $# -ne 2 ]; then
  echo "Usage: $0 <backup_dir> <target_database>" >&2
  exit 2
fi
target=$2
if ! [[ $target =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]]; then
  echo "Invalid database name: $target" >&2
  exit 2
fi
src=$(cd "$1" && pwd)
for f in db.dump filestore.tar; do
  if [ ! -f "$src/$f" ]; then
    echo "Missing $f in $src" >&2
    exit 1
  fi
done

cd "$(dirname "$0")/.."

names=$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT datname FROM pg_database"')
if grep -Fxq "$target" <<<"$names"; then
  read -r -p "Database '$target' already exists. Overwrite it and its filestore? [y/N] " answer
  case $answer in
    y | Y | yes | YES) ;;
    *)
      echo "Aborted." >&2
      exit 1
      ;;
  esac
  docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --force "$1"' _ "$target"
fi

docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' _ "$target"
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" --no-owner --exit-on-error -d "$1"' _ "$target" <"$src/db.dump"

# The archive holds one top-level folder named after the source database; rename it to the target.
docker compose exec -T odoo sh -c '
  set -e
  fs=/var/lib/odoo/filestore
  mkdir -p "$fs"
  rm -rf "$fs/$1"
  tmp=$(mktemp -d "$fs/.restore.XXXXXX")
  tar -C "$tmp" -xf -
  mv "$tmp"/* "$fs/$1"
  rmdir "$tmp"
' _ "$target" <"$src/filestore.tar"

echo "Restored $src into database $target"
