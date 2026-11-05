Price Currents: notes for Thiago

Hi Thiago! This is where I am with the price currents project. It's still messy and unfinished, so I wrote this to give you the context of the process. Feel free to change anything that helps.

Where things are
CLAUDE.md: the rules I give Claude Code when it helps me with the code
scripts/parse_tables_v2.py: the program that reads the tables (my newest version)
results/: what that program produced
table_blocks_md.json: the 89 tables I use to test it
schema/: the columns I want in each of my two tables
tests/: my first attempt at answer keys to check the program against
docs/process_log.md: a diary of what I tried, step by step
the rest of scripts/: older steps (downloading, sorting pages, pilots)
My two tables
Goods prices: one row per item, per market. Bread "assize" notices are marked separately, because the city set that price and it isn't a market price.
Financial quotes: exchange rates, bank stocks, bank-note discounts and similar. I keep these apart on purpose.
What happened in the first run

I ran the program on the 89 tables.

It found 1,704 goods prices and 31 financial rows. 283 things went to the "couldn't read" log.
Only 56 rows are ones I'm confident about. Most of the rest need a human to look at them. The ones to check are in review_queue_v2.csv.
About 1,550 rows have the price scale marked "unknown". On purpose: a plain "11" can be dollars or cents depending on the item.
The rules I'm following: I keep the text exactly as printed, I don't make up numbers or units, and if one value looks wrong I only blank that value, write down why, and flag the row. I don't delete anything.
What's going wrong
Almost every table is laid out differently. Some have dollar and cent columns (Natchez 1802), some have "from / to" ranges (Boston 1803, Portland 1804), some have one dollar column (Cadiz 1800), and the 1792-93 ones look like they're in pounds, shillings and pence. Each one needs its own rules, and I only have a few.
Often the table doesn't say whether a price is in dollars or cents.
The OCR makes mistakes in numbers. Sometimes the high price is lower than the low price.
Before 1790, "dollars" could mean paper money or silver, and shillings were worth different amounts in different colonies. I haven't tried converting anything.
The answer keys in tests/ were written by an AI and I haven't checked them against the originals. They have some mistakes and I'm redoing them. scripts/parser_v2_plan.md also has some mistakes.
For 62 of the 89 tables, the program uses a simpler fallback that works less well.

I'd really like your ideas on how to handle so many different layouts, and on the dollars-or-cents problem. Thank you!

Sara
