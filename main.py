#!/usr/bin/env python3
"""Draw one front page for the world's news of Thursday 19 November 2026.

The program reads news.jsonl (the day's wire, each story with its region and
the news service it came from) and writes a single PNG to
$MAKEFUN_OUTPUT_DIR/entry.png, by default out/entry.png. It uses nothing but
the Python standard library: its own bitmap typeface, its own drawing calls and
its own PNG encoder, so two runs of it write byte-identical files.

Layout, top to bottom, on a 1024x1024 sheet of newsprint:

  masthead   THE WORLD TODAY, the date it sums up, and how many stories it holds
  hero       the day's lead story, set large
  big        two more stories that led the wires, set medium
  grid       24 cards, four across and six down: region, headline, source
  briefs     the rest of the day in three columns, each line region, story, source
  footer     the news services the page drew on

Every headline carries the region it happened in and the service that reported
it, so a reader who missed the day can see what happened, where, and on whose
word. After drawing, the page is checked: every line must fit the column it was
set in, every story must reach the page, and nothing may run into the margin.
"""
from __future__ import annotations

import json
import os
import struct
import sys
import zlib

# --------------------------------------------------------------------------
# Colours: a sheet of newsprint, black ink, one accent red, a grey rule.
# --------------------------------------------------------------------------
PAPER = (246, 243, 235)
CARD = (255, 253, 249)
INK = (17, 16, 15)
ACCENT = (163, 29, 33)
MUTED = (102, 95, 86)
RULE = (52, 48, 44)
BORDER = (203, 196, 185)
WHITE = (255, 255, 255)

# --------------------------------------------------------------------------
# The typeface: a 5x7 bitmap alphabet, one line a glyph, seven fields of five
# cells each ('#' is ink). Headlines are set in it at a whole-number scale, so
# the page holds one clean type from the masthead down to the smallest brief.
# --------------------------------------------------------------------------
FONT_SRC = """
A .###. #...# #...# ##### #...# #...# #...#
B ####. #...# #...# ####. #...# #...# ####.
C .#### #.... #.... #.... #.... #.... .####
D ####. #...# #...# #...# #...# #...# ####.
E ##### #.... #.... ####. #.... #.... #####
F ##### #.... #.... ####. #.... #.... #....
G .#### #.... #.... #..## #...# #...# .###.
H #...# #...# #...# ##### #...# #...# #...#
I ##### ..#.. ..#.. ..#.. ..#.. ..#.. #####
J ##### ...#. ...#. ...#. ...#. #..#. .##..
K #...# #..#. #.#.. ##... #.#.. #..#. #...#
L #.... #.... #.... #.... #.... #.... #####
M #...# ##.## #.#.# #.#.# #...# #...# #...#
N #...# ##..# #.#.# #..## #...# #...# #...#
O .###. #...# #...# #...# #...# #...# .###.
P ####. #...# #...# ####. #.... #.... #....
Q .###. #...# #...# #...# #.#.# #..#. .##.#
R ####. #...# #...# ####. #.#.. #..#. #...#
S .#### #.... #.... .###. ....# ....# ####.
T ##### ..#.. ..#.. ..#.. ..#.. ..#.. ..#..
U #...# #...# #...# #...# #...# #...# .###.
V #...# #...# #...# #...# #...# .#.#. ..#..
W #...# #...# #...# #.#.# #.#.# ##.## #...#
X #...# #...# .#.#. ..#.. .#.#. #...# #...#
Y #...# #...# .#.#. ..#.. ..#.. ..#.. ..#..
Z ##### ....# ...#. ..#.. .#... #.... #####
0 .###. #...# #..## #.#.# ##..# #...# .###.
1 ..#.. .##.. ..#.. ..#.. ..#.. ..#.. .###.
2 .###. #...# ....# ...#. ..#.. .#... #####
3 ####. ....# ....# .###. ....# ....# ####.
4 ...#. ..##. .#.#. #..#. ##### ...#. ...#.
5 ##### #.... ####. ....# ....# #...# .###.
6 .###. #.... #.... ####. #...# #...# .###.
7 ##### ....# ...#. ..#.. .#... .#... .#...
8 .###. #...# #...# .###. #...# #...# .###.
9 .###. #...# #...# .#### ....# ....# .###.
SP ..... ..... ..... ..... ..... ..... .....
DOT ..... ..... ..... ..... ..... .##.. .##..
COMMA ..... ..... ..... ..... .##.. .##.. #....
APOS .#... .#... ..... ..... ..... ..... .....
DASH ..... ..... ..... ##### ..... ..... .....
COLON ..... .##.. .##.. ..... .##.. .##.. .....
SLASH ....# ....# ...#. ..#.. .#... #.... #....
DOLLAR ..#.. .#### #.#.. .###. ..#.# ####. ..#..
PCT ##..# ##..# ...#. ..#.. .#... #..## #..##
AMP .##.. #..#. #.#.. .#... #.#.# #..#. .##.#
LPAREN ..#.. .#... #.... #.... #.... .#... ..#..
RPAREN ..#.. ...#. ....# ....# ....# ...#. ..#..
QUEST .###. #...# ....# ...#. ..#.. ..... ..#..
BANG ..#.. ..#.. ..#.. ..#.. ..#.. ..... ..#..
QUOTE #.#.. #.#.. ..... ..... ..... ..... .....
PLUS ..... ..#.. ..#.. ##### ..#.. ..#.. .....
EQ ..... ..... ##### ..... ##### ..... .....
STAR ..... #.#.# .###. ##### .###. #.#.# .....
"""

