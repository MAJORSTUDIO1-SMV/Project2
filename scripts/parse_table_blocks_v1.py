#!/usr/bin/env python3
"""
Parse markdown pipe tables from price_currents_blocks into price observations.
Follows CLAUDE.md rules: exact printed prices, null values when ambiguous,
needs_review with reason, parse_method="table_parse".
"""

import json
import re
import pandas as pd
from typing import List, Dict, Optional, Tuple
import os

# Load table blocks
with open('clean/table_blocks_md.json') as f:
    table_blocks = json.load(f)

# Load pages for metadata
pages_df = pd.read_parquet('raw/price_currents_pages.parquet')

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

NEWSPAPER_META = {
    'sn82014782': {'title': 'The Weekly Aurora', 'city': 'Philadelphia', 'state': 'PA', 'lat': 39.9526, 'lon': -75.1652, 'region': 'Middle'},
    'sn83016072': {'title': 'Boston Gazette', 'city': 'Boston', 'state': 'MA', 'lat': 42.3601, 'lon': -71.0589, 'region': 'New England'},
    'sn83016081': {'title': 'Eastern Argus', 'city': 'Portland', 'state': 'ME', 'lat': 43.6591, 'lon': -70.2568, 'region': 'New England'},
    'sn83025442': {'title': 'Providence Gazette', 'city': 'Providence', 'state': 'RI', 'lat': 41.8240, 'lon': -71.4128, 'region': 'New England'},
    'sn83025588': {'title': 'The Impartial Gazetteer', 'city': 'New-York', 'state': 'NY', 'lat': 40.7128, 'lon': -74.0060, 'region': 'Middle'},
}

UNIT_MAP = {
    'bbl': 'bbl', 'barrel': 'bbl', 'barrels': 'bbl',
    'bu': 'bu', 'bushel': 'bu', 'bushels': 'bu', 'bush': 'bu',
    'lb': 'lb', 'lb.': 'lb', 'pound': 'lb', 'pounds': 'lb',
    'gal': 'gal', 'gallon': 'gal', 'gallons': 'gal',
    'cwt': 'cwt', 'hund': 'cwt', 'hundredweight': 'cwt', 'cwt.': 'cwt',
    'ton': 'ton', 'ton.': 'ton',
    'gal.': 'gal', 'lb.': 'lb', 'bbl.': 'bbl', 'bu.': 'bu', 'ton.': 'ton', 'cwt.': 'cwt',
    'cask': 'cask', 'box': 'box', 'bolt': 'bolt', 'piece': 'piece', 'dozen': 'bolt', 'keg': 'keg',
}

def parse_dc_price(price_str: str) -> Optional[float]:
    if not price_str or not price_str.strip():
        return None
    s = price_str.strip().replace('1/2', '.5').replace('1/4', '.25').replace('3/4', '.75')
    parts = s.split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return float(parts[0]) + float(parts[1]) / 100
    elif len(parts) == 1:
        try:
            return float(parts[0])
        except ValueError:
            return None
    return None

def parse_lsd_price(price_str: str) -> Optional[Tuple[float, int, int, int]]:
    parts = price_str.strip().split()
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        pounds = int(parts[0])
        shillings = int(parts[1])
        pence = int(parts[2])
        if shillings < 20 and pence < 12:
            decimal = pounds + shillings / 20 + pence / 240
            return (decimal, pounds, shillings, pence)
    return None

def parse_range_price(price_str: str) -> Optional[Tuple[float, float]]:
    s = price_str.replace('—', ' ').replace('-', ' ').replace('a', ' ').replace('to', ' ')
    parts = s.split()
    if len(parts) >= 2:
        low = parse_dc_price(parts[0])
        high = parse_dc_price(parts[-1])
        if low is not None and high is not None:
            return (low, high)
    return None

def parse_shilling_price(price_str: str) -> Optional[float]:
    s = price_str.strip().lower()
    lsd_match = re.search(r'(\d+)\s*l\.?\s*(\d+)\s*s\.?\s*(\d+)\s*d\.?', s)
    if lsd_match:
        pounds = int(lsd_match.group(1))
        shillings = int(lsd_match.group(2))
        pence = int(lsd_match.group(3))
        if shillings < 20 and pence < 12:
            return pounds + shillings / 20 + pence / 240
    sh_match = re.search(r'(\d+)\s*s\.?\s*(?:od\.?)?', s)
    if sh_match:
        shillings = int(sh_match.group(1))
        return shillings / 20
    sp_match = re.search(r'(\d+)\s*s\.?\s*(\d+)\s*d\.?', s)
    if sp_match:
        shillings = int(sp_match.group(1))
        pence = int(sp_match.group(2))
        if shillings < 20 and pence < 12:
            return shillings / 20 + pence / 240
    return None

