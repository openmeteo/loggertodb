==========
loggertodb
==========


.. image:: https://img.shields.io/travis/openmeteo/loggertodb.svg
        :target: https://travis-ci.org/openmeteo/loggertodb

.. image:: https://codecov.io/github/openmeteo/loggertodb/coverage.svg
        :target: https://codecov.io/gh/openmeteo/loggertodb
        :alt: Coverage

.. image:: https://img.shields.io/pypi/v/loggertodb.svg
        :target: https://pypi.python.org/pypi/loggertodb

.. image:: https://readthedocs.org/projects/loggertodb/badge/?version=latest
        :target: https://loggertodb.readthedocs.io/en/latest/?badge=latest
        :alt: Documentation Status

.. image:: https://pyup.io/repos/github/openmeteo/loggertodb/shield.svg
     :target: https://pyup.io/repos/github/openmeteo/loggertodb/
     :alt: Updates



Insert meteorological station data to Enhydris

License
=======

Free software: GNU General Public License v3

Documentation
=============

https://loggertodb.readthedocs.io.

Creating a Windows executable
=============================

**Note:** You have to work on Windows 7. If you work on Windows 10, the
resulting executable might not run on Windows 7. If you find a way to
create the executable on Windows 10 that runs on Windows 7 (or stop
supporting Windows 7), fix this README.

We've found that executables created on 64-bit Windows 7 do run on
32-bit Windows 7, however ideally the resulting executable should be
tested in both environments.

The first time:

 1. Install ``git``.
 2. Install a recent Python 3 version.
 3. Execute Git Bash.
 4. Clone loggertodb.
 5. Change to the working directory of ``loggertodb``.
 6. ``pip install virtualenv==16.1.0`` (this is because of a
    `pyinstaller bug`_).
 7. ``virtualenv ../venv``
 8. ``../venv/Scripts/pip install -e .``
 9. ``../venv/Scripts/pip install pyinstaller``

.. _pyinstaller bug: https://github.com/pyinstaller/pyinstaller/issues/4064

Next times:

 1. ``../venv/Scripts/pip install -e .`` (to upgrade dependencies if needed)
 2. ``../venv/Scripts/python setup.py test``
 3. ``rm -r dist loggertodb.spec``
 4. ``../venv/Scripts/pyinstaller --onefile --name=loggertodb bin/loggertodb-windows``

After this, ``loggertodb.exe`` should be in the ``dist`` directory.
