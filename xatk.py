#!/usr/bin/env python

import sys
import os.path
import re
import operator
import ConfigParser
from ConfigParser import RawConfigParser
from Xlib import display, error, protocol, X, Xatom, XK

VERBOSE = True
def print_v(string):
    if VERBOSE:
        print >> sys.stderr, string

def print_e(string):
    print >> sys.stderr, "Error: " + string

def print_w(string):
    print >> sys.stderr, "Warning: " + string

class ConfigError(Exception): pass

class ParseError(ConfigError): pass

class UnrecognizedOptions(ConfigError): pass

class MissedOptions(ConfigError): pass

class OptionValueError(ConfigError):
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

    def __init__(self, filename):
        self.filename = filename
        self._parse_options(self._get_defaults(), self._get_valid_opts())

    def parse(self):
        config = RawConfigParser()
        try:
            config.read(self.filename)
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
        try:
            config_file = open(self.filename, 'wb')
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
        # format:
        # option: (default_value, (variants) or parse_function or None),
        # None means that arbitary string is allowed.
        # Enclosing double quotes arround arbitary strings will be stripped.
        'keyboard_layout': ('QWERTY', ('QWERTY', 'Dvorak')),
        'modifiers' : ('Super', _parse_modifiers),
        'group_windows_by' : ('Class', ('Class', 'Group', 'None')),
        'title_format' : ('%t   /%s/', _parse_title_format),
    }

    _config_str = re.compile('^ +', re.M).sub('',
     """[SETTINGS]
     # Keyboard Layout. This is used to produce keybindings that are easier to
     # press with your keyboard.
     # Possible values: Dvorak, QWERTY.
     keyboard_layout = %(keyboard_layout)s

     # Combination of modifiers separated by '+'. All keybindings use the same
     # modifiers.
     # Possible modifiers: Control, Shift, Alt, Super.
     modifiers = %(modifiers)s

     # All windows of the same application will be grouped. The windows of one
     # group will be binded to keys with the same prefix. The following option
     # determines in what way different windows will be treated as of one group.
     # Possible values: Class, Group, None.
     # Class -- two windows will belong to the one group if they have equal
     # window classes. This property can be obtained with xprop.
     # Group -- will group windows as window manager normally does.
     # None -- will not group at all.
     group_windows_by = %(group_windows_by)s

     # Include shortcuts to window titles. %%t and %%s will be replaced by
     # corresponding window title and shortcut accordingly. Set to None to deny
     # modifying window titles.
     title_format = %(title_format)s

     [RULES]
     # Rules according to which window classes are transformed to abstract
     # window names (AWN), which are used when generating new keybindings.
     # Say, if AWN is 'xterm' than keybinding will more likely 'mod+x'. If it
     # is already in use, the programm will try to bind the window to 'mod+t'.
     # On the RIGHT side there is a regular expression that matches the window
     # class and the string that replaces it on the LEFT. Replacement string
     # can contain '$n' expression (where 0<n<10), which is substituted with
     # the text matched by the nth subexpression.
     # Note: everything after '=' or ':' will be interpreted as a regular
     # expression
     """
    ) + '\n'.join(['='.join((i[1],i[0])) for i in _rules])

