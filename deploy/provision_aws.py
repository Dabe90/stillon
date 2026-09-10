"""S3 Object Lock, DynamoDB live board, CloudFront door. Idempotent."""

from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-2"
ACCOUNT = "750390206396"
BUCKET = "stillon-harbor-light-750390206396"
TABLE = "stillon-desk"
OAC_NAME = "stillon-desk-oac"
ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web" / "static"


def _bucket(s3):
    try:
        s3.head_bucket(Bucket=BUCKET)
    except ClientError:
        s3.create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
            ObjectLockEnabledForBucket=True,
        )
        time.sleep(2)
    s3.put_public_access_block(
        Bucket=BUCKET,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )


def _table(ddb):
    existing = ddb.list_tables()["TableNames"]
    if TABLE in existing:
        return
    ddb.create_table(
        TableName=TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ],
        KeySchema=[
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ],
    )
    ddb.get_waiter("table_exists").wait(TableName=TABLE)


def _upload_static(s3):
    mapping = {
        WEB / "index.html": "index.html",
        WEB / "styles.css": "static/styles.css",
        WEB / "app.js": "static/app.js",
    }
    for src, key in mapping.items():
        body = src.read_bytes()
        ctype, _ = mimetypes.guess_type(src.name)
        s3.put_object(
            Bucket=BUCKET,
            Key=key,
            Body=body,
            ContentType=ctype or "application/octet-stream",
            CacheControl="max-age=60",
        )


def _oac(cf):
    listed = cf.list_origin_access_controls().get("OriginAccessControlList", {}).get("Items", [])
    for item in listed or []:
        if item.get("Name") == OAC_NAME:
            return item["Id"]
    created = cf.create_origin_access_control(
        OriginAccessControlConfig={
            "Name": OAC_NAME,
            "Description": "StillOn desk S3",
            "SigningBehavior": "always",
            "SigningProtocol": "sigv4",
            "OriginAccessControlOriginType": "s3",
        }
    )
    return created["OriginAccessControl"]["Id"]


def _bucket_policy(s3, distribution_id: str):
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowCloudFront",
                "Effect": "Allow",
                "Principal": {"Service": "cloudfront.amazonaws.com"},
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{BUCKET}/*",
                "Condition": {
                    "StringEquals": {
                        "AWS:SourceArn": f"arn:aws:cloudfront::{ACCOUNT}:distribution/{distribution_id}"
                    }
                },
            }
        ],
    }
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(policy))


def _distribution(cf, oac_id: str, lambda_url: str, secret: str) -> tuple[str, str]:
    host = lambda_url.replace("https://", "").rstrip("/")
    for dist in cf.list_distributions().get("DistributionList", {}).get("Items", []) or []:
        if dist.get("Comment") == "StillOn Harbor Light desk":
            return dist["Id"], dist["DomainName"]
    caller = f"stillon-desk-{int(time.time())}"
    created = cf.create_distribution(
        DistributionConfig={
            "CallerReference": caller,
            "Comment": "StillOn Harbor Light desk",
            "Enabled": True,
            "DefaultRootObject": "index.html",
            "Origins": {
                "Quantity": 2,
                "Items": [
                    {
                        "Id": "s3-stillon",
                        "DomainName": f"{BUCKET}.s3.{REGION}.amazonaws.com",
                        "S3OriginConfig": {"OriginAccessIdentity": ""},
                        "OriginAccessControlId": oac_id,
                    },
                    {
                        "Id": "lambda-stillon",
                        "DomainName": host,
                        "CustomOriginConfig": {
                            "HTTPPort": 80,
                            "HTTPSPort": 443,
                            "OriginProtocolPolicy": "https-only",
                            "OriginSslProtocols": {"Quantity": 1, "Items": ["TLSv1.2"]},
                        },
                        "CustomHeaders": {
                            "Quantity": 1,
                            "Items": [
                                {"HeaderName": "X-StillOn-Sweep", "HeaderValue": secret},
                            ],
                        },
                    },
                ],
            },
            "DefaultCacheBehavior": {
                "TargetOriginId": "s3-stillon",
                "ViewerProtocolPolicy": "redirect-to-https",
                "TrustedSigners": {"Enabled": False, "Quantity": 0},
                "ForwardedValues": {"QueryString": False, "Cookies": {"Forward": "none"}},
                "MinTTL": 0,
                "AllowedMethods": {
                    "Quantity": 2,
                    "Items": ["GET", "HEAD"],
                    "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
                },
                "Compress": True,
            },
            "CacheBehaviors": {
                "Quantity": 1,
                "Items": [
                    {
                        "PathPattern": "/api/*",
                        "TargetOriginId": "lambda-stillon",
                        "ViewerProtocolPolicy": "redirect-to-https",
                        "TrustedSigners": {"Enabled": False, "Quantity": 0},
                        "ForwardedValues": {
                            "QueryString": True,
                            "Headers": {"Quantity": 1, "Items": ["Content-Type"]},
                            "Cookies": {"Forward": "none"},
                        },
                        "MinTTL": 0,
                        "DefaultTTL": 0,
                        "MaxTTL": 0,
                        "AllowedMethods": {
                            "Quantity": 7,
                            "Items": ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"],
                            "CachedMethods": {"Quantity": 2, "Items": ["GET", "HEAD"]},
                        },
                        "Compress": False,
                    }
                ],
            },
        }
    )
    dist = created["Distribution"]
    return dist["Id"], dist["DomainName"]


def provision(lambda_url: str, secret: str) -> dict:
    s3 = boto3.client("s3", region_name=REGION)
    ddb = boto3.client("dynamodb", region_name=REGION)
    cf = boto3.client("cloudfront")
    _bucket(s3)
    _table(ddb)
    _upload_static(s3)
    oac_id = _oac(cf)
    dist_id, domain = _distribution(cf, oac_id, lambda_url, secret)
    _bucket_policy(s3, dist_id)
    return {
        "bucket": BUCKET,
        "table": TABLE,
        "cloudfront": f"https://{domain}",
        "distribution_id": dist_id,
    }
