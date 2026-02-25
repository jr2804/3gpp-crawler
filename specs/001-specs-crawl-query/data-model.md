# Data Model

## Specification

- **Purpose**: Canonical specification identity and core metadata.
- **Key fields**:
  - `spec_number` (canonical dotted format, e.g., 26.132)
  - `spec_number_compact` (undotted format, e.g., 26132)
  - `spec_type` (e.g., TS, TR)
  - `title`
  - `status`
  - `working_group`
  - `series` (e.g., 26_series)
  - `latest_version`
- **Validation**:
  - `spec_number` normalized to dotted form.
  - `spec_number_compact` derived from `spec_number`.

## SpecificationSourceRecord

- **Purpose**: Source-specific metadata snapshots.
- **Key fields**:
  - `spec_number` (FK to Specification)
  - `source_name` (e.g., 3gpp, whatthespec)
  - `source_identifier` (e.g., specificationId for 3GPP portal)
  - `metadata_payload` (raw or normalized JSON)
  - `versions` (list of available versions from the source)
  - `fetched_at`
- **Validation**:
  - `source_name` constrained to known sources.
  - `versions` stored in descending order for easy "latest" lookup.

## SpecificationVersion

- **Purpose**: Concrete spec revision details.
- **Key fields**:
  - `spec_number` (FK to Specification)
  - `version` (e.g., 19.0.0)
  - `file_name` (e.g., 26132-j00.zip)
  - `source_name` (FK to SpecificationSourceRecord)
- **Validation**:
  - `version` must match a parsed version from metadata.

## SpecificationDownload

- **Purpose**: Download and extraction outcomes per version.
- **Key fields**:
  - `spec_number` (FK to Specification)
  - `version` (FK to SpecificationVersion)
  - `download_url`
  - `checkout_path`
  - `document_path`
  - `attachment_paths`
  - `doc_only_used`
  - `outcome_status` (success, warning, failure)
  - `outcome_message`
  - `extracted_at`
- **Validation**:
  - `checkout_path` mirrors the 3GPP archive series layout.
  - `document_path` required on success.

## Relationships

- Specification 1---\* SpecificationSourceRecord
- Specification 1---\* SpecificationVersion
- SpecificationVersion 1---0..1 SpecificationDownload
