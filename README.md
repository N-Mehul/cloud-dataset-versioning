# Cloud Dataset Versioning

### A Cloud-Based System for Dataset Version Control, Comparison and Quality Analysis

## 1. Project Overview

Cloud Dataset Versioning is a cloud-based application designed to manage and track changes in CSV datasets. It allows users to upload datasets, maintain previous versions, compare dataset versions, and analyze data quality through a web dashboard.

The project uses Amazon Web Services (AWS) to provide cloud storage, backend processing, API communication, and comparison history management.

## 2. Objectives

- Store CSV datasets securely in Amazon S3.
- Maintain previous dataset versions using S3 Versioning.
- Compare two dataset versions to identify added and removed records.
- Analyze data quality by checking missing values, duplicate rows, empty columns, and invalid age values.
- Store comparison history in Amazon DynamoDB.
- Provide a centralized web dashboard for accessing project features.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Amazon S3 | Stores datasets and their versions |
| AWS Lambda | Processes uploads, comparisons, and quality checks using Python |
| Amazon API Gateway | Provides HTTP endpoints for dashboard requests |
| Amazon DynamoDB | Stores dataset comparison history |
| HTML | Structures the dashboard |
| CSS | Styles the dashboard |
| JavaScript | Supports frontend interactions and API communication |
| Python | Implements backend processing logic |

## 4. System Architecture

The application follows a serverless cloud architecture.

**Workflow:**

Web Dashboard → Amazon API Gateway → AWS Lambda → Amazon S3 and Amazon DynamoDB

- **Web Dashboard:** Allows users to interact with the application.
- **Amazon API Gateway:** Receives HTTP requests from the dashboard.
- **AWS Lambda:** Executes backend operations.
- **Amazon S3:** Stores CSV files and preserves previous versions when versioning is enabled.
- **Amazon DynamoDB:** Stores comparison metadata for later review.

## 5. Main Features

### Dataset Version Management
Stores CSV datasets in Amazon S3 and uses S3 Versioning to preserve earlier versions of the same object.

### Dataset Comparison
Compares selected dataset versions and identifies records added or removed between versions.

### Data Quality Analysis
Checks datasets for missing values, duplicate rows, empty columns, and invalid age values.

### Comparison History
Stores comparison metadata in Amazon DynamoDB to support traceability and review of previous comparison operations.

### Web Dashboard
Provides a centralized interface for uploading datasets and viewing version information, comparison results, and data-quality metrics.

## 6. AWS Resources

- **Lambda Function:** `DatasetVersionComparator`
- **DynamoDB Table:** `DatasetComparisonHistory`
- **API Gateway:** `CloudDatasetVersioningAPI`
- **Dataset S3 Bucket:** `cloud-dataset-versioning-mht2026`
- **Dashboard S3 Bucket:** `cloud-dataset-dashboard-mht2026`
- **AWS Region:** Asia Pacific (Mumbai), `ap-south-1`

## 7. API Endpoints

The application uses the following API Gateway routes:

| HTTP Method | Endpoint | Purpose |
|---|---|---|
| POST | `/upload` | Upload a CSV dataset |
| POST | `/compare` | Compare dataset versions |
| GET | `/versions` | Retrieve available dataset versions |
| GET | `/quality` | Perform data-quality analysis |

**Department:** Computer Science and Engineering  
**Institution:** NMIMS
