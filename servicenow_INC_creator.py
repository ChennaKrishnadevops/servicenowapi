import os
from azure.storage.blob import BlobServiceClient
from azure.data.tables import TableServiceClient
from azure.core.credentials import AzureNamedKeyCredential
from datetime import datetime
import requests

# Configuration from environment variables
account = os.getenv("AZURE_STORAGE_ACCOUNT")
key = os.getenv("AZURE_STORAGE_KEY")
container = os.getenv("CONTAINER_NAME")
table_name = os.getenv("TABLE_NAME")
keywords = ["error", "404", "not found", "failed"]

# ServiceNow credentials
servicenow_url = os.getenv("SERVICENOW_URL")
servicenow_user = os.getenv("SERVICENOW_USER")
servicenow_password = os.getenv("SERVICENOW_PASSWORD")

# Azure credentials
blob_service = BlobServiceClient(account_url=f"https://{account}.blob.core.windows.net", credential=key)
credential = AzureNamedKeyCredential(account, key)
table_service = TableServiceClient(endpoint=f"https://{account}.table.core.windows.net", credential=credential)
table_client = table_service.get_table_client(table_name)

def is_processed(blob_name, last_modified):
    try:
        entity = table_client.get_entity(partition_key="logs", row_key=blob_name)
        stored_time = datetime.fromisoformat(entity["Timestamp"])
        return stored_time >= last_modified.replace(tzinfo=None)
    except:
        return False

def mark_processed(blob_name, last_modified):
    entity = {
        "PartitionKey": "logs",
        "RowKey": blob_name,
        "Timestamp": last_modified.isoformat()
    }
    table_client.upsert_entity(entity)

def create_ticket(blob_name, content):
    data = {
        "short_description": f"Issue in log file: {blob_name}",
        "description": content[:4000],
        "category": "application",
        "subcategory": "log_error",
        "impact": "2",
        "urgency": "2"
    }
    response = requests.post(
        servicenow_url,
        auth=(servicenow_user, servicenow_password),
        headers={"Content-Type": "application/json"},
        json=data
    )
    if response.status_code == 201:
        print(f"✅ Ticket created for {blob_name}")
    else:
        print(f"❌ Failed to create ticket: {response.status_code} - {response.text}")

def process_logs():
    container_client = blob_service.get_container_client(container)
    for blob in container_client.list_blobs():
        blob_client = container_client.get_blob_client(blob)
        props = blob_client.get_blob_properties()
        last_modified = props['last_modified']
        print(f"last modified property:: {last_modified}")
        if is_processed(blob.name, last_modified):
            continue

        content = blob_client.download_blob().readall().decode('utf-8').lower()
        if any(k in content for k in keywords):
            create_ticket(blob.name, content)

        mark_processed(blob.name, last_modified)

if __name__ == "__main__":
    process_logs()
