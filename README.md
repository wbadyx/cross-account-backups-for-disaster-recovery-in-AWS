# Cross-Account Backups for Disaster Recovery in AWS

A comprehensive solution for setting up cross-account backups and disaster recovery (DR) in AWS, supporting S3, EC2, and RDS resources.

## 🎯 Disaster Recovery Objectives

- Build an efficient and cost-effective disaster recovery system in AWS
- Ensure business continuity and data security
- Recovery Time Objective (RTO): ≤ 12 hours
- Recovery Point Objective (RPO): ≤ 24 hours

## 🏗️ Solution Architecture

| Service | DR Strategy |
|---------|-------------|
| S3 | Cross-account replication within the same region with versioning and lifecycle management |
| EC2 | Cross-account AMI sharing within the same region with retention period |
| RDS | Cross-account snapshot sharing using AWS Backup service with retention period |

## 📋 Implementation Guide

### A. S3 Cross-Account Replication

1. Create source bucket (`ds-source-bucket-name`) with versioning enabled
2. Create target bucket (`ds-target-bucket-name`) with versioning enabled
3. Create replication rule in source bucket with role `s3crr_role_for_ds-source-bucket-name`
4. Configure bucket policies for both source and target buckets

<details>
<summary>Source Bucket IAM Role Policy</summary>

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": [
                "s3:ListBucket",
                "s3:GetReplicationConfiguration",
                "s3:GetObjectVersionForReplication",
                "s3:GetObjectVersionAcl",
                "s3:GetObjectVersionTagging",
                "s3:GetObjectRetention",
                "s3:GetObjectLegalHold"
            ],
            "Effect": "Allow",
            "Resource": [
                "arn:aws-cn:s3:::ds-source-bucket-name",
                "arn:aws-cn:s3:::ds-source-bucket-name/*",
                "arn:aws-cn:s3:::ds-target-bucket-name",
                "arn:aws-cn:s3:::ds-target-bucket-name/*"
            ]
        },
        {
            "Action": [
                "s3:ReplicateObject",
                "s3:ReplicateDelete",
                "s3:ReplicateTags",
                "s3:ObjectOwnerOverrideToBucketOwner"
            ],
            "Effect": "Allow",
            "Resource": [
                "arn:aws-cn:s3:::ds-source-bucket-name/*",
                "arn:aws-cn:s3:::ds-target-bucket-name/*"
            ]
        }
    ]
}
```
</details>

<details>
<summary>Target Bucket Policy</summary>

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "Set-permissions-for-objects",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws-cn:iam::AccountId:role/service-role/s3crr_role_for_ds-source-bucket-name"
            },
            "Action": [
                "s3:ReplicateObject",
                "s3:ReplicateDelete"
            ],
            "Resource": "arn:aws-cn:s3:::ds-target-bucket-name/*"
        },
        {
            "Sid": "Set permissions on bucket",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws-cn:iam::AccountId:role/service-role/s3crr_role_for_ds-source-bucket-name"
            },
            "Action": [
                "s3:GetBucketVersioning",
                "s3:PutBucketVersioning"
            ],
            "Resource": "arn:aws-cn:s3:::ds-target-bucket-name"
        }
    ]
}
```
</details>

### B. EC2 Cross-Account AMI Sharing

1. Create SNS topic `SharingNotifications`
2. Create IAM role `ShareBackupAMIRole` for Lambda
3. Create Lambda function `ShareBackupEC2AMI`
4. Configure EventBridge rule for AWS Backup job completion
5. Set up AWS Backup vault and backup jobs

