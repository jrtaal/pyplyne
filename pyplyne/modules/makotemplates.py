import mako
from mako.lookup import TemplateLookup, Template


class DeployMakoTemplatesMixin(object):
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
