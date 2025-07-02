# SimplePyWM

A simple Python Window Manager

## Installing Dependencies
Arch-based
```
sudo pacman -S xorg-server xorg-xinit python xterm dmenu lf
```
Debian-based
```
sudo apt install xserver-xorg xinit python3 dmenu xterm lf
```
## Installing python packages
```
pip install python-xlib
```
## Setup
- Clone the repository into a {directory}
- ```echo "exec python3 {directory}/main.py" > ~/.xinitrc```
- Run ```startx```

# Usage
## Configuration
- Edit ```config.json``` in location ```~/.config/simplepywm/config.json```
- Config is created after running the WM initially

## Shortcuts
- Ctrl + Shift + T  --> Terminal
- Ctrl + Arrow Keys --> Snap Active window
- Ctrl + Space      --> Dmenu Launcher
- Ctrl + E          --> Open File manager
- Ctrl + Q          --> Close Window Manager

# Features
- Window Snapping
- Window Dragging and Resizing
- Window Minimizing, Maximizing, Closing
- Taskbar

# WIP
- Widgets for Battery, Wifi, Sound
- Alt-Tab Switching active window