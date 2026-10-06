#!/bin/sh
set -e

# Start the public FlyHi web/proxy server first.
python cloud_server.py &

# Start the internal Rasa action server.
python -m rasa_sdk --actions actions --port 5055 &

# Run Rasa in the foreground.
exec rasa run \
  --enable-api \
  --cors "*" \
  --port 5005 \
  --credentials credentials.yml \
  --endpoints endpoints.cloud.yml