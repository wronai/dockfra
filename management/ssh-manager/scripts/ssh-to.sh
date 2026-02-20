#!/bin/bash
case "${1:-}" in
    developer) exec ssh ssh-developer ;;
    monitor)   exec ssh ssh-monitor ;;
    autopilot) exec ssh ssh-autopilot ;;
    *) echo "Usage: ssh-to <developer|monitor|autopilot>" ;;
esac
