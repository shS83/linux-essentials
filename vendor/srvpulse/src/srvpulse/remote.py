"""Read-only probe executed over SSH; Python standard library only.

The probe is sent to `python3 -` on the target. It never installs or writes
files and does not require sudo. Update counts use *existing* package indexes.
"""

REMOTE_SCRIPT = r'''
import json
import os
import platform
import re
import shutil
import socket
import subprocess


def run(args, timeout=8):
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "LC_ALL": "C"})
        return p.returncode, p.stdout, p.stderr
    except (OSError, subprocess.TimeoutExpired):
        return -1, "", ""


def read_os():
    try:
        values = {}
        with open("/etc/os-release", encoding="utf-8") as fp:
            for line in fp:
                if "=" in line and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    values[key] = value.strip('"')
        return values.get("PRETTY_NAME") or values.get("NAME") or "Linux"
    except OSError:
        return "Linux"


def meminfo():
    numbers = {}
    with open("/proc/meminfo", encoding="ascii") as fp:
        for line in fp:
            parts = line.split()
            if len(parts) >= 2 and parts[1].isdigit():
                numbers[parts[0][:-1]] = int(parts[1]) * 1024
    total = numbers.get("MemTotal", 0)
    available = numbers.get("MemAvailable", numbers.get("MemFree", 0))
    return {"total": total, "used": max(0, total-available)}


def disks():
    results = []
    root_device = None
    for path in ("/", "/data"):
        if not os.path.isdir(path):
            continue
        try:
            device = os.stat(path).st_dev
            if path != "/" and device == root_device:
                continue
            if path == "/":
                root_device = device
            usage = shutil.disk_usage(path)
            results.append({"mount": path, "total": usage.total,
                            "used": usage.used, "free": usage.free})
        except OSError:
            pass
    return results


def failed_units():
    code, out, _ = run(["systemctl", "list-units", "--failed", "--all",
                        "--no-legend", "--plain", "--no-pager"])
    if code != 0:
        return None
    names = []
    for line in out.splitlines():
        words = line.lstrip("● ").split()
        if words and "." in words[0]:
            names.append(words[0])
    return sorted(set(names))


def updates():
    if shutil.which("apt"):
        code, out, _ = run(["apt", "list", "--upgradable"], timeout=16)
        if code == 0:
            return {"manager": "apt", "count": sum(
                1 for x in out.splitlines() if "/" in x and not x.startswith("Listing"))}
        return {"manager": "apt", "count": None}
    if shutil.which("pacman"):
        code, out, _ = run(["pacman", "-Qu"], timeout=16)
        return {"manager": "pacman", "count": len(out.splitlines()) if code == 0 else None}
    return {"manager": "unknown", "count": None}


def service_states(names):
    result = {}
    for name in names:
        if not re.fullmatch(r"[A-Za-z0-9_.@:-]+", name) or name.startswith("-"):
            result[name] = "invalid"
            continue
        code, out, _ = run(["systemctl", "is-active", "--", name], timeout=5)
        state = out.strip().splitlines()[0] if out.strip() else "unknown"
        result[name] = state
    return result


def main():
    service_names = []
    try:
        raw = os.environ.get("SRVPULSE_SERVICES", "[]")
        parsed = json.loads(raw)
        if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
            service_names = parsed[:25]
    except (ValueError, TypeError):
        pass
    with open("/proc/uptime", encoding="ascii") as fp:
        uptime = int(float(fp.read().split()[0]))
    with open("/proc/loadavg", encoding="ascii") as fp:
        load = [float(x) for x in fp.read().split()[:3]]
    print(json.dumps({
        "hostname": socket.gethostname(),
        "os": read_os(),
        "uptime_seconds": uptime,
        "load": load,
        "cpus": os.cpu_count() or 1,
        "memory": meminfo(),
        "disks": disks(),
        "failed_units": failed_units(),
        "updates": updates(),
        "services": service_states(service_names),
    }, separators=(",", ":")))


if __name__ == "__main__":
    main()
'''
