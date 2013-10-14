class DeployDBManageMixin(object):
    def deploy_backup_db(self, test = False):
        self._run_command(self.target, ["bin/dbmanage", "app.ini", "backup", "backup before deployment"], test = test)


    def deploy_migrate_db(self,test = False):
        self._run_command(self.target, ["bin/alembic", "upgrade", "head"], test=test)

