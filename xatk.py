#!/usr/bin/env python

import ConfigParser
import logging.handlers
import optparse
import os.path
import re
import signal
import sys
from ConfigParser import RawConfigParser
from UserDict import DictMixin

try:
    import Xlib.X
    import Xlib.XK
    import Xlib.Xatom
    import Xlib.display
    import Xlib.error
    import Xlib.protocol
except ImportError:
    XLIB_PRESENT = False
else:
    XLIB_PRESENT = True


PROG_NAME = 'xatk'
VERSION  = (0,0,0)
CONFIG_PATH = '~/.xatkrc'
VERSION_NAME = '%s %s' % (PROG_NAME, '.'.join(map(str, VERSION)))
FIELDS = ('config', 'windows', 'keys', 'signals', 'X')

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

class Log(object):
    """Provide static methods for logging similar to those in the logging
    module."""

    SYSINFO = 5
    CATLEN = 7
    FORMAT_DICT = OrderedDict(
        (
            ('time'     , '%(asctime)-8s,%(msecs)03d'),
            ('level'    , '%(levelname)-8s'),
            ('category' , '%(catstr)-' + str(CATLEN) + 's'),
            ('message'  , '%(message)s')
        )
    )
    MSG_FORMAT_FULL = ' - '.join(FORMAT_DICT.values())
    MSG_FORMAT = '%s - %s' % (FORMAT_DICT['level'], FORMAT_DICT['message'])
    DATE_FORMAT = '%H:%M:%S'

    logging.addLevelName(SYSINFO, 'SYSINFO')
    logger = logging.getLogger('root')
    logger.setLevel(SYSINFO)
    handler = logging.StreamHandler()
    logger.addHandler(handler)
    formatter = logging.Formatter(MSG_FORMAT, DATE_FORMAT)
    # don't print exception information to stderr
    formatter.formatException = lambda exc_info: ''
    handler.setFormatter(formatter)

    categories = set()
    categoryFilter = logging.Filter('root')
    logfileCreated = False
    rotatingFileHandler = None

    setLevel = handler.setLevel

    class SessionRotatingFileHandler(logging.handlers.RotatingFileHandler):
        """Handler for logging to a set of files, which switches from one file
        to the next every new session."""

        def __init__(self, filename, backupCount=0):
            self.fileExists = os.path.exists(filename)
            logging.handlers.BaseRotatingHandler.__init__(self, filename, 'a',
                                                 'utf-8', 0)
            self.backupCount = backupCount

        def shouldRollover(self, record):
            if not Log.logfileCreated:
                Log.logfileCreated = True
                if self.fileExists:
                    return True
            return False

    @staticmethod
    def _update_extra(kwargs, category):
        """Update `extra` dictionary in `kwargs` dictionary with `catset`
        and `catstr` items obtained from `category`. `category` is expected
        to be a string or a tuple of strings."""
        if isinstance(category, basestring):
            catset = set([category])
        else:
            catset = set(category)
        # form `catstr` string with length not larger than CATLEN
        catlen = (Log.CATLEN - len(catset) + 1) / len(catset)
        rem    = (Log.CATLEN - len(catset) + 1) % len(catset)
        cuts = []
        for i,cat in enumerate(catset):
            if len(cat) < catlen:
                rem += catlen - len(cat)
                cuts.append(cat[:catlen])
                continue
            add = rem / (len(catset) - i)
            cuts.append(cat[:catlen + add])
            rem -= add
        catstr = ','.join(cuts)
        catdict = {'catset': catset, 'catstr': catstr}
        if 'extra' not in kwargs:
            kwargs['extra'] = catdict
        else:
            kwargs['extra'].update(catdict)

    @staticmethod
    def configFilter(categories):
        """Pass only log messages whose `category` attribute belong to the
        `categories` iterable."""
        Log.categories = set(categories)
        def filter_(record):
            if record.levelno >= logging.WARNING:
                return True
            if Log.categories.intersection(record.catset):
                return True
            return False
        Log.categoryFilter.filter = filter_
        Log.handler.addFilter(Log.categoryFilter)

    @staticmethod
    def resetFilter():
        """Remove filter added by `Log.configFilter`."""
        Log.categories = set()
        Log.handler.removeFilter(Log.categoryFilter)

    @staticmethod
    def configFormatter(format):
        """Change the format string to include the fields in
        `format` iterable in specified order."""
        try:
            fields = map(Log.FORMAT_DICT.__getitem__, format)
        except KeyError, e:
            raise ValueError("invalid format string: %s" % e.args[0])
        Log.formatter = logging.Formatter(' - '.join(fields))
        # don't print exception information to stderr
        Log.formatter.formatException = lambda exc_info: ''
        Log.handler.setFormatter(Log.formatter)

    @staticmethod
    def resetFormatter():
        """Reset to the default formatter."""
        Log.formatter = logging.Formatter(Log.MSG_FORMAT, Log.DATE_FORMAT)
        # don't print exception information to stderr
        Log.formatter.formatException = lambda exc_info: ''
        Log.handler.setFormatter(Log.formatter)

    @staticmethod
    def configRotatingFileHandler(filename, backupCount=0):
        Log.rotatingFileHandler = Log.SessionRotatingFileHandler(
            filename, backupCount)
        Log.rotatingFileHandler.setLevel(Log.SYSINFO)
        formatter = logging.Formatter(Log.MSG_FORMAT_FULL, Log.DATE_FORMAT)
        Log.rotatingFileHandler.setFormatter(formatter)
        Log.logger.addHandler(Log.rotatingFileHandler)

    @staticmethod
    def resetRotatingFileHandler():
        if Log.rotatingFileHandler is not None:
            Log.logger.removeHandler(Log.rotatingFileHandler)

    @staticmethod
    def sysinfo(category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        Log.logger.log(Log.SYSINFO, msg, *args, **kwargs)

    @staticmethod
    def debug(category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        Log.logger.debug(msg, *args, **kwargs)

    @staticmethod
    def info(category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        Log.logger.info(msg, *args, **kwargs)

    @staticmethod
    def warning(category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        Log.logger.warning(msg, *args, **kwargs)

    @staticmethod
    def error(category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        Log.logger.error(msg, *args, **kwargs)

    @staticmethod
    def critical(category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        Log.logger.critical(msg, *args, **kwargs)

    @staticmethod
    def exception(category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        kwargs['exc_info'] = True
        Log.logger.error(msg, *args, **kwargs)

    @staticmethod
    def log(level, category, msg, *args, **kwargs):
        Log._update_extra(kwargs, category)
        Log.logger.log(level, msg, *args, **kwargs)

    @staticmethod
    def log_system_information():
        Log.sysinfo('uname', '%s %s' % (os.uname()[0], os.uname()[2]))
        Log.sysinfo('python', sys.version[0:5])
        xlib_version = Xlib.__version_string__ if XLIB_PRESENT else 'no'
        Log.sysinfo('xlib', xlib_version)
        Log.sysinfo(PROG_NAME, VERSION_NAME)

class ConfigError(Exception):
    """Base class for Config exceptions."""
    pass

class ParseError(ConfigError):
    """Wrapper for all exceptions of ConfigParser module."""

class UnrecognizedOption(ConfigError):
    """Configuration file contains undefined option name."""

    def __init__(self, option):
        self.option = option

    def __str__(self):
        return "option '%s' is unrecognized" % self.option

class UnrecognizedSection(ConfigError):
    """Configuration file contains undefined section name."""

    def __init__(self, section):
        self.section = section

    def __str__(self):
        return "section '%s' is unrecognized" % self.section

class MissingOption(ConfigError):
    """Configuration file misses some option."""

    def __init__(self, option):
        self.option = option

    def __str__(self):
        return "option '%s' is missing" % self.option

class MissingSection(ConfigError):
    """Configuration file misses some section."""

    def __init__(self, section):
        self.section = section

    def __str__(self):
        return "section '%s' is missing" % self.section

class OptionValueError(ConfigError):
    """Raised when option has invalid value."""

    def __init__(self, section, option, value, values=None, message=None):
        """Either possible `values` or `message` must be specified"""
        self.section = section
        self.option = option
        self.value = value
        self.values = values
        self.message = message

    def __str__(self):
        msg = "in '%s' section: invalid value of '%s' option: %s" % \
              (self.section, self.option, self.value)
        if self.values is not None:
            return  msg +  ". The value should be one of the following %s" % \
                   str(self.values)[1:-1]
        elif self.message is not None:
            if self.message != '':
                msg += ' (' + self.message + ')'
            return msg
        else:
            raise TypeError("Either values or message must be specified")

class Config(object):
    """Object that reads, parses, and writes a configuration file."""

    @staticmethod
    def set_filename(filename):
        Config._filename = filename

    @staticmethod
    def use_defaults():
        """Set `Config` attributes to default values."""
        Config._parse_options(Config._get_defaults(), Config._get_valid_opts())

    @staticmethod
    def get_default_config():
        return Config._config_str % Config._get_defaults()

    @staticmethod
    def parse(rules, history):
        """
        Parse the configuration file, assign option values to the
        corresponding `Config` attributes. Call `parse()` methods of
        `rules` and `history` objects at the end.
        """
        config = RawConfigParser(OrderedDict(), OrderedDict)
        try:
            config.read(Config._filename)
        except ConfigParser.Error, cpe:
            raise ParseError(str(cpe))
        else:
            for sec in ('SETTINGS', 'RULES'):
                if not config.has_section(sec):
                    raise MissingSection(sec)
            items = dict(config.items('SETTINGS'))
            Log.info('config', 'option values: %s', str(items))
            options = set(items.keys())
            keys = set(Config._defaults.keys())
            missing = keys.difference(options)
            unrecognized = options.difference(keys)
            for opt in missing:
                raise MissingOption(opt)
            for opt in unrecognized:
                raise UnrecognizedOption(opt)
            Config._parse_options(items, Config._get_valid_opts())
            rules.parse()
            if Config.history_length != 0:
                if not config.has_section('HISTORY'):
                    raise MissingSection('HISTORY')
                history.parse(config.items('HISTORY'))

    @staticmethod
    def write(config=None):
        """Write a default configuration file if `config` is None.
        Otherwise write a `config` string to the configuration file."""
        if config is None:
            config = Config.get_default_config()
        rewrite = os.path.exists(Config._filename)
        try:
            if not rewrite:
                f = open(Config._filename, 'w')
            else:
                dir_ = os.path.dirname(Config._filename)
                tempfilename = os.path.join(dir_,
                    Config._filename + '.%s~' % PROG_NAME)
                f = open(tempfilename, 'w')
            f.write(config)
            f.flush()
            os.fsync(f.fileno())
            if rewrite:
                os.rename(tempfilename, Config._filename)
        except (IOError, OSError): raise
        else: Log.info('config', 'config written')
        finally:
            f.close()
            if rewrite and os.path.exists(tempfilename):
                os.remove(tempfilename)

    @staticmethod
    def _get_defaults():
        return dict([(k, Config._defaults[k][0]) for k in Config._defaults])

    @staticmethod
    def _get_valid_opts():
        return dict([(k, Config._defaults[k][1]) for k in Config._defaults])

    @staticmethod
    def read():
        try:
            f = open(Config._filename, 'r')
            config = f.read()
        except IOError: raise
        else: return config
        finally: f.close()

    SECRE = r"""
        (?P<section>^\[%s\].*?)         # a section header and a body
        (?=\s*                          # don't include whitespaces
        (?: (?:^\[[^]]+\])              # a new section
        | \Z) )                         # or the end of the string
        """

    @staticmethod
    def find_section(section, config):
        """Return a tuple containing the start and end positions of `section`
        in `config` string. If not found `MissingSection` is raised."""
        secre = re.compile(Config.SECRE % section,
                           re.DOTALL | re.MULTILINE | re.VERBOSE)
        m = secre.search(config)
        if m is None:
            raise MissingSection(section)
        else:
            return m.span()

    @staticmethod
    def write_section(secname, secbody):
        config = Config.read()
        start, end = Config.find_section(secname, config)
        header = '[' + secname + ']\n'
        newconfig = config[:start] + header + secbody + config[end:]
        Config.write(newconfig)

    @staticmethod
    def _parse_options(options, valid_opts):
        for opt in options:
            value = options[opt]
            possible = valid_opts[opt]
            if isinstance(possible, tuple):
                if value in possible:
                    setattr(Config, opt, value)
                    continue
                else:
                    raise OptionValueError('SETTINGS', opt, value, possible)
            elif callable(possible):
                setattr(Config, opt, possible(value))
            elif possible is None:
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                setattr(Config, opt, value)
                continue
            else:
                raise TypeError(type(possible))

    def _parse_modifiers(modifier_str):
        mods = modifier_str.split('+')
        for i, mod in enumerate(mods):
            if mod in ('Control', 'Shift'): pass
            elif mod == 'Alt': mods[i] = 'Mod1'
            elif mod == 'Super': mods[i] = 'Mod4'
            else:
                raise OptionValueError("SETTINGS", 'modifiers', modifier_str,
                    message="invalid modifier name '%s'" % mod)
        return mods

    def _parse_title_format(title_format):
        """Check title_format contains not more than one %t and %s"""
        if title_format.count('%t') > 1 or title_format.count('%s') > 1:
            raise OptionValueError("SETTINGS", "title_format", title_format,
                message="only one occurance of %t or %s is possible")
        return title_format

    def _parse_history_length(history_length):
        try:
            hist_len = int(history_length)
        except ValueError:
            raise OptionValueError("HISTORY", "history_length", history_length,
                                   message="")
        if(hist_len < 0):
            raise OptionValueError("HISTORY", "history_length", history_length,
                                   message="the value must be positive")
        return hist_len

    _defaults = {
        'keyboard_layout'  : ('QWERTY', ('QWERTY', 'Dvorak')),
        'modifiers'        : ('Super', _parse_modifiers),
        'group_windows_by' : ('AWN', ('AWN', 'Group', 'None')),
        'title_format'     : ('%t   /%s/', _parse_title_format),
        'history_length'   : (15, _parse_history_length),
        'desktop_action'   : ('SwitchDesktop', ('SwitchDesktop', 'MoveWindow',
                                              'None')),
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
     # Possible values:
     #  - AWN -- two windows belong to the same group if they have equal awns.
     #  - Group -- group windows as window manager normally does.
     #  - None -- do not group at all.
     group_windows_by = %(group_windows_by)s

     # Change window titles, so they include the corresponding shortcuts.
     # %%t and %%s are replaced by the window title and the shortcut
     # accordingly. Only one occurance of %%t or %%s in title_format is
     # possible. Set to None to deny modifying the window titles.
     title_format = %(title_format)s

     # What to do if the window which is to be activated is not on the
     # current desktop.
     # Possible values:
     #  - SwitchDesktop -- switch to the desktop which the window is on.
     #  - MoveWindow -- move the window to the current desktop.
     #  - None -- just activate the window (actual behaviour may differ
     # with different window managers).
     desktop_action = %(desktop_action)s

     # History of shortcuts is used to avoid them floating between
     # different windows across the sessions.
     # Set the value of history_length to 0 to disable the history feature.
     # It's recommended to set the option to slightly larger value than the
     # number of windows you use regularly but not much larger than 20 (because
     # of the limit of 27 latin letters).
     history_length = %(history_length)d

     [HISTORY]

     [RULES]
     # This section specifies rules according to which window classes or names
     # (titles) are transformed to abstract window names (AWNs). When a new
     # window appears the program tries out the rules (from top to bottom)
     # until it founds out one that matches a window property. If no
     # sutable rule is found the window class will be assigned to the AWN.

     # AWNs are used to determine window shortcuts.  For example, if AWN is
     # 'xterm' than keybinding will more likely 'mod+x'. If it is already
     # assigned to another window or is used by an another program the next
     # keybinding to try out will be 'mod+t'. It sorts out the alphabetical
     # characters of AWN until it finds one whose corresponding key is not
     # grabbed. If it turns out there is no such a key, the window will be
     # binded to any different unused key.

     # Format:
     # {title|class}.regex = awn

     # If regex matches a title or a class (depending on what is specified) the
     # leftmost occurence of it is replaced with awn. awn may contain
     # backreferences, e.g. \\1 is replaced with the first group of
     # regex. regex matching is case insensetive.

     # Examples:

     # set awn to firefox for all the windows whose titles end with firefox
     # title..*firefox$ = firefox

     # remove prefix gnome- from window classes
     # class.gnome-(.*) = \\1

     # transorm classes icecat, iceweasel, and icedove to awns cat, weasel, and
     # dove respectively
     # class.ice(cat|weasel|dove) = \\1
     """
    )

class History(OrderedDict):
    """
    Extend OrderedDict. Contain (awn, key) pairs. Number of these pairs is
    controlled by `Config.history_length` value.
    """

    def parse(self, history):
        Log.debug('config', 'parsing history...')
        history.reverse()
        for item in history:
            if len(item[1]) == 1 and item[1].isalpha():
                self[item[0]] = item[1]
            else:
                Log.warning('config', 'shortcut should be an alphabetical' +
                "character: '%s', ignored", item[1])
        self.truncate()
        Log.info('config', 'parsed history: %s', str(self))

    def update_item(self, awn, base_key):
        """Update history with a new window or its new base key."""
        if awn in self:
            del self[awn]
        self[awn] = base_key
        self.truncate()

    def write(self):
        """Rewrite a configuration file with the current history."""
        items = []
        for awn in self:
            if awn != '':
                items.insert(0, awn + ' = ' + self[awn])
        body = '\n'.join(items)
        try:
            Config.write_section('HISTORY', body)
        except (IOError, OSError, MissingSection), e:
            Log.exception('config',
                          'when writing the history: %s' % str(e))
        else:
            Log.info('config', 'history written: %s' % str(self))

    def truncate(self):
        """Leave `Config.history_length` last entries in the history."""
        for i in range(len(self) - Config.history_length):
            self.popitem(last=False)

class Rules(list):
    """Extend list. Contain tuples (type, regex, awn)."""

    def parse(self):
        """Read a configuration file and parse RULES section."""
        Log.debug('config', 'parsing rules...')
        try:
            config = Config.read()
            start, end = Config.find_section('RULES', config)
        except (IOError, MissingSection), e:
            Log.exception('config', 'when reading RULES: %s' % str(e))
            return
        rules = []
        bodylines = config[start:end].splitlines()[1:]
        for line in bodylines:
            stripline = line.lstrip()
            if stripline == '' or stripline.startswith('#'):
                continue
            h1, s1, t1 = map(str.strip, line.rpartition('='))
            h2, s2, t2 = map(str.strip, line.rpartition(':'))
            opt, awn = (h1, t1) if len(h1) > len(h2) else (h2, t2)
            if opt == '':
                raise OptionValueError('RULES', opt, awn, message='')
            if opt.startswith('class.'):
                type_ = Window.CLASS
            elif opt.startswith('title.'):
                type_ = Window.NAME
            else:
                raise OptionValueError('RULES', opt, awn,
                    message="option should start with 'class.' or 'title.'")
            regex = opt[6:]
            try:
                pattern = re.compile(regex, re.I)
            except re.error, e:
                raise OptionValueError("RULES", opt, awn,
                    message="invalid regex: %s: %s" % (str(e), regex))
            else:
                self.append((type_, pattern, awn))
                rules.append((type_, regex, awn)) # just for debugging
        Log.info('config', 'parsed rules: %s', str(rules))

    def get_awn(self, winclass, winname):
        """Transofrm winclass or winname to awn according to the rules.
        Return winclass if no rule matches."""
        for ruleno, rule in enumerate(self):
            type_, regex, awn = rule
            name = winclass if type_ == Window.CLASS else winname
            m = regex.match(name)
            if m is None:
                continue
            else:
                try:
                    awn = regex.sub(awn, name, 1)
                except re.error, e:
                    Log.exception('config', '%s: awn = %s ' % (str(e), awn))
                    return winclass
                else:
                    return awn
        return winclass

class KeyboardLayout(object):
    """Object holding information about the order of keys of different keboard
    layouts"""

    dvorak = '\',.pyfgcrlaoeuidhtns;qjkxbmwvz'
    qwerty = 'qwertyuiopasdfghjkl;zxcvbnm,./'

    def __init__(self, layout="QWERTY"):
        if layout == "DVORAK":
            # dvorak layout with 3 rows by 10 characters
            self.keys = self.dvorak
        elif layout == "QWERTY":
            # qwerty layout with 3 rows by 10 characters
            self.keys = self.qwerty
        else:
            raise ValueError("Unknown keyboard layout name: %s" % layout)
        self.indexes = dict(zip(self.keys, range(len(self.keys))))

class ShortcutGenerator(object):
    """Class which generates shortcuts for specified windows taking into
    account windows' and window list's information."""

    def __init__(self):
        self.layout = KeyboardLayout(Config.keyboard_layout)

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

    def new_shortcut(self, window, window_list, history):
        """Return a new shortcut generated for `window`.

        Return None if no new shortcut is possible. `wid` and `gid` attributes
        of `window` must be initialised before the method call.
        """
        shortcuts = window_list.get_group_shortcuts(window.gid)
        if not shortcuts:               # first shortcut for the group
            allbases = window_list.get_all_bases().union(self._forbidden_bases)
            if window.awn in history:
                base = history[window.awn]
                if base not in allbases:
                    return base
            # prefer shortcuts not present in the history
            bases = allbases.union(set(history.values()))
            base = self._new_base(window.awn, bases)
            if base is not None:
                return base
            else:
                return self._new_base(window.awn, allbases)
        else:                           # the group already has its base key
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

    def get_all_awns(self):
        """Return a set of awns of the window list."""
        return set([win.awn for win in self])

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
    - `klass`: window class
    - `shortcut`: is represented by a string of length one or two (e.g. 'a' or
      'bn', where 'a' is the base key, 'b' is the prefix, and 'n' is the
      suffix).
    """

    CLASS = 0
    NAME = 1

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

    def __str__(self):
        return str(self.__dict__)

class BadWindow(Exception):
    """Wrapper for Xlib's BadWindow exception"""

    def __init__(self, wid):
        self.wid = wid

    def __str__(self):
        return "Bad window with id=%s" % hex(self.wid)

class ConnectionClosedError(Exception):
    """Wrapper for Xlib's ConnectionClosedError exception."""

class Xtool(object):
    """Wrapper for Xlib related methods"""

    @staticmethod
    def connect(displaystr=None):
        Xtool._display = Xlib.display.Display(displaystr)
        Xtool._root = Xtool._display.screen().root
        Xtool._root.change_attributes(event_mask=Xlib.X.KeyPressMask |
            Xlib.X.KeyReleaseMask | Xlib.X.PropertyChangeMask)
        Xtool._init_mod_keycodes()

    # keyboard related methods

    @staticmethod
    def grab_key(keycode, mask, onerror=None):
        Xtool._root.grab_key(keycode, mask,
            1, Xlib.X.GrabModeAsync, Xlib.X.GrabModeAsync, onerror=onerror)
        Xtool._root.grab_key(keycode, mask | Xlib.X.Mod2Mask,
            1, Xlib.X.GrabModeAsync, Xlib.X.GrabModeAsync, onerror=onerror)
        Xtool._root.grab_key(keycode, mask | Xlib.X.LockMask,
            1, Xlib.X.GrabModeAsync, Xlib.X.GrabModeAsync, onerror=onerror)
        Xtool._root.grab_key(keycode, mask | Xlib.X.Mod2Mask | Xlib.X.LockMask,
            1, Xlib.X.GrabModeAsync, Xlib.X.GrabModeAsync, onerror=onerror)

    @staticmethod
    def ungrab_key(keycode, mask, onerror=None):
        Xtool._root.ungrab_key(keycode, mask, onerror=onerror)
        Xtool._root.ungrab_key(keycode, mask | Xlib.X.Mod2Mask,
                               onerror=onerror)
        Xtool._root.ungrab_key(keycode, mask | Xlib.X.LockMask,
                               onerror=onerror)
        Xtool._root.ungrab_key(keycode, mask | Xlib.X.Mod2Mask |
                               Xlib.X.LockMask, onerror=onerror)

    @staticmethod
    def grab_keyboard():
        Xtool._root.grab_keyboard(1, Xlib.X.GrabModeAsync,
                                  Xlib.X.GrabModeAsync, Xlib.X.CurrentTime)

    @staticmethod
    def ungrab_keyboard():
        Xtool._display.ungrab_keyboard(Xlib.X.CurrentTime)
        # after the keyboard is ungrabbed no release event
        # will come, so forget all pressed keys
        Xtool._pressed_keys.clear()

    @staticmethod
    def sync():
        Xtool._display.sync()

    @staticmethod
    def get_keycode(key, use_keysym=False):
        # Since keysyms are backward compatible with ASCII we can use ord()
        # instead of XK.string_to_keysym() to avoid translation of
        # non-alphabetical symbols to keysym strings previosly
        keysym = Xlib.XK.string_to_keysym(key) if use_keysym else ord(key)
        return Xtool._display.keysym_to_keycode(keysym)

    @staticmethod
    def get_key(keycode):
        return Xlib.XK.keysym_to_string(
            Xtool._display.keycode_to_keysym(keycode, 0))

    @staticmethod
    def _init_mod_keycodes():
        Xtool._mod_keycodes = set(
            [
                Xtool.get_keycode('Shift_L', True),
                Xtool.get_keycode('Shift_R', True),
                Xtool.get_keycode('Control_L', True),
                Xtool.get_keycode('Control_R', True),
                Xtool.get_keycode('Alt_L', True),
                Xtool.get_keycode('Alt_R', True),
                Xtool.get_keycode('Super_L', True),
                Xtool.get_keycode('Super_R', True)
            ])
        if 0 in Xtool._mod_keycodes:
            Xtool._mod_keycodes.remove(0)

    @staticmethod
    def is_mofifier(keycode):
        return keycode in Xtool._mod_keycodes

    @staticmethod
    def _is_key_pressed(keycode):
        bitmap = Xtool._display.query_keymap()
        return bitmap[keycode / 8] & (1 << (keycode % 8))

    # window reltaed methods

    @staticmethod
    def _atom(name):
        return Xtool._display.intern_atom(name)

    @staticmethod
    def get_window_list():
        return Xtool._root.get_full_property(
            Xtool._atom("_NET_CLIENT_LIST"), Xlib.Xatom.WINDOW).value

    @staticmethod
    def _get_window(wid):
        return Xtool._display.create_resource_object("window", wid)

    @staticmethod
    def get_window_name(wid):
        win = Xtool._get_window(wid)
        try:
            name = win.get_full_property(Xtool._atom("_NET_WM_NAME"),
                                         Xtool._atom('UTF8_STRING'))
        except Xlib.error.BadWindow:
            raise BadWindow(wid)
        if name:
            return unicode(name.value, 'utf-8')
        else:
            return unicode(win.get_wm_name())

    @staticmethod
    def get_window_application(wid):
        try:
            cls = Xtool._get_window(wid).get_wm_class()
        except Xlib.error.BadWindow:
            raise BadWindow(wid)
        if cls:
            return cls[0]
        else:
            return ''

    @staticmethod
    def get_window_class(wid):
        try:
            cls = Xtool._get_window(wid).get_wm_class()
        except Xlib.error.BadWindow:
            raise BadWindow(wid)
        if cls:
            return cls[1]
        else:
            return ''

    @staticmethod
    def get_window_group_id(wid):
        hints = Xtool._get_window(wid).get_wm_hints()
        group_id = 0
        if hints:
            group_id = hints.window_group.id
        return group_id

    @staticmethod
    def _set_property(wid, prop, name):
        if not isinstance(name, unicode):
            raise TypeError('an unicode string is required')
        win = Xtool._get_window(wid)
        win.change_property(
            Xtool._atom(prop),
            Xtool._atom('UTF8_STRING'),
            8,
            name.encode('utf-8'),
            mode=Xlib.X.PropModeReplace)

    @staticmethod
    def _send_client_message(wid, msg, data):
        window = Xtool._get_window(wid) if wid is not None else Xtool._root
        event = Xlib.protocol.event.ClientMessage(
            client_type=Xtool._atom(msg),
            window=window,
            data=(32, data))
        Xtool._display.send_event(
            Xtool._root,
            event,
            event_mask=Xlib.X.SubstructureRedirectMask |
                       Xlib.X.SubstructureNotifyMask)

    @staticmethod
    def set_window_name(wid, name):
        Xtool._set_property(wid, '_NET_WM_NAME', name)

    @staticmethod
    def set_window_icon_name(wid, name):
        Xtool._set_property(wid, '_NET_WM_ICON_NAME', name)

    @staticmethod
    def _get_desktop_number(wid=None):
        if wid is None:
            window = Xtool._root
            message = '_NET_CURRENT_DESKTOP'
        else:
            window = Xtool._get_window(wid)
            message = '_NET_WM_DESKTOP'
        reply = window.get_full_property(Xtool._atom(message),
                                         Xlib.Xatom.CARDINAL)
        if reply is not None:
            return reply.value[0]

    DESKTOP_IGNORE = 0
    DESKTOP_SWITCH_DESKTOP = 1
    DESKTOP_MOVE_WINDOW = 2

    @staticmethod
    def raise_window(wid, desktop_action=DESKTOP_IGNORE):
        if desktop_action == Xtool.DESKTOP_SWITCH_DESKTOP:
            deskno = Xtool._get_desktop_number(wid)
            if deskno is not None:
                Xtool._send_client_message(None, '_NET_CURRENT_DESKTOP',
                    [deskno, Xtool._last_key_event_time, 0, 0, 0])
        elif desktop_action == Xtool.DESKTOP_MOVE_WINDOW:
            deskno = Xtool._get_desktop_number()
            if deskno is not None:
                Xtool._send_client_message(wid, '_NET_WM_DESKTOP',
                                           [deskno, 2, 0, 0, 0])
        elif desktop_action != Xtool.DESKTOP_IGNORE:
            raise ValueError('invalid desktop_action: %d' % desktop_action)
        Xtool._send_client_message(wid, '_NET_ACTIVE_WINDOW',
                                   [2, Xtool._last_key_event_time, 0, 0, 0])

    @staticmethod
    def listen_window_name(wid):
        """Tell Xtool to watch the window name changes. Otherwise
        `window_name_listener.on_window_name_changed()` will not work."""
        Xtool._get_window(wid).change_attributes(
            event_mask=Xlib.X.PropertyChangeMask)

    @staticmethod
    def register_key_listener(key_listener):
        """Register `key_listener` which must have `on_key_press` and
        `on_key_release` methods."""
        Xtool._key_listener = key_listener

    @staticmethod
    def register_window_list_listener(window_list_listener):
        """Register `window_list_listener` which must have
        `on_window_list_changed` method."""
        Xtool._window_list_listener = window_list_listener

    @staticmethod
    def register_window_name_listener(window_name_listener):
        """Register `window_name_listener` which must have
        `on_window_name_changed` method."""
        Xtool._window_name_listener = window_name_listener

    @staticmethod
    def _window_list_changed(event):
        return event.type == Xlib.X.PropertyNotify and \
            event.atom == Xtool._atom("_NET_CLIENT_LIST")

    @staticmethod
    def _window_name_changed(event):
        return event.type == Xlib.X.PropertyNotify and \
            (event.atom == Xtool._atom("_NET_WM_NAME") or
            event.atom == Xtool._atom("WM_NAME"))

    @staticmethod
    def _check_listeners():
        """Check if all listeners are registered before entering event_loop"""
        if not hasattr(Xtool, '_key_listener'):
            raise AttributeError('no key_listener')
        elif not (hasattr(Xtool._key_listener, 'on_key_press') and
                hasattr(Xtool._key_listener, 'on_key_release')):
            raise AttributeError('bad key_listener')
        if not hasattr(Xtool, '_window_list_listener'):
            raise AttributeError('no window_list_listener')
        elif not hasattr(Xtool._window_list_listener, 'on_window_list_changed'):
            raise AttributeError('bad window_list_listener')

    _pressed_keys = set()

    @staticmethod
    def _is_key_press_fake(keycode):
        """Return True if KeyPress event was caused by auto-repeat mode."""
        if keycode in Xtool._pressed_keys:
            return True
        else:
            Xtool._pressed_keys.add(keycode)
            return False

    @staticmethod
    def _is_key_release_fake(keycode):
        """Return True if KeyRelease event was caused by auto-repeat mode."""
        if Xtool.is_mofifier(keycode):
            return False                # modifiers are never auto-repeated
        if not Xtool._is_key_pressed(keycode):
            try:
                Xtool._pressed_keys.remove(keycode)
            except KeyError:
                # some key had been pressed before the keyboard was grabbed
                # and now it is released while the keyboard is still
                # grabbed. Actually this is not a fake event, though ignore it.
                return True
            return False
        return True

    @staticmethod
    def event_loop():
        """Event loop. Before entering the loop all the listeners must be
        registered wih `Xtool.register_xxx_listener()`."""
        Xtool._check_listeners()
        while True:
            try:
                event = Xtool._display.next_event()
                if Xtool._window_list_changed(event):
                    Xtool._window_list_listener.on_window_list_changed()
                elif Xtool._window_name_changed(event):
                    Xtool._window_name_listener.on_window_name_changed(
                        event.window.id)
                elif event.type == Xlib.X.KeyPress:
                    Xtool._last_key_event_time = event.time
                    keycode = event.detail
                    if not Xtool._is_key_press_fake(keycode):
                        Xtool._key_listener.on_key_press(keycode)
                elif event.type == Xlib.X.KeyRelease:
                    Xtool._last_key_event_time = event.time
                    keycode = event.detail
                    if not Xtool._is_key_release_fake(keycode):
                        Xtool._key_listener.on_key_release(keycode)
            except Xlib.error.ConnectionClosedError, e:
                raise ConnectionClosedError(str(e))

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
        return ("can't grab key '%s' with modifier mask %s. It is already " +
        "grabbed by another program.") % (self.shortcut[0], hex(self.modmask))

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
        Xtool.register_key_listener(self._key_listener)

    def _get_modmask(self, modifiers):
        modmask = 0
        for modifier in modifiers:
            if modifier == 'Shift':
                modmask = modmask | Xlib.X.ShiftMask
            elif modifier == 'Control':
                modmask = modmask | Xlib.X.ControlMask
            elif modifier == 'Mod1':
                modmask = modmask | Xlib.X.Mod1Mask
            elif modifier == 'Mod4':
                modmask = modmask | Xlib.X.Mod4Mask
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
        ec = Xlib.error.CatchError(Xlib.error.BadAccess)
        if modifiers is not None:
            keycode = Xtool.get_keycode(shortcut, use_keysym=True)
            if not keycode:
                raise BadShortcut(shortcut)
            modmask = self._get_modmask(modifiers)
            Xtool.grab_key(keycode, modmask, onerror=ec)
            Xtool.sync()
            if ec.get_error():
                raise GrabError(shortcut, self._modmask)
            self._bindings2[(shortcut, modmask)] = callback
        else:
            keycode = Xtool.get_keycode(shortcut[0])
            if not keycode:
                raise BadShortcut(shortcut)
            Xtool.grab_key(keycode, self._modmask, onerror=ec)
            Xtool.sync()
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
            Xtool.ungrab_key(Xtool.get_keycode(shortcut[0]), self._modmask)

    def unbind_all(self):
        """Delete all the keybindings and ungrab related keys."""
        for base in self._bindings:
            Xtool.ungrab_key(Xtool.get_keycode(base), self._modmask)
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
            base_key = Xtool.get_key(keycode)
            if not base_key or base_key not in self._bindings:
                self._initial_state()
                return
            Log.debug('keys', 'base key press: %s', base_key)
            self._last_base = base_key
            Xtool.grab_keyboard()
            # only one shortcut for given base key, call corresponding function
            if len(self._bindings[base_key]) == 1:
                Log.info('keys', "keybinding caught: '%s'",
                    self._bindings[base_key][0][0])
                self._bindings[base_key][0][1]()
                Xtool.ungrab_keyboard()
                self._initial_state()
        # suffix key pressed
        elif self._base_state == self.PRESSED:
                suffix_key = Xtool.get_key(keycode)
                if not suffix_key:
                    self._initial_state()
                    return
                Log.debug('keys', 'suffix press: %s', suffix_key)
                shortcuts = [bind[0] for bind in
                             self._bindings[self._last_base]]
                shortcut = self._last_base + suffix_key
                try:
                    i = shortcuts.index(shortcut)
                except ValueError: pass # unregistered keybinding, ignore it
                else:
                    Log.info('keys', "keybinding caught: '%s'", shortcut)
                    self._bindings[self._last_base][i][1]()
                finally:
                    Xtool.ungrab_keyboard()
                    self._initial_state()

    def on_key_release(self, keycode):
        key = Xtool.get_key(keycode)
        # modifier released
        if Xtool.is_mofifier(keycode):
            Log.debug('keys', 'modifier release, keycode: 0x%x', keycode)
            self._modifier_sate = self.RELEASED
            if self._base_state == self.RELEASED:
                Xtool.ungrab_keyboard()
                self._initial_state()
        # base key released
        elif key == self._last_base:
            Log.debug('keys', 'base key release: %s', key)
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
                Log.info('keys', "keybinding caught: '%s'", shortcut)
                bindings[i][1]()
                if self._modifier_sate == self.RELEASED:
                    Xtool.ungrab_keyboard()
                    self._initial_state()
        # suffix key released
        else:
            Log.debug('keys', 'suffix key release: %s', key)

class WindowManager(object):
    """`WindowManager` tracks changes of the window list, their names, assigns
    the shortcuts to the new windows."""

    def __init__(self, rules, history):
        self._rules = rules
        self._history = history
        self._shortgen = ShortcutGenerator()
        self._keybinder = KeyBinder(Config.modifiers)
        self._windows = WindowList()
        for wid in Xtool.get_window_list():
            self._on_window_create(wid)
        Xtool.register_window_list_listener(self)
        Xtool.register_window_name_listener(self)

    def _bind(self, wid, shortcut):
        if Config.desktop_action == 'SwitchDesktop':
            action = Xtool.DESKTOP_SWITCH_DESKTOP
        elif Config.desktop_action == 'MoveWindow':
            action = Xtool.DESKTOP_MOVE_WINDOW
        else:
            action = Xtool.DESKTOP_IGNORE

        def raise_window(wid=wid, action=action):
            Xtool.raise_window(wid, action)
        self._keybinder.bind(shortcut, raise_window)

    def on_window_list_changed(self):
        old_wids = set([win.wid for win in self._windows])
        current_wids = set(Xtool.get_window_list())
        new_wids = current_wids.difference(old_wids)
        closed_wids = old_wids.difference(current_wids)
        for new_wid in sorted(new_wids):
            Log.debug('windows', 'new window (id=0x%x)', new_wid)
            self._on_window_create(new_wid)
        if closed_wids:
            Log.debug('windows', 'windows closed (ids: %s)' %
                ', '.join(map(hex, closed_wids)))
            self._on_windows_close(sorted(closed_wids))

    def on_window_name_changed(self, wid):
        Log.debug('windows', 'window name changed (id=0%x)', wid)
        win = self._windows.get_window(wid)
        # In some rare cases 'window name changed' event is recieved after
        # 'window closed' event somehow. Check if it has not already been
        # removed from the window list
        if win is not None:
            self._update_window_name(win, win.shortcut)
        else:
            Log.warning('windows', 'name of the window (id=0%x) changed ' +
                        'while it is not in the window list', wid)

    def _on_windows_close(self, wids):
        """Delete the window from the window list and unbind it.

        If the group leader (the first window of the group) was closed, rebind
        all the other windows of the group."""
        wins_closed = self._windows.get_windows(wids)
        for win_closed in wins_closed:
            self._keybinder.unbind(win_closed.shortcut)
            Log.info(('keys', 'windows'), "window '%s' (id=0x%x) was " +
                     "unbinded from '%s'", win_closed.name, win_closed.wid,
                     win_closed.shortcut)
            del self._windows[self._windows.index(win_closed)]
        groups = set([w.gid for w in wins_closed if len(w.shortcut) == 1])
        for group in groups:
            wins = self._windows.get_group_windows(group)
            if len(wins) > 0:
                base_key = wins[0].shortcut[0]
                # rebind all the windows of the group
                for win in wins:
                    self._keybinder.unbind(win.shortcut)
                    win.prev_shortcut, win.shortcut = win.shortcut, None
                for i, win in enumerate(wins):
                    if i == 0: # base key for the group should remain the same
                        win.shortcut = base_key
                        self._bind(win.wid, win.shortcut)
                        Log.info(('keys', 'windows'), "window '%s' (id=0x%x)" +
                                 " was binded to '%s'", win.awn, win.wid,
                                 win.shortcut)
                    else:
                        self._add_shortcut(win)
                    Log.info('keys', 'Rebinding: %s -> %s',
                             win.prev_shortcut, win.shortcut)
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
            window.name = Xtool.get_window_name(window.wid)
            window.klass = Xtool.get_window_class(wid)
        except BadWindow, e:
            Log.exception('windows', str(e))
            return
        window.awn = self._rules.get_awn(window.klass, window.name)
        if Config.group_windows_by == 'Group':
            window.gid = Xtool.get_window_group_id(wid)
        elif Config.group_windows_by == 'AWN':
            window.gid = self._windows.get_group_id(window.awn)
        if not window.gid:
            window.gid = self._windows.get_unique_group_id()
        self._add_shortcut(window)
        Log.info('windows', 'new window attributes: %s' % str(window))
        if window.shortcut:
            if window.awn not in self._windows.get_all_awns():
                self._history.update_item(window.awn, window.shortcut[0])
            self._windows.append(window)
            self._update_window_name(window, window.shortcut)
            Xtool.listen_window_name(window.wid)

    def _add_shortcut(self, window):
        """Generate a new unused shortcut for `window` and add the shortcut to
        the `window`. Set the shortcut to None if all the possible keys are
        grabbed."""
        while True:
            shortcut = self._shortgen.new_shortcut(window, self._windows,
                                                   self._history)
            if not shortcut:
                Log.info(('windows', 'keys'), 'so many windows, so few keys')
                window.shortcut = None
                return
            try:
                self._bind(window.wid, shortcut)
            except GrabError, e:
                Log.info('keys', str(e))
                self._shortgen.forbid_base(shortcut[0])
            else:
                break
        window.shortcut = shortcut
        Log.info(('windows', 'keys'), "window '%s' (id=0x%x) was binded to "
                 "'%s'", window.awn, window.wid, window.shortcut)

    def _update_window_name(self, window, prev_shortcut):
        """Change the window name, so it includes the shortcut."""
        if Config.title_format == 'None':
            return
        try:
            new_name = Xtool.get_window_name(window.wid)
        except BadWindow, e:
            Log.exception('windows', str(e))
            return
        edges = Config.title_format.split('%t')
        start = edges[0].replace('%s', prev_shortcut)
        end = edges[1].replace('%s', prev_shortcut)
        if new_name.startswith(start) and new_name.endswith(end):
            new_name = new_name[len(start):len(new_name)-len(end)]
            if new_name == window.name and prev_shortcut == window.shortcut:
                return                  # window name wasn't changed
        if new_name != window.name:
            Log.info('windows', "window name '%s' (id=0x%x) changed to '%s'",
                    window.name, window.wid, new_name)
        window.name = new_name
        new_name = Config.title_format.replace('%t', new_name)
        new_name = new_name.replace('%s', window.shortcut)
        Xtool.set_window_name(window.wid, new_name)

class SignalHandler:
    """Object holding static methods that implement the program behaviour
    when recieving a signal."""

    history = None

    @staticmethod
    def graceful_exit_handler(sig, frame):
        """Handle graceful exit of the program."""
        Log.info('signals', 'signal recieved: %i', sig)
        graceful_exit(history=SignalHandler.history)

    @staticmethod
    def save_histoy_handler(sig, frame):
        """Save the current history to the configuration file."""
        try:
            SignalHandler.history.write()
        except (IOError, OSError, MissingSection), e:
            Log.exception('config', str(e))

    @staticmethod
    def handle_all(history=None):
        """Handle all the signals defined in `SignalHandler` class"""
        SignalHandler.history = history
        signal.signal(signal.SIGTERM, SignalHandler.graceful_exit_handler)
        signal.signal(signal.SIGHUP, signal.SIG_IGN)
        if SignalHandler.history is not None:
            signal.signal(signal.SIGUSR1, SignalHandler.save_histoy_handler)

def graceful_exit(exit_code=0, history=None):
    """Write history if given, shutdown logging, and exit."""
    if history:
        try:
            history.write()
        except (IOError, OSError, MissingSection), e:
            Log.exception('config', str(e))
    logging.shutdown()
    sys.exit(exit_code)

def parse_options():
    """Parse command line options and return an object holding option
    values."""
    def splitstr(option, opt_str, value, parser, choice):
        splits = value.split(',')
        for s in splits:
            if not s in choice:
                raise optparse.OptionValueError('option %s: invalid field: '
                    '%s (valid fields: %s)' % (opt_str, s, ', '.join(choice)))
        setattr(parser.values, option.dest, splits)
    usage = 'usage: %s [options]' % PROG_NAME
    optparser = optparse.OptionParser(usage=usage,
                                      version=VERSION_NAME,
                                      add_help_option=False,
                                      conflict_handler='resolve'
    )
    optparser.add_option('-h', '--help',
                         action='help',
                         help="Show this help message and exit."
    )
    optparser.add_option('-V', '--version',
                         action='version',
                         help="Show program's version number and exit."
    )
    optparser.add_option('-p', '--print-defaults',
                         dest='print_defaults',
                         action='store_true',
                         default=False,
                         help='Print a default configuration file on the '
                         'standard output.'
    )
    optparser.add_option('-f', '--file',
                         dest='filename',
                         metavar='FILE',
                         default=os.path.expanduser(CONFIG_PATH),
                         help='Specify a configuration file. The default is '
                         '%s.' % CONFIG_PATH
    )
    optparser.add_option('-d', '--display',
                         dest='display',
                         metavar='DISPLAY',
                         type='string',
                         help='Specify X display name to connect to. If not '
                         'given the environment variable $DISPLAY is used.'
    )
    debgroup = optparse.OptionGroup(optparser, 'Debugging Options')
    debgroup.add_option('-v', '--verbose',
                        dest='verbosity',
                        action='count',
                        default=0,
                        help='Provide verbose output. When the option is '
                        'given twice the verbosity increases.'
    )
    debgroup.add_option('-t', '--format',
                        dest='fields',
                        type='string',
                        action='callback',
                        callback=splitstr,
                        callback_args=(Log.FORMAT_DICT.keys(),),
                        metavar='field1[,field2[,...]]',
                        help='Specify which fields to print and their order. '
                        'Possible fields: %s.' % ', '.join(Log.FORMAT_DICT.keys())
    )
    debgroup.add_option('-r', '--filter',
                        dest='categories',
                        type='string',
                        action='callback',
                        callback=splitstr,
                        callback_args=(FIELDS,),
                        metavar='category1[,category2[,...]]',
                        help='Print only those messages that belong to given '
                        'categories (this doesn\'t apply to errors and '
                        'warnings which are always printed). Possible '
                        'categories: %s.' % ', '.join(FIELDS)
    )
    debgroup.add_option('-l', '--log-file',
                        dest='logfile',
                        metavar='FILE',
                        help='Specify a file where to write a log. Options '
                        '-v/--verbose, -t/--format and -r/--filter don\'t '
                        'affect logging to the file.'
    )
    debgroup.add_option('-b', '--backup-count',
                        dest='backup_count',
                        type='int',
                        default=0,
                        metavar='NUMBER',
                        help='How many log files to store not counting the '
                        'current one (specified by -l/--log-file option). '
                        'Default value is %%default. If NUMBER is not 0 '
                        'log files will be rotated on every %s\'s start. '
                        'The name of the oldest file will have the largest '
                        'number at the end (e.g. %s.log.5).' % ((PROG_NAME,)*2)
    )
    optparser.add_option_group(debgroup)
    (options, args) = optparser.parse_args()
    if args:
        optparser.error('no argument was expected: %s' % ', '.join(args))
    if options.verbosity == 0:
        if options.fields is not None:
            optparser.error('option -t/--format: -v/--verbose should'
                            ' be specified')
        if options.categories is not None:
            optparser.error('option -r/--filter: -v/--verbose should '
                            'be specified')
    if options.logfile is None:
        if options.backup_count !=0:
            optparser.error('option -b/--backup-count: -l/--log-file should '
                            'be specified')
    if options.backup_count < 0:
        optparser.error('option -b/--backup-count: value should be 0 or '
                        'larger: %d' % options.backup_count)
    return options

if __name__ == "__main__":
    options = parse_options()
    if options.print_defaults:
        print Config.get_default_config()
        sys.exit(0)
    if options.verbosity == 0:
        Log.setLevel(logging.WARNING)
    elif options.verbosity == 1:
        Log.setLevel(logging.INFO)
    else:
        Log.setLevel(logging.DEBUG)
    if options.fields is not None:
        Log.configFormatter(options.fields)
    if options.categories is not None:
        Log.configFilter(options.categories)
    if options.logfile is not None:
        Log.configRotatingFileHandler(options.logfile, options.backup_count)
        Log.log_system_information()
    if not XLIB_PRESENT:
        Log.error('X', 'can\'t import Xlib, probably python-xlib '
                  'is no installed')
        graceful_exit(1)
    rules = Rules()
    history = History()
    Config.set_filename(options.filename)
    if os.path.exists(options.filename):
        try:
            Config.parse(rules, history)
        except ConfigError, e:
            Log.exception('config', str(e))
            graceful_exit(1)
    else:
        try:
            Config.write()
        except IOError, e:
            Log.exception('config', str(e))
            graceful_exit(1)
        else:
            Config.use_defaults()
    try:
        Xtool.connect(options.display)
    except Xlib.error.DisplayError, e:
        Log.exception('X', str(e))
        graceful_exit(1)
    WindowManager(rules, history)       # everything starts here
    SignalHandler.handle_all(history)
    try:
        Xtool.event_loop()              # and continues here
    except ConnectionClosedError, e:
        Log.exception('X', str(e))
        graceful_exit(1, history)
