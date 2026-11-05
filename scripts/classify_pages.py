#!/usr/bin/env python3
"""
Classify pages using simple rule-based signals (no LLM).
Signals as separate boolean columns; primary label with goods-prices priority.
Fixed: stricter LSD detection, split commodity words, strict dollar detection.
"""

import re
import pandas as pd
import os
import random

# Load data
df = pd.read_parquet('raw/price_currents_pages.parquet')
print(f'Loaded {len(df)} pages')

# Parse filename for newspaper_id and date
FILENAME_PATTERN = re.compile(r'^([a-zA-Z0-9]+)_(\d{4}-\d{2}-\d{2})_(\d+)\.pdf$')
def parse_filename(filename):
    match = FILENAME_PATTERN.match(filename)
    if match:
        return {'newspaper_id': match.group(1), 'date': match.group(2), 'edition': int(match.group(3))}
    return None

parsed = df['filename'].apply(parse_filename)
mask_matched = parsed.notna()
df_matched = df[mask_matched].copy()
parsed_df = parsed[mask_matched].apply(pd.Series)
df_matched = pd.concat([df_matched, parsed_df], axis=1)
df_matched['date_parsed'] = pd.to_datetime(df_matched['date'])
df_matched['year'] = df_matched['date_parsed'].dt.year
df_matched['decade'] = (df_matched['year'] // 10) * 10

print(f'Pages with valid filenames: {len(df_matched)}')

# --- Split commodity words ---
# Real commodities (38)
COMMODITY_WORDS = [
    'flour', 'wheat', 'corn', 'tobacco', 'beef', 'pork', 'salt',
    'rum', 'molasses', 'rice', 'butter', 'cotton', 'coffee',
    'sugar', 'hemp', 'iron', 'rye', 'oats', 'barley', 'hay',
    'cheese', 'whiskey', 'wine', 'brandy', 'cider', 'vinegar',
    'lard', 'tallow', 'candles', 'soap', 'boards', 'shingles',
    'lime', 'brick', 'coal', 'wood', 'fish', 'cod', 'mackerel',
    'hams', 'bacon', 'shoulders', 'sides'
]

# Quality/grade words (5) - for item_qualifier later
QUALITY_WORDS = [
    'middling', 'superfine', 'prime', 'common', 'ordinary'
]

# Trade/condition words (5) - for item_qualifier later
TRADE_WORDS = [
    'shipping', 'merchantable'
]

ALL_COMMODITY_RELATED = COMMODITY_WORDS + QUALITY_WORDS + TRADE_WORDS

# Price pattern regexes - STRICT DOLLAR DETECTION
# Dollar sign next to number: $5, $ 5, $5.50, etc.
DOLLAR_SIGN_PATTERN = re.compile(r'\$\s*\d')
# "Dolls. Cts." or "Dol. Ct." headings
DOLLS_CTS_HEADING_PATTERN = re.compile(r'Dolls?\.\s*Cts?\.', re.IGNORECASE)
# "D. C." heading (with dots)
DC_HEADING_PATTERN = re.compile(r'\bD\.\s*C\.', re.IGNORECASE)
# "Dollars" next to a number (e.g., "5 Dollars", "Dollars 5")
DOLLARS_WORD_PATTERN = re.compile(r'\b\d+\.?\d*\s+dollars?\b|\bdollars?\s+\d+\.?\d*\b', re.IGNORECASE)

# Range pattern with "a" (e.g., "5 a 6", "4 1/2 a 6 00") - still valid for dollars if dollars context
RANGE_PATTERN = re.compile(r'\d+\.?\d*\s+[aA]\s+\d+\.?\d*')

# LSD triple with validation: shillings < 20, pence < 12
LSD_TRIPLE_CANDIDATE_PATTERN = re.compile(r'\b(\d+)\s+(\d+)\s+(\d+)\b')
LSD_HEADING_PATTERN = re.compile(r'L\.\s*s\.\s*d\.', re.IGNORECASE)

# Explicitly EXCLUDE these from dollar evidence
# "per cent", "per ct", "cent." (hundredweight or percentage)
PER_CENT_PATTERN = re.compile(r'per\s+cent', re.IGNORECASE)
PER_CT_PATTERN = re.compile(r'per\s+ct', re.IGNORECASE)
CENT_ABBREV_PATTERN = re.compile(r'\bcent\.', re.IGNORECASE)  # "cent." as abbreviation

PRICE_CURRENT_HEADING_PATTERN = re.compile(r'^PRICES?\s+CURRENT', re.IGNORECASE | re.MULTILINE)
TABLE_DESC_PATTERN = re.compile(r'^table with', re.IGNORECASE | re.MULTILINE)
ASSIZE_PATTERN = re.compile(r'Assize of Bread', re.IGNORECASE)

# Pounds markers for LSD context
POUNDS_MARKER_PATTERN = re.compile(r'\d+l\.|\d+\s*l\.|\£\d+', re.IGNORECASE)
SHILLINGS_MARKER_PATTERN = re.compile(r'\d+s\.', re.IGNORECASE)
PENCE_MARKER_PATTERN = re.compile(r'\d+d\.', re.IGNORECASE)

EXCHANGE_PATTERNS = [
    re.compile(r'course of exchange', re.IGNORECASE),
    re.compile(r'bills? on london', re.IGNORECASE),
    re.compile(r'\bstock\b', re.IGNORECASE),
    re.compile(r'exchange rate', re.IGNORECASE),
    re.compile(r'bills of exchange', re.IGNORECASE),
    re.compile(r'sterling', re.IGNORECASE),
    re.compile(r'draft (on|at)', re.IGNORECASE),
    re.compile(r'bank (note|bill)', re.IGNORECASE),
    re.compile(r'promissory note', re.IGNORECASE),
]

def is_valid_lsd_triple(text, match, window=80):
    """Check if a triple of numbers is a valid L.s.d. (shillings<20, pence<12) with context."""
    try:
        pounds = int(match.group(1))
        shillings = int(match.group(2))
        pence = int(match.group(3))
    except ValueError:
        return False

    # Basic arithmetic validation
    if shillings >= 20 or pence >= 12:
        return False

    # Contextual evidence: check nearby for L.s.d. heading or £/s/d markers
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    context = text[start:end]
    context_lower = context.lower()

    has_lsd_heading = bool(LSD_HEADING_PATTERN.search(context))
    has_pounds_marker = bool(POUNDS_MARKER_PATTERN.search(context))
    has_shillings_marker = bool(SHILLINGS_MARKER_PATTERN.search(context))
    has_pence_marker = bool(PENCE_MARKER_PATTERN.search(context))

    return has_lsd_heading or has_pounds_marker or has_shillings_marker or has_pence_marker


def has_price_pattern_near(text, commodity, window=60):
    """Check if a commodity word has a price pattern within window characters."""
    text_lower = text.lower()
    commodity_lower = commodity.lower()
    for match in re.finditer(r'\b' + re.escape(commodity_lower) + r'\b', text_lower):
        start = max(0, match.start() - window)
        end = min(len(text_lower), match.end() + window)
        context = text_lower[start:end]
        # Check for dollar patterns
        if (DOLLAR_SIGN_PATTERN.search(context) or
            DOLLARS_WORD_PATTERN.search(context) or
            DOLLS_CTS_HEADING_PATTERN.search(context) or
            DC_HEADING_PATTERN.search(context) or
            RANGE_PATTERN.search(context)):
            return True
        # Check for valid LSD triple
        for lsd_match in LSD_TRIPLE_CANDIDATE_PATTERN.finditer(context):
            if is_valid_lsd_triple(context, lsd_match, window=40):
                return True
    return False


def find_match_context(text, patterns, chars=300):
    """Find first match of any pattern and return context."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - chars//2)
            end = min(len(text), match.end() + chars//2)
            return text[start:end], pattern.pattern
    return None, None


results = []
for _, row in df_matched.iterrows():
    text = str(row['new_ocr_text'])
    text_lower = text.lower()
    filename = row['filename']
    newspaper_id = row['newspaper_id']
    date = row['date']
    year = row['year']
    decade = row['decade']

    # --- Individual boolean signals ---
    has_price_current_heading = bool(PRICE_CURRENT_HEADING_PATTERN.search(text))

    # Price patterns - DOLLARS (STRICT)
    has_dollar_sign = bool(DOLLAR_SIGN_PATTERN.search(text))
    has_dollars_word = bool(DOLLARS_WORD_PATTERN.search(text))
    has_dolls_cts_heading = bool(DOLLS_CTS_HEADING_PATTERN.search(text))
    has_dc_heading = bool(DC_HEADING_PATTERN.search(text))
    has_range_pattern = bool(RANGE_PATTERN.search(text))

    # Dollar evidence: any of the above
    has_dollars = has_dollar_sign or has_dollars_word or has_dolls_cts_heading or has_dc_heading or has_range_pattern

    # Track what specifically fired for debugging
    dollar_evidence = []
    if has_dollar_sign:
        dollar_evidence.append('dollar_sign')
    if has_dollars_word:
        dollar_evidence.append('dollars_word')
    if has_dolls_cts_heading:
        dollar_evidence.append('dolls_cts_heading')
    if has_dc_heading:
        dollar_evidence.append('dc_heading')
    if has_range_pattern:
        dollar_evidence.append('range_pattern')

    # Exclude false positives: "per cent", "per ct", "cent."
    # These should NOT count as dollar evidence
    has_per_cent = bool(PER_CENT_PATTERN.search(text))
    has_per_ct = bool(PER_CT_PATTERN.search(text))
    has_cent_abbrev = bool(CENT_ABBREV_PATTERN.search(text))
    # Note: we don't subtract from has_dollars, but we track for currency_guess

    # Price patterns - LSD (strict)
    has_lsd_heading = bool(LSD_HEADING_PATTERN.search(text))
    # Check for valid LSD triples with context
    has_valid_lsd_triple = False
    lsd_matches = []
    for match in LSD_TRIPLE_CANDIDATE_PATTERN.finditer(text):
        valid = is_valid_lsd_triple(text, match)
        lsd_matches.append((match.group(), match.start(), valid))
        if valid:
            has_valid_lsd_triple = True
    has_lsd = has_valid_lsd_triple or has_lsd_heading

    # Pounds markers for currency guess
    has_pounds_marker = bool(POUNDS_MARKER_PATTERN.search(text))
    has_shillings_marker = bool(SHILLINGS_MARKER_PATTERN.search(text))
    has_pence_marker = bool(PENCE_MARKER_PATTERN.search(text))

    # Commodity words (only real commodities for goods_price_count)
    found_commodities = [w for w in COMMODITY_WORDS if re.search(r'\b' + re.escape(w) + r'\b', text_lower)]
    found_quality = [w for w in QUALITY_WORDS if re.search(r'\b' + re.escape(w) + r'\b', text_lower)]
    found_trade = [w for w in TRADE_WORDS if re.search(r'\b' + re.escape(w) + r'\b', text_lower)]
    commodity_count = len(found_commodities)
    quality_count = len(found_quality)
    trade_count = len(found_trade)

    # Goods price: commodity word with nearby price pattern (only real commodities)
    goods_price_commodities = []
    for comm in found_commodities:
        if has_price_pattern_near(text, comm, 60):
            goods_price_commodities.append(comm)
    has_goods_prices = len(goods_price_commodities) > 0
    goods_price_count = len(goods_price_commodities)

    # Table description
    has_table_description = bool(TABLE_DESC_PATTERN.search(text))

    # Assize
    has_assize = bool(ASSIZE_PATTERN.search(text))

    # Exchange/financial
    exchange_matches = []
    for p in EXCHANGE_PATTERNS:
        if p.search(text):
            exchange_matches.append(p.pattern)
    has_exchange = len(exchange_matches) > 0
    has_stock = any('stock' in m for m in exchange_matches)

    # --- Currency guess ---
    # Priority: explicit headings > markers > both = mixed
    if has_dolls_cts_heading or has_dc_heading or has_dollar_sign or has_dollars_word:
        # Explicit dollar evidence
        if has_lsd_heading or has_valid_lsd_triple or has_pounds_marker or has_shillings_marker or has_pence_marker:
            currency_guess = 'mixed'
        else:
            currency_guess = 'dollars'
    elif has_lsd_heading or has_valid_lsd_triple or has_pounds_marker or has_shillings_marker or has_pence_marker:
        currency_guess = 'lsd'
    elif has_range_pattern:
        # Range pattern alone is ambiguous - check context
        if has_per_cent or has_per_ct or has_cent_abbrev:
            currency_guess = 'unknown'  # likely percentage
        else:
            currency_guess = 'dollars'  # assume dollars for price ranges
    else:
        currency_guess = 'unknown'

    # --- Primary label with goods-prices priority ---
    label = 'likely_false_positive'
    score = 0
    reasons = []

    if has_assize:
        label = 'assize_notice'
        score = 10
        reasons.append('Assize of Bread')
    elif has_goods_prices:
        # Must be a price_list_* or assize_notice, never exchange_or_financial
        if has_table_description:
            label = 'price_list_table_description'
            score = 4 + goods_price_count
            reasons.append('Table description + goods prices')
        elif has_price_current_heading:
            if currency_guess == 'lsd':
                label = 'price_list_lsd'
            elif currency_guess == 'mixed':
                label = 'price_list_inline'  # dollars wins in mixed
            else:
                label = 'price_list_inline'
            score = 5 + goods_price_count
            reasons.append('Price current heading + goods prices')
        else:
            # Has goods prices but no heading/table desc
            if currency_guess == 'lsd':
                label = 'price_list_lsd'
            else:
                label = 'price_list_inline'
            score = 2 + goods_price_count
            reasons.append('Goods prices without heading')
        reasons.append(f'Goods commodities with prices: {", ".join(goods_price_commodities[:5])}')
    elif has_exchange:
        label = 'exchange_or_financial'
        score = 3 + len(exchange_matches)
        reasons.extend([f'exchange: {m}' for m in exchange_matches])
    elif has_table_description:
        label = 'price_list_table_description'
        score = 4
        reasons.append('Table description')
    elif has_price_current_heading:
        if currency_guess == 'lsd':
            label = 'price_list_lsd'
        elif currency_guess == 'mixed':
            label = 'price_list_inline'
        else:
            label = 'price_list_inline'
        score = 4
        reasons.append('Price current heading')
    elif commodity_count >= 3 and (has_dollars or has_lsd):
        # Commodities + price patterns but not close enough
        if currency_guess == 'lsd':
            label = 'price_list_lsd'
        else:
            label = 'price_list_inline'
        score = 1 + commodity_count
        reasons.append(f'Commodities ({commodity_count}) + price patterns')
    else:
        if commodity_count > 0:
            reasons.append(f'Commodities only: {", ".join(found_commodities[:3])}')
        if has_dollars or has_lsd:
            reasons.append('Price patterns without nearby commodities')
        if has_exchange:
            reasons.append('Exchange terms but no goods prices')
        score = max(1, commodity_count)

    results.append({
        'filename': filename,
        'newspaper_id': newspaper_id,
        'date': date,
        'year': year,
        'decade': decade,
        'label': label,
        'score': score,
        'reasons': '; '.join(reasons) if reasons else 'no signals',
        # Boolean signals
        'has_goods_prices': has_goods_prices,
        'has_lsd': has_lsd,
        'has_dollars': has_dollars,
        'has_assize': has_assize,
        'has_table_description': has_table_description,
        'has_exchange': has_exchange,
        'has_stock': has_stock,
        'has_price_current_heading': has_price_current_heading,
        # Currency guess
        'currency_guess': currency_guess,
        # Dollar evidence detail
        'dollar_evidence': ','.join(dollar_evidence) if dollar_evidence else 'none',
        # Counts
        'goods_price_count': goods_price_count,
        'commodity_count': commodity_count,
        'quality_count': quality_count,
        'trade_count': trade_count,
        'exchange_match_count': len(exchange_matches),
    })

results_df = pd.DataFrame(results)

# Load old v3 for comparison
try:
    old_df = pd.read_csv('clean/page_classification_v3.csv')
    print('\n=== Old v3 vs New label counts ===')
    old_counts = old_df['label'].value_counts()
    new_counts = results_df['label'].value_counts()
    all_labels = sorted(set(old_counts.index) | set(new_counts.index))
    print(f"{'Label':<35} {'Old v3':>6} {'New':>6} {'Change':>8}")
    print('-' * 60)
    for label in all_labels:
        old = old_counts.get(label, 0)
        new = new_counts.get(label, 0)
        print(f"{label:<35} {old:>6} {new:>6} {new-old:>+8}")
except FileNotFoundError:
    print('\n(No v3 file for comparison)')

# Save new classification
os.makedirs('clean', exist_ok=True)
results_df.to_csv('clean/page_classification.csv', index=False)
print(f'\nSaved to clean/page_classification.csv ({len(results_df)} pages)')

# Pages per label
print('\n=== Pages per label (new) ===')
for label, count in results_df['label'].value_counts().items():
    print(f'  {label}: {count}')

# Currency guess by decade
print('\n=== Currency guess by decade ===')
currency_by_decade = results_df.groupby(['decade', 'currency_guess']).size().unstack(fill_value=0)
for c in ['dollars', 'lsd', 'mixed', 'unknown']:
    if c not in currency_by_decade.columns:
        currency_by_decade[c] = 0
currency_by_decade = currency_by_decade[['dollars', 'lsd', 'mixed', 'unknown']]
print(currency_by_decade.to_string())

# --- Check specific pages with detailed evidence ---
print('\n=== Signal checks for key pages ===')

def check_page_signals(text):
    """Return detailed signal details for a page."""
    text_lower = text.lower()

    # Dollar signals
    has_dollar_sign = bool(DOLLAR_SIGN_PATTERN.search(text))
    has_dollars_word = bool(DOLLARS_WORD_PATTERN.search(text))
    has_dolls_cts_heading = bool(DOLLS_CTS_HEADING_PATTERN.search(text))
    has_dc_heading = bool(DC_HEADING_PATTERN.search(text))
    has_range_pattern = bool(RANGE_PATTERN.search(text))

    has_dollars = has_dollar_sign or has_dollars_word or has_dolls_cts_heading or has_dc_heading or has_range_pattern

    dollar_evidence = []
    if has_dollar_sign:
        dollar_evidence.append('dollar_sign')
    if has_dollars_word:
        dollar_evidence.append('dollars_word')
    if has_dolls_cts_heading:
        dollar_evidence.append('dolls_cts_heading')
    if has_dc_heading:
        dollar_evidence.append('dc_heading')
    if has_range_pattern:
        dollar_evidence.append('range_pattern')

    # Exclude patterns
    has_per_cent = bool(PER_CENT_PATTERN.search(text))
    has_per_ct = bool(PER_CT_PATTERN.search(text))
    has_cent_abbrev = bool(CENT_ABBREV_PATTERN.search(text))

    # LSD signals
    has_lsd_heading = bool(LSD_HEADING_PATTERN.search(text))
    has_valid_lsd_triple = False
    lsd_matches = []
    for match in LSD_TRIPLE_CANDIDATE_PATTERN.finditer(text):
        valid = is_valid_lsd_triple(text, match)
        lsd_matches.append((match.group(), match.start(), valid))
        if valid:
            has_valid_lsd_triple = True
    has_lsd = has_valid_lsd_triple or has_lsd_heading

    # Pounds markers
    has_pounds_marker = bool(POUNDS_MARKER_PATTERN.search(text))
    has_shillings_marker = bool(SHILLINGS_MARKER_PATTERN.search(text))
    has_pence_marker = bool(PENCE_MARKER_PATTERN.search(text))

    # Currency guess
    if has_dolls_cts_heading or has_dc_heading or has_dollar_sign or has_dollars_word:
        if has_lsd_heading or has_valid_lsd_triple or has_pounds_marker or has_shillings_marker or has_pence_marker:
            currency_guess = 'mixed'
        else:
            currency_guess = 'dollars'
    elif has_lsd_heading or has_valid_lsd_triple or has_pounds_marker or has_shillings_marker or has_pence_marker:
        currency_guess = 'lsd'
    elif has_range_pattern:
        if has_per_cent or has_per_ct or has_cent_abbrev:
            currency_guess = 'unknown'
        else:
            currency_guess = 'dollars'
    else:
        currency_guess = 'unknown'

    return {
        'has_dollar_sign': has_dollar_sign,
        'has_dollars_word': has_dollars_word,
        'has_dolls_cts_heading': has_dolls_cts_heading,
        'has_dc_heading': has_dc_heading,
        'has_range_pattern': has_range_pattern,
        'has_dollars': has_dollars,
        'dollar_evidence': dollar_evidence,
        'has_per_cent': has_per_cent,
        'has_per_ct': has_per_ct,
        'has_cent_abbrev': has_cent_abbrev,
        'has_lsd_heading': has_lsd_heading,
        'has_valid_lsd_triple': has_valid_lsd_triple,
        'lsd_matches': lsd_matches,
        'has_lsd': has_lsd,
        'has_pounds_marker': has_pounds_marker,
        'has_shillings_marker': has_shillings_marker,
        'has_pence_marker': has_pence_marker,
        'currency_guess': currency_guess,
    }

# Check the three pages from the 1770s
for fn in ['sn83030493_1777-09-08_1.pdf', 'sn83021183_1777-09-25_1.pdf', 'sn84023855_1779-12-21_1.pdf']:
    row = df_matched[df_matched['filename'] == fn].iloc[0]
    text = str(row['new_ocr_text'])
    signals = check_page_signals(text)
    print(f'\n--- {fn} ---')
    print(f"  has_dollar_sign: {signals['has_dollar_sign']}")
    print(f"  has_dollars_word: {signals['has_dollars_word']}")
    print(f"  has_dolls_cts_heading: {signals['has_dolls_cts_heading']}")
    print(f"  has_dc_heading: {signals['has_dc_heading']}")
    print(f"  has_range_pattern: {signals['has_range_pattern']}")
    print(f"  >>> has_dollars: {signals['has_dollars']}")
    print(f"  dollar_evidence: {signals['dollar_evidence']}")
    print(f"  has_per_cent: {signals['has_per_cent']}")
    print(f"  has_per_ct: {signals['has_per_ct']}")
    print(f"  has_cent_abbrev: {signals['has_cent_abbrev']}")
    print(f"  has_lsd_heading: {signals['has_lsd_heading']}")
    print(f"  has_valid_lsd_triple: {signals['has_valid_lsd_triple']}")
    print(f"  >>> has_lsd: {signals['has_lsd']}")
    print(f"  >>> currency_guess: {signals['currency_guess']}")
    # Show the exact text that fired
    for pattern_name, pattern in [
        ('dollar_sign', DOLLAR_SIGN_PATTERN),
        ('dollars_word', DOLLARS_WORD_PATTERN),
        ('dolls_cts_heading', DOLLS_CTS_HEADING_PATTERN),
        ('dc_heading', DC_HEADING_PATTERN),
        ('range_pattern', RANGE_PATTERN),
    ]:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 50)
            end = min(len(text), match.end() + 50)
            print(f"    Fired [{pattern_name}]: ...{repr(text[start:end])}...")

# 6 random pages from 1780s with currency_guess = dollars
print('\n=== 6 random pages: 1780s, currency_guess=dollars ===')
dollars_1780s = results_df[(results_df['currency_guess'] == 'dollars') & (results_df['decade'] == 1780)]
print(f'Total such pages: {len(dollars_1780s)}')
sample = dollars_1780s.sample(n=min(6, len(dollars_1780s)), random_state=42)
for _, r in sample.iterrows():
    full_row = df_matched[df_matched['filename'] == r['filename']].iloc[0]
    text = str(full_row['new_ocr_text'])
    signals = check_page_signals(text)
    print(f'\n  {r["filename"]} (year={r["year"]}, label={r["label"]}, goods_price_count={r["goods_price_count"]})')
    print(f"  currency_guess: {signals['currency_guess']}")
    print(f"  dollar_evidence: {signals['dollar_evidence']}")
    print(f"  has_per_cent: {signals['has_per_cent']}, has_per_ct: {signals['has_per_ct']}, has_cent_abbrev: {signals['has_cent_abbrev']}")
    # Show what fired
    for pattern_name, pattern in [
        ('dollar_sign', DOLLAR_SIGN_PATTERN),
        ('dollars_word', DOLLARS_WORD_PATTERN),
        ('dolls_cts_heading', DOLLS_CTS_HEADING_PATTERN),
        ('dc_heading', DC_HEADING_PATTERN),
        ('range_pattern', RANGE_PATTERN),
    ]:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - 80)
            end = min(len(text), match.end() + 80)
            print(f"    Fired [{pattern_name}]: ...{repr(text[start:end])}...")
            break
    else:
        print(f"    No specific dollar pattern matched (may be range_pattern without context)")
    is_goods = 'YES' if r['goods_price_count'] > 0 else 'NO'
    print(f"  >>> GOODS PRICE LIST: {is_goods}")