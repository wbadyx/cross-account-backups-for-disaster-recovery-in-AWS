# cross-account-backups-for-disaster-recovery-in-AWS
To set up cross-account backups for disaster recovery (DR) in AWS
容灾目标
在 AWS 环境中构建高效且具有成本效益的容灾体系，确保业务的连续性和数据的安全性。
数据恢复时间目标（RTO）不超过 12 小时。
数据恢复点目标（RPO）不超过24 小时。

容灾方案	
S3	同区域跨账号复制，开启版本控制，设定生命周期管理。
EC2	同区域跨账号AMI 分享，设定保留天数。
RDS	同区域跨账号镜像分享，使用AWS Backup 服务备份，设定保留天数。

A.S3 CrossAccount Replication
1、创建ds-source-bucket-name，开启存储桶版本控制
2、创建ds-target-bucket-name，开启存储桶版本控制
3、在ds-source-bucket-name "管理" 创建复制规则
Role:s3crr_role_for_ds-source-bucket-name -> policy
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

4、在ds-target-bucket-name编辑桶策略
{
    "Version": "2012-10-17",
    "Id": "",
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

5、在s3://SourceBucket/crr/上传文件（1M大小），等待约三十秒后，文件复制到DestinationBucket/crr/下
查看复制对象状态
aws s3api head-object --bucket source-bucket-name --key object-key

B.Share EC2 AMI  to another account
0、创建SNS -  SharingNotifications
1、IAM：ShareBackupAMIRole
#Trusted entities
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
#Policy
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
2、Lambda
ShareBackupEC2AMI
#General configuration
Timeout  30sec
Triggers  EventBridge 
Execution role  ShareBackupAMIRole
Environment variables:
    SNS_TOPIC_ARN
    TARGET_ACCOUNT_ID
3、Event
# AWS Services events Backup ，注意event-pattern
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
    
    
添加lambda触发
aws lambda add-permission \
    --function-name ShareBackupEC2AMI \
    --statement-id EventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws-cn:events:cn-northwest-1:AccountId:rule/BackupJobCompletion

4、AWS Backup
创建Backup vault ShareAMI
创建备份任务

C.Share RDS SnapShot to another account
A[AWS Backup完成] --> B[GetBackupInfo获取备份信息]
B --> C[CreateManualSnapshot开始复制]
C --> D[等待5分钟]
D --> E[CheckSnapshotStatus检查状态]
E --> F{是否Available?}
F -->|否| D
F -->|是| G[ShareSnapshot分享快照]

1、创建 Backup-vault - ShareSnapshot
2、创建 SNS 主题
aws sns create-topic --name rds-backup-notifications
aws sns subscribe --topic-arn <SNS_TOPIC_ARN> --protocol email --notification-endpoint your-email@example.com
#arn:aws-cn:sns:cn-northwest-1:AccountId:rds-backup-notifications
3、创建 Event
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

目标：arn:aws-cn:states:cn-northwest-1::AccountId:stateMachine:MyStateMachine-l4k3lss2q 
Role:默认生成
4、IAM Role
Lambda: arn:aws-cn:iam::AccountId:role/ShareRDSBackupRole
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

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

StepFunction:arn:aws-cn:iam::AccountId:role/service-role/StepFunctions-MyStateMachine-l4k3lss2q-role-96dwxtnop
#Trusted entities
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "states.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

#Policy
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

5、EventBridge:arn:aws-cn:iam::AccountId:role/service-role/Amazon_EventBridge_Invoke_Step_Functions_317086871
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "events.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}

{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "states:StartExecution"
            ],
            "Resource": [
                "arn:aws-cn:states:cn-northwest-1:AccountId:stateMachine:MyStateMachine-l4k3lss2q"
            ]
        }
    ]
}

6、创建Lambda
GetBackupInfo.py
配置：30s

CreateManualSnapshot.py
配置：30s
ENV:
RETENTION_DAYS   3
SNAPSHOT_PREFIX  shared-backup
重试次数 0

CheckSnapshotStatus.py
配置：30s

ShareSnapshot.py
配置：30s
ENV:
SNS_TOPIC_ARN   arn:aws-cn:sns:cn-northwest-1:AccountId:rds-backup-notifications
TARGET_ACCOUNT_ID  123456789012

7、创建StepFunction
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



容灾优势
1、缩短恢复时间：其他账号无需重新构建相同的环境，直接使用分享的镜像即可，节省了大量的时间和资源。大大缩短了业务恢复的时间。
2、一致性保障：分享的镜像通常包含了完整的操作系统、应用程序和配置信息，确保了恢复后的系统环境与灾难发生前的状态高度一致。
3、分布式备份：跨账号镜像分享可以看作是一种分布式的备份方式。增加了备份的可靠性和冗余度。
4、资源共享节约成本：通过跨账号镜像分享，多个账号可以共享相同的镜像资源，避免了每个账号都单独进行镜像创建和存储所带来的成本开销。可以显著降低容灾备份的成本。
5、简化管理降低成本：通过自动化流程统一管理和维护分享的镜像，减少重复的工作，降低管理成本。
6、增强安全控制：AWS 提供了多种安全机制来确保跨账号镜像分享的安全性，例如通过 IAM 角色和权限策略的设置，可以精确控制哪些账号可以访问和使用共享的镜像。

