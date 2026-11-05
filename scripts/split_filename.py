#!/usr/bin/env python3
"""
Split filename into newspaper_id, date (YYYY-MM-DD), and edition.
Expected pattern: {newspaper_id}_{YYYY-MM-DD}_{edition}.pdf
Example: sn83016082_1809-03-27_1.pdf → newspaper_id=sn83016082, date=1809-03-27, edition=1
"""

import re
import pandas as pd
import json
import os

# Pattern: newspaper_id (alphanumeric) + _ + date (YYYY-MM-DD) + _ + edition (digits) + .pdf
FILENAME_PATTERN = re.compile(r'^([a-zA-Z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d+)\.pdf$')


def parse_filename(filename: str) -> dict | None:
    """Parse a filename into components. Returns None if pattern doesn't match."""
    match = FILENAME_PATTERN.match(filename)
    if match:
        return {
            'newspaper_id': match.group(1),
            'date': match.group(2),
            'edition': int(match.group(3))
        }
    return None


def main():
    # Load the raw parquet
    df = pd.read_parquet('raw/price_currents_pages.parquet')
    print(f"Loaded {len(df)} rows from raw/price_currents_pages.parquet")

    # Parse filenames
    parsed = df['filename'].apply(parse_filename)

    # Check which rows didn't match
    mask_matched = parsed.notna()
    matched_count = mask_matched.sum()
    unmatched_count = (~mask_matched).sum()

    print(f"\nFilenames matching pattern: {matched_count}")
    print(f"Filenames NOT matching pattern: {unmatched_count}")

    if unmatched_count > 0:
        print("\nExamples of non-matching filenames:")
        unmatched_filenames = df.loc[~mask_matched, 'filename'].head(5)
        for fn in unmatched_filenames:
            print(f"  {fn}")

    # Add parsed columns to matched rows
    parsed_df = parsed[mask_matched].apply(pd.Series)
    df_matched = df[mask_matched].copy()
    df_matched = pd.concat([df_matched, parsed_df], axis=1)

    # Add text_length column
    df_matched['text_length'] = df_matched['new_ocr_text'].str.len()

    # Add first 500 chars of new_ocr_text
    df_matched['new_ocr_text_500'] = df_matched['new_ocr_text'].str[:500]

    # Sort by date for earliest selection
    df_matched['date_parsed'] = pd.to_datetime(df_matched['date'])
    df_sorted = df_matched.sort_values('date_parsed')

    # Select 10 earliest dates
    earliest_10 = df_sorted.head(10)

    # Select 10 random rows (excluding the earliest 10), seed=42
    remaining = df_sorted.iloc[10:]
    random_10 = remaining.sample(n=10, random_state=42)

    # Combine
    sample_20 = pd.concat([earliest_10, random_10]).reset_index(drop=True)

    # Select output columns
    output_cols = [
        'filename', 'newspaper_id', 'date', 'edition',
        'page_number', 'OCR_run_ID', 'text_length', 'new_ocr_text_500'
    ]
    sample_output = sample_20[output_cols]

    # Save to JSON
    os.makedirs('clean', exist_ok=True)
    sample_output.to_json('clean/sample_20.json', orient='records', indent=2)
    print(f"\nSaved {len(sample_output)} rows to clean/sample_20.json")

    # Show first 3 records
    print("\nFirst 3 records:")
    for i, row in sample_output.head(3).iterrows():
        print(f"\nRecord {i+1}:")
        for col in output_cols:
            val = row[col]
            if col == 'new_ocr_text_500':
                val = repr(val)
            print(f"  {col}: {val}")


if __name__ == '__main__':
    main()