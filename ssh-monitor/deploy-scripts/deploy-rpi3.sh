#!/bin/bash
echo "[deploy:rpi3] via ssh-rpi3..."
ssh ssh-rpi3 "ls /artifacts/*.tar.gz 2>/dev/null && echo 'Artifacts ready' || echo 'No artifacts'" 2>&1 || echo "⚠ SSH failed"
