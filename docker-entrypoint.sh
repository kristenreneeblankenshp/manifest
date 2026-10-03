#!/bin/sh
# Hosting platforms often mount the persistent disk owned by root: give it to the app user,
# then run the server without root privileges.
set -e
DATA="${MANIFEST_DATA_DIR:-/data}"
mkdir -p "$DATA"
if [ "$(id -u)" = "0" ]; then
  chown -R manifest:manifest "$DATA"
  export HOME=/home/manifest USER=manifest
  exec setpriv --reuid=manifest --regid=manifest --init-groups "$@"
fi
exec "$@"
