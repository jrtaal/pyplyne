import subprocess
import os, sys

class DeploySetuptoolsMixin(object):

    def deploy_virtualenv(self,  test = False):
        dest = self.target
        if not test and not os.path.exists(dest):
            os.mkdir(dest)
        self.progress("Creating virtualenv in %s", dest)
        if not test:
            process = subprocess.Popen(["virtualenv",dest])
            process.communicate()

    def deploy_setup_py_build(self,  test = False):
        targets = self.environment.get('setup.py').split()
        for target in targets:
            #config = dict(self.parser.items("setup.py:%s" % target))
            
            _dst = os.path.join(self.target, target)
            self.progress("Running setup.py in %s", _dst)
            _call = [ ".", os.path.join(self.target,"bin","activate"),"&&", os.path.join(self.target, "bin","python"),os.path.join(_dst,"setup.py"),"build"]
            self._run_command(_dst, _call, test=test, shell=True)
        
    def deploy_setup_py_install(self,  test = False):
        targets = self.environment.get('setup.py').split()
        for target in targets:
            #config = dict(self.parser.items("setup.py:%s" % target))


            _dst = os.path.join(self.target, target)
            self.progress("Running setup.py in %s", _dst)
            _call = [ ".", os.path.join(self.target,"bin","activate"),"&&", os.path.join(self.target, "bin","python"),os.path.join(_dst,"setup.py"),"install"]
            self._run_command(_dst, _call, test=test, shell=True)
        
    def deploy_pip_install(self,  test = False):
        packages = self.environment.get("pip") 
        self.progress("Installing %s in %s", packages, self.target)
        _call = [ ".", os.path.join(self.target,"bin","activate"),"&&", os.path.join(self.target, "bin","pip"),"install", packages]
        self._run_command(self.target, _call, test=test,shell=True)
