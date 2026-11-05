# Parser v2 Plan

## Overview
This document outlines a plan for parser v2 that addresses the limitations of the current parser (parse_table_blocks.py) by handling the various table structures and edge cases identified in the gold standard and pilot observations.

## 5 Blocks Analyzed
1. **Natchez/N. Orleans 1802** (sn82014782) - Two-market D.C. table
2. **Boston 1803** (sn83016072) - From/To Dols./Cts. table with em-dash ranges
3. **Portland 1804** (sn83016081) - From/To Dols./Cts. with em-dash ranges and continuation rows
4. **Providence 1809** (sn83025442) - Bank note discount table (single column, non-standard)
5. **Cadiz/Liverpool 1800** (sn83025588) - Single-column Dollars table with ranges

---

## Problem Analysis & Solutions

### 1. Two-Market Tables (Natchez/N. Orleans)
**Problem**: Header shows `D. | C. | D. | C.` for two markets (Natchez, New Orleans). Current parser creates 3 column pairs instead of 2, producing duplicate observations per row.

**Solution**:
- Detect multi-market headers by finding market names in the header rows (before the separator line)
- Parse market names from the heading area (lines before the table header)
- Create exactly one column pair per market
- For each row, create one observation per market with its own `market_place`
- Map columns: Natchez=(D,C cols 1,2), New Orleans=(D,C cols 3,4)

**Flag instead of guess**: If market names cannot be extracted from header, flag entire table for manual review rather than guessing.

---

### 2. From/To Tables with Split Cents (Boston, Portland)
**Problem**: Headers show `From | To` with sub-headers `Dols. | Cts.` under each. Prices split across two cells (e.g., `133 | 33—136 66` meaning 133.33 to 136.66). Current parser treats each cell as separate price column.

**Solution**:
- Detect `From`/`To` headers with `Dols.`/`Cts.` sub-headers
- Merge the two cells per market into a single price string: `"133 33—136 66"`
- Parse the range: low=`133 33`, high=`136 66`
- Never drop cents - always preserve the Cts column
- Handle em-dash (—) as range separator

**Flag instead of guess**: If Dols./Cts. cells don't align (e.g., missing cents), flag the specific price as `needs_review` with reason "cents column ambiguous" rather than dropping cents.

---

### 3. Ranges Written with Dashes (Boston, Portland)
**Problem**: Ranges use em-dash (—) between low and high: `33—136 66`, `50—73`, `50—9`. Current parser splits on em-dash but may misparse when combined with Dols/Cts.

**Solution**:
- Detect em-dash (—) as range separator within a cell
- Split on em-dash first, then parse each side with D.C. parser
- Preserve the full printed range in `price_low_as_printed` / `price_high_as_printed`
- Handle cases where only one side has cents: `50—73` (both whole dollars) vs `33—136 66` (both have cents)

**Flag instead of guess**: If em-dash appears but sides don't parse cleanly, flag the price with `needs_review` rather than guessing.

---

### 4. D. C. Pairs vs Cents Columns
**Problem**: Some tables have D.C. pairs (Natchez, Portland), some have single Dollars column (Cadiz), some have cents-only columns (Whiskey 75 in C column). Current parser assumes D.C. pairs everywhere.

**Solution**:
- Classify table type from header:
  - `D. C. D. C.` → two-market D.C. pairs
  - `From | To` with `Dols. | Cts.` → From/To D.C. pairs
  - `Dollars.` or `Dollars` single column → single-column dollars
  - `D. C.` single pair → single-market D.C.
- For cents-only columns (e.g., Whiskey `75` in C column with empty D): 
  - If header shows D.C. but D is empty and C has value → interpret as cents
  - Set `price_scale = "cents"` and `needs_review = true` unless table context confirms
  - Flag with `plausibility_flag` if value seems implausible

**Flag instead of guess**: Never assume cents vs dollars; use `price_scale = "unknown"` and `needs_review = true` unless table context (header, other rows) makes it unambiguous.

---

