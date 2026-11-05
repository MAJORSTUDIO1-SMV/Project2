# Process Log

## 2026-10-31 — Dataset Download
**Instruction:** Check Python 3, create `.venv`, install `datasets` and `pandas`; download `visualizedata/price-currents-pages` (train split) and save as `raw/price_currents_pages.parquet` without modification.

**Created/Changed:**
- `.venv/` virtual environment
- `raw/price_currents_pages.parquet` (55 MB, 2,464 rows, 6 columns: filename, collection, page_number, new_ocr_text_list, new_ocr_text, OCR_run_ID)

**Found:** 2,464 rows; 2 filenames (`parse_backup_0`) don't match the `newspaper_id_YYYY-MM-DD_edition.pdf` pattern.

**Problems/Decisions:** None.

---

## 2026-10-31 — Filename Split
**Instruction:** Write `scripts/split_filename.py` to parse filename into `newspaper_id`, `date` (YYYY-MM-DD), `edition`; report non-matching; save `clean/sample_20.json` with 20 rows (10 earliest dates + 10 random, seed=42) with specific fields.

**Created/Changed:**
- `scripts/split_filename.py`
- `clean/unmatched_rows.json` (2 rows, both `parse_backup_0`)
- `clean/sample_20.json` (20 rows)

**Found:** 2,462 matched, 2 unmatched; earliest date 1774-11-28 (`sn83021126`).

**Problems/Decisions:** Pattern matches standard filenames; `parse_backup_0` are backup entries, excluded from analysis.

---

## 2026-10-31 — Counts and Quality Checks
**Instruction:** Using `raw/price_currents_pages.parquet` and `scripts/split_filename.py`: (1) show 2 unmatched rows, save to `clean/unmatched_rows.json`; (2) count pages per year → `clean/pages_per_year.csv`; (3) count pages per newspaper_id → `clean/pages_per_newspaper.csv`; (4) check duplicates on (newspaper_id, date, page_number); (5) text length min/median/max, pages >100k chars; (6) for 3 earliest pages, print ~600 chars around first "price current" match and assess if real price list.

**Created/Changed:**
- `clean/unmatched_rows.json` (already existed)
- `clean/pages_per_year.csv` (37 years, 1774–1810)
- `clean/pages_per_newspaper.csv` (66 newspapers, top: `sn84024710` 410 pages)
- Console output for all checks

**Found:** 1 duplicate combo (`sn82014782_1789-08-08` page 1, editions 1&2); text length min 1,870 / median 17,540 / max 38,211; 0 pages >100k; all 3 earliest pages have real "PRICE CURRENT IN PHILADELPHIA" tables in L.s.d. format.

**Problems/Decisions:** Duplicates are different editions, not true duplicates; L.s.d. format confirmed for early pages.

---

## 2026-11-01 — CLAUDE.md and Schema Creation
**Instruction:** Create `CLAUDE.md` (project notes, rules, working style) and `schema/price_observation_schema.json` (51 fields in 7 groups + 3 examples from provided text snippets).

**Created/Changed:**
- `CLAUDE.md` (project rules: capture all price lists any currency, keep raw_text, never fix OCR, L.s.d. triple rule, no currency conversion, etc.)
- `schema/price_observation_schema.json` (51 fields, 3 examples: TOBACCO 5 50 a 6, Bacon lb. 12 1/2 scarce, Flour at 3l. 10s. per Cent.)

**Found:** Schema validates; examples match rules (D.C. column, cents column, L.s.d. with date_stated/repeated_notice).

**Problems/Decisions:** None.

---

## 2026-11-01 — First Page Classification (v1)
**Instruction:** Write `scripts/classify_pages.py` with simple rules (no LLM): signals for price current heading, price patterns (D.C., "a" range, L.s.d. triple), commodity words, table description, assize, exchange/financial. Labels: `price_list_inline`, `price_list_lsd`, `price_list_table_description`, `assize_notice`, `exchange_or_financial`, `likely_false_positive`. Save `clean/page_classification.csv`, print counts per label and per year, 5 examples per label.

**Created/Changed:**
- `scripts/classify_pages.py`
- `clean/page_classification.csv` (2,462 pages)

