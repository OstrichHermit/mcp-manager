"""Kill all MCP Manager related Python processes.

Usage:
    python kill_processes.py                # kill all
    python kill_processes.py X Y ...        # skip processes matching X, Y, ...
"""
import subprocess
import sys


def main():
    excludes = sys.argv[1:]

    result = subprocess.run(
        ["wmic", "process", "where",
         "name='python.exe' or name='pythonw.exe'",
         "get", "processid,commandline", "/format:csv"],
        capture_output=True, text=True
    )

    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if "mcp-manager" not in line:
            continue
        if any(exc in line for exc in excludes):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[2].isdigit():
            pid = int(parts[2])
            try:
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(pid)],
                    capture_output=True
                )
            except Exception:
                pass


if __name__ == "__main__":
    main()
