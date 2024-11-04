import boto3
import json
import os
from datetime import datetime
from botocore.exceptions import ClientError

def send_sns_notification(sns_client, topic_arn, subject, message):
    """Send an SNS notification."""
    try:
        response = sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=json.dumps(message, indent=2)
        )
        print(f"SNS notification sent. MessageId: {response['MessageId']}")
    except Exception as e:
        print(f"Failed to send SNS notification: {str(e)}")

def modify_permissions(ec2_client, ami_id, snapshot_ids, target_account_id):
    """Modify AMI and snapshot permissions for sharing."""
    try:
        # Modify AMI launch permissions
        ec2_client.modify_image_attribute(
            ImageId=ami_id,
            LaunchPermission={'Add': [{'UserId': target_account_id}]}
        )

        # Modify snapshot permissions
        for snapshot_id in snapshot_ids:
            ec2_client.modify_snapshot_attribute(
                SnapshotId=snapshot_id,
                CreateVolumePermission={'Add': [{'UserId': target_account_id}]}
            )
    except ClientError as e:
        print(f"Failed to modify permissions: {str(e)}")
        raise

def lambda_handler(event, context):
    """Main handler for the Lambda function."""
    print("Received event:", json.dumps(event))

    # Initialize AWS clients
    backup = boto3.client('backup')
    ec2 = boto3.client('ec2')
    sns = boto3.client('sns')

    # Get environment variables
    sns_topic_arn = os.environ['SNS_TOPIC_ARN']
    target_account_id = os.environ['TARGET_ACCOUNT_ID']

    # Extract backup job details
    ami_id = event['resources'][0].split(':')[-1].replace('image/', '')
    backup_vault_name = event['detail']['backupVaultName']
    backup_job_id = event['detail']['backupJobId']
    backup_job = backup.describe_backup_job(BackupJobId=backup_job_id)
    completion_date = backup_job['CompletionDate'].isoformat()
    resource_type = event['detail']['resourceType']

    try:
        # Get AMI details to find associated snapshots
        ami_response = ec2.describe_images(ImageIds=[ami_id])
        snapshot_ids = [block['Ebs']['SnapshotId'] for block in ami_response['Images'][0]['BlockDeviceMappings']]

        # Modify permissions for AMI and snapshots
        modify_permissions(ec2, ami_id, snapshot_ids, target_account_id)

        # Prepare success message
        success_message = {
            'status': 'Success',
            'amiId': ami_id,
            'sharedWithAccount': target_account_id,
            'backupVault': backup_vault_name,
            'completionTime': completion_date,
            'resourceType': resource_type,
            'timestamp': datetime.now().isoformat()
        }

        # Send notification
        send_sns_notification(sns, sns_topic_arn, f"AMI {ami_id} Shared Successfully", success_message)
        print(f"Shared AMI {ami_id} with account {target_account_id}")

        return {
            'statusCode': 200,
            'body': f"成功共享AMI {ami_id} 并允许账户 {target_account_id} 创建快照卷"
        }

    except Exception as e:
        print(f"共享AMI失败: {str(e)}")
        error_message = {
            'status': 'Failed',
            'error': str(e),
            'amiId': ami_id,
            'timestamp': datetime.now().isoformat(),
            'stackTrace': str(e.__traceback__)
        }

        send_sns_notification(sns, sns_topic_arn, "AMI Sharing Failed - Error Occurred", error_message)
        raise

