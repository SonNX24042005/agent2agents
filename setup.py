from setuptools import setup, find_packages

setup(
    name="agent2agents",
    version="1.5.0",
    description="Converter between Claude Code, Antigravity CLI (agy), and Codex sessions",
    author="Antigravity Pair Programmer",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "a2a=agent2agents.cli:main",
            "agent2agents=agent2agents.cli:main",
            "claude2agy=agent2agents.cli:main",
            "claude2codex=agent2agents.cli:main",
            "agy2claude=agent2agents.cli:main",
            "agy2codex=agent2agents.cli:main",
            "codex2claude=agent2agents.cli:main",
            "codex2agy=agent2agents.cli:main",
        ],
    },
    python_requires=">=3.8",
)
