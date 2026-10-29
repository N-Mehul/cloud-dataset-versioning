
import boto3
import base64
import csv
import io
import json
import uuid
import os
from datetime import datetime, timezone

s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")

BUCKET_NAME = "cloud-dataset-versioning-mht2026"
TABLE_NAME = "DatasetComparisonHistory"
DATASET_KEY = "customer_dataset.csv"

ALLOWED_ORIGIN = (
    "http://cloud-dataset-dashboard-mht2026.s3-website."
    "ap-south-1.amazonaws.com"
)

MAX_FILE_BYTES = 500_000


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": ALLOWED_ORIGIN,
            "Access-Control-Allow-Headers": "content-type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }


def parse_body(event):
    raw = event.get("body")

    if not raw:
        return {}

    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw).decode("utf-8")

    if isinstance(raw, dict):
        return raw

    return json.loads(raw)


def read_csv_version(key, version_id):
    result = s3.get_object(
        Bucket=BUCKET_NAME,
        Key=key,
        VersionId=version_id
    )

    content = result["Body"].read().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        raise ValueError("CSV must contain a header row.")

    return reader.fieldnames, list(reader)


def get_version_filename(version_id):
    try:
        result = s3.head_object(
            Bucket=BUCKET_NAME,
            Key=DATASET_KEY,
            VersionId=version_id
        )

        metadata = result.get("Metadata", {})
        return metadata.get("original-filename", DATASET_KEY)

    except Exception as error:
        print(f"Could not read filename metadata: {error}")
        return DATASET_KEY


def list_versions():
    result = s3.list_object_versions(
        Bucket=BUCKET_NAME,
        Prefix=DATASET_KEY
    )

    versions = []

    for item in result.get("Versions", []):
        if item["Key"] != DATASET_KEY:
            continue

        version_id = item["VersionId"]

        versions.append({
            "version_id": version_id,
            "filename": get_version_filename(version_id),
            "last_modified": item["LastModified"].isoformat(),
            "is_latest": item["IsLatest"],
            "size_bytes": item["Size"]
        })

    versions.sort(
        key=lambda item: item["last_modified"],
        reverse=True
    )

    return response(200, {"versions": versions})


def analyze_quality():
    result = s3.list_object_versions(
        Bucket=BUCKET_NAME,
        Prefix=DATASET_KEY
    )

    versions = [
        item for item in result.get("Versions", [])
        if item["Key"] == DATASET_KEY and item["IsLatest"]
    ]

    if not versions:
        return response(404, {
            "error": "No dataset version was found."
        })

    version_id = versions[0]["VersionId"]
    headers, rows = read_csv_version(DATASET_KEY, version_id)

    if not headers:
        return response(400, {
            "error": "CSV must contain a header row."
        })

    missing_cells = 0
    empty_columns = []

    for header in headers:
        values = [row.get(header) for row in rows]

        missing = sum(
            1 for value in values
            if value is None or not value.strip()
        )

        missing_cells += missing

        if values and missing == len(values):
            empty_columns.append(header)

    row_signatures = [
        json.dumps(row, sort_keys=True)
        for row in rows
    ]

    duplicate_rows = len(row_signatures) - len(set(row_signatures))

    age_column = next(
        (h for h in headers if h.strip().lower() == "age"),
        None
    )

    invalid_age_values = 0

    if age_column:
        for row in rows:
            value = (row.get(age_column) or "").strip()

            try:
                age = int(value)

                if age < 0 or age > 120:
                    invalid_age_values += 1

            except (ValueError, TypeError):
                invalid_age_values += 1

    total_cells = len(headers) * len(rows)

    missing_rate = (
        missing_cells / total_cells if total_cells else 0
    )

    duplicate_rate = (
        duplicate_rows / len(rows) if rows else 0
    )

    age_rate = (
        invalid_age_values / len(rows)
        if rows and age_column else 0
    )

    score = round(
        max(
            0,
            100 * (
                1
                - 0.5 * missing_rate
                - 0.3 * duplicate_rate
                - 0.2 * age_rate
            )
        ),
        1
    )

    return response(200, {
        "dataset": DATASET_KEY,
        "filename": get_version_filename(version_id),
        "version_id": version_id,
        "record_count": len(rows),
        "column_count": len(headers),
        "columns": headers,
        "missing_cells": missing_cells,
        "duplicate_rows": duplicate_rows,
        "empty_columns": empty_columns,
        "age_column_found": bool(age_column),
        "invalid_age_values": (
            invalid_age_values if age_column else None
        ),
        "quality_score": score,
        "analyzed_at": datetime.now(timezone.utc).isoformat()
    })


