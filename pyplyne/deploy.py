#!/usr/bin/env python

import shutil
import os, sys
import subprocess
import logging
import string
import shlex
import distutils.dir_util

from cStringIO import StringIO

from parser import HierarchicalConfigParser
from ConfigParser import SafeConfigParser

logger = logging.getLogger("pyplyne")


logging.addLevelName(logging.INFO+5, "INFO(stderr)")


class DeploymentException(Exception):
    default_message = "Deployment failed"
    def __init__(self, message = None, underlying = None):
        Exception.__init__(self)
        self.message = message or self.default_message
        self.underlying = underlying

    def __str__(self):
        if self.underlying:
            return super(DeploymentException, self).__str__() + "%s. Underlying Error: %s" % (self.message, self.underlying)
        return super(DeploymentException, self).__str__() + "%s" % self.message

class DeploymentAborted(DeploymentException):
    default_message = "Deployment aborted by user"
    pass

class DeploymentStepFailed(DeploymentException):
    default_message = "Deployment step failed"
    pass

class DeploymentStepSkipped(DeploymentException):
    pass

class DeploymentStepSkippedByUser(DeploymentStepSkipped):
    pass
    
class DeploymentStepSkippedForTesting(DeploymentStepSkipped):
    pass


def camelcaser(string):
    out = ""
    _prevc = ""
    nextupper = True
    for char in string:
        if char in "_-:/,.+=\\[]{}'\"":
            nextupper = True
            continue
        if nextupper:
            char = char.upper()
        out += char
        nextupper = False
    return out
    
