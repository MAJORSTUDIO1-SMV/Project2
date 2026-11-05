#!/usr/bin/env python3
"""
Download the public Hugging Face dataset visualizedata/price-currents-blocks (train split)
and save it unmodified as raw/price_currents_blocks.parquet
"""

from datasets import load_dataset
import pandas as pd
import os

# Load the dataset (train split)
print("Downloading visualizedata/price-currents-blocks (train split)...")
ds = load_dataset('visualizedata/price-currents-blocks', split='train')
print(f"Loaded {len(ds)} rows")

# Convert to pandas DataFrame
df = ds.to_pandas()

# Save unmodified
os.makedirs('raw', exist_ok=True)
df.to_parquet('raw/price_currents_blocks.parquet', index=False)
print(f"Saved to raw/price_currents_blocks.parquet")

# Print statistics
print(f"\n=== Dataset Statistics ===")
print(f"Number of rows: {len(df)}")
print(f"Column names: {list(df.columns)}")

# Number of rows per block_type
if 'block_type' in df.columns:
    print(f"\nRows per block_type:")
    print(df['block_type'].value_counts().to_string())

# Number of unique filenames
if 'filename' in df.columns:
    print(f"\nNumber of unique filenames: {df['filename'].nunique()}")

# Number of rows per year (from filename)
if 'filename' in df.columns:
    # Extract year from filename pattern: newspaper_id_YYYY-MM-DD_edition.pdf
    import re
    year_pattern = re.compile(r'_(\d{4})-\d{2}-\d{2}_')
    df['year'] = df['filename'].str.extract(year_pattern)[0].astype('Int64')
    print(f"\nRows per year:")
    year_counts = df['year'].value_counts().sort_index()
    for year, count in year_counts.items():
        print(f"  {year}: {count}")

# How many Table blocks contain at least one digit in block_markdown
if 'block_type' in df.columns and 'block_markdown' in df.columns:
    table_blocks = df[df['block_type'] == 'Table']
    if len(table_blocks) > 0:
        has_digit = table_blocks['block_markdown'].str.contains(r'\d', na=False)
        print(f"\nTable blocks: {len(table_blocks)}")
        print(f"Table blocks with at least one digit in block_markdown: {has_digit.sum()}")
    else:
        print("\nNo Table blocks found")

print("\nDone!")