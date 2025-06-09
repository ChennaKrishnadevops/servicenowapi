# Azure Log Monitor to ServiceNow REQ Automation

This Python script monitors Azure Blob Storage for application log files, scans them for error-related keywords, and automatically creates a ServiceNow Service Catalog Request (REQ) when issues are detected.

---

## Features

- Monitors Azure Blob Storage for new or updated log files
- Detects error patterns such as `error`, `404`, `not found`, `failed`
- Tracks processed logs and offsets using Azure Table Storage
- Automatically creates a REQ in ServiceNow using the Service Catalog API

---

## Prerequisites

- Python 3.7 or higher
- Azure Storage Account with:
  - Blob container for storing logs
  - Table storage for tracking processed logs
- ServiceNow instance with a configured catalog item for REQ creation

---

## Installation

Install the required Python packages:
pip3 install azure-storage-blob azure-data-tables azure-core