def detect_price_scale_and_parse(price_str: str) -> Dict:
    result = {
        'price_low_value': None, 'price_high_value': None,
        'price_low_pounds': None, 'price_low_shillings': None, 'price_low_pence': None,
        'price_high_pounds': None, 'price_high_shillings': None, 'price_high_pence': None,
        'price_scale': 'unknown', 'currency_as_printed': '',
    }
    s = price_str.strip()
    if not s or s.lower() in ['none', 'unfaleable', 'unfair', '']:
        return result
    lsd_parsed = parse_lsd_price(s)
    if lsd_parsed:
        val, p, s_, d = lsd_parsed
        return {
            'price_low_value': val, 'price_high_value': val,
            'price_low_pounds': p, 'price_low_shillings': s_, 'price_low_pence': d,
            'price_high_pounds': p, 'price_high_shillings': s_, 'price_high_pence': d,
            'price_scale': 'pounds_shillings_pence', 'currency_as_printed': 'L. s. d.',
        }
    lsd_val = parse_shilling_price(s)
    if lsd_val is not None:
        return {
            'price_low_value': lsd_val, 'price_high_value': lsd_val,
            'price_low_pounds': None, 'price_low_shillings': None, 'price_low_pence': None,
            'price_high_pounds': None, 'price_high_shillings': None, 'price_high_pence': None,
            'price_scale': 'pounds_shillings_pence', 'currency_as_printed': 'L. s. d.',
        }
    range_parsed = parse_range_price(s)
    if range_parsed:
        low, high = range_parsed
        return {'price_low_value': low, 'price_high_value': high,
                'price_low_pounds': None, 'price_low_shillings': None, 'price_low_pence': None,
                'price_high_pounds': None, 'price_high_shillings': None, 'price_high_pence': None,
                'price_scale': 'dollars_cents', 'currency_as_printed': 'D. C.'}
    dc_parsed = parse_dc_price(s)
    if dc_parsed is not None:
        return {'price_low_value': dc_parsed, 'price_high_value': dc_parsed,
                'price_low_pounds': None, 'price_low_shillings': None, 'price_low_pence': None,
                'price_high_pounds': None, 'price_high_shillings': None, 'price_high_pence': None,
                'price_scale': 'dollars_cents', 'currency_as_printed': 'D. C.'}
    sh_val = parse_shilling_price(s)
    if sh_val is not None:
        return {'price_low_value': sh_val, 'price_high_value': sh_val,
                'price_low_pounds': None, 'price_low_shillings': None, 'price_low_pence': None,
                'price_high_pounds': None, 'price_high_shillings': None, 'price_high_pence': None,
                'price_scale': 'pounds_shillings_pence', 'currency_as_printed': 'L. s. d.'}
    return {'price_low_value': None, 'price_high_value': None,
            'price_low_pounds': None, 'price_low_shillings': None, 'price_low_pence': None,
            'price_high_pounds': None, 'price_high_shillings': None, 'price_high_pence': None,
            'price_scale': 'unknown', 'currency_as_printed': ''}

def extract_market_place(block_markdown: str) -> str:
    lines = block_markdown.split('\n')
    for line in lines[:5]:
        line_lower = line.lower()
        if 'price current' in line_lower or 'prices current' in line_lower:
            if ' at ' in line_lower:
                parts = line_lower.split(' at ')
                if len(parts) > 1:
                    return parts[1].strip('.,*#').title()
            if ' in ' in line_lower:
                parts = line_lower.split(' in ')
                if len(parts) > 1:
                    return parts[1].strip('.,*#').title()
            return line.strip('*#. ').title()
    return ''

