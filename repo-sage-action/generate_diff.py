#!/usr/bin/env python3
"""
Generate Git diffs for RepoSage changes without creating PRs.
This script allows you to preview changes before creating PRs.
"""

import os
import sys
import argparse
import logging
import json
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('RepoSageDiff')

def save_temp_file(content: str, original_path: str) -> str:
    """Save content to a temporary file with the same extension as the original."""
    ext = Path(original_path).suffix
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode='w') as temp:
        temp.write(content)
        return temp.name

def generate_diff(original_content: str, modified_content: str, file_path: str) -> str:
    """Generate a unified diff between original and modified content."""
    if original_content == modified_content:
        return f"No changes for {file_path}"
    
    # Save contents to temporary files
    orig_file = save_temp_file(original_content, file_path)
    mod_file = save_temp_file(modified_content, file_path)
    
    try:
        # Generate diff using git diff
        cmd = [
    'git', 'diff', '--no-index', '--color=always',
    '--label', f'a/{file_path}',
    '--label', f'b/{file_path}',
    orig_file, mod_file
]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Clean up the diff output to make it more readable
        diff_lines = result.stdout.split('\n')
        # Remove temp file paths from the diff
        clean_diff = []
        for line in diff_lines:
            if orig_file in line:
                line = line.replace(orig_file, f"a/{file_path}")
            if mod_file in line:
                line = line.replace(mod_file, f"b/{file_path}")
            clean_diff.append(line)
        
        return '\n'.join(clean_diff)
    finally:
        # Clean up temporary files
        os.unlink(orig_file)
        os.unlink(mod_file)

def process_changes_file(changes_file: str) -> None:
    """Process a JSON file containing RepoSage changes and generate diffs."""
    try:
        with open(changes_file, 'r') as f:
            changes = json.load(f)
        
        if not changes:
            logger.error("No changes found in the file")
            return
        
        for idx, change in enumerate(changes, 1):
            file_path = change.get('file_path')
            if not file_path:
                logger.warning(f"Change #{idx} is missing file_path")
                continue
                
            original_content = change.get('original_content')
            if not original_content:
                logger.warning(f"Change #{idx} ({file_path}) is missing original_content")
                continue
                
            new_content = change.get('content')
            if not new_content:
                logger.warning(f"Change #{idx} ({file_path}) is missing content")
                continue
            
            # Generate and print diff
            print(f"\n{'='*80}\n")
            print(f"Changes for: {file_path}")
            print(f"{'='*80}\n")
            
            diff = generate_diff(original_content, new_content, file_path)
            print(diff)
            
            # Print summary of changes
            analysis = change.get('analysis', {})
            summary = analysis.get('summary')
            if summary:
                print(f"\nSummary: {summary}")
            
            suggested_changes = analysis.get('suggested_changes', [])
            if suggested_changes:
                print("\nDetailed changes:")
                for i, suggestion in enumerate(suggested_changes, 1):
                    explanation = suggestion.get('explanation')
                    if explanation:
                        print(f"  {i}. {explanation}")
            
            print(f"\n{'='*80}\n")
            
    except Exception as e:
        logger.error(f"Error processing changes file: {str(e)}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description='Generate diffs for RepoSage changes')
    parser.add_argument('changes_file', help='JSON file containing RepoSage changes')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.changes_file):
        logger.error(f"Changes file not found: {args.changes_file}")
        sys.exit(1)
        
    process_changes_file(args.changes_file)

if __name__ == "__main__":
    main()
