# Change Log

## v1.2.0
    * Auxiliary log file copy strategy used when all log files are > 200K.
    * Bulk deletes now used to speed up deletion of log file originals.
    * State machine to process historical logs. See template.yaml for details.

## v1.1.1
    * Fixed continuation bug. Now this utility handles log files of any size and any number.

## v1.1.0
    * Release v1.1.0.

## v1.0.9
    * Continuation mechanism in place to avoid lambda timeouts for large log files
      or large amounts of log files.

## v1.0.8
    * Flow change: first the main logs, then the additional logs. Parallelism in the
      latter temporarily set to 1 and debug printouts added.

## v1.0.7
    * The filler file is now exactly 5MB in size and sparse.

## v1.0.0
    * Initial release.