class DeployerBase(object):
    commands = ("deploy", "test", "update", "info")

    workflows = dict(
        deploy =  [ "dirs", "files", "run_scripts"],
        update =  [ "dirs", "files", "run_scripts"],
        test = []
    )

    def __new__(cls, options, target):
        if os.path.isdir(options.config):
            options.config = os.path.join(options.config, "deployment.ini")
        else:
            options.config =  os.path.abspath(options.config)

        parser = HierarchicalConfigParser(cls.get_configs(options.config), defaults = dict(target = target))
        deployment = parser.get("environment", "deployment")
        modules = []
        if parser.has_option("environment" ,"modules"):
            modules = parser.get("environment", "modules")
            if modules:
                modules = modules.split()

        parser.defaults = dict(target = target, deployment = deployment)

        DeployerClass = cls.deployer_factory( camelcaser(deployment) + "Deployer", modules)
        logger.info("Instantiating Deployer %s with modules: %s", DeployerClass, ", ".join(modules))
        return super(DeployerBase, cls).__new__(DeployerClass, options, target, parser = parser)
        
    @classmethod
    def deployer_factory(cls, name,  modules = [], Base = None):
        import types
        import importlib
        _modules = []
        for mod in modules:
            if isinstance(mod, types.ModuleType):
                _modules.append(mod)
            else:
                package_name, cls_name = mod.split(":")
                logger.info("Loading module %s from %s", cls_name, package_name)
                _package =importlib.import_module(package_name)
                _modules.append( getattr(_package,cls_name) )
        kls = type(name,tuple( [Base or cls, DeployBasicFunctionsMixin] + _modules), {})
        return kls    
    
    @classmethod
    def get_configs(cls, path):
        _config = path
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
        deployment = _parsers[0].get("environment","deployment")

        return configs


    def __init__(self, options, target = None, parser = None):
        if os.path.isdir(options.config):
            options.config = os.path.join(options.config, "deployment.ini")
        else:
            options.config =  os.path.abspath(options.config)
        
        self.parser = parser or HierarchicalConfigParser(self.get_configs(options.config), defaults = dict(target = target))
        
        self.deployment = self.parser.get("environment","deployment")

        self.parser.defaults = dict(target = target, deployment = self.deployment)
 
        self.options = options

        self.dryrun = options.dryrun
        
        self.target = target
       
        self.environment = dict(self.parser.items("environment"))
        self.replacements = dict(self.parser.items("replace"))
        self.replacements['target'] = target
        self.replacements['deployment'] = self.deployment

        self.logger = logging.getLogger("pyplyne.deployer")

        if self.parser.has_section("flows"):
            self.workflows = self.workflows.copy()
            flows = self.parser.items("flows")
            for command, items in flows:
                self.workflows[command] = items.split()
            logger.info("Workflows: %s", self.workflows)

    def progress(self, msg, *args, **kwargs):
        self.logger.info(( "TEST" if self.dryrun else "") +  " * " + msg + "\n", *args, **kwargs)
        
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
            try:
                cmd = getattr(self, command)
            except:
                tasks = self.workflows.get(command)
                self.logger.warn("=" * 60)
                self.logger.warn("Starting task %s using configuration: %s", command, self.deployment)
                self.logger.warn("Target path: %s" % self.target)
                self.logger.warn("=" * 60)
                self._run_tasks(tasks, test = self.dryrun)
            else:
                cmd( *args)
        else:
            print "command not in %s" % list(self.valid_commands())

    def info(self):
        self.parser.pretty_print(sys.stdout)
        import pprint

        print "\n\nVariable replacements\n"
        pprint.pprint(self.replacements)
        
    def run_tasks(self, task, test = False):
        tasks = self.workflows[task]
        self.logger.warn("=" * 60)
        self.logger.warn("Starting %s procedure using configuration: %s", task, self.deployment)
        self.logger.warn("Target path: %s" % self.target)
        self.logger.warn("=" * 60)
        self._run_tasks(tasks, test)

    def _run_tasks(self, tasks, test = False):
        for task_name in tasks:
            if self.options.stepwise:               
                answer = raw_input("%sNext Step: %s. Proceed? ( Yes/no/skip ) " % ( "TEST! " if test else "", task_name))
                if answer.lower().startswith("s"):
                    continue
                if answer.lower().startswith("n"):
                    raise DeploymentAborted()

            task = getattr(self, "deploy_" + task_name)

            self.progress("Running task %s", task_name)
            try:
                task(test = test)
            except Exception as e:
                if self.options.verbose:
                    self.logger.exception("Task %s failed", task_name)
                else:
                    self.logger.error("Task %s failed: %s", task_name, e)
                answer = raw_input("\nLast step failed. Proceed? ( yes/No/skip )  " )
                if answer.lower().startswith("s"):
                    continue
                if not answer.lower().startswith("y"):
                    if not isinstance(e, DeploymentException):
                        e = DeploymentException(underlying = e)
                    raise e

    def run_command(self, cwd, cmdline, test = False, **kwargs):
        try:
            self._internal_run_command(cwd,cmdline, test = test, **kwargs)
        except DeploymentException:
            raise
        except Exception as e:
            #raise
            raise DeploymentException("Runnning External Command failed", underlying=e)
            
    def _internal_run_command(self, cwd, cmdline, test = False, expect_returncodes = [None, 0], **kwargs):
        self.logger.info("%s** %s> %s\n", "TEST " if self.dryrun or test else "", os.path.abspath(cwd),
                         cmdline if isinstance(cmdline,basestring) else  " ".join([ (str(s) if not " " in s else ("\"%s\"" % s))  for s in cmdline]))

        if kwargs.get('shell')==True and not isinstance(cmdline, basestring):
            cmdline = " ".join(cmdline)


        stderr = StringIO()
        env = os.environ.copy()
        env['PATH'] = ":".join( env.get('PATH').split(":") + [ os.path.join(self.target,"bin") ]) 
        if not test and not self.dryrun:
            process = subprocess.Popen(cmdline , stdin = subprocess.PIPE, env = env,
                                       stdout = subprocess.PIPE, stderr = subprocess.STDOUT, cwd = cwd, **kwargs )


            while process.poll() == None:
                line = process.stdout.readline()
                if line == '':
                    break;
                self.logger.info(line.rstrip())
            
            if process.returncode not in expect_returncodes :
                self.logger.error("Process returned %s", process.returncode)
                print stderr.getvalue()
                raise DeploymentStepFailed("An error occurred in subprocess '%s'. Please see the logs." % " ".join(cmdline))
            else:
                self.progress("Process returned %s. (OK)", process.returncode)
            errtxt = stderr.getvalue()
            if errtxt:
                self.logger.error("Stderr output:\n" + errtxt)

                
    @staticmethod
    def _make_dir(dest, path):
        _pths = path.split(os.path.sep)
        for i,p in enumerate(_pths):
            _pth = os.path.join(dest, *_pths[0:i+1] )
            logger.log(5,"Checking path %s", _pth)
            if not os.path.exists(_pth):
                logger.info("Creating directory %s", _pth)
                os.mkdir(_pth )
              
