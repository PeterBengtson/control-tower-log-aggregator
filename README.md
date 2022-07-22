# control-tower-log-aggregator

SAM project to combine small daily log files into larger daily log files, 
to make it possible to store them in Glacier without extra overhead and
avoiding prohibitive costs. AWS Control Tower is required. 

Apart from the standard Control Tower log buckets, this application can also 
process any arbitrary log buckets, as long as the log files in them have 
dates in their path/object name.

It can also either process in place in each source bucket, or move the results 
to a dedicated long-term storage bucket with sensible Glacier lifecycle settings.

Install in the Log Archive account, in your main region.

Note that the Step Function can take several arguments. If a function finds that the
data it's been called to compute already exists, it will simply return that result.
This means you can call the Step function with an explicit date or bucket, etc, without
invoking the whole machinery.

