### xatk doesn't start or doesn't work ###

Run xatk in the terminal and look at the output. Probably it is something wrong
with your configuration. If there is no complains, and you
have still no idea what is going on, run xatk in foreground:

`xatk --no-daemon -vv`

If it is still not clear, where the problem is, please create
[a bug report](http://code.google.com/p/xatk/issues/entry).

### I have Python 2 installed but xatk doesn't start ###

If your shell prints something similar to

`/usr/bin/env: python2: No such file or directory`

then probably your OS distribution doesn't provide python2 symlink. The real fix
`[1]` is to convince maintainers of your distribution to provide python2 symlink.
The temporary fix is obvious: you can either edit xatk file replacing python2 with
your real python 2 executable name, or you can specify xatk path as command line
argument to python 2 interpreter.

`[1]` [PEP 394](http://www.python.org/dev/peps/pep-0394/)

### Running two instances of xatk ###

There is no reason to run two instances of xatk, but it can be done
by accident. xatk for its part does nothing to prevent this. This is subject to
change in xatk 0.2.