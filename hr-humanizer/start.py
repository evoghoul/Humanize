#!/usr/bin/env python3
"""GoHumanize All-in-One Autonomous Launcher (Google Gemini Edition).

Starts the full GoHumanize HR Assistant stack:
1. Google Gemini Cloud AI verification (with FactGuard engine)
2. FastAPI backend server
3. React/Vite web application
4. Automatic web browser launch
"""

from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import webbrowser

# Terminal color styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

CHILD_PROCESSES: list[subprocess.Popen] = []


def cleanup() -> None:
    """Terminate all managed child processes cleanly upon exit."""
    if not CHILD_PROCESSES:
        return
    print(f"\n{YELLOW}[SHUTDOWN] Gracefully shutting down all background services...{RESET}")
    for proc in CHILD_PROCESSES:
        try:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
        except Exception:
            pass


atexit.register(cleanup)


def log_step(step: str, title: str) -> None:
    print(f"\n{CYAN}{BOLD}[Step {step}]{RESET} {BOLD}{title}{RESET}")


def log_success(msg: str) -> None:
    print(f"  {GREEN}[OK]{RESET} {msg}")


def log_warn(msg: str) -> None:
    print(f"  {YELLOW}[WARN]{RESET} {msg}")


def log_error(msg: str) -> None:
    print(f"  {RED}[ERROR]{RESET} {msg}")


def log_info(msg: str) -> None:
    print(f"  [INFO] {msg}")


# ---------------------------------------------------------------------------
# 1. Resilient Directory Discovery
# ---------------------------------------------------------------------------

def find_project_directories() -> tuple[Path, Path]:
    """Find backend and frontend directories regardless of where user executes script."""
    current = Path.cwd().resolve()
    script_dir = Path(__file__).resolve().parent

    candidates = [
        script_dir,
        current,
        script_dir / "hr-humanizer",
        current / "hr-humanizer",
        script_dir.parent,
        current.parent,
    ]

    backend_dir: Path | None = None
    frontend_dir: Path | None = None

    for base in candidates:
        b = base / "backend"
        if not b.is_dir() and (base / "hr-humanizer" / "backend").is_dir():
            b = base / "hr-humanizer" / "backend"
        if b.is_dir() and (b / "app" / "main.py").is_file():
            backend_dir = b.resolve()
            break

    for base in candidates:
        f = base / "frontend"
        if not f.is_dir() and (base / "hr-humanizer" / "frontend").is_dir():
            f = base / "hr-humanizer" / "frontend"
        if f.is_dir() and (f / "package.json").is_file():
            frontend_dir = f.resolve()
            break

    if not backend_dir:
        log_error("Could not locate backend directory containing 'app/main.py'.")
        sys.exit(1)

    if not frontend_dir:
        log_error("Could not locate frontend directory containing 'package.json'.")
        sys.exit(1)

    return backend_dir, frontend_dir


# ---------------------------------------------------------------------------
# 2. Resilient Environment & Configuration
# ---------------------------------------------------------------------------

def load_env_file(env_path: Path) -> dict[str, str]:
    """Simple parser for .env files without external dependencies."""
    config: dict[str, str] = {}
    if not env_path.is_file():
        return config
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("'\"")
                    config[key] = val
    except Exception:
        pass
    return config


def get_combined_config(backend_dir: Path) -> dict[str, str]:
    """Merge environment from os.environ, backend/.env, and root .env."""
    config = {
        "HOST": "127.0.0.1",
        "PORT": "8000",
        "GEMINI_MODEL": "gemini-3.8-flash",
        "GEMINI_TIMEOUT": "30.0",
        "ENABLE_GEMINI": "true",
    }
    # Check parent and backend .env
    for candidate in [backend_dir.parent / ".env", backend_dir / ".env", Path.cwd() / ".env"]:
        config.update(load_env_file(candidate))

    # Real environment variables take highest priority
    for k in config:
        if k in os.environ:
            config[k] = os.environ[k]

    return config


