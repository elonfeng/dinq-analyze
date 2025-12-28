#!/usr/bin/env python3
"""
DINQ Service Manager

This script provides production-ready service management for the DINQ application,
supporting start, stop, restart, and status commands.

Usage:
    python dinq_service.py start   - Start the DINQ service
    python dinq_service.py stop    - Stop the DINQ service
    python dinq_service.py restart - Restart the DINQ service
    python dinq_service.py status  - Show the status of the DINQ service
"""

import os
import sys
import time
import signal
import argparse
import subprocess
import logging
import atexit
from pathlib import Path
import psutil

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/dinq_service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dinq_service")

# Configuration
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(PROJECT_ROOT, "dinq.pid")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
VENV_ACTIVATE = os.path.join(PROJECT_ROOT, ".venv", "bin", "activate")

# Default server settings
DEFAULT_HOST = "0.0.0.0"  # Listen on all interfaces in production
DEFAULT_PORT = 5001

def ensure_directories():
    """Ensure required directories exist"""
    os.makedirs(LOG_DIR, exist_ok=True)

def get_env_settings():
    """Get environment settings from .env file"""
    from dotenv import load_dotenv
    
    # Try to load .env file
    dotenv_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path)
        logger.info(f"Loaded environment settings from {dotenv_path}")
    else:
        logger.warning(f".env file not found at {dotenv_path}")
    
    # Get environment settings
    env = os.environ.get("DINQ_ENV", "production")
    host = os.environ.get("DINQ_HOST", DEFAULT_HOST)
    port = int(os.environ.get("DINQ_PORT", DEFAULT_PORT))
    
    return {
        "env": env,
        "host": host,
        "port": port
    }

def is_running():
    """Check if the service is running"""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process exists
        process = psutil.Process(pid)
        return process.is_running() and "python" in process.name().lower()
    except (ProcessLookupError, psutil.NoSuchProcess, ValueError):
        # Process doesn't exist or PID file is invalid
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return False

def get_pid():
    """Get the PID from the PID file"""
    if not os.path.exists(PID_FILE):
        return None
    
    try:
        with open(PID_FILE, 'r') as f:
            return int(f.read().strip())
    except (ValueError, IOError):
        return None

def write_pid(pid):
    """Write PID to the PID file"""
    with open(PID_FILE, 'w') as f:
        f.write(str(pid))

def remove_pid():
    """Remove the PID file"""
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)

def init_database():
    """Initialize database tables"""
    logger.info("Initializing database tables...")
    try:
        # Activate virtual environment and run initialization script
        cmd = f"source {VENV_ACTIVATE} && python tools/init_user_interactions_tables.py"
        subprocess.run(cmd, shell=True, check=True, executable="/bin/bash")
        logger.info("Database tables initialized successfully")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to initialize database tables: {e}")
        return False

def start_server(host, port):
    """Start the DINQ server"""
    if is_running():
        pid = get_pid()
        logger.info(f"DINQ service is already running (PID: {pid})")
        return False
    
    # Ensure directories exist
    ensure_directories()
    
    # Initialize database
    if not init_database():
        logger.error("Failed to initialize database. Server not started.")
        return False
    
    logger.info(f"Starting DINQ service on {host}:{port}...")
    
    try:
        # Start the server as a subprocess
        cmd = f"source {VENV_ACTIVATE} && DINQ_ENV=production python server/app.py --host={host} --port={port}"
        
        # Use nohup to keep the process running after the script exits
        process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=open(os.path.join(LOG_DIR, "dinq_stdout.log"), "a"),
            stderr=open(os.path.join(LOG_DIR, "dinq_stderr.log"), "a"),
            executable="/bin/bash",
            preexec_fn=os.setsid  # Create a new process group
        )
        
        # Write PID to file
        write_pid(process.pid)
        
        # Register cleanup function
        atexit.register(lambda: remove_pid() if process.poll() is not None else None)
        
        # Wait a moment to ensure the server starts
        time.sleep(2)
        
        # Check if the process is still running
        if process.poll() is None:
            logger.info(f"DINQ service started successfully (PID: {process.pid})")
            return True
        else:
            logger.error("DINQ service failed to start")
            remove_pid()
            return False
    
    except Exception as e:
        logger.error(f"Error starting DINQ service: {e}")
        return False

