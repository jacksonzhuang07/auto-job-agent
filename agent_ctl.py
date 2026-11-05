import os
import sys
import time
import signal
import subprocess
import json
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PID_FILE = BASE_DIR / "agent.pid"
LOG_FILE = BASE_DIR / "agent.log"
CONFIG_FILE = BASE_DIR / "config.yaml"
DB_FILE = BASE_DIR / "applications.db"

def is_running(pid: int) -> bool:
    """Check if process with given PID is alive."""
    if sys.platform == "win32":
        try:
            cmd = f'tasklist /FI "PID eq {pid}"'
            output = subprocess.check_output(cmd, shell=True).decode()
            return str(pid) in output
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

def start():
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            if is_running(pid):
                print(f"[!] AutoJobAgent is ALREADY RUNNING (PID: {pid}).")
                print("    Use 'python agent_ctl.py status' or 'python agent_ctl.py stop'.")
                return
            else:
                PID_FILE.unlink(missing_ok=True)
        except Exception:
            PID_FILE.unlink(missing_ok=True)

    print("[*] Starting Autonomous Job Applier Agent daemon...")
    log_fp = open(LOG_FILE, "a", encoding="utf-8")

    # Start detached daemon process
    if sys.platform == "win32":
        # Windows detached creation flags
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "daemon_runner.py")],
            stdout=log_fp,
            stderr=log_fp,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True
        )
    else:
        proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "daemon_runner.py")],
            stdout=log_fp,
            stderr=log_fp,
            start_new_session=True
        )

    PID_FILE.write_text(str(proc.pid))
    print(f"[+] Agent STARTED successfully with PID: {proc.pid}")
    print(f"[+] Output logs streaming to: {LOG_FILE}")
    print("    Run 'python agent_ctl.py status' to verify health.")

def stop():
    if not PID_FILE.exists():
        print("[-] Agent is NOT running (no PID file found).")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        if is_running(pid):
            print(f"[*] Stopping agent process (PID: {pid})...")
            if sys.platform == "win32":
                subprocess.run(f"taskkill /F /PID {pid} /T", shell=True, check=False)
            else:
                os.kill(pid, signal.SIGTERM)
            print("[+] Agent STOPPED successfully.")
        else:
            print("[-] Process was not running.")
    except Exception as e:
        print(f"[!] Error stopping agent: {e}")
    finally:
        PID_FILE.unlink(missing_ok=True)

def status():
    running = False
    pid = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            running = is_running(pid)
        except Exception:
            pass

    print("=" * 50)
    print("         AUTONOMOUS JOB AGENT STATUS")
    print("=" * 50)
    print(f"State:        {'RUNNING (PID: ' + str(pid) + ')' if running else 'STOPPED'}")
    print(f"Log File:     {LOG_FILE}")

    # Query DB stats
    if DB_FILE.exists():
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM applications WHERE status = 'APPLIED'")
                total_applied = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM applications")
                total_seen = cur.fetchone()[0]
                print(f"Total Seen:   {total_seen}")
                print(f"Applied:      {total_applied}")
        except Exception as e:
            print(f"DB Error:     {e}")
    else:
        print("Database:     Not initialized yet (will be created on first run)")

    print("=" * 50)

def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() not in ["start", "stop", "status", "restart"]:
        print("Usage: python agent_ctl.py [start|stop|status|restart]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "restart":
        stop()
        time.sleep(2)
        start()
    elif cmd == "status":
        status()

if __name__ == "__main__":
    main()
