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

```sh
python repo-sage-action/bot.py
```

## Testing the Bot

To test the bot's functionality, follow these steps:



**Run the Bot**: Once the pull request is merged, navigate to the repository's root directory and run the bot.

    ```sh
    python repo-sage-action/bot.py
    ```

