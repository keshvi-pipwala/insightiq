#!/bin/sh
# Railway injects $PORT at runtime. Default to 80 for local Docker.
export PORT="${PORT:-80}"

# Substitute $PORT into the nginx config template
envsubst '${PORT}' < /etc/nginx/templates/default.conf.template \
  > /etc/nginx/conf.d/default.conf

echo "Starting nginx on port $PORT"
exec nginx -g 'daemon off;'
