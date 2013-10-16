import os
from setuptools import setup
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()
    
setup(
    name = "pyplyne",
    version = "1.1",
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
                      "turmeric>=0.1",
                      "alembic",
                      #"git+ssh://git@gitlab.bitnomica.com:vidacle-team/turmeric.git@master#egg=turmeric"
                  ],
    tests_require=[],
    dependency_links = ["git+ssh://git@gitlab.bitnomica.com/vidacle-team/turmeric.git#egg=turmeric"],
    setup_requires = [ "setuptools-git>=0.3"],
    test_suite="lifeshare",
    entry_points = """\
      [console_scripts]
      deploy = pyplyne.deploy:main
      """,
)

