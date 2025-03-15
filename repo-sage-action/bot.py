#!/usr/bin/env python3
import pysqlite3
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import os
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
import tempfile
from typing import List, Dict, Any, Optional

# Import CrewAI components
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

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
DEFAULT_MODEL = "qwen/qwq-32b:free"

class GitHubFileTool(BaseTool):
    """Tool for fetching files from GitHub repository."""
    
    name: str = "GitHub File Fetcher"
    description: str = "Fetches file content from a GitHub repository"
    
    def __init__(self, github_token, repo_name, base_branch='main'):
        super().__init__()
        self.github_token = github_token
        self.repo_name = repo_name
        self.base_branch = base_branch
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
    
    def _run(self, file_path: str) -> str:
        """Fetch file content from GitHub."""
        try:
            file_content = self.repo.get_contents(file_path, ref=self.base_branch)
            content = base64.b64decode(file_content.content).decode('utf-8', errors='replace')
            return content
        except Exception as e:
            return f"Error fetching file: {str(e)}"

class GitHubCommitTool(BaseTool):
    """Tool for committing changes to GitHub repository."""
    
    name: str = "GitHub Commit Tool"
    description: str = "Commits changes to a file in a GitHub repository"
    
    def __init__(self, github_token, repo_name, branch_name):
        super().__init__()
        self.github_token = github_token
        self.repo_name = repo_name
        self.branch_name = branch_name
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
    
    def _run(self, file_path: str, content: str, commit_message: str) -> str:
        """Commit changes to GitHub."""
        try:
            file = self.repo.get_contents(file_path, ref=self.branch_name)
            self.repo.update_file(
                file.path,
                commit_message,
                content,
                file.sha,
                branch=self.branch_name
            )
            return f"Successfully committed changes to {file_path}"
        except Exception as e:
            return f"Error committing changes: {str(e)}"

