# control-tower-log-aggregator

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


## Background

Computer logs vary significantly in size from system to system, from log type to log
type, and even from day to day. They span from a few hundred bytes to several gigabytes
in size. This is in itself not a problem, as you pay per byte on AWS. 

However, if you need to keep your logs around for a long time,
size issues will become a very tangible problem when trying to reduce costs
by moving logs to Glacier deep storage. The reason for this is that 40K of extra storage
is added _to each log file_ in the process and that there are fairly high transfer costs, 
again per file, associated with moving files to permanent deep storage in Glacier. 
Furthermore, there are corresponding costs associated with retrieving items from Glacier, 
once again per file.

This means that there is a cutoff below which it is a very bad idea to store files in Glacier.
In fact, doing so may increase S3 costs dramatically, to the point where Glacier
becomes much more expensive than just leaving the files in Standard or Standard IA. It's
not a "slight increase" either, we're talking magnitudes. This is something that engineers
surprisingly often aren't aware of, only realising it post-fact when the AWS bill arrives.

The cutoff lies around 200K. Below 200K, the savings in storage costs is outweighed by
the storage class transfer costs and the storage cost of the extra added 40K. In other words,
if you have a 1 GB file you transfer to Glacier, the overhead will be minimal and the cost
savings manifest immediately. However, if you instead try to store the same 1 GB of data as
1 million files of 1K in size, your total costs will increase by several magnitudes. There's a
plethora of articles on the web about this; Google is your friend here. It's a known problem.

This application runs every night, concatenating the log files from the previous day 
into larger files more suited for Glacier storage. It also saves these new larger files in 
the Standard Infrequent Access (STANDARD_IA) storage class to further reduce costs. 
The original files are deleted (with all their versions). This results, in the vast majority 
of cases, in files larger than 200K. If configured to use a common destination bucket, 
the application sets up long-term storage properly per combined log item, only transferring
them to Glacier if they exceed the 200K limit, otherwise it simply leaves them in Standard_IA.

The 200K limit is of course configurable.

The daily main log files from Control Tower - CloudTrail, CloudTrail Digest, and Config logs -
are processed per account. For each of the three log types, you get one combined log file per
day and account. 

The application can also aggregate log files from other types of log buckets in your Log Archive
account, as long as they have parsable dates in their name/key/path. Such log buckets would
typically include CloudWatch logs, load balancer logs, CloudFront logs, GuardDuty logs, and
log bucket S3 access logs, but they may be anything. These logs will be combined into one log 
file per day per bucket, not per account.


## Architecture

TODO

The Step Function has the following structure:

<img src="https://github.com/PeterBengtson/control-tower-log-aggregator/blob/main/docs-images/StateMachine.png?raw=true." width="500"/>


## Installation

Install in the Log Archive account, in your main region.

Prerequisites:
* AWS CLI
* AWS SAM CLI
* Python 3.8 (if you have another version installed, change the default in the
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

If you have Control Tower version 2.8 or 2.9 installed, clean out the entire contents of the Control Tower log bucket
access log bucket (which has a name similar to `aws-controltower-s3-access-logs-111122223333-xx-xxxxx-1`) 
right before you begin installation of this application.

When you are ready to install, rename `samconfig.toml.example` to `samconfig.toml`, obtain your SSO temporary credentials from the login screen and paste them into your terminal, then enter:
```
sam build
```
followed by a first deployment command of:
```
sam deploy --guided
```
This will guide you interactively through setting the parameter overrides and then deploy the log aggregation application.

Next time you need to deploy or update the application, simply do a:
```
sam build && sam deploy
```
If you need to change the parameter overrides, you can do so by running `sam deploy --guided` again, or you can simply change the overrides in `samconfig.toml` and just build and deploy using the shorter form given above.
