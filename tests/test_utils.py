"""
Test utilities for RepoSage tests.
Contains common mock functions and classes used in both unit and integration tests.
"""

import base64
import json
from unittest.mock import MagicMock, PropertyMock
from pathlib import Path

class MockResponse:
    """Mock response object for requests."""
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json_data = json_data
        self.text = json.dumps(json_data)
    
    def json(self):
        return self._json_data

def create_mock_file_content(path, content="def old_function():\n    pass", sha=None, file_size=None):
    """
    Create a mock file content object that mimics GitHub API response.
    
    Args:
        path (str): File path
        content (str): File content as string
        sha (str, optional): Git SHA for the file
        file_size (int, optional): Size of the file in bytes
    
    Returns:
        MagicMock: Mock file content object
    """
    mock_file = MagicMock()
    mock_file.path = path
    mock_file.type = "file"
    mock_file.size = file_size or len(content)
    
    # Set SHA if provided
    if sha:
        mock_file.sha = sha
    
    # Encode content to base64 as GitHub API would return
    encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    
    # Configure the mock to return the encoded content when content property is accessed
    type(mock_file).content = PropertyMock(return_value=encoded_content)
    
    # Also provide decoded_content for convenience
    mock_file.decoded_content = content.encode('utf-8')
    
    return mock_file

def create_mock_file_from_path(file_path, sha=None):
    """
    Create a mock file content object from an actual file path.
    
    Args:
        file_path (Path or str): Path to the file
        sha (str, optional): Git SHA for the file
    
    Returns:
        MagicMock: Mock file content object
    """
    path_obj = Path(file_path)
    content = path_obj.read_text()
    return create_mock_file_content(
        path=str(path_obj.name),
        content=content,
        sha=sha,
        file_size=path_obj.stat().st_size
    )

def mock_openrouter_response(file_path=None, status_code=200, suggested_changes=None):
    """
    Create a mock OpenRouter API response.
    
    Args:
        file_path (str, optional): File path to customize the response
        status_code (int): HTTP status code
        suggested_changes (list, optional): List of suggested changes
    
    Returns:
        MockResponse: Mock response object
    """
    # Default suggested changes if none provided
    if suggested_changes is None:
        if '.py' in (file_path or ''):
            suggested_changes = [{
                "original_code": "def f(x, y):",
                "improved_code": "def multiply(x, y):",
                "explanation": "Improved function name to be more descriptive"
            }]
        elif '.js' in (file_path or ''):
            suggested_changes = [{
                "original_code": "function calc(a, b) {",
                "improved_code": "function multiply(a, b) {",
                "explanation": "Improved function name"
            }]
        else:
            suggested_changes = []
    
    # Create response content
    response_content = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "analysis": {
                        "code_quality": "Analysis of code quality",
                        "best_practices": "Analysis of best practices",
                        "potential_bugs": "Analysis of potential bugs",
                        "performance": "Analysis of performance"
                    },
                    "suggested_changes": suggested_changes,
                    "summary": "Summary of improvements"
                })
            }
        }]
    }
    
    return MockResponse(status_code, response_content)

def setup_mock_github_repo(mock_github, files=None):
    """
    Set up a mock GitHub repository with the specified files.
    
    Args:
        mock_github: The mocked Github instance
        files (list, optional): List of mock file content objects
    
    Returns:
        tuple: (mock_repo, mock_branch)
    """
    # Create mock repo and branch
    mock_repo = MagicMock()
    mock_branch = MagicMock()
    mock_branch.commit.sha = 'fake_commit_sha'
    mock_repo.get_branch.return_value = mock_branch
    mock_github.return_value.get_repo.return_value = mock_repo
    
    # Set up PR creation
    mock_pr = MagicMock()
    mock_pr.html_url = 'https://github.com/user/repo/pull/1'
    mock_repo.create_pull.return_value = mock_pr
    
    # Set up file contents if provided
    if files:
        def mock_get_contents(path, ref=None):
            if path == '':
                return files
            
            # Return specific file if path matches
            for file in files:
                if file.path == path:
                    return file
            
            return None
        
        mock_repo.get_contents.side_effect = mock_get_contents
    
    return mock_repo, mock_branch