class GitHubPRTool(BaseTool):
    """Tool for creating pull requests on GitHub."""
    
    name: str = "GitHub PR Creator"
    description: str = "Creates a pull request on GitHub"
    
    def __init__(self, github_token, repo_name, branch_name, base_branch='main'):
        super().__init__()
        self.github_token = github_token
        self.repo_name = repo_name
        self.branch_name = branch_name
        self.base_branch = base_branch
        self.github = Github(github_token)
        self.repo = self.github.get_repo(repo_name)
    
    def _run(self, title: str, body: str) -> str:
        """Create a pull request on GitHub."""
        try:
            pr = self.repo.create_pull(
                title=title,
                body=body,
                head=self.branch_name,
                base=self.base_branch
            )
            return f"Successfully created PR: {pr.html_url}"
        except Exception as e:
            return f"Error creating PR: {str(e)}"

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
            raise ValueError("Missing required environment variables. Please ensure GITHUB_TOKEN, GITHUB_REPOSITORY, and OPENROUTER_API_KEY are set.")
        
        # Initialize GitHub client
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repo_name)
        
        # Generate a unique branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.branch_name = f"reposage-improvements-{timestamp}"
        
        # Initialize OpenRouter LLM using LangChain's OpenAI integration
        self.llm = ChatOpenAI(
            model=self.model,
            openai_api_key=self.openrouter_api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            max_tokens=4096,
            temperature=0.7
        )
        
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

    def create_agents(self):
        """Create the CrewAI agents for code analysis and improvement."""
        # Create tools
        file_tool = GitHubFileTool(self.github_token, self.repo_name, self.base_branch)
        commit_tool = GitHubCommitTool(self.github_token, self.repo_name, self.branch_name)
        pr_tool = GitHubPRTool(self.github_token, self.repo_name, self.branch_name, self.base_branch)
        
        # Code Analyzer Agent
        code_analyzer = Agent(
            role="Code Analyzer",
            goal="Analyze code files for quality issues, bugs, and improvement opportunities",
            backstory="""You are an expert code analyzer with years of experience in software development.
            Your job is to review code files and identify quality issues, potential bugs, and areas for improvement.
            You have a keen eye for detail and can spot problems that others might miss.""",
            verbose=True,
            allow_delegation=True,
            tools=[file_tool],
            llm=self.llm
        )
        
        # Code Improver Agent
        code_improver = Agent(
            role="Code Improver",
            goal="Implement improvements to code based on analysis",
            backstory="""You are a skilled software engineer specializing in code improvement and refactoring.
            You take analysis reports and implement concrete changes to improve code quality, fix bugs,
            and enhance performance. You write clean, maintainable code that follows best practices.""",
            verbose=True,
            allow_delegation=True,
            tools=[file_tool, commit_tool],
            llm=self.llm
        )
        
        # PR Manager Agent
        pr_manager = Agent(
            role="PR Manager",
            goal="Create well-documented pull requests for code improvements",
            backstory="""You are a detail-oriented project manager who specializes in creating clear,
            informative pull requests. You document changes thoroughly, explaining the rationale
            behind each improvement and how it benefits the codebase.""",
            verbose=True,
            allow_delegation=True,
            tools=[pr_tool],
            llm=self.llm
        )
        
        return code_analyzer, code_improver, pr_manager

    def create_tasks(self, files, code_analyzer, code_improver, pr_manager):
        """Create tasks for the agents based on the files to analyze."""
        tasks = []
        
        # Group files for analysis to avoid too many tasks
        file_groups = [files[i:i+5] for i in range(0, len(files), 5)]
        
        for i, file_group in enumerate(file_groups):
            file_paths = [file.path for file in file_group]
            file_paths_str = "\n".join(file_paths)
            
            # Analysis task
            analysis_task = Task(
                description=f"""Analyze the following files for code quality issues, potential bugs, and improvement opportunities:
                {file_paths_str}
                
                {f'Focus on the following aspects: {self.description}' if self.description else ''}
                
                For each file, provide a detailed analysis in JSON format with the following structure:
                {{
                  "file_path": "path/to/file",
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
                """,
                agent=code_analyzer,
                expected_output="A JSON object containing analysis results for each file"
            )
            tasks.append(analysis_task)
            
            # Improvement task (depends on analysis task)
            improvement_task = Task(
                description="""Review the analysis results and implement the suggested changes.
                For each file:
                1. Fetch the current content
                2. Apply the suggested changes
                3. Commit the improved code with a descriptive commit message
                
                Return a list of all files that were improved, along with a summary of changes made.
                """,
                agent=code_improver,
                expected_output="A list of files that were improved and a summary of changes",
                context=[analysis_task]
            )
            tasks.append(improvement_task)
        
        # PR creation task (depends on all improvement tasks)
        pr_task = Task(
            description="""Create a pull request that includes all the improvements made.
            The PR should have:
            1. A clear title summarizing the improvements
            2. A detailed description explaining the changes
            3. A breakdown of improvements by file
            
            Return the URL of the created PR.
            """,
            agent=pr_manager,
            expected_output="URL of the created pull request",
            context=[task for task in tasks if task.agent == code_improver]
        )
        tasks.append(pr_task)
        
        return tasks

    def run(self, dry_run=False, output_file=None, max_workers=None):
        """Run the RepoSage analysis and improvement process using CrewAI."""
        logger.info("Starting RepoSage analysis with CrewAI...")
        
        # Only create branch if we're not in dry run mode
        if not dry_run and not self.create_branch():
            return
        
        # Fetch repository files
        files = self.fetch_repo_files()
        
        if not files:
            logger.info("No files found for analysis")
            return
        
        # Create agents
        code_analyzer, code_improver, pr_manager = self.create_agents()
        
        # Create tasks
        tasks = self.create_tasks(files, code_analyzer, code_improver, pr_manager)
        
        # Create and run the crew
        crew = Crew(
            agents=[code_analyzer, code_improver, pr_manager],
            tasks=tasks,
            verbose=2,
            process=Process.sequential
        )
        
        # If dry run, only run analysis tasks
        if dry_run:
            analysis_tasks = [task for task in tasks if task.agent == code_analyzer]
            analysis_crew = Crew(
                agents=[code_analyzer],
                tasks=analysis_tasks,
                verbose=2,
                process=Process.sequential
            )
            result = analysis_crew.kickoff()
            
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"\n💾 Saved analysis to {output_file}")
            
            print(f"\n🔍 Dry run completed. Analyzed {len(files)} files.")
        else:
            # Run the full crew
            result = crew.kickoff()
            
            if output_file:
                with open(output_file, 'w') as f:
                    json.dump(result, f, indent=2)
                print(f"\n💾 Saved results to {output_file}")
            
            # Extract PR URL from result
            pr_url = result.get("pr_url", "No PR URL found")
            if pr_url and "No PR URL found" not in pr_url:
                print(f"\n✅ Successfully created PR: {pr_url}")
                print(f"RepoSage suggested improvements to {len(files)} files.")
            else:
                print("\n❌ Failed to create pull request or no improvements were made.")

def main():
    try:
        # Create argument parser
        parser = argparse.ArgumentParser(description='RepoSage - AI-powered code improvement tool using CrewAI')
        
        # Add arguments with both short and long form options
        parser.add_argument('--github-token', '-g', required=True, help='GitHub token for repository access')
        parser.add_argument('--repo', '-r', dest='repo_name', required=True, help='Repository name in format owner/repo')
        parser.add_argument('--open-router-api-key', '-o', dest='openrouter_api_key', required=True, help='OpenRouter API key')
        parser.add_argument('--model', '-m', default=DEFAULT_MODEL, help=f'Model to use for analysis (default: {DEFAULT_MODEL})')
        parser.add_argument('--base-branch', '-b', default='main', help='Base branch to use for analysis (default: main)')
        parser.add_argument('--description', '-d', help='Optional description of what you want RepoSage to focus on')
        parser.add_argument('--dry-run', action='store_true', help='Generate changes but do not create PRs')
        parser.add_argument('--output-file', help='Save changes to a JSON file for later review')
        parser.add_argument('--max-workers', type=int, help='Maximum number of parallel workers for file analysis')
        
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
        
        # Run the bot with additional options
        bot.run(
            dry_run=args.dry_run,
            output_file=args.output_file,
            max_workers=args.max_workers
        )
    except Exception as e:
        logger.error(f"RepoSage failed: {str(e)}")
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()