#!/bin/bash
TARGET="${1:-developer}"
case "$TARGET" in
    developer) echo "=== Developer ===" && ssh ssh-developer "cat /home/developer/.service-env 2>/dev/null || echo '(empty)'" ;;
    monitor)   echo "=== Monitor ===" && ssh ssh-monitor "cat /home/monitor/.service-env 2>/dev/null || echo '(empty)'" ;;
    autopilot) echo "=== Autopilot ===" && ssh ssh-autopilot "cat /home/autopilot/.service-env 2>/dev/null || echo '(empty)'" ;;
    all) for s in developer monitor autopilot; do "$0" "$s"; echo ""; done ;;
    *) echo "Usage: config-show <developer|monitor|autopilot|all>" ;;
esac
