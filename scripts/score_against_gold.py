#!/usr/bin/env python3
"""
Score parser output against gold standard.
"""

import json
from typing import List, Dict, Any

def load_json(path: str) -> Any:
    with open(path) as f:
        return json.load(f)

def match_observations(extracted: List[Dict], gold: List[Dict]) -> Dict:
    """Match extracted observations to gold expectations by item_as_printed + market."""
    gold_by_key = {}
    for exp in gold:
        for market, vals in exp['markets'].items():
            key = (exp['item_as_printed'], market)
            if key not in gold_by_key:
                gold_by_key[key] = []
            gold_by_key[key].append({'exp': exp, 'market': market, 'vals': vals})

    extracted_by_key = {}
    for obs in extracted:
        key = (obs['item_as_printed'], obs.get('market_place', ''))
        if key not in extracted_by_key:
            extracted_by_key[key] = []
        extracted_by_key[key].append(obs)

    # Match
    matched = []
    wrong_values = []
    missing = []
    extra = []

    matched_gold = set()
    matched_extracted = set()

    for key, gold_list in gold_by_key.items():
        if key in extracted_by_key:
            ext_list = extracted_by_key[key]
            for i, gold_item in enumerate(gold_list):
                if i < len(ext_list):
                    ext = ext_list[i]
                    gold_exp = gold_item['exp']
                    market = gold_item['market']
                    gold_vals = gold_item['vals']

                    # Compare fields
                    mismatches = []
                    fields = ['price_low_as_printed', 'price_high_as_printed',
                             'price_low_value', 'price_high_value', 'price_scale',
                             'unit_as_printed', 'unit_status', 'availability_note',
                             'needs_review', 'review_reason']

                    for field in fields:
                        gold_val = gold_vals.get(field)
                        ext_val = ext.get(field)
                        if gold_val != ext_val:
                            mismatches.append(f"{field}: gold={gold_val} vs extracted={ext_val}")

                    if mismatches:
                        wrong_values.append({
                            'item': key[0],
                            'market': key[1],
                            'mismatches': mismatches,
                            'gold': gold_vals,
                            'extracted': {f: ext.get(f) for f in ['price_low_as_printed', 'price_high_as_printed', 'price_low_value', 'price_high_value', 'price_scale', 'unit_as_printed', 'unit_status', 'availability_note', 'needs_review', 'review_reason']}
                        })
                    else:
                        matched.append({'item': key[0], 'market': key[1]})
                    matched_gold.add((key, i))
                    matched_extracted.add((key, i))
                else:
                    missing.append({'item': key[0], 'market': key[1], 'gold': gold_vals})

    # Check for extra extracted rows
    for key, ext_list in extracted_by_key.items():
        for i, ext in enumerate(ext_list):
            if (key, i) not in matched_extracted:
                extra.append({'item': key[0], 'market': key[1], 'extracted': ext})

    # Count missing
    for key, gold_list in gold_by_key.items():
        for i, gold_item in enumerate(gold_list):
            if (key, i) not in matched_gold:
                missing.append({'item': key[0], 'market': key[1], 'gold': gold_item['vals']})

    return {
        'matched': matched,
        'wrong_values': wrong_values,
        'missing': missing,
        'extra': extra,
        'total_gold': sum(len(v) for v in gold_by_key.values()),
        'total_extracted': sum(len(v) for v in extracted_by_key.values())
    }

def load_gold(path: str) -> List[Dict]:
    with open(path) as f:
        data = json.load(f)
    return data['human_expectations']

def load_extracted(path: str) -> List[Dict]:
    with open(path) as f:
        return json.load(f)

def main():
    gold = load_gold('tests/gold_natchez_1802.json')
    extracted = load_json('clean/observations_blocks_pilot.json')

    # Only Natchez block
    natchez_extracted = [o for o in extracted if o['filename'] == 'sn82014782_1802-04-09_1.pdf']

    print(f"Gold expectations: {sum(len(e['markets']) for e in load_json('tests/gold_natchez_1802.json')['human_expectations'])} per-market expectations")
    print(f"Extracted observations: {len(natchez_extracted)}")

    result = match_observations(natchez_extracted, load_json('tests/gold_natchez_1802.json')['human_expectations'])

    print(f"\n=== SCORING RESULTS ===")
    print(f"Total gold per-market expectations: {result['total_gold']}")
    print(f"Total extracted: {result['total_extracted']}")
    print(f"Rows matched: {len(result['matched'])}")
    print(f"Wrong values: {len(result['wrong_values'])}")
    print(f"Missing rows: {len(result['missing'])}")
    print(f"Extra rows: {len(result['extra'])}")

    # Score
    score = (len(result['matched']) / result['total_gold']) * 100
    score -= (len(result['wrong_values']) / result['total_gold']) * 10
    score -= (len(result['missing']) / result['total_gold']) * 15
    score -= (len(result['extra']) / max(1, len(natchez_extracted))) * 10

    print(f"\nScore: {score:.1f}")
    print(f"Passed (>=90): {score >= 90}")
    print(f"Acceptable (>=75): {score >= 75}")

    # Print mismatches
    if result['wrong_values']:
        print(f"\n=== WRONG VALUES ({len(result['wrong_values'])}) ===")
        for wv in result['wrong_values']:
            print(f"\n  Item: {wv['item']} | Market: {wv['market']}")
            for m in wv['mismatches']:
                print(f"  {m}")

    if result['missing']:
        print(f"\n=== MISSING ROWS ({len(result['missing'])}) ===")
        for m in result['missing']:
            print(f"  {m['item']} | {m['market']}")

    if result['extra']:
        print(f"\n=== EXTRA ROWS ({len(result['extra'])}) ===")
        for e in result['extra']:
            print(f"  {e['item']} | {e['market']}")

if __name__ == '__main__':
    main()