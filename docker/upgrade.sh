#!/bin/sh
# Upgrade one install of Metra to a new image. Runs on the server.
# See docs/deploying.md.
#
#   upgrade.sh VERSION IMAGE_TAR [FOLDER]
#
# Takes a backup, loads IMAGE_TAR (made with `docker save` or `podman save`,
# tagged metra:VERSION), points FOLDER/.env at it with METRA_IMAGE and
# recreates the web and worker containers (migrations run on start). If the
# app does not answer /healthz afterwards, it goes back to the previous image
# and exits with an error. FOLDER defaults to the current folder. Needs only
# a POSIX shell and podman-compose: no Python on the server.
set -eu

usage() {
    echo "usage: $0 VERSION IMAGE_TAR [FOLDER]" >&2
    echo "  e.g. $0 0.2.0 ~/metra/images/metra-0.2.0.tar.gz ~/metra" >&2
    exit 2
}

[ $# -ge 2 ] && [ $# -le 3 ] || usage
version=$1
tar=$2
dir=${3:-.}

case $version in
    "" | *[!0-9.]* | .* | *. | *..*)
        echo "VERSION must look like 1.2.3." >&2
        exit 2
        ;;
esac
[ -f "$tar" ] || { echo "$tar does not exist." >&2; exit 1; }
[ -f "$dir/compose.yaml" ] && [ -f "$dir/.env" ] || {
    echo "$dir has no compose.yaml and .env; is it a Metra install?" >&2
    exit 1
}
tar=$(cd "$(dirname "$tar")" && pwd)/$(basename "$tar")
cd "$dir"

new=metra:$version
previous=$(sed -n 's/^METRA_IMAGE=//p' .env | tail -n 1)
previous=${previous:-metra:latest}
echo "Upgrading $(pwd) from $previous to $new."

set_image() {
    awk -v image="$1" '
        /^METRA_IMAGE=/ { next }
        { print }
        END { print "METRA_IMAGE=" image }
    ' .env >.env.upgrade
    # cat keeps the permissions of .env, which holds the secret key.
    cat .env.upgrade >.env
    rm -f .env.upgrade
}

start() {
    podman-compose up -d --force-recreate web worker
}

healthy() {
    tries=0
    while [ $tries -lt 40 ]; do
        if podman-compose exec -T web python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)" >/dev/null 2>&1; then
            return 0
        fi
        tries=$((tries + 1))
        sleep 3
    done
    return 1
}

if podman-compose exec -T web true >/dev/null 2>&1; then
    echo "Taking a snapshot first."
    podman-compose exec -T web python manage.py snapshot
else
    echo "The web container is not running, so no snapshot was taken (the new version takes one before migrating)."
fi

podman load -i "$tar"
podman image exists "$new" || {
    echo "$tar does not contain the image $new." >&2
    exit 1
}

set_image "$new"
start
if healthy; then
    echo "Metra $version is running in $(pwd)."
    exit 0
fi

echo "Metra $version did not become healthy; going back to $previous." >&2
podman-compose logs --tail 50 web >&2 || true
set_image "$previous"
start
if healthy; then
    echo "$previous is running again. If $version ran migrations, the old" >&2
    echo "version may not work with the database: restore the backup above" >&2
    echo "(see INSTALL.md) if you see errors." >&2
else
    echo "$previous did not come back either. Restore the backup (INSTALL.md)." >&2
fi
exit 1