GLYPH_KEYS = {
    " ": "SP", ".": "DOT", ",": "COMMA", "'": "APOS", "-": "DASH", ":": "COLON",
    "/": "SLASH", "$": "DOLLAR", "%": "PCT", "&": "AMP", "(": "LPAREN",
    ")": "RPAREN", "?": "QUEST", "!": "BANG", '"': "QUOTE", "+": "PLUS",
    "=": "EQ", "*": "STAR",
}

FONT: dict[str, tuple[str, ...]] = {}
for _line in FONT_SRC.strip().splitlines():
    _parts = _line.split()
    FONT[_parts[0]] = tuple(_parts[1:8])
for _char, _key in GLYPH_KEYS.items():
    FONT[_char] = FONT[_key]

GLYPH_W, GLYPH_H = 5, 7
TRACK = 1


def glyphs(text: str) -> list[tuple[str, ...]]:
    """The glyph rows of every character of a line, unknown ones as '?'."""
    return [FONT.get(ch, FONT["?"]) for ch in text.upper()]


def text_width(text: str, scale: int) -> int:
    """Pixels a line takes, including the gap between its letters."""
    if not text:
        return 0
    return len(text) * (GLYPH_W + TRACK) * scale - TRACK * scale


def wrap(text: str, scale: int, max_px: int) -> list[str]:
    """Break a line into the fewest lines that fit max_px, never mid-word.

    A word too long for the column on its own is broken at the column edge
    rather than allowed to run into the next one.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        while text_width(word, scale) > max_px:
            room = max(1, (max_px + TRACK * scale) // ((GLYPH_W + TRACK) * scale))
            lines.append(word[:room])
            word = word[room:]
        trial = word if not current else current + " " + word
        if text_width(trial, scale) <= max_px or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


# --------------------------------------------------------------------------
# The sheet: an RGB pixel buffer with flat fills and text drawn straight in.
# --------------------------------------------------------------------------
class Sheet:
    def __init__(self, width: int, height: int, background: tuple[int, int, int]):
        self.w, self.h = width, height
        self.px = bytearray(bytes(background) * (width * height))

    def rect(self, x: int, y: int, w: int, h: int, colour: tuple[int, int, int]) -> None:
        """Fill a rectangle, clipped to the sheet."""
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(colour) * (x1 - x0)
        for yy in range(y0, y1):
            start = (yy * self.w + x0) * 3
            self.px[start:start + len(row)] = row

    def frame(self, x: int, y: int, w: int, h: int, colour: tuple[int, int, int]) -> None:
        """Draw a hairline box, one pixel thick."""
        self.rect(x, y, w, 1, colour)
        self.rect(x, y + h - 1, w, 1, colour)
        self.rect(x, y, 1, h, colour)
        self.rect(x + w - 1, y, 1, h, colour)

    def text(self, x: int, y: int, line: str, scale: int,
             colour: tuple[int, int, int]) -> int:
        """Draw one line and return the width it used."""
        step = (GLYPH_W + TRACK) * scale
        pen = x
        for rows in glyphs(line):
            for ry, row in enumerate(rows):
                for rx, cell in enumerate(row):
                    if cell == "#":
                        self.rect(pen + rx * scale, y + ry * scale, scale, scale, colour)
            pen += step
        return pen - x

    def text_right(self, right: int, y: int, line: str, scale: int,
                   colour: tuple[int, int, int]) -> int:
        """Draw one line ending at right, and return its width."""
        return self.text(right - text_width(line, scale), y, line, scale, colour)

    def ink_bottom(self) -> int:
        """The last row holding anything but the paper colour."""
        paper = bytes(PAPER)
        for y in range(self.h - 1, -1, -1):
            row = self.px[y * self.w * 3:(y + 1) * self.w * 3]
            if any(row[x:x + 3] != paper for x in range(0, len(row), 3)):
                return y
        return -1


def png_bytes(sheet: Sheet) -> bytes:
    """Encode the sheet as one whole 8-bit RGB PNG."""
    raw = bytearray()
    stride = sheet.w * 3
    for y in range(sheet.h):
        raw.append(0)  # filter: none, so the bytes are plainly the picture
        raw += sheet.px[y * stride:(y + 1) * stride]

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", sheet.w, sheet.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


# --------------------------------------------------------------------------
# The page: one vertical chain, each band telling the next where to start.
# --------------------------------------------------------------------------
W = H = 1024
M = 18                     # margin on every side
CW = W - 2 * M             # 988 px of column
BOTTOM = H - M             # no ink below this row
DAY = "THURSDAY 19 NOVEMBER 2026"
REGION_CODE = {
    "Americas": "AM", "Europe": "EU", "Africa": "AF", "Middle East": "ME",
    "South Asia": "SA", "Asia-Pacific": "AP", "Eurasia": "EA",
    "World": "WD", "Economy": "EC",
}
SOURCE_LIST = ("BBC, AL JAZEERA, FRANCE 24, DW, TASS, NYT, GUARDIAN, NPR, CBC, ABC, SCMP, "
               "CNA, JAPAN TIMES, THE HINDU, YONHAP, AFRICANEWS, EURACTIV, IRISH TIMES")

# Layout: the y each band starts at, and how tall a row of the grid is.
GRID_ROWS, GRID_COLS = 5, 4
CARD_H = 70
CARD_GAP = 5
BRIEF_LINE_H = 9
BRIEF_GAP = 2


def load_news(path: str) -> list[dict]:
    """Read the day's wire, one JSON story a line."""
    stories = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                stories.append(json.loads(line))
    return stories


