import os
import time
import threading
import pygame
import dearpygui.dearpygui as dpg

from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

# -----------------------------------------------------------------------------
# Audio control helpers
# -----------------------------------------------------------------------------

def mute_microphone(mute):
    devices = AudioUtilities.GetMicrophone()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))
    volume.SetMute(1 if mute else 0, None)

def set_app_volume(app_name, volume):
    sessions = AudioUtilities.GetAllSessions()
    found = False
    for session in sessions:
        if session.Process and session.Process.name().lower() == app_name.lower():
            vol_ctrl = session._ctl.QueryInterface(ISimpleAudioVolume)
            vol_ctrl.SetMasterVolume(volume, None)
            found = True
            break
    if not found:
        print(f"Warning: process '{app_name}' not found")

def get_app_volume(app_name):
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name().lower() == app_name.lower():
            vol_ctrl = session._ctl.QueryInterface(ISimpleAudioVolume)
            return vol_ctrl.GetMasterVolume()
    return 0.5  # default if not found

def list_active_audio_processes():
    sessions = AudioUtilities.GetAllSessions()
    return {s.Process.name().lower() for s in sessions if s.Process}

# -----------------------------------------------------------------------------
# Load sound mappings
# -----------------------------------------------------------------------------

button_map = {}
mute_map = {}
action_map = {}
volume_map = {}

active_audio_processes = list_active_audio_processes()

with open('soundmap.txt', 'r') as f:
    for line in f:
        if line.startswith('#') or not line.strip():
            continue
        key, name, mute, action, comment = line.strip().split(',')
        key = int(key.strip())
        name = name.strip()
        mute_map[key] = eval(mute.strip())  # True/False

        # Parse action correctly
        action_str = action.strip()
        if action_str.lower() in ("false", "0"):
            action_map[key] = 0.0  # play sound
        else:
            action_map[key] = float(action_str)  # volume adjustment

        button_map[key] = name
        volume_map[name] = get_app_volume(name)

        # Only warn if this is a volume control entry
        if action_map[key] != 0 and name.lower() not in active_audio_processes:
            print(f"Warning: mapped app '{name}' not currently running")

# -----------------------------------------------------------------------------
# Pygame setup
# -----------------------------------------------------------------------------

pygame.init()
pygame.joystick.init()
pygame.mixer.init()

joystick = None
for i in range(pygame.joystick.get_count()):
    j = pygame.joystick.Joystick(i)
    j.init()
    if j.get_name() == "SimHub Controller Remapper Bridge":
        joystick = j
        break

# -----------------------------------------------------------------------------
# Sound playback
# -----------------------------------------------------------------------------

os.chdir("Sounds")

def play_sound(button):
    """Play the file mapped to the button if action == 0, else adjust volume"""
    name = button_map[button]
    mute_flag = mute_map[button]
    action = action_map[button]

    if action != 0:
        # Volume adjustment
        current_vol = volume_map[name]
        current_vol += action
        current_vol = max(0.0, min(1.0, current_vol))
        volume_map[name] = current_vol
        set_app_volume(name, current_vol)
        dpg.set_value("status_text", f"{name} volume set to {int(current_vol*100)}%")
    else:
        # Play sound file
        mp3_file = name
        if not os.path.exists(mp3_file):
            dpg.set_value("status_text", f"File not found: {mp3_file}")
            return
        if mute_flag:
            mute_microphone(True)
        pygame.mixer.music.load(mp3_file)
        pygame.mixer.music.play()
        dpg.set_value("status_text", f"Playing: {mp3_file}")
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        if mute_flag:
            mute_microphone(False)
        dpg.set_value("status_text", f"Finished: {mp3_file}")

# -----------------------------------------------------------------------------
# GUI setup
# -----------------------------------------------------------------------------

dpg.create_context()
dpg.create_viewport(title="Audio Button Controller", width=500, height=625, resizable=True)

slider_tag_map = {}  # maps slider tags to app names

with dpg.window(label="Sound Controller", width=-1, height=-1, tag="main_window"):
    dpg.add_text("Joystick: " + (joystick.get_name() if joystick else "Not Found"))
    dpg.add_separator()
    dpg.add_text("Status:")
    dpg.add_text("Waiting for input...", tag="status_text")
    dpg.add_separator()

    for button, name in button_map.items():
        with dpg.group(horizontal=True):
            dpg.add_text(f"Button {button}: {name}")
            if action_map[button] != 0:
                # Volume adjustment slider
                slider_tag = f"slider_{button}"
                dpg.add_slider_float(
                    label="",  # hide the default label to avoid stray characters
                    min_value=0.0,
                    max_value=1.0,
                    default_value=volume_map[name],
                    width=-1,
                    tag=slider_tag,
                    format="%.2f",
                    callback=lambda s, a, u=name: set_app_volume(u, dpg.get_value(s))
                )
                slider_tag_map[slider_tag] = name
            # Mute checkbox
            dpg.add_checkbox(
                label="Mute Mic",
                default_value=mute_map[button],
                callback=lambda s, a, u=button: mute_microphone(dpg.get_value(u))
            )
            # Play button triggers play_sound
            dpg.add_button(
                label="Play",
                callback=lambda s, a, u=button: threading.Thread(target=play_sound, args=(u,), daemon=True).start()
            )

    dpg.add_separator()
    dpg.add_button(label="Exit", callback=lambda: dpg.stop_dearpygui())

dpg.set_primary_window("main_window", True)

# -----------------------------------------------------------------------------
# Joystick monitoring thread
# -----------------------------------------------------------------------------

def joystick_thread():
    while True:
        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                dpg.set_value("status_text", f"Button {event.button + 1} pressed")
                if (event.button + 1) in button_map:
                    threading.Thread(target=play_sound, args=(event.button + 1,), daemon=True).start()
            elif event.type == pygame.JOYBUTTONUP:
                dpg.set_value("status_text", f"Button {event.button + 1} released")
        time.sleep(0.05)

threading.Thread(target=joystick_thread, daemon=True).start()

# -----------------------------------------------------------------------------
# Background thread for live slider updates
# -----------------------------------------------------------------------------

def live_slider_update():
    while True:
        for slider_tag, app_name in slider_tag_map.items():
            current_vol = get_app_volume(app_name)
            if abs(current_vol - dpg.get_value(slider_tag)) > 0.001:
                dpg.set_value(slider_tag, current_vol)
                volume_map[app_name] = current_vol
        time.sleep(0.2)

threading.Thread(target=live_slider_update, daemon=True).start()

# -----------------------------------------------------------------------------
# Run GUI
# -----------------------------------------------------------------------------

dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()