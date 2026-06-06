import os
import sys
import subprocess
import logging
from config import OBSIDIAN_VAULT_DIR, OBSIDIAN_LINKER_PATH

logger = logging.getLogger(__name__)

def trigger_obsidian_linker() -> bool:
    """
    Launches the Obsidian Linker (main.py) asynchronously in the background.
    Uses the active python interpreter to maintain the conda environment context.
    Passes the configured Obsidian vault path dynamically.
    """
    linker_main = str(OBSIDIAN_LINKER_PATH)
    
    if not OBSIDIAN_LINKER_PATH.exists():
        logger.error("Obsidian Linker main.py not found at: %s", OBSIDIAN_LINKER_PATH)
        return False
        
    try:
        # Prepare execution environment and arguments
        env = {**os.environ, "OBSIDIAN_VAULT_DIR": str(OBSIDIAN_VAULT_DIR)}
        args = [sys.executable, linker_main, "--dir", str(OBSIDIAN_VAULT_DIR)]
        
        # Run main.py asynchronously in the background
        # DEVNULL discards the outputs so it runs silently
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            close_fds=True if os.name != 'nt' else False
        )
        logger.info("Obsidian Linker triggered successfully in background for: %s", OBSIDIAN_VAULT_DIR)
        return True
    except Exception as e:
        logger.error("Failed to launch background linker: %s", e)
        return False

def run_obsidian_linker_sync() -> bool:
    """
    Runs the Obsidian Linker (main.py) synchronously, blocking until it completes.
    Maintains the conda environment context.
    Passes the configured Obsidian vault path dynamically.
    """
    linker_main = str(OBSIDIAN_LINKER_PATH)
    
    if not OBSIDIAN_LINKER_PATH.exists():
        logger.error("Obsidian Linker main.py not found at: %s", OBSIDIAN_LINKER_PATH)
        return False
        
    try:
        logger.info("Starting synchronous Obsidian Linker run for: %s...", OBSIDIAN_VAULT_DIR)
        env = {**os.environ, "OBSIDIAN_VAULT_DIR": str(OBSIDIAN_VAULT_DIR)}
        args = [sys.executable, linker_main, "--dir", str(OBSIDIAN_VAULT_DIR)]
        
        result = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        if result.returncode == 0:
            logger.info("Obsidian Linker completed successfully.")
            return True
        else:
            logger.error("Linker failed with code %s: %s", result.returncode, result.stderr)
            return False
    except Exception as e:
        logger.error("Failed to run linker synchronously: %s", e)
        return False

if __name__ == "__main__":
    # Test execution in isolation
    logger.info("Testing linker trigger...")
    success = trigger_obsidian_linker()
    logger.info("Trigger result: %s", success)
