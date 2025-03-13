import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import json
import base64
from io import BytesIO
import sys
import os.path

# Add the repo-sage-action directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'repo-sage-action')))
from bot import RepoSage
from test_utils import create_mock_file_content, mock_openrouter_response, setup_mock_github_repo

class TestRepoSage(unittest.TestCase):
    """Test suite for the RepoSage bot."""

    import unittest
from unittest.mock import patch, MagicMock, mock_open
import json

class TestRepoSage(unittest.TestCase):

    def setUp(self):
        self.github_token = 'fake_github_token'
        self.repo_name = 'user/repo'
        self.openrouter_api_key = 'fake_openrouter_api_key'
        self.model = 'google/gemma-3-27b-it:free'
        self.base_branch = 'main'

    def _setup_mocks(self):
        with patch('bot.Github') as mock_github, patch('bot.requests') as mock_requests:
            mock_repo = MagicMock()
            mock_github.return_value.get_repo.return_value = mock_repo
            mock_branch = MagicMock()
            mock_branch.commit.sha = 'fake_commit_sha'
            mock_repo.get_branch.return_value = mock_branch
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'choices': [{
                    'message': {
                        'content': json.dumps({
                            'analysis': {
                                'code_quality': 'Good code quality',
                                'best_practices': 'Follows best practices',
                                'potential_bugs': 'No potential bugs found',
                                'performance': 'Good performance'
                            },
                            'suggested_changes': [{
                                'original_code': 'def old_function():',
                                'improved_code': 'def improved_function():',
                                'explanation': 'Better function name'
                            }],
                            'summary': 'Improved function naming'
                        })
                    }
                }]
            }
            mock_requests.post.return_value = mock_response
            return mock_github, mock_requests, mock_repo

    def tearDown(self):
        pass  # Patches are handled by 'with' statement now


    def tearDown(self):
        """Clean up after each test."""
        # Stop patches
        self.github_patch.stop()
        self.requests_patch.stop()

    # Using the shared test utility function instead of a class method

    def test_initialization(self):
        """Test that RepoSage initializes correctly."""
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        
        # Verify GitHub client was initialized
        self.mock_github.assert_called_once_with('fake_github_token')
        self.mock_github.return_value.get_repo.assert_called_once_with('user/repo')
        
        # Verify attributes were set correctly
        self.assertEqual(bot.github_token, 'fake_github_token')
        self.assertEqual(bot.repo_name, 'user/repo')
        self.assertEqual(bot.openrouter_api_key, 'fake_openrouter_api_key')
        self.assertEqual(bot.model, 'google/gemma-3-27b-it:free')
        self.assertEqual(bot.base_branch, 'main')

    def test_fetch_repo_files(self):
        """Test fetching repository files."""
        # Set up mock files
        mock_py_file = create_mock_file_content('test.py')
        mock_js_file = create_mock_file_content('test.js')
        mock_txt_file = create_mock_file_content('test.txt')  # Should be filtered out
        mock_dir = MagicMock()
        mock_dir.type = "dir"
        mock_dir.path = "test_dir"
        
        # Set up mock responses for get_contents
        self.mock_repo.get_contents.side_effect = [
            [mock_dir, mock_txt_file],  # First call returns root contents
            [mock_py_file, mock_js_file]  # Second call returns directory contents
        ]
        
        # Create bot and fetch files
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        files = bot.fetch_repo_files()
        
        # Verify correct files were returned (txt file should be filtered out)
        self.assertEqual(len(files), 2)
        self.assertIn(mock_py_file, files)
        self.assertIn(mock_js_file, files)
        self.assertNotIn(mock_txt_file, files)

    def test_analyze_file(self):
        """Test file analysis with OpenRouter API."""
        # Create mock file
        mock_file = create_mock_file_content('test.py')
        
        # Create bot and analyze file
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        result = bot.analyze_file(mock_file)
        
        # Verify API was called correctly
        self.mock_requests.post.assert_called_once()
        call_args = self.mock_requests.post.call_args
        self.assertEqual(call_args[0][0], "https://openrouter.ai/api/v1/chat/completions")
        
        # Verify result structure
        self.assertIsNotNone(result)
        self.assertEqual(result['file_path'], 'test.py')
        self.assertIn('analysis', result)
        self.assertIn('suggested_changes', result['analysis'])

    def test_implement_changes(self):
        """Test implementing suggested changes."""
        # Create mock file analysis
        file_analysis = {
            'file_path': 'test.py',
            'analysis': {
                'suggested_changes': [{
                    'original_code': 'def old_function():',
                    'improved_code': 'def improved_function():',
                    'explanation': 'Better function name'
                }],
                'summary': 'Improved function naming'
            }
        }
        
        # Set up mock file content for implementation
        mock_file = create_mock_file_content('test.py')
        self.mock_repo.get_contents.return_value = mock_file
        
        # Create bot and implement changes
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        result = bot.implement_changes(file_analysis)
        
        # Verify result structure
        self.assertIsNotNone(result)
        self.assertEqual(result['file_path'], 'test.py')
        self.assertEqual(result['changes_applied'], 1)
        self.assertEqual(result['content'], 'def improved_function():\n    pass')

    def test_create_branch(self):
        """Test branch creation."""
        # Create bot and create branch
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        result = bot.create_branch()
        
        # Verify branch was created
        self.assertTrue(result)
        self.mock_repo.create_git_ref.assert_called_once()
        call_args = self.mock_repo.create_git_ref.call_args
        self.assertTrue(call_args[1]['ref'].startswith('refs/heads/reposage-improvements-'))
        self.assertEqual(call_args[1]['sha'], 'fake_commit_sha')

    def test_commit_changes(self):
        """Test committing changes."""
        # Create mock file changes
        file_changes = {
            'file_path': 'test.py',
            'content': 'def improved_function():\n    pass',
            'changes_applied': 1,
            'analysis': {
                'summary': 'Improved function naming'
            }
        }
        
        # Set up mock file for commit
        mock_file = create_mock_file_content('test.py')
        self.mock_repo.get_contents.return_value = mock_file
        
        # Create bot and commit changes
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        result = bot.commit_changes(file_changes)
        
        # Verify changes were committed
        self.assertTrue(result)
        self.mock_repo.update_file.assert_called_once()
        call_args = self.mock_repo.update_file.call_args
        self.assertEqual(call_args[0][0], 'test.py')
        self.assertTrue('Improve test.py' in call_args[0][1])
        self.assertEqual(call_args[0][2], 'def improved_function():\n    pass')

    def test_create_pull_request(self):
        """Test pull request creation."""
        # Create mock changes
        changes = [{
            'file_path': 'test.py',
            'content': 'def improved_function():\n    pass',
            'changes_applied': 1,
            'analysis': {
                'summary': 'Improved function naming',
                'suggested_changes': [{
                    'explanation': 'Better function name'
                }]
            }
        }]
        
        # Set up mock PR
        mock_pr = MagicMock()
        mock_pr.html_url = 'https://github.com/user/repo/pull/1'
        self.mock_repo.create_pull.return_value = mock_pr
        
        # Create bot and create PR
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        result = bot.create_pull_request(changes)
        
        # Verify PR was created
        self.assertIsNotNone(result)
        self.mock_repo.create_pull.assert_called_once()
        call_args = self.mock_repo.create_pull.call_args
        self.assertTrue('RepoSage: Code improvements' in call_args[1]['title'])
        self.assertTrue('AI-Suggested Code Improvements' in call_args[1]['body'])
        self.assertTrue('test.py' in call_args[1]['body'])

    @patch('bot.RepoSage.fetch_repo_files')
    @patch('bot.RepoSage.analyze_file')
    @patch('bot.RepoSage.implement_changes')
    @patch('bot.RepoSage.commit_changes')
    @patch('bot.RepoSage.create_pull_request')
    def test_run_full_process(self, mock_create_pr, mock_commit, mock_implement, mock_analyze, mock_fetch):
        """Test the full bot run process."""
        # Set up mock files
        mock_file = create_mock_file_content('test.py')
        mock_fetch.return_value = [mock_file]
        
        # Set up mock analysis
        mock_analysis = {
            'file_path': 'test.py',
            'analysis': {
                'suggested_changes': [{
                    'original_code': 'def old_function():',
                    'improved_code': 'def improved_function():',
                    'explanation': 'Better function name'
                }],
                'summary': 'Improved function naming'
            }
        }
        mock_analyze.return_value = mock_analysis
        
        # Set up mock implementation
        mock_changes = {
            'file_path': 'test.py',
            'content': 'def improved_function():\n    pass',
            'changes_applied': 1,
            'analysis': mock_analysis['analysis']
        }
        mock_implement.return_value = mock_changes
        
        # Set up mock commit
        mock_commit.return_value = True
        
        # Set up mock PR
        mock_pr = MagicMock()
        mock_pr.html_url = 'https://github.com/user/repo/pull/1'
        mock_create_pr.return_value = mock_pr
        
        # Create bot and run
        bot = RepoSage(self.github_token, self.repo_name, self.openrouter_api_key, self.model, self.base_branch)
        bot.run()
        
        # Verify all steps were called
        mock_fetch.assert_called_once()
        mock_analyze.assert_called_once_with(mock_file)
        mock_implement.assert_called_once_with(mock_analysis)
        mock_commit.assert_called_once_with(mock_changes)
        mock_create_pr.assert_called_once()

if __name__ == '__main__':
    unittest.main()
