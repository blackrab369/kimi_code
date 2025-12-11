import os
from github import Github, GithubException

def get_github_client(token):
    """
    Authenticate with GitHub using a Personal Access Token (PAT).
    """
    try:
        g = Github(token)
        user = g.get_user()
        print(f"Authenticated as: {user.login}")
        return g, user
    except Exception as e:
        print(f"Authentication failed: {e}")
        return None, None

def create_or_get_repo(user, repo_name):
    """
    Get a repository if it exists, otherwise create it.
    """
    try:
        repo = user.get_repo(repo_name)
        print(f"Repository '{repo_name}' already exists.")
    except GithubException:
        print(f"Creating repository '{repo_name}'...")
        repo = user.create_repo(repo_name, private=True) # Default to private for safety
        print(f"Repository '{repo_name}' created.")
    return repo

def upload_file_to_github(repo, file_path, content, commit_message="Update from Antigravity AI"):
    """
    Upload or update a file in the GitHub repository.
    """
    try:
        # Check if file exists to update or create
        try:
            contents = repo.get_contents(file_path)
            repo.update_file(contents.path, commit_message, content, contents.sha)
            print(f"Updated {file_path}")
        except GithubException:
            repo.create_file(file_path, commit_message, content)
            print(f"Created {file_path}")
            
        return True
    except Exception as e:
        print(f"Failed to upload {file_path}: {e}")
        return False
