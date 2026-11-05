#!/usr/bin/env python3
"""
Convert raw/price_currents_blocks.parquet to JSON files:
- clean/blocks_md.json: all blocks with selected keys
- clean/table_blocks_md.json: only Table blocks
"""

import pandas as pd
import json
import re
import os

# Load blocks
df = pd.read_parquet('raw/price_currents_blocks.parquet')
print(f"Loaded {len(df)} blocks")

# Extract newspaper_id and date from filename
FILENAME_PATTERN = re.compile(r'^([a-zA-Z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d+)\.pdf$')

def parse_filename(filename):
    match = FILENAME_PATTERN.match(filename)
    if match:
        return {
            'newspaper_id': match.group(1),
            'date': match.group(2),
            'edition': int(match.group(3))
        }
    return {'newspaper_id': None, 'date': None, 'edition': None}

parsed = df['filename'].apply(parse_filename)
df['newspaper_id'] = parsed.apply(lambda x: x['newspaper_id'])
df['date'] = parsed.apply(lambda x: x['date'])
df['year'] = pd.to_datetime(df['date'], errors='coerce').dt.year

# Build block_uid
df['block_uid'] = df['filename'] + '_' + df['block_id'].astype(str)

# Select columns for output
cols = ['block_uid', 'filename', 'newspaper_id', 'date', 'year', 'page_number', 'block_id', 'block_type', 'block_markdown']

# All blocks
all_blocks = df[cols].to_dict('records')

# Save all blocks
os.makedirs('clean', exist_ok=True)
with open('clean/blocks_md.json', 'w') as f:
    json.dump(all_blocks, f, indent=2)
print(f"Saved {len(all_blocks)} blocks to clean/blocks_md.json")

# Table blocks only
table_blocks = df[df['block_type'] == 'Table'][cols].to_dict('records')
with open('clean/table_blocks_md.json', 'w') as f:
    json.dump(table_blocks, f, indent=2)
print(f"Saved {len(table_blocks)} Table blocks to clean/table_blocks_md.json")

print("Done!")