def by_tier(stories: list[dict], tier: str) -> list[dict]:
    return [s for s in stories if s.get("tier") == tier]


def source_line(story: dict) -> str:
    return f"SOURCE: {story['source'].upper()}"


def draw_masthead(page: Sheet, total: int, regions: int, warnings: list[str]) -> int:
    """The name, the day it sums up, and the count. Returns the next free row."""
    page.rect(0, 0, W, 7, ACCENT)
    page.text(M, 12, "THE WORLD TODAY", 6, INK)
    page.text_right(W - M, 20, DAY, 3, ACCENT)
    page.text_right(W - M, 46, f"DAY EDITION - {total} STORIES FROM {regions} REGIONS", 1, MUTED)
    page.text(M, 60, "THE NEWS OF THURSDAY 19 NOVEMBER 2026 IN ONE PAGE", 2, INK)
    if text_width("EVERY STORY CARRIES ITS REGION AND SOURCE", 1) < CW:
        page.text_right(W - M, 62, "EVERY STORY CARRIES ITS REGION AND SOURCE", 1, MUTED)
    else:
        warnings.append("masthead strap line is too wide")
    page.rect(M, 78, CW, 4, RULE)
    page.rect(M, 84, CW, 1, RULE)
    return 92


def draw_hero(page: Sheet, story: dict, y: int, warnings: list[str]) -> int:
    """The lead story, large. Returns the next free row."""
    tag = f"LEAD STORY - {story['region'].upper()} - {story['source'].upper()}"
    page.rect(M, y, CW, 24, ACCENT)
    if text_width(tag, 2) > CW - 16:
        warnings.append(f"hero tag too wide: {tag}")
    page.text(M + 8, y + 5, tag, 2, WHITE)
    lines = wrap(story["title"].upper(), 4, CW)
    if len(lines) > 3:
        warnings.append(f"hero headline needs {len(lines)} lines")
    cy = y + 38
    for line in lines[:3]:
        page.text(M, cy, line, 4, INK)
        cy += 34
    cy += 6
    page.text(M, cy, source_line(story), 2, MUTED)
    cy += 24
    page.rect(M, cy, CW, 2, RULE)
    return cy + 10


