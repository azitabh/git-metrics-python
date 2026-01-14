#!/usr/bin/env python3

import csv
import json
import sys
import requests
from typing import Dict, Any, Optional, List
from datetime import datetime

# Constants
API_URL = "https://api.github.com/graphql"
REST_API_URL = "https://api.github.com"

def main():
    """Main function to process GitHub contribution metrics with categories"""
    
    # Capture command line arguments
    if len(sys.argv) < 6 or len(sys.argv) > 7:
        print("Usage: python script.py <access_token> <organization_name> <start_date> <end_date> <output_csv> [email_domain]")
        print("Example: python script.py ghp_xxxx my-org 2024-01-01 2024-12-31 results.csv")
        print("Example with email domain: python script.py ghp_xxxx my-org 2024-01-01 2024-12-31 results.csv sharechat.com")
        sys.exit(1)
    
    access_token = sys.argv[1]
    organization_name = sys.argv[2]
    start_date = sys.argv[3]
    end_date = sys.argv[4]
    file_path_for_results = sys.argv[5]
    email_domain = sys.argv[6] if len(sys.argv) == 7 else None
    
    print(f"Fetching members from organization: {organization_name}")
    
    # Fetch organization members with SAML identities from GitHub API
    org_members = get_organization_members_with_saml(organization_name, access_token)
    
    if not org_members:
        print(f"Error: No members found for organization '{organization_name}'")
        print("Please check:")
        print("  1. Organization name is correct")
        print("  2. Access token has 'read:org' scope")
        print("  3. You have access to view organization members")
        sys.exit(1)
    
    print(f"Found {len(org_members)} members in organization '{organization_name}'")
    print(f"Members: {[member['login'] for member in org_members]}")
    
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
            
            for member in org_members:
                git_handle = member['login']
                saml_email = member.get('saml_name_id', '')
                
                # Name might already be in member dict from GraphQL, otherwise fetch
                if 'name' in member and member['name']:
                    name = member['name']
                else:
                    # Get user details to fetch name
                    user_details = get_user_details(git_handle, access_token)
                    name = user_details.get('name', git_handle) if user_details else git_handle
                
                # Priority: SAML email (company email) > generated email (if domain provided)
                if saml_email:
                    email = saml_email
                elif email_domain:
                    email = f"{git_handle}@{email_domain}"
                    print(f"  Generated email for {git_handle}: {email}")
                else:
                    email = ''
                
                print(f"\nProcessing user: {git_handle} ({name}) - Email: {email or 'N/A'}")
                
                # Make API call to GitHub for contributions
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
                        print_contribution_summary(git_handle, contribution_stats)
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
            
            print(f"\n✅ Results written to: {file_path_for_results}")
    
    except Exception as e:
        print(f"Error creating/writing to results file: {e}")