<details>
<summary>Lambda IAM Role Policy</summary>

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "ec2:ModifySnapshotAttribute",
                "ec2:CreateTags",
                "ec2:DescribeSnapshots",
                "ec2:DescribeImages",
                "ec2:ModifyImageAttribute",
                "ec2:ModifySnapshotAttribute",
                "ec2:DescribeSnapshots",
                "ec2:CreateTags"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "backup:DescribeBackupJob",
                "backup:DescribeRecoveryPoint"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws-cn:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": "arn:aws-cn:sns:*:*:AMISharing*"
        }
    ]
}
```
</details>

#### Lambda Environment variables:
| KEY    | VALUE |
|---------|-------------|
| SNS | SharingNotifications ARN |
| TARGET_ACCOUNT_ID |  Cross-account ID |

<details>
<summary>Configure EventBridge rule</summary>

```code
aws events put-rule \
    --name "BackupJobCompletion" \
    --event-pattern '{        
        "source": ["aws.backup"],
        "detail-type": ["Backup Job State Change"],
        "detail": {
            "state": ["COMPLETED"],
           "resourceType": ["EC2"],
            "backupVaultName": ["ShareAMI"]
        }
    }' \
    --description "Trigger Lambda when AWS Backup jobs complete"

#Add-permission
aws lambda add-permission \
    --function-name ShareBackupEC2AMI \
    --statement-id EventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws-cn:events:cn-northwest-1:AccountId:rule/BackupJobCompletion

```
</details>

#### Create Backup vault `ShareAMI`


### C. RDS Cross-Account Snapshot Sharing

Implementation workflow:
1. AWS Backup completion
2. Get backup information
3. Create manual snapshot
4. Wait for snapshot availability
5. Share snapshot with target account

Setup steps:
1. Create Backup vault `ShareSnapshot`
2. Create SNS topic for notifications
3. Configure EventBridge rule
4. Create required IAM roles
5. Deploy Lambda functions:
   - GetBackupInfo
   - CreateManualSnapshot
   - CheckSnapshotStatus
   - ShareSnapshot
6. Create Step Functions state machine

<details>
<summary>Lambda IAM Role Policy</summary>

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "rds:CopyDBSnapshot",
                "rds:DeleteDBSnapshot",
                "rds:DescribeDBSnapshots",
                "rds:ModifyDBSnapshotAttribute"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "backup:DescribeBackupJob",
                "backup:DescribeRecoveryPoint"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            "Resource": "arn:aws-cn:logs:*:*:*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": "arn:aws-cn:sns:*:*:*"
        }
    ]
}

```
</details>

#### Lambda Environment variables:
|LambdaName |KEY | VALUE |
|---------|---------|-------------|
| CreateManualSnapshot|RETENTION_DAYS | How long will retention ? |
| CreateManualSnapshot|SNAPSHOT_PREFIX |  default `shared-backup`|
| ShareSnapshot|SNS_TOPIC_ARN |Backup-notifications ARN |
| ShareSnapshot|TARGET_ACCOUNT_ID | Cross-account ID |

<details>
<summary>StepFunction IAM Role Policy</summary>

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CloudWatchLogsFullAccess",
            "Effect": "Allow",
            "Action": [
                "logs:*",
                "cloudwatch:GenerateQuery"
            ],
            "Resource": "*"
        }
    ]
}
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": [
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:ShareSnapshot:*",
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:GetBackupInfo:*",
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:CheckSnapshotStatus:*",
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:CreateManualSnapshot:*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "lambda:InvokeFunction"
            ],
            "Resource": [
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:ShareSnapshot",
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:GetBackupInfo",
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:CheckSnapshotStatus",
                "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:CreateManualSnapshot"
            ]
        }
    ]
}
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "sns:Publish"
            ],
            "Resource": [
                "arn:aws-cn:sns:cn-northwest-1:AccountId:rds-backup-notifications"
            ]
        }
    ]
}
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "xray:PutTraceSegments",
                "xray:PutTelemetryRecords",
                "xray:GetSamplingRules",
                "xray:GetSamplingTargets"
            ],
            "Resource": [
                "*"
            ]
        }
    ]
}