**Found:** Labels: exchange_or_financial 1,123, price_list_inline 442, price_list_lsd 397, assize_notice 238, likely_false_positive 191, price_list_table_description 71.

**Problems/Decisions:** `exchange_or_financial` too large (1,123) because "stock", "course of exchange" appear inside real price lists.

---

## 2026-11-02 — Improved Classification (v2)
**Instruction:** Copy v1 to `clean/page_classification_v1.csv`. Fix: make each signal a separate boolean column; goods-prices priority (if `has_goods_prices` true, label must be price_list_* or assize); add `goods_price_count` (commodities with price pattern within 60 chars); save `clean/page_classification.csv`; print old vs new, label by decade, pages with `has_goods_prices` per year, 8 random new exchange_or_financial with context.

**Created/Changed:**
- `clean/page_classification_v1.csv` (copy)
- `scripts/classify_pages.py` (rewritten with separate signals)
- `clean/page_classification.csv` (new)

**Found:** exchange_or_financial dropped to 697 (-426); price_list_inline 613 (+171), price_list_lsd 656 (+259), price_list_table_description 138 (+67); 566 pages moved from exchange to price_list_*; goods prices grow from ~1-15/year (1770s-1790s) to 100-175/year (1800s-1810s); 8 random new exchange pages all have `goods_price_count=0`.

**Problems/Decisions:** Goods-prices priority works; but L.s.d. detection still catches false positives (e.g., `180 200 110` in dollar tables).

---

## 2026-11-02 — LSD vs Dollars Fix (v2 → v3)
**Instruction:** Copy to `clean/page_classification_v2.csv`. Fix LSD detection: triple counts only if shillings<20 and pence<12 AND context (L.s.d. heading, £, "3l. 10s."). Split COMMODITY_WORDS into real commodities (38) vs quality/trade words (10). Currency guess: prefer dollars if "D. C."/"Dolls. Cts." heading, lsd only if L.s.d. heading/valid triple/markers. Add `currency_guess` column (dollars, lsd, mixed, unknown). Print comparison, label by decade, currency_guess by decade, signals for 4 key pages, 6 random pages changed from price_list_lsd.

**Created/Changed:**
- `clean/page_classification_v2.csv` (copy)
- `scripts/classify_pages.py` (stricter LSD, split commodities, currency_guess)
- `clean/page_classification.csv` (new)

**Found:** price_list_lsd drops to 445 (-211), price_list_inline rises to 796 (+183); currency_guess: 1770s mostly lsd (144), 1800s mostly dollars (804); mixed=0 (headings always decide); 3 earliest pages correctly lsd; Richmond page correctly dollars; 6 random changed pages all correctly reclassified to dollars (false LSD triples like `11 12 1`, `180 200 110` rejected).

**Problems/Decisions:** `mixed` never used because headings always present; 211 pages moved from lsd to inline were dollar tables with false LSD triples.

---

## 2026-11-03 — Dollar Signal Fix (v3 → v4)
**Instruction:** Copy to `clean/page_classification_v3.csv`. Fix `has_dollars`: true only if `$` sign + number, "Dolls. Cts.", "D. C.", "Dollars" + number. Never count "per cent", "per ct", "cent." as dollar evidence. Update `currency_guess`: both signals = mixed. Print currency_guess by decade, signals for 3 key 1770s pages, 6 random 1780s dollars pages with evidence.

**Created/Changed:**
- `clean/page_classification_v3.csv` (copy)
- `scripts/classify_pages.py` (strict dollar patterns, exclude "per cent")
- `clean/page_classification.csv` (new)

**Found:** currency_guess now has mixed (1790s: 127, 1800s: 329, 1810s: 86); 1770s: 1 dollar (Richmond 1777 "8 Dollars per Gallon"), 2 lsd; 1780s: 10 dollars (6 "dollars" word, 2 range_pattern), 6 false positives (book prices, certificates, exchange rates); Richmond 1777 correctly dollars ("8 Dollars per Gallon").

**Problems/Decisions:** "dollars" word alone catches non-price-list mentions (books, certificates); "per cent" correctly excluded.

---

