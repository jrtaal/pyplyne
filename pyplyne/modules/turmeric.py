class DeployDatabaseManagementMixin(object):
    def deploy_backup_db(self, test = False):
        self.run_command(self.target, ["bin/turmeric", "backup", "backup before deployment"], test = test)


    def deploy_migrate_db(self,test = False):
        self.run_command(self.target, ["bin/alembic", "upgrade", "head"], test=test)

