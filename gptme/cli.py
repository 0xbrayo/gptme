"""
GPTMe
=====

This is an AI agent called GPTMe, it is designed to be a helpful companion.

It should be able to help the user in various ways, such as:

 - Writing code
 - Using the shell and Python REPL
 - Assisting with technical tasks
 - Writing prose (such as email, code docs, etc.)
 - Acting as an executive assistant

The agent should be able to learn from the user and adapt to their needs.
The agent should always output information using GitHub Flavored Markdown.
THe agent should always output code and commands in markdown code blocks with the appropriate language tag.

Since the agent is long-living, it should be able to remember things that the user has told it,
to do so, it needs to be able to store and query past conversations in a database.
"""
# The above may be used as a prompt for the agent.
import logging
import os
import readline  # noqa: F401
import sys
from datetime import datetime
from pathlib import Path
from typing import Generator, Literal

import click
from dotenv import load_dotenv
from pick import pick
from rich import print
from rich.console import Console

from .constants import HISTORY_FILE, LOGSDIR, PROMPT_USER
from .llm import init_llm, reply
from .logmanager import LogManager, print_log
from .message import Message
from .prompts import initial_prompt
from .tools import execute_msg, execute_python, execute_shell
from .tools.shell import get_shell
from .util import epoch_to_age, generate_unique_name

logger = logging.getLogger(__name__)


LLMChoice = Literal["openai", "llama"]
ModelChoice = Literal["gpt-3.5-turbo", "gpt4"]


Actions = Literal[
    "continue",
    "summarize",
    "log",
    "summarize",
    "context",
    "load",
    "shell",
    "python",
    "replay",
    "undo",
    "help",
    "exit",
]

action_descriptions: dict[Actions, str] = {
    "continue": "Continue",
    "undo": "Undo the last action",
    "log": "Show the conversation log",
    "summarize": "Summarize the conversation so far",
    "load": "Load a file",
    "shell": "Execute a shell command",
    "python": "Execute a Python command",
    "exit": "Exit the program",
    "help": "Show this help message",
    "replay": "Rerun all commands in the conversation (does not store output in log)",
}


def handle_cmd(
    cmd: str, logmanager: LogManager, no_confirm: bool
) -> Generator[Message, None, None]:
    """Handles a command."""
    cmd = cmd.lstrip(".")
    name, *args = cmd.split(" ")
    match name:
        case "bash" | "sh" | "shell":
            yield from execute_shell(" ".join(args), ask=not no_confirm)
        case "python" | "py":
            yield from execute_python(" ".join(args), ask=not no_confirm)
        case "continue":
            raise NotImplementedError
        case "log":
            logmanager.print(show_hidden="--hidden" in args)
        case "summarize":
            raise NotImplementedError
        case "context":
            # print context msg
            print(_gen_context_msg())
        case "undo":
            # if int, undo n messages
            n = int(args[0]) if args and args[0].isdigit() else 1
            logmanager.undo(n)
        case "load":
            filename = args[0] if args else input("Filename: ")
            with open(filename) as f:
                contents = f.read()
            yield Message("system", f"# filename: {filename}\n\n{contents}")
        case "exit":
            sys.exit(0)
        case "replay":
            print("Replaying conversation...")
            for msg in logmanager.log:
                if msg.role == "assistant":
                    for msg in execute_msg(msg):
                        print_log(msg, oneline=False)
        case _:
            print("Available commands:")
            for cmd, desc in action_descriptions.items():
                print(f"  {cmd}: {desc}")


script_path = Path(os.path.realpath(__file__))
action_readme = "\n".join(
    f"  .{cmd:10s}  {desc}." for cmd, desc in action_descriptions.items()
)


docstring = f"""
GPTMe, a chat-CLI for LLMs, enabling them to execute commands and code.

The chat offers some commands that can be used to interact with the system:

\b
{action_readme}"""


