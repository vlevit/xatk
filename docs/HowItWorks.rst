How it works
============

Motivation
----------

Most of window switchers are interactive. They provide attributes
associated with windows (e.g. titles, icons, previews) which we scan
first and than choose one of them. That works well enough when we deal
with a set of applications for the first time. However, we regularly
use the same applications. So, in most cases our wish to switch a
window can be expressed like "Show me <my favourite text editor>". One
possible solution to switch between windows efficiently is to bind
regularly used windows to keyboard shortcuts with such tools as
`wmctrl <http://tomas.styblo.name/wmctrl/>`__ and `xbindkeys
<http://www.nongnu.org/xbindkeys/xbindkeys.html>`__. However, this
approach has a few drawbacks:

-  switching to the particular window of the program which has more than
   one window is hard if not impossible;
-  only limited number of windows are covered;
-  manual composition of keyboard shortcuts which becomes even more
   boring when you stop using one program and start using another one;
-  it is not easy to keep in mind all defined keyboard shortcuts.

xatk was created to resolve these issues.

How it works
------------

When a new window appears xatk determines its special name called
abstract window name (awn). This name is used for 2 purposes:

-  windows which have the same awn fall into one group;
-  characters of awn are preferable keys to compose a shortcut from for
   the corresponding window.

By default, window class property is assigned to awn. However, user may
define own rules based on window class and window name (title) to form
awns.

When awn of the window is determined, xatk looks it up in the history,
holding awn — shortcut pairs. If the history contains the appropriate
entry, xatk will bind the window to the previously used shortcut.
Otherwise the shortcut is generated from the awn. This technique results
in next xatk's features:

-  new shortcuts are usually not hard to remember as they are derived
   from the application names (more precisely, from the awns);
-  regularly used windows have the same shortcuts all the time;
-  shortcuts of applications that are not used anymore for some time get
   freed.

Windows which belong to the same group have the same base key which is
the first key of the shortcut.

Keybindings
-----------

xatk tries to compose keybindings which would be easy to press and
predict. If a window is alone in the group, then to activate it you have
to press a one-key shortcut while holding a prefix key. If the group
contains more than one window, than a keybinding of the first window
will remain the same (but window activation will be triggered by key
release instead of key press). Other windows of the group will have
keybindings with prefix+base key+suffix key scheme. Such notation means
that you should press base key while holding prefix key and then press
suffix key while holding base key. xatk takes into consideration the
keyboard layout when it produces suffix keys. So, a distance between
base key and suffix key is one, two, and three keys for the second,
third, and fourth window of the group respectively. Another way to reach
deeper windows of the group is cycling through them by pressing a base
key repeatedly.

Finally, if you don't like pressing key sequences, you can configure
xatk not to group windows.