## 2026-11-03 — Currency Rules Added to CLAUDE.md
**Instruction:** Add 5 rules to CLAUDE.md Rules section: (1) currency per price list from its own headings/symbols; (2) slash notation (4/6, "5 3/4 a 5 6") = shillings/pence, not dollars; (3) "per cent"/"Cent." never dollar evidence, "a" range alone not currency evidence; (4) "Spanish Milled Dollars 4/8" = exchange rate, row_kind exchange_or_financial; (5) dollars before 1790 = Continental/Spanish, currency_basis unknown unless text says paper/specie.

**Created/Changed:**
- `CLAUDE.md` (5 new rules added as Rules 28–32)

**Found:** Rules now cover currency decisions, slash notation, exchange rate handling, pre-1790 ambiguity.

**Problems/Decisions:** None.

---

## 2026-11-03 — Printed-Price Rule Added to CLAUDE.md
**Instruction:** Add rule: `price_low_as_printed`/`price_high_as_printed` must be exact printed text; if ambiguous, `price_low_value`/`price_high_value` = null, `needs_review`=true, `review_reason` explains; never compute/average/invent values not in text.

**Created/Changed:**
- `CLAUDE.md` (Rule 33 added)

**Found:** Applies to BAR IRON "180 200 110" — values should be null, needs_review true.

**Problems/Decisions:** None.

---

## 2026-11-03 — First Pilot Extraction (Richmond 1805)
**Instruction:** Write `scripts/extract_pilot.py` for ONE page (`sn84024736_1805-06-04_1.pdf`), regex only, under 120 lines, fill schema fields from filename/text, null for unclear, `needs_review` when unclear, keep `raw_text`. Save `clean/observations_pilot.json`. Show all rows.

**Created/Changed:**
- `scripts/extract_pilot.py` (199 lines — exceeds 120 target)
- `clean/observations_pilot.json` (8 rows)
- `clean/richmond_1805_list.txt` (price list section)

**Found:** 8 items extracted (TOBACCO, FLOUR, WHEAT, INDIAN CORN, WHISKEY, BACON, HEMP, BAR IRON); price list is inline text with "D. C. D. C." heading; **no units in text** (inferred by convention); BAR IRON has "180 200 110" (3 numbers, no "a") — ambiguous; BACON "50 a 60" likely cents/lb (divided by 100 in script).

**Problems/Decisions:**
- Script 199 lines (over 120 limit)
- BAR IRON parsed as 182.00 (not in text — violates new Rule 33; should be null + needs_review)
- BACON auto-divided by 100 (assumption, not from text — violates Rule 33; should flag needs_review but keep as-printed)
- Units not in text — `unit_as_printed` should be empty or null with needs_review
- No more items in list beyond the 8

---

## 2026-11-03 — Pilot Extraction v2 (Strict Rules)
**Instruction:** Copy v1 files to v2. Update schema with `unit_status`, `unit_inferred`, `unit_inference_basis`. Rewrite `scripts/extract_pilot.py`: `unit_status` = "printed" only if unit appears in text, else "not_stated" (no inference). `needs_review` only for real ambiguity (BAR IRON, BACON), not for missing units. `review_reason` empty when `needs_review` false. Re-run and show table.

**Created/Changed:**
- `clean/observations_pilot_v2.json`, `scripts/extract_pilot_v2.py`
- `schema/price_observation_schema.json` (added 3 unit fields)
- `scripts/extract_pilot.py` (209 lines)
- `clean/observations_pilot.json` (v3 output)

**Found:** 8 rows; all `unit_status = "not_stated"` (no units in Richmond list); 6 rows parsed as `dollars_cents` with numeric values; BACON & BAR IRON `needs_review=true`, `price_scale=unknown`, numeric values null; `review_reason` empty for clean rows.

**Problems/Decisions:** Script 209 lines (over 120 target). Rules now correctly implemented: no unit inference, no guessing cents, exact printed text preserved.

---

## 2026-11-03 — Item Counts & Candidate Items
**Instruction:** From pages with `has_goods_prices=True`, count pages per commodity (real words only, treat Indian corn separately). Save `clean/item_counts_by_page.csv`. Print top 40. For top 20, show pages per year 1774-1810. Find candidate items (words at line start/column break followed by price pattern), save top 80 to `clean/candidate_items.csv`.

