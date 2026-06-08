import os
import logging
import requests
from config import OBSIDIAN_VAULT_DIR

logger = logging.getLogger(__name__)

def trigger_obsidian_linker() -> bool:
    """
    Triggers the Obsidian Linker FastAPI endpoint asynchronously.
    """
    api_url = os.getenv("LINKER_API_URL")
    if not api_url:
        logger.error("LINKER_API_URL not set in environment.")
        return False
        
    repo_url = os.getenv("OBSIDIAN_REPO_URL", "")
    token = os.getenv("GITHUB_TOKEN", "")
    
    try:
        payload = {
            "github_url": repo_url,
            "github_token": token
        }
        # Fire and forget (timeout=1 to avoid blocking, handle Timeout as success since it's background processing)
        try:
            requests.post(f"{api_url}/sync", json=payload, timeout=1)
        except requests.exceptions.ReadTimeout:
            pass
        logger.info("Obsidian Linker API triggered successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to trigger linker API: {e}")
        return False

def run_obsidian_linker_sync() -> bool:
    """
    Runs the Obsidian Linker sync synchronously via the API.
    """
    api_url = os.getenv("LINKER_API_URL")
    if not api_url:
        logger.error("LINKER_API_URL not set in environment.")
        return False
        
    repo_url = os.getenv("OBSIDIAN_REPO_URL", "")
    token = os.getenv("GITHUB_TOKEN", "")
    
    try:
        logger.info("Starting synchronous Obsidian Linker API run...")
        payload = {
            "github_url": repo_url,
            "github_token": token
        }
        response = requests.post(f"{api_url}/sync", json=payload, timeout=90)
        
        if response.status_code == 200:
            logger.info("Obsidian Linker API responded successfully.")
            return True
        else:
            logger.error(f"Linker API failed with code {response.status_code}: {response.text}")
            return False
    except requests.exceptions.ReadTimeout:
        logger.warning("Linker API request timed out. This is normal if Render is cold-starting or cloning a large vault.")
        return True
    except Exception as e:
        logger.error(f"Failed to run linker API synchronously: {e}")
        return False
