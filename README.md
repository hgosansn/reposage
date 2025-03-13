# RepoSage

![Logo](resources/reposage.png)

RepoSage leverages AI and Retrieval-Augmented Generation (RAG) to implement features/fix bugs and makes changes on a repository.


## Features

- Analyzes the repository state
- Finds potential improvements
- Implements the improvements in the form of changesets
- Creates a pull request with the changes
- Each pull request contains a title and a description of the changes that are also generated

## Setup

1. Clone the repository.
2. Install dependencies using `pip install -r repo-sage-action/requirements.txt`.
3. Configure the bot using the `repo-sage-action/config.yaml` file.
4. Run the bot using `python repo-sage-action/bot.py`.

## Running the Bot

### Local Execution

```sh
python repo-sage-action/bot.py --github-token YOUR_TOKEN --repo owner/repo --open-router-api-key YOUR_API_KEY
```

You can also provide additional parameters:

```sh
python repo-sage-action/bot.py \
  --github-token YOUR_TOKEN \
  --repo owner/repo \
  --open-router-api-key YOUR_API_KEY \
  --model "qwen/qwq-32b:free" \
  --base-branch "main" \
  --description "Focus on improving error handling and documentation"
```

### Manual GitHub Action Trigger

You can manually trigger the RepoSage action from your GitHub repository:

1. Go to your repository on GitHub
2. Click on the "Actions" tab
3. Select the "RepoSage" workflow from the sidebar
4. Click the "Run workflow" dropdown button
5. (Optional) Configure the following parameters:
   - **Model**: AI model to use for analysis (default: qwen/qwq-32b:free)
   - **Base branch**: Branch to use for analysis (default: main)
   - **Description**: What you want RepoSage to focus on (e.g., "Improve error handling", "Optimize performance", "Enhance documentation")
6. Click "Run workflow"

## Testing the Bot

To test the bot's functionality, follow these steps:

**Run the Bot**: Once the pull request is merged, navigate to the repository's root directory and run the bot.

```sh
python repo-sage-action/bot.py --github-token YOUR_TOKEN --repo owner/repo --open-router-api-key YOUR_API_KEY
```