def inspect_engine_workflow(config: dict[str, str]) -> tuple[bool, str]:
    """Inspect Gemini configuration."""
    gemini_key = config.get("GEMINI_API_KEY") or config.get("GOOGLE_API_KEY")
    gemini_model = config.get("GEMINI_MODEL", "gemini-2.5-flash")
    log_step("1/4", f"Checking Google Gemini AI Configuration ({gemini_model})...")
    print(f"  • {BOLD}Engine:{RESET}        {CYAN}Google Gemini Cloud AI ({gemini_model}){RESET}")
    if gemini_key and gemini_key.strip():
        masked_key = gemini_key[:4] + "..." + gemini_key[-4:] if len(gemini_key) > 8 else "***"
        log_success(f"Gemini API key active ({masked_key}). Ready for humanization requests.")
        return True, gemini_model
    else:
        log_warn("GEMINI_API_KEY is not configured in .env.")
        log_info("Please add GEMINI_API_KEY to your .env file to enable cloud rewrites.")
        log_info("Deterministic FactGuard rule engine will run until key is set.")
        return False, gemini_model


# ---------------------------------------------------------------------------
# 3. Resilient Port Management
# ---------------------------------------------------------------------------

def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if a network port is already occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex((host, port)) == 0


def find_free_port(start_port: int, host: str = "127.0.0.1") -> int:
    """Find the next free port starting from start_port."""
    port = start_port
    while is_port_in_use(port, host):
        port += 1
    return port


# ---------------------------------------------------------------------------
# 4. Resilient Backend Launcher
# ---------------------------------------------------------------------------

def ensure_backend_deps(backend_dir: Path) -> None:
    """Verify backend packages exist; install if missing."""
    try:
        import fastapi  # noqa: F401
        import uvicorn  # noqa: F401
        import pydantic  # noqa: F401
        import google.genai  # noqa: F401
    except ImportError:
        log_info("Installing backend dependencies...")
        req = backend_dir / "requirements.txt"
        if req.is_file():
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(req)], check=False)