@click.command(help=docstring)
@click.argument("prompt", default=None, required=False)
@click.option(
    "--prompt-system",
    default="full",
    help="System prompt. Can be 'full', 'short', or something custom.",
)
@click.option(
    "--name",
    default="random",
    help="Name of conversation. Defaults to generating a random name. Pass 'ask' to be prompted for a name.",
)
@click.option(
    "--llm",
    default="openai",
    help="LLM to use.",
    type=click.Choice(["openai", "llama"]),
)
@click.option(
    "--model",
    default="gpt-4",
    help="Model to use (gpt-3.5 not recommended)",
    type=click.Choice(["gpt-4", "gpt-3.5-turbo", "wizardcoder-..."]),
)
@click.option(
    "--stream/--no-stream",
    is_flag=True,
    default=True,
    help="Stream responses",
)
@click.option("-v", "--verbose", is_flag=True, help="Verbose output.")
@click.option(
    "-y", "--no-confirm", is_flag=True, help="Skips all confirmation prompts."
)
@click.option(
    "--show-hidden",
    is_flag=True,
    help="Show hidden system messages.",
)
def main(
    prompt: str | None,
    prompt_system: str,
    name: str,
    llm: LLMChoice,
    model: ModelChoice,
    stream: bool,
    verbose: bool,
    no_confirm: bool,
    show_hidden: bool,
):
    # log init
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    # init
    logger.debug("Started")
    load_dotenv()
    _load_readline_history()
    init_llm(llm)  # set up API_KEY and API_BASE

    if no_confirm:
        print("WARNING: Skipping all confirmation prompts.")

    if prompt_system in ["full", "short"]:
        promptmsgs = initial_prompt(short=prompt_system == "short")
    else:
        promptmsgs = [Message("system", prompt_system)]

    logfile = get_logfile(name)
    print(f"Using logdir {logfile.parent}")
    logmanager = LogManager.load(
        logfile, initial_msgs=promptmsgs, show_hidden=show_hidden
    )
    logmanager.print()
    print("--- ^^^ past messages ^^^ ---")

    log = logmanager.log

    # if last message was from assistant, try to run tools again
    if log[-1].role == "assistant":
        for m in execute_msg(log[-1], ask=not no_confirm):
            logmanager.append(m)

    command_triggered = False

    while True:
        # if non-interactive command given on cli, exit
        if command_triggered:
            print("Command triggered, exiting")
            break

        # If last message was a response, ask for input.
        # If last message was from the user (such as from crash/edited log),
        # then skip asking for input and generate response
        last_msg = log[-1] if log else None
        if not last_msg or (
            (last_msg.role in ["system", "assistant"])
            or (log[-1].role == "user" and log[-1].content.startswith("."))
        ):
            inquiry = prompt_user(prompt)
            if prompt:
                command_triggered = True

            if not inquiry:
                # Empty command, ask for input again
                print()
                continue
            logmanager.append(Message("user", inquiry), quiet=True)

        assert log[-1].role == "user"
        inquiry = log[-1].content
        # if message starts with ., treat as command
        # when command has been run,
        if inquiry.startswith(".") or inquiry.startswith("$"):
            for msg in handle_cmd(inquiry, logmanager, no_confirm=no_confirm):
                logmanager.append(msg)
            if prompt:
                command_triggered = True
                print("Continue 2")
            continue

        # if large context, try to reduce/summarize
        # print response
        try:
            # performs reduction/context trimming
            msgs = logmanager.prepare_messages()

            # append temporary message with current context
            msgs += [_gen_context_msg()]

            # generate response
            msg_response = reply(msgs, model, stream)

            # log response and run tools
            if msg_response:
                logmanager.append(msg_response, quiet=True)
                for msg in execute_msg(msg_response, ask=not no_confirm):
                    logmanager.append(msg)
        except KeyboardInterrupt:
            print("Interrupted")


def get_name(name: str) -> Path:
    datestr = datetime.now().strftime("%Y-%m-%d")

    # returns a name for the new conversation
    if name == "random":
        # check if name exists, if so, generate another one
        for _ in range(3):
            name = generate_unique_name()
            logpath = LOGSDIR / f"{datestr}-{name}"
            if not logpath.exists():
                break
        else:
            raise ValueError("Failed to generate unique name")
    elif name == "ask":
        while True:
            # ask for name, or use random name
            name = input("Name for conversation (or empty for random words): ")
            name = f"{datestr}-{name}"
            logpath = LOGSDIR / name

            # check that name is unique/doesn't exist
            if not logpath.exists():
                break
            else:
                print(f"Name {name} already exists, try again.")
    else:
        # if name starts with date, use as is
        try:
            datetime.strptime(name[:10], "%Y-%m-%d")
        except ValueError:
            name = f"{datestr}-{name}"
        logpath = LOGSDIR / name
    return logpath


def _gen_context_msg() -> Message:
    shell = get_shell()
    msgstr = ""

    cmd = "pwd"
    ret, pwd, _ = shell.run_command(cmd)
    assert ret == 0
    msgstr += f"$ {cmd}\n{pwd.strip()}\n"

    cmd = "git status -s"
    ret, git, _ = shell.run_command(cmd)
    if ret == 0 and git:
        msgstr += f"$ {cmd}\n{git}\n"

    return Message("system", msgstr.strip(), hide=True)


# default history if none found
history_examples = [
    "What is love?",
    "Have you heard about an open-source app called ActivityWatch?",
    "Explain 'Attention is All You Need' in the style of Andrej Karpathy.",
    "Explain how public-key cryptography works as if I'm five.",
    "Write a Python script that prints the first 100 prime numbers.",
    "Find all TODOs in the current git project",
]


def _load_readline_history() -> None:
    logger.debug("Loading history")
    try:
        readline.read_history_file(HISTORY_FILE)
    except FileNotFoundError:
        for line in history_examples:
            readline.add_history(line)


def get_logfile(name: str) -> Path:
    # let user select between starting a new conversation and loading a previous one
    # using the library
    title = "New conversation or load previous? "
    NEW_CONV = "New conversation"
    prev_conv_files = sorted(
        list(LOGSDIR.glob("*/*.jsonl")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    NEWLINE = "\n"
    prev_convs = [
        f"{f.parent.name:30s} \t{epoch_to_age(f.stat().st_mtime)} \t{len(f.read_text().split(NEWLINE)):5d} msgs"
        for f in prev_conv_files
    ]

    # don't run pick in tests/non-interactive mode
    if sys.stdout.isatty():
        print("is a tty")
        options = [
            NEW_CONV,
        ] + prev_convs
        option, index = pick(options, title)
        if index == 0:
            logdir = get_name(name)
        else:
            logdir = LOGSDIR / prev_conv_files[index - 1].parent
    else:
        print("is NOT a tty")
        logdir = get_name(name)

    if not os.path.exists(logdir):
        os.mkdir(logdir)
    logfile = logdir / "conversation.jsonl"
    if not os.path.exists(logfile):
        open(logfile, "w").close()
    return logfile


def prompt_user(value=None) -> str:
    response = prompt_input(PROMPT_USER, value)
    if response:
        readline.add_history(response)
        readline.write_history_file(HISTORY_FILE)
    return response


def prompt_input(prompt: str, value=None) -> str:
    prompt = prompt.strip() + ": "
    if value:
        print(prompt + value)
    else:
        console = Console()
        value = console.input(prompt)
    return value


if __name__ == "__main__":
    main()
