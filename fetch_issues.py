#!/usr/bin/env python3

import requests
import json
import sys
from collections import defaultdict
import re
import time

def fetch_issues(owner, repo, token=None):
    """
    Fetch all issues (open and closed) from a GitHub repository.
    """
    headers = {
        'Accept': 'application/vnd.github.v3+json',
        'User-Agent': 'FetchGitIssue-Analyzer'
    }
    
    if token:
        headers['Authorization'] = f'token {token}'
    
    issues = []
    page = 1
    per_page = 100  # Maximum allowed by GitHub API
    
    print(f"Fetching issues from {owner}/{repo}...")
    
    while True:
        url = f"https://api.github.com/repos/{owner}/{repo}/issues"
        params = {
            'state': 'all',  # Get both open and closed issues
            'page': page,
            'per_page': per_page,
            'direction': 'asc'
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            # Check rate limit
            if response.status_code == 403:
                # Check if it's a rate limit error
                if 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    current_time = int(time.time())
                    sleep_time = reset_time - current_time + 1  # Add 1 second buffer
                    print(f"Rate limit exceeded. Waiting for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue  # Retry the same page
                else:
                    print(f"HTTP Error fetching issues: {response.status_code} - {response.text}")
                    sys.exit(1)
            
            response.raise_for_status()
            
            page_issues = response.json()
            
            # If no issues are returned, we've fetched all
            if not page_issues:
                break
                
            issues.extend(page_issues)
            
            # If we got fewer issues than requested, this is the last page
            if len(page_issues) < per_page:
                break
                
            page += 1
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
            
        except requests.exceptions.HTTPError as e:
            if response.status_code == 422:
                # This might happen if we've gone past the last page
                print("Reached end of issues (422 error, likely no more pages)")
                break
            else:
                print(f"HTTP Error fetching issues: {e}")
                sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching issues: {e}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            sys.exit(1)
    
    # Filter out pull requests (they have 'pull_request' key)
    issues = [issue for issue in issues if 'pull_request' not in issue]
    
    print(f"Fetched {len(issues)} issues")
    return issues

def extract_comments(issue_number, owner, repo, token=None):
    """
    Extract all comments for a specific issue.
    """
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
        params = {
            'page': page,
            'per_page': per_page
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            
            # Check rate limit
            if response.status_code == 403:
                # Check if it's a rate limit error
                if 'X-RateLimit-Remaining' in response.headers and response.headers['X-RateLimit-Remaining'] == '0':
                    reset_time = int(response.headers['X-RateLimit-Reset'])
                    current_time = int(time.time())
                    sleep_time = reset_time - current_time + 1  # Add 1 second buffer
                    print(f"Rate limit exceeded. Waiting for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue  # Retry the same page
                else:
                    print(f"HTTP Error fetching comments for issue #{issue_number}: {response.status_code} - {response.text}")
                    break
            
            response.raise_for_status()
            
            page_comments = response.json()
            
            if not page_comments:
                break
                
            comments.extend(page_comments)
            
            if len(page_comments) < per_page:
                break
                
            page += 1
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching comments for issue #{issue_number}: {e}")
            break
    
    return comments

def summarize_issue(issue):
    """
    Create a brief 2-3 sentence summary of an issue while preserving technical details.
    """
    title = issue.get('title', 'No title')
    body = issue.get('body', '')
    number = issue.get('number', 'Unknown')
    state = issue.get('state', 'unknown')
    
    # Clean up the body text
    if body:
        # Remove extra whitespace and newlines
        body = re.sub(r'\s+', ' ', body.strip())
        # Truncate if too long for summary
        if len(body) > 500:
            body = body[:500] + "..."
    
    # Create summary
    summary = f"Issue #{number} [{state}]: {title}. "
    
    if body:
        summary += f"Description: {body} "
    else:
        summary += "No description provided. "
    
    return summary.strip()

def detect_duplicates(issues):
    """
    Detect potential duplicate issues based on title similarity.
    """
    duplicates = []
    title_groups = defaultdict(list)
    
    # Group issues by similar titles
    for issue in issues:
        title = issue.get('title', '').lower()
        # Simplify title for comparison
        simplified = re.sub(r'[^\w\s]', '', title)
        simplified = re.sub(r'\s+', ' ', simplified).strip()
        title_groups[simplified].append(issue)
    
    # Find groups with multiple issues
    for title, group in title_groups.items():
        if len(group) > 1:
            duplicates.append({
                'title': title,
                'issues': [issue['number'] for issue in group]
            })
    
    return duplicates

def detect_inconsistencies(issues):
    """
    Detect inconsistencies in issues (e.g., conflicting labels, status).
    """
    inconsistencies = []
    
    # Check for issues with both "bug" and "feature" labels
    for issue in issues:
        labels = [label['name'].lower() for label in issue.get('labels', [])]
        if 'bug' in labels and 'feature' in labels:
            inconsistencies.append({
                'issue': issue['number'],
                'type': 'conflicting_labels',
                'details': 'Issue has both "bug" and "feature" labels'
            })
    
    return inconsistencies

def detect_unaddressed_errors(issues):
    """
    Detect potentially unaddressed errors based on issue patterns.
    """
    unaddressed = []
    
    # Check for old open issues
    for issue in issues:
        if issue.get('state') == 'open':
            # Check if issue is old (more than 1 year old)
            import datetime
            created_at = issue.get('created_at')
            if created_at:
                created_date = datetime.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ")
                if (datetime.datetime.utcnow() - created_date).days > 365:
                    unaddressed.append({
                        'issue': issue['number'],
                        'type': 'old_unaddressed',
                        'age_days': (datetime.datetime.utcnow() - created_date).days
                    })
    
    return unaddressed

def categorize_issues(issues):
    """
    Categorize issues into bugs, documentation, and coding errors.
    """
    bugs = []
    documentation = []
    coding_errors = []
    
    for issue in issues:
        labels = [label['name'].lower() for label in issue.get('labels', [])]
        title = issue.get('title', '').lower() if issue.get('title') else ''
        body = issue.get('body', '').lower() if issue.get('body') else ''
        
        # Check for bug indicators
        bug_keywords = ['bug', 'error', 'crash', 'fail', 'broken', 'not working']
        if 'bug' in labels or any(keyword in title for keyword in bug_keywords) or any(keyword in body for keyword in bug_keywords):
            bugs.append(issue['number'])
            
        # Check for documentation indicators
        doc_keywords = ['document', 'doc', 'readme', 'tutorial', 'example']
        if 'documentation' in labels or any(keyword in title for keyword in doc_keywords) or any(keyword in body for keyword in doc_keywords):
            documentation.append(issue['number'])
            
        # Check for coding error indicators
        coding_keywords = ['exception', 'stack trace', 'compile', 'syntax', 'runtime']
        if any(keyword in title for keyword in coding_keywords) or any(keyword in body for keyword in coding_keywords):
            coding_errors.append(issue['number'])
    
    return {
        'bugs': bugs,
        'documentation': documentation,
        'coding_errors': coding_errors
    }

def main():
    if len(sys.argv) < 3:
        print("Usage: python fetch_issues.py <owner> <repo> [token]")
        print("Example: python fetch_issues.py octocat Hello-World")
        sys.exit(1)
    
    owner = sys.argv[1]
    repo = sys.argv[2]
    token = sys.argv[3] if len(sys.argv) > 3 else None
    
    # Fetch all issues
    issues = fetch_issues(owner, repo, token)
    
    if not issues:
        print("No issues found in the repository.")
        return
    
    # Process each issue
    processed_issues = []
    
    for i, issue in enumerate(issues):
        print(f"Processing issue {i+1}/{len(issues)}: #{issue['number']}")
        
        # Extract comments
        comments = extract_comments(issue['number'], owner, repo, token)
        
        # Summarize issue
        summary = summarize_issue(issue)
        
        # Add to processed issues
        processed_issues.append({
            'number': issue['number'],
            'title': issue.get('title', ''),
            'state': issue.get('state', 'unknown'),
            'labels': [label['name'] for label in issue.get('labels', [])],
            'summary': summary,
            'comments_count': len(comments),
            'comments': [{'user': c['user']['login'], 'body': c['body']} for c in comments]
        })
        
        # Add a small delay to avoid rate limiting
        time.sleep(0.1)
    
    # Detect duplicates
    duplicates = detect_duplicates(issues)
    
    # Detect inconsistencies
    inconsistencies = detect_inconsistencies(issues)
    
    # Detect unaddressed errors
    unaddressed = detect_unaddressed_errors(issues)
    
    # Categorize issues
    categories = categorize_issues(issues)
    
    # Output results
    print("\n" + "="*80)
    print("ISSUE ANALYSIS REPORT")
    print("="*80)
    
    # Print issues organized by number
    print("\nISSUES BY NUMBER:")
    print("-" * 40)
    
    # Sort issues by number
    processed_issues.sort(key=lambda x: x['number'])
    
    for issue in processed_issues:
        print(f"\nISSUE #{issue['number']} [{issue['state'].upper()}]")
        print(f"Title: {issue['title']}")
        print(f"Labels: {', '.join(issue['labels']) if issue['labels'] else 'None'}")
        print(f"Summary: {issue['summary']}")
        print(f"Comments: {issue['comments_count']} comments")
    
    # Print duplicates section
    if duplicates:
        print("\n\nPOTENTIAL DUPLICATES:")
        print("-" * 40)
        for dup in duplicates:
            print(f"Similar title: '{dup['title']}'")
            print(f"Affected issues: {', '.join([f'#{num}' for num in dup['issues']])}")
            print()
    
    # Print inconsistencies section
    if inconsistencies:
        print("\nPOTENTIAL INCONSISTENCIES:")
        print("-" * 40)
        for inc in inconsistencies:
            print(f"Issue #{inc['issue']}: {inc['details']}")
    
    # Print unaddressed errors section
    if unaddressed:
        print("\nPOTENTIALLY UNADDRESSED ERRORS:")
        print("-" * 40)
        for err in unaddressed:
            print(f"Issue #{err['issue']}: Open for {err['age_days']} days")
    
    # Print categorized issues
    print("\n\nCATEGORIZED ISSUES:")
    print("-" * 40)
    print(f"Bug issues: {', '.join([f'#{num}' for num in categories['bugs']]) if categories['bugs'] else 'None'}")
    print(f"Documentation issues: {', '.join([f'#{num}' for num in categories['documentation']]) if categories['documentation'] else 'None'}")
    print(f"Coding error issues: {', '.join([f'#{num}' for num in categories['coding_errors']]) if categories['coding_errors'] else 'None'}")

if __name__ == "__main__":
    main()