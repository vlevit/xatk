**xatk** dynamically binds windows to keyboard shortcuts, so it is
possible to reach any window with one or a few keystrokes.

## Installation ##

xatk is a single python file program which doesn't require installation. Just
put it in any directory defined in the PATH environment variable. To run xatk
you should have [python 2 (>= 2.6)](http://www.python.org) and
[python-xlib](http://python-xlib.sourceforge.net/) installed.

## Running ##

Before running xatk you may want to change some configuration options. To do
so, first create the default configuration file:

```
mkdir -p ~/.xatk
xatk --print-defaults > ~/.xatk/xatkrc
```

Then open `~/.xatk/xatkrc` and make changes. The most interesting option is
prefix, which is set to Super by default. This means that all keyboard shortcuts
will start with Super modifier. You can define any modifier you like, or even
combination of modifiers and keys. Most other options are for fine-tuning and it
is not necessary to learn them all just to benefit from use of xatk. Look at the
comment blocks in the default configuration file if you want to learn more.

When you get ready with configuration, you can start xatk daemon with the following
command:

```
xatk
```

If no error occurred, you can notice that window titles now contain shortcuts
which they are bound to. To activate a window you should press prefix+shortcut.

If you want to exit the program, send SIGTERM to it:

```
pkill -f xatk      # this may kill other programs which have xatk in the command line, be careful!
```

## Autostart ##

Automatic start of xatk can be accomplished in different ways. If you use GDM or
KDM, you can add `xatk` to `~/.xprofile`. If you use `startx` or `xinit` you can
add `xatk` to `~/.xinitirc` before line `exec window-manager`. Also GNOME, KDE
and Xfce have dedicated GUI tools to add programs to startup.

See also [FAQ](FAQ.md), [Troubleshooting](Troubleshooting.md), [ForTheCurious](ForTheCurious.md), [Roadmap](Roadmap.md).