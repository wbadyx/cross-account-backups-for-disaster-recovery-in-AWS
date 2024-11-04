import boto3
import os
import json

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    backup = boto3.client('backup')

    backup_job_id = event['detail']['backupJobId']
    job_details = backup.describe_backup_job(BackupJobId=backup_job_id)

    return {
        'backupJobId': backup_job_id,
        'recoveryPointArn': job_details['RecoveryPointArn'],
        'databaseArn': job_details['ResourceArn']
    }

