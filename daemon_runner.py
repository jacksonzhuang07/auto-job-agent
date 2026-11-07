import time
import logging
import signal
import sys
from pathlib import Path
from datetime import datetime, timedelta
from main import run_daily_workflow

BASE_DIR = Path(__file__).resolve().parent
handlers = [logging.FileHandler(str(BASE_DIR / "agent.log"), encoding="utf-8")]
if sys.stdout is not None:
    handlers.append(logging.StreamHandler(sys.stdout))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Daemon]: %(message)s",
    handlers=handlers
)
logger = logging.getLogger("DaemonRunner")

RUNNING = True

def handle_signal(sig, frame):
    global RUNNING
    logger.info(f"Received shutdown signal ({sig}). Exiting cleanly...")
    RUNNING = False
    sys.exit(0)

signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

def run_loop():
    logger.info("AutoJobAgent daemon initialized. Starting continuous passive monitoring...")
    
    while RUNNING:
        try:
            logger.info("Executing scheduled job discovery and application batch...")
            run_daily_workflow()
        except Exception as e:
            logger.error(f"Error occurred during application run: {e}", exc_info=True)

        # Sleep interval: calculate time until next cycle (24 hours or next morning)
        # Default passive interval: 24 hours (86,400s) with check every 60s for shutdown
        logger.info("Workflow completed for this cycle. Entering passive sleep mode (next cycle in ~24h)...")
        sleep_seconds = 24 * 3600
        start_sleep = time.time()

        while RUNNING and (time.time() - start_sleep < sleep_seconds):
            time.sleep(10)

if __name__ == "__main__":
    run_loop()
