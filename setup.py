from setuptools import find_packages
from setuptools import setup

setup(
    name="hari_client",
    version="6.2.1",
    description="A Python client for the HARI API",
    author="Quality Match GmbH",
    author_email="info@quality-match.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.32",
        "pydantic>=2.11",
        "pydantic-settings>=2.3",
        "tqdm~=4.66",
        "exceptiongroup==1.3.0",
    ],
    extras_require={
        "tests": ["pytest", "pytest-mock", "pre-commit"],
        "dev": ["pytest", "pytest-mock", "pre-commit", "bumpversion"],
        "scripts": ["pandas", "scikit-learn", "Pillow"],
    },
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