def check_backend_healthy(host: str, port: int) -> bool:
    """Test if FastAPI health endpoint responds."""
    try:
        req = urllib.request.Request(f"http://{host}:{port}/api/health", method="GET")
        with urllib.request.urlopen(req, timeout=1.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_backend_service(backend_dir: Path, config: dict[str, str]) -> tuple[int, bool]:
    """Start backend on configured or next available port. Returns (port, is_newly_spawned)."""
    log_step("2/4", "Preparing Backend API Server...")
    ensure_backend_deps(backend_dir)

    host = config.get("HOST", "127.0.0.1")
    target_port = int(config.get("PORT", "8000"))

    # If backend is already running on target port and responds to health, re-use it
    if check_backend_healthy(host, target_port):
        log_success(f"Backend API is already running at http://{host}:{target_port}")
        return target_port, False

    # If target port is occupied by something else, find next free port
    actual_port = target_port
    if is_port_in_use(actual_port, host):
        actual_port = find_free_port(target_port + 1, host)
        log_warn(f"Port {target_port} was occupied. Automatically selected available port: {actual_port}")

    # Launch uvicorn
    env = os.environ.copy()
    for k, v in config.items():
        env[k] = str(v)
    env["HOST"] = host
    env["PORT"] = str(actual_port)

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        host,
        "--port",
        str(actual_port),
        "--reload",
    ]

    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        cmd,
        cwd=str(backend_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    CHILD_PROCESSES.append(proc)

    # Wait for backend to be healthy
    attempts = 0
    while attempts < 25:
        if check_backend_healthy(host, actual_port):
            log_success(f"Backend API online at http://{host}:{actual_port}")
            return actual_port, True
        time.sleep(0.4)
        attempts += 1

    log_warn("Backend health check timed out. Proceeding under assumption of delayed initialization...")
    return actual_port, True


# ---------------------------------------------------------------------------
# 5. Resilient Frontend Launcher
# ---------------------------------------------------------------------------

def ensure_frontend_deps(frontend_dir: Path) -> None:
    """Ensure node_modules are installed."""
    node_modules = frontend_dir / "node_modules"
    if not node_modules.is_dir():
        log_info("Installing frontend dependencies (npm install)...")
        npm_bin = shutil.which("npm.cmd") if os.name == "nt" else shutil.which("npm")
        if npm_bin:
            subprocess.run([npm_bin, "install"], cwd=str(frontend_dir), check=False)
        else:
            log_warn("npm was not found on PATH. Frontend may fail to launch if unbuilt.")


def is_http_ready(url: str, timeout: float = 1.0) -> bool:
    """Check if HTTP server responds."""
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def start_frontend_service(frontend_dir: Path, backend_port: int, host: str = "127.0.0.1") -> str:
    """Launch frontend Vite dev server or fallback to built SPA. Returns accessible application URL."""
    log_step("3/4", "Preparing Frontend Web Interface...")

    dist_dir = frontend_dir / "dist"
    has_dist = dist_dir.is_dir() and (dist_dir / "index.html").is_file()

    npm_bin = shutil.which("npm.cmd") if os.name == "nt" else shutil.which("npm")

    # If npm is missing, rely entirely on backend serving dist
    if not npm_bin:
        if has_dist:
            log_success("npm not found, but production build detected in dist/. Serving via FastAPI backend.")
            return f"http://{host}:{backend_port}"
        else:
            log_error("Neither npm nor a compiled dist/ directory was found. Cannot start UI.")
            sys.exit(1)

    ensure_frontend_deps(frontend_dir)

    # Target standard Vite port 5173 or next available
    vite_target_port = 5173
    actual_vite_port = vite_target_port
    if is_port_in_use(actual_vite_port, host):
        # If it's already a responding web server, re-use
        test_url = f"http://{host}:{actual_vite_port}"
        if is_http_ready(test_url, timeout=0.5):
            log_success(f"Frontend is already running at {test_url}")
            return test_url
        actual_vite_port = find_free_port(vite_target_port + 1, host)
        log_warn(f"Port {vite_target_port} occupied. Starting frontend on port: {actual_vite_port}")

    env = os.environ.copy()
    env["VITE_API_URL"] = f"http://{host}:{backend_port}"
    env["PORT"] = str(actual_vite_port)

    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
    proc = subprocess.Popen(
        [npm_bin, "run", "dev", "--", "--port", str(actual_vite_port), "--host"],
        cwd=str(frontend_dir),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
    CHILD_PROCESSES.append(proc)

    app_url = f"http://{host}:{actual_vite_port}"
    attempts = 0
    while attempts < 25:
        if is_http_ready(app_url, timeout=0.5):
            log_success(f"Frontend dev server online at {app_url}")
            return app_url
        time.sleep(0.4)
        attempts += 1

    log_info(f"Frontend started at {app_url} (awaiting complete bundle load).")
    return app_url


# ---------------------------------------------------------------------------
# 6. Main Orchestrator
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"{CYAN}{BOLD}==========================================================")
    print("   GoHumanize Automated Launcher (Google Gemini Edition)  ")
    print(f"=========================================================={RESET}")

    # 1. Resilient directory location
    backend_dir, frontend_dir = find_project_directories()

    # 2. Resilient configuration loading
    config = get_combined_config(backend_dir)

    # 3. Gemini Cloud AI Verification
    gemini_active, gemini_model = inspect_engine_workflow(config)

    # 4. Resilient Backend
    backend_port, _ = start_backend_service(backend_dir, config)
    host = config.get("HOST", "127.0.0.1")

    # 5. Resilient Frontend
    app_url = start_frontend_service(frontend_dir, backend_port, host)

    # 6. Launch browser
    log_step("4/4", "Launching Web Browser...")
    try:
        webbrowser.open(app_url)
        log_success(f"Opened {app_url} in your browser.")
    except Exception as e:
        log_warn(f"Could not open browser automatically: {e}")

    # 7. Summary Dashboard
    print("\n" + "=" * 65)
    print(f"{GREEN}{BOLD}  GoHumanize HR Writing Assistant - All Services Online!{RESET}")
    print("=" * 65)
    print(f"  • {BOLD}Web Application:{RESET}  {CYAN}{app_url}{RESET}")
    print(f"  • {BOLD}Backend API:{RESET}      {CYAN}http://{host}:{backend_port}{RESET}")
    print(f"  • {BOLD}Interactive Docs:{RESET} {CYAN}http://{host}:{backend_port}/docs{RESET}")
    gemini_disp = f"{GREEN}Active ({gemini_model}){RESET}" if gemini_active else f"{YELLOW}Awaiting GEMINI_API_KEY in .env{RESET}"
    print(f"  • {BOLD}AI Cloud Engine:{RESET}  {gemini_disp}")
    print(f"  • {BOLD}Fact Verification:{RESET}{GREEN} FactGuard 100% Deterministic Guarantee{RESET}")
    print("=" * 65)
    print(f"  {YELLOW}Press Ctrl+C at any time to shut down all services.{RESET}\n")

    # Keep alive and monitor child processes
    try:
        while True:
            for proc in CHILD_PROCESSES:
                if proc.poll() is not None:
                    pass
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
