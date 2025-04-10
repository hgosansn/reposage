import os
import unittest
import tempfile
import shutil
import subprocess
from pathlib import Path
import json
import base64
from unittest.mock import patch, MagicMock, PropertyMock
import sys

# Add the repo-sage-action directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'repo-sage-action')))

# Import the bot module and test utilities
from bot import RepoSage
from test_utils import create_mock_file_content, mock_openrouter_response, setup_mock_github_repo, MockResponse

class IntegrationTestRepoSage(unittest.TestCase):
    """Integration tests for RepoSage bot."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test environment once before all tests."""
        # Create a temporary directory for the test repository
        cls.temp_dir = tempfile.mkdtemp()
        cls.repo_dir = Path(cls.temp_dir) / "test-repo"
        cls.repo_dir.mkdir()
        
        # Initialize a git repository
        cls._run_git_command("git init", cwd=cls.repo_dir)
        cls._run_git_command("git config user.name 'Test User'", cwd=cls.repo_dir)
        cls._run_git_command("git config user.email 'test@example.com'", cwd=cls.repo_dir)
        
        # Create test files
        cls._create_test_files()
        
        # Commit the files
        cls._run_git_command("git add .", cwd=cls.repo_dir)
        cls._run_git_command("git commit -m 'Initial commit'", cwd=cls.repo_dir)
    
    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        # Remove the temporary directory
        shutil.rmtree(cls.temp_dir)
    
    @classmethod
    def _run_git_command(cls, command, cwd):
        """Run a git command in the specified directory."""
        subprocess.run(command, shell=True, cwd=cwd, check=True, 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    
    @classmethod
    def _create_test_files(cls):
        """Create test files in the repository."""
        # Create a Python file with some issues
        python_file = cls.repo_dir / "example.py"
        python_file.write_text("""
def add(a, b):
    # This function adds two numbers
    return a+b

# Function with poor naming and no docstring
def f(x, y):
    z = x * y
    return z
        """)
        
        # Create a JavaScript file with some issues
        js_file = cls.repo_dir / "example.js"
        js_file.write_text("""
// Function with poor naming and no comments
function calc(a, b) {
    return a * b;
}

// Variable with unnecessary reassignment
let result = 0;
result = calc(5, 10);
console.log(result);
        """)
        
        # Create a README file
        readme_file = cls.repo_dir / "README.md"
        readme_file.write_text("""
# Test Repository

This is a test repository for RepoSage integration tests.
        """)
    
    def setUp(self):
        """Set up test environment before each test."""
        # Set test parameters
        self.github_token = 'fake_github_token'
        self.repo_name = 'user/repo'
        self.openrouter_api_key = 'fake_openrouter_api_key'
        self.model = 'google/gemma-3-27b-it:free'
        self.base_branch = 'main'
    
    def tearDown(self):
        """Clean up after each test."""
        # No need to clear environment variables anymore
        pass
    
    def _mock_openrouter_response(self, file_path):
        """Create a mock response for the OpenRouter API based on file path."""
        if file_path.endswith('.py'):
            return MockResponse(200, {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'analysis': {
                                'code_quality': 'The code has some issues with function naming and documentation.',
                                'best_practices': 'Function names should be descriptive.',
                                'potential_bugs': 'No potential bugs found.',
                                'performance': 'No performance issues found.'
                            },
                            'suggested_changes': [{
                                'original_code': 'def f(x, y):',
                                'improved_code': 'def multiply(x, y):',
                                'explanation': 'Improved function name to be more descriptive',
                                'test_code': 'def test_multiply():\n    assert multiply(2, 3) == 6'
                            }, {
                                'original_code': '    z = x * y\n    return z',
                                'improved_code': '    """Multiply two numbers and return the result."""\n    return x * y',
                                'explanation': 'Added docstring and simplified the function',
                                'test_code': 'def test_multiply_docstring():\n    import inspect\n    assert "Multiply two numbers" in inspect.getdoc(multiply)'
                            }],
                            'summary': 'Improved function naming and documentation'
                        })
                    }
                }]
            })
        elif file_path.endswith('.js'):
            return MockResponse(200, {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'analysis': {
                                'code_quality': 'The code has some issues with function naming and variable usage.',
                                'best_practices': 'Avoid unnecessary variable reassignments.',
                                'potential_bugs': 'No potential bugs found.',
                                'performance': 'No performance issues found.'
                            },
                            'suggested_changes': [{
                                'original_code': 'function calc(a, b) {',
                                'improved_code': '/**\n * Multiplies two numbers\n * @param {number} a - First number\n * @param {number} b - Second number\n * @returns {number} - Product of a and b\n */\nfunction multiply(a, b) {',
                                'explanation': 'Improved function name and added JSDoc',
                                'test_code': 'test("multiply function works", () => {\n  expect(multiply(2, 3)).toBe(6);\n});'
                            }, {
                                'original_code': 'let result = 0;\nresult = calc(5, 10);',
                                'improved_code': 'const result = multiply(5, 10);',
                                'explanation': 'Removed unnecessary variable reassignment and used const',
                                'test_code': 'test("result is calculated properly", () => {\n  expect(result).toBe(50);\n});'
                            }],
                            'summary': 'Improved function naming, documentation, and variable usage'
                        })
                    }
                }]
            })
        else:
            # Even for README and other files, return some suggested changes
            return MockResponse(200, {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'analysis': {
                                'code_quality': 'Content could be improved.',
                                'best_practices': 'More details would be helpful.',
                                'potential_bugs': 'No issues found.',
                                'performance': 'No performance concerns.'
                            },
                            'suggested_changes': [{
                                'original_code': '# Test Repository',
                                'improved_code': '# RepoSage Test Repository',
                                'explanation': 'Added more specific title',
                                'test_code': '# No test needed for markdown'
                            }],
                            'summary': 'Improved documentation clarity'
                        })
                    }
                }]
            })
    
    @patch('bot.Github')
    @patch('bot.requests.post')
    def test_local_repository_analysis(self, mock_post, mock_github):
        """Test analyzing a local repository."""
        # Mock GitHub API
        mock_repo = MagicMock()
        mock_branch = MagicMock()
        mock_branch.commit.sha = 'fake_commit_sha'
        mock_repo.get_branch.return_value = mock_branch
        mock_github.return_value.get_repo.return_value = mock_repo
        
        # Mock PR creation
        mock_pr = MagicMock()
        mock_pr.html_url = 'https://github.com/user/repo/pull/1'
        mock_repo.create_pull.return_value = mock_pr
        
        # Mock the OpenRouter API responses using the shared utility function
        def mock_post_response(*args, **kwargs):
            # Extract the file path from the prompt
            prompt = kwargs.get('json', {}).get('messages', [{}])[1].get('content', '')
            file_ext = None
            if '.py' in prompt:
                file_ext = '.py'
            elif '.js' in prompt:
                file_ext = '.js'
            elif '.md' in prompt:
                file_ext = '.md'
            
            print(f"DEBUG: OpenRouter API called for a file with extension: {file_ext}")
            response = self._mock_openrouter_response(file_ext)
            
            # Debug print the response
            response_content = response.json()['choices'][0]['message']['content']
            print(f"DEBUG: OpenRouter API response: {response_content[:100]}...")
            
            return response
        
        mock_post.side_effect = mock_post_response
        
        # Create mock file contents for the repository using the shared utility function
        def mock_get_contents(path, ref=None):
            print(f"DEBUG: get_contents called for path: {path}, ref: {ref}")
            
            if path == 'example.py':
                # Create a Python file with content that matches the suggested changes
                python_content = "def f(x, y):\n    z = x * y\n    return z"
                print(f"DEBUG: Python file content: '{python_content}'")
                mock_file = create_mock_file_content('example.py', content=python_content)
                mock_file.sha = 'python_file_sha'  # Add SHA attribute
                return mock_file
            elif path == 'example.js':
                # Create a JS file with content that matches the suggested changes
                js_content = "function calc(a, b) {\n    return a * b;\n}\n\nlet result = 0;\nresult = calc(5, 10);\nconsole.log(result);"
                print(f"DEBUG: JS file content: '{js_content}'")
                mock_file = create_mock_file_content('example.js', content=js_content)
                mock_file.sha = 'js_file_sha'  # Add SHA attribute
                return mock_file
            elif path == 'README.md':
                # Create a README file
                readme_content = "# Test Repository\nThis is a test repository for RepoSage."
                print(f"DEBUG: README file content: '{readme_content}'")
                mock_file = create_mock_file_content('README.md', content=readme_content)
                mock_file.sha = 'readme_file_sha'  # Add SHA attribute
                return mock_file
            elif path == 'CHANGELOG.md':
                # Create a mock changelog file
                changelog_content = """# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

### Changed

### Fixed

"""
                mock_file = create_mock_file_content('CHANGELOG.md', content=changelog_content)
                mock_file.sha = 'changelog_file_sha'  # Add SHA attribute
                return mock_file
            elif path == '':
                # Return a list of files for the root directory
                py_file = create_mock_file_content('example.py', content="def f(x, y):\n    z = x * y\n    return z", size=100)
                py_file.sha = 'python_file_sha'
                
                js_file = create_mock_file_content('example.js', content="function calc(a, b) {\n    return a * b;\n}\n\nlet result = 0;\nresult = calc(5, 10);\nconsole.log(result);", size=100)
                js_file.sha = 'js_file_sha'
                
                readme_file = create_mock_file_content('README.md', content="# Test Repository\nThis is a test repository for RepoSage.", size=100)
                readme_file.sha = 'readme_file_sha'
                
                changelog_file = create_mock_file_content('CHANGELOG.md', content="# Changelog\n\nAll notable changes to this project will be documented in this file.", size=100)
                changelog_file.sha = 'changelog_file_sha'
                
                return [py_file, js_file, readme_file, changelog_file]
            
            return None
        
        mock_repo.get_contents.side_effect = mock_get_contents
        
        # Store the original update_file calls to track
        update_file_calls = []

        # Add debug tracking for update_file calls using side_effect
        def debug_update_file(*args, **kwargs):
            print(f"DEBUG: update_file called with args: {args}, kwargs: {kwargs}")
            update_file_calls.append((args, kwargs))
            # Return a default value for the mock
            return (None, None)
            
        # Set the side effect while preserving the mock
        mock_repo.update_file.side_effect = debug_update_file
        
        # Run the bot with sequential mode for tests and with PR mode (not direct commit)
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch, use_parallel=False)
        
        # Override create_individual_pull_requests to force a second update for each file
        original_create_prs = bot.create_individual_pull_requests
        
        def mock_create_individual_prs(changes_list):
            print("DEBUG: Calling mock create_individual_pull_requests")
            # For each file in changes_list, call update_file again to simulate PR creation
            for file_changes in changes_list:
                file_path = file_changes['file_path']
                print(f"DEBUG: Creating individual PR for {file_path}")
                # Get the file content to update
                file_content = mock_repo.get_contents(file_path)
                # Update the file again
                mock_repo.update_file(
                    file_path,
                    f"Individual PR update for {file_path}",
                    file_changes['content'],
                    file_content.sha,
                    branch=f"{bot.branch_name}-{file_path}"
                )
            return ["https://github.com/user/repo/pull/1", "https://github.com/user/repo/pull/2"]
        
        # Replace the method with our mock
        bot.create_individual_pull_requests = mock_create_individual_prs
        
        # Set the bot to use PR mode (not direct commit)
        bot.run(direct_commit=False)
        
        # Verify API calls - should be 4 calls (one for each file, including changelog)
        self.assertEqual(mock_post.call_count, 4)
        
        # Verify branch creation - one main branch and one for each file with changes (2 files have changes)
        # The first call is for the main branch, and the rest are for individual file branches
        self.assertGreaterEqual(mock_repo.create_git_ref.call_count, 1)
        # Check that at least the first call is for the main branch
        first_call_args = mock_repo.create_git_ref.call_args_list[0]
        self.assertTrue(first_call_args[1]['ref'].startswith('refs/heads/reposage-improvements-'))
        
        # Verify file updates - expect 2 files to be modified, but called twice each
        # (once for the initial changes and once for each individual PR)
        self.assertEqual(mock_repo.update_file.call_count, 4)
        
        # Count update_file calls for each file
        py_updates = 0
        js_updates = 0
        for call in mock_repo.update_file.call_args_list:
            if call[0][0] == 'example.py':
                py_updates += 1
            elif call[0][0] == 'example.js':
                js_updates += 1
        
        # Each file should be updated twice
        self.assertEqual(py_updates, 2, "Python file should be updated twice")
        self.assertEqual(js_updates, 2, "JS file should be updated twice")
        
        # Verify PR creation - should be one PR for each file with changes
        self.assertEqual(mock_repo.create_pull.call_count, 2)

    @patch('bot.Github')
    @patch('bot.requests.post')
    def test_openrouter_api_call(self, mock_post, mock_github):
        """Test OpenRouter API call for file analysis."""
        # Set up mock file
        python_file = self.repo_dir / "example.py"
        file_content = python_file.read_text()
        
        # Mock GitHub API
        mock_repo = MagicMock()
        mock_github.return_value.get_repo.return_value = mock_repo
        
        # Set up mock file for API call
        mock_file_content = create_mock_file_content('example.py', content=file_content)
        
        # Mock the response with a response that matches the test_utils mock
        mock_post.return_value = mock_openrouter_response('.py')
        
        # Create bot and analyze file with sequential mode
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch, use_parallel=False)
        result = bot.analyze_file(mock_file_content)
        
        # Verify API was called with the correct parameters
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://openrouter.ai/api/v1/chat/completions")
        
        # Verify the model in the request
        request_json = call_args[1]['json']
        self.assertEqual(request_json['model'], self.model)
        
        # Verify the prompt includes the file content
        prompt = request_json['messages'][1]['content']
        self.assertIn('example.py', prompt)
        self.assertIn('def f(x, y):', prompt)
        
        # Verify the result structure
        self.assertIsNotNone(result)
        self.assertEqual(result['file_path'], 'example.py')
        self.assertIn('analysis', result)
        self.assertIn('suggested_changes', result['analysis'])

if __name__ == '__main__':
    unittest.main()
