"""SRVPULSE: agentless SSH diagnostics and independently checked HTTPS sites."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import http.client
import json
import os
from pathlib import Path
import re
import shlex
import socket
import ssl
import subprocess
import sys
import tomllib

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .remote import REMOTE_SCRIPT

DEFAULT_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "srvpulse" / "config.toml"
EXAMPLE = Path(__file__).resolve().parents[2] / "config.example.toml"
CONFIG_TEMPLATE = '''# SRVPULSE — user configuration
[settings]
ssh_timeout = 45
https_timeout = 6
certificate_warn_days = 30
disk_warn_pct = 80
disk_critical_pct = 90
memory_warn_pct = 90

[servers.ouroboros]
ssh = "ouroboros"
services = ["postfix", "opendkim", "nadar-pong.socket"]

[servers.lmlilja]
ssh = "lmlilja"
services = ["nginx", "granian"]

[servers.asuntokauppa]
ssh = "asuntokauppa"
services = ["nginx", "granian"]

[https]
domains = ["lilja-viherlampi.fi", "asuntokauppa-turku.fi", "viherlampi.fi", "prometheus-alexander.fi"]
'''

NAME_RE = re.compile(r"^[A-Za-z0-9_.@:-]+$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")

@dataclass(frozen=True)
class Settings:
    ssh_timeout: int = 45
    https_timeout: int = 6
    certificate_warn_days: int = 30
    disk_warn_pct: int = 80
    disk_critical_pct: int = 90
    memory_warn_pct: int = 90

@dataclass(frozen=True)
class Server:
    name: str
    ssh: str
    services: tuple[str, ...]

@dataclass
class ServerResult:
    server: Server
    info: dict = field(default_factory=dict)
    error: str | None = None
    state: str = "UNKNOWN"
    alerts: list[str] = field(default_factory=list)

@dataclass
class HTTPSResult:
    domain: str
    verified: bool = False
    http_status: int | None = None
    expires: str | None = None
    days_left: int | None = None
    error: str | None = None
    state: str = "UNKNOWN"


def read_config(path: Path) -> tuple[Settings, list[Server], list[str]]:
    with path.open("rb") as fp:
        doc = tomllib.load(fp)
    raw_settings = doc.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise ValueError("[settings] must be a table")
    limits = {"ssh_timeout": (5, 180), "https_timeout": (1, 30),
              "certificate_warn_days": (1, 365), "disk_warn_pct": (1, 99),
              "disk_critical_pct": (1, 100), "memory_warn_pct": (1, 100)}
    kw = {}
    for key, (low, high) in limits.items():
        value = raw_settings.get(key, getattr(Settings(), key))
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"settings.{key} must be an integer in {low}..{high}")
        kw[key] = value
    settings = Settings(**kw)
    if settings.disk_critical_pct <= settings.disk_warn_pct:
        raise ValueError("disk_critical_pct must exceed disk_warn_pct")
    sections = doc.get("servers", {})
    if not isinstance(sections, dict) or not sections:
        raise ValueError("at least one [servers.NAME] entry is required")
    if len(sections) > 30:
        raise ValueError("maximum 30 configured servers")
    servers = []
    for name, raw in sections.items():
        if not isinstance(raw, dict) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,50}", name):
            raise ValueError("invalid server name")
        alias = raw.get("ssh", name)
        if not isinstance(alias, str) or not NAME_RE.fullmatch(alias) or alias.startswith("-"):
            raise ValueError(f"invalid SSH alias for {name}")
        services = raw.get("services", [])
        if not isinstance(services, list) or len(services) > 30 or any(
            not isinstance(x, str) or not NAME_RE.fullmatch(x) or x.startswith("-") for x in services
        ):
            raise ValueError(f"invalid service names in {name}")
        servers.append(Server(name, alias, tuple(services)))
    https = doc.get("https", {})
    if not isinstance(https, dict):
        raise ValueError("[https] must be a table")
    domains = https.get("domains", [])
    if not isinstance(domains, list) or len(domains) > 80 or any(
        not isinstance(x, str) or not DOMAIN_RE.fullmatch(x) for x in domains
    ):
        raise ValueError("https.domains must contain valid domain names")
    if len(set(domains)) != len(domains):
        raise ValueError("duplicate entries in https.domains")
    return settings, servers, domains


def probe_ssh(server: Server, settings: Settings) -> ServerResult:
    result = ServerResult(server)
    # The only remote command is a standard-library-only, read-only Python probe.
    services_json = json.dumps(server.services)
    remote_cmd = f"SRVPULSE_SERVICES={shlex.quote(services_json)} python3 -"
    cmd = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=7",
           "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=2",
           server.ssh, remote_cmd]
    try:
        proc = subprocess.run(cmd, input=REMOTE_SCRIPT, text=True,
                              capture_output=True, timeout=settings.ssh_timeout)
    except FileNotFoundError:
        result.error = "OpenSSH client is missing"
        return result
    except subprocess.TimeoutExpired:
        result.error = f"SSH timeout ({settings.ssh_timeout}s)"
        return result
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()
        result.error = (detail[-1] if detail else f"SSH exited {proc.returncode}")[:180]
        return result
    try:
        parsed = json.loads(proc.stdout.strip())
        if not isinstance(parsed, dict) or not isinstance(parsed.get("memory"), dict) or not isinstance(parsed.get("disks"), list):
            raise ValueError("missing mandatory fields")
        result.info = parsed
    except (ValueError, TypeError):
        result.error = "Invalid remote JSON; verify python3 is installed"
    return result


def probe_https(domain: str, settings: Settings) -> HTTPSResult:
    """TLS verification including hostname, certificate expiry, and HTTP response."""
    result = HTTPSResult(domain)
    conn = http.client.HTTPSConnection(domain, port=443, timeout=settings.https_timeout,
                                       context=ssl.create_default_context())
    try:
        # HTTPS HEAD proves that HTTP is actually served, not merely TLS handshaking.
        conn.connect()
        assert conn.sock is not None
        certificate = conn.sock.getpeercert()
        if not certificate or not certificate.get("notAfter"):
            raise ValueError("certificate expiry unavailable")
        expiry = datetime.strptime(certificate["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        result.expires = expiry.isoformat()
        result.days_left = int((expiry - datetime.now(timezone.utc)).total_seconds() // 86400)
        result.verified = True
        conn.request("HEAD", "/", headers={"Host": domain, "User-Agent": f"srvpulse/{__version__}", "Connection": "close"})
        response = conn.getresponse()
        result.http_status = response.status
    except (OSError, ssl.SSLError, ValueError, http.client.HTTPException) as exc:
        result.error = f"{type(exc).__name__}: {str(exc)[:155]}"
    finally:
        conn.close()
    return evaluate_https(result, settings)


def pct(used: int | float, total: int | float) -> float:
    return 100 * used / total if total else 0


def evaluate_server(res: ServerResult, settings: Settings) -> ServerResult:
    if res.error:
        res.state = "DOWN"
        res.alerts = [f"SSH: {res.error}"]
        return res
    info, alerts, critical = res.info, [], False
    for disk in info.get("disks", []):
        used_pct = pct(disk.get("used", 0), disk.get("total", 0))
        if used_pct >= settings.disk_critical_pct:
            alerts.append(f"Disk {disk.get('mount','?')}: {used_pct:.0f}% used")
            critical = True
        elif used_pct >= settings.disk_warn_pct:
            alerts.append(f"Disk {disk.get('mount','?')}: {used_pct:.0f}% used")
    mem = info.get("memory", {})
    if pct(mem.get("used", 0), mem.get("total", 0)) >= settings.memory_warn_pct:
        alerts.append(f"Memory: {pct(mem.get('used', 0), mem.get('total', 0)):.0f}% used")
    failed = info.get("failed_units")
    if failed is None:
        alerts.append("Failed systemd units could not be queried")
    elif failed:
        alerts.append(f"Failed systemd units: {', '.join(failed[:5])}")
        critical = True
    for name, state in info.get("services", {}).items():
        if state != "active":
            alerts.append(f"Service {name}: {state}")
            critical = True
    updates = info.get("updates", {}).get("count")
    if isinstance(updates, int) and updates > 0:
        alerts.append(f"{updates} available package upgrades (cached lists)")
    if updates is None:
        alerts.append("Package update count unavailable")
    res.alerts = alerts
    res.state = "CRITICAL" if critical else "WARN" if alerts else "OK"
    return res


def evaluate_https(res: HTTPSResult, settings: Settings) -> HTTPSResult:
    if not res.verified or res.error:
        res.state = "CRITICAL"
    elif res.days_left is None or res.days_left <= 7 or (res.http_status is not None and res.http_status >= 500):
        res.state = "CRITICAL"
    elif res.days_left <= settings.certificate_warn_days or (res.http_status is not None and res.http_status >= 400):
        res.state = "WARN"
    else:
        res.state = "OK"
    return res


def collect(servers: list[Server], domains: list[str], settings: Settings) -> tuple[list[ServerResult], list[HTTPSResult]]:
    sr = {s.name: ServerResult(s) for s in servers}
    hr = {d: HTTPSResult(d) for d in domains}
    with ThreadPoolExecutor(max_workers=min(16, max(1, len(servers) + len(domains)))) as pool:
        tasks = {pool.submit(probe_ssh, s, settings): ("ssh", s.name) for s in servers}
        tasks.update({pool.submit(probe_https, d, settings): ("https", d) for d in domains})
        for future in as_completed(tasks):
            kind, key = tasks[future]
            try:
                result = future.result()
            except Exception as exc:
                if kind == "ssh":
                    result = ServerResult(sr[key].server, error=f"Unexpected probe failure: {type(exc).__name__}")
                else:
                    result = HTTPSResult(key, error=f"Unexpected HTTPS failure: {type(exc).__name__}", state="CRITICAL")
            if kind == "ssh":
                sr[key] = evaluate_server(result, settings)
            else:
                hr[key] = result
    return list(sr.values()), list(hr.values())


def fmt_bytes(value: int) -> str:
    n = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if n < 1024 or unit == "PiB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PiB"


def fmt_uptime(seconds: int) -> str:
    days, rem = divmod(int(seconds), 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    return f"{days}d {hours}h" if days else f"{hours}h {minutes}m"


def style(state: str) -> str:
    return {"OK": "bold bright_green", "WARN": "bold yellow", "CRITICAL": "bold red", "DOWN": "bold red"}.get(state, "dim")


def style_pct(value: float, settings: Settings) -> str:
    if value >= settings.disk_critical_pct:
        return "bold red"
    if value >= settings.disk_warn_pct:
        return "bold yellow"
    return "bright_cyan"


def display(servers: list[ServerResult], https: list[HTTPSResult], settings: Settings, console: Console,
            *, details: bool = False, demo: bool = False) -> None:
    title = Text()
    title.append("◈  ", style="bright_cyan")
    title.append("SRVPULSE", style="bold #b69cff")
    title.append("  /  SERVER HEALTH RADAR", style="bold white")
    title.append(f"  v{__version__}", style="dim")
    console.print(Panel(title, border_style="#755ac2", box=box.ROUNDED,
                        subtitle="DEMO DATA • NOT LIVE" if demo else "SSH • SYSTEMD • HTTPS • READ ONLY"))

    summary = Table(title="◈  SERVER TELEMETRY", title_style="bold #beaaff", box=box.SIMPLE_HEAVY,
                    expand=True, show_edge=False, header_style="bold #b8a8df")
    for col in ("SERVER", "STATUS", "UPTIME", "LOAD", "MEM", "ROOT", "UPDATES", "FAILED"):
        summary.add_column(col, no_wrap=True, justify="right" if col in ("MEM", "ROOT", "UPDATES", "FAILED") else "left")
    for res in servers:
        info = res.info
        memory = info.get("memory", {})
        mem_used = pct(memory.get("used", 0), memory.get("total", 0))
        root = next((d for d in info.get("disks", []) if d.get("mount") == "/"), None)
        disk_used = pct(root["used"], root["total"]) if root else 0
        load = info.get("load", [])
        updates = info.get("updates", {}).get("count")
        failed = info.get("failed_units")
        summary.add_row(Text(res.server.name, style="bold white"), Text(res.state, style=style(res.state)),
                        fmt_uptime(info.get("uptime_seconds", 0)) if info else "—",
                        f"{load[0]:.2f}" if load else "—",
                        Text(f"{mem_used:.0f}%", style=style_pct(mem_used, settings)) if info else "—",
                        Text(f"{disk_used:.0f}%", style=style_pct(disk_used, settings)) if root else "—",
                        str(updates) if updates is not None else "—",
                        str(len(failed)) if failed is not None else "—")
    console.print(summary)

    sites = Table(title="◈  HTTPS / TLS CERTIFICATES", title_style="bold #beaaff", box=box.SIMPLE_HEAVY,
                  expand=True, show_edge=False, header_style="bold #b8a8df")
    sites.add_column("DOMAIN", style="bright_cyan")
    sites.add_column("STATUS", no_wrap=True)
    sites.add_column("HTTP", justify="right")
    sites.add_column("CERT EXPIRES", justify="right")
    sites.add_column("DAYS LEFT", justify="right")
    for res in https:
        sites.add_row(res.domain, Text(res.state, style=style(res.state)),
                      str(res.http_status) if res.http_status is not None else "—",
                      res.expires[:10] if res.expires else "—",
                      Text(str(res.days_left) if res.days_left is not None else "—", style=style(res.state)))
    if https:
        console.print(sites)

    alerts = [(f"SSH {res.server.name}", issue) for res in servers for issue in res.alerts]
    for res in https:
        if res.state != "OK":
            detail = res.error or (f"Certificate expires in {res.days_left} day(s)" if res.days_left is not None and res.days_left <= settings.certificate_warn_days else f"HTTP status {res.http_status}")
            alerts.append((f"HTTPS {res.domain}", detail))
    if alerts:
        issues = Table.grid(padding=(0, 2))
        issues.add_column(style="bold #bda3ff", no_wrap=True)
        issues.add_column()
        for origin, item in alerts:
            issues.add_row(origin, item)
        console.print(Panel(issues, title="◈ ATTENTION", border_style="yellow"))
    else:
        console.print("[bold bright_green]✓ All selected checks passed.[/]")

    if details:
        for res in servers:
            lines = Table.grid(padding=(0, 2))
            lines.add_column(style="bold #b8a7ff")
            lines.add_column()
            if res.error:
                lines.add_row("SSH", Text(res.error, style="bold red"))
            else:
                info = res.info
                lines.add_row("Hostname", info.get("hostname", "—"))
                lines.add_row("OS", info.get("os", "—"))
                lines.add_row("Load 1/5/15", " / ".join(f"{x:.2f}" for x in info.get("load", [])))
                lines.add_row("CPU threads", str(info.get("cpus", "—")))
                memory = info.get("memory", {})
                lines.add_row("Memory", f"{fmt_bytes(memory.get('used', 0))} / {fmt_bytes(memory.get('total', 0))}")
                for disk in info.get("disks", []):
                    lines.add_row(f"Disk {disk.get('mount')}", f"{fmt_bytes(disk['used'])} / {fmt_bytes(disk['total'])} ({pct(disk['used'], disk['total']):.1f}%)")
                updates = info.get("updates", {})
                lines.add_row("Available upgrades", f"{updates.get('count') if updates.get('count') is not None else 'unavailable'} ({updates.get('manager', '?')}; cached lists)")
                failed = info.get("failed_units")
                lines.add_row("Failed units", ", ".join(failed) if failed else "none" if failed == [] else "unavailable")
                for name, state in info.get("services", {}).items():
                    lines.add_row(f"Service {name}", Text(state, style="bright_green" if state == "active" else "bold red"))
            console.print(Panel(lines, title=f"◈ {res.server.name}  /  {res.state}", border_style=style(res.state)))
    console.print("[dim]Update counts are from already cached APT/pacman metadata (no refresh). HTTPS is checked from this workstation.[/]")


def demo_data(settings: Settings) -> tuple[list[ServerResult], list[HTTPSResult]]:
    fixtures = [
        (Server("ouroboros", "ouroboros", ("postfix", "opendkim", "nadar-pong.socket")), 25, 40, 1, {"postfix": "active", "opendkim": "active", "nadar-pong.socket": "active"}, []),
        (Server("lmlilja", "lmlilja", ("nginx", "granian")), 9, 62, 12, {"nginx": "active", "granian": "active"}, []),
        (Server("asuntokauppa", "asuntokauppa", ("nginx", "granian")), 40, 85, 3, {"nginx": "active", "granian": "failed"}, ["granian.service"]),
    ]
    servers = []
    for s, days, disk, upgrades, services, failed in fixtures:
        res = ServerResult(s, info={"hostname": s.name, "os": "Debian/Ubuntu (demo)",
            "uptime_seconds": days * 86400 + 7500, "load": [0.18, 0.45, 0.67], "cpus": 4,
            "memory": {"total": 8 * 1024**3, "used": 3 * 1024**3},
            "disks": [{"mount": "/", "total": 100 * 1024**3, "used": disk * 1024**3, "free": (100 - disk) * 1024**3}],
            "failed_units": failed, "services": services, "updates": {"manager": "apt", "count": upgrades}})
        servers.append(evaluate_server(res, settings))
    fake_cert_days = [65, 27, 10, 73]
    domains = ["lilja-viherlampi.fi", "asuntokauppa-turku.fi", "viherlampi.fi", "prometheus-alexander.fi"]
    https = [evaluate_https(HTTPSResult(d, verified=True, http_status=200, expires="2027-01-01T00:00:00+00:00", days_left=days), settings)
             for d, days in zip(domains, fake_cert_days)]
    return servers, https


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SRVPULSE — agentless SSH server and HTTPS health radar")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Configuration TOML path")
    parser.add_argument("--init-config", action="store_true", help="Create config template if it does not exist")
    parser.add_argument("--server", action="append", metavar="NAME", help="Select SSH server; HTTPS checks remain enabled (repeatable)")
    parser.add_argument("--no-https", action="store_true", help="Skip HTTPS probes")
    parser.add_argument("--details", action="store_true", help="Display per-server service, disk and OS details")
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument("--demo", action="store_true", help="Use simulated data without network connections")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI styling")
    parser.add_argument("--version", action="version", version=f"SRVPULSE v{__version__}")
    args = parser.parse_args(argv)
    console = Console(color_system=None if args.no_color else "auto", no_color=args.no_color)
    if args.init_config:
        args.config.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.config.open("x", encoding="utf-8") as stream:
                stream.write(CONFIG_TEMPLATE)
        except FileExistsError:
            console.print(f"[yellow]Existing configuration left unchanged:[/] {args.config}")
            return 1
        console.print(f"[green]Created configuration:[/] {args.config}")
        return 0
    if args.demo:
        settings = Settings()
        servers, https = demo_data(settings)
    else:
        try:
            settings, targets, domains = read_config(args.config)
        except (ValueError, OSError, tomllib.TOMLDecodeError) as exc:
            console.print(f"[bold red]Configuration error:[/] {exc}\nRun: srvpulse --init-config")
            return 2
        if args.server:
            unknown = set(args.server) - {x.name for x in targets}
            if unknown:
                console.print(f"[red]Unknown SSH server(s): {', '.join(sorted(unknown))}[/]")
                return 2
            targets = [x for x in targets if x.name in args.server]
        if args.no_https:
            domains = []
        if args.json:
            servers, https = collect(targets, domains, settings)
        else:
            with console.status("[bold #b69cff]◈ Checking servers and HTTPS endpoints...", spinner="dots"):
                servers, https = collect(targets, domains, settings)
    if args.demo and args.server:
        unknown = set(args.server) - {x.server.name for x in servers}
        if unknown:
            console.print(f"[red]Unknown SSH server(s): {', '.join(sorted(unknown))}[/]")
            return 2
        servers = [r for r in servers if r.server.name in args.server]
    if args.no_https:
        https = []
    if args.json:
        print(json.dumps({"version": __version__, "demo": args.demo,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "servers": [{"name": r.server.name, "ssh": r.server.ssh, "state": r.state,
                         "info": r.info, "error": r.error, "alerts": r.alerts} for r in servers],
            "https": [asdict(r) for r in https]}, indent=2))
    else:
        display(servers, https, settings, console, details=args.details, demo=args.demo)
    return int(any(r.state in ("CRITICAL", "DOWN") for r in servers) or any(r.state == "CRITICAL" for r in https))

if __name__ == "__main__":
    sys.exit(main())
