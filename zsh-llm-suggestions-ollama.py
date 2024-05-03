#!/usr/bin/env python3
import sys
import subprocess
import json
import os

MISSING_PREREQUISITES = "zsh-llm-suggestions missing prerequisites:"

def highlight_explanation(explanation):
    try:
        import pygments
        from pygments.lexers import MarkdownLexer
        from pygments.formatters import TerminalFormatter
        return pygments.highlight(explanation, MarkdownLexer(), TerminalFormatter(style='material'))
    except ImportError:
        print(f'echo "{MISSING_PREREQUISITES} Install pygments" && pip3 install pygments')
        return explanation  # Return unhighlighted text if pygments is not installed

def send_request(prompt):
    model = os.environ.get('ZSH_LLM_SUGGESTION_MODEL', 'tinyllama')
    data = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False
    })
    try:
        response = subprocess.run(
            ["curl", "-XPOST", "localhost:11434/api/generate", "-d", data],
            capture_output=True,
            text=True,
            timeout=60
        )
        if response.stdout:
            # Parse the JSON response
            json_response = json.loads(response.stdout)
            # Extract the 'response' field from the JSON object
            command_response = json_response.get('response', 'No response received.')
            return command_response
        else:
            return "No response received."
    except subprocess.TimeoutExpired:
        return "Request timed out. Please try again."
    except json.JSONDecodeError:
        return "Failed to decode the response. Please check the API response format."
    except Exception as e:
        return f"Error: {str(e)}"

def zsh_llm_suggestions_ollama(prompt):
    try:
        print("Processing your request...")
        result = send_request(prompt)
        return result
    except Exception as e:
        print(f"Error: {e}")
        return ""

def main():
    mode = sys.argv[1]
    if mode != 'generate' and mode != 'explain':
        print("ERROR: something went wrong in zsh-llm-suggestions, please report a bug. Got unknown mode: " + mode)
        return

    buffer = sys.stdin.read()
    if mode == 'generate':
        message = f"You are a ZSH shell expert. Please write a ZSH command that solves my query. You should only output the completed command. Do not include any explanation at all. The query follows: '{buffer}'"
    elif mode == 'explain':
        message = f"You are a ZSH shell expert. Please briefly explain how the given command works. Be as concise as possible. Use Markdown syntax for formatting. The command follows: '{buffer}'"
    result = zsh_llm_suggestions_ollama(message)

    if mode == 'generate':
        result = result.replace('```bash', '').replace('```zsh', '').replace('```', '').strip()
        print(result)
    elif mode == 'explain':
        print(highlight_explanation(result))

if __name__ == '__main__':
    main()
