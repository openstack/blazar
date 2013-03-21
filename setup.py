#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright © 2013 Julien Danjou <julien@danjou.info>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import setuptools

from climate.openstack.common import setup as common_setup

requires = common_setup.parse_requirements(['tools/pip-requires'])
depend_links = common_setup.parse_dependency_links(['tools/pip-requires'])
project = 'climate'
version = common_setup.get_version(project, '2013.1')


setuptools.setup(

    name='climate',
    version=version,

    description='cloud computing metering',

    author='OpenStack',
    author_email='climate@lists.launchpad.net',

    url='https://launchpad.net/climate',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Setuptools Plugin',
        'Environment :: OpenStack',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Topic :: System :: Monitoring',
    ],

    packages=setuptools.find_packages(exclude=['tests',
                                               'tests.*',
                                               '*.tests']),
    cmdclass=common_setup.get_cmdclass(),
    include_package_data=True,

    test_suite='nose.collector',

    scripts=['bin/climate-scheduler'],

    py_modules=[],

    install_requires=requires,
    dependency_links=depend_links,

    zip_safe=False,
)
