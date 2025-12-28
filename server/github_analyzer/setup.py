from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="github-analyzer",
    version="1.0.0",
    author="GitHub Analyzer Team",
    author_email="your-email@example.com",
    description="A powerful GitHub user analysis tool with Flask API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/github-analyzer",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Flask",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    include_package_data=True,
    package_data={
        "github_analyzer": ["dev_pioneers.csv", ".env.template"],
    },
    entry_points={
        "console_scripts": [
            "github-analyzer=github_analyzer.run:main",
        ],
    },
)