### 5. Ditto Handling ("do.", "—", "do")
**Problem**: Continuation rows use `—`, `do.`, `ditto` to indicate "same as above". Current parser skips these rows entirely, losing price data.

**Solution**:
- Detect ditto markers: `—`, `do.`, `do`, `ditto` at start of item cell
- For ditto rows: inherit item name and unit from previous row
- Create observation with `unit_status = "ditto_of_previous"`
- Use previous item's category and unit unless overridden
- Track ditto chain: if multiple consecutive ditto rows, chain back to last non-ditto item

**Flag instead of guess**: If ditto chain is broken (e.g., first row is ditto), flag for review.

---

### 6. Availability Words (none, no demand, unsaleable, scarce, plenty)
**Problem**: Words like `none`, `no demand`, `unsaleable` (OCR: `unfaleable`), `scarce`, `plenty` appear in price cells but are not prices.

**Solution**:
- Before parsing price, check cell text for availability keywords:
  - `none`, `no demand`, `unsaleable`/`unfaleable` → `availability_note = "unsaleable"` (with OCR note if `unfaleable`)
  - `no demand` → `availability_note = "no demand"`
  - `scarce`, `plenty` → `availability_note = "scarce"` / `"plenty"`
- Do NOT attempt to parse these as prices
- Set `price_low_value = null`, `price_high_value = null`, `price_scale = "unknown"`, `needs_review = false`
- Keep original text in `price_low_as_printed`

---

### 7. Single-Column Tables (Cadiz)
**Problem**: Cadiz table has single `Dollars.` column with ranges like `28 a 40`. Current parser expects column pairs.

**Solution**:
- Detect single-column price tables: header has only one price column (e.g., `Dollars.`)
- Parse ranges directly: `28 a 40` → low=`28`, high=`40`
- Set `price_scale = "dollars_cents"` (or `unknown` if ambiguous)
- No column pairing needed

**Flag instead of guess**: If single column but prices look like ranges with ambiguous separators, flag.

---

### 8. Financial Tables (Providence Bank Notes)
**Problem**: Providence table is bank note discounts (`3 to 6 per cent. dis.`) not goods prices. Current parser tries to parse as goods table and produces 0 observations.

**Solution**:
- Detect financial tables early by:
  - Heading contains "Bank Notes", "Discount", "Exchange", "Stocks"
  - Cells contain `%`, `per cent.`, `dis.`, `par`, `premium`
  - No commodity units (cwt, bbl, lb, etc.)
- Route to financial_quotes parser instead of goods parser
- For bank-note tables: each row = one quote with `quote_kind = "other"` or `exchange_rate`, `quote_basis = "percent_discount"`
- Preserve exact printed text: `quote_as_printed = "3 to 6 per cent. dis."`

---

### 9. Continuation Rows (—, do., ditto)
**Problem**: Rows starting with `—` or `do.` continue the previous item. Current parser skips them.

**Solution**:
- See ditto handling above (Problem 5)
- For `—` continuation rows: inherit item name from previous row, but price cells are new
- Create separate observation with `unit_status = "ditto_of_previous"`
- Link to previous observation via `item_as_printed` and same `price_list_id`

---

### 10. OCR Errors & Suspect Fields
**Problem**: OCR errors like `unfaleable` (unsaleable), `braped` (braided), `fane` (famed), `sysil`, `duto` appear in text. Current parser flags entire row.

**Solution - Field-Level Flagging**:
- Don't null entire row for one suspect field
- Add field-level `suspect` flag in observation:
  ```json
  "price_high_as_printed": "unfaleable",
  "price_high_suspect": true,
  "price_high_suspect_reason": "OCR error: unfaleable (likely unsaleable)"
  ```
- Keep good fields (price_low, item, unit) intact
- Only null the specific suspect numeric field

**Plausibility Flag**:
- After parsing all rows in a table, compute median/mean price per commodity
- Flag outliers: `plausibility_flag = true` if price > 3x IQR from median
- Add `plausibility_reason`: "Price 182.00 far exceeds median 18.5 for BAR IRON"

---

## Scoring Against Gold File

