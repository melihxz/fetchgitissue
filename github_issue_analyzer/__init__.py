"""
GitHub Issue Analyzer
=====================

A comprehensive tool to fetch and analyze GitHub issues from any public repository.

This package provides functionality to:
- Fetch all open and closed issues from a GitHub repository
- Summarize each issue in 2-3 sentences while preserving technical details
- Extract all comments for each issue
- Highlight potential duplicates based on title similarity
- Identify inconsistencies (e.g., conflicting labels)
- Detect potentially unaddressed errors (e.g., old open issues)
- Categorize issues into bugs, documentation, and coding errors
- Organize output clearly by issue number
"""

__version__ = "1.0.0"
__author__ = "GitHub Issue Analyzer"

from .fetch_github_issues import main

__all__ = ["main"]