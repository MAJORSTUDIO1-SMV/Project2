#!/usr/bin/env python3
"""
Link SectionHeader/Text blocks containing "price current" to their price lists
using the pages dataset's new_ocr_text_list.
Updated with: described_only detection, inline_in_heading_block, market_place extraction.
"""

import pandas as pd
import re
import json
import os

# Load data
blocks = pd.read_parquet('raw/price_currents_blocks.parquet')
pages = pd.read_parquet('raw/price_currents_pages.parquet')

# Parse filename for newspaper_id, date, year
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

# Add parsed fields to blocks
parsed = blocks['filename'].apply(parse_filename)
blocks['newspaper_id'] = parsed.apply(lambda x: x['newspaper_id'])
blocks['date'] = parsed.apply(lambda x: x['date'])
blocks['year'] = pd.to_datetime(blocks['date'], errors='coerce').dt.year
blocks['decade'] = (blocks['year'] // 10) * 10
blocks['block_uid'] = blocks['filename'] + '_' + blocks['block_id'].astype(str)

# Also parse pages
pages_parsed = pages['filename'].apply(parse_filename)
pages['newspaper_id'] = pages_parsed.apply(lambda x: x['newspaper_id'])
pages['date'] = pages_parsed.apply(lambda x: x['date'])
pages['year'] = pd.to_datetime(pages['date'], errors='coerce').dt.year

# Real commodity words (from CLAUDE.md)
COMMODITY_WORDS = [
    'flour', 'wheat', 'corn', 'tobacco', 'beef', 'pork', 'salt',
    'rum', 'molasses', 'rice', 'butter', 'cotton', 'coffee',
    'sugar', 'hemp', 'iron', 'rye', 'oats', 'barley', 'hay',
    'cheese', 'whiskey', 'wine', 'brandy', 'cider', 'vinegar',
    'lard', 'tallow', 'candles', 'soap', 'boards', 'shingles',
    'lime', 'brick', 'coal', 'wood', 'fish', 'cod', 'mackerel',
    'hams', 'bacon', 'shoulders', 'sides', 'indian corn'
]

# Number patterns
NUMBER_PATTERNS = [
    re.compile(r'\b\d+\s+\d{2}\b'),           # 5 50 (D.C.)
    re.compile(r'\d+\.?\d*\s+[aA]\s+\d+\.?\d*'),  # 5 a 6 (range)
    re.compile(r'\b\d+\s+\d+\s+\d+\b'),       # 0 17 6 (L.s.d.)
    re.compile(r'\d+/\d+'),                   # 4/6 (shillings/pence)
    re.compile(r'\d+s\.?\s*\d*d?'),           # 30s., 6s. 6d.
    re.compile(r'\d+l\.?\s*\d*s?\.?\s*\d*d?'), # 3l. 10s.
]

# Financial keywords
FINANCIAL_KEYWORDS = ['securities', 'stock', 'bank', 'exchange', 'bonds', 'bills', 'funds', 'consols', 'dividend', 'interest', 'discount', 'premium']

def count_number_patterns(text):
    """Count number pattern matches in text."""
    count = 0
    for pattern in NUMBER_PATTERNS:
        count += len(pattern.findall(str(text)))
    return count

def count_commodity_words(text):
    """Count real commodity word matches in text."""
    text_lower = str(text).lower()
    count = 0
    for comm in COMMODITY_WORDS:
        count += len(re.findall(r'\b' + re.escape(comm.lower()) + r'\b', text_lower))
    return count

def is_heading_like(text):
    """Check if text looks like a heading (short, maybe all caps, ends with period/colon)."""
    text = str(text).strip()
    if len(text) > 120:
        return True  # long text is likely a heading
    # Check for heading patterns
    if re.match(r'^[A-Z\s\.]+$', text):  # all caps
        return True
    if text.endswith('.') or text.endswith(':') or text.endswith('.'):
        return True
    if text.startswith('#') or text.startswith('##') or text.startswith('###'):
        return True
    return False

def extract_market_place(heading_text):
    """Extract market place from heading text (word after 'at' or 'in')."""
    text = heading_text.lower()
    for prep in [' at ', ' in ']:
        if prep in text:
            parts = text.split(prep)
            if len(parts) > 1:
                # Get first word after preposition
                rest = parts[1].strip()
                # Remove punctuation and get first 1-2 words (for compound names like "New-York")
                # Only keep alphabetic words, stop at punctuation
                words = re.findall(r'[a-zA-Z\-]+', rest)
                if words:
                    # Return first 1-2 words that look like place names
                    market = ' '.join(words[:2]).title()
                    # Filter out obvious non-places
                    if market.lower() not in ['the', 'this', 'a', 'an', 'of', 'and', 'or', 'in', 'at', 'on', 'for', 'to', 'from', 'by', 'with', 'is', 'as', 'it', 'be', 'was', 'were', 'been', 'being', 'has', 'have', 'had', 'do', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'cannot', 'not', 'no', 'yes', 'if', 'then', 'else', 'when', 'where', 'who', 'what', 'which', 'how', 'why', 'all', 'any', 'some', 'such', 'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'now', 'here', 'there', 'where', 'here', 'there', 'every', 'each', 'both', 'either', 'neither', 'other', 'another', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']:
                        return market
    return None

# Find candidate headings: SectionHeader or Text blocks with "price current" or "prices current"
# that are short (< 120 chars)
candidate_blocks = blocks[
    (blocks['block_type'].isin(['SectionHeader', 'Text'])) &
    (blocks['block_markdown'].str.contains(r'price current', case=False, na=False)) &
    (blocks['block_markdown'].str.len() < 120)
].copy()

print(f"Found {len(candidate_blocks)} candidate heading blocks")

# Build a lookup for pages
pages_by_key = {}
for _, p in pages.iterrows():
    key = (p['filename'], p['page_number'])
    pages_by_key[key] = p

results = []

for _, block in candidate_blocks.iterrows():
    filename = block['filename']
    page_num = block['page_number']
    heading_text = block['block_markdown']
    block_uid = block['block_uid']
    block_year = int(block['year']) if pd.notna(block['year']) else None

    # Find matching page
    page_key = (filename, page_num)
    if page_key not in pages_by_key:
        continue

    page = pages_by_key[page_key]
    text_array = page['new_ocr_text_list']
    text_list = list(text_array)

    # Find heading position
    heading_pos = -1
    heading_in_same_item = False
    for i, item in enumerate(text_list):
        item_str = str(item)
        if heading_text.strip() in item_str or item_str.strip() in heading_text:
            heading_pos = i
            # Check if heading is a substring of a longer item (inline case)
            if len(item_str) > len(heading_text) + 20:
                heading_in_same_item = True
            break

    if heading_pos == -1:
        # Try partial match
        for i, item in enumerate(text_list):
            heading_words = [w for w in heading_text.lower().split() if len(w) > 4]
            if any(word in str(item).lower() for word in heading_words):
                heading_pos = i
                item_str = str(item)
                if len(item_str) > len(heading_text) + 20:
                    heading_in_same_item = True
                break

    if heading_pos == -1:
        continue

    # Look at next 12 items, up to next heading-like item
    search_limit = min(heading_pos + 13, len(text_list))
    list_status = "not_found"
    distance = None
    list_text = ""
    n_numbers = 0
    n_commodities = 0
    list_kind = "unknown"

    # First, check if heading itself contains numbers (inline_in_heading_block)
    if heading_in_same_item:
        heading_item_text = str(text_list[heading_pos])
        n_nums_heading = count_number_patterns(heading_item_text)
        n_comms_heading = count_commodity_words(heading_item_text)
        if n_nums_heading >= 4 or n_comms_heading >= 3:
            list_status = "inline_in_heading_block"
            distance = 0
            list_text = text_list[heading_pos]
            n_numbers = n_nums_heading
            n_commodities = n_comms_heading
            item_lower = text_list[heading_pos].lower()
            if any(fin in item_lower for fin in FINANCIAL_KEYWORDS) and n_comms < 3:
                list_kind = "financial"
            else:
                list_kind = "goods"

    # If not inline, search subsequent items
    if list_status == "not_found":
        for j in range(1, min(13, len(text_list) - heading_pos)):
            idx = heading_pos + j
            if idx >= len(text_list):
                break

            item_text = str(text_list[idx])

            # Stop if we hit another heading-like item
            if j > 1 and is_heading_like(item_text):
                break

            distance = j
            n_nums = count_number_patterns(item_text)
            n_comms = count_commodity_words(item_text)

            # Check if described_only (starts with "Table with")
            if item_text.strip().lower().startswith("table with"):
                list_status = "described_only"
                list_text = item_text
                n_numbers = count_number_patterns(item_text)
                n_commodities = n_comms
                list_kind = "described_only"
                break

            # Check if this item qualifies as a price list
            if n_nums >= 4 or n_comms >= 3:
                # Check financial
                item_lower = item_text.lower()
                if any(fin in item_lower for fin in FINANCIAL_KEYWORDS) and n_comms < 3:
                    list_kind = "financial"
                    list_status = "financial"
                elif n_comms >= 3:
                    list_kind = "goods"
                    list_status = "found"
                else:
                    list_kind = "unknown"
                    list_status = "found"

                list_text = item_text
                n_numbers = n_nums
                n_commodities = n_comms
                break

    # Extract market_place from heading
    market_place = extract_market_place(heading_text)

    results.append({
        'block_uid': block_uid,
        'filename': filename,
        'newspaper_id': block['newspaper_id'],
        'date': block['date'],
        'year': block_year,
        'page_number': int(page_num),
        'heading_text': heading_text,
        'list_status': list_status,
        'distance': distance if list_status != "not_found" else None,
        'list_text': list_text if list_status != "not_found" else "",
        'n_numbers': n_numbers,
        'n_commodities': n_commodities,
        'list_kind': list_kind if list_status != "not_found" else "none",
        'market_place': market_place,
    })

# Save results
os.makedirs('clean', exist_ok=True)
with open('clean/heading_links.json', 'w') as f:
    json.dump(results, f, indent=2)

print(f"Saved {len(results)} links to clean/heading_links.json")

# Statistics
total_headings = len(results)
status_counts = {}
for r in results:
    s = r['list_status']
    status_counts[s] = status_counts.get(s, 0) + 1

print(f"\nTotal headings processed: {total_headings}")
print("List status counts:")
for status, count in sorted(status_counts.items()):
    print(f"  {status}: {count}")

# By decade with status breakdown
decade_stats = {}
for r in results:
    dec = r['year'] // 10 * 10 if r['year'] else 0
    if dec not in decade_stats:
        decade_stats[dec] = {}
    s = r['list_status']
    decade_stats[dec][s] = decade_stats[dec].get(s, 0) + 1

print("\n=== List Status by Decade ===")
for dec in sorted(decade_stats.keys()):
    s = decade_stats[dec]
    total = sum(s.values())
    parts = [f"{k}={v}" for k, v in s.items()]
    print(f"  {dec}s: {total} total ({', '.join(parts)})")

# Top 15 market_place values
market_counts = {}
for r in results:
    if r['market_place']:
        market_counts[r['market_place']] = market_counts.get(r['market_place'], 0) + 1

print("\n=== Top 15 Market Places ===")
for market, count in sorted(market_counts.items(), key=lambda x: -x[1])[:15]:
    print(f"  {market}: {count}")

# 10 examples
print("\n=== 10 Examples ===")
found_examples = [r for r in results if r['list_status'] not in ['not_found', 'described_only']][:10]
for i, r in enumerate(found_examples, 1):
    print(f"\n{i}. {r['filename']} (year={r['year']})")
    print(f"   Heading: {r['heading_text']}")
    print(f"   Status: {r['list_status']}, Distance: {r['distance']}")
    print(f"   Numbers: {r['n_numbers']}, Commodities: {r['n_commodities']}, Kind: {r['list_kind']}")
    print(f"   Market: {r['market_place']}")
    print(f"   List: {r['list_text'][:300]}")

# Specific files check
print("\n=== Specific Files Check ===")
for fn in ['sn84024710_1805-09-04_1.pdf', 'sn84023379_1803-04-05_1.pdf', 'sn83030483_1790-11-27_1.pdf']:
    matches = [r for r in results if r['filename'] == fn]
    if matches:
        for m in matches:
            print(f"  {fn}: heading='{m['heading_text'][:80]}', status={m['list_status']}, distance={m['distance']}, kind={m['list_kind']}, market={m['market_place']}")
            if m['list_status'] not in ['not_found', 'described_only']:
                print(f"    list_text (first 300): {m['list_text'][:300]}")
    else:
        print(f"  {fn}: NOT FOUND in candidate headings")

# Why 1770s headings not found
print("\n=== 1770s Headings Not Found Analysis ===")
not_found_1770s = [r for r in results if r['year'] and 1770 <= r['year'] <= 1779 and r['list_status'] == 'not_found']
print(f"Total 1770s headings: {sum(1 for r in results if r['year'] and 1770 <= r['year'] <= 1779)}")
print(f"Not found: {len(not_found_1770s)}")
for r in not_found_1770s[:5]:
    print(f"  {r['filename']}: heading='{r['heading_text'][:80]}'")
    # Check if heading was found in text_list at all
    page_key = (r['filename'], r['page_number'])
    if page_key in pages_by_key:
        page = pages_by_key[page_key]
        text_list = list(page['new_ocr_text_list'])
        found = False
        for i, item in enumerate(text_list):
            if r['heading_text'].strip() in str(item) or str(item).strip() in r['heading_text']:
                found = True
                print(f"    Found at position {i} in text_list (len={len(str(item))} chars)")
                break
        if not found:
            print(f"    Heading NOT found in text_list at all")
            # Show first few items
            for i, item in enumerate(text_list[:3]):
                print(f"    text_list[{i}]: {str(item)[:100]}...")

# Save updated results
with open('clean/heading_links.json', 'w') as f:
    json.dump(results, f, indent=2)

print("\nDone!")