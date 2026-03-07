"""BlindOracle Marketplace Client SDK setup."""

from setuptools import setup, find_packages

setup(
    name="blindoracle-marketplace-client",
    version="0.1.0",
    description="Python client for the BlindOracle Agent-to-Agent Economy",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Craig M. Brown",
    author_email="craigmbrown@gmail.com",
    url="https://github.com/craigmbrown/blindoracle-marketplace-client",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[],  # stdlib only — no external dependencies
    extras_require={
        "dev": ["pytest", "black", "mypy"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries",
    ],
    license="MIT",
)
