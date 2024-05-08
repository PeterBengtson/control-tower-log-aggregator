# Foundation-control-tower-log-aggregator

<img src="https://github.com/PeterBengtson/control-tower-log-aggregator/blob/main/docs-images/logs.jpg?raw=true." align="right"/>
SAM project to combine small daily log files into larger daily log files, 
to make it possible to store them in Glacier without extra overhead, thereby
avoiding prohibitive costs. AWS Control Tower is required. 

Apart from the standard Control Tower log buckets, this application can also 
process any arbitrary log buckets, as long as the log files in them have 
dates in their path/object name.

It can also either process in place in each source bucket, or move the results 
to a dedicated long-term storage bucket with sensible Glacier lifecycle settings.

This is a serverless solution, meaning there are no instances or clusters to
maintain. Also, all copying is done entirely within S3, without down- or uploading 
log files, something which is of importance when the volume of log files is large.

If you are running Control Tower v2.8 to v3.0, this application also provides a 
workaround for a serious AWS misconfiguration of the standard install 
Control Tower access log bucket. You may have many millions of log files you really 
don't need in there, so if you are running Control Tower v2.8 to v3.0, do check.
(AWS finally fixed their misconfiguration in v3.1.)

This application will recognise the changed file paths for Control Tower v3.0 or later
and adapt accordingly. It is to be noted that the Control Tower team changed the
file paths for _all_ log files in v3.0, not just for CloudTrail and CloudTrail-Digest,
but also for Config logs. The latter, moreover, is an undocumented change.


## Background

### The Problem 
Computer logs vary significantly in size from system to system, from log type to log
type, and even from day to day. They can span from a few hundred bytes to terabytes
in size. This is in itself not a problem, as you pay per byte on AWS. 

However, if you need to keep your logs around for a long time,
size issues will become a very tangible problem when trying to reduce costs
by moving logs to Glacier deep storage. The reason for this is that 40K of extra metadata
is added _to each log file_ in the process and that there are fairly high one-time transfer 
costs incurred, again per file. Furthermore, there are corresponding per-file costs associated 
with retrieving items from Glacier.

This means that there is a cutoff below which it is a very bad idea to store files in Glacier.
In fact, doing so may increase S3 costs dramatically, to the point where Glacier
becomes much more expensive than just leaving the files in Standard or Standard IA. It's
not a "slight increase" either, we're talking magnitudes. This is something that engineers
surprisingly often aren't aware of, only realising it post-fact when the AWS bill arrives.

The cutoff lies around 200K. Below 200K, the savings in storage costs are outweighed by
the class transfer costs and the storage cost of the extra added 40K. In other words,
if you have a 1 GB file you transfer to Glacier, the overhead will be minimal and the cost
savings manifest themselves immediately. However, if you instead try to store the same 1 GB 
of data as 1 million files of 1K in size, your total costs will increase by several magnitudes. 
There's a plethora of articles on the web about this; Google is your friend here. It's a known problem.

### The Solution
This application runs every night, concatenating the log files from the previous day 
into larger files more suited for Glacier storage. It also saves these new larger files in 
the Standard Infrequent Access (STANDARD_IA) storage class to further reduce costs. 
The original files are deleted (with all their versions). This results, in the vast majority 
of cases, in files larger than 200K. If configured to use a common destination bucket, 
the application sets up long-term storage properly per combined log item, only transferring
them to Glacier if they exceed the 200K limit, otherwise it simply leaves them in STANDARD_IA.

The 200K limit is of course configurable, as is the number of days before log files are 
transferred to Glacier (default 90 days), and the total number of days after which data is to 
expire altogether (default 3650 days).

The application can also aggregate log files from other types of log buckets in your Log Archive
account, as long as they have parsable dates in their name/key/path. Such log buckets would
typically include VPC Flow logs, CloudWatch logs, load balancer logs, CloudFront logs, 
GuardDuty logs, and log bucket S3 access logs, but they may be anything. This application will
collect all such logs from disparate sources and store them in a consistent directory structure.

The file size problem is one that needs to be solved in any system required to store logs for
a long time. There seems to be a remarkable lack of solutions to this problem, given that every
system needs to collect various types of logs from member accounts and store them in a central
log archive. The few solutions I have seen out there also involve running and maintaining 
instances or containers, which nowadays is clunky and expensive old tech for Foundation-level
tasks such as this. This solution, on the other hand, is entirely serverless.


## Architecture

### The Step Function
Every night at 1 AM, an AWS Step Function is triggered to process the log files produced for the 
last day. It has the following structure:

<img src="https://github.com/PeterBengtson/control-tower-log-aggregator/blob/main/docs-images/StateMachine.png?raw=true." width="500"/>

Parallel processing is used to optimise log processing times. 

The main logs are processed in parallel, and in each account the three main log types 
(`CloudTrail`, `CloudTrail-Digest`, `Config`) are in their turn also processed in parallel. 
This means that AWS Step Functions will allocate resources in parallel dynamically to 
optimise the process as much as possible. 

The number of accounts processed at a time can be changed in the `combine_log_files.asl.yaml` 
configuration file; look for `Process Accounts` and then `MaxConcurrency` which both have a 
value of 0. Change them as you see fit. (These numbers can unfortunately not be parametrised.)

The number of auxiliary log buckets processed at a time can likewise be changed in 
`Process Other Logs`. It is by default set to 10.

### Storage Classes
This application handles storage classes and class changes in the following way:

1. STANDARD - this is the default storage class in which the vast majority of log files
   are originally created
2. STANDARD_IA - all files produced by this application use this storage class
3. DEEP_ARCHIVE - the final storage class in Glacier for log files >= 200K.

