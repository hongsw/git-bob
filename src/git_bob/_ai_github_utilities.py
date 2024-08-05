# This module contains utility functions for interacting with GitHub issues and pull requests using AI.
# It includes functions for setting up AI remarks, commenting on issues, reviewing pull requests, and solving issues.

from ._utilities import remove_indentation, catch_error
from ._logger import Log

SYSTEM_PROMPT = """You are an extremely skilled python developer. Your name is git-bob."""

def setup_ai_remark():
    """
    Set up the AI remark for comments.

    Returns
    -------
    str
        The AI remark string.
    """
    from git_bob import __version__
    from ._utilities import get_llm_name
    model = get_llm_name()
    return f"<sup>This message was generated by [git-bob](https://github.com/haesleinhuepf/git-bob) (version:{__version__}, model:{model}), an experimental AI-based assistant. It can make mistakes and has [limitations](https://github.com/haesleinhuepf/git-bob?tab=readme-ov-file#limitations). Check its messages carefully.</sup>"


@catch_error
def comment_on_issue(repository, issue, prompt_function):
    """
    Comment on a GitHub issue using a prompt function.

    Parameters
    ----------
    repository : str
        The full name of the GitHub repository.
    issue : int
        The issue number to comment on.
    prompt_function : function
        The function to generate the comment.
    """
    Log().log(f"-> comment_on_issue({repository}, {issue})")
    from ._github_utilities import get_conversation_on_issue, add_comment_to_issue

    ai_remark = setup_ai_remark()

    discussion = get_conversation_on_issue(repository, issue)
    print("Discussion:", discussion)

    comment = prompt_function(remove_indentation(f"""
    {SYSTEM_PROMPT}
    Respond to a github issue. Its entire discussion is given.

    ## Discussion

    {discussion}

    ## Your task

    Respond to the discussion above. 
    Do NOT explain your response or anything else. 
    Just respond to the discussion.
    """))

    print("comment:", comment)

    add_comment_to_issue(repository, issue, remove_indentation(f"""        
    {ai_remark}

    {comment}
    """))


@catch_error
def review_pull_request(repository, issue, prompt_function):
    """
    Review a GitHub pull request using a prompt function.

    Parameters
    ----------
    repository : str
        The full name of the GitHub repository.
    issue : int
        The pull request number to review.
    prompt_function : function
        The function to generate the review comment.
    """
    Log().log(f"-> review_pull_request({repository}, {issue})")
    from ._github_utilities import get_conversation_on_issue, add_comment_to_issue, get_diff_of_pull_request

    ai_remark = setup_ai_remark()

    discussion = get_conversation_on_issue(repository, issue)
    print("Discussion:", discussion)

    file_changes = get_diff_of_pull_request(repository, issue)

    print("file_changes:", file_changes)

    comment = prompt_function(remove_indentation(f"""
    {SYSTEM_PROMPT}
    Generate a response to a github pull-request. 
    Given are the discussion on the pull-request and the changed files.

    ## Discussion

    {discussion}

    ## Changed files

    {file_changes}

    ## Your task

    Review this pull-request and contribute to the discussion. 
    
    Do NOT explain your response or anything else. 
    Just respond to the discussion.
    """))

    print("comment:", comment)

    add_comment_to_issue(repository, issue, remove_indentation(f"""        
    {ai_remark}

    {comment}
    """))


@catch_error
def summarize_github_issue(repository, issue, prompt_function):
    """
    Summarize a GitHub issue.

    Parameters
    ----------
    repository : str
        The full name of the GitHub repository.
    issue : int
        The issue number to summarize.
    llm_model : str
        The language model to use for generating the summary.
    """
    Log().log(f"-> summarize_github_issue({repository}, {issue})")
    from ._github_utilities import get_github_issue_details

    issue_conversation = get_github_issue_details(repository, issue)

    summary = prompt_function(remove_indentation(f"""
    Summarize the most important details of this issue #{issue} in the repository {repository}. 
    In case filenames, variables and code-snippetes are mentioned, keep them in the summary, they are very important.
    
    ## Issue to summarize:
    {issue_conversation}
    """))

    print("Issue summary:", summary)
    return summary


@catch_error
def create_or_modify_file(repository, issue, filename, branch_name, issue_summary, prompt_function):
    """
    Create or modify a file in a GitHub repository.

    Parameters
    ----------
    repository : str
        The full name of the GitHub repository.
    issue : int
        The issue number to solve.
    filename : str
        The name of the file to create or modify.
    branch_name : str
        The name of the branch to create or modify the file in.
    issue_summary : str
        The summary of the issue to solve.
    """
    Log().log(f"-> create_or_modify_file({repository}, {issue}, {filename}, {branch_name})")
    from ._github_utilities import get_repository_file_contents, write_file_in_new_branch, create_branch, check_if_file_exists
    from ._utilities import remove_outer_markdown, split_content_and_summary

    try:
        file_content = get_repository_file_content(repository, branch_name, file_path)
        print(filename, "will be overwritten")
        file_content_instruction = remove_indentation(remove_indentation(f"""Modify the file "{filename}" to solve the issue #{issue}:
        <BEGIN_FILE>
        {file_content}
        </END_FILE>
        """))
    except:
        print(filename, "will be created")
        file_content_instruction = remove_indentation(remove_indentation(f"""Create the file "{filename}" to solve the issue #{issue}.
        """))

    response = prompt_function(remove_indentation(f"""
    Given a github issue summary (#{issue}) and optionally, file content (filename {filename}), modify the file content or create the file content to solve the issue.
    
    ## Issue {issue} Summary
    
    {issue_summary}
    
    ## File {filename}
    {file_content_instruction}
    
    ## Your task
    Generate content of file "{filename}" to [partially] solve the issue above.
    Do not do any additional modifications you were not instructed to do.
    Respond ONLY the content of the file and afterwards a single line summarizing the changes you made (without mentioning the issue).
    """))

    new_content, commit_message = split_content_and_summary(response)


    print("New file content", new_content)
    print("Summary", commit_message)

    write_file_in_new_branch(repository, branch_name, filename, new_content, commit_message)

    return commit_message


