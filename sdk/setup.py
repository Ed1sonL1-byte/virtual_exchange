from setuptools import setup, find_packages

setup(
    name="agent-metaverse",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["httpx>=0.28.0"],
    python_requires=">=3.10",
    description="Python SDK for Agent Metaverse Virtual Exchange",
)
