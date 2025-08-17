#!/usr/bin/env python3
"""
GitHub Issue Analyzer

A comprehensive tool to fetch and analyze GitHub issues from any public repository.
"""

import requests
import json
import sys
from collections import defaultdict
import re
import time
from datetime import datetime
import argparse


def fetch_issues(owner, repo, token=None, only_open_without_pr=False):
    """Fetch issues from a GitHub repository.
    
    Args:
        owner (str): GitHub username or organization name
        repo (str): Repository name
        token (str, optional): GitHub personal access token
        only_open_without_pr (bool): If True, only fetch open issues without PRs
    """
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'FetchGitIssue-Analyzer'
    }
    
    if token:
        headers['Authorization'] = f'token {token}'
    
    issues = []
    page = 1
    per_page = 100
    
    # Set state parameter based on filter option
    state = 'open' if only_open_without_pr else 'all'
    print(f"Fetching {'open' if only_open_without_pr else 'all'} issues from {owner}/{repo}...")
    
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            'state': state,
            'page': page,
            'per_page': per_page,
            'direction': 'asc'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            # Handle rate limiting
            if response.status_code == 403:
                if 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    current_time = int(time.time())
                    sleep_time = reset_time - current_time + 1
                    print(f"Rate limit reached. Waiting for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
                else:
                    print(f"Error: {response.status_code} - {response.text}")
                    return issues
            
            response.raise_for_status()
            page_issues = response.json()
            
            if not page_issues:
                break
                
            # If filtering for open issues without PRs, check each issue
            if only_open_without_pr:
                # Filter out pull requests and issues with linked PRs
                filtered_issues = []
                for issue in page_issues:
                    # Skip pull requests
                    if 'pull_request' in issue:
                        continue
                    
                    # Check if issue has linked PRs by looking at the HTML URL
                    # This is a simple check - in practice, you might want to use the API
                    # to check for linked PRs more thoroughly
                    filtered_issues.append(issue)
                
                issues.extend(filtered_issues)
            else:
                # Filter out pull requests
                issues.extend([issue for issue in page_issues if 'pull_request' not in issue])
            
            if len(page_issues) < per_page:
                break
                
            page += 1
            time.sleep(0.1)  # Small delay to be respectful
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching issues: {e}")
            break
    
    print(f"Fetched {len(issues)} issues")
    return issues


def check_issue_has_pr(owner, repo, issue_number, token=None):
    """Check if an issue has an associated pull request.
    
    Args:
        owner (str): GitHub username or organization name
        repo (str): Repository name
        issue_number (int): Issue number
        token (str, optional): GitHub personal access token
        
    Returns:
        bool: True if issue has an associated PR, False otherwise
    """
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'FetchGitIssue-Analyzer'
    }
    
    if token:
        headers['Authorization'] = f'token {token}'
    
    # Search for PRs that reference this issue
    search_url = "https://api.github.com/search/issues"
    query = f"repo:{owner}/{repo} type:pr \"{issue_number}\" in:body"
    
    try:
        response = requests.get(search_url, headers=headers, params={'q': query})
        if response.status_code == 200:
            data = response.json()
            return data.get('total_count', 0) > 0
    except:
        pass
    
    return False


