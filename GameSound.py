# uncomment to build .exe
import pyautogui
import sys
import pygame
import time

from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, ISimpleAudioVolume

debug = False

def mute_microphone(mute):
    # Get the default audio endpoint for the microphone
    devices = AudioUtilities.GetMicrophone()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    volume = cast(interface, POINTER(IAudioEndpointVolume))

    if mute:    # mute the microphone
        volume.SetMute(1, None)         # 1 to mute, 0 to unmute
    else:
        volume.SetMute(0, None)         # 1 to mute, 0 to unmute

def set_app_volume(app_name, volume):
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        if session.Process and session.Process.name().lower() == app_name.lower():
            volume_control = session._ctl.QueryInterface(ISimpleAudioVolume)
            volume_control.SetMasterVolume(volume, None)  # Volume: 0.0 to 1.0
            if debug == True:
                print(f"Set {app_name} volume to {volume*100}%")

def get_app_volume(app_name):
    sessions = AudioUtilities.GetAllSessions()
    for session in sessions:
        volume = session._ctl.QueryInterface(ISimpleAudioVolume)
        if session.Process and session.Process.name().lower() == app_name.lower():
            return volume.GetMasterVolume()  # Returns volume as float (0.0 to 1.0)
    return None

if len(sys.argv) > 1:
    if sys.argv[1] == "-d":
        debug = True

# Initialize the pygame library
pygame.init()

# Set up the simhub remapper bridge game controller
joysticks = []
for i in range(pygame.joystick.get_count()):
    joysticks.append(pygame.joystick.Joystick(i))
    joysticks[-1].init()

for joystick in joysticks:
    #if debug == True:
        if joystick.get_name() == "SimHub Controller Remapper Bridge":
            print("Found simhub remapper")  # found the remapper bridge
            break

# Set up the MP3 player
import os
import subprocess

button_map = {}
mute_map = {}
action_map = {}
volume_map = {}

# get button / sound file mapping / current volumes
with open('soundmap.txt', 'r') as file:
    for line in file:
        if line.startswith('#'):
            continue            # skip comments
        # strip whitespace and split line into key and value
        key, name, mute, action, comment = line.strip().split(',')
        name = name.strip()
        mute = mute.strip()
        action = action .strip()
        if debug == True:
            print(key, name, mute, action)
        button_map[int(key)] = name
        mute_map[int(key)] = eval(mute)
        action_map[int(key)] = eval(action)
#        volume_map[int(key)] = get_app_volume(button_map[int(key)])
        volume_map[name.strip()] = get_app_volume(button_map[int(key)])
        if debug == True:
            print("Current volume ", button_map[int(key)], " is ", volume_map[name])

if debug == True:
    print("Current directory:", os.getcwd())

os.chdir("Sounds")

# test setting volume
#set_app_volume("discord.exe", 1.0)

# Main loop
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.JOYBUTTONDOWN:
            buttons = joystick.get_numbuttons()
            for i in range(buttons):
                if joystick.get_button(i):
                    button = i + 1
                    if debug == True:
                        print(button, " pressed")
                    if button in button_map:
                        if action_map[button]:          # change volume command
                            # increase/decrease volume
                            volume_map[button_map[button]] = volume_map[button_map[button]] + action_map[button]
                            if volume_map[button_map[button]] > 1.0:
                                volume_map[button_map[button]] = 1.0
                            elif volume_map[button_map[button]] < 0:
                                volume_map[button_map[button]] = 0
                            set_app_volume(button_map[button], volume_map[button_map[button]])
                        else:
                            mp3_file = button_map[button]
                            mute_flag = mute_map[button]
                            pygame.mixer.music.load(mp3_file)
                            if mute_flag:
                                mute_microphone(True)
                            pygame.mixer.music.play()
                            # Wait for the music to finish playing
                            while pygame.mixer.music.get_busy():  # Check if music is still playing
                                time.sleep(0.2)  # Sleep for a short time to avoid busy waiting
                            if mute_flag:
                                mute_microphone(False)
        elif event.type == pygame.JOYBUTTONUP:
            buttons = joystick.get_numbuttons()
            for i in range(buttons):
                if joystick.get_button(i):
                    button = i + 1
                    if debug == True:
                        print(button, " released")
                    