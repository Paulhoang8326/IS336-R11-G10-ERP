#!/usr/bin/env bash
# Back up an Odoo database and its filestore into backups/<db>_<timestamp>/.
# Usage: scripts/backup.sh <database>
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <database>" >&2
  exit 2
fi
db=$1
if ! [[ $db =~ ^[A-Za-z0-9_][A-Za-z0-9_.-]*$ ]]; then
  echo "Invalid database name: $db" >&2
  exit 2
fi

cd "$(dirname "$0")/.."

names=$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT datname FROM pg_database"')
if ! grep -Fxq "$db" <<<"$names"; then
  echo "Database not found: $db" >&2
  exit 1
fi
if ! docker compose exec -T odoo test -d "/var/lib/odoo/filestore/$db"; then
  echo "Filestore not found: /var/lib/odoo/filestore/$db" >&2
  exit 1
fi

dest="backups/${db}_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$dest"
trap 'echo "Backup failed, removing $dest" >&2; rm -rf "$dest"' ERR

docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$1"' _ "$db" >"$dest/db.dump"
docker compose exec -T odoo tar -C /var/lib/odoo/filestore -cf - "$db" >"$dest/filestore.tar"

trap - ERR
echo "Backup written to $dest"