```
</details>


<details>
<summary>Step Functions State Machine Definition</summary>

```json
{
  "Comment": "RDS Backup Share Workflow",
  "StartAt": "GetBackupInfo",
  "States": {
    "GetBackupInfo": {
      "Type": "Task",
      "Resource": "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:GetBackupInfo",
      "Next": "CreateManualSnapshot",
      "Retry": [
        {
          "ErrorEquals": [
            "States.TaskFailed"
          ],
          "IntervalSeconds": 30,
          "MaxAttempts": 3
        }
      ],
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Next": "NotifyError"
        }
      ]
    },
    "CreateManualSnapshot": {
      "Type": "Task",
      "Resource": "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:CreateManualSnapshot",
      "Next": "WaitForSnapshotReady",
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Next": "NotifyError"
        }
      ]
    },
    "WaitForSnapshotReady": {
      "Type": "Wait",
      "Seconds": 300,
      "Next": "CheckSnapshotStatus"
    },
    "CheckSnapshotStatus": {
      "Type": "Task",
      "Resource": "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:CheckSnapshotStatus",
      "Next": "IsSnapshotReady",
      "Retry": [
        {
          "ErrorEquals": [
            "States.TaskFailed"
          ],
          "IntervalSeconds": 30,
          "MaxAttempts": 3
        }
      ],
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Next": "NotifyError"
        }
      ]
    },
    "IsSnapshotReady": {
      "Type": "Choice",
      "Choices": [
        {
          "Variable": "$.snapshotReady",
          "BooleanEquals": true,
          "Next": "ShareSnapshot"
        }
      ],
      "Default": "WaitForSnapshotReady"
    },
    "ShareSnapshot": {
      "Type": "Task",
      "Resource": "arn:aws-cn:lambda:cn-northwest-1:AccountId:function:ShareSnapshot",
      "End": true,
      "Retry": [
        {
          "ErrorEquals": [
            "States.TaskFailed"
          ],
          "IntervalSeconds": 30,
          "MaxAttempts": 3
        }
      ],
      "Catch": [
        {
          "ErrorEquals": [
            "States.ALL"
          ],
          "Next": "NotifyError"
        }
      ]
    },
    "NotifyError": {
      "Type": "Task",
      "Resource": "arn:aws-cn:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws-cn:sns:cn-northwest-1:AccountId:rds-backup-notifications",
        "Subject": "RDS Snapshot Workflow Error",
        "Message.$": "States.Format('Error occurred in state: {}. Error: {}', $.Error, $.Cause)"
      },
      "End": true
    }
  }
}
```
</details>

#### Set up an EventBridge rule with Step Functions as the target, using the default role.
<details>
<summary>Configure EventBridge rule</summary>

```code
aws events put-rule \
    --name "RDSBackupJobCompletion" \
    --event-pattern '{
        "source": ["aws.backup"],
        "detail-type": ["Backup Job State Change"],
        "detail": {
            "state": ["COMPLETED"],
           "resourceType": ["RDS"],
            "backupVaultName": ["ShareSnapshot"]
        }
    }' \
    --description "Trigger StepFunctions when AWS Backup jobs complete"

```
</details>


## 🏗️ Architecture

![AWS Cross-Account Backup Architecture](assets/images/architecture.svg)

*Architecture diagram showing the cross-account backup workflow for S3, EC2, and RDS resources.*




## 💪 Solution Benefits

1. **Reduced Recovery Time**: Direct use of shared images eliminates environment rebuild time
2. **Consistency Assurance**: Complete system state preservation including OS, applications, and configurations
3. **Distributed Backup**: Enhanced reliability through cross-account redundancy
4. **Cost Optimization**: Resource sharing reduces duplicate storage and management costs
5. **Simplified Management**: Automated workflows reduce operational overhead
6. **Enhanced Security**: Fine-grained access control through AWS IAM roles and policies

## 📝 Prerequisites

- Multiple AWS accounts (source and target)
- Appropriate IAM roles and permissions
- AWS services: S3, EC2, RDS, Lambda, Step Functions, EventBridge, SNS
- AWS Backup service enabled

## 🚀 Getting Started

1. Clone this repository
2. Update the account IDs and region in the policy documents
3. Deploy the IAM roles and policies
4. Create the required AWS resources (S3 buckets, backup vaults, etc.)
5. Deploy the Lambda functions and Step Functions state machine
6. Configure EventBridge rules
7. Test the backup and sharing workflows

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