def get_organization_members_with_saml(org_name: str, access_token: str) -> List[Dict[str, Any]]:
    """
    Fetch all members of a GitHub organization with SAML identities using GraphQL API
    
    Args:
        org_name: Name of the GitHub organization
        access_token: GitHub personal access token with 'read:org' and 'admin:org' scope
    
    Returns:
        List of member dictionaries with 'login' and 'saml_name_id' (company email)
    """
    
    print("Fetching organization members with SAML identities via GraphQL...")
    
    # GraphQL query to get SAML identities
    query = """
    query($login: String!, $cursor: String) {
      organization(login: $login) {
        samlIdentityProvider {
          externalIdentities(first: 100, after: $cursor) {
            totalCount
            pageInfo {
              hasNextPage
              endCursor
            }
            edges {
              node {
                user {
                  login
                  name
                }
                samlIdentity {
                  nameId
                }
                guid
              }
            }
          }
        }
      }
    }
    """
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    members_dict = {}
    cursor = None
    page = 1
    
    while True:
        variables = {
            "login": org_name,
            "cursor": cursor
        }
        
        json_data = {
            "query": query,
            "variables": variables
        }
        
        try:
            response = requests.post(API_URL, json=json_data, headers=headers, timeout=30)
            
            if response.status_code == 401:
                print("Authentication failed. Please check your access token")
                break
            elif response.status_code != 200:
                print(f"Error fetching SAML identities: {response.status_code}")
                print(f"Response: {response.text}")
                break
            
            data = response.json()
            
            # Check for errors
            if 'errors' in data:
                print(f"GraphQL errors: {data['errors']}")
                # Check if it's a SAML not configured error
                for error in data['errors']:
                    if 'samlIdentityProvider' in error.get('message', ''):
                        print("\n⚠️  SAML SSO may not be configured for this organization or you don't have admin:org permission")
                        print("   Falling back to basic member list without SAML emails...")
                return get_organization_members_basic(org_name, access_token)
            
            # Extract SAML identities
            org_data = data.get('data', {}).get('organization', {})
            saml_provider = org_data.get('samlIdentityProvider', {})
            
            if not saml_provider:
                print("\n⚠️  No SAML identity provider found for this organization")
                print("   Falling back to basic member list without SAML emails...")
                return get_organization_members_basic(org_name, access_token)
            
            external_identities = saml_provider.get('externalIdentities', {})
            edges = external_identities.get('edges', [])
            
            if not edges and page == 1:
                print("\n⚠️  No SAML identities found (organization may not use SAML SSO)")
                print("   Falling back to basic member list without SAML emails...")
                return get_organization_members_basic(org_name, access_token)
            
            # Process identities
            for edge in edges:
                node = edge.get('node', {})
                user = node.get('user', {})
                saml_identity = node.get('samlIdentity', {})
                
                if user:
                    login = user.get('login')
                    name = user.get('name', login)
                    saml_name_id = saml_identity.get('nameId', '')
                    
                    members_dict[login] = {
                        'login': login,
                        'name': name,
                        'saml_name_id': saml_name_id
                    }
                    
                    if saml_name_id:
                        print(f"  ✓ {login}: {saml_name_id}")
            
            # Check for more pages
            page_info = external_identities.get('pageInfo', {})
            if page_info.get('hasNextPage'):
                cursor = page_info.get('endCursor')
                page += 1
                print(f"Fetching page {page}...")
            else:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"Error making request to GitHub API: {e}")
            break
        except (KeyError, TypeError) as e:
            print(f"Error parsing response: {e}")
            print(f"Response: {json.dumps(data, indent=2)}")
            break
    
    members_list = list(members_dict.values())
    print(f"\n✓ Found {len(members_list)} members with SAML identities")
    return members_list

def get_organization_members_basic(org_name: str, access_token: str) -> List[Dict[str, Any]]:
    """
    Fetch basic organization members list (fallback when SAML is not available)
    
    Args:
        org_name: Name of the GitHub organization
        access_token: GitHub personal access token with 'read:org' scope
    
    Returns:
        List of member dictionaries with 'login' (no SAML data)
    """
    headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    members = []
    page = 1
    
    print("Fetching basic organization member list...")
    
    while True:
        url = f'{REST_API_URL}/orgs/{org_name}/members'
        params = {'page': page, 'per_page': 100}
        
        try:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 404:
                print(f"Organization '{org_name}' not found or you don't have access")
                break
            elif response.status_code == 401:
                print("Authentication failed. Please check your access token")
                break
            elif response.status_code != 200:
                print(f"Error fetching members: {response.status_code}")
                print(f"Response: {response.text}")
                break
            
            data = response.json()
            
            if not data:
                break
            
            # Add saml_name_id as empty for basic members
            for member in data:
                member['saml_name_id'] = ''
                members.append(member)
            
            page += 1
            print(f"  Fetched page {page-1}: {len(data)} members")
            
        except requests.exceptions.RequestException as e:
            print(f"Error making request to GitHub API: {e}")
            break
    
    return members

def get_user_details(username: str, access_token: str) -> Optional[Dict[str, Any]]:
    """
    Fetch user details (name, email, etc.) using REST API
    
    Args:
        username: GitHub username
        access_token: GitHub personal access token
    
    Returns:
        Dictionary with user details or None if error
    """
    headers = {
        'Authorization': f'token {access_token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    url = f'{REST_API_URL}/users/{username}'
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Warning: Could not fetch details for {username}: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching user details for {username}: {e}")
        return None

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

def print_contribution_summary(username: str, stats: Dict[str, int]):
    """Print a detailed contribution summary for a user"""
    print(f"Contribution Summary for {username}:")
    print(f"  Total Contributions: {stats['total']}")
    print(f"  Code Commits: {stats['commits']}")
    print(f"  Issues: {stats['issues']}")
    print(f"  Pull Requests: {stats['pull_requests']}")
    print(f"  PR Reviews: {stats['pull_request_reviews']}")
    print(f"  Repository Contributions: {stats['repositories']}")
    print(f"  Restricted Contributions: {stats['restricted']}")
    
    # Debug: Check if we're getting any non-zero values
    if all(value == 0 for value in stats.values()):
        print(f"  ⚠️  WARNING: All contributions are zero for {username}")
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

