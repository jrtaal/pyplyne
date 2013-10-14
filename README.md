PyPlyne
=======

PyPlyne is a easy but powerful deployment engine. The philosophy behind PyPlyne is that git checkout is not meant to deploy a service, such as a website. Furthermore deployment instructions should be decoupled from source code of a project.


Usage:
```
deploy --help
```

```
usage: deploy [-h] [-c FILE] [-s STEPWISE] [-d DRYRUN] [-v VERBOSE]
              command destination [arguments [arguments ...]]

Deploy a service into a destination path.

positional arguments:
  command               The deployment command to run. ('deploy' / 'test' /
                        'update' / 'info')
  destination           The target path to deploy in. It does not need to
                        exist, but you should have rights to create it
  arguments             Positional arguments to pass on the the command

optional arguments:
  -h, --help            show this help message and exit
  -c FILE, --config FILE
                        Deployment configuration file
  -s STEPWISE, --step-by-step STEPWISE
                        Step by Step processing
  -d DRYRUN, --dry-run DRYRUN
                        Do Nothing
  -v VERBOSE, --verbose VERBOSE
                        Be more verbose
```