class KeyboardLayout(object):

    dvorak = '"<>pyfgcrlaoeuidhtns-;qjkxbmwvz'
    qwerty = 'qwertyuiopassdfghjkl;zxcvbnm,./'

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
    def __init__(self, keyboard_layout):
        self.layout = keyboard_layout

    def _get_direction(self, base):
        """Determine where next suffix key would be from the base key
        Return 1 if to the right, and -1 if to the left"""
        return 1 if self.layout.indexes[base] % 10 < 5 else -1

    def _last_suffix(self, shortcuts):
        # base key and prefix key must be equal
        base = shortcuts[0][0]
        if len(shortcuts) == 1:
            if len(shortcuts[0]) == 1:
                return shortcuts[0][0]
        suffixes = [shortcut[1] for shortcut in shortcuts if len(shortcut) == 2]
        most = operator.gt if self._get_direction(base) == 1 else operator.lt
        return reduce(lambda s1, s2: s1 if most(self.layout.indexes[s1],
            self.layout.indexes[s2]) else s2, suffixes)

    def _next_suffix_(self, base, suffix):
        step = self._get_direction(base)
        next_i = self.layout.indexes[suffix] + step
        if next_i == len(self.layout.keys):
            suffix = self.layout.keys[0]
        else:
            suffix = self.layout.keys[next_i]
        if not suffix == base:
            return suffix
        else:
            return None

    def _next_suffix(self, shortcuts):
        suffix = self._last_suffix(shortcuts)
        return self._next_suffix_(shortcuts[0][0], suffix)

    def _new_base(self, name, all_bases):
        if len(all_bases) >= 26: # all alphabet keys are already in use
            return None
        for base in name:
            if base not in all_bases and base.isalpha():
                return base
        free_bases = set(self.layout.keys).symmetric_difference(all_bases)
        for base in free_bases:
            if base.isalpha():
                return base

    _forbidden_bases = set()

    def forbid_base(self, base):
        """Tell `ShortcutGenerator` not to use `base` key for new shortcuts"""
        self._forbidden_bases.add(base)

    def new_shortcut(self, window_list, window):
        """Return a new shortcut generated for `window`.  Return None if no new
        shortcut is possible. `wid` and `gid` attributes of `window` must be
        set before the call of `new_shortcut`.

        """
        shortcuts = window_list.get_group_shortcuts(window.gid)
        # prefix, base = None, None
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
        '''Return a `Window` object with the window id `wid`'''
        for win in self:
            if win.wid == wid:
                return win

    def get_windows(self, wids):
        '''Return the `Window` objects with the window ids `wids`'''
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
        return sorted(
            [win for win in self if win.gid == gid], key=lambda win: win.wid)

    def get_group_shortcuts(self, gid):
        """Return a list of shortcuts with the window group id `gid`."""
        return [win.shortcut for win in self if win.gid == gid and win.shortcut]

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
    - `awn`: abstract window name, from which shortcut is generated
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

class XTool(object):

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

    # windows reltaed methods

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
            print_v("bad window (id=%s) on retrieving name" % hex(wid))
            return None
        if name:
            return unicode(name.value, 'utf-8')
        else:
            return unicode(win.get_wm_name())

    def get_window_application(self, wid):
        try:
            cls = self._get_window(wid).get_wm_class()
        except error.BadWindow:
            print_v("bad window (id=%s) on retrieving application" % hex(wid))
            return None
        if cls:
            return cls[0]
        else:
            return ''

    def get_window_class(self, wid):
        try:
            cls = self._get_window(wid).get_wm_class()
        except error.BadWindow:
            print_v("bad window (id=%s) on retrieving class" % hex(wid))
            return None
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
        self._get_window(wid).change_attributes(
            event_mask=X.PropertyChangeMask)

    def register_key_listener(self, key_listener):
        self._key_listener = key_listener

    def register_window_list_listener(self, window_list_listener):
        self._window_list_listener = window_list_listener

    def register_window_name_listener(self, window_name_listener):
        self._window_name_listener = window_name_listener

    def _window_list_changed(self, event):
        return event.type == X.PropertyNotify and \
            event.atom == self._atom("_NET_CLIENT_LIST")

    def _window_name_changed(self, event):
        return event.type == X.PropertyNotify and \
            (event.atom == self._atom("_NET_WM_NAME") or
            event.atom == self._atom("WM_NAME"))

    def _check_listeners(self):
        '''Check if all listeners are registered before entering event_loop'''
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

    # two following methods help to recognize fake key events (KeyPress and
    # KeyRelease) caused by auto-repeat mode

    _pressed_keys = set()

    def _is_key_press_fake(self, keycode):
        if keycode in self._pressed_keys:
            return True
        else:
            self._pressed_keys.add(keycode)
            return False

    def _is_key_release_fake(self, keycode):
        is_mod = self.is_mofifier(keycode)
        if not self._is_key_pressed(keycode) or is_mod:
            if not is_mod:
                try:
                    self._pressed_keys.remove(keycode)
                except KeyError: # some key had been pressed before we grabbed
                    return True  # the keyboard and now it is released while
                                 # keyboard is still grabbed
            else: # after keyboard is ungrabbed (modifier is released) no key
                  # release events will come, so forget all pressed keys
                self._pressed_keys.clear()
            return False
        return True

    def event_loop(self):
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
    pass