**Created/Changed:**
- `clean/item_counts_by_page.csv` (42 items)
- `clean/candidate_items.csv` (80 items)

**Found:** Top items: flour 590, corn 554, tobacco 546, wheat 513, iron 487, bacon 463. Almost all pages 1800-1810. Top candidates: `fine` (161, quality word), `herrings` (116, real commodity missing), `bread` (115, real commodity missing), `pimento` (109, real commodity missing), `antigua` (109, origin), `loaf` (108, unit/form), `bar` (107, OCR fragment of BAR IRON), `duck` (107, real commodity missing), `pilot` (107, quality), `pepper` (106, real commodity missing), `indigo` (102, real commodity missing), `do.` (102, OCR artifact), `shad` (101, real commodity missing).

**Problems/Decisions:** 14 real commodities missing from list (herrings, bread, pimento, duck, pepper, indigo, shad, port, flaxseed, gin, gunpowder, hyson, chocolate, glass). Several OCR artifacts (bar, indian, per., do., dolls.) and quality words (fine, pilot, loaf, lump, dipt, ship, white, young, ravens). Place/origin modifiers (antigua, malaga, lisbon, potomac, windward).

---

## 2026-11-03 — Blocks Dataset Download
**Instruction:** Write `scripts/download_blocks.py` to download `visualizedata/price-currents-blocks` (train split) and save as `raw/price_currents_blocks.parquet`. Print stats: rows, columns, block_type counts, unique filenames, rows per year, Table blocks with digits.

**Created/Changed:**
- `scripts/download_blocks.py`
- `raw/price_currents_blocks.parquet` (2,751 rows, 9 columns)

**Found:** 2,751 blocks across 2,310 unique filenames. Block types: SectionHeader 1,556, Text 1,077, Table 89, ListGroup 28, ComplexRegion 1. Years 1774-1810 (matching pages dataset). 89 Table blocks, 85 contain at least one digit in block_markdown.

**Problems/Decisions:** Blocks dataset provides structured markdown/html for each block; can be used for more precise table extraction later. 2,310 unique filenames vs 2,462 pages — some pages have no blocks or multiple blocks per page.

---

## 2026-11-04 — Blocks to JSON & Analysis
**Instruction:** Write `scripts/blocks_to_json.py` to convert blocks parquet to JSON; analyze Table blocks (per year, per newspaper, pipe tables with numbers, descriptive only); count SectionHeader with "price current" and top 20 headings; check 5 random heading blocks against pages dataset for price list following; count filename overlap between blocks and pages.

**Created/Changed:**
- `scripts/blocks_to_json.py`
- `clean/blocks_md.json` (2,751 blocks)
- `clean/table_blocks_md.json` (89 Table blocks)

**Found:**
- Table blocks: 89 total; 66 have markdown pipe tables with numbers; 1 descriptive only ("Table with..."); years 1781–1810 (mostly 1800s); top newspapers: sn84024710 (25), sn83030483 (14), sn84024736 (10).
- SectionHeader with "price current": 967 of 1,556. Top headings: "## Richmond Price Current." (132), "PRICE CURRENT.—PUBLIC SECURITIES." (123), "**Alexandria Price Current.**" (115).
- 5 random heading checks: 2/5 have price list immediately following (Richmond 1807, New-York 1787); 2/5 have other text first (Richmond 1805 subscription, Portsmouth 1803 congress); 1/5 is securities not goods (Philadelphia 1790).
- Filename overlap: blocks 2,310 unique filenames, pages 2,309 valid filenames, intersection 2,309 (1 filename in blocks only: parse_backup_0 variant).

**Problems/Decisions:** One descriptive Table block (not pipe format). Many "PRICE CURRENT" headings are for securities/financial pages, not goods price lists. Filename overlap is near-perfect (2,309/2,310). The blocks dataset can help locate price tables precisely within pages.

---

