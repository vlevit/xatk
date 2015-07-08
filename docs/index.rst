Welcome to xatk's documentation
================================

.. toctree::
   :maxdepth: 2

   index


xatk__ is a keyboard-driven window switcher for X11. It dynamically
binds windows to keyboard shortcuts, so it is possible to reach any
window with one or a few keystrokes.

__ https://github.com/vlevit/xatk

Installation
~~~~~~~~~~~~

xatk is a `single python file`__ program that you can put in any
directory defined in the PATH environment variable. To run xatk you
should have `python 2 (>= 2.7)`__ and `python-xlib`__ installed.

__ https://raw.githubusercontent.com/vlevit/xatk/master/xatk
__ http://www.python.org
__ http://python-xlib.sourceforge.net/

Running
~~~~~~~

Before running xatk you may want to change some configuration options.
First, create the default configuration file:

.. code:: bash

    $ mkdir -p ~/.xatk
    $ xatk --print-defaults > ~/.xatk/xatkrc

Then open ``~/.xatk/xatkrc`` and make changes. The most interesting
option is ``prefix`` which is set to Super (Windows) by default. This
means that all keyboard shortcuts will start with Super modifier. You
can define any modifier you like or even combination of modifiers and
keys. Look at the comment blocks in the default configuration file for
more customization options.

When you get ready with configuration, you can start xatk by running it
with no arguments:

.. code:: bash

    $ xatk

If no error occurr you will be able to notice shortcuts in window
titles. To activate a specific window press ``prefix + shortcut``.

If you want to exit the program run:

.. code:: bash

    $ xatk --kill

It's the same as kill xatk with SIGTERM. It's safe.

Autostart
~~~~~~~~~

If you use GDM or KDM, you can add ``xatk`` to ``~/.xprofile``. If you
use ``startx`` or ``xinit`` you can add ``xatk`` to ``~/.xinitirc``
before line ``exec window-manager``. Also GNOME, KDE and Xfce have
dedicated GUI tools to add programs to startup.

More Info
~~~~~~~~~

For more information on configuration options look at the comment
blocks in `~/.xatk/xatkrc`. For other information look at the links
below.

.. toctree::
   :maxdepth: 2

   HowItWorks
   FAQ
   Troubleshooting
   Roadmap
