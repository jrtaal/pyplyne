PyPlyne
=======

PyPlyne is a easy but powerful deployment engine. The philosophy behind PyPlyne is that git checkout is not meant to deploy a service, such as a website. Furthermore deployment instructions should be decoupled from source code of a project.


Usage:
> deploy -c <configuration path> <command> <destination>


Help:
> deploy --help

> Usage: deploy [options]
>
> Options:
>   -h, --help             show this help message and exit
>   -c FILE, --config=FILE Deployment configuration file
>   -s STEPWISE, --step-by-step=STEPWISE
>                          Step by Step processing
>   -d DRYRUN, --dry-run=DRYRUN
>                          Do Nothing
>   -v VERBOSE, --verbose=VERBOSE
>                          Be more verbose
