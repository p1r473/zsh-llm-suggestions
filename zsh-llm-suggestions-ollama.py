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

def send_request(prompt, system_message=None, context=None):
    server_address = os.environ.get('ZSH_LLM_SUGGESTION_SERVER', 'localhost:11434')
    model = os.environ.get('ZSH_LLM_SUGGESTION_MODEL', 'tinyllama')
    data = {
        "model": model,
        "prompt": prompt,
	"keep_alive": "30m",
        "stream": False
    }
    if system_message:
        data["system"] = system_message
    if context:
        data["context"] = context

    try:
        response = subprocess.run(
            ["curl", "-XPOST", f"http://{server_address}/api/generate", "-H", "Content-Type: application/json", "-d", json.dumps(data)],
            capture_output=True,
            text=True,
            timeout=60
        )
        if response.stdout:
            json_response = json.loads(response.stdout)
            return json_response.get('response', 'No response received.'), json_response.get('context', None)
        else:
            return "No response received.", None
    except subprocess.TimeoutExpired:
        return "Request timed out. Please try again.", None
    except json.JSONDecodeError:
        return "Failed to decode the response. Please check the API response format.", None
    except Exception as e:
        return f"Error: {str(e)}", None

def zsh_llm_suggestions_ollama(prompt, system_message=None, context=None):
    try:
        result, new_context = send_request(prompt, system_message, context)
        return result, new_context
    except Exception as e:
        print(f"Error: {e}")
        return "", None

def main():
    mode = sys.argv[1]
    if mode not in ['generate', 'explain', 'freestyle']:
        print("ERROR: something went wrong in zsh-llm-suggestions, please report a bug. Got unknown mode: " + mode)
        return

    buffer = sys.stdin.read()
    system_message = None
    if mode == 'generate':
        system_message = "You are a ZSH shell expert. Please write a ZSH command that solves my query. Do not include any explanation at all."
    elif mode == 'explain':
        system_message = "You are a ZSH shell expert. Please briefly explain how the given command works. Be as concise as possible. Use Markdown syntax for formatting."

    # Load the previous context
    try:
        with open(os.path.expanduser('~/.ollama_history'), 'r') as file:
            file_contents = file.read().strip()  # Read and strip whitespace
            if file_contents:  # Check if the file is not empty
                context = json.loads(file_contents)
            else:
                context = None  # Set context to None if the file is empty
    except FileNotFoundError:
        context = None  # Handle the case where the file does not exist
    except json.JSONDecodeError:
        print("Failed to decode JSON from context file. It may be corrupt or empty.")
        context = None  # Reset context if there's an error decoding it
    except Exception as e:
        print(f"Unexpected error when loading context: {e}")
        context = None

    result, new_context = zsh_llm_suggestions_ollama(buffer, system_message, context)

    # Store the new context
    try:
        with open(os.path.expanduser('~/.ollama_history'), 'w') as file:
            if new_context is not None:
                file.write(json.dumps(new_context))  # Assuming new_context needs to be serialized
    except Exception as e:
        print(f"Error saving context: {e}")

    if mode == 'generate':
        result = result.replace('```bash', '').replace('```zsh', '').replace('```', '').strip()
        print(result)
    elif mode == 'explain':
        print(highlight_explanation(result))
    elif mode == 'freestyle':
        print(result)

if __name__ == '__main__':
    main()
