#!/usr/bin/env python

from setuptools import setup, find_packages

readme = open('README.md').read()

install_requires = [
    "boto>=2.27.0",
    "dnspython>=1.10.0",
    "pyyaml"
]

setup(
    name='hesiod53',
    version='0.1.0',
    description='Utilities for using hesiod with route53',
    long_description=readme,
    author='Data Science Team',
    author_email='team-data-science@fullcontact.com',
    url='https://github.com/fullcontact/OpsTools/hesiod53',
    packages=find_packages(),
    include_package_data=True,
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'hesiod53 = hesiod53.sync:main',
            'hesiod53ssh = hesiod53.ssh:main'
        ]
    },
)