As the application deletes the original files after having aggregated them into larger files,
the vast majority of all recent log files will be in STANDARD_IA, not in STANDARD. 
Originals using STANDARD only live for a day. This also results in substantial cost savings, 
as STANDARD_IA is about half the price of STANDARD.

### Log File Combination Algorithm
AWS S3 surprisingly offers no built-in support for concatenating files of any sort. This is always
left to the individual developer. The obvious brute-force approach of concatenating log files together 
in lambda or instance memory doesn't scale well enough here and also presents problems when it comes 
to large log files, memory sizes, and the fairly conservative maximum size for lambda output. 

It's also not ideal from a cost perspective as transfer costs and times will become significant. 
There are also security implications stemming from the fact that logs may contain sensitive 
information that never must end up in any other logs. So the less the contents of the log files
is in transit, the better.

There is one way in which data can be copied in place within S3, however, and that is by leveraging 
so-called multipart uploads. They can be done entirely within the S3 service, 
thus avoiding shuffling data to and from lambdas or instances altogether. However, multipart uploads 
require all files except the last one in the list of files to be 5 MB in size or larger, something
we can never guarantee with log files.

To get around the 5 MB limitation, the application first creates a 5 MB dummy file to use
as a starting point. It then adds one file at a time to that file until all component files have been 
aggregated.  

When all log files have been added, a final result file is produced by making a last multi-part upload
of the aggregation file to the final destination, but without the initial 5 MB of dummy data.

As the aggregation is done in place in a dedicated, unversioned scratch pad bucket, the process is fast even 
though a multipart upload is done for each component log file. S3 is a high-capacity storage engine that
really can take a pounding - it's designed for this sort of thing.

#### Aggregate or Copy
All main log files (`CloudTrail`, `CloudTrail-Digest`, `Config`) are always aggregated into larger files
according to the above algorithm as we know that it never will be the case that they all exceed the 200K
limit, especially not per account. 

With the additional log buckets specified by `OtherBuckets` we can make no such assumptions, which
means that there is room for an optimisation: if _all_ log files in a bucket exceed the configurable
minimum size for Glacier, these files are simply copied individually to the destination without aggregating 
them together into larger files, thus further saving processing time and S3 costs. This is very useful when
processing high-volume CloudWatch logs using utilities such as https://github.com/Delegat-AB/Foundation-CloudWatch2S3.


## Stand-Alone Installation

Install in the Log Archive account, in your main region.

Prerequisites:
* AWS CLI
* AWS SAM CLI
* Python 3.12 (if you have another version installed, change the default in the
  Globals section in `template.yaml.`)

Take a look at the Parameters section in `template.yaml` for an explanation of the parameters. Using a common
destination bucket is strongly recommended as this provides the cleanest structure from an administration perspective. 
It also allows the application to create a bucket configured for the purpose of optimising long-term storage from a cost perspective.

Before you begin, I strongly recommend you to clean up your existing log buckets.
This application processes log files from the previous day only, which means that files older than that
will remain where and as they are. You need to decide what to do with them if you have legal requirements 
to keep them.

This application will have no problems processing standard log files - CloudTrail, CloudTrail Digest, Config -
no matter how many files there are in the main Control Tower log bucket. With the buckets listed in `OtherBuckets` 
however, all log names must be processed every time and then filtered on the correct date, so make sure they 
don't contain millions of log files or the `get_files` lambda may time out. If you can, empty these buckets 
from all versions of all objects. This is easily done in the console using the Empty button or using the CLI.

If any log files are encrypted with KMS keys from other accounts, make sure the originating accounts allow the
Log Archive account to use them.

If you are using Control Tower version 2.8 to 3.0, clean out the entire contents of the Control Tower log bucket
access log bucket (which has a name similar to `aws-controltower-s3-access-logs-111122223333-xx-xxxxx-1`) 
right before you begin installation of this application.

When you are ready to install, rename `samconfig.toml.example` to `samconfig.toml`, obtain your SSO temporary credentials from the login screen and paste them into your terminal, then enter:
```console
sam build
```
followed by a first deployment command of:
```console
sam deploy --guided
```
This will guide you interactively through setting the parameter overrides and then deploy the log aggregation application.

Next time you need to deploy or update the application, simply do a:
```console
sam build && sam deploy
```
If you need to change the parameter overrides, you can do so by running `sam deploy --guided` again, or you can simply change the overrides in `samconfig.toml` and just build and deploy using the shorter form given above.


## Installation as Part of Delegat Foundation

It's the usual configuration in `Delegat-Install` and then `./deploy`. Or just let `Delegat-Install` handle it using a `./deploy-all Foundation`.


## Processing Old Main Logs

Version 1.2 of this application includes an AWS Step Function specifically designed to process the
mass of your existing historical main log files. As the daily processing involves the past day only, you
can use this Step Function to process the main log files produced by AWS Control Tower before that
date.

To do so, log in to the Log Archive and find the console for the Step Function called `ProcessHistoricalMainLogsSM`.
Run it with an input such as the following:

```
   {
     "start_date": "YYYY-MM-DD",
     "end_date": "YYYY-MM-DD",
     "bucket_name": "aws-controltower-logs-123456789012-xx-yyyy-1"
   }

```

Where the bucket name is the source bucket for old log files. It can be the same as your Control
Tower log bucket (which has the format `aws-controltower-logs-<account-id>-<region>`), or it can
be any other bucket containing AWS Control Tower main log files.

Note that only AWS Control Tower main log files (`CloudTrail`, `CloudTrail-Digest`, `Config`) will 
be processed by this batch mode processor. If your batch execution spans a long period
of time, or there is a large volume of log data, make sure that the execution does not run at the
same time as the main daily processor `CombineLogFilesSM`. You may want to disable the EventBridge
`cron` event that runs `CombineLogFilesSM` at 1 AM until the batch job is done.