def draw_big(page: Sheet, stories: list[dict], y: int, warnings: list[str]) -> int:
    """The two runners-up, set medium, side by side. Returns the next free row."""
    gap = 16
    colw = (CW - gap) // 2
    bottom = y
    for i, story in enumerate(stories[:2]):
        x = M + i * (colw + gap)
        page.text(x, y, f"{story['region'].upper()} - {story['source'].upper()}", 1, ACCENT)
        cy = y + 16
        lines = wrap(story["title"].upper(), 3, colw)
        if len(lines) > 3:
            warnings.append(f"big headline needs {len(lines)} lines: {story['title'][:40]}")
        for line in lines[:3]:
            page.text(x, cy, line, 3, INK)
            cy += 26
        page.text(x, cy + 4, source_line(story), 1, MUTED)
        bottom = max(bottom, cy + 14)
    page.rect(M, bottom, CW, 2, RULE)
    return bottom + 10


def draw_grid(page: Sheet, stories: list[dict], y: int, warnings: list[str]) -> int:
    """One card a story, region and source on its top line. Returns the next row."""
    gap = CARD_GAP
    colw = (CW - gap * (GRID_COLS - 1)) // GRID_COLS
    capacity = GRID_ROWS * GRID_COLS
    if len(stories) > capacity:
        warnings.append(f"grid holds {capacity} cards, {len(stories)} offered")
    for i, story in enumerate(stories[:capacity]):
        x = M + (i % GRID_COLS) * (colw + gap)
        cy = y + (i // GRID_COLS) * (CARD_H + gap)
        page.rect(x, cy, colw, CARD_H, CARD)
        page.frame(x, cy, colw, CARD_H, BORDER)
        page.rect(x, cy, 3, CARD_H, ACCENT)
        page.text(x + 8, cy + 6, story["region"].upper(), 1, ACCENT)
        page.text_right(x + colw - 6, cy + 6, story["source"].upper(), 1, MUTED)
        lines = wrap(story["title"].upper(), 2, colw - 18)
        if len(lines) > 3:
            warnings.append(f"card needs {len(lines)} lines: {story['title'][:40]}")
        ly = cy + 20
        for line in lines[:3]:
            page.text(x + 9, ly, line, 2, INK)
            ly += 16
    rows_used = min(GRID_ROWS, (len(stories) + GRID_COLS - 1) // GRID_COLS)
    return y + rows_used * (CARD_H + CARD_GAP) - CARD_GAP


def draw_briefs(page: Sheet, stories: list[dict], y: int, warnings: list[str]) -> tuple[int, int]:
    """The rest of the day in three columns: region code, headline, source.

    The region code is tinted and a hairline rule divides the columns, so the
    eye can walk the band the way it walks a newspaper's own brief column.
    Returns how many stories were set and how many text lines they took.
    """
    page.text(M, y, "ALSO TODAY", 2, ACCENT)
    legend = "REGIONS: " + " ".join(
        f"{code} {name.split(' ')[0].upper()}" for name, code in REGION_CODE.items())
    if text_width(legend, 1) < CW:
        page.text_right(W - M, y + 3, legend, 1, MUTED)
    else:
        warnings.append("region legend too wide")

    top = y + 24
    cols, colgap = 3, 16
    colw = (CW - colgap * (cols - 1)) // cols
    floor = BOTTOM - 22                      # leave the footer its own strip
    for i in range(1, cols):
        rule_x = M + i * colw + (i - 1) * colgap + colgap // 2
        page.rect(rule_x, top, 1, floor - top, BORDER)
    pen = [top] * cols
    capacity = cols * ((floor - top) // BRIEF_LINE_H)
    column, drawn, used = 0, 0, 0
    for story in stories:
        code = REGION_CODE.get(story["region"], "WD")
        label = f"{code} {story['title'].upper()} - {story['source'].upper()}"
        lines = wrap(label, 1, colw - 8)
        need = len(lines) * BRIEF_LINE_H + BRIEF_GAP
        if pen[column] + need > floor:
            column += 1
            while column < cols and pen[column] + need > floor:
                column += 1
            if column >= cols:
                warnings.append(f"briefs ran out of room with {len(stories) - drawn} left")
                break
        x = M + column * (colw + colgap)
        for j, line in enumerate(lines):
            if j == 0 and line.startswith(code + " "):
                page.text(x, pen[column], code, 1, ACCENT)
                page.text(x + text_width(code + " ", 1), pen[column],
                          line[len(code) + 1:], 1, INK)
            else:
                page.text(x + text_width(code + " ", 1), pen[column], line, 1, INK)
            pen[column] += BRIEF_LINE_H
        pen[column] += BRIEF_GAP
        drawn += 1
        used += len(lines)
    if used > capacity:
        warnings.append(f"briefs took {used} lines, room for {capacity}")
    return drawn, used


def draw_footer(page: Sheet, total: int, warnings: list[str]) -> None:
    line = f"SOURCES: {SOURCE_LIST}"
    page.rect(M, BOTTOM - 18, CW, 1, BORDER)
    if text_width(line, 1) > CW:
        warnings.append("footer line too wide")
    page.text(M, BOTTOM - 13, line, 1, MUTED)
    tail = f"{total} STORIES OF 19 NOVEMBER 2026"
    if text_width(line, 1) + 24 + text_width(tail, 1) <= CW:
        page.text_right(W - M, BOTTOM - 13, tail, 1, ACCENT)


def build_page(stories: list[dict]) -> tuple[Sheet, dict]:
    """Draw the whole front page and report what went on it."""
    warnings: list[str] = []
    regions = sorted({s["region"] for s in stories})
    page = Sheet(W, H, PAPER)

    y = draw_masthead(page, len(stories), len(regions), warnings)
    heros = by_tier(stories, "hero")
    if heros:
        y = draw_hero(page, heros[0], y, warnings)
    y = draw_big(page, by_tier(stories, "big"), y, warnings)
    y = draw_grid(page, by_tier(stories, "card"), y + 4, warnings)
    briefs_drawn, brief_lines = draw_briefs(page, by_tier(stories, "brief"), y + 12, warnings)
    draw_footer(page, len(stories), warnings)

    report = {
        "stories": len(stories),
        "regions": len(regions),
        "region_names": regions,
        "hero": len(heros),
        "big": len(by_tier(stories, "big")),
        "cards": len(by_tier(stories, "card")),
        "briefs": briefs_drawn,
        "briefs_offered": len(by_tier(stories, "brief")),
        "brief_lines": brief_lines,
        "ink_bottom": page.ink_bottom(),
        "warnings": warnings,
    }
    return page, report


def main() -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or os.path.join(here, "out")
    os.makedirs(out_dir, exist_ok=True)
    data = os.environ.get("NEWS_FILE") or os.path.join(here, "news.jsonl")

    stories = load_news(data)
    page, report = build_page(stories)
    blob = png_bytes(page)
    target = os.path.join(out_dir, "entry.png")
    with open(target, "wb") as handle:
        handle.write(blob)

    print(f"wrote {target}: {len(blob)} bytes, {W}x{H} px")
    print(f"  hero {report['hero']}  big {report['big']}  cards {report['cards']}  "
          f"briefs {report['briefs']}/{report['briefs_offered']} on {report['brief_lines']} lines")
    print(f"  {report['stories']} stories from {report['regions']} regions: "
          f"{', '.join(report['region_names'])}")
    print(f"  lowest inked row {report['ink_bottom']} of {H - 1} (margin {M})")
    for warning in report["warnings"]:
        print(f"  ! {warning}", file=sys.stderr)
    if report["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
