# Route 53 DynDNS API

## This project is no longer active

Rather than upgrade this to Python3, I've moved to using
[ddns-route53](https://github.com/crazy-max/ddns-route53) running in a kube pod
in my home network.

## Overview

This project implements a DynDNS v2 API compatible front end for the AWS Route
53 service.  This allows most consumer routers and any other DynDNS compatible
clients to update `A` records in Route 53 hosted domains.

This is implemented as an AWS Lambda function fronted by the AWS API Gateway
service.  With updates once an hour, this service can be run entirely within
the free tier for these services.

## Prerequisites

* Amazon Web Services Account
* Domain hosted with AWS Route 53
* Client that speaks the DynDNS v2 API (most common)
* [Terraform](https://www.terraform.io/) (for install, tested with 0.9.2)

## Setup

### Step 1: Terraform Credentials

Terraform needs credentials in order to be able to create AWS resources.  The
simplest way to do this is to set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
and `AWS_DEFAULT_REGION` environment variables.  

Alternatively, if you have the AWS CLI tools installed and configured, you can
get away with setting just `AWS_DEFAULT_REGION` and Terraform will use the
credentials you've configured for use with them.

More details on other options can be found in the [Terraform documentation for
AWS
Authentication](https://www.terraform.io/docs/providers/aws/#authentication).

### Step 2: Configuration

You will need to configure at a minimum the username and password you want
clients to use for authentication.  The simplest way to do this is to copy
`terraform.tfvars.example` to `terraform.tfvars` then edit the file.

The `password` key is the only value in this file that must be changed.

The `username` key should be self-explanatory.

The default TTL on records when created or updated is 5 minutes (300 seconds).
If you wish to change that value then uncomment the `ttl` key in the config
file and set it to the number of seconds you want the TTL to be set to.

### Step 3: Deploying

There are two ways to deploy this to AWS:

#### Quick And Easy

Type `make`.  This will build the zip files for deployment and run `terraform
apply`.  If it works, the last line of output should contain the url for your
API endpoint like this:

    Outputs:

    url = https://24ufed9k37.execute-api.us-east-2.amazonaws.com/nic

#### Step By Step

1. Run `make zip`.  This will build the deployment packages for the main
   function and the custom authorizer.

2. Run `terraform plan`.  This will validate that your AWS credentials are
   working properly, evaluate existing state and describe what it will do when
   you deploy.

3. Run `terraform apply`.  This will deploy the functions, API gateway and all
   other supporting resources.  If it works, the last line of output should
   contain the url for your API endpoint like this:


    Outputs:

    url = https://24ufed9k37.execute-api.us-east-2.amazonaws.com/nic

### Step 4: Configuring your client

Documenting the configuration for every possible client is impossible.  For the
most part this should work with any client that supports the DynDNS v2 API that
allows you to specify a different server name.  Generally you want to configure
just like any other DynDNS v2 API service, but make sure you specify the server
as the value returned in the last line of the `terraform apply` output.

Here is an example config that works with ddclient:

    daemon=1m
    syslog=yes
    ssl=yes
    use=if, if=eth0

    server=24ufed9k37.execute-api.us-east-2.amazonaws.com,protocol=dyndns2
    login=route53-ddns
    password=<password here>
    your.hostname.com

Example configuration for a Ubiquiti EdgeRouter:

    service {
        dns {
            dynamic {
                interface eth0 {
                    service dyndns {
                        host-name your.hostname.com
                        login route53-ddns
                        password <password here>
                        protocol dyndns2
                        server 24ufed9k37.execute-api.us-east-2.amazonaws.com
                    }
                }
            }
        }
    
## Updating

If you update this code, the simplest way to update is just to run `make`
again.  That will update deployment archives if needed and run `terraform
apply` for you automatically.

## Debugging

If you encounter errors being sent back to your client, there are a few things
to try.

First, check CloudWatch.  You should have a pair of log groups named
`/aws/lambda/route53-ddns` and `/aws/lambda/route53-ddns-authorizer`.  The
authorizer is used only for checking the username and password.  If it allows
access, then the main function will be called.  It can be helpful to manually
force an update and look to see if a new log event shows up in both the
authorizer and the main function.  If no log even shows up in either, the error
may be in the API Gateway itself.  Unfortunately this can be very difficult to
troubleshoot.  In theory you can enable CloudWatch log groups for API gateway,
but I've had limited success with this.

If you are getting logs for requests, but still can't figure out what is going
on, you should try turning on debug logging via the Terraform `debug` key.
This will enable debug level logging.  This can be a bit overwhelming, since it
includes all the boto3 logs, but generally has worked well for me.

You may also want to manually force an update via `curl`.  In this case the
output from the function or the error message returned may be helpful.  For
example:

    curl -v -G -d hostname=<hostname> https://route53-ddns:<password here>@<api endpoint>/nic/update

## Notes

* The Terraform plans don't currently support deploying to a endpoint in a
  custom domain.  It would be nice to add this in the future.

* The normal DynDNS v2 API endpoint path is `/nic/update`, but the function
  isn't particular about the path.  Anything under `/nic` will work, and you
  can configure a custom stage name via Terraform if you want a different base
  path.

## Known Issues

* Sometimes you may see an error like below when initially running `terraform apply`:

```
Error applying plan:

1 error(s) occurred:

* aws_api_gateway_deployment.deployment: 1 error(s) occurred:

* aws_api_gateway_deployment.deployment: Error creating API Gateway Deployment: BadRequestException: No integration defined for method
        status code: 400, request id: e32e0d75-1b02-11e7-ac81-e98a6fba3c24
```
This appears to be caused by a race condition during creation where the
integration is not yet fully created in AWS when the deployment is triggered.
Running `terraform apply` again will succeessfully execute the plan.

* When running Terraform in plan or apply mode, it will always report that the
  `aws_api_gateway_deployment.deployment` resource is changed.  This is
  intentional and is intended to force a deployment on every deploy.  This is
  needed current due to [Terraform issue
  #6613](https://github.com/hashicorp/terraform/issues/6613)

* Due to API Gateway limitations, Basic Authentication isn't implemented
  completely correctly.  This is because it's not possible for a custom
  authenticator to control the headers sent, so the `WWW-Authenticate` header
  cannot be sent back.  This isn't needed for DDClient or other clients that
  send the `Authorization` in the initial response.  Please let me know if you
  encounter any client that has problems with it.

* When a change is accepted, it is queued in Route 53 for update, but will
  still be pending for up to a few minutes.  Because of this when a change is
  submitted via the API it will always return with the "good" response instead
  of "nochg", even if the IP associated with the record hasn't changed.

## Running Tests

Tests are setup to be run via [tox](https://pypi.python.org/pypi/tox).  There
is one test environment for unit tests and another for PEP8 tests.  Once tox is
installed just run `tox` to run both.

## Author

Clayton O'Neill 
<clayton@oneill.net>
