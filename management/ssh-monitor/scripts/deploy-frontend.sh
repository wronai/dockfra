#!/bin/bash
echo "[deploy:frontend] via ssh-frontend..."
ssh ssh-frontend "curl -sf http://frontend:80/health && echo ' ✓ healthy' || echo ' ✗ down'" 2>&1 || echo "⚠ SSH failed"
