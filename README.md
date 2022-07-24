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
anything, something which is of importance when the volume of log files is large.


## background

TODO


## installation

Install in the Log Archive account, in your main region.

Prerequisites:
* AWS CLI
* AWS SAM CLI
* Python 3.8 (if you have another version installed, change the default in the
  Globals section in `template.yaml.`)

Obtain your SSO temporary credentials from the login screenand paste them into your terminal.

Take a look at the Parameters section in `template.yaml` for an explanation of the parameters. Then rename `samconfig.toml.example` to `samconfig.toml`. Then do a:
```
sam build
```
followed by a first deploy command of:
```
sam deploy --guided --config-file=samconfig.toml
```
This will guide you interactively through setting the parameter overrides and then deploy the log aggregation application.

Next time you need to deploy or update, simply do a:
```
sam build && sam deploy
```
If you need to change the parameter overrides, you can do so by rerunning the --guided deployment, or you can simply change the overrides in `samconfig.toml` and just build and deploy using the shorter form.

## architecture

The Step Function has the following structure:

![](https://github.com/PeterBengtson/control-tower-log-aggregator/blob/main/docs-images/StateMachine.png?raw=true)

