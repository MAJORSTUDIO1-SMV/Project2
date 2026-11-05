# Project Notes: Price Currents Dataset

**Goal:** Build a dataset of price currents from the Revolution Crossroads newspaper data (1770–1810) that tracks item prices through time and by place of publication.

**Folders:**
- `raw/` = original data (never modify or delete)
- `clean/` = outputs
- `scripts/` = code
- `schema/` = data structure

## Rules

- **Capture ALL price lists and price tables** in any currency (dollars, pounds shillings pence, coppers, or other), including exchange rates and financial prices that appear inside them.
- **Never drop a table because of its currency.**
- Only pages that are **not price lists at all** (poems, speeches, news) are excluded, and they are tracked in the page classification.
- Keep the **original text of every row** in `raw_text`.
- Keep **printed numbers as strings** in `*_as_printed` fields.
- **Never guess or fix OCR errors** — flag them with `needs_review` and `review_reason`.
- `'a'` between two prices means `'to'` (a range).
- Fractions like `1/2` become decimals.
- In `'D. C.'` columns: two numbers are dollars then cents (e.g., `5 50` = 5.50); a single number is whole dollars.
- In cents columns: the number is cents.
- **In an L. s. d. column, a triple like `0 17 6` means 0 pounds 17 shillings 6 pence.**
- If unsure, use `price_scale` `'unknown'`.
- **Do NOT convert between currencies.** `price_low_value` and `price_high_value` only restate the printed numbers in the main unit: dollars, or decimal pounds where 20 shillings = 1 pound and 12 pence = 1 shilling. This is arithmetic within one currency, not an exchange rate.
- Keep words like `scarce`/`plenty` in `availability_note`.
- Record `price_date_stated` and `repeated_notice` when a notice repeats an older published date.
- **Currency is decided per price list from its own headings and symbols, never from the page classification.**
- **Slash notation such as `4/6` or `"5 3/4 a 5 6"` in a price list means shillings and pence (price_scale `pounds_shillings_pence` or `shillings`), not dollars.**
- **`"per cent"` or `"Cent."` (as in `"30s. per Cent."`, meaning hundredweight) is never dollar evidence, and an `"a"` range alone is never currency evidence.**
- **Lines such as `"Spanish Milled Dollars 4/8"` are exchange rates: set `row_kind` `exchange_or_financial` and keep them, because they feed the later currency conversion table.**
- **Dollars before 1790 may be Continental paper or Spanish silver dollars: never assume US dollars; set `currency_basis` to `unknown` unless the text says paper or specie.**
- **`price_low_as_printed` and `price_high_as_printed` must always contain the exact printed text. If the printed price is ambiguous or I cannot tell how many prices or which columns it has, `price_low_value` and `price_high_value` must be null, `needs_review` must be true, and `review_reason` must explain what is unclear. Never compute, average or invent a numeric value that does not appear in the text.**
- **If `needs_review` is true, EVERY numeric value field in the row (`price_low_value`, `price_high_value`, `price_low_pounds`, `price_low_shillings`, `price_low_pence`, `price_high_pounds`, `price_high_shillings`, `price_high_pence`, `unit_quantity`) must be null, even if a number could be guessed; the printed text stays.**
- **`price_low` must not exceed `price_high`; if it does, set `needs_review` true with a reason and null values.**
- **In tables with From/To columns and Dols./Cts. sub-headers, a price can be split across cells (for example `133 | 33—136 66`); rebuild it only if the structure is clear, otherwise flag it. Never drop printed cents.**
- **A table with several markets gives one observation per market per item, with its own `market_place` taken from the heading and cleaned of markdown characters (no asterisks or hashes); never use words like "Prices Current" as a market.**
- **`"do."` or `"ditto"` in a unit position or item label means same as the item above: set `unit_status` `"ditto_of_previous"` (add it to the enum), and fill the unit only if the chain is clear.**
- **Small per-unit prices may be cents: when the header says Dols. Cts., never assume; use `price_scale` `"unknown"` and `needs_review` true unless the table itself makes it clear, and add a plausibility flag (field `plausibility_flag`) when a price is far out of line with the others in the same table or newspaper.**
- **Words like `none`, `no demand`, `unsaleable`, `scarce` and `plenty` go in `availability_note`, not in the price fields.**
- **In `schema/financial_quotes_schema.json` add `"percent_discount"` and `"unclear"` to `quote_basis`. Add the field `interpretation_note` to both schemas, and `plausibility_flag` to the goods schema.**
- **Bank-note discount tables (for example `"3 to 6 per cent. dis."`) go to Table 2 `financial_quotes` with the exact printed text.**
- **Arithmetic, conversions and interpretations never go in numeric fields, only in `interpretation_note`, and only when the text supports it.**

## Two Tables

The project produces two separate tables that share source, date, and place fields:

**Table 1: goods_prices** (one row per item price)
- Includes regulated assize prices with `price_type = assize`
- Never contains financial lines (exchange rates, securities, stocks)
- `row_kind` is always `goods_price` (or `assize` for regulated prices)
- Captures goods prices in any currency

**Table 2: financial_quotes** (one row per financial quote)
- Contains exchange rates, public securities, bank/insurance stocks, interest/premiums
- `quote_kind` distinguishes: `exchange_rate`, `public_security`, `bank_stock`, `insurance_stock`, `interest_or_premium`, `other`
- A financial quote found inside a goods price list keeps that list's `price_list_id`
- Both tables share: `source_dataset`, `filename`, `newspaper_id`, `date`, `year`, `market_place`, `publication_*` fields
- Neither table converts currencies
- Financial quotes are evidence for building `reference/currency_rates.csv`, but only reviewed values with a source go into that file

## Working Style

- Small steps
- Show output after each step
- Ask before installing anything or deleting anything
- Test on a few pages before running on everything