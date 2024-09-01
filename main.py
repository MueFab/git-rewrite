import os
import random
import subprocess
import sys
import git
import openai
from openai import OpenAI

# Retrieve the OpenAI API key from an environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    print("Error: The OpenAI API key is not set. Please set the 'OPENAI_API_KEY' environment variable.")
    sys.exit(1)

def generate_commit_message(diff, current_message):
    """
    Generate a commit message using OpenAI's GPT model.

    Args:
        diff (str): The git diff for the commit.
        current_message (str): The current commit message.

    Returns:
        str: The generated commit message.
    """

    truncated_diff = truncate_diff(diff)

    client = OpenAI(
        # This is the default and can be omitted
        api_key=os.environ.get("OPENAI_API_KEY"),
    )
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that writes descriptive, but concise and improved commit messages for git repositories. You only ever answer with the new commit message only, and with no additional comments or statements.",
            },
            {
                "role": "user",
                "content": "Improve the following commit message:\n\n'"+ current_message +"'\n\nBased on the following git diff:" + truncated_diff + "\n\n",
            },
        ]
    )
    return response.choices[0].message.content

def truncate_diff(diff, max_length=10000):
    """
    Truncate the diff by removing the longest lines first until it is smaller than max_length.

    Args:
        diff (str): The git diff for the commit.
        max_length (int): The maximum allowed length for the diff.

    Returns:
        str: The truncated diff.
    """
    diff_lines = diff.splitlines()

    # Sort lines by length in descending order (longest lines first)
    diff_lines.sort(key=len, reverse=True)

    while len("\n".join(diff_lines)) > max_length:
        if len(diff_lines) == 1:  # Safety check to prevent infinite loop
            break
        diff_lines.pop(0)  # Remove the longest line

    return "\n".join(diff_lines)


def run_command(command):
    """Run a shell command and return the output."""
    result = subprocess.run(command, shell=True, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def change_commit_messages_to_bob():
    # Get the list of all commits in reverse order
    commits = run_command("git rev-list --reverse HEAD").splitlines()

    # Create a new branch to rewrite history
    subprocess.run("git checkout -b rewrite-history", shell=True, check=True)

    for commit in commits:
        # Reset to each commit, amend the message, and then continue
        try:
            subprocess.run(f"git cherrypick {commit}", shell=True, check=True)
            subprocess.run("git commit --amend -m 'bob'", shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to amend commit {commit}: {e}")
            break

    # Finally, force push the rewritten history to the original branch
    subprocess.run("git checkout main", shell=True, check=True)  # replace 'main' with your branch name if different
    subprocess.run("git reset --hard rewrite-history", shell=True, check=True)
    print("All commits have been changed to 'bob'. Now you can force push your changes.")


def apply_messages(repo, commit_hashes, new_messages):
    """
    Rebase and reword commit messages by creating a new branch and applying the changes.

    Args:
        repo (git.Repo): The git repository object.
        commit_hashes (list): List of commit hashes to be rebased.
        new_messages (list): List of new commit messages corresponding to each commit.
    """
    if len(commit_hashes) != len(new_messages):
        print("Error: The number of commit hashes and new messages must be the same.")
        return

    # Create a new branch from the current branch
    current_branch = repo.active_branch.name
    new_branch_name = current_branch + "-amended"

    change_commit_messages_to_bob()

def main(repo_path, start_commit=None):
    """
    Main function to process all commits in the current branch.

    Args:
        repo_path (str): Path to the git repository.
        start_commit (str): The earliest commit hash to start updating. If None, all commits on the current branch will be updated.
    """
    repo = git.Repo(repo_path)

    current_branch = repo.active_branch.name

    # Create a new branch from the current branch
    #new_branch_name = current_branch + "-amended"
    #repo.git.checkout('-b', new_branch_name)

    commits = list(repo.iter_commits(current_branch))

    # If a start commit is provided, filter commits to start from that commit
    if start_commit:
        try:
            start_commit_obj = repo.commit(start_commit)
            commits = [commit for commit in commits if commit.committed_date >= start_commit_obj.committed_date]
        except git.exc.BadName:
            print(f"Error: Invalid commit hash {start_commit}")
            sys.exit(1)

    commit_hashes = []
    new_messages = []

    for commit in reversed(commits):
        # Get the diff for the commit
        diff = repo.git.diff(f'{commit.hexsha}^!', '--unified=0')

        # Generate a new commit message using the current message and diff
        new_message = "bob" #generate_commit_message(diff, commit.message.strip())
        print(f"Old Message: {commit.message.strip()}\nNew Message: {new_message}\n")

        # Store the commit hash and new message for rebasing
        commit_hashes.append(commit.hexsha)
        new_messages.append(new_message)

    # Apply the new commit messages via rebase
    apply_messages(repo, commit_hashes, new_messages)

if __name__ == "__main__":
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python script.py /path/to/repo [start_commit_hash]")
        sys.exit(1)

    repo_path = sys.argv[1]
    start_commit = sys.argv[2] if len(sys.argv) == 3 else None

    if not os.path.isdir(repo_path):
        print("Invalid directory path.")
        sys.exit(1)

    main(repo_path, start_commit)
