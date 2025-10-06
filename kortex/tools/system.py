import os
import json
import webbrowser
import subprocess
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import screen_brightness_control as sbc

APP_ALIASES = {
    "calculator": "calc.exe",
    "notepad": "notepad.exe",
    "file explorer": "explorer.exe",
}

def find_application(app_query, apps_cache):
    """
    Finds application names from a cached list that match a query, checking aliases first.
    Parameters: {"app_query": "The name of the application to find, e.g., 'calculator' or 'photoshop'."}
    """
    app_query = app_query.lower()
    matches = set()

    for name in apps_cache:
        name_lower = name.lower()
        if app_query in name_lower:
            matches.add(name)
        elif name_lower in app_query:
            matches.add(name)
            
    return list(matches)

def open_application_internal(app_path_or_alias):
    """Internal function to open an application given its full path or an alias."""
    try:
        if app_path_or_alias in APP_ALIASES:
            exe_name = APP_ALIASES[app_path_or_alias]
            subprocess.Popen(exe_name, shell=True)
            return f"Opening {app_path_or_alias.title()}."

        app_path = app_path_or_alias
        if app_path.endswith(('.lnk', '.url')):
            os.startfile(app_path)
        else:
            subprocess.Popen([app_path])
        return f"Opening {os.path.basename(app_path).split('.')[0]}."
    except Exception as e:
        return f"Sorry, I couldn't open that application. Error: {e}"

def scan_applications():
    """Scans for applications in Start Menu and Program Files."""
    apps = {}
    
    for alias in APP_ALIASES:
        apps[alias] = alias

    start_menu_paths = [
        os.path.join(os.environ['APPDATA'], 'Microsoft\\Windows\\Start Menu\\Programs'),
        os.path.join(os.environ['ALLUSERSPROFILE'], 'Microsoft\\Windows\\Start Menu\\Programs')
    ]
    prog_files_paths = [os.environ.get('ProgramFiles'), os.environ.get('ProgramFiles(x86)')]

    for path in start_menu_paths:
        for root, _, files in os.walk(path):
            for file in files:
                if file.endswith(('.lnk', '.url')):
                    name = os.path.splitext(file)[0]
                    if name not in apps: apps[name] = os.path.join(root, file)

    for path in prog_files_paths:
        if path:
            for root, dirs, _ in os.walk(path, topdown=True):
                if root.count(os.sep) > path.count(os.sep) + 1: dirs[:] = []; continue
                for d in dirs:
                    if d.lower() not in ['common files', 'windows defender', 'installshield installation information']:
                        exe_path = os.path.join(root, d, f"{d}.exe")
                        if os.path.exists(exe_path) and d not in apps: apps[d] = exe_path
    return apps

def create_folder(folder_name):
    """
    Creates a new folder on the user's desktop.
    Parameters: {"folder_name": "The name for the new folder."}
    """
    desktop_path = os.path.join(os.path.join(os.environ['USERPROFILE']), 'Desktop')
    path_to_create = os.path.join(desktop_path, folder_name)
    try:
        os.makedirs(path_to_create)
        return f"Folder '{folder_name}' created on your desktop."
    except FileExistsError:
        return f"A folder named '{folder_name}' already exists on your desktop."
    except Exception as e:
        return f"Error creating folder: {e}"

def open_website(url):
    """
    Opens a given URL in the default web browser.
    Parameters: {"url": "The full URL of the website to open, e.g., 'https://www.google.com'."}
    """
    try:
        # Prepend https:// if the url doesn't have a scheme
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        webbrowser.open(url)
        return f"Opening {url}."
    except Exception as e:
        return f"Sorry, I couldn't open that URL. Error: {e}"

def set_system_volume(level):
    """
    Sets the system master volume to a specific percentage.
    Parameters: {"level": "A number between 0 and 100 for the desired volume level."}
    """
    try:
        level = int(level)
        if not 0 <= level <= 100:
            return "Volume level must be between 0 and 100."
            
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        
        scalar_volume = level / 100.0
        volume.SetMasterVolumeLevelScalar(scalar_volume, None)
        return f"System volume set to {level}%."
    except Exception as e:
        return f"Failed to set volume. Error: {e}"

def set_screen_brightness(level):
    """
    Sets the screen brightness to a specific percentage.
    Parameters: {"level": "A number between 0 and 100 for the desired brightness level."}
    """
    try:
        level = int(level)
        if not 0 <= level <= 100:
            return "Brightness level must be between 0 and 100."
        
        sbc.set_brightness(level)
        return f"Screen brightness set to {level}%."
    except sbc.ScreenBrightnessError as e:
        return f"Failed to set brightness. This may not be supported on your display. Error: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"