variable "debug" {
  type        = "string"
  default     = "false"
  description = "Whether or not to enable debug logging in python lambda function"
}

variable "username" {
  type        = "string"
  description = "Username for basic authentication"
}

variable "password" {
  type        = "string"
  description = "Password for basic authentication"
}

variable "stage_name" {
  type        = "string"
  default     = "nic"
  description = "Endpoint name to use for stage"
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {
  current = true
}

data "aws_iam_policy_document" "lambda-assume-role-policy" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "role" {
  name               = "lambda_route53-ddns"
  assume_role_policy = "${data.aws_iam_policy_document.lambda-assume-role-policy.json}"
}

resource "aws_iam_role_policy_attachment" "lambda-basic-execution-role" {
  role       = "${aws_iam_role.role.name}"
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "route53fullaccess" {
  role       = "${aws_iam_role.role.name}"
  policy_arn = "arn:aws:iam::aws:policy/AmazonRoute53FullAccess"
}

resource "aws_lambda_function" "lambda" {
  description      = "DynDNS v2 API compatible front end for Route 53"
  function_name    = "route53-ddns"
  handler          = "route53_ddns.handler"
  runtime          = "python2.7"
  filename         = "route53-ddns.zip"
  source_code_hash = "${base64sha256(file("route53-ddns.zip"))}"
  role             = "${aws_iam_role.role.arn}"

  environment = {
    variables = {
      DEBUG = "${var.debug}"
    }
  }
}

resource "aws_lambda_function" "authorizer" {
  description      = "Authorizer for DynDNS v2 API compatible front end for Route 53"
  function_name    = "route53-ddns-authorizer"
  handler          = "route53_ddns_authorizer.handler"
  runtime          = "python2.7"
  filename         = "route53-ddns-authorizer.zip"
  source_code_hash = "${base64sha256(file("route53-ddns-authorizer.zip"))}"
  role             = "${aws_iam_role.role.arn}"

  environment = {
    variables = {
      DEBUG    = "${var.debug}"
      USERNAME = "${var.username}"
      PASSWORD = "${var.password}"
    }
  }
}

resource "aws_lambda_permission" "apigw_lambda" {
  statement_id  = "route53-ddns-sid"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.lambda.function_name}"
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:${aws_api_gateway_rest_api.api.id}/*/${aws_api_gateway_method.method.http_method}/"
}

resource "aws_lambda_permission" "apigw_lambda_authorizer" {
  statement_id  = "route53-ddns-authorizer-sid"
  action        = "lambda:InvokeFunction"
  function_name = "${aws_lambda_function.authorizer.function_name}"
  principal     = "apigateway.amazonaws.com"
}

resource "aws_api_gateway_rest_api" "api" {
  name        = "route53-ddns"
  description = "Proxy API for dyndns2 API Lambda"
}

resource "aws_api_gateway_authorizer" "apigw_authorizer" {
  name                             = "route53-ddns-authorizer"
  rest_api_id                      = "${aws_api_gateway_rest_api.api.id}"
  authorizer_uri                   = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.authorizer.arn}/invocations"
  authorizer_result_ttl_in_seconds = 3600
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = "${aws_api_gateway_rest_api.api.id}"
  parent_id   = "${aws_api_gateway_rest_api.api.root_resource_id}"
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "method" {
  rest_api_id   = "${aws_api_gateway_rest_api.api.id}"
  resource_id   = "${aws_api_gateway_resource.proxy.id}"
  http_method   = "ANY"
  authorization = "CUSTOM"
  authorizer_id = "${aws_api_gateway_authorizer.apigw_authorizer.id}"
}

resource "aws_api_gateway_integration" "integration" {
  rest_api_id             = "${aws_api_gateway_rest_api.api.id}"
  resource_id             = "${aws_api_gateway_resource.proxy.id}"
  http_method             = "${aws_api_gateway_method.method.http_method}"
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${aws_lambda_function.lambda.arn}/invocations"
}

resource "aws_api_gateway_deployment" "deployment" {
  depends_on = ["aws_api_gateway_method.method"]

  rest_api_id       = "${aws_api_gateway_rest_api.api.id}"
  stage_name        = "${var.stage_name}"
  stage_description = "Deployed at ${timestamp()}"
}

output "url" {
  value = "https://${aws_api_gateway_rest_api.api.id}.execute-api.${data.aws_region.current.name}.amazonaws.com/${var.stage_name}"
}
