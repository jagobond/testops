"""Draw the three-stage TestOps architecture evolution as presentation PNGs.

Style: flat boxes, one idea per box, arrows left-to-right, a footer that states what the stage does NOT have.
Everything is hand-placed: no graph layout, because a generated graph is unreadable at presentation size.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 2000, 1180
NAVY = (15, 37, 64)
GOLD = (218, 160, 0)
BRONZE = (140, 94, 44)
INK = (33, 41, 54)
MUTED = (95, 107, 124)
LINE = (196, 205, 216)
FILL = (246, 248, 251)
GOLD_FILL = (253, 247, 230)
GREEN_FILL = (234, 243, 236)
GREEN = (46, 110, 68)
RED_FILL = (251, 237, 235)
RED = (150, 55, 45)

FONTS = {
    "h1": "C:/Windows/Fonts/segoeuib.ttf",
    "h2": "C:/Windows/Fonts/segoeuib.ttf",
    "body": "C:/Windows/Fonts/segoeui.ttf",
    "bold": "C:/Windows/Fonts/segoeuib.ttf",
    "small": "C:/Windows/Fonts/segoeui.ttf",
}


def font(kind, size):
    return ImageFont.truetype(FONTS[kind], size)


def wrap(draw, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if draw.textlength(t, font=fnt) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def box(d, x, y, w, h, title, body="", fill=FILL, edge=LINE, title_size=27, body_size=21,
        accent=None, radius=14, title_color=INK, align="left"):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=edge, width=2)
    if accent:
        d.rounded_rectangle([x, y, x + w, y + 7], radius=4, fill=accent)
    tf, bf = font("h2", title_size), font("body", body_size)
    tx = x + 20
    ty = y + (20 if not body else 18)
    for line in wrap(d, title, tf, w - 40):
        d.text((tx, ty), line, font=tf, fill=title_color)
        ty += title_size + 6
    if body:
        ty += 2
        for line in wrap(d, body, bf, w - 40):
            d.text((tx, ty), line, font=bf, fill=MUTED)
            ty += body_size + 5


def arrow(d, x1, y1, x2, y2, label="", color=MUTED, width=3, dashed=False, head=13, label_size=19):
    if dashed:
        total = math.hypot(x2 - x1, y2 - y1)
        step, drawn = 14, 0
        while drawn < total - head:
            t0, t1 = drawn / total, min((drawn + step) / total, (total - head) / total)
            d.line([x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0, x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1],
                   fill=color, width=width)
            drawn += step * 2
    else:
        d.line([x1, y1, x2, y2], fill=color, width=width)
    ang = math.atan2(y2 - y1, x2 - x1)
    d.polygon([[x2, y2],
               [x2 - head * math.cos(ang - 0.42), y2 - head * math.sin(ang - 0.42)],
               [x2 - head * math.cos(ang + 0.42), y2 - head * math.sin(ang + 0.42)]], fill=color)
    if label:
        f = font("small", label_size)
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tw = d.textlength(label, font=f)
        d.rectangle([mx - tw / 2 - 8, my - 15, mx + tw / 2 + 8, my + 15], fill=(255, 255, 255))
        d.text((mx - tw / 2, my - 12), label, font=f, fill=color)


def header(d, num, title, subtitle):
    d.rectangle([0, 0, W, 132], fill=NAVY)
    d.rectangle([0, 132, W, 140], fill=GOLD)
    d.text((46, 26), f"STAGE {num}", font=font("bold", 24), fill=GOLD)
    d.text((46, 58), title, font=font("h1", 44), fill=(255, 255, 255))
    d.text((W - 46 - d.textlength(subtitle, font=font("body", 23)), 70), subtitle,
           font=font("body", 23), fill=(206, 214, 226))


def footer(d, lines, y=H - 116):
    d.line([46, y - 18, W - 46, y - 18], fill=LINE, width=2)
    f = font("small", 21)
    ty = y
    for ln in lines:
        for line in wrap(d, ln, f, W - 120):
            d.text((46, ty), line, font=f, fill=MUTED)
            ty += 27
        ty += 2


def canvas():
    img = Image.new("RGB", (W, H), (255, 255, 255))
    return img, ImageDraw.Draw(img)


def save(img, name):
    out = Path(__file__).resolve().parent / name
    img.save(out)
    print(out)


# ---------------------------------------------------------------- stage 1
def stage1():
    img, d = canvas()
    header(d, 1, "The deterministic engine", "what the rules can prove on their own")
    y = 210
    box(d, 60, y, 330, 150, "Product repository",
        "pinned to one commit SHA; files fetched once and stored", edge=LINE)
    box(d, 60, y + 180, 330, 150, "Test repository",
        "same commit discipline; features + step definitions", edge=LINE)

    box(d, 440, y - 10, 360, 350, "Readers, one per ecosystem",
        "Gherkin plus step bindings (.NET, cucumber-js); Java/Spring routes from annotations; "
        "surface discovery. A language nobody wrote a reader for reports itself as unread - never as empty.",
        fill=GOLD_FILL, edge=GOLD)

    box(d, 850, y - 10, 380, 350, "Evidence store",
        "SQLite plus content-addressed blobs. Every artefact, claim, finding and decision is a row with a path, "
        "a line and a commit. Nothing on a page is fetched live.", fill=FILL)

    box(d, 1290, y - 10, 300, 160, "Level fitness",
        "is this assertion settled at the layer the test drives?", fill=FILL)
    box(d, 1290, y + 180, 300, 160, "Duplication",
        "the same assertion made twice, across suites", fill=FILL)

    box(d, 1290, y + 370, 300, 120, "Analysers are pure",
        "same rows in, same verdict out", fill=GREEN_FILL, edge=GREEN)
    box(d, 1640, y + 40, 300, 220, "Case pages",
        "verdict, the test line, the product line, the proposed action", fill=FILL)
    box(d, 1640, y + 290, 300, 150, "Human decision",
        "resolved / false positive / needs fixing - suppresses permanently", fill=FILL)

    arrow(d, 390, y + 75, 440, y + 75)
    arrow(d, 390, y + 255, 440, y + 255)
    arrow(d, 800, y + 165, 850, y + 165)
    arrow(d, 1230, y + 90, 1290, y + 90)
    arrow(d, 1230, y + 240, 1290, y + 240)
    arrow(d, 1590, y + 90, 1640, y + 120)
    arrow(d, 1590, y + 250, 1640, y + 190)
    arrow(d, 1790, y + 260, 1790, y + 290)

    d.text((60, 640), "No model is called anywhere in this picture.", font=font("h2", 30), fill=BRONZE)
    d.text((60, 682), "Every verdict can be rebuilt from stored rows, with no network, which is what makes it checkable.",
           font=font("body", 24), fill=MUTED)

    footer(d, [
        "What this stage cannot do: it can only find issue shapes its vocabulary names, so tests that assert nothing, or "
        "assert their own fixture, or are satisfied by a mock, are invisible - and a page that says 'distinct' reads as "
        "'fine' when it means 'nothing my rules look for'.",
        "It cannot explain itself in plain English, and it cannot generalize a rule from one language to another.",
    ])
    save(img, "stage1-deterministic.png")


# ---------------------------------------------------------------- stage 2
def stage2():
    img, d = canvas()
    header(d, 2, "Deterministic engine plus an agentic narrator", "the model explains; it never decides")
    y = 200
    box(d, 60, y, 300, 120, "Repositories", "product + tests, one commit", edge=LINE)
    box(d, 60, y + 160, 300, 120, "Readers", "one per ecosystem", fill=GOLD_FILL, edge=GOLD)
    box(d, 60, y + 320, 300, 120, "Evidence store", "rows + blobs, content-addressed")
    arrow(d, 210, y + 120, 210, y + 160)
    arrow(d, 210, y + 280, 210, y + 320)

    box(d, 420, y, 300, 140, "Analysers", "level fitness, duplication - pure functions")
    box(d, 420, y + 180, 300, 140, "Case page", "the same page, and its stored evidence")
    arrow(d, 360, y + 380, 420, y + 380)
    arrow(d, 570, y + 140, 570, y + 180)

    box(d, 790, y - 10, 340, 190, "Foundry hosted agent",
        "testops-narrator, its own managed identity, model deployment deepseek-flash", fill=GOLD_FILL, edge=GOLD)
    box(d, 790, y + 230, 340, 190, "Citation guard",
        "every sentence must cite a stored row; an invented route, file, count or verb kills the reply",
        fill=GREEN_FILL, edge=GREEN)
    arrow(d, 720, y + 60, 790, y + 70, "agent=on")
    arrow(d, 960, y + 180, 960, y + 230)
    box(d, 1180, y + 230, 300, 190, "Rendered page",
        "explanation above the verdict, labelled commentary, or the honest fallback", fill=FILL)
    arrow(d, 1130, y + 325, 1180, y + 325, "accepted")
    arrow(d, 960, y + 420, 960, y + 470)
    box(d, 790, y + 470, 340, 120, "Fallback sentence",
        "names the reason it could not explain", fill=RED_FILL, edge=RED)
    arrow(d, 1130, y + 290, 1180, y + 290, "rejected", color=RED, dashed=True)

    box(d, 1180, y + 470, 300, 120, "Token ledger + votes", "per call, per route, per state", fill=FILL)
    arrow(d, 960, y + 350, 1180, y + 520, dashed=True, color=LINE)
    arrow(d, 1330, y + 420, 1330, y + 470)

    box(d, 1540, y + 40, 400, 260, "What stays true",
        "The verdict above the prose is byte-identical to the agent-off page - proved over all 275 real pages. "
        "Switching the agent off costs nothing and changes no finding.",
        fill=GREEN_FILL, edge=GREEN)
    arrow(d, 1480, y + 325, 1540, y + 200)

    footer(d, [
        "What this stage does not yet do: the model only reacts to findings the rules already made. It cannot notice "
        "something the rules missed, because it is never asked.",
        "It also is not cheap by construction - every explanation is a paid call, which is why the ledger and the votes exist.",
    ])
    save(img, "stage2-with-narrator.png")


# ---------------------------------------------------------------- stage 3
def stage3():
    img, d = canvas()
    header(d, 3, "Model proposes, rules dispose", "recall from the model, authority from the rules")
    y = 195
    box(d, 50, y, 250, 110, "Repositories", "product + tests, one commit", edge=LINE)
    box(d, 50, y + 145, 250, 110, "Readers", "one per ecosystem", fill=GOLD_FILL, edge=GOLD)
    box(d, 50, y + 290, 250, 110, "Evidence store", "rows + blobs, one commit")
    arrow(d, 175, y + 110, 175, y + 145)
    arrow(d, 175, y + 255, 175, y + 290)

    box(d, 340, y, 320, 140, "Deterministic analysers",
        "what a rule can prove: level fitness, duplication", fill=FILL)
    box(d, 340, y + 200, 320, 190, "Proposal stage (model)",
        "the agent reads an evidence pack and suggests candidates: wrong level, duplicate of product, asserts nothing. "
        "No authority, no page, no verdict.", fill=GOLD_FILL, edge=GOLD)
    arrow(d, 300, y + 345, 340, y + 345)
    arrow(d, 300, y + 380, 340, y + 300)

    box(d, 700, y + 200, 300, 190, "Candidate store",
        "the suggestion, the rows it points at, agent name and version, prompt hash, tokens, raw reply",
        fill=FILL)
    arrow(d, 660, y + 295, 700, y + 295)

    box(d, 1040, y + 170, 320, 250, "The gate (rules)",
        "route exists at that commit?  claim maps to that layer?  the duplicate's wording really differs?  "
        "assertion really empty?  No gate, no finding.", fill=GREEN_FILL, edge=GREEN)
    arrow(d, 1000, y + 295, 1040, y + 295)

    box(d, 1400, y + 40, 300, 170, "Verified finding",
        "a case, saying: proposed by agent v3, verified by rule X", fill=GREEN_FILL, edge=GREEN)
    box(d, 1400, y + 260, 300, 130, "Rejection ledger",
        "why it failed, per candidate kind - the acceptance rate", fill=RED_FILL, edge=RED)
    box(d, 1740, y + 40, 210, 170, "Human decision",
        "resolved / false positive / needs fixing", fill=FILL)
    box(d, 1740, y + 260, 210, 130, "Cost per finding",
        "tokens and time, measured", fill=FILL)
    arrow(d, 1360, y + 200, 1400, y + 125, "accepted", color=GREEN)
    arrow(d, 1360, y + 260, 1400, y + 320, "rejected", color=RED, dashed=True)
    arrow(d, 1700, y + 125, 1740, y + 125)
    arrow(d, 1700, y + 325, 1740, y + 325)
    arrow(d, 1845, y + 210, 1845, y + 260, dashed=True)

    box(d, 340, y + 440, 700, 130, "Recall measurement - the part that makes this honest",
        "a blind gold set labelled by people, plus a model-as-probe pass over cases we called distinct: "
        "so 'what we miss' is a number with an interval, not an opinion.",
        fill=GOLD_FILL, edge=GOLD)
    arrow(d, 690, y + 440, 690, y + 400, dashed=True, color=GOLD)
    box(d, 1080, y + 440, 870, 130, "Authority is unchanged",
        "Nothing the model proposes is published until a rule passes it. With every candidate rejected, the case set is "
        "byte-identical to a run with the proposal stage switched off.",
        fill=FILL)

    footer(d, [
        "The trade in one line: the model buys recall we cannot write rules for, and pays for it in tokens and in a gate "
        "that must be strict enough to keep every published finding checkable.",
        "Not yet true today - this is the target architecture, queued as TESTOPS-95 to 99.",
    ], y=H - 120)
    save(img, "stage3-propose-dispose.png")


if __name__ == "__main__":
    stage1()
    stage2()
    stage3()
