import random
import string
import os,sys

class DeployGitMixin(object):
    def deploy_git_install(self,  test = False):
        repos = self.environment.get('git').split()
        for repo in repos:
        
            config = dict(self.parser.items("git:%s" % repo))
            branch = config.get("branch","master")
            uri = config.get("repo")
            package = config.get("package", repo)
            target = config.get("git_target") or ("build/%s" % package)
            
            self.progress("Installing %s (branch %s) in %s", uri, branch, target)
            cwd = os.path.join(self.target, target)
            _call = [ "git","clone"] +  (["-b" , branch] if branch else []) + [ uri, cwd]                            
            self._run_command(self.target, _call, test=test, shell=False)


    def deploy_git_checkout(self,  test = False):
        repos = self.environment.get('git').split()
        for repo in repos:

            config = dict(self.parser.items("git:%s" % repo))
            branch = config.get("branch")
            uri = config.get("repo")
            package = config.get("package",repo)
            target = config.get("git_target") or ("build/%s" % package)

            local_name = branch + "/" + ''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(6))
            cwd = os.path.join(self.target, target)

            self.progress("Updating %s in %s to branch %s (%s) from %s", uri, self.target, branch, local_name, cwd)

            _call = [ "git", "fetch" ]
            self._run_command(cwd, _call, test=test, shell=False )
            _call = [ "git", "fetch" ,"--tags"]
            self._run_command(cwd, _call, test=test, shell=False )
            _call = [ "git", "checkout", branch]
            self._run_command(cwd, _call, test=test, shell=False)

