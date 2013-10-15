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
       
        self.environment = dict(self.parser.items("environment"))
        self.replacements = dict(self.parser.items("replace"))
        self.replacements['target'] = target
        self.replacements['deployment'] = self.deployment

        self.logger = logging.getLogger("pyplyne.deployer")

    def progress(self, msg, *args, **kwargs):
        self.logger.info(" * " + msg + "\n", *args, **kwargs)
        
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
        tasks = [ "dirs", "files", "run_scripts"]
        self.logger.warn("=" * 60)
        self.logger.warn("Starting Deployment procedure using configuration: %s" % self.deployment)
        self.logger.warn("Target path: %s" % self.target)
        self.logger.warn("=" * 60)
        self._run_tasks(tasks)

    def update(self, test = False):
        tasks = [ "dirs", "files", "run_scripts"]
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
                answer = raw_input("%sNext Step: %s. Proceed? ( Y/n/s(kip) ) " % ( "TEST! " if test else "", task_name))
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
                answer = raw_input("\nLast step failed. Proceed? ( y/N/s(kip) ) " )
                if answer.lower().startswith("s"):
                    continue
                if not answer.lower().startswith("y"):
                    if not isinstance(e, DeploymentException):
                        e = DeploymentException(underlying = e)
                    raise e

    def _run_sub_tasks(self, task_name, argument_sets, test = False):
        for task_args, task_kwargs in argument_sets:
            if self.options.stepwise:               
                answer = raw_input("%sNext task: %s (%s). Proceed? ( Y/n/s(kip) ) " % ( "TEST! " if test else "", task_name), argument_set)
                if answer.lower().startswith("s"):
                    continue
                if answer.lower().startswith("n"):
                    raise DeploymentAborted()


            task = getattr(self, "deploy_" + task_name)

            self.progress("Running task %s (%s, %s)", task_name, ", ".join(task_args), task_kwargs)
            try:
                if not test:
                    task(*task_args, **task_kwargs)
            except Exception as e:
                if self.options.verbose:
                    self.logger.exception("Task %s failed", task_name)
                else:
                    self.logger.error("Task %s failed: %s", task_name, e)
                answer = raw_input("\nLast subtask failed. Proceed with next subtask? ( y/N/s(kip) ) " )
                if answer.lower().startswith("s"):
                    continue
                if not answer.lower().startswith("y"):
                    if not isinstance(e, DeploymentException):
                        e = DeploymentException(underlying = e)
                    raise e
        
                    
    def _run_command(self, cwd, cmdline, test = False, **kwargs):
        try:
            self._internal_run_command(cwd,cmdline, test = test, **kwargs)
        except DeploymentException:
            raise
        except Exception as e:
            raise
            #raise DeploymentException("Runnning External Command failed", underlying=e)
            
    def _internal_run_command(self, cwd, cmdline, test = False, expect_returncodes = [None, 0], **kwargs):
        self.logger.info("** %s> %s\n", os.path.abspath(cwd),
                         cmdline if isinstance(cmdline,basestring) else  " ".join([ (str(s) if not " " in s else ("\"%s\"" % s))  for s in cmdline]))
        if not test:
            if kwargs.get('shell')==True and not isinstance(cmdline, basestring):
                cmdline = " ".join(cmdline)

                
            stderr = StringIO()
            env = os.environ.copy()
            env['PATH'] = ":".join( env.get('PATH').split(":") + [ os.path.join(self.target,"bin") ]) 
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
                        self._run_command(_pwd, _call, shell = True)
                else:
                    
                    _call_list = shlex.split(_call)

                    self.progress("Calling script %s in %s", script, _pwd)
                
                    if not test:
                        self._run_command(_pwd, _call_list)


from modules.git import DeployGitMixin
from modules.setuptools import DeploySetuptoolsMixin
from modules.turmeric import DeployDatabaseManagementMixin
from modules.supervisor import DeploySupervisorMixin
from modules.makotemplates import DeployMakoTemplatesMixin



class Deployer(DeployerBase, DeployBasicFunctionsMixin, DeployGitMixin,
               DeploySetuptoolsMixin, DeploySupervisorMixin, DeployDatabaseManagementMixin,
               DeployMakoTemplatesMixin):
    
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
    #from optparse import OptionParser
    from argparse import ArgumentParser
    import traceback
    import datetime
    import random
    #datestr = ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6))
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
    parser.add_argument("command", metavar = "command", default = "info", help = "The deployment command to run. ('%s') " % "' / '".join(Deployer.commands), choices = Deployer.commands )
    parser.add_argument("destination", metavar = "destination", default = "/tmp", help = "The target path to deploy in. It does not need to exist, but you should have rights to create it")
    parser.add_argument("arguments", metavar = "arguments",nargs="*" , help = "Positional arguments to pass on the the command")
    
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
       
    deployer = Deployer(config, config.destination)

    try:
        deployer.perform_command(config.command, config.arguments)
    except Exception as e:
        print e
        if config.verbose:
            traceback.print_exc()

    print "The log was saved to %s" % logname
            
