import boto3
import json

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))
    rds = boto3.client('rds')

    target_snapshot_id = event['targetSnapshotId']

    response = rds.describe_db_snapshots(
        DBSnapshotIdentifier=target_snapshot_id
    )

    snapshot_status = response['DBSnapshots'][0]['Status']

    return {
        **event,
        'snapshotReady': snapshot_status == 'available'
    }

