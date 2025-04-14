# vpnmon_scheduler.py
import time
import subprocess
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("vpnmon-scheduler")

INTERVAL_SECONDS = 300  # 5 minutes

def collect_data():
    logger.info("Running data collection...")
    try:
        result = subprocess.run(
            ["/opt/venv/bin/python3", "/app/cli/monitor.py", "collect"], 
            capture_output=True, 
            text=True
        )
        if result.returncode == 0:
            logger.info("Data collection successful")
        else:
            logger.error(f"Data collection failed: {result.stderr}")
    except Exception as e:
        logger.error(f"Error running data collection: {e}")

# Main loop
logger.info(f"Scheduler starting, will collect data every {INTERVAL_SECONDS} seconds")
while True:
    collect_data()
    time.sleep(INTERVAL_SECONDS)