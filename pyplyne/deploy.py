#!/usr/bin/env python

from ConfigParser import SafeConfigParser, NoSectionError, NoOptionError
from mako.lookup import TemplateLookup, Template

import shutil
import os, sys
import subprocess
import random
import logging
import string
import shlex
import distutils.dir_util

from cStringIO import StringIO
logger = logging.getLogger("pyplyne")

def _make_dir(dest, path):
    _pths = path.split(os.path.sep)
    for i,p in enumerate(_pths):
        _pth = os.path.join(dest, *_pths[0:i+1] )
        logger.log(5,"Checking path %s", _pth)
        if not os.path.exists(_pth):
            logger.info("Creating directory %s", _pth)
            os.mkdir(_pth )

logging.addLevelName(logging.INFO+5, "INFO(stderr)")

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
            val = parser.get(section, option, raw=raw, vars= vars)
            if val:
                return val
        return None
        
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

class DeploymentException(Exception):
    def __init__(self, message, underlying = None):
        Exception.__init__(self)
        self.message = message
        self.underlying = underlying

    def __str__(self):
        if self.underlying:
            return super(DeploymentException, self).__str__() + "%s. Underlying Error: %s" % (self.message, self.underlying)
        return super(DeploymentException, self).__str__() + "%s" % self.message

class DeploymentAborted(DeploymentException):
    pass
    
class DeployerBase(object):
    commands = ("deploy","test","update","info")

    def __init__(self, options, target = None):
        self.options = options
        if os.path.isdir(options.config):
            options.config = os.path.join(options.config, "deployment.ini")
        else:
            options.config =  os.path.abspath(options.config)

        _config = options.config
        configs = [_config]
        _parsers = []
        while True:
            _parser = SafeConfigParser()
            _parsers.append(_parser)
            _parser.read([_config])
            
            logger.info("Reading deployment file %s", _config)
            if _parser.has_option("environment","base"):
                _base = _parser.get("environment","base", None)
                if not _base.startswith("/"):
                    _base = os.path.abspath(os.path.join(os.path.dirname(_config), _base))
                if os.path.exists(_base):
                    _config = _base
                    configs = [_base] + configs
                else:
                    break
            else:
                break

        del _config, _parser

        self.dryrun = options.dryrun
        self.dependencies = configs
        self.target = target
        self.deployment = _parsers[0].get("environment","deployment")

        self.parser  =  HierarchicalConfigParser(configs, dict(target = target, deployment = self.deployment))
        #parser = SafeConfigParser()
        #parser.read(configs)
        #self.parser = parser
        
        self.environment = dict(self.parser.items("environment"))
        self.replacements = dict(self.parser.items("replace"))
        self.replacements['target'] = target
        self.replacements['deployment'] = self.deployment

        self.logger = logging.getLogger("pyplyne.deployer")

    def valid_commands(self):
        for cmd in self.commands:
            yield cmd
        for cls in self.__class__.__mro__:
            for k,v in cls.__dict__.iteritems():
                for command in self.commands:
                    if k.startswith(command + "_") and callable(getattr(self, k)):
                        yield k


    def perform_command(self, command, args):
        if command in self.valid_commands():
            getattr(self, command)( *args)
        else:
            print "command not in %s" % list(self.valid_commands())

    def info(self):
        self.parser.pretty_print(sys.stdout)
        import pprint

        print "\n\nVariable replacements\n"
        pprint.pprint(self.replacements)
        
    def deploy(self, test = False):
        tasks = [ "dirs", "files", "templates", "run_scripts"]
        self.logger.warn("=" * 60)
        self.logger.warn("Starting Deployment procedure using configuration: %s" % self.deployment)
        self.logger.warn("Target path: %s" % self.target)
        self.logger.warn("=" * 60)
        self._run_tasks(tasks)

    def update(self, test = False):
        tasks = [ "dirs", "files", "templates", "run_scripts"]
        self.logger.warn("=" * 60)
        self.logger.warn("Starting update procedure using configuration: %s" % self.deployment)
        self.logger.warn("Target path: %s" % self.target)
        self.logger.warn("=" * 60)
        self._run_tasks(tasks, test)
        

    def test(self, test = True):
        self.deploy( test = True)

    def _run_tasks(self, tasks, test = False):
        for task_name in tasks:
            if self.options.stepwise:               
                answer = raw_input("%sNext Step: %s. Proceed?" % ( "TEST! " if test else "", task_name))
                if not answer.lower().startswith("y"):
                    raise DeploymentAborted()

            task = getattr(self, "deploy_" + task_name)
            self.logger.info("")
            self.logger.info("Running task %s", task_name)
            task(test = test)

    def _run_command(self, cwd, cmdline, test = False, **kwargs):
        try:
            self._internal_run_command(cwd,cmdline, test = test, **kwargs)
        except DeploymentException:
            raise
        except Exception as e:
            raise
            #raise DeploymentException("Runnning External Command failed", underlying=e)
            
    def _internal_run_command(self, cwd, cmdline, test = False, **kwargs):
        self.logger.info("** > %s", cmdline if isinstance(cmdline,basestring) else  " ".join([ (str(s) if not " " in s else ("\"%s\"" % s))  for s in cmdline]))
        if not test:
            if kwargs.get('shell')==True and not isinstance(cmdline, basestring):
                cmdline = " ".join(cmdline)

                
            stderr = StringIO()
            process = subprocess.Popen(cmdline , stdin = subprocess.PIPE,
                                       stdout = subprocess.PIPE, stderr = subprocess.STDOUT, cwd = cwd, **kwargs )


            while process.poll() == None:
                line = process.stdout.readline()
                if line == '':
                    break;
                self.logger.info(line.rstrip())
            
            if process.returncode > 1 :
                self.logger.error("Process returned %s", process.returncode)
                print stderr.getvalue()
                raise DeploymentException("An error occurred in subprocess '%s'. Please see the logs." % " ".join(cmdline))
            else:
                self.logger.info("Process returned %s", process.returncode)
            errtxt = stderr.getvalue()
            if errtxt:
                self.logger.error("Stderr output:\n" + errtxt)

