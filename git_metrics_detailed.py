#!/usr/bin/env python3

import csv
import json
import sys
import requests
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Constants
API_URL = "https://api.github.com/graphql"

def main():
    """Main function to process GitHub contribution metrics with categories"""
    
    # Capture command line arguments
    if len(sys.argv) != 6:
        print("Usage: python script.py <access_token> <start_date> <end_date> <input_csv> <output_csv>")
        sys.exit(1)
    
    access_token = sys.argv[1]
    start_date = sys.argv[2]
    end_date = sys.argv[3]
    file_path_with_git_handles = sys.argv[4]
    file_path_for_results = sys.argv[5]
    
    # Read the CSV file with GitHub handles
    try:
        with open(file_path_with_git_handles, 'r', newline='', encoding='utf-8') as file:
            reader = csv.reader(file)
            records = list(reader)
            # Skip the header row (first row)
            if records:
                records = records[1:]
    except FileNotFoundError:
        print(f"Error: Could not find CSV file at {file_path_with_git_handles}")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return
    
    # Create and write to results file
    try:
        with open(file_path_for_results, 'w', newline='', encoding='utf-8') as results_file:
            # Write enhanced header row with contribution categories
            header = (
                "Name,GitHandle,Email,TotalContributions,CommitContributions,"
                "IssueContributions,PullRequestContributions,PullRequestReviewContributions,"
                "RepositoryContributions,RestrictedContributions\n"
            )
            results_file.write(header)
            
            for row in records:
                if len(row) < 9:
                    print(f"Warning: Skipping row with insufficient columns: {row}")
                    continue
                
                # Extract data from CSV row
                git_handle = row[0]
                name = row[1]
                email = row[8]  # Email is at index 8 (9th column)
                
                # Make API call to GitHub
                try:
                    response_data = get_user_contribution_from_github(
                        git_handle, start_date, end_date, access_token
                    )
                    
                    if response_data and 'data' in response_data:
                        # Check for errors in the API response
                        if 'errors' in response_data:
                            print(f"GitHub API errors for {git_handle}: {response_data['errors']}")
                        
                        contribution_stats = extract_contribution_details(response_data)
                        write_to_file(results_file, name, git_handle, email, contribution_stats)
                        print_contribution_summary(email, contribution_stats)
                    else:
                        print(f"Warning: No data received for user {git_handle}")
                        if response_data and 'errors' in response_data:
                            print(f"API Errors: {response_data['errors']}")
                        empty_stats = create_empty_contribution_stats()
                        write_to_file(results_file, name, git_handle, email, empty_stats)
                        
                except Exception as e:
                    print(f"Error getting user contribution for {git_handle}: {e}")
                    empty_stats = create_empty_contribution_stats()
                    write_to_file(results_file, name, git_handle, email, empty_stats)
    
    except Exception as e:
        print(f"Error creating/writing to results file: {e}")

def create_empty_contribution_stats() -> Dict[str, int]:
    """Create an empty contribution statistics dictionary"""
    return {
        'total': 0,
        'commits': 0,
        'issues': 0,
        'pull_requests': 0,
        'pull_request_reviews': 0,
        'repositories': 0,
        'restricted': 0
    }

def print_contribution_summary(email: str, stats: Dict[str, int]):
    """Print a detailed contribution summary for a user"""
    print(f"\nContribution Summary for {email}:")
    print(f"  Total Contributions: {stats['total']}")
    print(f"  Code Commits: {stats['commits']}")
    print(f"  Issues: {stats['issues']}")
    print(f"  Pull Requests: {stats['pull_requests']}")
    print(f"  PR Reviews: {stats['pull_request_reviews']}")
    print(f"  Repository Contributions: {stats['repositories']}")
    print(f"  Restricted Contributions: {stats['restricted']}")
    
    # Debug: Check if we're getting any non-zero values
    if all(value == 0 for value in stats.values()):
        print(f"  ⚠️  WARNING: All contributions are zero for {email}")
        print(f"     This might indicate: private repos, privacy settings, or date range issues")

def write_to_file(file_handle, name: str, git_handle: str, email: str, stats: Dict[str, int]):
    """Write a result row to the CSV file with detailed contribution categories"""
    result_row = (
        f"{name},{git_handle},{email},{stats['total']},"
        f"{stats['commits']},{stats['issues']},{stats['pull_requests']},"
        f"{stats['pull_request_reviews']},{stats['repositories']},{stats['restricted']}\n"
    )
    file_handle.write(result_row)
    file_handle.flush()  # Ensure data is written to disk

def get_user_contribution_from_github(
    git_handle: str, 
    start_date: str, 
    end_date: str, 
    access_token: str
) -> Optional[Dict[str, Any]]:
    """Fetch detailed user contribution data from GitHub GraphQL API"""
    
    # Simplified GraphQL query similar to original working version
    query = f"""
    {{ 
      user(login: "{git_handle}") {{
        email
        createdAt
        contributionsCollection(from: "{start_date}T00:00:00Z", to: "{end_date}T00:00:00Z") {{
          totalCommitContributions
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
          totalRepositoryContributions
          restrictedContributionsCount
          contributionCalendar {{
            totalContributions
          }}
        }}
      }}
    }}
    """
    
    # Create JSON payload
    json_data = {"query": query}
    
    # Set up headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Make the POST request
        response = requests.post(API_URL, json=json_data, headers=headers, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        # Parse JSON response
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error making request to GitHub API: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        return None

def extract_contribution_details(response_data: Dict[str, Any]) -> Dict[str, int]:
    """Extract detailed contribution statistics from GitHub API response"""
    try:
        contributions_collection = response_data["data"]["user"]["contributionsCollection"]
        
        # Debug: Print raw API response for troubleshooting
        print(f"Debug - Raw contribution data keys: {list(contributions_collection.keys())}")
        
        stats = {
            'total': int(contributions_collection["contributionCalendar"]["totalContributions"]),
            'commits': int(contributions_collection.get("totalCommitContributions", 0)),
            'issues': int(contributions_collection.get("totalIssueContributions", 0)),
            'pull_requests': int(contributions_collection.get("totalPullRequestContributions", 0)),
            'pull_request_reviews': int(contributions_collection.get("totalPullRequestReviewContributions", 0)),
            'repositories': int(contributions_collection.get("totalRepositoryContributions", 0)),
            'restricted': int(contributions_collection.get("restrictedContributionsCount", 0))
        }
        
        return stats
        
    except (KeyError, TypeError, ValueError) as e:
        print(f"Error extracting contribution details: {e}")
        print(f"Response data structure: {json.dumps(response_data, indent=2)}")
        return create_empty_contribution_stats()

def get_detailed_repository_breakdown(
    git_handle: str,
    start_date: str,
    end_date: str,
    access_token: str
) -> Optional[Dict[str, Any]]:
    """Get detailed breakdown by repository (optional additional function)"""
    
    query = f"""
    {{
      user(login: "{git_handle}") {{
        contributionsCollection(from: "{start_date}T00:00:00Z", to: "{end_date}T00:00:00Z") {{
          commitContributionsByRepository(maxRepositories: 50) {{
            repository {{
              name
              owner {{
                login
              }}
              primaryLanguage {{
                name
              }}
            }}
            contributions {{
              totalCount
            }}
            url
          }}
        }}
      }}
    }}
    """
    
    json_data = {"query": query}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(API_URL, json=json_data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error getting repository breakdown: {e}")
        return None

if __name__ == "__main__":
    main()