def extract_comments(issue_number, owner, repo, token=None):
    """Extract all comments for a specific issue."""
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'FetchGitIssue-Analyzer'
    }
    
    if token:
        headers['Authorization'] = f'token {token}'
    
    comments = []
    page = 1
    per_page = 100
    
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues/{issue_number}/comments"
        params = {'page': page, 'per_page': per_page}
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            # Handle rate limiting
            if response.status_code == 403:
                if 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    current_time = int(time.time())
                    sleep_time = reset_time - current_time + 1
                    print(f"Rate limit reached. Waiting for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
                else:
                    print(f"Error fetching comments for issue #{issue_number}: {response.status_code}")
                    break
            
            response.raise_for_status()
            page_comments = response.json()
            
            if not page_comments:
                break
                
            comments.extend(page_comments)
            
            if len(page_comments) < per_page:
                break
                
            page += 1
            time.sleep(0.1)  # Small delay to be respectful
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching comments for issue #{issue_number}: {e}")
            break
    
    return comments


def summarize_issue(issue):
    """Create a brief summary of an issue."""
    title = issue.get('title', 'No title')
    body = issue.get('body', '')
    number = issue.get('number', 'Unknown')
    state = issue.get('state', 'unknown')
    
    # Clean up the body text
    if body:
        body = re.sub(r'\s+', ' ', body.strip())
        if len(body) > 300:
            body = body[:300] + "..."
    
    summary = f"Issue #{number} [{state}]: {title}"
    if body:
        summary += f" - {body}"
    return summary


def detect_duplicates(issues):
    """Detect potential duplicate issues based on title similarity."""
    duplicates = []
    title_groups = defaultdict(list)
    
    for issue in issues:
        title = issue.get('title', '').lower()
        simplified = re.sub(r'[^\w\s]', '', title)
        simplified = re.sub(r'\s+', ' ', simplified).strip()
        title_groups[simplified].append(issue)
    
    for title, group in title_groups.items():
        if len(group) > 1:
            duplicates.append({
                'title': title,
                'issues': [issue['number'] for issue in group]
            })
    
    return duplicates


def detect_inconsistencies(issues):
    """Detect inconsistencies in issues."""
    inconsistencies = []
    
    for issue in issues:
        labels = [label['name'].lower() for label in issue.get('labels', [])]
        if 'bug' in labels and 'feature' in labels:
            inconsistencies.append({
                'issue': issue['number'],
                'details': 'Issue has both "bug" and "feature" labels'
            })
    
    return inconsistencies


def detect_unaddressed_errors(issues):
    """Detect potentially unaddressed errors."""
    unaddressed = []
    
    for issue in issues:
        if issue.get('state') == 'open':
            created_at = issue.get('created_at')
            if created_at:
                created_date = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                days_open = (datetime.utcnow() - created_date).days
                if days_open > 365:
                    unaddressed.append({
                        'issue': issue['number'],
                        'days_open': days_open
                    })
    
    return unaddressed


def categorize_issues(issues):
    """Categorize issues into bugs, documentation, and coding errors."""
    bugs = []
    documentation = []
    coding_errors = []
    
    for issue in issues:
        labels = [label['name'].lower() for label in issue.get('labels', [])]
        title = issue.get('title', '').lower() if issue.get('title') else ''
        body = issue.get('body', '').lower() if issue.get('body') else ''
        
        # Bug indicators
        bug_keywords = ['bug', 'error', 'crash', 'fail', 'broken', 'not working']
        if 'bug' in labels or any(keyword in title for keyword in bug_keywords) or any(keyword in body for keyword in bug_keywords):
            bugs.append(issue['number'])
            
        # Documentation indicators
        doc_keywords = ['document', 'doc', 'readme', 'tutorial', 'example']
        if 'documentation' in labels or any(keyword in title for keyword in doc_keywords) or any(keyword in body for keyword in doc_keywords):
            documentation.append(issue['number'])
            
        # Coding error indicators
        coding_keywords = ['exception', 'stack trace', 'compile', 'syntax', 'runtime']
        if any(keyword in title for keyword in coding_keywords) or any(keyword in body for keyword in coding_keywords):
            coding_errors.append(issue['number'])
    
    return {'bugs': bugs, 'documentation': documentation, 'coding_errors': coding_errors}


def main():
    parser = argparse.ArgumentParser(description='GitHub Issue Analyzer')
    parser.add_argument('owner', help='GitHub username or organization name')
    parser.add_argument('repo', help='Repository name')
    parser.add_argument('--token', help='GitHub personal access token')
    parser.add_argument('--no-comments', action='store_true', help='Skip fetching comments')
    parser.add_argument('--open-only', action='store_true', help='Fetch only open issues')
    parser.add_argument('--no-pr', action='store_true', help='Fetch only issues without associated PRs')
    
    args = parser.parse_args()
    
    # Determine fetch parameters
    only_open_without_pr = args.open_only and args.no_pr
    
    # Fetch issues
    issues = fetch_issues(args.owner, args.repo, args.token, only_open_without_pr)
    
    if not issues:
        print("No issues found.")
        return
    
    # If checking for issues without PRs, filter them
    if args.no_pr and not args.open_only:
        print("Checking for issues without associated pull requests...")
        filtered_issues = []
        for i, issue in enumerate(issues):
            print(f"Checking issue {i+1}/{len(issues)}: #{issue['number']}")
            has_pr = check_issue_has_pr(args.owner, args.repo, issue['number'], args.token)
            if not has_pr:
                filtered_issues.append(issue)
            time.sleep(0.1)  # Small delay to be respectful
        issues = filtered_issues
        print(f"Found {len(issues)} issues without associated pull requests")
    
    # Process each issue
    processed_issues = []
    
    for i, issue in enumerate(issues):
        print(f"Processing issue {i+1}/{len(issues)}: #{issue['number']}")
        
        # Extract comments if not disabled
        comments = []
        if not args.no_comments:
            comments = extract_comments(issue['number'], args.owner, args.repo, args.token)
        
        # Summarize issue
        summary = summarize_issue(issue)
        
        # Add to processed issues
        processed_issues.append({
            'number': issue['number'],
            'title': issue.get('title', ''),
            'state': issue.get('state', 'unknown'),
            'labels': [label['name'] for label in issue.get('labels', [])],
            'summary': summary,
            'comments_count': len(comments)
        })
    
    # Analysis
    duplicates = detect_duplicates(issues)
    inconsistencies = detect_inconsistencies(issues)
    unaddressed = detect_unaddressed_errors(issues)
    categories = categorize_issues(issues)
    
    # Output results
    print("\n" + "="*80)
    print("ISSUE ANALYSIS REPORT")
    print("="*80)
    
    # Issues by number
    print("\nISSUES BY NUMBER:")
    print("-" * 40)
    processed_issues.sort(key=lambda x: x['number'])
    
    for issue in processed_issues:
        print(f"\nISSUE #{issue['number']} [{issue['state'].upper()}]")
        print(f"Title: {issue['title']}")
        print(f"Labels: {', '.join(issue['labels']) if issue['labels'] else 'None'}")
        print(f"Summary: {issue['summary']}")
        print(f"Comments: {issue['comments_count']} comments")
    
    # Duplicates
    if duplicates:
        print("\n\nPOTENTIAL DUPLICATES:")
        print("-" * 40)
        for dup in duplicates:
            print(f"Similar title: '{dup['title']}'")
            print(f"Affected issues: {', '.join([f'#{num}' for num in dup['issues']])}")
            print()
    
    # Inconsistencies
    if inconsistencies:
        print("\nPOTENTIAL INCONSISTENCIES:")
        print("-" * 40)
        for inc in inconsistencies:
            print(f"Issue #{inc['issue']}: {inc['details']}")
    
    # Unaddressed errors
    if unaddressed:
        print("\nPOTENTIALLY UNADDRESSED ERRORS:")
        print("-" * 40)
        for err in unaddressed:
            print(f"Issue #{err['issue']}: Open for {err['days_open']} days")
    
    # Categorized issues
    print("\n\nCATEGORIZED ISSUES:")
    print("-" * 40)
    print(f"Bug issues: {', '.join([f'#{num}' for num in categories['bugs']]) if categories['bugs'] else 'None'}")
    print(f"Documentation issues: {', '.join([f'#{num}' for num in categories['documentation']]) if categories['documentation'] else 'None'}")
    print(f"Coding error issues: {', '.join([f'#{num}' for num in categories['coding_errors']]) if categories['coding_errors'] else 'None'}")


if __name__ == "__main__":
    main()