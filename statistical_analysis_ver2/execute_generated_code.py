#!/usr/bin/env python3
"""Step 2: Execute generated code.

This script takes a Python file path and executes it, optionally using
a specific virtual environment.
"""

import asyncio
import logging
import re
import shutil
import sys
from pathlib import Path
from typing import List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class CodeExecutor:
    """Executes Python code files with automatic package installation."""

    def __init__(self, venv_dir: Optional[Path] = None, auto_install: bool = True):
        """Initialize code executor.

        Args:
            venv_dir: Optional path to virtual environment directory.
                     If None, uses system Python or project .venv
            auto_install: If True, automatically install missing packages
        """
        self.venv_dir = venv_dir
        self.auto_install = auto_install
        self.installed_packages: List[str] = []

    def _get_python_command(self) -> str:
        """Get Python command to use.

        Returns:
            Path to Python executable
        """
        # If venv directory is provided, use its Python
        if self.venv_dir:
            venv_python = self.venv_dir / "bin" / "python"
            if venv_python.exists():
                return str(venv_python.resolve())
            logger.warning(
                f"Venv Python not found at {venv_python}, using system Python"
            )

        # Try to use project .venv if it exists
        project_venv = Path(".venv/bin/python")
        if project_venv.exists():
            return str(project_venv.resolve())

        # Fall back to system Python
        return sys.executable

    def _extract_missing_package(self, stderr: str) -> str | None:
        """Extract package name from ImportError or ModuleNotFoundError message.

        Args:
            stderr: Error message containing ImportError or ModuleNotFoundError

        Returns:
            Package name or None
        """
        # Pattern: "No module named 'package_name'" (works for both ImportError and ModuleNotFoundError)
        pattern = r"No module named ['\"]([^'\"]+)['\"]"
        match = re.search(pattern, stderr)
        if match:
            package_name = match.group(1)
            # Handle submodules (e.g., 'scipy.stats' -> 'scipy')
            package_name = package_name.split(".")[0]
            # Map common package names to pip install names
            package_map = {
                "sklearn": "scikit-learn",
                "PIL": "Pillow",
                "cv2": "opencv-python",
            }
            return package_map.get(package_name, package_name)
        return None

    async def _install_package(self, package_name: str) -> bool:
        """Install a Python package into the environment.

        Args:
            package_name: Name of package to install

        Returns:
            True if installation succeeded
        """
        try:
            python_cmd = self._get_python_command()

            # Use uv pip install with -p flag to target the specific environment
            # This avoids externally-managed-environment errors
            if shutil.which("uv"):
                process = await asyncio.create_subprocess_exec(
                    "uv",
                    "pip",
                    "install",
                    "-p",
                    python_cmd,
                    package_name,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    logger.info(f"Successfully installed {package_name} via uv pip")
                    return True
                else:
                    stderr_str = stderr.decode()
                    logger.warning(f"uv pip install failed: {stderr_str[:200]}")

            # Fall back to regular pip install using the same Python
            # Use --break-system-packages if needed (for uv-managed environments)
            logger.info(f"Trying pip install for {package_name}")
            process = await asyncio.create_subprocess_exec(
                python_cmd,
                "-m",
                "pip",
                "install",
                "--break-system-packages",  # Needed for uv-managed environments
                package_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                logger.info(f"Successfully installed {package_name} via pip")
                return True

            logger.error(f"Failed to install {package_name}: {stderr.decode()}")
            return False

        except Exception as e:
            logger.error(f"Error installing package {package_name}: {e}")
            return False

    async def execute_file(
        self, file_path: Path, working_dir: Optional[Path] = None
    ) -> int:
        """Execute a Python file with automatic package installation.

        Args:
            file_path: Path to Python file to execute
            working_dir: Optional working directory for execution.
                        If None, uses file's parent directory

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        # Resolve file path
        file_path = file_path.resolve()

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            print(f"❌ Error: File not found: {file_path}")
            return 1

        if not file_path.is_file():
            logger.error(f"Path is not a file: {file_path}")
            print(f"❌ Error: Path is not a file: {file_path}")
            return 1

        # Set working directory
        if working_dir:
            working_dir = working_dir.resolve()
        else:
            working_dir = file_path.parent

        # Get Python command
        python_cmd = self._get_python_command()

        logger.info(f"Executing: {file_path}")
        logger.info(f"Using Python: {python_cmd}")
        logger.info(f"Working directory: {working_dir}")

        print(f"\n🚀 Executing: {file_path.name}")
        print(f"   Python: {python_cmd}")
        print(f"   Working directory: {working_dir}")
        print("-" * 60)

        # Track packages installed during this execution
        session_packages: List[str] = []
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Use relative path from working_dir when cwd is set
                try:
                    file_path_rel = file_path.relative_to(working_dir)
                except ValueError:
                    # If file is not relative to working_dir, use absolute path
                    file_path_rel = file_path

                # Execute the file
                process = await asyncio.create_subprocess_exec(
                    python_cmd,
                    str(file_path_rel),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(working_dir),
                )

                stdout, stderr = await process.communicate()

                # Decode output
                stdout_text = stdout.decode("utf-8", errors="replace")
                stderr_text = stderr.decode("utf-8", errors="replace")

                # Check for ImportError or ModuleNotFoundError if auto_install is enabled
                if (
                    self.auto_install
                    and process.returncode != 0
                    and (
                        "ImportError" in stderr_text
                        or "ModuleNotFoundError" in stderr_text
                    )
                ):
                    missing_package = self._extract_missing_package(stderr_text)
                    if missing_package and missing_package not in session_packages:
                        logger.info(f"Detected missing package: {missing_package}")
                        print(f"\n📦 Installing missing package: {missing_package}")
                        install_success = await self._install_package(missing_package)
                        if install_success:
                            session_packages.append(missing_package)
                            self.installed_packages.append(missing_package)
                            retry_count += 1
                            print(
                                f"✅ Installed {missing_package}, retrying execution...\n"
                            )
                            continue

                # Print output
                if stdout_text:
                    print(stdout_text)

                if stderr_text:
                    print(stderr_text, file=sys.stderr)

                print("-" * 60)

                if process.returncode == 0:
                    if session_packages:
                        print(f"✅ Execution completed successfully!")
                        print(f"📦 Installed packages: {', '.join(session_packages)}")
                    else:
                        print("✅ Execution completed successfully!")

                    # Save requirements.txt if packages were installed
                    if session_packages:
                        requirements_file = working_dir / "requirements.txt"
                        requirements_file.write_text("\n".join(session_packages) + "\n")
                        logger.info(f"Saved requirements.txt: {requirements_file}")

                    return 0
                else:
                    print(f"❌ Execution failed with exit code: {process.returncode}")
                    return process.returncode

            except Exception as e:
                logger.error(f"Error executing file: {e}", exc_info=True)
                print(f"❌ Error executing file: {e}")
                return 1

        # If we exhausted retries
        if session_packages:
            print(
                f"\n⚠️  Exhausted retry attempts after installing: {', '.join(session_packages)}"
            )
        return 1


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: execute_generated_code.py <file_path> [venv_dir]")
        print("\nExamples:")
        print("  execute_generated_code.py binary_search.py")
        print("  execute_generated_code.py binary_search.py query_venvs/abc12345")
        sys.exit(1)

    file_path = Path(sys.argv[1])
    venv_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    executor = CodeExecutor(venv_dir=venv_dir)
    exit_code = await executor.execute_file(file_path)

    sys.exit(exit_code)


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
