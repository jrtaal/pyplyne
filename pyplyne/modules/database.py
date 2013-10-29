class DeployDatabaseManagementMixin(object):
    def deploy_backup_db(self, test = False):
        from turmeric import DBManager
        url = self.replacements['db_url']
        manager = DBManager(url = url, root = self.target)
        if not test:
            manager.backup(message = "backup before deployment")
        #self.run_command(self.target, ["bin/turmeric", "backup", "backup before deployment"], test = test)


    def deploy_migrate_db(self,test = False):
        #from alembic.config import Config
        #from alembic import command
        #alembic_cfg = Config(os.path.join(self.target, "alembic.ini"))
        #command.upgrade(alembic_cfg, "head", sql=False, tag=None)
        #import os
        # Alembic has to run in its own process since it has to have the pythonenv of the target"
        self.run_command(self.target, ["bin/alembic", "upgrade", "head"], test=test)

