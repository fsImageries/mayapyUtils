import codecs
import os
import re

try:
    from setuptools import find_packages, setup
except ImportError:
    from distutils.core import setup
    find_packages = None

# This whole setup is shamelessly copied from https://github.com/robertjoosten mayapip setup.py.
# Thanks nonetheless :*
#----------------------------------------------------------------------#

def read(*parts):
    with codecs.open(os.path.join(here, *parts), 'r') as fp:
        return fp.read()
  
def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(
        r"^__version__ = ['\"]([^'\"]*)['\"]",
        version_file,
        re.M,
    )
    if version_match:
        return version_match.group(1)

    raise RuntimeError("Unable to find version string.")
  
#----------------------------------------------------------------------#


package = "mayapyUtils"
here = os.path.abspath(os.path.dirname(__file__))  
packages = ['mayapyUtils']
long_description = read("README.md")
requires = [
    "pyUtils @ https://github.com/fsImageries/pyUtils/tarball/main#egg=pyUtils-0.1.0"]
    



attrs = {"name":package,
         "version":find_version("src", package, "__init__.py"),
         "author":"Farooq Singh",
         "author_email":"imageries@mail.de",
         "package_dir":{"": "src"},
         "packages":find_packages(where="src") if find_packages else packages,
         "license": "GPL2",
         "install_requires": requires,
         "description":"Maya-Python helper library.",
         "long_description":long_description,
         "keywords":"maya python mayapy utilities"}


if __name__ == "__main__":
    setup(**attrs)