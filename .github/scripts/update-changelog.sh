#!/bin/bash
# Update CHANGELOG.md with new entry
#
# Usage:
#   ./update-changelog.sh --version 0.3.38 --entry changelog-entry.md [--dry-run]

set -e

# Configuration
CHANGELOG_HEADER_LINES=7  # Number of header lines in CHANGELOG.md before entries begin

VERSION=""
ENTRY_FILE=""
DRY_RUN=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --version)
      VERSION="$2"
      shift 2
      ;;
    --entry)
      ENTRY_FILE="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

if [ -z "$VERSION" ] || [ -z "$ENTRY_FILE" ]; then
  echo "Usage: $0 --version <version> --entry <file> [--dry-run]"
  exit 1
fi

if [ ! -f "$ENTRY_FILE" ]; then
  echo "Error: Entry file not found: $ENTRY_FILE"
  exit 1
fi

if [ ! -f "CHANGELOG.md" ]; then
  echo "Error: CHANGELOG.md not found in current directory"
  exit 1
fi

TODAY=$(date +%Y-%m-%d)
ENTRY_CONTENT=$(cat "$ENTRY_FILE")

# Create new entry with version and date
NEW_ENTRY="
## [v${VERSION}] - ${TODAY}

${ENTRY_CONTENT}
"

if [ "$DRY_RUN" = true ]; then
  echo "DRY RUN MODE - No files will be modified"
  echo ""
  echo "Would insert the following entry into CHANGELOG.md:"
  echo "========================================"
  echo "$NEW_ENTRY"
  echo "========================================"
  echo ""
  echo "After line ${CHANGELOG_HEADER_LINES} of CHANGELOG.md"
  exit 0
fi

# Create temporary files
TEMP_CHANGELOG=$(mktemp)
HEADER_FILE=$(mktemp)

# Extract header (first N lines)
head -n $CHANGELOG_HEADER_LINES CHANGELOG.md > "$HEADER_FILE"

# Build new changelog
cat "$HEADER_FILE" > "$TEMP_CHANGELOG"
echo "$NEW_ENTRY" >> "$TEMP_CHANGELOG"
tail -n +$((CHANGELOG_HEADER_LINES + 1)) CHANGELOG.md >> "$TEMP_CHANGELOG"

# Replace original with new version
mv "$TEMP_CHANGELOG" CHANGELOG.md

# Cleanup
rm -f "$HEADER_FILE"

echo "CHANGELOG.md updated successfully"
echo "Version: v${VERSION}"
echo "Date: ${TODAY}"

