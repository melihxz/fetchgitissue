from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh.readlines()]

setup(
    name="github-issue-analyzer",
    version="1.0.0",
    author="GitHub Issue Analyzer",
    author_email="example@example.com",
    description="A tool to fetch and analyze GitHub issues from any public repository",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/example/github-issue-analyzer",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=requirements,
    entry_points={
        'console_scripts': [
            'github-issue-analyzer=github_issue_analyzer.fetch_github_issues:main',
        ],
    },
)