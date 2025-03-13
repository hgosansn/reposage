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
        subprocess.run(command, cwd=cwd, check=True, 
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False)
    
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
                                'explanation': 'Improved function name to be more descriptive'
                            }, {
                                'original_code': '    z = x * y\n    return z',
                                'improved_code': '    """Multiply two numbers and return the result."""\n    return x * y',
                                'explanation': 'Added docstring and simplified the function'
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
                                'explanation': 'Improved function name and added JSDoc'
                            }, {
                                'original_code': 'let result = 0;\nresult = calc(5, 10);',
                                'improved_code': 'const result = multiply(5, 10);',
                                'explanation': 'Removed unnecessary variable reassignment and used const'
                            }],
                            'summary': 'Improved function naming, documentation, and variable usage'
                        })
                    }
                }]
            })
        else:
            return MockResponse(200, {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'analysis': {
                                'code_quality': 'No issues found.',
                                'best_practices': 'Follows best practices.',
                                'potential_bugs': 'No potential bugs found.',
                                'performance': 'No performance issues found.'
                            },
                            'suggested_changes': [],
                            'summary': 'No improvements needed'
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
            
            return mock_openrouter_response(file_ext)
        
        mock_post.side_effect = mock_post_response
        
        # Create mock file contents for the repository using the shared utility function
        def mock_get_contents(path, ref=None):
            if path == 'example.py':
                # Create a Python file with content that matches the suggested changes
                python_content = "def f(x, y):\n    return x * y"
                return create_mock_file_content('example.py', content=python_content, sha='py_file_sha')
            elif path == 'example.js':
                # Create a JS file with content that matches the suggested changes
                js_content = "function calc(a, b) {\n    return a * b;\n}"
                return create_mock_file_content('example.js', content=js_content, sha='js_file_sha')
            elif path == 'README.md':
                # Create a README file
                readme_content = "# Test Repository\nThis is a test repository for RepoSage."
                return create_mock_file_content('README.md', content=readme_content, sha='md_file_sha')
            elif path == '':
                # Return a list of files for the root directory
                return [
                    create_mock_file_content('example.py', content="def f(x, y):\n    return x * y", file_size=100),
                    create_mock_file_content('example.js', content="function calc(a, b) {\n    return a * b;\n}", file_size=100),
                    create_mock_file_content('README.md', content="# Test Repository\nThis is a test repository for RepoSage.", file_size=100)
                ]
            
            return None
        
        mock_repo.get_contents.side_effect = mock_get_contents
        
        # Run the bot
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        bot.run()
        
        # Verify API calls - should be 3 calls (one for each file)
        self.assertEqual(mock_post.call_count, 3)
        
        # Verify branch creation
        mock_repo.create_git_ref.assert_called_once()
        
        # Verify file updates - should be 2 updates (Python and JS files)
        self.assertEqual(mock_repo.update_file.call_count, 2)
        
        # Verify PR creation
        mock_repo.create_pull.assert_called_once()

    @patch('bot.Github')
    @patch('bot.requests.post')
    def test_openrouter_api_call(self, mock_post, mock_github):
        """Test the OpenRouter API call functionality."""
        # Mock GitHub API
        mock_repo = MagicMock()
        mock_github.return_value.get_repo.return_value = mock_repo
        
        # Mock the response
        mock_post.return_value = MockResponse(200, {
            'choices': [{
                'message': {
                    'content': '{"analysis": {"code_quality": "Good"}}'
                }
            }]
        })
        
        # Create a bot instance
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        
        # Call the API
        response = bot.call_openrouter_api("Test prompt")
        
        # Verify the API was called correctly
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://openrouter.ai/api/v1/chat/completions")
        self.assertEqual(kwargs['headers']['Authorization'], f"Bearer {bot.openrouter_api_key}")
        self.assertEqual(kwargs['json']['model'], bot.model)
        self.assertEqual(kwargs['json']['messages'][1]['content'], "Test prompt")
        
        # Verify the response
        self.assertEqual(response['choices'][0]['message']['content'], '{"analysis": {"code_quality": "Good"}}')

if __name__ == '__main__':
    unittest.main()
