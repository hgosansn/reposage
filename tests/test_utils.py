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

def create_mock_file_content(path, content=None, size=100):
    """Create a mock file content for testing."""
    mock_file = MagicMock()
    mock_file.path = path
    mock_file.type = "file"
    mock_file.size = size
    
    if content is None:
        default_content = f"def old_function():\n    pass"
        mock_file.content = base64.b64encode(default_content.encode('utf-8'))
    else:
        mock_file.content = base64.b64encode(content.encode('utf-8'))
    
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
        size=path_obj.stat().st_size
    )

def mock_openrouter_response(success=True, with_changes=True):
    """Create a mock response from OpenRouter API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    if success:
        if with_changes:
            mock_response.json.return_value = {
                'choices': [{
                    'message': {
                        'content': '''{
                            "analysis": {
                                "code_quality": "Good code quality",
                                "best_practices": "Follows best practices",
                                "potential_bugs": "No potential bugs found",
                                "performance": "Good performance"
                            },
                            "suggested_changes": [{
                                "original_code": "def old_function():",
                                "improved_code": "def improved_function():",
                                "explanation": "Better function name",
                                "test_code": "def test_improved_function():\\n    assert True"
                            }],
                            "summary": "Improved function naming"
                        }'''
                    }
                }]
            }
        else:
            mock_response.json.return_value = {
                'choices': [{
                    'message': {
                        'content': '''{
                            "analysis": {
                                "code_quality": "Excellent code quality",
                                "best_practices": "Follows best practices",
                                "potential_bugs": "No potential bugs found",
                                "performance": "Good performance"
                            },
                            "suggested_changes": [],
                            "summary": "No improvements needed"
                        }'''
                    }
                }]
            }
    else:
        mock_response.status_code = 400
        mock_response.text = "Bad request"
    
    return mock_response

def setup_mock_github_repo(mock_repo):
    """Set up a mock GitHub repository with common operations."""
    # Mock branch
    mock_branch = MagicMock()
    mock_branch.commit.sha = 'fake_commit_sha'
    mock_repo.get_branch.return_value = mock_branch
    
    # Mock file content
    mock_file = create_mock_file_content('test.py')
    mock_repo.get_contents.return_value = mock_file
    
    # Mock create_git_ref
    mock_repo.create_git_ref.return_value = None
    
    # Mock update_file
    mock_repo.update_file.return_value = None
    
    # Mock create_file
    mock_repo.create_file.return_value = None
    
    # Mock create_pull
    mock_pr = MagicMock()
    mock_pr.html_url = 'https://github.com/user/repo/pull/1'
    mock_repo.create_pull.return_value = mock_pr
    
    return mock_repo
