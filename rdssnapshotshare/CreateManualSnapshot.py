import boto3
import json
import time
import os
from datetime import datetime, timedelta

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    rds = boto3.client('rds')

    # 清理旧快照
    retention_days = int(os.environ['RETENTION_DAYS'])
    cutoff_date = datetime.now() - timedelta(days=retention_days)

    # 获取所有手动快照
    snapshots = rds.describe_db_snapshots(
        SnapshotType='manual',
        IncludeShared=False
    )['DBSnapshots']

    # 使用环境变量中的前缀创建快照名称
    prefix = os.environ['SNAPSHOT_PREFIX']
    # 删除超过保留期的快照
    for snapshot in snapshots:
        print("Received eventrds:", snapshot)
        if (snapshot['DBSnapshotIdentifier'].startswith(prefix) and snapshot['SnapshotCreateTime'].replace(tzinfo=None) < cutoff_date):
            try:
                rds.delete_db_snapshot(
                    DBSnapshotIdentifier=snapshot['DBSnapshotIdentifier']
                )
                print(f"Deleted old snapshot: {snapshot['DBSnapshotIdentifier']}")
            except Exception as e:
                print(f"Error deleting snapshot: {str(e)}")

    # 使用新的创建快照
    recovery_point_arn = event['recoveryPointArn']
    source_snapshot_id = recovery_point_arn.split(':')[-2] + ':' + recovery_point_arn.split(':')[-1]
    timestamp = datetime.now().strftime('%Y-%m-%d-%H-%M')
    target_snapshot_id = f"{prefix}-{timestamp}"

    # 复制快照
    response = rds.copy_db_snapshot(
        SourceDBSnapshotIdentifier=source_snapshot_id,
        TargetDBSnapshotIdentifier=target_snapshot_id,
        CopyTags=True
    )

    return {
        'sourceSnapshotId': source_snapshot_id,
        'targetSnapshotId': target_snapshot_id,
        'backupJobId': event['backupJobId'],
        'databaseArn': event['databaseArn']
    }

