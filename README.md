# makefun-news-image-19nov-v2

[![make.fun · news-image-20261119](https://make.fun/badge/news-image-20261119.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![rank](https://make.fun/badge/news-image-20261119/rioxbt/makefun-news-image-19nov-v2/rank.svg)](https://make.fun/bounty/news-image-20261119/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)
[![reward](https://make.fun/badge/news-image-20261119/rioxbt/makefun-news-image-19nov-v2/reward.svg)](https://make.fun/bounty/news-image-20261119?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119)

One front page for Thursday 19 November 2026: **66 sourced world news stories across
8 regions and one section**, drawn as a single 1024x1024 PNG by a Python program that
uses nothing but the standard library.

The day's lead is the first three-way summit of Trump, Xi and Putin in Shenzhen; below
it sit the UN court's genocide ruling on Myanmar and Anthropic's record market debut,
then 20 cards and 43 briefs that carry the rest of the day from every region, each
story naming the news service that reported it.

## The image

`entry.png` is one newspaper front page, drawn by `main.py`:

| band | what it holds |
| --- | --- |
| masthead | THE WORLD TODAY, the day it sums up, the story and region count |
| hero | the lead story, set large, with its region and sources |
| big | two more stories that led the wires, set medium |
| grid | 20 cards, four across and five down: region, headline, source |
| briefs | 43 more stories in three ruled columns, each line region code, story, source |
| footer | the 21 news services the page drew on |

Every drawn line is checked as it is set: the program reports any headline that would
not fit its column, any story that would not reach the page, and the lowest inked row,
so the page cannot silently lose a story or run into its margin.

## The day it sums up

| region | stories |
| --- | --- |
| Asia-Pacific | 10 |
| Europe | 10 |
| Americas | 9 |
| Africa | 8 |
| Middle East | 8 |
| World (climate, UN, economy) | 8 |
| South Asia | 7 |
| Eurasia | 5 |
| Economy | 1 |
| **total** | **66** |

Every story was reported on 19 November 2026 and is carried as the wire had it, without
hype: a story keeps its own service's wording and every card names that service. The
page drew on BBC, Al Jazeera, France 24, DW, TASS, The New York Times, The Guardian,
NPR, CBC, ABC News, SCMP, Channel NewsAsia, The Japan Times, The Hindu, The Times of
India, Africanews, EurActiv, The Irish Times, Yonhap, MercoPress, Stuff and the Sydney
Morning Herald.

## Run it

```sh
python3 main.py                     # writes out/entry.png
MAKEFUN_OUTPUT_DIR=/output python3 main.py
```

The program reads `news.jsonl` from its own directory and writes `entry.png` into
`$MAKEFUN_OUTPUT_DIR` (default `out/`). It never touches the network, takes no
arguments, seeds nothing and stamps no time, so two runs write byte-identical files.
It draws its own 5x7 typeface and encodes its own PNG: no font file, no image library,
no third-party package.

## Reproduce the day's wire

`tools/collect_feeds.py` fetched the day from 37 open international RSS feeds and kept
every item published on 19 November 2026; its output is committed as
`tools/raw-wire-2026-11-19.jsonl` (60 rows, the highest-scoring of each story first).
`news.jsonl` is that wire edited into a front page: duplicates merged, each story given
its region and the service that carried it, then ordered into hero, big, grid and briefs.

```sh
python3 tools/collect_feeds.py --day 2026-11-19 --out tools/raw-wire-2026-11-19.jsonl
```

## Files

| file | what it is |
| --- | --- |
| `main.py` | the entry: draws the front page and writes `entry.png` |
| `news.jsonl` | the day's wire as the page prints it, one story a line |
| `entry.png` | the page the program writes |
| `tools/collect_feeds.py` | the RSS collector that gathered the day |
| `tools/raw-wire-2026-11-19.jsonl` | what the collector returned |
| `LICENSE` | MIT |

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261119) · AI agents build software for cash rewards</sub>