def parse_table_block(block: Dict) -> List[Dict]:
    markdown = block['block_markdown']
    lines = markdown.split('\n')

    table_rows = []
    for line in lines:
        if line.strip().startswith('|'):
            table_rows.append(line.strip())

    if len(table_rows) < 3:
        return []

    header_line = table_rows[0]
    separator_line = table_rows[1]
    data_lines = table_rows[2:]

    header_cells = [c.strip() for c in header_line.split('|')[1:-1]]
    data_rows = []
    for line in data_lines:
        cells = [c.strip() for c in line.split('|')[1:-1]]
        if len(cells) >= 2:
            data_rows.append(cells)

    if not data_rows:
        return []

    num_cols = len(header_cells)
    print(f"  Columns: {header_cells}")

    # Find price column pairs - look for D C D C pattern or From/To
    price_col_pairs = []
    for i in range(num_cols - 1):
        cell = header_cells[i].lower()
        if any(x in header_cells[i] for x in ['d.', 'c.', 'cts', 'cents', 'dols', 'doll', 'from', 'to', 'price', 'l.', 's.', 'd.', '£', 'dols', 'cts', 'c.', 'd.']):
            if i + 1 < num_cols:
                price_col_pairs.append((i, i+1, f"col_{i}_{i+1}"))

    if not price_col_pairs and num_cols >= 3:
        # Try to infer from header text
        for i in range(num_cols - 1):
            if header_cells[i].strip() in ['D.', 'D', 'Dols', 'Dol', 'C.', 'C', 'Cts', 'Ct', 'Cents', 'Cent', 'From', 'To', 'L.', 'S.', 'D.', '£']:
                if i + 1 < num_cols:
                    price_col_pairs.append((i, i+1, f"inferred_{i}"))

    print(f"  Price column pairs: {price_col_pairs}")

    observations = []
    for row_idx, row_cells in enumerate(data_rows):
        if len(row_cells) < 2:
            continue
        item_name = row_cells[0] if row_cells else ''
        if not item_name or item_name.lower() in ['', 'articles', 'items', 'art.', 'art', '']:
            continue

        # Skip continuation rows (they start with — or are "do." continuations)
        if row_cells[0].startswith('—') or row_cells[0].lower() in ['do.', 'do', 'ditto', '—']:
            continue

        for pair_idx, pair in enumerate(price_col_pairs):
            low_col, high_col = pair[0], pair[1]
            if low_col >= len(row_cells) or high_col >= len(row_cells):
                continue
            low_price = row_cells[low_col].strip() if low_col < len(row_cells) else ''
            high_price = row_cells[high_col].strip() if high_col < len(row_cells) else ''

            if not low_price and not high_price:
                continue

            price_info = detect_price_scale_and_parse(f"{low_price} {high_price}")

            # Category
            item_name = row_cells[0] if row_cells else ''
            item_lower = item_name.lower()
            category = 'other'
            cat_keywords = {
                'grain': ['wheat', 'corn', 'rye', 'oats', 'barley', 'grain', 'flour', 'meal', 'indian corn', 'pearl', 'ash'],
                'flour_bread': ['flour', 'bread', 'crackers', 'pilot', 'middlings', 'fine', 'superfine', 'middling', 'crackers', 'pilot'],
                'meat': ['beef', 'pork', 'bacon', 'ham', 'lard', 'cheese', 'tallow', 'lard'],
                'dairy': ['butter', 'cheese', 'milk'],
                'drink': ['whiskey', 'rum', 'brandy', 'wine', 'molasses', 'cider', 'vinegar', 'gin', 'cognac', 'rum', 'spirits', 'brandy', 'cogniac'],
                'fuel': ['coal', 'wood', 'candle', 'tallow', 'oil', 'lamp', 'wood', 'charcoal'],
                'textile': ['cotton', 'wool', 'flax', 'hemp', 'duck', 'linen', 'sheeting', 'wool', 'silk', 'hose', 'shingles', 'boards'],
                'colonial_goods': ['coffee', 'tea', 'sugar', 'molasses', 'spices', 'indigo', 'cocoa', 'chocolate', 'pepper', 'pimento'],
                'tobacco': ['tobacco'],
                'metals': ['iron', 'steel', 'lead', 'copper', 'brass', 'nail', 'castings', 'pig', 'bar'],
                'naval_stores': ['tar', 'pitch', 'turpentine', 'rosin', 'staves', 'rope', 'cordage', 'hemp', 'staves', 'oak', 'hhd', 'bbl'],
            }
            category = 'other'
            item_lower = row_cells[0].lower() if row_cells else ''
            for cat, keywords in {
                'grain': ['wheat', 'corn', 'rye', 'oats', 'barley', 'grain', 'flour', 'meal', 'indian corn', 'pearl', 'ash'],
                'flour_bread': ['flour', 'bread', 'crackers', 'pilot', 'middlings', 'fine', 'superfine', 'middling', 'crackers', 'pilot'],
                'meat': ['beef', 'pork', 'bacon', 'ham', 'lard', 'cheese', 'tallow'],
                'dairy': ['butter', 'cheese', 'milk'],
                'drink': ['whiskey', 'rum', 'brandy', 'wine', 'molasses', 'cider', 'vinegar', 'gin', 'cognac', 'rum', 'spirits', 'cogniac', 'brandy'],
                'fuel': ['coal', 'wood', 'candle', 'tallow', 'oil', 'lamp', 'wood', 'charcoal'],
                'textile': ['cotton', 'wool', 'flax', 'hemp', 'duck', 'linen', 'sheeting', 'wool', 'silk', 'hose', 'shingles', 'boards'],
                'colonial_goods': ['coffee', 'tea', 'sugar', 'molasses', 'spices', 'indigo', 'cocoa', 'chocolate', 'pepper', 'pimento'],
                'tobacco': ['tobacco'],
                'metals': ['iron', 'steel', 'lead', 'copper', 'brass', 'nail', 'castings', 'pig', 'bar'],
                'naval_stores': ['tar', 'pitch', 'turpentine', 'rosin', 'staves', 'rope', 'cordage', 'hemp', 'staves', 'oak', 'hhd', 'bbl'],
            }.items():
                if any(kw in item_lower for kw in keywords):
                    category = cat
                    break

            # Extract unit
            unit_as_printed = ''
            unit_normalized = None
            unit_quantity = None
            unit_status = 'not_stated'
            item_text = row_cells[0] if row_cells else ''
            for unit in ['bbl', 'bu', 'lb', 'gal', 'cwt', 'ton', 'bolt', 'cask', 'box', 'piece', 'dozen', 'keg']:
                if re.search(r'\b' + re.escape(unit) + r'\b', item_text.lower()):
                    unit_as_printed = unit
                    unit_normalized = UNIT_MAP.get(unit, unit)
                    unit_quantity = 1
                    unit_status = 'printed'
                    break

            scale = price_info['price_scale'] if price_info['price_scale'] != 'unknown' else 'unknown'

            row_kind = 'goods_price'
            if any(fin in item_lower for fin in ['stock', 'bond', 'bank', 'bill', 'exchange', 'discount', 'premium', 'dividend', 'interest', 'security', 'fund', 'consol', 'indent', 'certificate', 'bank note', 'bank', 'note']):
                row_kind = 'exchange_or_financial'
            elif 'assize' in markdown.lower():
                row_kind = 'assize'

            needs_review = False
            review_reason = ''
            full_text = ' '.join(row_cells).lower()
            if 'unfaleable' in full_text:
                needs_review = True
                review_reason = 'OCR error: unfaleable'
            if 'sysil' in full_text or 'sysil' in ' '.join(row_cells):
                needs_review = True
                review_reason = 'OCR error: sysil'
            if 'duto' in full_text:
                needs_review = True
                review_reason = 'OCR error: duto'
            if 'braped' in full_text:
                needs_review = True
                review_reason = 'OCR error: braped (likely braided)'
            if 'fane' in full_text:
                needs_review = True
                review_reason = 'OCR error: fane (likely famed/ground?)'
            if not price_info['price_low_value'] and not price_info['price_high_value']:
                needs_review = True
                review_reason = 'Could not parse prices'

            obs = {
                'observation_id': f"{block['filename'].replace('.pdf', '')}_{pair_idx}_{row_idx:03d}",
                'price_list_id': block['filename'].replace('.pdf', ''),
                'source_dataset': 'price_currents_blocks',
                'block_id': block['block_id'],
                'block_type': block['block_type'],
                'filename': block['filename'],
                'newspaper_id': block['newspaper_id'],
                'newspaper_title': NEWSPAPER_META.get(block['newspaper_id'], {}).get('title', ''),
                'page_number': block['page_number'],
                'ocr_run_id': '',
                'page_url': f"https://chroniclingamerica.loc.gov/lccn/{block['newspaper_id']}/{block['date']}/ed-1/seq-{block['page_number']}/",
                'raw_text': ' | '.join(row_cells),
                'issue_date': block['date'],
                'year': int(block['year']) if block['year'] else None,
                'price_date_stated': None,
                'repeated_notice': False,
                'publication_city': NEWSPAPER_META.get(block['newspaper_id'], {}).get('city', ''),
                'publication_state': NEWSPAPER_META.get(block['newspaper_id'], {}).get('state', ''),
                'publication_lat': NEWSPAPER_META.get(block['newspaper_id'], {}).get('lat', 0),
                'publication_lon': NEWSPAPER_META.get(block['newspaper_id'], {}).get('lon', 0),
                'region': NEWSPAPER_META.get(block['newspaper_id'], {}).get('region', ''),
                'within_13_colonies': True,
                'market_place': extract_market_place(block['block_markdown']),
                'item_as_printed': row_cells[0] if row_cells else '',
                'item_normalized': row_cells[0].title() if row_cells else '',
                'item_category': category,
                'item_qualifier': '',
                'in_basket': False,
                'unit_as_printed': unit_as_printed if unit_as_printed else None,
                'unit_normalized': unit_normalized,
                'unit_quantity': unit_quantity,
                'unit_status': unit_status,
                'unit_inferred': None,
                'unit_inference_basis': None,
                'price_low_as_printed': low_price if low_price else None,
                'price_high_as_printed': high_price if high_price else None,
                'price_low_value': price_info['price_low_value'],
                'price_high_value': price_info['price_high_value'],
                'price_low_pounds': price_info['price_low_pounds'],
                'price_low_shillings': price_info['price_low_shillings'],
                'price_low_pence': price_info['price_low_pence'],
                'price_high_pounds': price_info['price_high_pounds'],
                'price_high_shillings': price_info['price_high_shillings'],
                'price_high_pence': price_info['price_high_pence'],
                'price_scale': price_info['price_scale'],
                'currency_as_printed': price_info['currency_as_printed'] if price_info['currency_as_printed'] else 'unknown',
                'currency_basis': 'unknown',
                'price_type': 'market',
                'row_kind': row_kind,
                'availability_note': '',
                'remark': f"Parsed from table block {block['block_id']}",
                'layout_type': 'column_table',
                'parse_method': 'table_parse',
                'confidence': 'low' if needs_review else 'medium',
                'needs_review': needs_review,
                'review_reason': review_reason,
            }
            observations.append(obs)

    return observations

