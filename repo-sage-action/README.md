# RepoSage GitHub Action

An AI-driven bot that analyzes a repository and suggests improvements using CrewAI and OpenRouter.

## Overview

RepoSage is a GitHub Action that uses AI to analyze your codebase and suggest concrete improvements. It can:

1. Analyze your repository's code files
2. Identify potential improvements
3. Generate specific code changes
4. Create individual pull requests for each file
5. Provide detailed explanations for each suggested change

## Features

- **CrewAI Integration**: Uses CrewAI's agent-based architecture for sophisticated code analysis
- **Role-Based Agents**: Specialized agents for code analysis, improvement, and PR management
- **OpenRouter Integration**: Access to a wide range of AI models through OpenRouter
- **Dry Run Mode**: Preview changes without creating PRs
- **Customizable**: Configure which model to use, what to focus on, and more

## Usage

### GitHub Action

Add this to your GitHub workflow:

```yaml
name: RepoSage Code Improvement

on:
  workflow_dispatch:  # Manual trigger
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday at midnight

jobs:
  improve-code:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run RepoSage
        uses: your-username/repo-sage-action@main
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          open_router_api_key: ${{ secrets.OPENROUTER_API_KEY }}
          # Optional parameters:
          # model: "qwen/qwq-32b:free"
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
  --model "qwen/qwq-32b:free" \
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
| `model` | AI model to use for analysis | No | qwen/qwq-32b:free |
| `base_branch` | Base branch to use for analysis | No | main |
| `description` | Optional description of what you want RepoSage to focus on | No | - |
| `dry_run` | Generate changes but do not create PRs | No | false |
| `output_file` | Save changes to a JSON file for later review | No | - |
| `max_workers` | Maximum number of parallel workers for file analysis | No | Auto (based on CPU) |

## How It Works

RepoSage now uses CrewAI to orchestrate a team of specialized AI agents:

1. **Code Analyzer Agent**: Analyzes code files for quality issues, bugs, and improvement opportunities
2. **Code Improver Agent**: Implements improvements to code based on the analysis
3. **PR Manager Agent**: Creates well-documented pull requests for the code improvements

Each agent has specific tools and capabilities:

- **GitHub File Tool**: Fetches file content from the repository
- **GitHub Commit Tool**: Commits changes to files
- **GitHub PR Tool**: Creates pull requests

## Advanced Usage

### Dry Run Mode

You can use the dry run mode to generate analysis without creating PRs, and save the results to a file for review:

```bash
python bot.py \
  --github-token YOUR_GITHUB_TOKEN \
  --open-router-api-key YOUR_OPENROUTER_API_KEY \
  --repo owner/repo-name \
  --dry-run \
  --output-file "analysis.json"
```

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
- Required packages (see requirements.txt):
  - PyGithub
  - requests
  - openai
  - pyyaml
  - crewai
  - langchain-openrouter
  - langchain-core

## License

[MIT License](LICENSE)
