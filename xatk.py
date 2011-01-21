#!/usr/bin/env python

import sys
import os.path
import re
import ConfigParser
from ConfigParser import RawConfigParser
from Xlib import display, error, protocol, X, Xatom, XK
from UserDict import DictMixin

class OrderedDict(dict, DictMixin):
    """OrderedDict implementaion equivalent to Python2.7's OrderedDict by
    Raymond Hettinger. http://code.activestate.com/recipes/576693/"""

    def __init__(self, *args, **kwds):
        if len(args) > 1:
            raise TypeError('expected at most 1 arguments, got %d' % len(args))
        try:
            self.__end
        except AttributeError:
            self.clear()
        self.update(*args, **kwds)

    def clear(self):
        self.__end = end = []
        end += [None, end, end]         # sentinel node for doubly linked list
        self.__map = {}                 # key --> [key, prev, next]
        dict.clear(self)

    def __setitem__(self, key, value):
        if key not in self:
            end = self.__end
            curr = end[1]
            curr[2] = end[1] = self.__map[key] = [key, curr, end]
        dict.__setitem__(self, key, value)

    def __delitem__(self, key):
        dict.__delitem__(self, key)
        key, prev, next = self.__map.pop(key)
        prev[2] = next
        next[1] = prev

    def __iter__(self):
        end = self.__end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.__end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def popitem(self, last=True):
        if not self:
            raise KeyError('dictionary is empty')
        if last:
            key = reversed(self).next()
        else:
            key = iter(self).next()
        value = self.pop(key)
        return key, value

    def __reduce__(self):
        items = [[k, self[k]] for k in self]
        tmp = self.__map, self.__end
        del self.__map, self.__end
        inst_dict = vars(self).copy()
        self.__map, self.__end = tmp
        if inst_dict:
            return (self.__class__, (items,), inst_dict)
        return self.__class__, (items,)

    def keys(self):
        return list(self)

    setdefault = DictMixin.setdefault
    update = DictMixin.update
    pop = DictMixin.pop
    values = DictMixin.values
    items = DictMixin.items
    iterkeys = DictMixin.iterkeys
    itervalues = DictMixin.itervalues
    iteritems = DictMixin.iteritems

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, self.items())

    def copy(self):
        return self.__class__(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        d = cls()
        for key in iterable:
            d[key] = value
        return d

    def __eq__(self, other):
        if isinstance(other, OrderedDict):
            return len(self)==len(other) and self.items() == other.items()
        return dict.__eq__(self, other)

    def __ne__(self, other):
        return not self == other

VERBOSE = True
def print_v(string):
    """Print message."""
    if VERBOSE:
        print >> sys.stderr, string

def print_e(string):
    """Print erorr."""
    print >> sys.stderr, "Error: " + string

def print_w(string):
    """Print warning."""
    print >> sys.stderr, "Warning: " + string

class ConfigError(Exception):
    """Base class for Config exceptions."""
    pass

class ParseError(ConfigError):
    """Wrapper for all exceptions of ConfigParser module."""
    pass

class UnrecognizedOptions(ConfigError):
    """Configuration file contains undefined option names."""

class MissedOptions(ConfigError):
    """Configuration file misses some options."""
    pass

class OptionValueError(ConfigError):
    """Raised when option has invalid value."""

    def __init__(self, option=None, values=None, message=None):
        # `option` and `values` or only `message` must be specified
        self.option = option
        self.values = values
        self.message = message

    def __str__(self):
        if self.option and self.values:
            return "value of '%s' should be one of the following %s" % \
                (self.option, str(self.values))
        elif self.message:
            return self.message

class Config(object):
    """Object that reads, parses, and writes a configuration file."""

    def __init__(self, filename):
        """Remember the filename."""
        self._filename = filename
        self._parse_options(self._get_defaults(), self._get_valid_opts())

    def parse(self):
        """Parse the configuration file, assign option values to the
        corresponding `Config` attributes. Can raise ParseError, MissedOptions,
        UnrecognizedOptions, and OptionValueError exceptions."""
        config = RawConfigParser(OrderedDict(), OrderedDict)
        try:
            config.read(self._filename)
        except ConfigParser.Error, cpe:
            raise ParseError(str(cpe))
        else:
            items = dict(config.items('SETTINGS'))
            print_v(items)
            options = set(items.keys())
            keys = set(self._defaults.keys())
            missed = keys.difference(options)
            unrecognized = options.difference(keys)
            if missed:
                raise MissedOptions("options '%s' are missed" % \
                    str(list(missed)))
            if unrecognized:
                raise UnrecognizedOptions("options '%s' are unrecognized" % \
                    str(list(unrecognized)))
            self._parse_options(items, self._get_valid_opts())
            self._parse_rules([(i[1],i[0]) for i in config.items('RULES')])

    def write(self):
        """Write a default configuration file."""
        try:
            config_file = open(self._filename, 'wb')
            config_file.write(self._config_str % self._get_defaults())
        except IOError:
            raise
        finally:
            if config_file:
                config_file.close()

    def _get_defaults(self):
        return dict([(k, self._defaults[k][0]) for k in self._defaults])

    def _get_valid_opts(self):
        return dict([(k, self._defaults[k][1]) for k in self._defaults])

    def _parse_options(self, options, valid_opts):
        for opt in options:
            value = options[opt]
            possible = valid_opts[opt]
            if isinstance(possible, tuple):
                if value in possible:
                    setattr(self, opt, value)
                    continue
                else:
                    raise OptionValueError(opt, possible)
            elif callable(possible):
                setattr(self, opt, possible(self, value))
            elif possible is None:
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                setattr(self, opt, value)
                continue
            else:
                raise TypeError(type(possible))

    def _parse_rules(self, rules):
        for item in rules:
            regex, awn = item[0], item[1]
            try:
                pattern = re.compile(regex, re.I)
            except re.error, e:
                raise OptionValueError(message="invalid regex " +
                    "'%s': %s" % (regex, str(e)))
            else:
                groupsno = len(re.compile('\((?!\?)').findall(regex))
                tokens = re.compile('\$[0-9]').findall(awn)
                if tokens:
                    max_groupno = max([int(t[1]) for t in tokens])
                    if max_groupno > groupsno:
                        raise OptionValueError(
                            message="invalid group number " +
                            "(%i) in AWN '%s', maximum is %i for regex '%s'" %
                            (groupsno, awn, max_groupno, regex))
                repl = re.compile('(\$[0-9])').split(awn)
                for i,t in enumerate(repl):
                    if t and t[0] == '$':
                        repl[i] = int(t[1])
                self.rules.append((pattern, repl))

    def _parse_modifiers(self, modifier_str):
        mods = modifier_str.split('+')
        for i, mod in enumerate(mods):
            if mod in ('Control', 'Shift'): pass
            elif mod == 'Alt': mods[i] = 'Mod1'
            elif mod == 'Super': mods[i] = 'Mod4'
            else:
                raise OptionValueError(
                    message="invalid modifier name '%s'" % mod)
        return mods

    def _parse_title_format(self, title_format):
        """Check title_format contains not more than one %t and %s"""
        if title_format.count('%t') > 1 or title_format.count('%s') > 1:
            raise OptionValueError(message=
                "only one occurance of %t or %s in title_format is possible")
        return title_format

    rules = list()

    _rules = [
        ("gnome-(.*)", "$1")
    ]

    _defaults = {
        'keyboard_layout': ('QWERTY', ('QWERTY', 'Dvorak')),
        'modifiers' : ('Super', _parse_modifiers),
        'group_windows_by' : ('Class', ('Class', 'Group', 'None')),
        'title_format' : ('%t   /%s/', _parse_title_format),
        }
    """Dictionary with keys containing options, and values containing
    tuples of the default value and a list of possible valid values.

    Format:
    {option: (default_value, (variants) or parse_function or None), ...},
    where None means that arbitary string is allowed.
    Enclosing double quotes arround arbitary strings will be stripped.
    """

    _config_str = re.compile('^ +', re.M).sub('',
     """[SETTINGS]
     # Keyboard Layout. This is used to produce keybindings that are easier to
     # press with your keyboard layout.
     # Possible values: Dvorak, QWERTY.
     keyboard_layout = %(keyboard_layout)s

     # Combination of the modifiers separated by '+'. All keybindings use the
     # same modifiers.
     # Possible modifiers: Control, Shift, Alt, Super.
     modifiers = %(modifiers)s

     # All windows of the same application are grouped. Windows of the same
     # group are binded to the keys with the same prefix. The following option
     # specifies what windows should belong to the same group.
     # Possible values: Class, Group, None.
     # Class -- two windows belong to the one group if they have equal window
     # classes. This property can be obtained with xprop utility.
     # Group -- group windows as window manager normally does.
     # None -- do not group at all.
     group_windows_by = %(group_windows_by)s

     # Change window titles, so they include the corresponding shortcuts.
     # %%t and %%s are replaced by the window title and the shortcut
     # accordingly. Only one occurance of %%t or %%s in title_format is
     # possible. Set to None to deny modifying the window titles.
     title_format = %(title_format)s

     [RULES]
     # This section specifies rules according to which window classes are
     # transformed to abstract window names (AWNs). AWNs are used to determine
     # window shortcuts.  For example, if AWN is 'xterm' than keybinding will
     # more likely 'mod+x'. If it is already assigned to another window or is
     # used by an another programm, xatk will try to bind the window to
     # 'mod+t'. It sorts out the keys until it finds one that is not
     # occupied. If it turns out there is no such a key, xatk will assign the
     # window to an arbitary unused keybinding.

     # Format:
     # replacement_string = class_regexp
     # Replacement string can contain '$n' expression (where 0<n<10),
     # which is substituted with the text matched by the nth subexpression.
     # Note: everything after '=' or ':' will be interpreted as a regular
     # expression
     """
    ) + '\n'.join(['='.join((i[1],i[0])) for i in _rules])

class KeyboardLayout(object):
    """Object holding information about the order of keys of different keboard
    layouts"""

    dvorak = '\',.pyfgcrlaoeuidhtns;qjkxbmwvz'
    qwerty = 'qwertyuiopasdfghjkl;zxcvbnm,./'

    def __init__(self, layout="QWERTY"):
        if layout == "DVORAK":
            # dvorak layout with 3 rows by 10 charachters
            self.keys = self.dvorak
        elif layout == "QWERTY":
            # qwerty layout with 3 rows by 10 charachters
            self.keys = self.qwerty
        else:
            print_v("Unknown keyboard layout name: %s. "
                "QWERTY will be used." % layout)
            self.keys = self.qwerty
        self.indexes = dict(zip(self.keys, range(len(self.keys))))

class ShortcutGenerator(object):
    """Class which generates shortcuts for specified windows taking into
    account windows' and window list's information."""

    def __init__(self, keyboard_layout):
        self.layout = keyboard_layout

    def _get_direction(self, base):
        """Determine where next suffix key would be from the base key
        Return 1 if to the right, and -1 if to the left"""
        return 1 if self.layout.indexes[base] % 10 < 5 else -1

    def _next_suffix(self, shortcuts):
        """Return a new suffix which can be any symbol from
        `KeyboardLayout.keys` for a shortcut with the base key
        `shortcuts[0][0]`."""
        base = shortcuts[0][0]
        dir_ = self._get_direction(base)
        suffixes = [s[1] for s in shortcuts if len(s) == 2]
        if not suffixes:                # first shortcut with suffix
            return self.layout.keys[self.layout.indexes[base] + dir_]
        suffix_indexes = [self.layout.indexes[s] for s in suffixes]
        # get last suffix index
        first_index = self.layout.indexes[suffixes[0]]
        left_indexes  = [i for i in suffix_indexes if i < first_index]
        right_indexes = [i for i in suffix_indexes if i > first_index]
        if dir_ == 1:                   # move right
            if left_indexes:            # crossed over the rightmost symbol
                last_index = max(left_indexes)
            elif right_indexes:
                last_index = max(right_indexes)
            else:                       # only one suffix
                last_index = first_index
        else:                           # move left
            if right_indexes:           # crossed over the leftmost symbol
                last_index = min(right_indexes)
            elif left_indexes:
                last_index = min(left_indexes)
            else:                       # only one suffix
                last_index = first_index
        next_index = (last_index + dir_) % len(self.layout.keys)
        next_suffix = self.layout.keys[next_index]
        if next_suffix == base:         # all suffixes are over
            return None
        else:
            return next_suffix

    def _new_base(self, name, bases):
        for base in name:
            if base not in bases and base.isalpha():
                return base
        free_bases = set(self.layout.keys).symmetric_difference(bases)
        for base in free_bases:
            if base.isalpha():
                return base
        return None                     # all the bases are overed

    _forbidden_bases = set()

    def forbid_base(self, base):
        """Tell `ShortcutGenerator` not to use the `base` key for new
        shortcuts"""
        self._forbidden_bases.add(base)

    def new_shortcut(self, window_list, window):
        """Return a new shortcut generated for `window`.

        Return None if no new shortcut is possible. `wid` and `gid` attributes
        of `window` must be initialised before the method call.
        """
        shortcuts = window_list.get_group_shortcuts(window.gid)
        if not shortcuts:
            base = self._new_base(window.awn,
                window_list.get_all_bases().union(self._forbidden_bases))
            return base
        else:
            prefix = shortcuts[0][0]
            suffix = self._next_suffix(shortcuts)
            if suffix is None:
                return None
            else:
                return prefix + suffix

class WindowList(list):
    """Extend list. `WindowList` elements must be of type `Window`."""

    def get_window(self, wid):
        """Return a `Window` object with the window id `wid`"""
        for win in self:
            if win.wid == wid:
                return win

    def get_windows(self, wids):
        """Return a list of `Window` objects with the window ids in `wids`"""
        windows = list()
        for win in self:
            if win.wid in wids:
                windows.append(win)
        return windows

    def get_group_id(self, name):
        for win in self:
            if win.awn == name:
                return win.gid
        return 0

    def get_group_windows(self, gid):
        """Return a list of `Window` objects with the window group id `gid`
        and sorted by `wid` attribute."""
        return sorted([w for w in self if w.gid == gid], key=lambda w: w.wid)

    def get_group_shortcuts(self, gid):
        """Return a list of shortcuts with the window group id `gid`."""
        return [w.shortcut for w in self if w.gid == gid and w.shortcut]

    def get_all_bases(self):
        """Return a set of all used base keys."""
        return set([win.shortcut[0] for win in self if win.shortcut])

    last_unique_group_id = 0

    def get_unique_group_id(self):
        self.last_unique_group_id += 1
        return self.last_unique_group_id

class Window(object):
    """An object holding attributes related to a window.

    Attributes:
    - `wid`: window id
    - `gid`: window group id
    - `awn`: abstract window name, from which shortcut is produced
    - `name`: real window name (title)
    - `shortcut`: is represented by a string of length one or two (e.g. 'a' or
      'bn', where 'a' is the base key, 'b' is the prefix, and 'n' is the
      suffix).
    """

    def _get_awn(self):
        return self._awn

    def _set_awn(self, awn):
        if isinstance(awn, basestring):
            self._awn = awn.lower()
        elif awn is None:
            self._awn = ''
        else:
            raise TypeError('awn must be a string object or None')

    awn = property(_get_awn, _set_awn)

    def _get_shortcut(self):
        return self._shortcut

    def _set_shortcut(self, shortcut):
        if isinstance(shortcut, basestring):
            self._shortcut = shortcut.lower()
        elif shortcut is None:
            self._shortcut = ''
        else:
            raise TypeError('Shortcut must be a string object or None')

    shortcut = property(_get_shortcut, _set_shortcut)

class BadWindow(Exception):
    """Wrapper for Xlib's BadWindow exception"""

    def __init__(self, wid):
        self.wid = wid

    def __str__(self):
        return "Bad window with id=%s" % hex(self.wid)


class XTool(object):
    """Wrapper for Xlib related methods"""

    def __init__(self):
        self._display = display.Display()
        self._root = self._display.screen().root
        self._root.change_attributes(event_mask=X.KeyPressMask |
            X.KeyReleaseMask | X.PropertyChangeMask)
        self._init_mod_keycodes()

    # keyboard related methods

    def grab_key(self, keycode, mask, onerror=None):
        self._root.grab_key(keycode, mask,
            1, X.GrabModeAsync, X.GrabModeAsync, onerror=onerror)
        self._root.grab_key(keycode, mask | X.Mod2Mask,
            1, X.GrabModeAsync, X.GrabModeAsync, onerror=onerror)
        self._root.grab_key(keycode, mask | X.LockMask,
            1, X.GrabModeAsync, X.GrabModeAsync, onerror=onerror)
        self._root.grab_key(keycode, mask | X.Mod2Mask | X.LockMask,
            1, X.GrabModeAsync, X.GrabModeAsync, onerror=onerror)

    def ungrab_key(self, keycode, mask, onerror=None):
        self._root.ungrab_key(keycode, mask, onerror=onerror)
        self._root.ungrab_key(keycode, mask | X.Mod2Mask, onerror=onerror)
        self._root.ungrab_key(keycode, mask | X.LockMask, onerror=onerror)
        self._root.ungrab_key(keycode, mask | X.Mod2Mask | X.LockMask,
            onerror=onerror)

    def grab_keyboard(self):
        self._root.grab_keyboard(1, X.GrabModeAsync, X.GrabModeAsync,
            X.CurrentTime)

    def ungrab_keyboard(self):
        self._display.ungrab_keyboard(X.CurrentTime)
        # after the keyboard is ungrabbed no release event
        # will come, so forget all pressed keys
        self._pressed_keys.clear()

    def sync(self):
        self._display.sync()

    def get_keycode(self, key, use_keysym=False):
        # Since keysyms are backward compatible with ASCII we can use ord()
        # instead of XK.string_to_keysym() to avoid translation of
        # non-alphabetical symbols to keysym strings previosly
        keysym = XK.string_to_keysym(key) if use_keysym else ord(key)
        return self._display.keysym_to_keycode(keysym)

    def get_key(self, keycode):
        return XK.keysym_to_string(self._display.keycode_to_keysym(keycode, 0))

    def _init_mod_keycodes(self):
        self._mod_keycodes = set(
            [
                self.get_keycode('Shift_L', True),
                self.get_keycode('Shift_R', True),
                self.get_keycode('Control_L', True),
                self.get_keycode('Control_R', True),
                self.get_keycode('Alt_L', True),
                self.get_keycode('Alt_R', True),
                self.get_keycode('Super_L', True),
                self.get_keycode('Super_R', True)
            ])
        if 0 in self._mod_keycodes:
            self._mod_keycodes.remove(0)

    def is_mofifier(self, keycode):
        return keycode in self._mod_keycodes

    def _is_key_pressed(self, keycode):
        bitmap = self._display.query_keymap()
        return bitmap[keycode / 8] & (1 << (keycode % 8))

    # window reltaed methods

    def _atom(self, name):
        return self._display.intern_atom(name)

    def get_window_list(self):
        return self._root.get_full_property(
            self._atom("_NET_CLIENT_LIST"), Xatom.WINDOW).value

    def _get_window(self, wid):
        return self._display.create_resource_object("window", wid)

    def get_window_name(self, wid):
        win = self._get_window(wid)
        try:
            name = win.get_full_property(self._atom("_NET_WM_NAME"), 0)
        except error.BadWindow:
            raise BadWindow(wid)
        if name:
            return unicode(name.value, 'utf-8')
        else:
            return unicode(win.get_wm_name())

    def get_window_application(self, wid):
        try:
            cls = self._get_window(wid).get_wm_class()
        except error.BadWindow:
            raise BadWindow(wid)
        if cls:
            return cls[0]
        else:
            return ''

    def get_window_class(self, wid):
        try:
            cls = self._get_window(wid).get_wm_class()
        except error.BadWindow:
            raise BadWindow(wid)
        if cls:
            return cls[1]
        else:
            return ''

    def get_window_group_id(self, wid):
        hints = self._get_window(wid).get_wm_hints()
        group_id = 0
        if hints:
            group_id = hints.window_group.id
        return group_id

    def _set_property(self, wid, prop, name):
        if not isinstance(name, unicode):
            raise TypeError('an unicode string is required')
        win = self._get_window(wid)
        win.change_property(
            self._atom(prop),
            self._atom('UTF8_STRING'),
            8,
            name.encode('utf-8'),
            mode=X.PropModeReplace);

    def set_window_name(self, wid, name):
        self._set_property(wid, '_NET_WM_NAME', name)

    def set_window_icon_name(self, wid, name):
        self._set_property(wid, '_NET_WM_ICON_NAME', name)

    def raise_window(self, wid):
        window = self._get_window(wid)
        raise_event = protocol.event.ClientMessage(
            client_type=self._atom('_NET_ACTIVE_WINDOW'),
            window=window,
            data=(32, [2,0,0,0,0]))
        self._display.send_event(
            self._root,
            raise_event,
            event_mask=X.SubstructureRedirectMask or X.SubstructureNotifyMask)
        self._display.flush()

    def listen_window_name(self, wid):
        """Tell XTool to watch the window name changes. Otherwise
        `window_name_listener.on_window_name_changed()` will not work."""
        self._get_window(wid).change_attributes(
            event_mask=X.PropertyChangeMask)

    def register_key_listener(self, key_listener):
        """Register `key_listener` which must have `on_key_press` and
        `on_key_release` methods."""
        self._key_listener = key_listener

    def register_window_list_listener(self, window_list_listener):
        """Register `window_list_listener` which must have
        `on_window_list_changed` method."""
        self._window_list_listener = window_list_listener

    def register_window_name_listener(self, window_name_listener):
        """Register `window_name_listener` which must have
        `on_window_name_changed` method."""
        self._window_name_listener = window_name_listener

    def _window_list_changed(self, event):
        return event.type == X.PropertyNotify and \
            event.atom == self._atom("_NET_CLIENT_LIST")

    def _window_name_changed(self, event):
        return event.type == X.PropertyNotify and \
            (event.atom == self._atom("_NET_WM_NAME") or
            event.atom == self._atom("WM_NAME"))

    def _check_listeners(self):
        """Check if all listeners are registered before entering event_loop"""
        ok = True
        if not self._key_listener:
            ok = False
            print_e('No key_listener')
        elif not (hasattr(self._key_listener, 'on_key_press') and
                hasattr(self._key_listener, 'on_key_release')):
            ok = False
            print_e('Bad key_listener')
        if not self._window_list_listener:
            ok = False
            print_e('No window_list_listener')
        elif not hasattr(self._window_list_listener, 'on_window_list_changed'):
            ok = False
            print_e('Bad window_list_listener')
        if not ok:
            sys.exit(1)

    _pressed_keys = set()

    def _is_key_press_fake(self, keycode):
        """Return True if KeyPress event was caused by auto-repeat mode."""
        if keycode in self._pressed_keys:
            return True
        else:
            self._pressed_keys.add(keycode)
            return False

    def _is_key_release_fake(self, keycode):
        """Return True if KeyRelease event was caused by auto-repeat mode."""
        if self.is_mofifier(keycode):
            return False                # modifiers are never auto-repeated
        if not self._is_key_pressed(keycode):
            try:
                self._pressed_keys.remove(keycode)
            except KeyError:
                # some key had been pressed before the keyboard was grabbed
                # and now it is released while the keyboard is still
                # grabbed. Actually this is not a fake event, though ignore it.
                return True
            return False
        return True

    def event_loop(self):
        """Event loop. Before entering the loop all the listeners must be
        registered wih `XTool.register_xxx_listener()`."""
        self._check_listeners()
        while True:
            event = self._display.next_event()
            if self._window_list_changed(event):
                self._window_list_listener.on_window_list_changed()
            elif self._window_name_changed(event):
                self._window_name_listener.on_window_name_changed(
                    event.window.id)
            elif event.type == X.KeyPress:
                keycode = event.detail
                if not self._is_key_press_fake(keycode):
                    self._key_listener.on_key_press(keycode)
            elif event.type == X.KeyRelease:
                keycode = event.detail
                if not self._is_key_release_fake(keycode):
                    self._key_listener.on_key_release(keycode)

class KeyBinderError(Exception):
    """Base class for KeyBinder exceptions."""

class BadShortcut(KeyBinderError):
    """Raised when one of the shortcut's symbol has invalid keycode."""

    def __init__(self, shortcut):
        self.shortcut = shortcut

    def __str__(self):
        return "can't bind shotcut '%s'. Symbol '%s' has bad keycode." % \
                (self.shortcut, self.shortcut[0])

class GrabError(KeyBinderError):
    """Raised when the key is already grabbed."""

    def __init__(self, shortcut, modmask):
        self.shortcut = shortcut
        self.modmask = modmask

    def __str__(self):
        return ("can't grab key '%s' with modifier mask %s. It is already " +\
        "grabbed by another programm.") % (self.shortcut[0], hex(self.modmask))

class KeyBinder(object):

    _bindings = dict()
    """Complex keybindings: shortcuts of length two are allowed.
    Multiple pressing a base key call respective callback functions
    alternately.
    Format: {base_key: [(shortcut, callback), ...], ...}
    base_key and bindings[base_key][0] must be equal.
    Default modifier (passed to `self.__init__()`) is used."""

    _bindings2 = list()
    """Simple keybindings: only one length shortcuts.
    `_bindings2` format: {(shortcut, modmask): callback, ...}"""

    def __init__(self, modifiers):
        self._modmask = self._get_modmask(modifiers)
        self._key_listener = KeyListener(self._bindings)
        XTOOL.register_key_listener(self._key_listener)

    def _get_modmask(self, modifiers):
        modmask = 0
        for modifier in modifiers:
            if modifier == 'Shift':
                modmask = modmask | X.ShiftMask
            elif modifier == 'Control':
                modmask = modmask | X.ControlMask
            elif modifier == 'Mod1':
                modmask = modmask | X.Mod1Mask
            elif modifier == 'Mod4':
                modmask = modmask | X.Mod4Mask
            else:
                raise ValueError('Bad modifier name:%s\n' % modifier)
        return modmask

    def bind(self, shortcut, callback, modifiers=None):
        """Bind `shortcut` to `callback` function.

        When `modifiers` is None, use default modifiers to form
        keybinding. `shortcut` could have one or two keys. These keybindings
        are used to bind window actions.
        With `modifiers` being a list of modifiers only one key shortcuts are
        allowed. THIS KIND OF KEYBINDINGS ISN'T IMPLEMENTED YET."""
        ec = error.CatchError(error.BadAccess)
        if modifiers is not None:
            keycode = XTOOL.get_keycode(shortcut, use_keysym=True)
            if not keycode:
                raise BadShortcut(shortcut)
            modmask = self._get_modmask(modifiers)
            XTOOL.grab_key(keycode, modmask, onerror=ec)
            XTOOL.sync()
            if ec.get_error():
                raise GrabError(shortcut, self._modmask)
            self._bindings2[(shortcut, modmask)] = callback
        else:
            keycode = XTOOL.get_keycode(shortcut[0])
            if not keycode:
                raise BadShortcut(shortcut)
            XTOOL.grab_key(keycode, self._modmask, onerror=ec)
            XTOOL.sync()
            if ec.get_error():
                raise GrabError(shortcut, self._modmask)
            base_key = shortcut[0]
            if base_key not in self._bindings:
                self._bindings[base_key] = [(shortcut, callback)]
            else:
                self._bindings[base_key].append((shortcut, callback))

    def unbind(self, shortcut):
        """Delete keybinding and ungrab key."""
        base_key = shortcut[0]
        binds = self._bindings[base_key]
        i = [bind[0] for bind in binds].index(shortcut)
        del binds[i]
        if not binds:
            del self._bindings[base_key]
        if len(shortcut) == 1:
            XTOOL.ungrab_key(XTOOL.get_keycode(shortcut[0]), self._modmask)

    def unbind_all(self):
        """Delete all the keybindings and ungrab related keys."""
        for base in self._bindings:
            XTOOL.ungrab_key(XTOOL.get_keycode(base), self._modmask)
        self._bindings.clear()

class KeyListener(object):
    """`KeyListener` recieves the key events, determines the pressed
    keybindings, and calls the appropriate functions."""

    def __init__(self, bindings):
        self._bindings = bindings
        self._initial_state()

    RELEASED, PRESSED = 0, 1

    def _initial_state(self):
        self._modifier_sate = self.PRESSED
        self._base_state = self.RELEASED
        self._next_shortcut = None

    def on_key_press(self, keycode):
        # base key pressed
        if self._base_state == self.RELEASED:
            self._base_state = self.PRESSED
            base_key = XTOOL.get_key(keycode)
            if not base_key or base_key not in self._bindings:
                self._initial_state()
                return
            print_v("base key press: %s" % base_key)
            self._last_base = base_key
            XTOOL.grab_keyboard()
            # only one shortcut for given base key, call corresponding function
            if len(self._bindings[base_key]) == 1:
                print_v("keybinding caught: '%s'" % \
                    self._bindings[base_key][0][0])
                self._bindings[base_key][0][1]()
                XTOOL.ungrab_keyboard()
                self._initial_state()
        # suffix key pressed
        elif self._base_state == self.PRESSED:
                suffix_key = XTOOL.get_key(keycode)
                if not suffix_key:
                    self._initial_state()
                    return
                print_v("suffix press: %s" % suffix_key)
                shortcuts = [bind[0] for bind in
                             self._bindings[self._last_base]]
                shortcut = self._last_base + suffix_key
                try:
                    i = shortcuts.index(shortcut)
                except ValueError: pass # unregistered keybinding, ignore it
                else:
                    print_v("keybinding caught: '%s'" % shortcut)
                    self._bindings[self._last_base][i][1]()
                finally:
                    XTOOL.ungrab_keyboard()
                    self._initial_state()

    def on_key_release(self, keycode):
        key = XTOOL.get_key(keycode)
        # modifier released
        if XTOOL.is_mofifier(keycode):
            print_v("modifier release, keycode: %s" % hex(keycode))
            self._modifier_sate = self.RELEASED
            if self._base_state == self.RELEASED:
                XTOOL.ungrab_keyboard()
                self._initial_state()
        # base key released
        elif key == self._last_base:
            print_v("base key release: %s" % key)
            if self._base_state == self.PRESSED:
                self._base_state = self.RELEASED
                if self._next_shortcut is None or \
                        self._next_shortcut[0] != self._last_base:
                    shortcut = self._last_base
                else:
                    shortcut = self._next_shortcut
                bindings = self._bindings[self._last_base]
                i = [bind[0] for bind in bindings].index(shortcut)
                next_i = (i + 1) % len(bindings)
                self._next_shortcut = bindings[next_i][0]
                print_v("keybinding caught: '%s'" % shortcut)
                bindings[i][1]()
                if self._modifier_sate == self.RELEASED:
                    XTOOL.ungrab_keyboard()
                    self._initial_state()
        # suffix key released
        else:
            print_v("suffix key release: %s" % key)

class WindowManager(object):
    """`WindowManager` tracks changes of the window list, their names, assigns
    the shortcuts to thw new windows."""

    def __init__(self, shortcut_generator, key_binder):
        self._shortcut_generator = shortcut_generator
        self._key_binder = key_binder
        self._windows = WindowList()
        for wid in XTOOL.get_window_list():
            self._on_window_create(wid)
        XTOOL.register_window_list_listener(self)
        XTOOL.register_window_name_listener(self)

    def _bind(self, wid, shortcut):
        def raise_window(wid=wid):
            XTOOL.raise_window(wid)
        self._key_binder.bind(shortcut, raise_window)

    def on_window_list_changed(self):
        old_wids = set([win.wid for win in self._windows])
        current_wids = set(XTOOL.get_window_list())
        new_wids = current_wids.difference(old_wids)
        closed_wids = old_wids.difference(current_wids)
        for new_wid in sorted(new_wids):
            print_v("new window (id=%s)" % hex(new_wid))
            self._on_window_create(new_wid)
        if closed_wids:
            print_v("windows closed (ids: %s)" %
                ', '.join(map(hex, closed_wids)))
            self._on_windows_close(sorted(closed_wids))

    def on_window_name_changed(self, wid):
        print_v("window name changed (id=%s)" % hex(wid))
        win = self._windows.get_window(wid)
        # In some rare cases 'window name changed' event is recieved after
        # 'window closed' event somehow. Check if it has not already been
        # removed from the window list
        if win is not None:
            self._update_window_name(win, win.shortcut)
        else:
            print_w(('name of the window with id=%s changed while it is ' +
                     'not in the window list') % hex(wid))

    def _on_windows_close(self, wids):
        """Delete the window from the window list and unbind it.

        If the group leader (the first window of the group) was closed, rebind
        all the other windows of the group."""
        wins_closed = self._windows.get_windows(wids)
        for win_closed in wins_closed:
            self._key_binder.unbind(win_closed.shortcut)
            print_v("window '%s' (id=%s) was unbinded from '%s'" %
                (win_closed.name, hex(win_closed.wid), win_closed.shortcut))
            del self._windows[self._windows.index(win_closed)]
        groups = set([w.gid for w in wins_closed if len(w.shortcut) == 1])
        for group in groups:
            wins = self._windows.get_group_windows(group)
            if len(wins) > 0:
                base_key = wins[0].shortcut[0]
                # rebind all the windows of the group
                for win in wins:
                    self._key_binder.unbind(win.shortcut)
                    win.prev_shortcut, win.shortcut = win.shortcut, None
                for i, win in enumerate(wins):
                    if i == 0: # base key for the group should remain the same
                        win.shortcut = base_key
                        self._bind(win.wid, win.shortcut)
                        print_v("window '%s' (id=%s) was binded to '%s'" %
                            (win.awn, hex(win.wid), win.shortcut))
                    else:
                        self._add_shortcut(win)
                    print_v('Rebinding: %s -> %s' % (win.prev_shortcut,
                                                     win.shortcut))
                    self._update_window_name(win, win.prev_shortcut)
                    del win.prev_shortcut

    def _on_window_create(self, wid):
        """Create window, initialise its attributes, add to the window list,
        possibly change its name, and register the window for watching its
        name."""
        window = Window()
        window.wid = wid
        window.gid = 0
        try:
            window.name = XTOOL.get_window_name(window.wid)
            window_class = XTOOL.get_window_class(wid)
        except BadWindow, err:
            print_e(str(err))
            return
        window.awn = self._get_awn(window_class)
        if CONFIG.group_windows_by == 'Group':
            window.gid = XTOOL.get_window_group_id(wid)
        elif CONFIG.group_windows_by == 'Class':
            window.gid = self._windows.get_group_id(window.awn)
        if not window.gid:
            window.gid = self._windows.get_unique_group_id()
        self._add_shortcut(window)
        if window.shortcut:
            self._windows.append(window)
            self._update_window_name(window, window.shortcut)
            XTOOL.listen_window_name(window.wid)

    def _add_shortcut(self, window):
        """Generate a new unused shortcut for `window` and add the shortcut to
        the `window`. Set the shortcut to None if all the possible keys are
        grabbed."""
        while True:
            shortcut = self._shortcut_generator.new_shortcut(
                self._windows, window)
            if not shortcut:
                print_w('so many windows, so few keys')
                window.shortcut = None
                return
            try:
                self._bind(window.wid, shortcut)
            except GrabError, ge:
                print_w(str(ge))
                self._shortcut_generator.forbid_base(shortcut[0])
            else:
                break
        window.shortcut = shortcut
        print_v("window '%s' (id=%s) was binded to '%s'" %
            (window.awn, hex(window.wid), window.shortcut))

    def _update_window_name(self, window, prev_shortcut):
        """Change the window name, so it includes the shortcut."""
        if CONFIG.title_format == 'None':
            return
        try:
            new_name = XTOOL.get_window_name(window.wid)
        except BadWindow, err:
            print_e(str(err))
            return
        edges = CONFIG.title_format.split('%t')
        start = edges[0].replace('%s', prev_shortcut)
        end = edges[1].replace('%s', prev_shortcut)
        if new_name.startswith(start) and new_name.endswith(end):
            new_name = new_name[len(start):len(new_name)-len(end)]
            if new_name == window.name and prev_shortcut == window.shortcut:
                return                  # window name wasn't changed
        if new_name != window.name:
            print_v("window name '%s' (id=%s) changed to '%s'" %
                    (window.name, hex(window.wid), new_name))
        window.name = new_name
        new_name = CONFIG.title_format.replace('%t', new_name)
        new_name = new_name.replace('%s', window.shortcut)
        XTOOL.set_window_name(window.wid, new_name)

    def _get_awn(self, win_class):
        for ruleno, rule in enumerate(CONFIG.rules):
            pat = rule[0]
            repl = list(rule[1])
            match = pat.match(win_class)
            if not match:
                continue
            else:
                for i,token in enumerate(repl):
                    if type(token) == int:
                        try:
                            repl[i] = match.group(token)
                        # actually should be detected by config parser
                        except IndexError:
                            print_e("invalid group number %i in '%s'" %
                                (token, ''.join([str(s) for s in repl])))
                            del CONFIG.rules[ruleno]
                            continue
                return ''.join(repl)
        return win_class

if __name__ == "__main__":
    filename = os.path.expanduser('~/.xatkrc')
    CONFIG = Config(filename)
    if os.path.exists(filename):
        try:
            CONFIG.parse()
        except (ParseError, OptionValueError, UnrecognizedOptions,
                MissedOptions), err:
            print_e(str(err))
            sys.exit(1)
    else:
        try:
            CONFIG.write()
        except IOError, ioe:
            print_e(str(ioe))
            sys.exit(1)

    XTOOL = XTool()
    kblayout = KeyboardLayout(CONFIG.keyboard_layout)
    shortcut_generator = ShortcutGenerator(kblayout)
    keybinder = KeyBinder(CONFIG.modifiers)
    winmanager = WindowManager(shortcut_generator, keybinder)
    XTOOL.event_loop()
