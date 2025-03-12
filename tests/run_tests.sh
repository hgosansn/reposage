#!/bin/bash

# Change to the tests directory
cd "$(dirname "$0")"

# Set up test environment variables
export GITHUB_TOKEN="test_github_token"
export GITHUB_REPOSITORY="test_user/test_repo"
export OPENROUTER_API_KEY="test_openrouter_api_key"

echo "Running unit tests..."
python -m unittest test_bot.py

echo -e "\nRunning integration tests..."
python -m unittest integration_test.py

# Clean up environment variables
unset GITHUB_TOKEN
unset GITHUB_REPOSITORY
unset OPENROUTER_API_KEY