class BadShortcut(KeyBinderError):
    def __init__(self, shortcut):
        self.shortcut = shortcut

    def __str__(self):
        return "can't bind shotcut '%s'. Symbol '%s' has bad keycode." % \
                (self.shortcut, self.shortcut[0])

class GrabError(KeyBinderError):
    def __init__(self, shortcut, modmask):
        self.shortcut = shortcut
        self.modmask = modmask

    def __str__(self):
        return ("can't grab key '%s' with modifier mask %s. It is already " +\
        "grabbed by another programm.") % (self.shortcut[0], hex(self.modmask))

class KeyBinder(object):

    _bindings = dict()
    '''Complex keybindings: shortcuts of length two are allowed.
    Multiple pressing a base key call respective callback functions
    alternately.
    `_bindings format`: {base_key: [(shortcut, callback), ...], ...}
    base_key and bindings[base_key][0] must be equal.
    Default modifier (passed to `KeyBinder`) is used.'''

    _bindings2 = list()
    '''Simple keybindings: only one length shortcuts
    `_bindings2` format: {(shortcut, modmask): callback, ...}'''

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
        base_key = shortcut[0]
        binds = self._bindings[base_key]
        i = [bind[0] for bind in binds].index(shortcut)
        del binds[i]
        if not binds:
            del self._bindings[base_key]
        if len(shortcut) == 1:
            XTOOL.ungrab_key(XTOOL.get_keycode(shortcut[0]), self._modmask)

    def unbind_all(self):
        for base in self._bindings:
            XTOOL.ungrab_key(XTOOL.get_keycode(base), self._modmask)
        self._bindings.clear()

class KeyListener(object):

    def __init__(self, bindings):
        self._bindings = bindings
        self._initial_state()

    RELEASED, PRESSED = 0, 1

    def _initial_state(self):
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
                self._initial_state()
                print_v("keybinding caught: '%s'" % \
                    self._bindings[base_key][0][0])
                self._bindings[base_key][0][1]()
        # suffix key pressed
        elif self._base_state == self.PRESSED:
                suffix_key = XTOOL.get_key(keycode)
                if not suffix_key:
                    self._initial_state()
                    return
                print_v("suffix press: %s" % suffix_key)
                shortcuts = [bind[0] for bind in self._bindings[self._last_base]]
                shortcut = self._last_base + suffix_key
                try:
                    i = shortcuts.index(shortcut)
                # unregistered keybinding, ignore it
                except ValueError: pass
                else:
                    print_v("keybinding caught: '%s'" % shortcut)
                    self._bindings[self._last_base][i][1]()
                finally:
                    self._initial_state()

    def on_key_release(self, keycode):
        key = XTOOL.get_key(keycode)
        # modifier released
        if XTOOL.is_mofifier(keycode):
            print_v("modifier release, keycode: %s" % hex(keycode))
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
        # suffix key released
        else:
            print_v("suffix key release: %s" % key)

class WindowManager(object):
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
        self._update_window_name(win, win.shortcut)

    def _on_windows_close(self, wids):
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
                    print_v('Rebinding: %s -> %s' % (win.prev_shortcut, win.shortcut))
                    self._update_window_name(win, win.prev_shortcut)
                    del win.prev_shortcut

    def _on_window_create(self, wid):
        window = Window()
        window.wid = wid
        window.gid = 0
        window.name = XTOOL.get_window_name(window.wid)
        window.awn = self._get_awn(XTOOL.get_window_class(wid))
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
        while True:
            shortcut = self._shortcut_generator.new_shortcut(
                self._windows, window)
            if not shortcut:
                print_w('So many windows, so few keys')
                return
            try:
                # self._key_binder.bind(shortcut, raise_window)
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
        if CONFIG.title_format == 'None':
            return
        new_name = XTOOL.get_window_name(window.wid)
        if new_name is None:
            return
        edges = CONFIG.title_format.split('%t')
        start = edges[0].replace('%s', prev_shortcut)
        end = edges[1].replace('%s', prev_shortcut)
        if new_name.startswith(start) and new_name.endswith(end):
            new_name = new_name[len(start):len(new_name)-len(end)]
            if new_name == window.name and prev_shortcut == window.shortcut:
                return
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
