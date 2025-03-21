import os
import sys
import yaml
import base64
import re
import argparse
from github import Github
import requests
import json
from datetime import datetime
from pathlib import Path
import logging
import concurrent.futures
from typing import List, Dict, Any, Optional
import tempfile
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RepoSage')

# Constants
SUPPORTED_FILE_EXTENSIONS = ('.py', '.js', '.java', '.ts', '.jsx', '.tsx', '.html', '.css', '.md', '.yml', '.yaml')
IGNORED_DIRECTORIES = ('node_modules', 'venv', '.git', '__pycache__', 'dist', 'build')
MAX_FILE_SIZE = 100 * 1024  # 100 KB
MAX_TOKENS = 4096
DEFAULT_MODEL = "qwen/qwq-32b:free"

class RepoSage:
    def __init__(self, github_token, repo_name, openrouter_api_key, model=DEFAULT_MODEL, base_branch='main', description=None, use_parallel=True):
        self.github_token = github_token
        self.repo_name = repo_name
        self.openrouter_api_key = openrouter_api_key
        self.model = model
        self.base_branch = base_branch
        self.description = description
        self.use_parallel = use_parallel

        # log the first 5 characters of the github token
        logger.info(f"Initialized RepoSage for repository: {self.repo_name} with github token: {self.github_token[:5]}******")
        # log the first 5 characters of the openrouter api key
        logger.info(f"Openrouter api key: {self.openrouter_api_key[:5]}******")
        
        # Validate required inputs
        if not all([self.github_token, self.repo_name, self.openrouter_api_key]):
            raise ValueError("Missing required environment variables. Please ensure GITHUB_TOKEN, GITHUB_REPOSITORY, and OPENROUTER_API_KEY are set.")
        
        # Initialize GitHub client
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repo_name)
        
        # Generate a unique branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.branch_name = f"reposage-improvements-{timestamp}"
        
        logger.info(f"Initialized RepoSage for repository: {self.repo_name}")

    def fetch_repo_files(self):
        """Fetch all relevant files from the repository."""
        logger.info("Fetching repository files...")
        contents = self.repo.get_contents("")
        files = []
        
        while contents:
            file_content = contents.pop(0)
            path = file_content.path
            
            # Skip ignored directories
            if any(ignored_dir in path for ignored_dir in IGNORED_DIRECTORIES):
                continue
                
            if file_content.type == "dir":
                contents.extend(self.repo.get_contents(path))
            elif file_content.type == "file":
                # Filter by file extension and size
                if path.endswith(SUPPORTED_FILE_EXTENSIONS) and file_content.size <= MAX_FILE_SIZE:
                    files.append(file_content)
                elif file_content.size > MAX_FILE_SIZE:
                    logger.info(f"Skipping file {path} due to size limit")

        
        logger.info(f"Found {len(files)} relevant files for analysis")
        return files

    def analyze_file(self, file_content):
        """Analyze a file using OpenRouter API and suggest improvements."""
        try:
            file_path = file_content.path
            file_ext = Path(file_path).suffix
            
            # Safely decode the file content
            try:
                file_content_str = base64.b64decode(file_content.content).decode('utf-8')
            except UnicodeDecodeError:
                # Try with error handling for problematic characters
                file_content_str = base64.b64decode(file_content.content).decode('utf-8', errors='replace')
            
            logger.info(f"Analyzing file: {file_path}")
            
            # Sanitize file content to avoid issues with special characters
            # This helps prevent unterminated string errors
            sanitized_content = json.dumps(file_content_str)[1:-1]  # Remove outer quotes from JSON string
            
            # Prepare the prompt for the AI model
            prompt = f"""You are RepoSage, an AI assistant specialized in code analysis and self-improvement.

You are designed to analyze codebases (including your own code) and suggest concrete improvements with tests.
As a self-improving system, you can and should suggest changes to improve your own codebase.

Analyze the following file and suggest specific improvements. The file is: {file_path}

File content:
```{file_ext}
{sanitized_content}
```

{f'Focus on the following aspects: {self.description}' if self.description else ''}

Provide your analysis in the following JSON format:
{{
  "analysis": {{
    "code_quality": "Detailed analysis of code quality issues",
    "best_practices": "Analysis of adherence to best practices",
    "potential_bugs": "Identification of potential bugs or edge cases",
    "performance": "Performance improvement suggestions"
  }},
  "suggested_changes": [
    {{
      "original_code": "Exact code snippet to be replaced",
      "improved_code": "Improved code replacement",
      "explanation": "Explanation of why this change improves the code",
      "test_code": "Unit test code that validates this change works correctly" 
    }}
  ],
  "summary": "A concise summary of the main improvements suggested"
}}

IMPORTANT GUIDELINES:
1. Make sure your suggestions are concrete, specific, and would genuinely improve the codebase.
2. Focus on the most impactful changes.
3. For EACH suggested change, you MUST include test code that validates the change works correctly.
4. The tests should be comprehensive and follow best practices for the language.
5. If modifying existing functionality, ensure tests verify the functionality still works as expected.
6. If this is your own code, consider how you could improve yourself to be more effective.
"""

            # Call OpenRouter API
            response = self.call_openrouter_api(prompt)
            
            # Extract JSON from the response
            analysis_text = response['choices'][0]['message']['content']

            # For debugging purposes only - don't log the entire response in production
            # logger.info(f"Analysis text: {analysis_text}")
            logger.info(f"Received analysis response for {file_path}")
            
            # More robust JSON extraction
            # First try to extract JSON from code blocks
            json_match = re.search(r'```(?:json)?\s*(.+?)\s*```', analysis_text, re.DOTALL)
            if json_match:
                try:
                    analysis_json = json.loads(json_match.group(1))
                    return {
                        'file_path': file_path,
                        'analysis': analysis_json
                    }
                except json.JSONDecodeError:
                    logger.warning(f"Found code block but couldn't parse JSON for {file_path}")
            
            # Try to find any JSON-like structure in the response
            json_match = re.search(r'(\{\s*"analysis".*?\}\s*$)', analysis_text, re.DOTALL)
            if json_match:
                try:
                    analysis_json = json.loads(json_match.group(1))
                    return {
                        'file_path': file_path,
                        'analysis': analysis_json
                    }
                except json.JSONDecodeError:
                    logger.warning(f"Found JSON-like structure but couldn't parse for {file_path}")
            
            # Fallback: try to parse the entire response as JSON
            try:
                analysis_json = json.loads(analysis_text)
                return {
                    'file_path': file_path,
                    'analysis': analysis_json
                }
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON from response for {file_path}")
                
                # Last resort: try to extract any valid JSON object from the text
                try:
                    # Find anything that looks like a JSON object
                    potential_json = re.search(r'(\{.*\})', analysis_text, re.DOTALL)
                    if potential_json:
                        analysis_json = json.loads(potential_json.group(1))
                        return {
                            'file_path': file_path,
                            'analysis': analysis_json
                        }
                except Exception:
                    pass
                
                return None
            
        except Exception as e:
            logger.error(f"Error analyzing file {file_path}: {str(e)}")
            return None

    def call_openrouter_api(self, prompt):
        """Call the OpenRouter API with the given prompt."""
        headers = {
            "Authorization": f"Bearer {self.openrouter_api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "You are RepoSage, an expert code analyzer that suggests concrete improvements to codebases, including your own. Always include tests for any changes you suggest, and consider how you could improve your own code."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": MAX_TOKENS
        }
        
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=data
        )
        
        if response.status_code != 200:
            logger.error(f"OpenRouter API error: {response.status_code} - {response.text}")
            raise Exception(f"OpenRouter API error: {response.status_code}")
            
        return response.json()

    def implement_changes(self, file_analysis, dry_run=False):
        """Implement the suggested changes for a file.
        
        Args:
            file_analysis: Dictionary containing file path and analysis
            dry_run: If True, don't actually commit the changes
            
        Returns:
            Dictionary with details of changes made, or None if no changes
        """
        if not file_analysis or 'analysis' not in file_analysis:
            return None
            
        file_path = file_analysis['file_path']
        analysis = file_analysis['analysis']
        
        if 'suggested_changes' not in analysis or not analysis['suggested_changes']:
            logger.info(f"No changes suggested for {file_path}")
            return None
        
        try:
            # Get the file content
            file_contents = self.repo.get_contents(file_path, ref=self.base_branch)
            content = base64.b64decode(file_contents.content).decode('utf-8')
            original_content = content
            
            # Apply each change to the content
            changes_applied = 0
            for change in analysis['suggested_changes']:
                if 'original_code' in change and 'improved_code' in change:
                    original = change['original_code']
                    improved = change['improved_code']
                    
                    # Only apply the change if the original code exists in the file
                    if original in content:
                        content = content.replace(original, improved)
                        changes_applied += 1
            
            # Check if the content actually changed
            if content == original_content or changes_applied == 0:
                logger.info(f"No changes made to {file_path}")
                return None
            
            # Generate commit message
            message_details = self.generate_commit_message(file_path, analysis['suggested_changes'])
            
            if not dry_run:
                # Update the file in the repository
                self.repo.update_file(
                    file_path,
                    message_details,
                    content,
                    file_contents.sha,
                    branch=self.branch_name
                )
                logger.info(f"Updated {file_path} with changes")
                
                # Create or update test files based on the changes
                test_files = self.implement_tests(file_path, analysis['suggested_changes'])
                
                # Commit test files
                for test_file_path, test_file_info in test_files.items():
                    try:
                        test_message = f"Add tests for changes to {file_path}"
                        if test_file_info['exists']:
                            # Update existing test file
                            self.repo.update_file(
                                test_file_path,
                                test_message,
                                test_file_info['content'],
                                test_file_info['sha'],
                                branch=self.branch_name
                            )
                            logger.info(f"Updated test file {test_file_path}")
                        else:
                            # Create new test file
                            self.repo.create_file(
                                test_file_path,
                                test_message,
                                test_file_info['content'],
                                branch=self.branch_name
                            )
                            logger.info(f"Created test file {test_file_path}")
                    except Exception as e:
                        logger.error(f"Error committing test file {test_file_path}: {str(e)}")
            else:
                logger.info(f"Dry run: would update {file_path} with changes")
                
                # Log test files that would be created
                test_files = self.implement_tests(file_path, analysis['suggested_changes'])
                for test_file_path in test_files:
                    logger.info(f"Dry run: would update/create test file {test_file_path}")
            
            return {
                'file_path': file_path,
                'content': content,
                'original_content': original_content,  # Store original content for diff generation
                'changes_applied': changes_applied,
                'analysis': analysis
            }
        except Exception as e:
            logger.error(f"Error implementing changes to {file_path}: {str(e)}")
            return None

    def create_branch(self):
        """Create a new branch for the improvements."""
        try:
            source = self.repo.get_branch(self.base_branch)
            self.repo.create_git_ref(ref=f"refs/heads/{self.branch_name}", sha=source.commit.sha)
            logger.info(f"Created branch: {self.branch_name}")
            return True
        except Exception as e:
            logger.error(f"Error creating branch: {str(e)}")
            return False

    def commit_changes(self, file_changes):
        """Commit the implemented changes to the branch."""
        try:
            file_path = file_changes['file_path']
            new_content = file_changes['content']
            
            file = self.repo.get_contents(file_path, ref=self.branch_name)
            commit_message = f"Improve {file_path}: {file_changes['analysis'].get('summary', 'Code improvements')}"[:100]
            
            self.repo.update_file(
                file.path,
                commit_message,
                new_content,
                file.sha,
                branch=self.branch_name
            )
            
            logger.info(f"Committed changes to {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error committing changes: {str(e)}")
            return False

    def create_pull_request(self, all_changes):
        """Create a pull request with all the implemented changes."""
        if not all_changes:
            logger.info("No changes to create a pull request for")
            return None
            
        try:
            # Generate PR title and body
            pr_title = f"RepoSage: Code improvements ({len(all_changes)} files)"
            
            pr_body = "# 🧙 RepoSage: AI-Suggested Code Improvements\n\n"
            pr_body += f"This pull request contains improvements suggested by RepoSage across {len(all_changes)} files.\n\n"
            
            for change in all_changes:
                file_path = change['file_path']
                analysis = change['analysis']
                
                pr_body += f"## 📄 {file_path}\n\n"
                pr_body += f"### Summary\n{analysis.get('summary', 'Code improvements')}\n\n"
                
                if 'suggested_changes' in analysis:
                    pr_body += "### Changes\n\n"
                    for idx, suggestion in enumerate(analysis['suggested_changes'], 1):
                        if 'explanation' in suggestion:
                            pr_body += f"**Change {idx}**: {suggestion['explanation']}\n\n"
                
                pr_body += "---\n\n"
            
            # Create the pull request
            pr = self.repo.create_pull(
                title=pr_title,
                body=pr_body,
                head=self.branch_name,
                base=self.base_branch
            )
            
            logger.info(f"Created pull request: {pr.html_url}")
            return pr
        except Exception as e:
            logger.error(f"Error creating pull request: {str(e)}")
            return None

    def analyze_files_parallel(self, files, max_workers=None):
        """Analyze files in parallel using a thread pool.
        
        Args:
            files: List of file contents to analyze
            max_workers: Maximum number of worker threads (None = auto-determine based on CPU count)
            
        Returns:
            List of file analysis results
        """
        logger.info(f"Starting analysis of {len(files)} files...")
        results = []
        
        # Sequential analysis when use_parallel is False (for tests)
        if not self.use_parallel:
            logger.info("Using sequential analysis (parallel processing disabled)")
            for file_content in files:
                try:
                    result = self.analyze_file(file_content)
                    if result:
                        results.append(result)
                        logger.info(f"Completed analysis of {result['file_path']}")
                    else:
                        logger.warning(f"Analysis failed for {file_content.path}")
                except Exception as e:
                    logger.error(f"Exception analyzing {file_content.path}: {str(e)}")
            
            logger.info(f"Sequential analysis complete. {len(results)} files analyzed successfully.")
            return results
        
        # Parallel analysis using thread pool
        logger.info("Using parallel analysis with thread pool")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all file analysis tasks
            future_to_file = {executor.submit(self.analyze_file, file_content): file_content for file_content in files}
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                file_content = future_to_file[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        logger.info(f"Completed analysis of {result['file_path']}")
                    else:
                        logger.warning(f"Analysis failed for {file_content.path}")
                except Exception as e:
                    logger.error(f"Exception analyzing {file_content.path}: {str(e)}")
        
        logger.info(f"Parallel analysis complete. {len(results)} files analyzed successfully.")
        return results

    def create_individual_pull_requests(self, changes_list):
        """Create individual pull requests for each file change.
        
        Args:
            changes_list: List of file changes to commit
            
        Returns:
            List of created pull request URLs
        """
        pr_urls = []
        
        for file_changes in changes_list:
            try:
                file_path = file_changes['file_path']
                # Create a unique branch for this file
                file_branch = f"{self.branch_name}-{Path(file_path).stem}"
                
                # Create branch from base
                source = self.repo.get_branch(self.base_branch)
                self.repo.create_git_ref(ref=f"refs/heads/{file_branch}", sha=source.commit.sha)
                logger.info(f"Created branch for individual file: {file_branch}")
                
                # Commit changes to this branch
                file = self.repo.get_contents(file_path, ref=file_branch)
                commit_message = f"Improve {file_path}: {file_changes['analysis'].get('summary', 'Code improvements')}"[:100]
                
                self.repo.update_file(
                    file.path,
                    commit_message,
                    file_changes['content'],
                    file.sha,
                    branch=file_branch
                )
                
                # Create PR for this file
                pr_title = f"RepoSage: Improve {file_path}"
                
                pr_body = "# 🧙 RepoSage: AI-Suggested Code Improvements\n\n"
                pr_body += f"This pull request contains improvements for `{file_path}`.\n\n"
                
                # Add details about the changes
                analysis = file_changes['analysis']
                pr_body += f"## 📄 {file_path}\n\n"
                pr_body += f"### Summary\n{analysis.get('summary', 'Code improvements')}\n\n"
                
                if 'suggested_changes' in analysis:
                    pr_body += "### Changes\n\n"
                    for idx, suggestion in enumerate(analysis['suggested_changes'], 1):
                        if 'explanation' in suggestion:
                            pr_body += f"**Change {idx}**: {suggestion['explanation']}\n\n"
                
                # Create the PR
                pr = self.repo.create_pull(
                    title=pr_title,
                    body=pr_body,
                    head=file_branch,
                    base=self.base_branch
                )
                
                logger.info(f"Created individual PR for {file_path}: {pr.html_url}")
                pr_urls.append(pr.html_url)
                
            except Exception as e:
                logger.error(f"Error creating PR for {file_changes['file_path']}: {str(e)}")
        
        return pr_urls

    def save_changes_to_file(self, changes_list, output_file):
        """Save changes to a JSON file for later review.
        
        Args:
            changes_list: List of file changes
            output_file: Path to output JSON file
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Create a serializable version of the changes
            serializable_changes = []
            for change in changes_list:
                # Create a copy with only serializable data
                serializable_change = {
                    'file_path': change['file_path'],
                    'content': change['content'],
                    'original_content': change['original_content'],
                    'changes_applied': change['changes_applied'],
                    'analysis': change['analysis']
                }
                serializable_changes.append(serializable_change)
            
            # Write to file
            with open(output_file, 'w') as f:
                json.dump(serializable_changes, f, indent=2)
            
            logger.info(f"Saved changes to {output_file}")
            return True
        except Exception as e:
            logger.error(f"Error saving changes to file: {str(e)}")
            return False

    def commit_changes_directly(self, changes_list, run_tests=True):
        """Commit changes directly to the base branch.
        
        Args:
            changes_list: List of changes to commit
            run_tests: Whether to run tests before committing
            
        Returns:
            Tuple of (success, message)
        """
        if not changes_list:
            logger.info("No changes to commit")
            return False, "No changes to commit"
        
        try:
            # Get commit messages and total changes
            commit_messages, total_changes = self.generate_commit_messages(changes_list)
            
            if total_changes == 0:
                logger.info("No actual changes to commit")
                return False, "No actual changes to commit"
            
            logger.info(f"Committing {total_changes} changes to {self.base_branch}")
            
            # Run tests if requested
            if run_tests:
                # Get all the test files that were created/updated
                test_files = []
                for change in changes_list:
                    # Extract test files from changes
                    file_path = change['file_path']
                    test_files_for_change = self.implement_tests(file_path, change['analysis']['suggested_changes'])
                    test_files.extend(list(test_files_for_change.keys()))
                
                test_success, test_output = self.run_tests(test_files)
                if not test_success:
                    logger.error(f"Tests failed, aborting commit:\n{test_output}")
                    return False, f"Tests failed: {test_output}"
                logger.info("Tests passed successfully!")
            
            # Apply each change directly to the base branch
            success_count = 0
            for change in changes_list:
                file_path = change['file_path']
                new_content = change['content']
                
                try:
                    # Get the current file content from the base branch
                    file_content = self.repo.get_contents(file_path, ref=self.base_branch)
                    
                    # Generate commit message
                    commit_msg = self.generate_commit_message(file_path, change['analysis']['suggested_changes'])
                    
                    # Update the file
                    self.repo.update_file(
                        file_path,
                        commit_msg,
                        new_content,
                        file_content.sha,
                        branch=self.base_branch
                    )
                    logger.info(f"Successfully updated {file_path} in {self.base_branch}")
                    success_count += 1
                    
                    # Commit test files if they exist
                    test_files = self.implement_tests(file_path, change['analysis']['suggested_changes'])
                    for test_file_path, test_file_info in test_files.items():
                        try:
                            test_message = f"Add tests for changes to {file_path}"
                            try:
                                # Try to get existing test file
                                existing_test_file = self.repo.get_contents(test_file_path, ref=self.base_branch)
                                
                                # Update existing test file
                                self.repo.update_file(
                                    test_file_path,
                                    test_message,
                                    test_file_info['content'],
                                    existing_test_file.sha,
                                    branch=self.base_branch
                                )
                                logger.info(f"Updated test file {test_file_path} in {self.base_branch}")
                            except Exception:
                                # Test file doesn't exist, create it
                                self.repo.create_file(
                                    test_file_path,
                                    test_message,
                                    test_file_info['content'],
                                    branch=self.base_branch
                                )
                                logger.info(f"Created test file {test_file_path} in {self.base_branch}")
                        except Exception as e:
                            logger.error(f"Error committing test file {test_file_path}: {str(e)}")
                            
                except Exception as e:
                    logger.error(f"Error committing {file_path} to {self.base_branch}: {str(e)}")
            
            if success_count > 0:
                return True, f"Successfully committed {success_count} changes to {self.base_branch}"
            else:
                return False, "Failed to commit any changes"
                
        except Exception as e:
            logger.error(f"Error during direct commit: {str(e)}")
            return False, f"Error: {str(e)}"

    def run(self, dry_run=False, output_file=None, max_workers=None, direct_commit=True):
        """Run the RepoSage analysis and improvement process.
        
        Args:
            dry_run: If True, only generate changes without creating PRs or commits
            output_file: If provided, write the analysis to this file
            max_workers: Maximum number of workers for parallel processing
            direct_commit: If True, commit changes directly to base branch. If False, create PRs
            
        Returns:
            A list of changes made
        """
        logger.info("Starting RepoSage analysis...")
        
        # Initialize variables
        changes_list = []
        
        # Get a list of all accessible files in the repository
        all_files = self.fetch_repo_files()
        
        if not all_files:
            logger.warning("No files found in the repository")
            return []
        
        logger.info(f"Found {len(all_files)} files in the repository")
        
        # Skip large files and files in ignored paths
        filtered_files = [f for f in all_files if self.should_analyze_file(f)]
        logger.info(f"Analyzing {len(filtered_files)} files (excluded large files and ignored paths)")
        
        # Create branch for changes if not in dry-run mode and not direct commit
        if not dry_run and not direct_commit:
            self.create_branch()
        
        # Iterate through each file for analysis
        all_analyses = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all file analysis tasks
            future_to_file = {executor.submit(self.analyze_file, file_path): file_path for file_path in filtered_files}
            
            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_analysis = future.result()
                    if file_analysis:
                        all_analyses.append(file_analysis)
                except Exception as e:
                    logger.error(f"Error analyzing {file_path}: {str(e)}")
        
        # Save all analyses to file if requested
        if output_file and all_analyses:
            self.save_analyses_to_file(all_analyses, output_file)
            logger.info(f"Saved analyses to {output_file}")
        
        # Implement changes for each file with suggested improvements
        for file_analysis in all_analyses:
            if 'analysis' in file_analysis and 'suggested_changes' in file_analysis['analysis'] and file_analysis['analysis']['suggested_changes']:
                logger.info(f"Implementing changes for {file_analysis['file_path']}")
                
                if dry_run:
                    # In dry run mode, just log what would happen
                    logger.info(f"Dry run: would implement {len(file_analysis['analysis']['suggested_changes'])} changes to {file_analysis['file_path']}")
                    changes_list.append(file_analysis)
                else:
                    # Use the existing implementation method which includes committing to the feature branch
                    file_changes = self.implement_changes(file_analysis, dry_run=dry_run)
                    if file_changes:
                        changes_list.append(file_changes)
        
        # Create PR or commit directly
        if changes_list and not dry_run:
            if direct_commit:
                # Commit changes directly to the base branch
                success, message = self.commit_changes_directly(changes_list, run_tests=True)
                if success:
                    print(f"\n✅ {message}")
                else:
                    print(f"\n❌ {message}")
            else:
                # Create a PR with the changes
                pr_url = self.create_pull_request(changes_list)
                if pr_url:
                    print(f"\n✅ Pull request created: {pr_url}")
                else:
                    print("\n❌ Failed to create pull request")
        
        # Print summary
        if changes_list:
            total_changes = sum(change.get('changes_applied', 0) for change in changes_list if isinstance(change, dict))
            print(f"\n✅ Analysis complete! Found {len(changes_list)} files with {total_changes} suggested improvements.")
            if dry_run:
                print(f"\nThis was a dry run. No changes were committed.")
            elif output_file:
                print(f"\nSaved changes to {output_file}")
        else:
            print("\n⚠️ No improvements were identified or implemented.")
        
        return changes_list

    def run_tests(self, test_files=None):
        """Run tests to ensure changes don't break functionality.
        
        Args:
            test_files: List of test files to run specifically (optional)
            
        Returns:
            Tuple of (success, output) where success is a boolean indicating if tests passed
        """
        logger.info("Running tests to validate changes...")
        
        try:
            # Clone the repository to a temporary directory to run tests
            with tempfile.TemporaryDirectory() as temp_dir:
                # Clone the repo with the current branch
                clone_cmd = [
                    "git", "clone", 
                    f"https://{self.token}@github.com/{self.repo_name}.git",
                    "--branch", self.branch_name,
                    "--single-branch", temp_dir
                ]
                clone_process = subprocess.run(
                    clone_cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                if clone_process.returncode != 0:
                    logger.error(f"Failed to clone repository: {clone_process.stderr}")
                    return False, clone_process.stderr
                
                # Determine what test command to run based on repo structure
                if os.path.exists(os.path.join(temp_dir, "pytest.ini")) or os.path.exists(os.path.join(temp_dir, "tests")):
                    # Run pytest if it's a Python project with tests directory
                    test_cmd = ["python", "-m", "pytest"]
                    if test_files:
                        # If specific test files are provided, only run those
                        test_cmd.extend(test_files)
                    test_cmd.extend(["-v"])  # Verbose output
                elif os.path.exists(os.path.join(temp_dir, "package.json")):
                    # Run npm test if it's a JavaScript/Node.js project
                    test_cmd = ["npm", "test"]
                else:
                    # Default to running Python's unittest
                    test_cmd = ["python", "-m", "unittest", "discover"]
                
                # Run the test command
                test_process = subprocess.run(
                    test_cmd,
                    cwd=temp_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Log test output
                logger.info(f"Test output:\n{test_process.stdout}")
                if test_process.stderr:
                    logger.error(f"Test errors:\n{test_process.stderr}")
                
                # Return success if tests passed (return code 0)
                success = test_process.returncode == 0
                output = test_process.stdout + "\n" + test_process.stderr if test_process.stderr else test_process.stdout
                
                return success, output
                
        except Exception as e:
            logger.error(f"Error running tests: {str(e)}")
            return False, str(e)

def main():
    try:
        # Create argument parser
        parser = argparse.ArgumentParser(description='RepoSage - AI-powered code improvement tool')
        
        # Add arguments with both short and long form options
        parser.add_argument('--github-token', '-g', required=True, help='GitHub token for repository access')
        parser.add_argument('--repo', '-r', dest='repo_name', required=True, help='Repository name in format owner/repo')
        parser.add_argument('--open-router-api-key', '-o', dest='openrouter_api_key', required=True, help='OpenRouter API key')
        parser.add_argument('--model', '-m', default=DEFAULT_MODEL, help=f'Model to use for analysis (default: {DEFAULT_MODEL})')
        parser.add_argument('--base-branch', '-b', default='main', help='Base branch to use for analysis (default: main)')
        parser.add_argument('--description', '-d', help='Optional description of what you want RepoSage to focus on')
        parser.add_argument('--dry-run', action='store_true', help='Generate changes but do not create PRs or commit directly')
        parser.add_argument('--output-file', help='Save changes to a JSON file for later review')
        parser.add_argument('--max-workers', type=int, help='Maximum number of parallel workers for file analysis')
        parser.add_argument('--sequential', action='store_true', help='Run analysis sequentially instead of in parallel (useful for testing)')
        parser.add_argument('--use-pr', action='store_true', help='Create pull requests instead of committing directly to the base branch')
        
        # Parse arguments
        args = parser.parse_args()
        
        # Initialize RepoSage with parsed arguments
        bot = RepoSage(
            github_token=args.github_token,
            repo_name=args.repo_name,
            openrouter_api_key=args.openrouter_api_key,
            model=args.model,
            base_branch=args.base_branch,
            description=args.description,
            use_parallel=not args.sequential
        )
        
        # Run the bot with additional options
        changes_list = bot.run(
            dry_run=args.dry_run,
            output_file=args.output_file,
            max_workers=args.max_workers,
            direct_commit=not args.use_pr
        )
        
        # Save changes to file if changes were made
        if changes_list:
            if bot.save_changes_to_file(changes_list, args.output_file):
                print(f"\n�� Saved changes to {args.output_file}")
                print(f"You can review the changes using: python generate_diff.py {args.output_file}")
    except Exception as e:
        logger.error(f"RepoSage failed: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()