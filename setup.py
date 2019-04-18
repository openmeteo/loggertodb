#!/usr/bin/env python

from setuptools import find_packages, setup

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "Click>=6.0",
    "iso8601",
    "htimeseries>=0.2",
    "simpletail",
    "enhydris_api_client>=0.2",
]

setup_requirements = []

test_requirements = ["pyfakefs"]

setup(
    author="Antonis Christofides",
    author_email="antonis@antonischristofides.com",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    description="Insert meteorological station data to Enhydris",
    entry_points={"console_scripts": ["loggertodb=loggertodb.cli:main"]},
    install_requires=requirements,
    license="GNU General Public License v3",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="loggertodb",
    name="loggertodb",
    packages=find_packages(include=["loggertodb"]),
    setup_requires=setup_requirements,
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/aptiko/loggertodb",
    version="0.1.1",
    zip_safe=False,
)
