__xatk__ is a keyboard-driven window switcher for X11. It dynamically
binds windows to keyboard shortcuts, so it is possible to reach any
window with one or a few keystrokes.

# Installation

xatk is a single python file program that you can put in any directory
defined in the PATH environment variable. To run xatk you should have
[python 2 (>= 2.7)](http://www.python.org) and
[python-xlib](http://python-xlib.sourceforge.net/) installed.

# Running

Before running xatk you may want to change some configuration options.
First, create the default configuration file:

    mkdir -p ~/.xatk
    xatk --print-defaults > ~/.xatk/xatkrc

Then open `~/.xatk/xatkrc` and make changes. The most interesting
option is `prefix`, which is set to Super (Windows) by default. This
means that all keyboard shortcuts will start with Super modifier. You
can define any modifier you like, or even combination of modifiers and
keys. Most other options are for fine-tuning and it is not necessary
to learn them all. Look at the comment blocks in the default
configuration file if you want to learn more.

When you get ready with configuration, you can start xatk by running
it with no arguments:

    xatk

If no error occurr you will notice that window titles contain
shortcuts they are bound to. To activate a window you can press
`prefix+shortcut`.

If you want to exit the program run:

    xatk --kill

It's the same as kill xatk with SIGTERM. It's safe.

# Autostart

If you use GDM or KDM, you can add `xatk` to `~/.xprofile`. If you use
`startx` or `xinit` you can add `xatk` to `~/.xinitirc` before line
`exec window-manager`. Also GNOME, KDE and Xfce have dedicated GUI
tools to add programs to startup.

# Documentation

For more information look at [Read the Docs pages](http://xatk.readthedocs.org/en/latest/):

 * [FAQ](FAQ.md)
 * [Troubleshooting](Troubleshooting.md)
 * [How it works](HowItWorks.md)
 * [Roadmap](Roadmap.md).
