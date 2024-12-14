import platform
import subprocess

from . import get_installed_programs

copytext = ""
pastetext = ""


def set_copytext(new_text: str):
    global copytext
    copytext = new_text

def set_pastetext(new_text: str):
    global pastetext
    pastetext = new_text


def copy() -> bool:
    """return True if successful"""

    global copytext
    if platform.system() == "Linux":
        # check if xclip or wl-clipboard is installed
        installed = get_installed_programs(("xclip", "wl-copy"))
        if "wl-copy" in installed:
            output = subprocess.run(["wl-copy"], input=copytext, text=True, check=True)
            if output.returncode != 0:
                print("wl-copy failed to copy to clipboard.")
                return False
            return True
        elif "xclip" in installed:
            output = subprocess.run(
                ["xclip", "-selection", "clipboard"], input=copytext, text=True
            )
            if output.returncode != 0:
                print("xclip failed to copy to clipboard.")
                return False
            return True
        else:
            print("No clipboard utility found. Please install xclip or wl-clipboard.")
            return False
    elif platform.system() == "Darwin":
        output = subprocess.run(["pbcopy"], input=copytext, text=True)
        if output.returncode != 0:
            print("pbcopy failed to copy to clipboard.")
            return False
        return True

    return False

def paste() -> bool:
    """return True if successful"""

    global pastetext
    if platform.system() == "Linux":
        # check if xclip or wl-clipboard is installed
        installed = get_installed_programs(("xclip", "wl-paste"))
        if "wl-paste" in installed:
            output = subprocess.run(["wl-paste"], text=True, capture_output=True)
            if output.returncode != 0:
                print("wl-paste failed to paste from clipboard.")
                return False
            pastetext = output.stdout
            return True
        elif "xclip" in installed:
            output = subprocess.run(["xclip", "-selection", "clipboard", "-o"], text=True, capture_output=True)
            if output.returncode != 0:
                print("xclip failed to paste from clipboard.")
                return False
            pastetext = output.stdout
            return True
        else:
            print("No clipboard utility found. Please install xclip or wl-clipboard.")
            return False
    elif platform.system() == "Darwin":
        output = subprocess.run(["pbpaste"], text=True, capture_output=True)
        if output.returncode != 0:
            print("pbpaste failed to paste from clipboard.")
            return False
        pastetext = output.stdout
        return True

    return False
