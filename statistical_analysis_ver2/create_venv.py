#!/usr/bin/env python3
"""Step 1: Create virtual environment from user query.

This script takes a user query and creates an isolated virtual environment
for executing code related to that query.
"""

import asyncio
import logging
import shutil
import sys
import uuid
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class VenvCreator:
    """Creates virtual environments for user queries."""

    def __init__(self, base_dir: Path = Path("query_venvs")):
        """Initialize venv creator.

        Args:
            base_dir: Base directory where venvs will be created
        """
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def create_venv(self, user_query: str) -> Optional[Path]:
        """Create a virtual environment for a user query.

        Args:
            user_query: The user's query/request

        Returns:
            Path to created venv directory, or None if creation failed
        """
        # Generate a unique session ID for this query
        session_id = str(uuid.uuid4())[:8]
        venv_dir = self.base_dir / session_id

        # Check if uv is available
        if not shutil.which("uv"):
            logger.error(
                "uv not found. Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
            )
            return None

        logger.info(f"Creating virtual environment for query: {user_query[:50]}...")
        logger.info(f"Session ID: {session_id}")
        logger.info(f"Venv directory: {venv_dir}")

        # Remove existing venv if it exists
        if venv_dir.exists():
            logger.warning(f"Removing existing venv at {venv_dir}")
            shutil.rmtree(venv_dir)

        # Create parent directory if needed
        venv_dir.parent.mkdir(parents=True, exist_ok=True)

        # Use uv to create venv
        try:
            process = await asyncio.create_subprocess_exec(
                "uv",
                "venv",
                str(venv_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                logger.error(f"Failed to create venv: {error_msg}")
                return None

            logger.info(f"✅ Virtual environment created successfully at: {venv_dir}")
            logger.info(f"Python executable: {venv_dir / 'bin' / 'python'}")

            return venv_dir

        except Exception as e:
            logger.error(f"Error creating venv: {e}", exc_info=True)
            return None

    def get_python_path(self, venv_dir: Path) -> Optional[Path]:
        """Get the Python executable path for a venv.

        Args:
            venv_dir: Path to venv directory

        Returns:
            Path to Python executable, or None if not found
        """
        python_path = venv_dir / "bin" / "python"
        if python_path.exists():
            return python_path
        return None


async def main():
    """Main entry point."""
    # Get user query from command line or prompt
    if len(sys.argv) > 1:
        user_query = " ".join(sys.argv[1:])
    else:
        user_query = input("Enter your query: ").strip()
        if not user_query:
            print("Error: Query cannot be empty")
            sys.exit(1)

    print(f"\n📝 User Query: {user_query}\n")

    # Create venv creator
    creator = VenvCreator()

    # Create virtual environment
    venv_dir = await creator.create_venv(user_query)

    if venv_dir:
        python_path = creator.get_python_path(venv_dir)
        print(f"\n✅ Success! Virtual environment created:")
        print(f"   Location: {venv_dir}")
        if python_path:
            print(f"   Python: {python_path}")
        print(f"\n💡 Next steps:")
        print(f"   - Install packages: uv pip install -p {python_path} <package>")
        print(f"   - Run Python: {python_path} <script.py>")
        return 0
    else:
        print("\n❌ Failed to create virtual environment")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