### Metrics
| Metric | Definition |
|--------|------------|
| **Rows Matched** | Extracted observation matches gold item_as_printed + market_place |
| **Wrong Values** | Extracted row matches gold item but price/unit/scale differs |
| **Missing Rows** | Gold row has no matching extracted observation |
| **Extra Rows** | Extracted row has no matching gold row |
| **Field Accuracy** | % of fields matching gold (per field: price_low, price_high, unit, scale, etc.) |

### Scoring Formula
```
Score = (Rows_Matched / Gold_Rows) * 100
     - (Wrong_Values / Gold_Rows) * 10
     - (Missing_Rows / Gold_Rows) * 15
     - (Extra_Rows / Extracted_Rows) * 10
     + (Field_Accuracy_Bonus) * 5
```

### Field-Level Scoring
| Field | Weight |
|-------|--------|
| item_as_printed | 3 |
| market_place | 3 |
| price_low_as_printed | 3 |
| price_high_as_printed | 3 |
| price_low_value | 3 |
| price_high_value | 3 |
| price_scale | 2 |
| unit_as_printed | 2 |
| unit_status | 1 |
| needs_review | 1 |
| availability_note | 1 |

### Passing Threshold
- **Gold Standard**: Score ≥ 90
- **Acceptable**: Score ≥ 75
- **Needs Work**: Score < 75

---

## Implementation Priority

| Phase | Problems | Dependencies |
|-------|----------|--------------|
| 1 | Multi-market detection, ditto handling, availability words | None |
| 2 | From/To split cents, D.C. pair detection, ditto chaining | Phase 1 |
| 3 | Range parsing (em-dash), single-column tables | Phase 1 |
| 4 | OCR error detection, plausibility flag | Phase 1-3 |
| 5 | Financial table routing | Phase 1-2 |
| 6 | Field-level flagging, scoring harness | All above |

---

## When to Flag vs Guess

| Situation | Action |
|-----------|--------|
| Market names not in header | Flag table, don't guess markets |
| Cents column ambiguous (empty D, value in C) | Flag specific price, `needs_review=true` |
| Em-dash range unparsable | Flag price, keep printed text |
| Ditto chain broken (first row is ditto) | Flag row, don't guess previous item |
| OCR error in single field | Flag only that field, keep others |
| Price implausible (plausibility_flag) | Flag field, don't null |
| Financial table detected | Route to financial parser, don't force goods parsing |
| Single-column table with ranges | Parse ranges, don't guess column pairs |
| Availability words in price cell | Move to availability_note, don't parse as price |

---

## Field-Level Suspect Flagging (New Design)

Add to observation schema:
```json
"price_low_suspect": false,
"price_low_suspect_reason": "",
"price_high_suspect": false,
"price_high_suspect_reason": "",
"unit_suspect": false,
"unit_suspect_reason": ""
```

When a specific field is suspect:
- Set `_suspect = true`
- Set `_suspect_reason = "..."`
- Keep other fields intact
- `needs_review = true` (row-level)
- Don't null the suspect field's printed text; only null the computed `_value`

---

## Scoring Harness

```python
def score_against_gold(extracted: List[Dict], gold: List[Dict]) -> Dict:
    # Match by item_as_printed + market_place
    # Compute metrics
    return {
        "rows_matched": 0,
        "wrong_values": 0,
        "missing_rows": 0,
        "extra_rows": 0,
        "field_accuracy": {},
        "score": 0.0,
        "passed": False
    }
```

Run: `python scripts/score_parser.py --gold tests/gold_natchez_1802.json --extracted clean/observations_blocks_pilot.json`

---

## Summary of Changes Needed

| Component | Changes |
|-----------|---------|
| `parse_table_blocks.py` | Complete rewrite with modular functions for each problem type |
| `schema/price_observation_schema.json` | Add `price_low_suspect`, `price_high_suspect`, `suspect_reason` fields |
| `gold_natchez_1802.json` | Already created as gold standard |
| `scripts/score_parser.py` | New scoring harness |
| `tests/` | Add gold files for Boston, Portland tables |