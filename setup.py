from setuptools import find_packages
from setuptools import setup

setup(
    name="hari_client",
    version="2.2.0",
    description="A Python client for the HARI API",
    author="Quality Match GmbH",
    author_email="info@quality-match.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.32",
        "pydantic>=2.8",
        "pydantic-settings>=2.3",
        "tqdm~=4.66",
    ],
    extras_require={"tests": ["pytest", "pytest-mock", "pre-commit"]},
    classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
