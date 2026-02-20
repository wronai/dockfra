# dockfra

Docker infrastructure setup wizard with web UI and CLI.

See full documentation at [github.com/wronai/dockfra](https://github.com/wronai/dockfra).

## Install

```bash
pip install dockfra
```

## Usage

```bash
# Start the wizard web UI
dockfra                          # → http://localhost:5050
dockfra --port 8080 --root /path/to/project

# CLI shell
dockfra-cli status
dockfra-cli health
dockfra-cli logs 50
dockfra-cli launch
```