class DeployBasicFunctionsMixin(object):   

    def deploy_dirs(self,  test = False):
        dirs = self.parser.get_tuples("environment","dirs")
        if not test:
            self._make_dir("/", self.target)
        for base, dir_val in dirs:
            for dir in dir_val.split():
                if not test:
                    self._make_dir(self.target, dir)

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
                    self.progress("Copying subtree of %s to %s", _src , _dst)
                    # copy subtree
                    #shutil.copytree(_src, _dst)
                    distutils.dir_util.copy_tree(_src,_dst)
                else:
                    self.progress("Copying %s to %s", _src , _dst)
                    if not test:
                        shutil.copy( _src , _dst)

    def deploy_run_scripts(self,  test = False):
        scripts = self.parser.get_tuples("environment", "scripts")
        for base, scripts_val in scripts:
            for script in scripts_val.split():
                _opts = self.parser.items("script:" + script)
                _call = dict(_opts)['call']
                _pwd = dict(_opts).get('pwd', self.target)
                if ";" in _call:
                    if not test:
                        self.run_command(_pwd, _call, shell = True)
                else:
                    
                    _call_list = shlex.split(_call)

                    self.progress("Calling script %s in %s", script, _pwd)
                
                    if not test:
                        self.run_command(_pwd, _call_list)


        
def main(argv=sys.argv, quiet = False):
    from argparse import ArgumentParser
    import traceback
    import datetime
    import random
    datestr = datetime.datetime.utcnow().isoformat()

    try:
        logname = "./deployment-%s.log" % datestr
        logger.addHandler(logging.FileHandler(logname))
    except IOError:
        logname = "/tmp/deployment-%s.log" % datestr
        logger.addHandler(logging.FileHandler(logname))

    so = logging.StreamHandler(sys.stdout)
    so.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(so)
    logger.setLevel(logging.INFO)
    
    parser = ArgumentParser(description="Deploy a service into a destination path.")
    parser.add_argument("command", metavar = "command",
                        default = "info",
                        help = "The deployment command to run. ('%s') " % "' / '".join(DeployerBase.commands),
                        choices = list(DeployerBase.commands) )
    parser.add_argument("destination", metavar = "destination", default = "/tmp", help = "The target path to deploy in. It does not need to exist, but you should have rights to create it")
    parser.add_argument("arguments", metavar = "arg",nargs="*" , help = "Positional arguments to pass on the the command")
    
    parser.add_argument("-c","--config",dest = "config", help = "Deployment configuration file", metavar = "FILE")
    parser.add_argument("-s","--step-by-step",dest = "stepwise", help = "Step by Step processing", action = "store_true")
    parser.add_argument("-d","--dry-run",dest = "dryrun", help = "Do Nothing", action = "store_true")
    parser.add_argument("-v","--verbose", dest = "verbose", help ="Be more verbose", action = "store_true")

    
    config = parser.parse_args()
    if config.verbose:
        logger.setLevel(logging.DEBUG)

    if not config.command or not config.config:
        parser.print_help()
        sys.exit(0)

    deployer = DeployerBase(config, config.destination)

    try:
        deployer.perform_command(config.command, config.arguments)
    except Exception as e:
        print e
        if config.verbose:
            traceback.print_exc()

    print "The log was saved to %s" % logname
            
