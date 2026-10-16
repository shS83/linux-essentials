# SRVPULSE — Server Health Radar v0.1.0

One command gives an overview of **three SSH servers** and **four HTTPS sites**. The program is read-only, runs locally on Arch Linux, and uses only OpenSSH + Python 3 on the remote servers; **no remote daemon, passwords, or sudo are required**.

## Targets

| SSH alias | Server | Watched services |
| --- | --- | --- |
| `ouroboros` | Your mail / infrastructure server | `postfix`, `opendkim`, `nadar-pong.socket` |
| `lmlilja` | Lilja-Viherlampi | `nginx`, `granian` |
| `asuntokauppa` | Viherlampi / Asuntokauppa | `nginx`, `granian` |

The HTTPS targets are independent of SSH server associations:

- `https://lilja-viherlampi.fi`
- `https://asuntokauppa-turku.fi`
- `https://viherlampi.fi`
- `https://prometheus-alexander.fi`

Each HTTPS check verifies the hostname and TLS certificate via the local system trust store, reports the certificate expiration, and makes a `HEAD /` request to determine the HTTP response status. An untrusted/expired certificate or unavailable HTTPS endpoint is reported as critical; certificate expiry in ≤30 days is a warning, and ≤7 days is critical. HTTP 4xx is warning, HTTP 5xx is critical.

## Installation (Arch Linux)

Prerequisites: `python3 >= 3.11`, `ssh` and `uv` (or `pip`). The remote servers also need `python3`, `systemd`, and either `apt` or `pacman` for package counts.

```bash
sudo pacman -S --needed openssh python uv
cd srvpulse-v0.1.0
uv tool install --from . srvpulse
srvpulse --init-config
srvpulse --demo
srvpulse
```

`uv tool install` creates the `srvpulse` CLI entry point in your user tools directory (ensure `~/.local/bin` is in `$PATH`). To install over an existing version: `uv tool install --force --from . srvpulse`. Alternatively, for development:

```bash
uv sync
uv run srvpulse --demo
uv run srvpulse --details
```

Edit `~/.config/srvpulse/config.toml` to adjust services, thresholds, and targets. `srvpulse --init-config` does **not** overwrite an existing configuration. The packaged `config.example.toml` is also ready to copy.

## Commands

```bash
srvpulse                    # overview of three servers and four HTTPS domains
srvpulse --details          # OS, load, RAM, / and /data usage, services, failed units
srvpulse --server ouroboros # one SSH server, still checks all four HTTPS endpoints
srvpulse --no-https         # skip website / certificate checks
srvpulse --json             # structured output for scripts or cron
srvpulse --demo             # safe simulated presentation; no SSH or network
srvpulse --init-config      # create default config once
srvpulse --no-color         # disable terminal colors
srvpulse --version
```

Exit codes: `0` for completed checks without critical findings; `1` for one or more critical/down findings; `2` for invalid configuration/arguments. Warnings alone do not make exit code `1`.

## What is measured?

- **Host uptime**: `/proc/uptime`; **load average**: `/proc/loadavg`.
- **Memory**: `MemTotal - MemAvailable` from `/proc/meminfo`.
- **Disk use**: mounted `/` and `/data` (if a distinct filesystem) using `shutil.disk_usage`.
- **Failed systemd units**: `systemctl list-units --failed`.
- **Watched services**: `systemctl is-active`, configured individually for each server.
- **Available updates**: `apt list --upgradable` or `pacman -Qu` **using existing indexes only**. Counts may be stale. The script intentionally never runs `apt update` or `pacman -Sy`, does not install anything, and does not alter services.
- **HTTPS/TLS**: fresh, verified connections from the local machine, not checks on the server's local certificate store.

**Security:** SSH follows your existing `~/.ssh/config` aliases and host-key checking; it uses `BatchMode=yes` so it never hangs prompting for a password. Configure working SSH keys and try `ssh ouroboros true`, `ssh lmlilja true`, `ssh asuntokauppa true` first. The SSH command executes a fixed, read-only Python probe via standard input. It never requests root access. The program never disables host key or TLS certificate verification.

**Interpretation:** HTTPS can work even if SSH is unavailable, and SSH can work while HTTPS is down. That is why HTTPS sites have their own table, separate from the server health table. `HTTP 200` and valid TLS report the public-facing status at the moment of inspection, but they do not guarantee the entire website or mail stack is healthy.

## Tests

```bash
uv run python -m unittest discover -s tests -v
uv run srvpulse --demo
```

The unit tests do not connect to any real server or website.
