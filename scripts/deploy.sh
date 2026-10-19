#!/bin/sh
# Deploy a tagged release of Metra to a server that has no internet access.
# Runs on a machine that has internet and Docker (or Podman). See
# docs/deploying.md.
#
#   scripts/deploy.sh [-n] [-H HOST] [-d FOLDER] VERSION
#
# Builds the image from the tag vVERSION for the server's CPU, copies it and
# docker/upgrade.sh to HOST over SSH and runs the upgrade in FOLDER there.
#   -n         dry run: check everything, print the steps, change nothing
#   -H HOST    SSH host, as in ~/.ssh/config (default: metra)
#   -d FOLDER  install folder on the server, relative to the SSH user's home
#              (default: metra)
# METRA_PLUGIN_PACKAGES, if set, is passed to the build (see docs/plugins.md).
# Set METRA_DOCKER=podman to build with Podman.
set -eu

usage() {
    echo "usage: $0 [-n] [-H HOST] [-d FOLDER] VERSION" >&2
    exit 2
}

dry_run=
host=metra
dir=metra
while getopts nH:d: option; do
    case $option in
        n) dry_run=1 ;;
        H) host=$OPTARG ;;
        d) dir=$OPTARG ;;
        *) usage ;;
    esac
done
shift $((OPTIND - 1))
[ $# -eq 1 ] || usage
version=$1
docker=${METRA_DOCKER:-docker}

case $version in
    "" | *[!0-9.]* | .* | *. | *..*)
        echo "VERSION must look like 1.2.3 (without the v)." >&2
        exit 2
        ;;
esac
case $dir in
    "" | /* | *[!A-Za-z0-9._/-]*)
        echo "FOLDER must be a plain path relative to the home folder, such as metra." >&2
        exit 2
        ;;
esac

run() {
    echo "+ $*"
    [ -n "$dry_run" ] || "$@"
}

cd "$(dirname "$0")/.."
tag=v$version
git fetch --quiet --tags origin 2>/dev/null || echo "Could not fetch tags; using the local ones."
git rev-parse --quiet --verify "refs/tags/$tag" >/dev/null || {
    echo "There is no tag $tag." >&2
    exit 1
}
tagged=$(git show "$tag:pyproject.toml" | sed -n 's/^version = "\(.*\)"$/\1/p' | head -n 1)
[ "$tagged" = "$version" ] || {
    echo "pyproject.toml at $tag says version $tagged, not $version." >&2
    exit 1
}

work=$(mktemp -d)
sockets=$(mktemp -d)
# All SSH and scp calls share one connection, so a deploy logs in once.
# Several logins in a row can look like an SSH scan to a firewall's IPS,
# which then blocks the laptop.
ssh_opts="-o ControlMaster=auto -o ControlPath=$sockets/ssh -o ControlPersist=600"
trap 'ssh $ssh_opts -O exit "$host" 2>/dev/null; rm -rf "$work" "$sockets"' EXIT

arch=$(ssh $ssh_opts "$host" uname -m)
case $arch in
    x86_64) platform=linux/amd64 ;;
    aarch64 | arm64) platform=linux/arm64 ;;
    *) echo "Unknown server CPU $arch." >&2; exit 1 ;;
esac
if ssh $ssh_opts "$host" test -f "$dir/compose.yaml" -a -f "$dir/.env"; then
    :
elif [ $? -eq 255 ]; then
    echo "Lost the SSH connection to $host." >&2
    exit 1
else
    echo "$host:$dir has no compose.yaml and .env; set up the install first (docs/deploying.md)." >&2
    exit 1
fi

git archive "$tag" | tar -x -C "$work/" -f -
image=metra:$version
file=metra-$version.tar.gz

echo "Deploying $tag to $host:$dir ($platform)."
run "$docker" build --platform "$platform" \
    --build-arg "METRA_PLUGIN_PACKAGES=${METRA_PLUGIN_PACKAGES:-}" \
    -t "$image" "$work"
echo "+ $docker save $image | gzip >$work/$file"
[ -n "$dry_run" ] || "$docker" save "$image" | gzip >"$work/$file"
run ssh $ssh_opts "$host" mkdir -p "$dir/images"
run scp $ssh_opts "$work/$file" "$work/docker/upgrade.sh" "$host:$dir/images/"
run ssh $ssh_opts "$host" sh "$dir/images/upgrade.sh" "$version" "$dir/images/$file" "$dir"
run ssh $ssh_opts "$host" rm -f "$dir/images/$file"
if [ -n "$dry_run" ]; then
    echo "Dry run: nothing was changed."
else
    echo "Deployed $version to $host."
fi
