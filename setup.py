#!/usr/bin/env python3
"""
Setup script for Audio Transcription Pipeline
Automates project setup including dependencies, environment variables, and Docker services.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import shutil

# Make script executable-friendly
if __name__ == "__main__" and os.name != "nt":
    # On Unix-like systems, ensure script is executable
    pass


# Color codes for terminal output
class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_step(message):
    """Print a step message with formatting"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}▶ {message}{Colors.END}")


def print_success(message):
    """Print a success message"""
    print(f"{Colors.GREEN}✓ {message}{Colors.END}")


def print_warning(message):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.END}")


def print_error(message):
    """Print an error message"""
    print(f"{Colors.RED}✗ {message}{Colors.END}")


def check_python_version():
    """Check if Python version is 3.12+"""
    print_step("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 12):
        print_error(
            f"Python 3.12+ required. Found Python {version.major}.{version.minor}"
        )
        sys.exit(1)
    print_success(f"Python {version.major}.{version.minor}.{version.micro} detected")


def check_command(command, name):
    """Check if a command is available"""
    if shutil.which(command):
        print_success(f"{name} is installed")
        return True
    else:
        print_warning(f"{name} is not installed")
        return False


def install_dependencies():
    """Install project dependencies"""
    print_step("Installing dependencies...")

    # Check for uv
    has_uv = check_command("uv", "uv")

    if has_uv:
        print("Using uv to install dependencies...")
        try:
            # Try uv sync first
            result = subprocess.run(
                ["uv", "sync"], capture_output=True, text=True, check=True
            )
            print_success("Dependencies installed using uv sync")
            return True
        except subprocess.CalledProcessError:
            print_warning("uv sync failed, trying uv pip install...")
            try:
                result = subprocess.run(
                    ["uv", "pip", "install", "-e", "."],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                print_success("Dependencies installed using uv pip install")
                return True
            except subprocess.CalledProcessError as e:
                print_error(f"uv pip install failed: {e.stderr}")

    # Fallback to pip
    print("Falling back to pip...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-e", "."],
            capture_output=True,
            text=True,
            check=True,
        )
        print_success("Dependencies installed using pip")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"pip install failed: {e.stderr}")
        return False


def setup_environment():
    """Set up environment variables"""
    print_step("Setting up environment variables...")

    env_file = Path(".env")
    env_example = Path(".env.example")

    # Create .env.example if it doesn't exist
    if not env_example.exists():
        env_example.write_text(
            """# Required: Gemini API key for generating study notes
GEMINI_API_KEY=your-gemini-api-key-here

# Optional: OpenAI settings for local Whisper server
OPENAI_BASE_URL=http://localhost:8001/v1/
OPENAI_API_KEY=cant-be-empty
"""
        )
        print_success("Created .env.example file")

    # Check if .env exists
    if env_file.exists():
        print_warning(".env file already exists")
        response = input("Do you want to update it? (y/n): ").strip().lower()
        if response != "y":
            print("Skipping .env setup")
            return

    # Get GEMINI_API_KEY from user
    print("\nPlease provide your GEMINI_API_KEY.")
    print("You can get it from: https://aistudio.google.com/app/apikey")
    gemini_key = input("GEMINI_API_KEY (or press Enter to skip): ").strip()

    # Create .env file
    env_content = []
    if gemini_key:
        env_content.append(f"GEMINI_API_KEY={gemini_key}")
    else:
        env_content.append("GEMINI_API_KEY=your-gemini-api-key-here")
        print_warning("GEMINI_API_KEY not provided. Please set it in .env file later.")

    env_content.append("\n# Optional: OpenAI settings for local Whisper server")
    env_content.append("OPENAI_BASE_URL=http://localhost:8001/v1/")
    env_content.append("OPENAI_API_KEY=cant-be-empty")

    env_file.write_text("\n".join(env_content))
    print_success(f"Created .env file at {env_file.absolute()}")

    # Set environment variables for current session
    if gemini_key:
        os.environ["GEMINI_API_KEY"] = gemini_key
        print_success("GEMINI_API_KEY set for current session")


