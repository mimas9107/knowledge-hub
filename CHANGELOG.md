# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Improved error logging in `scripts/index_documents.py` to include full traceback for processing exceptions
- Added detailed debug logging for parsing and embedding steps to aid in diagnosing document indexing failures
- Enhanced exception handling with step-by-step error reporting for document processing pipeline

### Added
- CLI tool `scripts/index_documents.py` for memory-optimized document indexing
  - Batch processing to prevent memory exhaustion (configurable batch size, default: 5)
  - Resume capability for interrupted indexing jobs using database state tracking
  - Progress tracking with database job management (`index_jobs` table)
  - Memory optimization strategies including:
    - File size limits (50MB default max per file)
    - Automatic memory cleanup after each document using garbage collection
    - Memory usage monitoring with configurable limits (default: 80% of available RAM)
    - Batch embedding processing (32 embeddings per batch) to reduce memory spikes
  - Independent from Flask app to avoid memory overhead
  - Support for dry-run mode for testing without actual processing
  - Comprehensive error handling and logging with timestamps
  - Command-line options:
    - `--resume`: Continue unfinished jobs (default)
    - `--full-reindex`: Re-index all documents
    - `--single-file PATH`: Process only specified file
    - `--batch-size N`: Files per batch (default: 5)
    - `--max-memory MB`: Memory limit in MB
    - `--dry-run`: Simulation mode
    - `--verbose`: Detailed output

### Tested
- Dry-run mode successfully processes 28 documents in batches
- Single file processing works correctly (39 chunks generated for test file)
- Resume functionality creates and tracks jobs in database
- Memory monitoring and cleanup mechanisms functional
- Progress tracking updates database correctly