@catch_error
def solve_github_issue(repository, issue, llm_model, prompt_function):
    """
    Attempt to solve a GitHub issue by modifying a single file and sending a pull-request.

    Parameters
    ----------
    repository : str
        The full name of the GitHub repository.
    issue : int
        The issue number to solve.
    llm_model : str
        The language model to use for generating the solution.
    """
    # modified from: https://github.com/ScaDS/generative-ai-notebooks/blob/main/docs/64_github_interaction/solving_github_issues.ipynb

    Log().log(f"-> solve_github_issue({repository}, {issue})")

    from ._github_utilities import get_github_issue_details, list_repository_files, get_repository_file_contents, write_file_in_new_branch, send_pull_request, add_comment_to_issue, create_branch, check_if_file_exists, get_diff_of_branches
    from ._utilities import remove_outer_markdown, split_content_and_summary
    from blablado import Assistant
    import json

    ai_remark = setup_ai_remark()

    issue_summary = summarize_github_issue(repository, issue, prompt_function)

    all_files = "* " + "\n* ".join(list_repository_files(repository))

    relevant_files = remove_outer_markdown(prompt_function(remove_indentation(f"""
    Given a list of files in the repository {repository} and a github issues description (# {issue}), determine which files are relevant to solve the issue.
    
    ## Files in the repository
    
    {all_files}
    
    ## Github Issue (#{issue}) Summary
    
    {issue_summary}
    
    ## Your task
    Which of these files might be relevant for issue #{issue} ? 
    You can also consider files which do not exist yet. 
    Respond ONLY the filenames as JSON list.
    """)))

    filenames = json.loads(relevant_files)

    # create a new branch
    branch_name = create_branch(repository)

    """
    assistant = Assistant(model=llm_model)
    assistant.register_tool(get_github_issue_details)
    assistant.register_tool(list_repository_files)
    assistant.register_tool(create_branch)
    assistant.register_tool(send_pull_request)

    issue_summary = assistant.tell(f"Summarize the most important details of issue #{issue} in the repository {repository}")
    print("issue_summary", issue_summary)

    assistant.do(f"List all files in the repository {repository}")
    filenames_json = remove_outer_markdown(assistant.tell("Which of these files might be relevant for issue #{issue} ? You can also consider files which do not exist yet. Respond ONLY the filenames  as JSON list."))

    print("Related filenames", filenames_json)

    # parse the filenames_json into list:
    import json
    filenames = json.loads(filenames_json)

    branch_name = assistant.tell(f"Create a new branch on repository {repository}. Respond ONLY the branch name.")
    branch_name = branch_name.strip().strip('"')
    """

    print("Created branch", branch_name)

    errors = []
    commit_messages = []
    for filename in filenames:
        if filename.startswith(".github/workflows"):
            # skip github workflows
            continue
        try:
            message = filename + ":" + create_or_modify_file(repository, issue, filename, branch_name, issue_summary, prompt_function)
            commit_messages.append(message)
        except Exception as e:
            errors.append(f"Error processing {filename}" + str(e))

    error_messages = ""
    if len(errors) > 0:
        error_messages = "The following errors occurred:\n\n* " + "\n* ".join(errors) + "\n"

    # get a diff of all changes
    diffs_prompt = get_diff_of_branches(repository, branch_name)

    # summarize the changes
    commit_messages_prompt = "* " + "\n* ".join(commit_messages)
    pull_request_summary = prompt_function(remove_indentation(f"""
    Given a list of commit messages and a git diff, summarize the changes you made in the files.
    You modified the repository {repository} to solve the issue #{issue}, which is also summarized below.
    
    ## Issue Summary
    
    {issue_summary}
    
    ## Commit messages
    You committed these changes to these files
    
    {commit_messages_prompt}
        
    ## Git diffs
    The following changes were made in the files:
    
    {diffs_prompt}
        
    ## Your task
    Summarize the changes above to a one paragraph line Github pull-request message. 
    Afterwards, summarize the summary in a single line, which will become the title of the pull-request.
    Do not add headnline or any other formatting. Just respond with the paragraphe and the title in a new line below.
    """))

    pull_request_description, pull_request_title = split_content_and_summary(pull_request_summary)

    send_pull_request(repository, branch_name, pull_request_title, pull_request_description + "\n\ncloses #" + str(issue))
