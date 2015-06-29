#!/usr/bin/env python

from setuptools import setup, find_packages

readme = open('README.rst').read()

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
    author='FullContact',
    author_email='ops+hesiod53@fullcontact.com',
    url='https://github.com/fullcontact/hesiod53',
    packages=find_packages(),
    include_package_data=True,
    license='MIT',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Systems Administration :: Authentication/Directory',
        'Operating System :: POSIX :: Linux',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],
    keywords='ssh ',
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'hesiod53 = hesiod53.sync:main',
            'hesiod53ssh = hesiod53.ssh:main'
        ]
    },
)
