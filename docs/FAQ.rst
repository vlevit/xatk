Frequently Asked Questions
==========================

Is xatk compatible with my window manager?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

xatk uses some hints specified in
`EWMH <http://standards.freedesktop.org/wm-spec/wm-spec-latest.html>`__.
So xatk should work fine with window managers that support such hints.
Metacity/Mutter, KWin, Compiz, Openbox, Awesome have been reported to
work with xatk. Share your experience with us via `issue tracking
system <https://github.com/vlevit/xatk/issues>`__.

Customization
-------------

All customizations are done by modifying xatk's configuration file
``~/.xatk/xatkrc``. Before making any changes ensure that xatk is not
running.

How to assign keybindings to the certain windows permanently?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Create a rule and prefix awn with !. For example,

::

    class.emacs = !e

How to forbid xatk to assign keybindings to the certain windows?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Crate a rule and specify empty awn. For example,

::

    class.emacs =

How to make xatk ignore all windows except a few ones?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Specify rules for windows which should not be ignored and the following
rule at the end of RULES:

::

    class..* =

How to forbid xatk to modify all window titles?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set title\_format to None.

How to disable multi-key shortcuts?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Change group\_windows\_by option value to None.

Shortcuts for my windows change all the time.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Try to increase the value of history\_length option or specify premanent
keys for some windows.

How to make two windows belong to the same group?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Windows belong to the same group if they have identical awn attributes.
You can specify identical awns for those windows in the RULES section.

I want shortcuts to be in certain order (e.g. q,w,e,r...) without considering programs they belong to.
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can set history\_length to 0, group\_windows\_by to None and define
the rule like this:

::

    title..*=qwertyuiopasdfghjklzxcvbnm

Miscellaneous
-------------

How can I get a window class or instance?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With xatk
^^^^^^^^^

First stop xatk if it is running. Run xatk with the following options:

::

    xatk --no-daemon --filter=windows --verbose

You will see information messages starting with
``new window attributes``. These lines contain klass, instance and name
attributes. They correspond to window class, instance and title
respectively.

With xprop
^^^^^^^^^^

Run ``'xprop WM_CLASS'`` and select a window. The first string after '='
is a window instance and the second one is a window class.

With wmctrl
^^^^^^^^^^^

``wmctrl -xl`` prints a window list on the standard output. The second
column is in ``instance.class`` format.

Contributing
------------

How can I help the project?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Report bugs and request features via `issue tracking
system <https://github.com/vlevit/xatk/issues>`__.

Make a screencast.

Spread the word. Write about xatk on your site or blog.

Help with code, see `Roadmap <Roadmap.md>`__. A preliminary discussion
with developers is encouraged.