def create_directories():
    """Create necessary directories"""
    print_step("Creating necessary directories...")

    directories = [
        Path("media"),
        Path("cache/huggingface"),
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print_success(f"Created directory: {directory}")


def check_docker():
    """Check if Docker is installed and running"""
    print_step("Checking Docker...")

    if not check_command("docker", "Docker"):
        print_error("Docker is not installed. Please install Docker first.")
        print("Visit: https://docs.docker.com/get-docker/")
        return False

    # Check if Docker daemon is running
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, check=True
        )
        print_success("Docker daemon is running")
        return True
    except subprocess.CalledProcessError:
        print_error("Docker daemon is not running. Please start Docker.")
        return False


def setup_docker_compose():
    """Set up and start Docker Compose services"""
    print_step("Setting up Docker Compose...")

    if not check_docker():
        print_warning("Skipping Docker Compose setup")
        return False

    docker_compose_file = Path("docker-compose.yml")
    if not docker_compose_file.exists():
        print_error("docker-compose.yml not found")
        return False

    # Check if docker-compose is available
    compose_command = None
    if shutil.which("docker-compose"):
        compose_command = "docker-compose"
    elif shutil.which("docker"):
        # Try docker compose (newer version)
        try:
            subprocess.run(
                ["docker", "compose", "version"], capture_output=True, check=True
            )
            compose_command = "docker compose"
        except:
            pass

    if not compose_command:
        print_error("docker-compose not found. Please install docker-compose.")
        return False

    print(f"Using: {compose_command}")

    # Start services
    print("Starting Docker Compose services...")
    try:
        if compose_command == "docker-compose":
            subprocess.run(["docker-compose", "up", "-d"], check=True)
        else:
            subprocess.run(["docker", "compose", "up", "-d"], check=True)
        print_success("Docker Compose services started")
        print("  - Faster Whisper server running on http://localhost:8001")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"Failed to start Docker Compose services: {e}")
        return False


def initialize_database():
    """Initialize the database"""
    print_step("Initializing database...")

    try:
        from src.database import init_db

        init_db()
        print_success("Database initialized successfully")
        return True
    except Exception as e:
        print_error(f"Failed to initialize database: {e}")
        return False


def print_next_steps():
    """Print instructions for next steps"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}")
    print("Setup Complete! Next Steps:")
    print(f"{'='*60}{Colors.END}\n")

    print("1. Start Celery Worker (Terminal 1):")
    if platform.system() == "Windows":
        print(
            f"   {Colors.YELLOW}celery -A src.workers.celery worker --pool=solo --loglevel=info{Colors.END}"
        )
    else:
        print(
            f"   {Colors.YELLOW}celery -A src.workers.celery worker --loglevel=info{Colors.END}"
        )

    print("\n2. Start FastAPI Server (Terminal 2):")
    print(f"   {Colors.YELLOW}fastapi dev main.py{Colors.END}")

    print("\n3. Access API Documentation:")
    print(f"   {Colors.BLUE}http://localhost:8000/docs{Colors.END}")

    print("\n4. Test the API:")
    print(f'   {Colors.YELLOW}curl -X POST "http://localhost:8000/notes/youtube" \\')
    print(f'     -H "Content-Type: application/json" \\')
    print(
        f'     -d \'{{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}}\'{Colors.END}'
    )

    print(f"\n{Colors.BOLD}Important:{Colors.END}")
    print("  - Make sure GEMINI_API_KEY is set in .env file")
    print("  - Docker Compose services should be running for Whisper transcription")
    print("  - Both Celery worker and FastAPI server need to be running")


def main():
    """Main setup function"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}")
    print("Audio Transcription Pipeline - Setup Script")
    print(f"{'='*60}{Colors.END}\n")

    # Check Python version
    check_python_version()

    # Install dependencies
    if not install_dependencies():
        print_error("Failed to install dependencies. Please install manually.")
        sys.exit(1)

    # Create directories
    create_directories()

    # Setup environment
    setup_environment()

    # Setup Docker Compose
    setup_docker_compose()

    # Initialize database
    initialize_database()

    # Print next steps
    print_next_steps()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Setup interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Setup failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
