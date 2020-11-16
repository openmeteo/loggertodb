==============
For developers
==============

Loggers are machines to which sensors are connected; they log the
measurements of the sensors. In order to avoid confusion with Python
Logger_ objects, here and in the code we call them **meteologgers**. But
the user should not be bothered with that, so user documentation uses
"loggers" for meteologgers.

MeteologgerStorage objects
==========================

In its simplest and most usual form, a "meteologger storage" is a text
file to which the meteologger software appends records. Each line of the
file has a timestamp and the values of the various measurements.

Some kinds of meteologgers (or meteologger software), however, use
different kinds of storage. They may be automatically starting a new
file daily or monthly. In such cases, the "meteologger storage" is a
directory that has these files.

The :class:`MeteoLoggerStorage` class is an abstract base class that is
meant to be subclassed. It provides functionality that is common to all
kinds of meteologger storages. Since each make of meteologger, or even
each type of software used to unload data from a meteologger, provides a
different kind of meteologger storage, MeteologgerStorage subclasses are
specialized, each to a specific kind of meteologger storage.

.. class:: MeteologgerStorage(parameters[, logger=None])

   A :class:`MeteologgerStorage` instance should never be constructed;
   instead, a subclass should be constructed; however, the call for
   constructing any subclass has the same arguments.  *parameters* is a
   dictionary containing values for configuration parameters such as
   :attr:`path` and :attr:`fields`.  The *logger* argument is a Logger_
   object to which error, progress, and debugging information is
   written.

   When :class:`MeteologgerStorage` is initialized, it checks the
   correctness of *parameters* and raises :class:`ConfigurationError` if
   anything's wrong. See :meth:`get_required_parameters()` and
   :meth:`get_optional_parameters()` for more information.

   The following :class:`MeteologgerStorage` attributes are initialized
   from *parameters*:

   .. attribute:: path

      The pathname to the storage; a filename or directory name.

   .. attribute:: null

      A representation of values that will be treated as NaN (or null)
      (see :ref:`usage` for more information).

      (``nullstr`` is a deprecated synonym of ``null``.)

   .. attribute:: fields 

      A comma-separated list of integers representing the ids of the
      time series groups to which the fields correspond; a zero
      indicates that the field is to be ignored. The first number
      corresponds to the first field after the date (and other fixed
      fields, such as the possible subset identifier; which are those
      fields depends on the file format, that is, the specific
      :class:`MeteologgerStorage` subclass) and should be the id of the
      corresponding time series group, or zero if the field is dummy;
      the second number corresponds to the second field after the fixed
      fields, and so on.
     
   .. attribute:: nfields_to_ignore

      This is used only in the simple format; it’s an integer that
      represents a number of fields before the date and time that should
      be ignored. The default is zero. If, for example, the date and
      time are preceded by a record id, set ``nfields_to_ignore=1`` to
      ignore the record id.

   .. attribute:: subset_identifiers
       
      This is used only on some :class:`MeteologgerStorage` subclasses.
      Some file formats mix two or more sets of measurements in the same
      file; for example, there may be ten-minute and hourly measurements
      in the same file, and for every 6 lines with ten-minute
      measurements there may be an additional line with hourly
      measurements (not necessarily the same variables). Such files have
      one or more additional distinguishing fields in each line, which
      helps to distinguish which set it is. We call these fields, which
      depend on the specific file format, the **subset identifiers**.

      :class:`MeteologgerStorage` (in fact its subclass) processes only
      one set of lines each time, and *subset_identifiers* specifies
      which subset it is. *subset_identifiers* is a comma-separated list
      of identifiers, and will cause :class:`MeteologgerStorage` (in
      fact its subclass) to ignore lines with different subset
      identifiers.

   .. attribute:: delimiter
   
   .. attribute:: decimal_separator
   
   .. attribute:: date_format

      Some file formats may be dependent on regional settings; these
      formats (i.e. these :class:`MeteologgerStorage` subclasses)
      support :attr:`delimiter`, :attr:`decimal_separator`, and
      :attr:`date_format`. :attr:`date_format` is specified in the same
      way as for strftime_.

      .. _strftime: http://docs.python.org/lib/module-time.html#time.strftime

   :class:`MeteologgerStorage` also has the following methods and
   properties:

   .. attribute:: MeteologgerStorage.timeseries_group_ids

      A list of time series group ids. This is extracted from
      :attr:`fields` (zeros are ignored).
   
   .. method:: MeteologgerStorage.get_recent_data(ts_group_id, ts_id, after_timestamp)

      Read the storage and extract the last part of the time series that
      is specified by *ts_group_id* and *ts_id*; specifically, provide
      the part that is more recent than *after_timestamp*. Returns that
      part of the time series as a pandas dataframe.

      :meth:`get_recent_data()` will actually extract the last part of
      all time series from storage, but only return the data for the
      requested time series. It will cache the rest and have them ready
      to return for subsequent calls. However, if in subsequent calls
      *after_timestamp* is earlier than in the first call, it will need
      to re-extract the time series from storage. Therefore, for better
      performance, use the smallest *after_timestamp* first.

   .. method:: _raise_error(line, msg)

      This is only meant to be used internally, i.e. called by
      subclasses whenever an error is found in a data file. The method
      raises an exception. *line* and *msg* are strings used in the
      error message.

   .. method:: _is_null(value)

      This is only meant to be called by subclasses whenever they want
      to check whether a given value is null.

   :class:`MeteologgerStorage` subclasses need to define the following
   methods:

   .. method:: _subset_identifiers_match(line)

      Return :const:`True` if *line* matches the
      :attr:`subset_identifiers`. The base method always returns
      :const:`True`, and subclasses only need to redefine it if the file
      format has subsets.

   .. method:: _extract_timestamp(line)

      Parse *line* and extract and return the date and time as a
      datetime_ object.

      .. _datetime: http://docs.python.org/library/datetime.html#datetime-objects
      
   .. method:: _extract_value_and_flags(line, seq)

      Extract the value and flags in sequence *seq* from *line*, and
      return it as a tuple.  :samp:`{seq}=1` is the first field after
      the fixed field, and so on (similar to :attr:`fields`).

   .. method:: get_required_parameters()

      Return a set of parameters that are required. The base method
      returns ``{"path", "storage_format", "file_fields"}`` and must be
      overridden to add items to the list if the subclass requires more
      parameters.

   .. method:: get_optional_parameters()
    
      Return a list of optional parameters. The base method returns
      ``{"null", "nullstr", "timezone"}`` and must be overridden if the
      subclass allows a different set.

.. _Logger: http://docs.python.org/library/logging.html
