#!/usr/bin/env python3

import csv
import json
import sys
import requests
from typing import Dict, Any, Optional

# Constants
API_URL = "https://api.github.com/graphql"

def main():
    """Main function to process GitHub contribution metrics"""
    
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
    except FileNotFoundError:
        print(f"Error: Could not find CSV file at {file_path_with_git_handles}")
        return
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return
    
    # Create and write to results file
    try:
        with open(file_path_for_results, 'w', newline='', encoding='utf-8') as results_file:
            # Write header row
            results_file.write("Name,GitHandle,Email,TotalContributions\n")
            
            for row in records:
                if len(row) < 8:
                    print(f"Warning: Skipping row with insufficient columns: {row}")
                    continue
                
                # Extract data from CSV row
                git_handle = row[0]
                name = row[1]
                email = row[7]  # Email is at index 7
                
                # Make API call to GitHub
                try:
                    response_data = get_user_contribution_from_github(
                        git_handle, start_date, end_date, access_token
                    )
                    
                    if response_data and 'data' in response_data:
                        total_contributions = extract_total_contributions(response_data)
                        write_to_file(results_file, name, git_handle, email, total_contributions)
                        print(f"Total Contributions by {email} = {total_contributions}")
                    else:
                        print(f"Warning: No data received for user {git_handle}")
                        write_to_file(results_file, name, git_handle, email, 0)
                        
                except Exception as e:
                    print(f"Error getting user contribution for {git_handle}: {e}")
                    write_to_file(results_file, name, git_handle, email, 0)
    
    except Exception as e:
        print(f"Error creating/writing to results file: {e}")

def write_to_file(file_handle, name: str, git_handle: str, email: str, total_contributions: int):
    """Write a result row to the CSV file"""
    result_row = f"{name},{git_handle},{email},{total_contributions}\n"
    file_handle.write(result_row)
    file_handle.flush()  # Ensure data is written to disk

def get_user_contribution_from_github(
    git_handle: str, 
    start_date: str, 
    end_date: str, 
    access_token: str
) -> Optional[Dict[str, Any]]:
    """Fetch user contribution data from GitHub GraphQL API"""
    
    # Define the GraphQL query
    query = f"""
    {{ 
      user(login: "{git_handle}") {{
        email
        createdAt
        contributionsCollection(from: "{start_date}T00:00:00Z", to: "{end_date}T00:00:00Z") {{
          contributionCalendar {{
            totalContributions
            weeks {{
              contributionDays {{
                weekday
                date 
                contributionCount 
                color
              }}
            }}
            months {{
              name
              year
              firstDay 
              totalWeeks 
            }}
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

def extract_total_contributions(response_data: Dict[str, Any]) -> int:
    """Extract total contributions from GitHub API response"""
    try:
        return int(
            response_data["data"]["user"]["contributionsCollection"]
            ["contributionCalendar"]["totalContributions"]
        )
    except (KeyError, TypeError, ValueError) as e:
        print(f"Error extracting total contributions: {e}")
        return 0

if __name__ == "__main__":
    main()
