#!/bin/sh
set -e

python -m rasa_sdk --actions actions --port 5055 &

rasa run \
  --enable-api \
  --cors "*" \
  --port 5005 \
  --credentials credentials.yml \
  --endpoints endpoints.cloud.yml &

python cloud_server.py
