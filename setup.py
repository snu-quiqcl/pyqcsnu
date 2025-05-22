"""
Setup configuration for the PyQCSNU package.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pyqcsnu",
    version="0.1.0",
    author="SNU Quantum Software Team",
    author_email="myfirstexp@snu.ac.kr",
    description="Python client for SNU quantum computing services",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/snu-quiqcl/pyqcsnu",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Physics",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=[
        "requests>=2.31.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "qiskit>=1.0.0",
        "pydantic>=2.0.0",
        "python-dateutil>=2.8.2",
        "typing-extensions>=4.5.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.10.0",
            "pytest-timeout>=2.1.0",
            "responses>=0.23.0",
            "requests-mock>=1.11.0",
            "black>=23.0.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "flake8-docstrings>=1.7.0",
            "flake8-bugbear>=23.3.0",
            "mypy>=1.0.0",
            "types-requests>=2.28.0",
            "types-python-dateutil>=2.8.19.14",
            "pre-commit>=3.3.0",
            "coverage>=7.2.7",
            "safety>=2.3.0",
        ],
    },
) 