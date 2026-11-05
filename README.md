# Price Currents: notes for Thiago

Hi Thiago! This is where I am with the price currents project. It's still messy and unfinished, so I wrote this to give you the context of the process. Feel free to change anything that helps.

## Where things are

- `CLAUDE.md`: the rules I give Claude Code when it helps me with the code
- `scripts/parse_tables_v2.py`: the program that reads the tables (my newest version)
- `results/`: what that program produced
- `table_blocks_md.json`: the 89 tables I use to test it
- `schema/`: the columns I want in each of my two tables
- `tests/`: my first attempt at answer keys to check the program against
- `docs/process_log.md`: a diary of what I tried, step by step
- the rest of `scripts/`: older steps (downloading, sorting pages, pilots)

## My two tables

1. **Goods prices**: one row per item, per market. Bread "assize" notices are marked separately, because the city set that price and it isn't a market price.
2. **Financial quotes**: exchange rates, bank stocks, bank-note discounts and similar. I keep these apart on purpose.

## What happened in the first run

I ran the program on the 89 tables.

- It found 1,705 goods prices and 31 financial rows. 284 things went to the "couldn't read" log.
- Only 56 rows are ones I'm confident about (815 medium, 834 low). Most of the rest need a human to look at them. The ones to check are in `review_queue_v2.csv`.
- About 1,550 rows have the price scale marked "unknown". On purpose: a plain "11" can be dollars or cents depending on the item.
- The rules I'm following: I keep the text exactly as printed, I don't make up numbers or units, and if one value looks wrong I only blank that value, write down why, and flag the row. I don't delete anything.

## What's going wrong

- Almost every table is laid out differently. Some have dollar and cent columns (Natchez 1802), some have "from / to" ranges (Boston 1803, Portland 1804), some have one dollar column (Cadiz 1800), and the 1792-93 ones look like they're in pounds, shillings and pence. Each one needs its own rules, and I only have a few.
- Often the table doesn't say whether a price is in dollars or cents.
- The OCR makes mistakes in numbers. Sometimes the high price is lower than the low price.
- Before 1790, "dollars" could mean paper money or silver, and shillings were worth different amounts in different colonies. I haven't tried converting anything.
- The answer key `tests/gold_v2.json` covers only three tables (Natchez, Boston first 10 rows, Cadiz first table). I wrote it from the text and then checked those rows against the newspaper images. `tests/gold_natchez_1802.json` is an older version with mistakes, and `scripts/parser_v2_plan.md` also has some mistakes.
- For 62 of the 89 tables, the program uses a simpler fallback that works less well.

- I checked three tables against the newspaper images (Natchez 1802, Boston 1803, Cadiz 1800), 38 observations. The parser found all of them. The OCR itself made mistakes: 6 wrong numbers (for example Cotton 28 read as 23, Beef 13 read as 73, Logwood 2 1/2 read as 24), plus a long s read as f. Details are in `tests/gold_v2.json`.
- In the pounds/shillings/pence lists (Liverpool inside the Cadiz block), the OCR turns the s and d marks into fractions or extra digits ("51s" became "5 1/2", "20d a 22d" became "200 a 220"). `block_text` has the same problem, so I can't trust those numbers.
- Dollars vs cents depends on which column a number sits in, and the OCR table loses that. In Boston, "Bacon 11 - 12" is cents (Cts. columns) and "Bread 4 - 5" is dollars, but they look the same in the text.
- The OCR also moved prices into the item names in Natchez ("Tobacco, do. 3 to 4"). I fixed this one in the parser.
- The text comes from a vision-language model (`OCR_run_ID` is VLM_OCR_1 or VLM_OCR_2; 1,922 and 829 blocks, no page has both), not classic OCR. `block_bbox` seems to be in the model's own image space, not the original page pixels: I tried cropping Natchez from the Library of Congress image with it and got a different part of the page.

I'd really like your ideas on how to handle so many different layouts, and on the dollars-or-cents problem. Thank you!

Sara
