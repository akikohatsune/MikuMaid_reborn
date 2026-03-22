from __future__ import annotations

import shutil
from pathlib import Path


def auto_merge_dotenv() -> None:
    """Synchronize missing keys from .env.example to .env."""
    try:
        example_path = Path(__file__).parent / ".env.example"
        env_path = Path(__file__).parent / ".env"

        if not example_path.exists():
            return
        
        if not env_path.exists():
            env_path.touch()

        with open(example_path, "r", encoding="utf-8") as f:
            example_keys = {line.split("=")[0].strip() for line in f if "=" in line and not line.strip().startswith("#")}
        with open(env_path, "r", encoding="utf-8") as f:
            env_keys = {line.split("=")[0].strip() for line in f if "=" in line and not line.strip().startswith("#")}

        missing_keys = example_keys - env_keys
        
        if not missing_keys:
            return

        print(f"Auto-merging {len(missing_keys)} missing keys from .env.example into .env...")
        
        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n\n# Auto-merged from .env.example\n")
            with open(example_path, "r", encoding="utf-8") as f_example:
                for line in f_example:
                    key = line.split("=")[0].strip()
                    if key in missing_keys:
                        f.write(line)
        
        print("Merge complete. Please review the new keys in your .env file.")

    except Exception as e:
        print(f"Warning: Could not auto-merge .env file: {e}")


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