## 2026-11-04 — Heading-to-List Linking
**Instruction:** Write `scripts/link_headings_to_lists.py` to link every short SectionHeader/Text block containing "price current" to its following price list in the pages dataset. Search 12 items after heading, count number patterns and commodity words, pick first with ≥4 numbers or ≥3 commodities. Save `clean/heading_links.json`. Print stats, specific file checks, 10 examples, and flag potential wrong links.

**Created/Changed:**
- `scripts/link_headings_to_lists.py`
- `clean/heading_links.json` (1,229 links)

**Found:**
- 1,229 candidate headings (short SectionHeader/Text with "price current")
- 440 (36%) have `list_found=True`
- By decade: 1770s 3/132, 1780s 41/126, 1790s 126/284, 1800s 227/579, 1810s 43/108
- Specific files:
  - sn84024710_1805-09-04_1.pdf: list_found=True (distance=1, kind=goods) — but list_text is "Table with 2 columns..." (OCR description, not actual prices) — **WRONG LINK**
  - sn84023379_1803-04-05_1.pdf: list_found=False (heading is PORTSMOUTH PRICE CURRENT mixed with newspaper title)
  - sn83030483_1790-11-27_1.pdf: list_found=True (distance=1, kind=unknown) — correctly links to securities table
- 10 examples show good goods lists (Cadiz 1805, Demarara 1787, Savannah 1799, Liverpool 1799) and financial lists (Philadelphia 1791, Boston 1791)
- **Potential wrong links flagged:** 5 financial lists misclassified as goods; some with distance > 5

**Problems/Decisions:**
- The Richmond 1805 page (sn84024710_1805-09-04_1.pdf) falsely links to an OCR description "Table with 2 columns..." instead of the actual price list — the "Table with" text has many commodity words and counts as a false positive.
- sn84023379_1803-04-05_1.pdf heading not found in text_list (multi-line heading with newspaper title).
- The `is_heading_like` stop condition doesn't catch "Table with" descriptions, allowing them to be selected as lists.
- Financial lists (securities) often have many number patterns but few commodities, yet some are misclassified as goods because commodity count threshold is met by coincidence.
- Need to exclude "Table with" descriptions and improve financial detection.

---

## 2026-11-04 — Table Block Parsing Pilot
**Instruction:** Update schema with block_id, block_type, source_dataset, market_place; update CLAUDE.md with notes on multiple market columns and market_place vs publication place; pick 5 Table blocks from different newspaper_ids/years with real markdown pipe tables; write scripts/parse_table_blocks.py to parse tables into observations following schema rules (exact printed prices, null when ambiguous, needs_review with reason, parse_method="table_parse"). Print all extracted rows, identify OCR errors. Save clean/observations_blocks_pilot.json.

**Created/Changed:**
- `schema/price_observation_schema.json` (added block_id, block_type, source_dataset; updated market_place description)
- `CLAUDE.md` (added rules: multiple observations per row for multi-market tables; market_place from heading not publication city)
- `scripts/parse_table_blocks.py`
- `clean/observations_blocks_pilot.json` (257 observations from 3 of 5 tables)

**Found:**
- 5 Table blocks selected: Natchez/N. Orleans 1802 (sn82014782), Boston 1803 (sn83016072), Portland 1804 (sn83016081), Providence bank notes 1809 (sn83025442), Cadiz/Liverpool 1800 (sn83025588)
- 3 of 5 tables parsed successfully (Natchez, Boston, Portland); 2 tables (Providence bank notes, Cadiz/Liverpool) yielded 0 observations due to non-standard table structures
- 257 total observations extracted (26 from Natchez, 139 from Boston, 92 from Portland)
- Market place extraction works for Boston ("Boston.**") and Portland ("Portland.**") but fails for Natchez/N. Orleans (returns "Prices Current" instead of "Natchez" and "N. Orleans")
- OCR errors flagged: "unfaleable" (Peach Brandy), "braped fane" (Indian Corn), "sysil" (Caudies tal. mo. Am.), "duto" (d.p.t. do.), "cau" (Caudies), "braped" (Indian Corn), "fane" (Indian Corn)
- Price parsing works for D.C. format ("23" → 23.0), range format ("50—73" → 50.0-73.0), and shilling format ("33—136 66" partially parsed)
- Issues: market_place extraction returns heading text instead of location for multi-market tables; unit extraction fails for most items; continuation rows (starting with —) should be merged with previous row; multi-market tables (Natchez/N. Orleans) need one observation per market column per row; bank notes table and Cadiz/Liverpool table have non-standard structures not handled

