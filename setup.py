import sys
from distutils.core import setup
if sys.version_info < (2, 3):
    print >> sys.stderr, 'error: python 2.3 or higher is required, you are using %s' %'.'.join([str(i) for i in sys.version_info])

    sys.exit(1)

args = dict(
    name = 'hprose',
    version = '1.4.3',
    description = 'Hprose is a High Performance Remote Object Service Engine.',
    long_description = open('README.md').read(),
    keywords = "hprose rpc serialize wsgi web service server development rest webservice json",
    author = 'Ma Bingyao',
    author_email = 'andot@hprose.com',
    url = 'https://github.com/hprose/hprose-python',
    license = 'MIT',
    platforms = 'any')

if sys.version_info < (3, 0):
    args['install_requires'] = ['fpconst']
    args['packages'] = ["hprose"]
    args['package_dir'] = dict(hprose = "python2/hprose")
else:
    args['packages'] = ["hprose", 'fpconst']
    args['package_dir'] = dict(
        hprose = "python3/hprose",
        fpconst = "python3/fpconst")

args['classifiers'] = [
    'Development Status :: 5 - Production/Stable',
    'Intended Audience :: Developers',
    'Programming Language :: Python :: 2',
    'Programming Language :: Python :: 2.3',
    'Programming Language :: Python :: 2.4',
    'Programming Language :: Python :: 2.5',
    'Programming Language :: Python :: 2.6',
    'Programming Language :: Python :: 2.7',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.0',
    'Programming Language :: Python :: 3.1',
    'Programming Language :: Python :: 3.2',
    'Programming Language :: Python :: 3.3',
    'Programming Language :: Python :: 3.4',
    'License :: OSI Approved :: MIT License',
    'Topic :: Internet',
    'Topic :: Internet :: WWW/HTTP :: WSGI',
    'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
    'Topic :: Internet :: WWW/HTTP :: WSGI :: Middleware',
    'Topic :: Software Development :: Libraries :: Python Modules',
    'Topic :: Software Development :: Object Brokering',
    'Topic :: System :: Networking',
    'Topic :: System :: Distributed Computing']

setup(**args)
