import os
import logging
from datetime import datetime
from pathlib import Path
from github import Github
from typing import List, Dict, Any, Optional

# Configure logging for GitHub PR functionality
logger = logging.getLogger('RepoSage.GitHubPR')

class GitHubPRManager:
    def __init__(self, github_token, repo_name, base_branch='main'):
        """Initialize the GitHub PR Manager.
        
        Args:
            github_token (str): GitHub authorization token
            repo_name (str): Repository name in format 'owner/repo'
            base_branch (str): Base branch to create PRs against (default: 'main')
        """
        self.github_token = github_token
        self.repo_name = repo_name
        self.base_branch = base_branch
        
        # Initialize GitHub client
        self.github = Github(self.github_token)
        self.repo = self.github.get_repo(self.repo_name)
        
        # Generate a unique branch name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        self.branch_name = f"reposage-improvements-{timestamp}"
        
        logger.info(f"Initialized GitHub PR Manager for repository: {self.repo_name}")
    
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