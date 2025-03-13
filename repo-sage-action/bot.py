import os
import yaml
import base64
import re
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
DEFAULT_MODEL = "google/gemma-3-27b-it:free"

class RepoSage:
    def __init__(self):
        # Read inputs from the GitHub Action or environment variables
        self.github_token = os.environ.get('INPUT_GITHUB_TOKEN') or os.environ.get('GITHUB_TOKEN')
        self.repo_name = os.environ.get('INPUT_REPO', os.environ['GITHUB_REPOSITORY'])
        self.openrouter_api_key = os.environ.get('INPUT_OPEN_ROUTER_API_KEY') or os.environ.get('OPENROUTER_API_KEY')
        self.model = os.environ.get('INPUT_MODEL') or DEFAULT_MODEL
        self.base_branch = os.environ.get('INPUT_BASE_BRANCH') or 'main'
        
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
        
        logger.info(f"Found {len(files)} relevant files for analysis")
        return files

    def analyze_file(self, file_content):
        """Analyze a file using OpenRouter API and suggest improvements."""
        try:
            file_path = file_content.path
            file_ext = Path(file_path).suffix
            file_content_str = base64.b64decode(file_content.content).decode('utf-8')
            
            logger.info(f"Analyzing file: {file_path}")
            
            # Prepare the prompt for the AI model
            prompt = f"""You are RepoSage, an AI assistant specialized in code analysis and improvement.

Analyze the following file and suggest specific improvements. The file is: {file_path}

File content:
```{file_ext}
{file_content_str}
```

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
            
            # Extract JSON from the response text (handles cases where model might add markdown formatting)
            json_match = re.search(r'```json\s*(.+?)\s*```', analysis_text, re.DOTALL)
            if json_match:
                analysis_json = json.loads(json_match.group(1))
            else:
                # Try to find any JSON-like structure in the response
                json_match = re.search(r'\{\s*"analysis".*\}', analysis_text, re.DOTALL)
                if json_match:
                    analysis_json = json.loads(json_match.group(0))
                else:
                    # Fallback: try to parse the entire response as JSON
                    try:
                        analysis_json = json.loads(analysis_text)
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse JSON from response for {file_path}")
                        return None
            
            return {
                'file_path': file_path,
                'analysis': analysis_json
            }
            
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
        bot = RepoSage()
        bot.run()
    except Exception as e:
        logger.error(f"RepoSage failed: {str(e)}")
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    main()