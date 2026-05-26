"""Kiwi — Autonomous Code Quality Agent

Setup script for pip installation.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

setup(
    name="kiwi-scanner",
    version="2.0.0",
    description="Autonomous code quality agent with bug pattern scanning and auto-fix",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Wezone Team",
    author_email="dev@wezone.vn",
    url="https://github.com/wezone/kiwi",
    packages=find_packages(exclude=["tests", "tests.*"]),
    include_package_data=True,
    python_requires=">=3.11",
    install_requires=[
        # Core dependencies (minimal)
    ],
    extras_require={
        "agent": [
            "anthropic>=0.40.0",  # Claude API for agent full mode
        ],
        "deploy": [
            "paramiko>=3.0",      # SSH for VPS deployment
            "requests>=2.31",     # HTTP for health checks
        ],
        "ast": [
            "tree-sitter>=0.20",  # AST parsing for Python/PHP
        ],
        "all": [
            "anthropic>=0.40.0",
            "paramiko>=3.0",
            "requests>=2.31",
            "tree-sitter>=0.20",
        ],
    },
    py_modules=["cli", "__main__"],
    entry_points={
        "console_scripts": [
            "kiwi=cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
    ],
    keywords="code-quality scanner linter bug-detection autonomous-agent",
)