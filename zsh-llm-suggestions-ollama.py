#!/usr/bin/env python3
import sys
import subprocess
import json
import os
import platform
import distro
import subprocess
import os
import socket
import psutil
import pygments

def colorize_output(text):
    try:
        return highlight(text, BashLexer(), TerminalFormatter())
    except ImportError:
        print(f'echo "{MISSING_PREREQUISITES} Install pygments" && pip3 install pygments')
        return text  # Return unhighlighted text if pygments is not installed

def highlight_explanation(explanation):
    try:
        from pygments.lexers import MarkdownLexer
        from pygments.formatters import TerminalFormatter
        return pygments.highlight(explanation, MarkdownLexer(), TerminalFormatter(style='material'))
    except ImportError:
        print(f'echo "{MISSING_PREREQUISITES} Install pygments" && pip3 install pygments')
        return explanation  # Return unhighlighted text if pygments is not installed

def get_system_load():
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_usage = psutil.virtual_memory().percent
    return cpu_usage, memory_usage

def get_shell_version():
    result = subprocess.run(["zsh", "--version"], capture_output=True, text=True)
    return result.stdout.strip()

def is_user_root():
    return os.geteuid() == 0

def get_cpu_architecture():
    return platform.machine()

def get_network_info():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return hostname, ip_address

def get_env_vars():
    path = os.getenv('PATH')
    home = os.getenv('HOME')
    ld_library_path = os.getenv('LD_LIBRARY_PATH')
    return path, home, ld_library_path

def get_current_username():
    return os.environ.get('USER', os.environ.get('USERNAME', 'Unknown User'))

def get_os_info():
    try:
        # This will work on Linux distributions with the distro module installed
        os_id = distro.id()
        os_version = distro.version()
        os_name = distro.name()
        return f"{os_name} ({os_id} {os_version})".strip()
    except ModuleNotFoundError:
        # Fallback for non-Linux platforms
        system = platform.system()
        version = platform.version()
        return f"{system} {version}".strip()

def filter_non_ascii(text):
    return ''.join(char for char in text if ord(char) < 128)

MISSING_PREREQUISITES = "zsh-llm-suggestions missing prerequisites:"

def highlight_explanation(explanation):
    try:
        from pygments.lexers import MarkdownLexer
        from pygments.formatters import TerminalFormatter
        return pygments.highlight(explanation, MarkdownLexer(), TerminalFormatter(style='material'))
    except ImportError:
        print(f'echo "{MISSING_PREREQUISITES} Install pygments" && pip3 install pygments')
        return explanation  # Return unhighlighted text if pygments is not installed

def send_request(prompt, system_message=None, context=None):
    server_address = os.environ.get('ZSH_LLM_SUGGESTION_SERVER', 'localhost:11434')
    model = os.environ.get('ZSH_LLM_SUGGESTION_MODEL', 'tinyllama')  # Default model

    # Base request data
    data = {
        "model": model,
        "prompt": prompt,
        "keep_alive": "30m",
        "stream": False
    }

    # Optional parameters: Check and add if set
    optional_params = [
        "num_ctx",        # Context length
        "temperature",    # Sampling randomness
        "top_k",          # Top-K sampling
        "top_p",          # Nucleus sampling
        "repeat_penalty", # Penalizes repetition
        "frequency_penalty",  # Penalizes frequent tokens
        "presence_penalty",   # Penalizes new tokens based on presence
        "mirostat",       # Mirostat sampling
        "mirostat_tau",   # Mirostat parameter
        "mirostat_eta",   # Mirostat parameter
        "stop"            # Stop sequences
    ]

    for param in optional_params:
        value = os.environ.get(f"ZSH_LLM_SUGGESTION_{param.upper()}")
        if value is not None:
            # Convert numeric values appropriately
            if param in ["temperature", "top_p", "repeat_penalty", "frequency_penalty", "presence_penalty", "mirostat_tau", "mirostat_eta"]:
                data[param] = float(value)
            elif param in ["top_k", "mirostat", "num_ctx"]:
                data[param] = int(value)
            elif param == "stop":
                # Handle stop sequences as a JSON array if provided
                try:
                    data[param] = json.loads(value) if value.startswith("[") else value
                except json.JSONDecodeError:
                    print(f"Invalid JSON format for {param}, skipping.")
            else:
                data[param] = value

    # Handle context if enabled
    use_context = os.environ.get('ZSH_LLM_SUGGESTION_USE_CONTEXT', 'true').lower() == 'true'
    if context and use_context:
        data["context"] = context

    debug = os.environ.get('ZSH_LLM_SUGGESTION_DEBUG', 'false').lower() == 'true'
    if debug:
            print("Final API Request Payload:")
            print(json.dumps(data, indent=4))  # Pretty-print the data dictionary for easy debugging

    try:
        response = subprocess.run(
            ["curl", "-XPOST", f"http://{server_address}/api/generate", "-H", "Content-Type: application/json", "-d", json.dumps(data)],
            capture_output=True,
            text=True,
            timeout=60
        )
        if response.returncode != 0:
            return f"Curl error: {response.stderr.strip()}", None

        if response.stdout:
            try:
                json_response = json.loads(response.stdout)
                if "error" in json_response:
                    return f"Error from server: {json_response['error']}", None
                return json_response.get('response', 'No response received.'), json_response.get('context', None)
            except json.JSONDecodeError:
                return f"Invalid JSON response: {response.stdout.strip()}", None
        else:
            return "No response received.", None

    except subprocess.TimeoutExpired:
        return "Request timed out. Please try again.", None
    except Exception as e:
        return f"Unexpected error: {str(e)}", None

