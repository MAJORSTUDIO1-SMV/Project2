#!/usr/bin/env python3
"""
Extract price rows from sn84024736_1805-06-04_1.pdf (Richmond, dollars, inline text).
Regex rules only, no LLM. Schema: price_observation_schema.json
"""

import re
import json
import pandas as pd

# Load the page
df = pd.read_parquet('raw/price_currents_pages.parquet')
row = df[df['filename'] == 'sn84024736_1805-06-04_1.pdf'].iloc[0]
text = str(row['new_ocr_text'])
filename = row['filename']
newspaper_id = 'sn84024736'
page_number = int(row['page_number'])
ocr_run_id = row['OCR_run_ID']
issue_date = '1805-06-04'
year = 1805

# Metadata
newspaper_title = 'Richmond Enquirer'
publication_city = 'Richmond'
publication_state = 'VA'
publication_lat = 37.5407
publication_lon = -77.4360
region = 'South'
within_13_colonies = True
market_place = 'RICHMOND PRICE CURRENT'
price_list_id = filename.replace('.pdf', '')
source_dataset = 'price_currents_pages'
page_url = f'https://chroniclingamerica.loc.gov/lccn/{newspaper_id}/{issue_date}/ed-1/seq-{page_number}/'

# Extract price section
price_section_match = re.search(r'Richmond Prices Current\.\s+D\.\s*C\.\s*D\.\s*C\.\s*(.+?)(?:\n\s*Just|\n\s*A NEW|$)', text, re.DOTALL | re.IGNORECASE)
if not price_section_match:
    price_section_match = re.search(r'Richmond Prices Current\.\s*(.+?)(?:\n\s*Just|\n\s*A NEW|$)', text, re.DOTALL | re.IGNORECASE)

price_text = price_section_match.group(1) if price_section_match else ''
print(f'Extracted: {price_text[:300]}...')

# Known items with expected units
known_items = [
    ('TOBACCO', 'cwt', 'cwt', 1, 'tobacco'),
    ('FLOUR', 'bbl', 'bbl', 1, 'flour_bread'),
    ('WHEAT', 'bushel', 'bu', 1, 'grain'),
    ('INDIAN CORN', 'bushel', 'bu', 1, 'grain'),
    ('WHISKEY', 'gallon', 'gal', 1, 'drink'),
    ('BACON', 'lb', 'lb', 1, 'meat'),
    ('HEMP', 'ton', 'ton', 1, 'textile'),
    ('BAR IRON', 'ton', 'ton', 1, 'metals'),
]

rows = []
for item, unit_printed, unit_norm, unit_qty, category in known_items:
    # For BAR IRON, capture to end of price section (it has trailing numbers)
    # For others, capture up to double-space
    if item == 'BAR IRON':
        pattern = rf'{re.escape(item)}\s+(.+?)(?:\n|$)'
    else:
        pattern = rf'{re.escape(item)}\s+(.+?)(?:\s{{2,}}|$)'
    match = re.search(pattern, price_text)
    if match:
        price_str = match.group(1).strip()
        rows.append({
            'item': item,
            'price_str': price_str,
            'unit_printed': unit_printed,
            'unit_normalized': unit_norm,
            'unit_quantity': unit_qty,
            'category': category,
            'raw_text': f'{item} {price_str}'
        })
        print(f'Found: {item} -> {price_str}')

# Parse D.C. price string
def parse_dc_price(price_str):
    """Parse D.C. price: handles '5 50 a 6', '8 a 9 50', '50 a 60', '15', '180 200 110'"""
    price_str = price_str.strip()

    # Split on 'a' for range
    if ' a ' in price_str.lower():
        parts = re.split(r'\s+[aA]\s+', price_str)
        low_str, high_str = parts[0].strip(), parts[1].strip()
    else:
        low_str = high_str = price_str

    def parse_single(s):
        nums = s.strip().split()
        if len(nums) == 1:
            return float(nums[0])
        elif len(nums) == 2:
            return float(nums[0]) + float(nums[1]) / 100
        elif len(nums) == 3:
            # e.g., "180 200 110" - ambiguous; treat as 180-200 range, ignore third
            return float(nums[0]) + float(nums[1]) / 100
        return None

    low = parse_single(low_str)
    high = parse_single(high_str)
    return low, high, low_str, high_str

