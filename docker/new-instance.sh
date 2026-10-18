#!/bin/sh
# Set up a separate install of SmallCompanyRegister for one organisation.
# See docs/multiple-organisations.md.
#
#   new-instance.sh NAME HOSTNAME PORT [FOLDER]
#
# Creates FOLDER (default ./NAME) with its own compose.yaml, .env and
# compose.override.yaml. The install gets its own containers and volumes
# (prefixed NAME), so it shares no data with any other install, and its web
# container listens on 127.0.0.1:PORT for a Cloudflare Tunnel or a reverse
# proxy on the host. Needs only a POSIX shell: no Python on the server.
set -eu

usage() {
    echo "usage: $0 NAME HOSTNAME PORT [FOLDER]" >&2
    echo "  e.g. $0 vatten register.vattenlag.ax 8001" >&2
    exit 2
}

[ $# -ge 3 ] && [ $# -le 4 ] || usage
name=$1
host=$2
port=$3
dir=${4:-./$name}

case $name in
    "" | [!a-z0-9]* | *[!a-z0-9_-]*)
        echo "NAME must be lower-case letters, digits, - or _, starting with a letter or digit." >&2
        exit 2
        ;;
esac
case $host in
    "" | *[!A-Za-z0-9.-]*)
        echo "HOSTNAME must be a plain host name such as register.example.com." >&2
        exit 2
        ;;
esac
case $port in
    "" | *[!0-9]*) echo "PORT must be a number." >&2; exit 2 ;;
esac
if [ "$port" -lt 1024 ] || [ "$port" -gt 65535 ]; then
    echo "PORT must be between 1024 and 65535." >&2
    exit 2
fi

# compose.yaml and .env.example sit next to this script on a server, or one
# folder up in a checkout of the repository.
here=$(cd "$(dirname "$0")" && pwd)
src=
for candidate in "$here" "$here/.."; do
    if [ -f "$candidate/compose.yaml" ] && [ -f "$candidate/.env.example" ]; then
        src=$candidate
        break
    fi
done
if [ -z "$src" ]; then
    echo "compose.yaml and .env.example were not found next to $0." >&2
    exit 1
fi

if [ -e "$dir" ]; then
    echo "$dir already exists; pick another NAME or FOLDER." >&2
    exit 1
fi

# Other installs are usually the sibling folders; refuse a port they use.
parent=$(dirname "$dir")
for other in "$parent"/compose.override.yaml "$parent"/*/compose.override.yaml; do
    [ -f "$other" ] || continue
    if grep -q ":$port:8000" "$other"; then
        echo "Port $port is already used by $other." >&2
        exit 1
    fi
done

secret=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 50)

mkdir -p "$dir"
cp "$src/compose.yaml" "$dir/compose.yaml"

{
    echo "# Install: $name ($host). Written by new-instance.sh."
    echo "COMPOSE_PROJECT_NAME=$name"
    echo
    awk -v host="$host" -v secret="$secret" '
        /^SCR_DOMAIN=/ { print "SCR_DOMAIN=" host; next }
        /^SCR_SECRET_KEY=/ { print "SCR_SECRET_KEY=" secret; next }
        /^SCR_DEBUG=/ { print "SCR_DEBUG=false"; next }
        /^SCR_ALLOWED_HOSTS=/ { print "SCR_ALLOWED_HOSTS=" host; next }
        /^SCR_CSRF_TRUSTED_ORIGINS=/ { print "SCR_CSRF_TRUSTED_ORIGINS=https://" host; next }
        /^# COMPOSE_PROJECT_NAME=/ { next }
        { print }
    ' "$src/.env.example"
} >"$dir/.env"
chmod 600 "$dir/.env"

cat >"$dir/compose.override.yaml" <<EOF
# Written by new-instance.sh: the app on localhost only, for the tunnel.
services:
  web:
    ports:
      - "127.0.0.1:$port:8000"
EOF

cat <<EOF
Created $dir for $name.

Next:
  1. Check $dir/.env (email, SMS, backups). If you send backups off the
     server, give this install its own SCR_BACKUP_REMOTE_PATH and password.
  2. Start it:
       cd $dir && podman-compose up -d web worker
  3. In Cloudflare, add the public hostname $host with service
     http://localhost:$port
  4. Make the first admin:
       podman-compose exec web python manage.py createsuperuser
EOF