def zsh_llm_suggestions_ollama(prompt, system_message=None, context=None):
    try:
        result, new_context = send_request(prompt, system_message, context)
        return result, new_context
    except Exception as e:
        print(f"Error: {e}")
        return "", None

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ['generate', 'explain', 'freestyle']:
        mode = sys.argv[1]
        prompt_index = 2
    else:
        mode = 'freestyle'  # Default mode
        prompt_index = 1

    if not sys.stdin.isatty():
        input_content = sys.stdin.read().strip()  # Read piped input directly
        if len(sys.argv) > prompt_index:
            prompt = ' '.join(sys.argv[prompt_index:])
            buffer = f"{prompt}\n{input_content}"
        else:
            buffer = input_content
    else:
        if len(sys.argv) > prompt_index:
            buffer = ' '.join(sys.argv[prompt_index:])
        else:
            buffer = input("Enter your prompt: ").strip()

    system_message = None
    context = None

    os_info = get_os_info()
    shell_version = get_shell_version()
    user_is_root = is_user_root()
    cpu_arch = get_cpu_architecture()
    path, home, ld_library_path = get_env_vars()
    username = get_current_username()
    freestyle_system_message = os.environ.get('OLLAMA_FREESTYLE_SYSTEM_MESSAGE')

    #Unused
    #hostname, ip_address = get_network_info()
    #cpu_usage, memory_usage = get_system_load()
    #Your system is on {hostname} ({ip_address}), with CPU usage at {cpu_usage}% and memory usage at {memory_usage}%

    if mode == 'generate':
        system_message = f"You are a ZSH shell expert using {os_info} on {cpu_arch}, shell version {shell_version}, running as {'root' if user_is_root else f'non-root as user {username}'}. Please write a ZSH command that solves my query without any additional explanation."
    elif mode == 'explain':
        system_message = f"You are a ZSH shell expert using {os_info} on {cpu_arch}, shell version {shell_version}, running as {'root' if user_is_root else f'non-root as user {username}'}. Please briefly explain how the given command works. Be as concise as possible using Markdown syntax."
    elif mode == 'freestyle':
        # Load the previous context only for freestyle mode
        try:
            with open(os.path.expanduser('~/.ollama_history'), 'r') as file:
                file_contents = file.read().strip()
                if file_contents:
                    context = json.loads(file_contents)
        except FileNotFoundError:
            context = None  # Handle the case where the file does not exist
            if freestyle_system_message:
                system_message = freestyle_system_message
        except json.JSONDecodeError:
            print("Failed to decode JSON from context file. It may be corrupt or empty.")
            context = None
        except Exception as e:
            print(f"Unexpected error when loading context: {e}")
    result, new_context = zsh_llm_suggestions_ollama(buffer, system_message, context)
    result=filter_non_ascii(result)
    if mode == 'freestyle':
        # Save the new context only for freestyle mode
        try:
            with open(os.path.expanduser('~/.ollama_history'), 'w') as file:
                if new_context is not None:
                    file.write(json.dumps(new_context))
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
