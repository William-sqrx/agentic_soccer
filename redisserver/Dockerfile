FROM redis:7-alpine

# Use a custom config so we can set a password via env var at runtime.
# The entrypoint script will generate redis.conf from the env.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 6379

ENTRYPOINT ["/entrypoint.sh"]
