from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError

import logging
logger  = logging.getLogger("pyplyne.parser")
import os,sys

class HierarchicalConfigParser(object):
    def __init__(self, files, defaults = {}):
        self._files = files
        self._parsers = []
        self._paths = {}
        self.defaults = defaults
        for _file in files:
            _dflts = {'here':os.path.dirname(os.path.abspath(_file)),
                }
            _dflts.update(defaults)
            parser = SafeConfigParser(_dflts)
            parser.read([_file])
            self._parsers.append(parser)
            self._paths[parser] = os.path.dirname(os.path.abspath(_file))

    @property
    def path_hierarchy(self):
        return [self._paths[parser] for parser in reversed(self._parsers) ]
        
    def sections(self):
        secs = []
        for parser in self._parsers:
            secs.extend(parser.sections())
        return list(set(secs))

    def get(self, section, option, raw=False, vars=None):
        for parser in reversed(self._parsers):
            try:
                return  parser.get(section, option, raw=raw, vars= vars)
            except NoOptionError:
                pass
                
        raise NoOptionError
        
    def get_tuples(self, section, option, raw=False, vars=None):
        ret = []
        for parser in reversed(self._parsers):
            try:
                val = parser.get(section, option, raw=raw, vars = vars)
            except (NoOptionError, NoSectionError):
                continue
            if val:
                ret.append((self._paths[parser], val))
                
        return ret
        
    def getpath(self, section, option, raw=False, vars=None):
        for parser in reversed(self._parsers):
            if vars is None:
                vars = {}
            #vars['here'] = self._paths[parser]
            val = parser.get(section, option, raw=raw, vars= vars)
            if val:
                if not val.startswith("/"):
                    return os.path.join(self._paths[parser], val)
                return val
        return None

    def getpaths(self, section, option, raw=False, vars=None):
        for parser in reversed(self._parsers):
            if vars is None:
                vars = {}
            vars['here'] = self._paths[parser]
            vars['target']
            val = parser.get(section, option, raw=raw, vars= vars)
            if val:
                return [ (_file if not _file.startswith("/") else os.path.join(self._paths[parser], _file)) for _file in val.split()]
        return None


    def write(self, buf):
        for parser in reversed(self._parsers):
            _ln = "Configuration file: %s\n" % self._files[self._parsers.index(parser)]
            buf.write("\n" + ("#" * len(_ln)) +"\n")
            buf.write(_ln)
            buf.write("here = %s\n" % self._paths[parser])
            buf.write("#" * len(_ln) +"\n\n")
            parser.write(buf)
                
    def pretty_print(self, buf):
        sections = self.sections()
        default_path = self._paths[self._parsers[0]]
        def print_sec(sec):
            print >> buf, "\n[%s]" % sec
            keys = self.options(sec)
            for key in keys:
                values = self.get_tuples(sec, key)

                if len(values) > 1:
                    print >> buf, "%20s = %s\n" % (key,  "\\\n".join ( [ ( ("%s%s     (here=%s)" % (" "*23, pair[1],pair[0]) ) if pair[0] == default_path else "\t%s" % pair[1]) for pair in values ]))
                else:
                    if (values[0][0] == default_path):
                        print >> buf, "%20s = %s" % (key, values[0][1])
                    else:
                        print >> buf, "%20s = %s     (here=%s)" % (key, values[0][1], values[0][0])

        #print_sec("DEFAULT")
        for sec in sections:
            print_sec(sec)

    def has_option(self, section, option):
        for parser in self._parsers:
            if parser.has_option(section, option):
                return True
        return False
        
            
    def has_section(self, section):
        for parser in self._parsers:
            if parser.has_section(section):
                return True
        return False
        
    def options(self, section):
        keys = []
        for parser in reversed(self._parsers):
            if parser.has_section(section):
                for k in parser.options(section):
                    if k not in keys:
                        keys.append(k)
        return keys
            
    def items(self, section, raw=False, vars=None):
        itms = []
        _vars = self.defaults.copy()
        _vars.update(vars or {})
        for parser in reversed(self._parsers):
            try:
#                for key,val in parser.items(section, raw=raw, vars=vars):
                for key in parser._sections[section].keys():
                    if key != "__name__":
                        val = parser.get(section, key, raw = raw, vars = _vars)
                        if key not in [i[0] for i in itms]: # only take value highest in the stack
                            itms.append((key, val))
            except (NoSectionError, KeyError):
                pass
        return itms
