from setuptools import find_packages, setup

setup(
    name="discord-absence-bot",
    version="1.0.0",
    description="Discord bot for daily absence day reports",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.9",
    install_requires=[
        "discord.py>=2.4.0,<3.0.0",
        "aiosqlite>=0.20.0,<1.0.0",
        "APScheduler>=3.10.4,<4.0.0",
        "aiohttp>=3.9.5,<4.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.3.0,<9.0.0",
            "pytest-asyncio>=0.23.8,<1.0.0",
        ]
    },
)
