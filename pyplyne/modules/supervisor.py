import subprocess
import os, sys


class DeploySupervisorMixin(object):

    def deploy_offline(self,  test = False):
        _call_list = ["bin/supervisorctl", "stop", "all"]
        try:
            self.run_command(self.target, _call_list)
        except Exception:
            self.logger.warn("Deploy offline failed, going on")
            pass
            
    def deploy_online(self,  test = False):
        _call_list = ["bin/supervisorctl", "start", "all"]
        self.run_command(self.target, _call_list)

    def deploy_install_init_script(self,  test = False):
        
        _call_list = ["ln", "-s", "supervisor.init.d", os.path.join("etc","init.d","supervisor-%s" % self.deployment) ]
        self.run_command(self.target, _call_list)