class DeployBasicFunctionsMixin(object):
    

    def deploy_dirs(self,  test = False):
        dirs = self.parser.get_tuples("environment","dirs")
        if not test:
            _make_dir("/", self.target)
        for base, dir_val in dirs:
            for dir in dir_val.split():
                if not test:
                    _make_dir(self.target, dir)
            
    def deploy_files(self,  test = False):
        #copy = self.environment["files"].split()
        copy = self.parser.get_tuples("environment","files")
        print copy
        for base, files in copy:
            for file in files.split():
                config_section = "file:"+file
                if file.startswith("/"):
                    _, __dst = os.path.split(file)
                    _dst = os.path.join(self.target, __dst) 
                    _src = file
                else:
                    _dst = os.path.join(self.target, file)
                    _src = os.path.join(base, file)

                if config_section in  self.parser.sections():
                    if self.parser.has_option(config_section, "target"):
                        _tgt = self.parser.get(config_section, "target")
                        _dst = _tgt

                if os.path.isdir(_src):
                    self.logger.info("Copying subtree of %s to %s", _src , _dst)
                    # copy subtree
                    #shutil.copytree(_src, _dst)
                    distutils.dir_util.copy_tree(_src,_dst)
                else:
                    self.logger.info("Copying %s to %s", _src , _dst)
                    if not test:
                        shutil.copy( _src , _dst)

    def deploy_templates(self, test = False):
        #mako = self.environment["templates"].split()
        mako = self.parser.get_tuples("environment", "templates")
        replacements = self.replacements.copy()
        replacements.update(installpath = self.target, deployment = self.environment['deployment'])

        if mako:
            _pth = "var/cache/mako"
            _make_dir(self.target, _pth)

        lookup_paths = list(set([os.path.dirname(p) for p in self.parser.path_hierarchy ]))  #[0]] + [ os.path.dirname(p) for p in self.parser.path_hierarchy[1:]]
        lookup_paths.append(self.target)
        lookup = TemplateLookup(directories = lookup_paths, module_directory = os.path.join(self.target,_pth))
        
        for base, templates_val in mako:
            templates = templates_val.split()
            for mako_template in templates:
                config_section = "template:"+mako_template 
                local_replacements = replacements.copy()

                __dst =  mako_template
                if __dst.endswith(".mak"):
                    __dst = __dst[:-4]
                _dst = os.path.join(self.target, __dst)

                if config_section in  self.parser.sections():
                    if self.parser.has_option(config_section, "target"):
                        __dst = self.parser.get(config_section, "target")
                        _dst = os.path.join(self.target,__dst)
                    local_replacements.update(dict(self.parser.items(config_section)))

                base_head, base_tail = os.path.split(base)
                try:
                    tmpl = lookup.get_template(os.path.join(base_tail, mako_template) )
                except:
                    if mako_template.startswith("/"): # absolute path
                        tmpl = Template(filename = mako_template)
                        _, _dst = os.path.split(__dst) 
                        _dst = os.path.join(self.target, _dst)  # always in root 
                    else:
                        raise
                        
                _src = tmpl.filename

                self.logger.info("Rendering %s using template %s", _dst, _src)
                self.logger.debug("replacements: %s", local_replacements)
                if not test:
                    with open(_dst,"w") as fp:
                        fp.write(tmpl.render( **local_replacements ))
                else:
                    self.logger.info(tmpl.render(**local_replacements))

    def deploy_run_scripts(self,  test = False):
        scripts = self.parser.get_tuples("environment", "scripts")
        for base, scripts_val in scripts:
            for script in scripts_val.split():
                _opts = self.parser.items("script:" + script)
                _call = dict(_opts)['call']
                _call_list = shlex.split(_call)
                self.logger.info("Calling script %s in %s", script, self.target)
                if not test:
                    self._run_command(self.target, _call_list)