**Problems/Decisions:**
- Multi-market tables (e.g., Natchez | N. Orleans with D.C. columns for each) need one observation per market column per row
- Market place extraction from table heading needs improvement for multi-market tables
- Continuation rows (starting with —) need to be merged with previous row's item
- Unit extraction fails for most items (units embedded in item name like "per cwt.", "per ton", "lb.")
- Bank notes table and Cadiz/Liverpool table have different structures requiring special handling
- Need to handle "do." and "—" continuation rows properly

---

## 2026-11-04 — Heading-to-List Linking v2
**Instruction:** Copy `clean/heading_links.json` to v1. Update `scripts/link_headings_to_lists.py`: (1) items starting with "Table with" → list_status "described_only", don't count words; (2) goods lists need ≥4 number patterns; (3) financial if text has "securities", "stock", "bank", "exchange" and few commodities; (4) if heading inside longer text item, check same item for numbers → list_status "inline_in_heading_block"; (5) extract market_place from heading (word after "at"/"in"). Save with list_status (found, described_only, inline_in_heading_block, financial, not_found). Print counts by decade, top 15 market_places, 10 examples, why 5 1770s headings not found.

**Created/Changed:**
- `clean/heading_links_v1.json` (copy)
- `scripts/link_headings_to_lists.py` (updated)
- `clean/heading_links.json` (1,229 links)

**Found:**
- 1,229 candidate headings (short SectionHeader/Text with "price current")
- List status counts: found=295, described_only=103, financial=56, not_found=775, inline_in_heading_block=0
- By decade: 1770s 3/132 found, 1780s 34/126 found, 1790s 62/284 found, 1800s 155/579 found, 1810s 41/108 found
- Top market_places: New-York (196), Philadelphia (3), Demarara (1), Aux-Cayes (1), Liverpool (1)
- 10 examples: goods lists (Cadiz 1805, Demarara 1787, Savannah 1799, Liverpool 1799) and financial lists (Philadelphia 1791, Boston 1791)
- Specific files: Richmond 1805 → described_only (links to "Table with..." OCR description); Portsmouth 1803 → not_found (multi-line heading); Philadelphia 1790 securities → found (financial)
- 1770s analysis: 132 headings, 129 not found — all 5 checked found at position 0 in text_list but with 0 chars (empty string in text_list), so heading match succeeds but item is empty

**Problems/Decisions:**
- 1770s pages have empty strings in text_list at position 0 where heading matches, causing false "found" but no actual text
- "Table with" OCR descriptions now correctly marked as described_only (103 cases)
- Financial detection works: 56 financial lists identified, including securities pages
- Market place extraction partially works (New-York 196, Demarara, Aux-Cayes, Liverpool) but misses many (Philadelphia, Boston, Savannah, etc.)
- inline_in_heading_block never triggered — heading text is never a substring of a longer text item in practice
- Market place extraction needs improvement for headings like "PRICE CURRENT IN PHILADELPHIA" (no "at"/"in" preposition)

---

## 2026-11-04 — Two-Table Split & Financial Quotes Schema
**Instruction:** (1) Add "Two Tables" section to CLAUDE.md: Table 1 goods_prices (row_kind = goods_price or assize; never financial) and Table 2 financial_quotes (exchange_rate, public_security, bank_stock, insurance_stock, interest_or_premium, other); both share source/date/place; financial quotes inside goods list keep that list's price_list_id; no currency conversion; financial quotes feed currency_rates.csv but only reviewed values go in. (2) Update price_observation_schema.json: row_kind enum now only [goods_price, assize]. (3) Create schema/financial_quotes_schema.json with 28 fields and 3 real examples from data: exchange rate (Spanish Milled Dollars 4/8, Charleston 1788), public security (6 per Cents 17 3/4 pr. £. or 37 1/2 per cent., Philadelphia 1791), bank stock (Bank Stock whole shares 65 per cent, half shares 109 per cent premium, Philadelphia 1792). (4) Add entry to process_log.md.

