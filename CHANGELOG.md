# Change Log

## v1.5.1
    * Corrected S3 client initialisation.

## v1.5.0
    * Performance optimization for CombineLogFilesFunction:
      * Increased memory allocation to 2048MB
      * Added S3 connection pooling with retry configuration

## v1.4.1
    * Added prefix data in debug printout.

## v1.4.0
    * Added `.python-version` file for pyenv.
    * Upgraded to Python 3.12.

## v1.3.1
    * Included the Control Tower bucket size on the dashboard.

## v1.3.0
    * Dashboard added.

## v1.2.1
    * Documented the new features in the README.

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

## v1.0.6
    * Fixed the 1B bug when aggregation regions are specified.

## v1.0.5
    * Specified boto3 version 1.33.12.

## v1.0.4
    * Added final slash to prefix string now required to work as a prefix.

## v1.0.3
    * Corrected bug to select no buckets when the prefix list is empty.

## v1.0.2
    * Refreshed deployment scripts.

## v1.0.1
    * Open-source credits and URLs
    * Fixed installer initial stackset creation.

## v1.0.0
    * Initial release.