from modules.git import DeployGitMixin
from modules.setuptools import DeploySetuptoolsMixin
from modules.dbmanage import DeployDBManageMixin
from modules.supervisor import DeploySupervisorMixin


class Deployer(DeployerBase, DeployBasicFunctionsMixin, DeployGitMixin,
               DeploySetuptoolsMixin, DeploySupervisorMixin, DeployDBManageMixin):
    
    def deploy(self, test = False):
        tasks = [ "dirs", "git_install", "virtualenv", "files", "templates",
                  "setup_py_build", "setup_py_install", "pip_install", "run_scripts", "online"]
        self._run_tasks(tasks, test = test)

    def update(self, test = False):
        tasks = [ "offline", "backup_db", "dirs",  
                  "git_checkout", "files", "templates",
                  "setup_py_build", "setup_py_install", "pip_install", "run_scripts", "migrate_db", "online"]
        self._run_tasks(tasks, test=test)


    def init_system(self, test = False):
        tasks = ["install_init_script", "install_nginx_conf"]
        self._run_tasks(tasks, test=test)

    def deploy_install_nginx_conf(self, test = False):

        self._run_command(self.target, ["ln","-s", "nginx.conf", os.path.join("etc", "nginx", "sites-available",self.deployment)], shell = True,
                          test = test)
        self._run_command(self.target, [os.path.join("etc", "nginx", "sites-available",self.deployment),
                                 os.path.join("etc", "nginx", "sites-enabled",self.deployment)], shell = True, test = test)

        
def main(argv=sys.argv, quiet = False):
    from optparse import OptionParser
    #from argparse import ArgumentParser
    import traceback
    
    logging.basicConfig(level = logging.INFO)
    local_name = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6))
    try:
        logger.addHandler(logging.FileHandler("./deployment-%s.log" % local_name))
    except IOError:
        logger.addHandler(logging.FileHandler("/tmp/deployment-%s.log" % local_name))
        
    parser = OptionParser()
    parser.add_option("-c","--config",dest = "config", help = "Deployment configuration file", metavar = "FILE")
    parser.add_option("-s","--step-by-step",dest = "stepwise", help = "Step by Step processing", default = False)
    parser.add_option("-d","--dry-run",dest = "dryrun", help = "Do Nothing", default = False)
    parser.add_option("-v","--verbose", dest = "verbose", help ="Be more verbose")
#    parser.add_option("-h","--help", dest ="usage", help = "Print usage information")
    
    config, args = parser.parse_args()
    if config.verbose:
        logger.setLevel(logging.DEBUG)

    if  len(args)<1:
        parser.print_help()
        sys.exit(0)

    if config.usage:
        parser.print_usage()
        sys.exit(0)
        
    command = args[0]
    target = args[1] if len(args)>1 else "/tmp"

    deployer = Deployer(config, target)

    try:
        deployer.perform_command(command, args[2:])
    except:
        traceback.print_exc()

if __name__ == "__main__":
    main(sys.argv, quiet=False)