def stop_server():
    """Stop the DINQ server"""
    if not is_running():
        logger.info("DINQ service is not running")
        return True
    
    pid = get_pid()
    if not pid:
        logger.warning("PID file exists but no valid PID found")
        remove_pid()
        return True
    
    logger.info(f"Stopping DINQ service (PID: {pid})...")
    
    try:
        # Try to terminate the process group gracefully
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        
        # Wait for the process to terminate
        for _ in range(10):  # Wait up to 10 seconds
            if not is_running():
                break
            time.sleep(1)
        
        # If the process is still running, force kill it
        if is_running():
            logger.warning(f"Process {pid} did not terminate gracefully, forcing...")
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        
        # Remove PID file
        remove_pid()
        logger.info("DINQ service stopped successfully")
        return True
    
    except (ProcessLookupError, psutil.NoSuchProcess) as e:
        logger.warning(f"Process {pid} not found: {e}")
        remove_pid()
        return True
    except Exception as e:
        logger.error(f"Error stopping DINQ service: {e}")
        return False

def restart_server():
    """Restart the DINQ server"""
    logger.info("Restarting DINQ service...")
    
    # Stop the server if it's running
    stop_server()
    
    # Wait a moment before starting again
    time.sleep(2)
    
    # Get environment settings
    settings = get_env_settings()
    
    # Start the server
    return start_server(settings["host"], settings["port"])

def show_status():
    """Show the status of the DINQ server"""
    if is_running():
        pid = get_pid()
        
        try:
            # Get process information
            process = psutil.Process(pid)
            create_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(process.create_time()))
            cpu_percent = process.cpu_percent(interval=0.5)
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)
            
            # Get environment settings
            settings = get_env_settings()
            
            print("\n=== DINQ Service Status ===")
            print(f"Status:       RUNNING")
            print(f"PID:          {pid}")
            print(f"Started:      {create_time}")
            print(f"Environment:  {settings['env']}")
            print(f"Host:         {settings['host']}")
            print(f"Port:         {settings['port']}")
            print(f"CPU Usage:    {cpu_percent:.1f}%")
            print(f"Memory Usage: {memory_mb:.1f} MB")
            print(f"Log Files:    {LOG_DIR}")
            print("===========================\n")
            
            return True
        
        except (ProcessLookupError, psutil.NoSuchProcess):
            print("\n=== DINQ Service Status ===")
            print(f"Status:       NOT RUNNING (stale PID file)")
            print("===========================\n")
            
            # Remove stale PID file
            remove_pid()
            return False
    
    else:
        print("\n=== DINQ Service Status ===")
        print(f"Status:       NOT RUNNING")
        print("===========================\n")
        return False

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description="DINQ Service Manager")
    parser.add_argument("command", choices=["start", "stop", "restart", "status"],
                        help="Command to execute")
    parser.add_argument("--host", help="Host to bind to (default: from .env or 0.0.0.0)")
    parser.add_argument("--port", type=int, help="Port to listen on (default: from .env or 5001)")
    
    args = parser.parse_args()
    
    # Get environment settings
    settings = get_env_settings()
    
    # Override settings with command line arguments
    if args.host:
        settings["host"] = args.host
    if args.port:
        settings["port"] = args.port
    
    # Execute the requested command
    if args.command == "start":
        start_server(settings["host"], settings["port"])
    elif args.command == "stop":
        stop_server()
    elif args.command == "restart":
        restart_server()
    elif args.command == "status":
        show_status()

if __name__ == "__main__":
    # Ensure we're in the project root directory
    os.chdir(PROJECT_ROOT)
    main()
