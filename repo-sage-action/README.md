# RepoSage GitHub Action

An AI-driven bot that analyzes a repository and suggests improvements based on AI and RAG (Retrieval-Augmented Generation).

## Overview

RepoSage is a GitHub Action that uses AI to analyze your codebase and suggest concrete improvements. It can:

1. Analyze your repository's code files
2. Identify potential improvements
3. Generate specific code changes
4. Create individual pull requests for each file
5. Provide detailed explanations for each suggested change

## Features

- **Parallel Processing**: Analyzes multiple files simultaneously for faster execution
- **Individual PRs**: Creates separate pull requests for each file change for easier review
- **Dry Run Mode**: Preview changes without creating PRs
- **Diff Generation**: Save changes to a file and review diffs before creating PRs
- **Customizable**: Configure which model to use, what to focus on, and more

## Usage

### GitHub Action

Add this to your GitHub workflow:

```yaml
name: RepoSage Code Improvement

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 0 * * 0' # Runs weekly on Sunday midnight (UTC)  # Weekly on Sunday at midnight

jobs:
  improve-code:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run RepoSage
        uses: <your-username>/repo-sage-action@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          open_router_api_key: ${{ secrets.OPENROUTER_API_KEY }}
          # Optional parameters:
          # model: "google/gemma-3-27b-it:free"
          # base_branch: "main"
          # description: "Focus on performance improvements and code readability"
          # dry_run: "false"
          # output_file: "reposage-changes.json"
          # max_workers: "4"
```

### Command Line Usage

You can also run RepoSage directly from the command line:

```bash
python bot.py \
  --github-token YOUR_GITHUB_TOKEN \
  --open-router-api-key YOUR_OPENROUTER_API_KEY \
  --repo owner/repo-name \
  --model "google/gemma-3-27b-it:free" \
  --base-branch "main" \
  --description "Focus on performance improvements" \
  --max-workers 4
```

## Parameters

| Parameter | Description | Required | Default |
|-----------|-------------|----------|---------|
| `github_token` | GitHub Token for repository access | Yes | - |
| `open_router_api_key` | OpenRouter API Key | Yes | - |
| `repo` | Repository to analyze (format: owner/repo) | Yes | - |
| `model` | AI model to use for analysis | No | google/gemma-3-27b-it:free |
| `base_branch` | Base branch to use for analysis | No | main |
| `description` | Optional description of what you want RepoSage to focus on | No | - |
| `dry_run` | Generate changes but do not create PRs | No | false |
| `output_file` | Save changes to a JSON file for later review | No | - |
| `max_workers` | Maximum number of parallel workers for file analysis | No | Auto (based on CPU) |

## Advanced Usage

### Generating and Reviewing Diffs

You can use the dry run mode to generate changes without creating PRs, and save them to a file for review:

```bash
python bot.py \
  --github-token YOUR_GITHUB_TOKEN \
  --open-router-api-key YOUR_OPENROUTER_API_KEY \
  --repo owner/repo-name \
  --dry-run \
  --output-file "changes.json"
```

Then review the changes using the diff generator:

```bash
python generate_diff.py changes.json
```

This will show you a git-style diff for each file that would be changed, allowing you to review before creating PRs.

### Creating Individual PRs

By default, RepoSage creates individual PRs for each file change This makes it easier to:

1. Review changes for each file independently
2. Merge changes selectively
3. Track the status of each improvement separately

## Supported File Types

RepoSage can analyze the following file types:
- Python (.py)
- JavaScript (.js)
- TypeScript (.ts)
- JSX/TSX (.jsx, .tsx)
- Java (.java)
- HTML (.html)
- CSS (.css)
- Markdown (.md)
- YAML (.yml, .yaml)

## Requirements

- Python 3.8+
- GitHub repository access

## License

[MIT License](LICENSE)