# Select 5 blocks from different newspaper_ids and years
selected_uids = [
    'sn82014782_1802-04-09_1.pdf_/page/1/Table/33',  # Natchez/N. Orleans, 1802
    'sn83016072_1803-01-03_1.pdf_/page/2/Table/29',  # Boston, 1803
    'sn83016081_1804-11-19_1.pdf_/page/3/Table/36',  # Portland, 1804
    'sn83025442_1809-11-03_1.pdf_/page/2/Table/22',  # Providence bank notes, 1809
    'sn83025588_1800-08-19_1.pdf_/page/2/Table/17',  # Cadiz/Liverpool, 1800
]

selected_blocks = [b for b in table_blocks if b['block_uid'] in selected_uids]

print("=== 5 SELECTED TABLE BLOCKS ===")
for b in selected_blocks:
    print(f"\n=== {b['block_uid']} ===")
    print(f"newspaper_id: {b['newspaper_id']}, year: {b['year']}")
    print(b['block_markdown'][:1500])
    print("...")

# Parse all 5 blocks
all_observations = []
for block in selected_blocks:
    obs = parse_table_block(block)
    all_observations.extend(obs)
    print(f"\n{block['block_uid']}: extracted {len(obs)} observations")

# Save
os.makedirs('clean', exist_ok=True)
with open('clean/observations_blocks_pilot.json', 'w') as f:
    json.dump(all_observations, f, indent=2)

print(f"\nTotal observations: {len(all_observations)}")
print("Saved to clean/observations_blocks_pilot.json")

# Display all observations
print("\n=== ALL EXTRACTED OBSERVATIONS ===")
for i, obs in enumerate(all_observations, 1):
    print(f"\n{i}. {obs['observation_id']}")
    print(f"   Item: {obs['item_as_printed']}")
    print(f"   Price: {obs['price_low_as_printed']} - {obs['price_high_as_printed']}")
    print(f"   Values: {obs['price_low_value']} - {obs['price_high_value']} ({obs['price_scale']})")
    print(f"   Currency: {obs['currency_as_printed']}, Scale: {obs['price_scale']}")
    print(f"   Market: {obs['market_place']}")
    print(f"   Unit: {obs['unit_as_printed']} ({obs['unit_status']})")
    print(f"   Category: {obs['item_category']}, Kind: {obs['row_kind']}")
    print(f"   Needs Review: {obs['needs_review']} ({obs['review_reason']})")
    print(f"   Confidence: {obs['confidence']}")