**Created/Changed:**
- `CLAUDE.md` (added "Two Tables" section with rules for goods_prices and financial_quotes tables)
- `schema/price_observation_schema.json` (row_kind enum now ["goods_price", "assize"])
- `schema/financial_quotes_schema.json` (28 fields, 3 real examples from data)

**Found:**
- Exchange rate example: "Spanish Milled Dollars 4/8" from Charleston 1788 (sn83030007_1788-12-12_1.pdf) — 4 shillings 8 pence sterling per Spanish Milled Dollar
- Public security example: "6 per Cents 17 3/4 pr. £. or 37 1/2 per cent." from Philadelphia 1791 (sn83025587_1791-02-05_1.pdf) — US 6% bond at 108.75% of par
- Bank stock example: "Bank Stock--whole shares 65 per cent. --half shares 109 per cent premium." from Philadelphia 1792 (sn83030483_1792-02-01_1.pdf) — whole shares at 65% of par, half shares at 209% of par (109% premium)

- reference/currency_rates.csv will be built later from reviewed financial_quotes only

---

## 2026-11-04 — Enhanced Rules & Schema Updates
**Instruction:** Add 10 new rules to CLAUDE.md covering: (1) needs_review=true → all numeric fields null; (2) price_low ≤ price_high; (3) From/To Dols./Cts. tables with split cells; (4) one observation per market per item, market_place cleaned, no "Prices Current"; (5) do./ditto handling with unit_status "ditto_of_previous"; (6) cents vs dollars with price_scale "unknown" and plausibility_flag; (7) availability terms in availability_note; (8) financial schema updates (percent_discount, unclear, interpretation_note, plausibility_flag); (9) bank-note discount tables to financial_quotes; (10) arithmetic only in interpretation_note. Update both schemas accordingly.

**Created/Changed:**
- `CLAUDE.md` (added 10 new rules at lines 34-43)
- `schema/price_observation_schema.json` (added `plausibility_flag`, `interpretation_note`, updated `unit_status` enum with `ditto_of_previous`)
- `schema/financial_quotes_schema.json` (added `percent_discount`, `unclear` to `quote_basis`; added `interpretation_note`)

**Found:**
- Both schemas now have `interpretation_note` field
- goods_prices schema: 58 fields (was 56), added `plausibility_flag`, `interpretation_note`
- financial_quotes schema: 36 fields (was 35), added `interpretation_note`
- `quote_basis` enum now includes `percent_discount` and `unclear` (7 values total)
- `unit_status` enum now includes `ditto_of_previous` (4 values total)
- goods schema has `plausibility_flag` boolean field
- Both schemas have `interpretation_note` field

**Problems/Decisions:**
- All new rules are explicit in CLAUDE.md lines 34-43
- Schema updates are backward-compatible (new fields are optional)
- The `plausibility_flag` in goods schema will help catch outlier prices during review
- `ditto_of_previous` unit_status handles chained unit references across rows
- `percent_discount` in quote_basis handles bank-note discount tables
- `unclear` in quote_basis handles ambiguous financial quotes

---

## 2026-11-04 — Financial Quotes Examples Fixed & Fourth Added
**Instruction:** Fix three examples in financial_quotes_schema.json (Charleston Spanish Milled Dollars 4/8, Philadelphia 6 per Cents, Philadelphia Bank Stock) by removing computed values, setting quote_basis unclear, needs_review true with reasons. Add fourth example from Providence 1809 bank notes table (New-Hampshire bills 3 to 6 per cent. dis.) with quote_kind other, basis percent_discount. All computed values set to null, quote_basis unclear where ambiguous, needs_review true with reasons. Exact printed text preserved.

**Created/Changed:**
- `schema/financial_quotes_schema.json` (updated 3 examples, added 4th)

