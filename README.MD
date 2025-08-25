# SimplePyWM

A simple Python Window Manager

## Installing Dependencies
Arch-based
```
sudo pacman -S xorg-server xorg-xinit python kitty dmenu lf
```
Debian-based
```
sudo apt install xserver-xorg xinit python3 kitty dmenu lf
```
## Installing python packages
```
pip install python-xlib

## For Arch its managed by pacman itself
pacman -S python-xlib
```
## Setup
- Clone the repository into a {directory}
- ```echo "exec python3 {directory}/main.py" > ~/.xinitrc```
- Run ```startx```

## Usage
### Configuration
- Edit ```config.json``` in location ```~/.config/simplepywm/config.json```
- Config is created after running the WM initially

### Shortcuts
- Ctrl + Shift + T  --> Terminal
- Ctrl + Arrow Keys --> Snap Active window
- Ctrl + Space      --> Dmenu Launcher
- Ctrl + E          --> Open File manager
- Windows + Q          --> Close Window Manager
- Alt  + Tab        --> Switch to next window
- Shift + Alt + Tab --> Switch to previous window

## Features
- Window Snapping
- Window Dragging and Resizing
- Window Minimizing, Maximizing, Closing
- Taskbar
- Alt-Tabbing windows

## WIP
- Widgets for Battery, Wifi, Sound
- Workspaces

## Fresh Install Caveats

### Font
Install font
```
sudo pacman -S ttf-roboto
```
Reboot after installation

### Audio

Install pulseaudio
```
sudo pacman -S pulseaudio
```
Start pulseaudio with window manager in .xinitrc
```
exec pulseaudio --start & python3 {directory}/main.py
```
Reboot after installation

### Mouse
Install xorg-xinput
```
sudo pacman -S xorg-xinput
```
Find ID of your mouse
```
xinput --list
```
Remove Acceleration in .xinitrc
```
xinput set-prop {id} "libinput Accel Profile Enabled" 0, 1
xinput set-prop {id} "libinput Accel Speed" 0
```

### Touchpad

Enable tap to click in .xinitrc
```
xinput set-prop {id} "libinput Tapping Enabled" 1
```
Enable natural scrolling in .xinitrc
```
xinput set-prop {id} "libinput Natural Scrolling Enabled" 1
```