#!/bin/sh
# Starts the API container. Shared by the Dockerfile's CMD and Railway's
# startCommand, so every deploy that runs this image (Railway, Kubernetes, a
# private fork's own platform) seeds the annotation sets the same way.
#
# The sync reads the eval datasets baked into the image and upserts the
# annotation sets; it is idempotent and takes a couple of seconds. It needs the
# migrations applied first, which each platform does before this runs (Railway's
# preDeployCommand, the Kubernetes init container). A failed sync is reported
# but does not stop the API from starting: annotation is optional, serving is not.
uv run python -m lib.services.annotations.sync ||
  echo "Annotation sync failed; starting the API without it." >&2

exec uv run uvicorn lib.api.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WORKERS:-4}"
