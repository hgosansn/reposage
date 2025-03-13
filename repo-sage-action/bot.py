import os
import sys
// Remove unused import
import base64
import re
import argparse
from github import Github
import requests
import json
from datetime import datetime
from pathlib import Path
import logging

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
    def __init__(self, github_token, repo_name, openrouter_api_key, model=DEFAULT_MODEL, base_branch='main', description=None):
        self.github_token = github_token
        self.repo_name = repo_name
        self.openrouter_api_key = openrouter_api_key
        self.model = model
        self.base_branch = base_branch
        self.description = description

        # log the first 5 characters of the github token
        logger.info(f"Initialized RepoSage for repository: {self.repo_name} with github token: {self.github_token[:5]}******")
        # log the first 5 characters of the openrouter api key
        logger.info(f"Openrouter api key: {self.openrouter_api_key[:5]}******")
        
        # Validate required inputs
        if not all([self.github_token, self.repo_name, self.openrouter_api_key]):
            raise ValueError("Missing required command-line arguments. Please ensure --github-token, --repo, and --open-router-api-key are provided.")
        
        # Initialize GitHub client
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repo_name)
        
        # Generate a unique branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.branch_name = f"reposage-improvements-{timestamp}"
        
        // Remove duplicate log statement

    def fetch_repo_files(self):
        """Fetch all relevant files from the repository."""
        logger.info("Fetching repository files...")
        contents = self.repo.get_contents("")
        files = []
        
        while contents:
            file_content = contents.pop(0)
            path = file_content.path
            
            # Skip ignored directories
            if any(ignored_dir == path.split('/')[0] for ignored_dir in IGNORED_DIRECTORIES):
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
            prompt = f"""You are RepoSage, an AI assistant specialized in code analysis and improvement.

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
      "explanation": "Explanation of why this change improves the code"
    }}
  ],
  "summary": "A concise summary of the main improvements suggested"
}}

Make sure your suggestions are concrete, specific, and would genuinely improve the codebase. Focus on the most impactful changes."""

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
                {"role": "system", "content": "You are RepoSage, an expert code analyzer that suggests concrete improvements to codebases."},
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

    def implement_changes(self, file_analysis):
        """Implement the suggested changes for a file."""
        if not file_analysis or 'analysis' not in file_analysis:
            return None
            
        file_path = file_analysis['file_path']
        analysis = file_analysis['analysis']
        
        if 'suggested_changes' not in analysis or not analysis['suggested_changes']:
            logger.info(f"No changes suggested for {file_path}")
            return None
            
        try:
            # Get the current file content
            file_content = self.repo.get_contents(file_path, ref=self.base_branch)
            current_content = base64.b64decode(file_content.content).decode('utf-8')
            new_content = current_content
            
            # Apply each suggested change
            changes_applied = 0
            for change in analysis['suggested_changes']:
                if 'original_code' in change and 'improved_code' in change:
                    original = change['original_code']
                    improved = change['improved_code']
                    
                    # Only apply the change if the original code exists in the file
                    if original in new_content:
                        new_content = new_content.replace(original, improved)
                        changes_applied += 1
            
            if changes_applied > 0 and new_content != current_content:
                logger.info(f"Applied {changes_applied} changes to {file_path}")
                return {
                    'file_path': file_path,
                    'content': new_content,
                    'changes_applied': changes_applied,
                    'analysis': analysis
                }
            else:
                logger.info(f"No changes were applied to {file_path}")
                return None
                
        except Exception as e:
            logger.error(f"Error implementing changes for {file_path}: {str(e)}")
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

    def run(self):
        """Run the RepoSage analysis and improvement process."""
        logger.info("Starting RepoSage analysis...")
        
        # Create a new branch
        if not self.create_branch():
            return
        
        # Fetch repository files
        files = self.fetch_repo_files()
        
        # Analyze files and implement changes
        all_changes = []
        for file_content in files:
            # Analyze the file
            file_analysis = self.analyze_file(file_content)
            if file_analysis:
                # Implement suggested changes
                file_changes = self.implement_changes(file_analysis)
                if file_changes:
                    # Commit the changes
                    if self.commit_changes(file_changes):
                        all_changes.append(file_changes)
        
        # Create a pull request with all changes
        if all_changes:
            pr = self.create_pull_request(all_changes)
            if pr:
                print(f"\n✅ Pull request created successfully: {pr.html_url}")
                print(f"RepoSage suggested improvements to {len(all_changes)} files.")
            else:
                print("\n❌ Failed to create pull request.")
        else:
            print("\n⚠️ No improvements were identified or implemented.")

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
        
        # Parse arguments
        args = parser.parse_args()
        
        # Initialize RepoSage with parsed arguments
        bot = RepoSage(
            github_token=args.github_token,
            repo_name=args.repo_name,
            openrouter_api_key=args.openrouter_api_key,
            model=args.model,
            base_branch=args.base_branch,
            description=args.description
        )
        
        # Run the bot
        bot.run()
    except Exception as e:
        logger.error(f"RepoSage failed: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()