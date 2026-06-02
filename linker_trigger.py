import os
import sys
import subprocess
from config import OBSIDIAN_VAULT_DIR

def trigger_obsidian_linker() -> bool:
    """
    Launches the Obsidian Linker (main.py) asynchronously in the background.
    Uses the active python interpreter to maintain the conda environment context.
    Passes the configured Obsidian vault path dynamically.
    """
    linker_main = r"c:\Users\saraf\Desktop\projects\obsidian-linker\main.py"
    
    if not os.path.exists(linker_main):
        print(f"[Linker Trigger Error] Obsidian Linker main.py not found at: {linker_main}")
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
        print(f"[Linker Trigger] Obsidian Linker triggered successfully in background for: {OBSIDIAN_VAULT_DIR}")
        return True
    except Exception as e:
        print(f"[Linker Trigger Error] Failed to launch background linker: {e}")
        return False

def run_obsidian_linker_sync() -> bool:
    """
    Runs the Obsidian Linker (main.py) synchronously, blocking until it completes.
    Maintains the conda environment context.
    Passes the configured Obsidian vault path dynamically.
    """
    linker_main = r"c:\Users\saraf\Desktop\projects\obsidian-linker\main.py"
    
    if not os.path.exists(linker_main):
        print(f"[Linker Trigger Error] Obsidian Linker main.py not found at: {linker_main}")
        return False
        
    try:
        print(f"[Linker Trigger] Starting synchronous Obsidian Linker run for: {OBSIDIAN_VAULT_DIR}...")
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
            print("[Linker Trigger] Obsidian Linker completed successfully.")
            return True
        else:
            print(f"[Linker Trigger Error] Linker failed with code {result.returncode}: {result.stderr}")
            return False
    except Exception as e:
        print(f"[Linker Trigger Error] Failed to run linker synchronously: {e}")
        return False

if __name__ == "__main__":
    # Test execution in isolation
    print("Testing linker trigger...")
    success = trigger_obsidian_linker()
    print(f"Trigger result: {success}")
