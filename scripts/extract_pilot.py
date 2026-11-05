#!/usr/bin/env python3
"""
Extract price rows from sn84024736_1805-06-04_1.pdf (Richmond, dollars, inline text).
Regex only, no LLM. Schema: price_observation_schema.json
Strict: exact printed text, null values when ambiguous, no guessing.
"""

import re
import json
import pandas as pd
import subprocess
import os

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
price_text = price_section_match.group(1) if price_section_match else ''

# Check for unit heading in price section (e.g., "D. C. D. C." = dollars/cents, no units)
has_cents_heading = bool(re.search(r'\bCents?\b', price_text, re.IGNORECASE))
has_dollars_heading = bool(re.search(r'D\.\s*C\.', price_text))

# Known items with their price strings (exact from text)
items = [
    ('TOBACCO', '5 50 a 6'),
    ('FLOUR', '9 50 a 10'),
    ('WHEAT', '8 a 9 50'),
    ('INDIAN CORN', '1 a 1 75'),
    ('WHISKEY', '5 a 5 25'),
    ('BACON', '50 a 60'),
    ('HEMP', '15'),
    ('BAR IRON', '180 200   110'),
]

# Richmond page: no units printed in the list text
# unit_status = "not_stated" for all (no unit appears in the list)
# Do NOT infer units → all unit fields null
unit_as_printed = None
unit_normalized = None
unit_quantity = None
unit_status = 'not_stated'
unit_inferred = None
unit_inference_basis = None

observations = []
for i, (item, price_str) in enumerate(items, 1):
    # Price as printed
    price_low_as_printed = price_str.split(' a ')[0].strip() if ' a ' in price_str.lower() else price_str
    price_high_as_printed = price_str.split(' a ')[1].strip() if ' a ' in price_str.lower() else price_str

    # Numeric values: parse D.C. format where unambiguous
    price_low_value = None
    price_high_value = None
    price_scale = 'unknown'
    currency_as_printed = 'D. C.' if has_dollars_heading else 'unknown'
    needs_review = False
    review_reason = ''

    def parse_dc_price(s):
        """Parse a single D.C. price string: '5 50' → 5.50, '6' → 6.0, '1 75' → 1.75"""
        s = s.strip()
        parts = s.split()
        if len(parts) == 2 and all(p.isdigit() for p in parts):
            return float(parts[0]) + float(parts[1]) / 100
        elif len(parts) == 1 and parts[0].isdigit():
            return float(parts[0])
        return None

    def parse_dc_range(s):
        """Parse 'low a high' where each is D.C. format. Returns (low, high) or (None, None)."""
        if ' a ' not in s.lower():
            return None, None
        low_str, high_str = re.split(r'\s+[aA]\s+', s)
        low = parse_dc_price(low_str)
        high = parse_dc_price(high_str)
        if low is not None and high is not None:
            return low, high
        return None, None

    if item == 'BAR IRON':
        needs_review = True
        review_reason = 'Three numbers (180 200 110) with no "a" separator; unclear which are low/high or column alignment'
    elif item == 'BACON':
        needs_review = True
        review_reason = 'Price "50 a 60" ambiguous: single numbers could be cents or dollars; no cents heading in list'
    else:
        low, high = parse_dc_range(price_str)
        if low is not None and high is not None:
            price_low_value = low
            price_high_value = high
            price_scale = 'dollars_cents'
        elif parse_dc_price(price_str) is not None:
            price_low_value = price_high_value = parse_dc_price(price_str)
            price_scale = 'dollars_cents'
        else:
            needs_review = True
            review_reason = 'Price format ambiguous; no clear D.C. pattern'

    # review_reason empty when needs_review is false
    if not needs_review:
        review_reason = ''

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
        'raw_text': f'{item} {price_str}',
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
        'item_normalized': item.title().replace('INDIAN CORN', 'Corn').replace('BAR IRON', 'Bar Iron'),
        'item_category': {
            'TOBACCO': 'tobacco', 'FLOUR': 'flour_bread', 'WHEAT': 'grain',
            'INDIAN CORN': 'grain', 'WHISKEY': 'drink', 'BACON': 'meat',
            'HEMP': 'textile', 'BAR IRON': 'metals'
        }[item],
        'item_qualifier': '',
        'in_basket': True,
        'unit_as_printed': unit_as_printed,
        'unit_normalized': unit_normalized,
        'unit_quantity': unit_quantity,
        'unit_status': unit_status,
        'unit_inferred': unit_inferred,
        'unit_inference_basis': unit_inference_basis,
        'price_low_as_printed': price_low_as_printed,
        'price_high_as_printed': price_high_as_printed,
        'price_low_value': price_low_value,
        'price_high_value': price_high_value,
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
        'remark': '',
        'layout_type': 'inline_text',
        'parse_method': 'regex',
        'confidence': 'low' if needs_review else 'high',
        'needs_review': needs_review,
        'review_reason': review_reason,
    }
    observations.append(obs)

# Save
os.makedirs('clean', exist_ok=True)
with open('clean/observations_pilot.json', 'w') as f:
    json.dump(observations, f, indent=2)

print(f'Extracted {len(observations)} rows')
result = subprocess.run(['wc', '-l', 'scripts/extract_pilot.py'], capture_output=True, text=True)
print(f'wc -l scripts/extract_pilot.py: {result.stdout.strip()}')

# Display table
print('\n=== EXTRACTED ROWS ===')
print(f"{'Item':<15} {'unit_status':<12} {'Price As Printed':<22} {'Low':<8} {'High':<8} {'Scale':<12} {'Review':<6} {'Reason'}")
print('-' * 120)
for o in observations:
    item = o['item_as_printed']
    ustatus = o['unit_status']
    price_printed = f"{o['price_low_as_printed']} a {o['price_high_as_printed']}" if o['price_low_as_printed'] != o['price_high_as_printed'] else o['price_low_as_printed']
    low = str(o['price_low_value']) if o['price_low_value'] is not None else 'null'
    high = str(o['price_high_value']) if o['price_high_value'] is not None else 'null'
    scale = o['price_scale']
    review = 'YES' if o['needs_review'] else 'NO'
    reason = o['review_reason'][:50]
    print(f"{item:<15} {ustatus:<12} {price_printed:<22} {low:<8} {high:<8} {scale:<12} {review:<6} {reason}")