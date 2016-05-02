from setuptools import setup, find_packages
import os
import re
import platform

if os.environ.get('USER', '') == 'vagrant':
    del os.link

requirements = [r.strip() for r in open('requirements.txt').readlines() if not r.startswith('--')]
requirements = [r if ('git+' not in r) else re.sub(r".*egg=(.*)", r"\1", r).strip() for r in requirements]

data_files = []
if platform.system() != "Windows":
    data_files = [
        ('/etc/jobmanager', ['bin/client.ini', 'bin/client.spec']),
        ('/var/log/jobmanager', [])
    ]

setup(
    name='jobmanager-client',
    version=open('VERSION.txt').read().strip(),
    author='Ronan Delacroix',
    author_email='ronan.delacroix@gmail.com',
    url='https://github.com/ronhanson/python-jobmanager-client',
    packages=find_packages(where='.', exclude=["fabfile", "tools", "*.tests", "*.tests.*", "tests.*", "tests"]) + ['jobmanager'],
    package_data={ 'jobmanager': ['jobmanager/*.py'] },
    scripts=['bin/jobmanager-client'],
    data_files=data_files,
    license=open('LICENCE.txt').read().strip(),
    description='Job Manager Client',
    long_description=open('README.md').read().strip(),
    include_package_data=True,
    install_requires=requirements,
    classifiers=[
        'Topic :: Utilities',
        'Topic :: Software Development :: Libraries',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Intended Audience :: Manufacturing',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
    ],
)