observations = []
for i, r in enumerate(rows, 1):
    low_val, high_val, low_printed, high_printed = parse_dc_price(r['price_str'])

    item = r['item']
    item_normalized = item.title()
    if item == 'INDIAN CORN':
        item_normalized = 'Corn'
    elif item == 'BAR IRON':
        item_normalized = 'Bar Iron'

    # Determine if cents vs dollars
    # Heuristic: per-lb items with prices 10-99 are likely cents
    price_scale = 'dollars_cents'
    currency_as_printed = 'D. C.'
    needs_review = False
    review_reason = ''

    if item == 'BACON' and low_val is not None and 10 <= low_val <= 99:
        # 50-60 cents per lb is reasonable; 50-60 dollars is not
        price_scale = 'cents'
        currency_as_printed = 'cents'
        needs_review = True
        review_reason = 'BACON price 50 a 60 likely cents per lb (not dollars); price_scale set to cents'
        low_val = low_val / 100
        high_val = high_val / 100

    if item == 'BAR IRON' and ' 200 ' in r['price_str'] and ' 110' in r['price_str']:
        needs_review = True
        review_reason = 'BAR IRON has three numbers (180 200 110) - ambiguous; parsed as 180-200 range'

    obs = {
        'observation_id': f'{price_list_id}_{i:03d}',
        'price_list_id': price_list_id,
        'source_dataset': source_dataset,
        'filename': filename,
        'newspaper_id': newspaper_id,
        'newspaper_title': newspaper_title,
        'page_number': page_number,
        'ocr_run_id': ocr_run_id,
        'page_url': page_url,
        'raw_text': r['raw_text'],
        'issue_date': issue_date,
        'year': year,
        'price_date_stated': None,
        'repeated_notice': False,
        'publication_city': publication_city,
        'publication_state': publication_state,
        'publication_lat': publication_lat,
        'publication_lon': publication_lon,
        'region': region,
        'within_13_colonies': within_13_colonies,
        'market_place': market_place,
        'item_as_printed': item,
        'item_normalized': item_normalized,
        'item_category': r['category'],
        'item_qualifier': '',
        'in_basket': True,
        'unit_as_printed': r['unit_printed'],
        'unit_normalized': r['unit_normalized'],
        'unit_quantity': r['unit_quantity'],
        'price_low_as_printed': low_printed,
        'price_high_as_printed': high_printed,
        'price_low_value': low_val,
        'price_high_value': high_val,
        'price_low_pounds': None,
        'price_low_shillings': None,
        'price_low_pence': None,
        'price_high_pounds': None,
        'price_high_shillings': None,
        'price_high_pence': None,
        'price_scale': price_scale,
        'currency_as_printed': currency_as_printed,
        'currency_basis': 'unknown',
        'price_type': 'market',
        'row_kind': 'goods_price',
        'availability_note': '',
        'remark': f'D.C. column: {low_printed} = {low_val}' if low_val else '',
        'layout_type': 'inline_text',
        'parse_method': 'regex',
        'confidence': 'low' if needs_review else 'high',
        'needs_review': needs_review,
        'review_reason': review_reason,
    }
    observations.append(obs)

# Save
import os
os.makedirs('clean', exist_ok=True)
with open('clean/observations_pilot.json', 'w') as f:
    json.dump(observations, f, indent=2)

print(f'\n=== Extracted {len(observations)} rows ===')
for obs in observations:
    print(f"\n  {obs['observation_id']}: {obs['item_as_printed']} = {obs['price_low_as_printed']} a {obs['price_high_as_printed']} -> {obs['price_low_value']}-{obs['price_high_value']} ({obs['price_scale']})")
    print(f"    unit: {obs['unit_as_printed']}, category: {obs['item_category']}, needs_review: {obs['needs_review']} ({obs['review_reason']})")
    print(f"    raw_text: {obs['raw_text']}")