def upload_csv(data):
    encoded = data.get("content_base64")

    if not encoded:
        return response(400, {
            "error": "Select a CSV file to upload."
        })

    try:
        content = base64.b64decode(encoded, validate=True)

    except Exception:
        return response(400, {
            "error": "Invalid file encoding."
        })

    if len(content) > MAX_FILE_BYTES:
        return response(413, {
            "error": "CSV must be 500 KB or smaller."
        })

    filename = data.get("filename", DATASET_KEY)

    # Keep only the filename, not any local directory path.
    filename = str(filename).replace("\\", "/").split("/")[-1].strip()

    if not filename:
        filename = DATASET_KEY

    if not filename.lower().endswith(".csv"):
        return response(400, {
            "error": "Please upload a CSV file."
        })

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames

        if not headers or len(headers) < 2:
            return response(400, {
                "error": "CSV must have a header row and at least two columns."
            })

        rows = list(reader)

        if not rows:
            return response(400, {
                "error": "CSV must contain data rows."
            })

        if len(rows) > 5000:
            return response(400, {
                "error": "CSV must have 5,000 rows or fewer."
            })

        if any(None in row for row in rows):
            return response(400, {
                "error": "Rows must match the number of header columns."
            })

    except (UnicodeDecodeError, csv.Error):
        return response(400, {
            "error": "Could not read a valid UTF-8 CSV."
        })

    result = s3.put_object(
        Bucket=BUCKET_NAME,
        Key=DATASET_KEY,
        Body=content,
        ContentType="text/csv",
        Metadata={
            "original-filename": filename
        }
    )

    return response(200, {
        "message": "CSV uploaded successfully.",
        "dataset": DATASET_KEY,
        "filename": filename,
        "version_id": result.get("VersionId"),
        "record_count": len(rows)
    })


def compare_versions(data):
    key = data.get("key", DATASET_KEY)
    old_version = data.get("old_version_id")
    new_version = data.get("new_version_id")

    if key != DATASET_KEY:
        return response(400, {
            "error": "Invalid dataset key."
        })

    if not old_version or not new_version:
        return response(400, {
            "error": "Provide old_version_id and new_version_id."
        })

    if old_version == new_version:
        return response(400, {
            "error": "Choose two different versions."
        })

    _, old_rows = read_csv_version(key, old_version)
    _, new_rows = read_csv_version(key, new_version)

    old_set = {
        json.dumps(row, sort_keys=True)
        for row in old_rows
    }

    new_set = {
        json.dumps(row, sort_keys=True)
        for row in new_rows
    }

    added = [
        json.loads(row)
        for row in sorted(new_set - old_set)
    ]

    removed = [
        json.loads(row)
        for row in sorted(old_set - new_set)
    ]

    result = {
        "comparison_id": str(uuid.uuid4()),
        "dataset": key,
        "old_version_id": old_version,
        "new_version_id": new_version,
        "old_record_count": len(old_rows),
        "new_record_count": len(new_rows),
        "added_records": added,
        "removed_records": removed,
        "compared_at": datetime.now(timezone.utc).isoformat()
    }

    dynamodb.Table(TABLE_NAME).put_item(
        Item={
            "comparison_id": result["comparison_id"],
            "dataset": key,
            "old_version_id": old_version,
            "new_version_id": new_version,
            "old_record_count": result["old_record_count"],
            "new_record_count": result["new_record_count"],
            "added_records": json.dumps(
                added, ensure_ascii=False
            ),
            "removed_records": json.dumps(
                removed, ensure_ascii=False
            ),
            "compared_at": result["compared_at"]
        }
    )

    return response(200, result)


def lambda_handler(event, context):
    try:
        route = event.get("routeKey", "")

        method = (
            event.get("requestContext", {})
            .get("http", {})
            .get("method", "POST")
        )

        if method == "OPTIONS":
            return response(200, {"message": "CORS preflight successful."})

        if method == "GET" and route == "GET /versions":
            return list_versions()

        if method == "GET" and route == "GET /quality":
            return analyze_quality()

        data = parse_body(event)

        if method == "POST" and route == "POST /upload":
            return upload_csv(data)

        if method == "POST" and route == "POST /compare":
            return compare_versions(data)

        return response(404, {
            "error": "Route not found."
        })

    except json.JSONDecodeError:
        return response(400, {
            "error": "Invalid JSON request."
        })

    except Exception:
        import traceback
        print("Request failed:")
        traceback.print_exc()

        return response(500, {
            "error": "Request failed. Check Lambda CloudWatch logs."
        })