**Found:**
- Exchange rate: "Spanish Milled Dollars 4/8" (Charleston 1788) — from_currency "Spanish milled dollar", to_currency "not stated", quote_basis unclear, needs_review true; interpretation_note: 4/8 may be shillings/pence of local currency
- Public security: "6 per Cents 17 3/4 pr. £. or 37 1/2 per cent." (Philadelphia 1791) — quote_basis unclear, needs_review true; both values as printed, basis unclear
- Bank stock: "Bank Stock--whole shares 65 per cent. --half shares 109 per cent premium." (Philadelphia 1792) — quote_basis unclear, needs_review true; line doesn't say if 65% and 109% are premiums or percentages of par
- Bank notes (4th): "Bills of the New-Hampshire... 3 to 6 per cent. dis." (Providence 1809) — quote_kind other, basis percent_discount, exact text preserved

**Problems/Decisions:**
- All computed values (108.75%, 209%, 109%, etc.) removed; set to null per rules
- quote_basis set to "unclear" where text doesn't specify basis
- needs_review=true with specific reasons for each
- interpretation_note added explaining the ambiguity
- Fourth example from Providence 1809 bank notes table added with exact text
- Bank-note discount tables now properly classified with percent_discount basis

---

## 2026-11-04 — Fourth Example Fixed: Providence 1809 Bank Notes
**Instruction:** Fix the fourth example in financial_quotes_schema.json (Providence 1809 bank notes table). Corrections: block_id must be /page/2/Table/22 (block containing "J. B. WOOD'S"); quote_as_printed must be exactly "3 to 6 per cent. dis." with no ellipsis; quote_low_as_printed "3" and quote_high_as_printed "6"; instrument_as_printed must be "Bills of the New-Hampshire, ditto payable in Philadelphia, Portsmouth, Union, Strafford, and Exeter Banks". All computed values already null, quote_basis "percent_discount", needs_review true.

**Created/Changed:**
- `schema/financial_quotes_schema.json` (fixed fourth example)

**Found:**
- block_id corrected to /page/2/Table/22 (block containing "J. B. WOOD'S")
- quote_as_printed now exactly "3 to 6 per cent. dis." (no ellipsis)
- instrument_as_printed: "Bills of the New-Hampshire, ditto payable in Philadelphia, Portsmouth, Union, Strafford, and Exeter Banks"
- quote_low_as_printed "3", quote_high_as_printed "6"
- All numeric values null, quote_basis "percent_discount", needs_review true

**Problems/Decisions:**
- Block ID verified against clean/table_blocks_md.json (block containing "J. B. WOOD'S")
- quote_as_printed now exactly matches the printed text "3 to 6 per cent. dis." with no ellipsis
- All four examples now consistent: exact printed text, null computed values, needs_review true with reasons

---

## 2026-11-04 — Gold Standard & Parser v2 Plan
**Instruction:** Create tests/gold_natchez_1802.json for the Natchez/N. Orleans 1802 table with human-verified expectations for each row and market. Write parser_v2_plan.md addressing: two-market tables, From/To tables with split cents, ranges with dashes, D.C. pairs vs cents columns, ditto handling, availability words, single-column tables, financial tables, OCR errors, field-level suspect flagging, plausibility flag, and scoring against gold.

**Created/Changed:**
- `tests/gold_natchez_1802.json` (12 expectations with block_markdown for each)
- `scripts/parser_v2_plan.md` (detailed plan for parser v2)

**Found:**
- 5 blocks analyzed: Natchez (2 markets), Boston (From/To Dols./Cts.), Portland (From/To with dashes), Providence (bank notes), Cadiz (single-column Dollars)
- 10 major problems identified with specific solutions and "flag instead of guess" principles
- Field-level suspect flagging proposed (don't null entire row for one bad field)
- Plausibility flag for outlier detection
- Scoring formula with field weights and passing thresholds
- Implementation phased in 6 phases

**Problems/Decisions:**
- Multi-market tables need one observation per market per row
- From/To tables require rebuilding split Dols./Cts. cells
- Ditto rows must be chained to previous item
- Availability words (none, unsaleable, scarce) go in availability_note, not price fields
- Cents vs dollars ambiguity requires price_scale "unknown" + needs_review + plausibility_flag
- Single-column tables (Cadiz) and financial tables (Providence) need separate handling
- Field-level suspect flagging: don't null entire row for one bad field
- Scoring harness with field weights and passing threshold (≥90 gold, ≥75 acceptable)
- Implementation in 6 phases, starting with multi-market and ditto handling