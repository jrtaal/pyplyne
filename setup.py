import os
from setuptools import setup
from setuptools import setup, find_packages

try:
    import gitversion
    version = gitversion.get_git_version()
except:
    try:
        version = open("RELEASE-VERSION").read()
    except:
        version = "dev"

def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()
    
setup(
    name = "pyplyne",
    version = version,
    author = "Jacco Taal",
    author_email = "jacco@bitnomica.com",
    description = ("""PyPlyne is a easy but powerful deployment engine. The philosophy behind PyPlyne is that git checkout
                   is not meant to deploy a service, such as a website. Furthermore deployment instructions
                   should be decoupled from source code of a project.
                   """),
    license = "All rights reserved",
    keywords = "deployment",
    url = "http://gitlab.bitnomica.com/vidacle-team/pyplyne",
    long_description=read('README.md'),
    classifiers=[ ],
    packages=find_packages(exclude = ["test"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=["mako" ,
                      "turmeric>=1.1",
                      "alembic",
                      "gitversion",
                  ],
    tests_require=[],
    dependency_links = ["git+ssh://git@gitlab.bitnomica.com/vidacle-team/turmeric.git#egg=turmeric-1.1",
                        "git+ssh://git@gitlab.bitnomica.com/jacco/gitversion.git#egg=gitversion-0.2",
                        ],
    setup_requires = [ "setuptools-git>=0.3"],
    test_suite="lifeshare",
    entry_points = """\
      [console_scripts]
      pyplyne = pyplyne.deploy:main
      """,
)

