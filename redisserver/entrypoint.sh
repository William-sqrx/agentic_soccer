#!/bin/sh
# Build a minimal redis.conf at container start so the password is
# injected from the REDIS_PASSWORD environment variable.
set -e

CONF=/tmp/redis.conf

echo "bind 0.0.0.0" > "$CONF"
echo "protected-mode no" >> "$CONF"

if [ -n "$REDIS_PASSWORD" ]; then
  echo "requirepass $REDIS_PASSWORD" >> "$CONF"
fi

exec redis-server "$CONF"
