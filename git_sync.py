import os
import subprocess
import logging
from pathlib import Path
from config import OBSIDIAN_VAULT_DIR

logger = logging.getLogger(__name__)

def sync_obsidian_repo() -> bool:
    """
    Clones or pulls the Obsidian Vault from a private GitHub repository.
    Reads OBSIDIAN_REPO_URL and GITHUB_TOKEN from the environment.
    """
    repo_url = os.getenv("OBSIDIAN_REPO_URL")
    github_token = os.getenv("GITHUB_TOKEN")

    if not repo_url:
        logger.info("GitHub sync skipped. OBSIDIAN_REPO_URL not set.")
        return False

    # Strip any https:// prefix and build the auth URL
    clean_repo_url = repo_url.replace("https://", "").replace("http://", "")
    if github_token:
        auth_url = f"https://{github_token}@{clean_repo_url}"
    else:
        auth_url = f"https://{clean_repo_url}"

    vault_path = Path(OBSIDIAN_VAULT_DIR)

    try:
        # Check if the directory exists and is a git repository
        git_dir = vault_path / ".git"
        if vault_path.exists() and git_dir.exists():
            logger.info("Vault directory exists. Pulling latest changes...")
            result = subprocess.run(
                ["git", "-C", str(vault_path), "pull"],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("Git Pull successful: %s", result.stdout.strip())
        else:
            logger.info("Vault directory not found or empty. Cloning repository...")
            # Ensure the parent directory exists
            vault_path.parent.mkdir(parents=True, exist_ok=True)
            
            result = subprocess.run(
                ["git", "clone", auth_url, str(vault_path)],
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("Git Clone successful.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Git sync failed. Exit Code: %s\nError Output: %s", e.returncode, e.stderr)
        return False
    except Exception as e:
        logger.error("Unexpected error during Git sync: %s", e)
        return False

def push_obsidian_vault() -> bool:
    """
    Stages, commits, and pushes any local updates in the Obsidian Vault to the remote GitHub repository.
    """
    vault_path = Path(OBSIDIAN_VAULT_DIR)
    git_dir = vault_path / ".git"
    if not git_dir.exists():
        logger.info("Not a git repository, skipping push.")
        return False
        
    try:
        # Check if there are changes
        status = subprocess.run(
            ["git", "-C", str(vault_path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True
        )
        if not status.stdout.strip():
            logger.info("No local vault changes to push.")
            return True
            
        logger.info("Staging, committing, and pushing local vault updates to GitHub...")
        # Stage all changes
        subprocess.run(["git", "-C", str(vault_path), "add", "."], check=True)
        # Commit changes
        subprocess.run(
            ["git", "-C", str(vault_path), "commit", "-m", "Auto-sync local vault updates [Chatbot App]"],
            check=True
        )
        # Push changes
        subprocess.run(["git", "-C", str(vault_path), "push"], check=True)
        logger.info("Successfully pushed local vault updates to GitHub.")
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Git vault push failed. Exit Code: %s\nError Output: %s", e.returncode, e.stderr)
        return False
    except Exception as e:
        logger.error("Unexpected error during git vault push: %s", e)
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sync_obsidian_repo()
