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
    Triggers the Obsidian Linker sync and polls its /status endpoint until completed.
    """
    import time
    api_url = os.getenv("LINKER_API_URL")
    if not api_url:
        logger.error("LINKER_API_URL not set in environment.")
        return False
        
    repo_url = os.getenv("OBSIDIAN_REPO_URL", "")
    token = os.getenv("GITHUB_TOKEN", "")
    
    try:
        logger.info("Starting Obsidian Linker API run...")
        payload = {
            "github_url": repo_url,
            "github_token": token
        }
        # Render POST /sync starts the background task and returns 200 immediately
        response = requests.post(f"{api_url}/sync", json=payload, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Linker API trigger failed with code {response.status_code}: {response.text}")
            return False
            
        logger.info("Linker task triggered successfully. Polling status endpoint for completion...")
        
        # Poll GET /status until status is 'completed' or 'failed'
        timeout_seconds = 360 # 6 minutes max
        start_time = time.time()
        
        # Sleep for a moment to let the background task start running
        time.sleep(3)
        
        while time.time() - start_time < timeout_seconds:
            try:
                status_res = requests.get(f"{api_url}/status", timeout=10)
                if status_res.status_code == 200:
                    status_data = status_res.json()
                    status = status_data.get("status")
                    if status == "completed":
                        logger.info("Obsidian Linker completed successfully.")
                        return True
                    elif status == "failed":
                        logger.error("Obsidian Linker task failed: %s", status_data.get("error"))
                        return False
                    elif status == "running":
                        logger.info("Linker task is running... (elapsed: %ds)", int(time.time() - start_time))
                    else:
                        logger.info("Linker task is in state: %s", status)
                else:
                    logger.warning("Linker status check returned code %d", status_res.status_code)
            except Exception as check_err:
                logger.warning("Polling status endpoint failed: %s", check_err)
                
            time.sleep(5)
            
        logger.error("Timed out waiting for Obsidian Linker task to finish.")
        return False
        
    except Exception as e:
        logger.error(f"Failed to run linker API and poll: {e}")
        return False
