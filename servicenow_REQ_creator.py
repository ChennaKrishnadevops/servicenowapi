import os
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from azure.core.credentials import AzureNamedKeyCredential
from datetime import datetime, timezone
import requests

# Configuration from environment variables
account = os.getenv("AZURE_STORAGE_ACCOUNT")
key = os.getenv("AZURE_STORAGE_KEY")
container = os.getenv("CONTAINER_NAME")
table_name = os.getenv("TABLE_NAME")
keywords = ["error", "404", "not found", "failed"]

# ServiceNow credentials and catalog item
servicenow_url = os.getenv("SERVICENOW_URL")
servicenow_user = os.getenv("SERVICENOW_USER")
servicenow_password = os.getenv("SERVICENOW_PASSWORD")
catalog_item_sys_id = os.getenv("SERVICENOW_CATALOG_ITEM_SYS_ID")  # Required

# Azure credentials
blob_service = BlobServiceClient(account_url=f"https://{account}.blob.core.windows.net", credential=key)
credential = AzureNamedKeyCredential(account, key)
table_service = TableServiceClient(endpoint=f"https://{account}.table.core.windows.net", credential=credential)
table_client = table_service.get_table_client(table_name)

def is_processed(blob_name, last_modified):
    try:
        entity = table_client.get_entity(partition_key="logs", row_key=blob_name)
        stored_time = datetime.fromisoformat(entity["ProcessedTime"]).replace(tzinfo=timezone.utc)
        last_modified = last_modified.replace(tzinfo=timezone.utc)
        return stored_time >= last_modified, int(entity["LastProcessedOffset"])
    except Exception as e:
        print(f"No offset found for blob {blob_name}, starting from offset 0. Error: {e}")
        return False, 0

def mark_processed(blob_name, last_modified, offset):
    entity = {
        "PartitionKey": "logs",
        "RowKey": blob_name,
        "ProcessedTime": last_modified.isoformat(),
        "LastProcessedOffset": str(offset)
    }
    print(f"Saving entity for blob {blob_name}: {entity}")
    table_client.upsert_entity(entity)
    print(f"Successfully upserted entity for blob {blob_name}")

def create_ticket(blob_name, content):
    url = f"{servicenow_url}/api/sn_sc/servicecatalog/items/{catalog_item_sys_id}/order_now"

    payload = {
        "sysparm_id": catalog_item_sys_id,
        "sysparm_quantity": "1",
        "variables": {
            "name": "App Failure Auto Request",
            "short_description": f"Issue in log file: {blob_name}",
            "description": f"<p>{content[:4000]}</p>",
            "requested_for": "javascript:gs.getUserID();",
            "needed_by": datetime.now().strftime("%Y-%m-%d")
        }
    }

    response = requests.post(
        url,
        auth=(servicenow_user, servicenow_password),
        headers={"Content-Type": "application/json"},
        json=payload
    )

    if response.status_code == 200:
        result = response.json().get("result", {})
        print(f"✅ REQ: {result.get('request_number')} | RITM: {result.get('request_item_number')}")
    else:
        print(f"❌ Failed to create REQ: {response.status_code} - {response.text}")

def process_logs():
    container_client = blob_service.get_container_client(container)
    for blob in container_client.list_blobs():
        blob_client = container_client.get_blob_client(blob)
        props = blob_client.get_blob_properties()
        last_modified = props['last_modified']

        processed, last_offset = is_processed(blob.name, last_modified)
        if processed:
            continue

        content = blob_client.download_blob(offset=last_offset).readall().decode('utf-8').lower()
        if not content:
            continue

        new_errors = [line for line in content.splitlines() if any(k in line for k in keywords)]
        if new_errors:
            create_ticket(blob.name, "\n".join(new_errors[:10]))

        mark_processed(blob.name, last_modified, last_offset + len(content))

if __name__ == "__main__":
    process_logs()
