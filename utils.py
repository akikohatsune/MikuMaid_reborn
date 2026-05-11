from __future__ import annotations

import shutil
from pathlib import Path


def auto_merge_dotenv() -> None:
    """Synchronize missing keys from .env.example to .env with visual feedback."""
    try:
        example_path = Path(__file__).parent / ".env.example"
        env_path = Path(__file__).parent / ".env"

        if not example_path.exists():
            return
        
        if not env_path.exists():
            print("[\033[94mINFO\033[0m] .env file not found. Creating a new one from .env.example...")
            shutil.copy(example_path, env_path)
            print("[\033[92mSUCCESS\033[0m] .env created successfully. Please fill in your credentials.")
            return

        with open(example_path, "r", encoding="utf-8") as f:
            example_lines = f.readlines()
            
        with open(env_path, "r", encoding="utf-8") as f:
            env_lines = f.readlines()

        example_keys = {}
        for line in example_lines:
            stripped = line.strip()
            if "=" in line and not stripped.startswith("#"):
                key = line.split("=")[0].strip()
                example_keys[key] = line

        env_keys = {line.split("=")[0].strip() for line in env_lines if "=" in line and not line.strip().startswith("#")}

        missing_keys = [k for k in example_keys if k not in env_keys]
        
        if not missing_keys:
            return

        print("\n" + "="*60)
        print("\033[1m      SYSTEM: ENVIRONMENT SYNCHRONIZATION      \033[0m")
        print("="*60)
        print(f"Detected \033[93m{len(missing_keys)}\033[0m missing configurations in your .env file.")
        
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n\n# --- AUTO-MERGED KEYS ---\n")
            for key in missing_keys:
                print(f"  \033[94m+\033[0m Adding: \033[96m{key}\033[0m")
                f.write(example_keys[key])
        
        print("-" * 60)
        print("\033[92mCOMPLETED:\033[0m Your .env has been updated with default values.")
        print("\033[91mIMPORTANT:\033[0m Please check .env and provide necessary values.")
        print("="*60 + "\n")

    except Exception as e:
        print(f"[\033[91mWARNING\033[0m] Environment merge failed: {e}")


def clear_pycache() -> None:
    """Remove __pycache__ directories to prevent stale code."""
    try:
        root_dir = Path(__file__).parent
        for path in root_dir.glob("**/__pycache__"):
            if path.is_dir():
                print(f"Clearing cache: {path}")
                shutil.rmtree(path)
    except Exception as e:
        print(f"Error clearing __pycache__: {e}")
