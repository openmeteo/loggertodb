=============
Release notes
=============

Version 2.2 (2021-01-13)
========================

This makes loggertodb compatible with a new version of Enhydris that
no longer has a "raw" time series type, and instead has an "initial"
time series type. (This update has occurred in an internal unnumbered
Enhydris release that precedes the release of Enhydris 3).

Version 2.1 (2020-11-17)
========================

The ``nullstr`` parameter has been renamed to ``null``, keeping
``nullstr`` as a deprecated synonym. If the value of ``null`` is a
number, it is interpreted as a number instead of as a string.

Version 2.0 (2020-10-14)
========================

``loggertodb`` version 2 is not compatible with Enhydris versions
earlier than 3.  Use ``loggertodb`` version 1 for Enhydris version 2.

Token authentication
--------------------

``loggertodb`` used to use a username and password to logon to Enhydris.
Now it uses a token instead. Accordingly, the ``username`` and
``password`` configuration file parameters have been abolished and
``auth_token`` has been introduced. See the :ref:`documentation on
authentication <authentication>` for more detailed instructions.

Time series groups
------------------

Enhydris 3 contains the notion of a time series group—a group of related
time series for the same variable, e.g. the initial, checked and
aggregated versions of a time series. Accordingly, ``loggertodb`` has
been changed so that the ``fields`` parameter and the wdat5-specific
meteorological parameters specify time series group ids rather than time
series ids.  ``loggertodb`` will always upload data in the "initial"
time series of the time series group; if such a time series does not
exist, it is automatically created.

How to upgrade from version 1
-----------------------------

If you have a ``loggertodb`` v1 configuration file, ``loggertodb`` v2 can
convert it. Enter this:

   :samp:`loggertodb --upgrade {loggertodb.conf}`

where :samp:`{loggertodb.conf}` is the configuration file you want to
upgrade.  ``loggertodb`` will make requests to Enhydris in order to
determine the ``auth_token`` from ``username`` and ``password``, and the
time series group ids from the time series ids.  The configuration file
will be upgraded accordingly. The original file will be backed up by
adding the ``.bak`` extension (e.g. ``loggertodb.conf.bak``). (If the
backup file already exists and is different from the original,
``loggertodb`` will terminate with an error.)

Changes in 2.0 microversions
----------------------------

2.0.1 (2020-10-21)
^^^^^^^^^^^^^^^^^^

- Fixed inability of the 2.0.0 Windows executable to run on Windows 7.

2.0.2 (2020-10-23)
^^^^^^^^^^^^^^^^^^

- Fixed malfunctioning Windows executable (it had been built with wrong
  dependencies).

History up to Version 1
=======================

1.0.0 (2019-10-29)
------------------

- Improved handling of switch from DST to winter time.

0.2.2 (2019-08-20)
------------------

- Improved error message in multi-file simple format when
  nfields_to_ignore was 1 or more and a line did not have enough fields.

0.2.1 (2019-07-17)
------------------

- Fixed a crash when a file was empty in multi-file simple format.
- Improved error messages in multi-file simple format when the
  timestamps were badly ordered in a file or overlapping between files.

0.2.0 (2019-07-16)
------------------

- Added multi-file option to simple format.
- Added configuration parameters "encoding" and "ignore_lines".

0.1.3 (2019-06-07)
------------------

- Upgraded htimeseries to 1.0.
- Made dependencies more robust.

0.1.2 (2019-05-27)
------------------

- Made parsing dates more robust in simple format.
- Fixed extreme slowness when thousands of records had to be inserted.
- Fixed unhelpful error message when file was out of order.

0.1.1 (2019-04-18)
------------------

- Fixed a bug that prevented using a log file.

0.1.0 (2019-04-18)
------------------

- Initial release
