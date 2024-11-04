import boto3
import json
import os

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    rds = boto3.client('rds')
    sns = boto3.client('sns')
    target_account = os.environ['TARGET_ACCOUNT_ID']
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    
    target_snapshot_id = event['targetSnapshotId']
    
    try:
        # 共享快照到目标账号
        rds.modify_db_snapshot_attribute(
            DBSnapshotIdentifier=target_snapshot_id,
            AttributeName='restore',
            ValuesToAdd=[target_account]
        )
        
        # 发送成功通知
        message = f"Successfully shared snapshot {target_snapshot_id} with account {target_account}"
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject='RDS Snapshot Share Success',
            Message=message
        )
        
        return {
            'status': 'completed',
            'sharedSnapshotId': target_snapshot_id,
            'targetAccount': target_account
        }
        
    except Exception as e:
        # 发送失败通知
        error_message = f"Failed to share snapshot {target_snapshot_id} with account {target_account}. Error: {str(e)}"
        sns.publish(
            TopicArn=sns_topic_arn,
            Subject='RDS Snapshot Share Failed',
            Message=error_message
        )
        raise e
