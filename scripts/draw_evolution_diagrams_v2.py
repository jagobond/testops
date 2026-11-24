"""Draw the three-stage TestOps architecture evolution as presentation PNGs (v2: bigger type, full canvas).

Grid: five columns, fixed gutters, one idea per box. Hand-placed: a generated graph is unreadable at presentation size.
Every stage fills its canvas - dead space is a design fault, not breathing room.
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 2000, 1040
NAVY = (15, 37, 64)
GOLD = (218, 160, 0)
INK = (28, 35, 46)
MUTED = (82, 94, 110)
LINE = (188, 198, 210)
FILL = (245, 247, 250)
GOLD_FILL = (253, 246, 227)
GREEN_FILL = (232, 242, 234)
GREEN = (38, 100, 60)
RED_FILL = (251, 235, 233)
RED = (146, 50, 40)
WHITE = (255, 255, 255)

COL = [70, 450, 830, 1210, 1590]
CW = 340

F = {
    "h1": "C:/Windows/Fonts/segoeuib.ttf",
    "h2": "C:/Windows/Fonts/segoeuib.ttf",
    "body": "C:/Windows/Fonts/segoeui.ttf",
    "small": "C:/Windows/Fonts/segoeuib.ttf",
    "bold": "C:/Windows/Fonts/segoeuib.ttf",
}


def font(kind, size):
    return ImageFont.truetype(F[kind], size)


def wrap(d, text, fnt, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=fnt) <= width:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def box(d, x, y, w, h, title, body="", fill=FILL, edge=LINE, accent=None,
        title_size=27, body_size=22, radius=14, title_color=INK):
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill, outline=edge, width=2)
    if accent:
        d.rounded_rectangle([x + 1, y + 1, x + w - 1, y + 8], radius=4, fill=accent)
    tf, bf = font("h2", title_size), font("body", body_size)
    ty = y + 24
    for line in wrap(d, title, tf, w - 40):
        d.text((x + 20, ty), line, font=tf, fill=title_color)
        ty += title_size + 5
    if body:
        ty += 4
        for line in wrap(d, body, bf, w - 40):
            if ty + body_size > y + h - 12:
                break
            d.text((x + 20, ty), line, font=bf, fill=MUTED)
            ty += body_size + 6


def arrow(d, x1, y1, x2, y2, label="", color=MUTED, width=3, dashed=False, head=13, label_size=19):
    if dashed:
        total = math.hypot(x2 - x1, y2 - y1)
        step, drawn = 13, 0
        while drawn < total - head:
            t0, t1 = drawn / total, min((drawn + step) / total, (total - head) / total)
            d.line([x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0,
                    x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1], fill=color, width=width)
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
        d.rectangle([mx - tw / 2 - 9, my - 16, mx + tw / 2 + 9, my + 16], fill=WHITE)
        d.text((mx - tw / 2, my - 12), label, font=f, fill=color)


def header(d, num, title, subtitle):
    d.rectangle([0, 0, W, 120], fill=NAVY)
    d.rectangle([0, 120, W, 127], fill=GOLD)
    d.text((70, 22), f"STAGE {num}", font=font("bold", 23), fill=GOLD)
    d.text((70, 52), title, font=font("h1", 42), fill=WHITE)
    f = font("body", 23)
    d.text((W - 70 - d.textlength(subtitle, font=f), 66), subtitle, font=f, fill=(214, 222, 234))


def band(d, y, cards, h=132):
    n = len(cards)
    gap = 30
    w = (W - 140 - gap * (n - 1)) // n
    for i, (title, body, fill, edge) in enumerate(cards):
        box(d, 70 + i * (w + gap), y, w, h, title, body, fill=fill, edge=edge, title_size=24, body_size=20)


def footer(d, text):
    d.line([70, H - 88, W - 70, H - 88], fill=LINE, width=2)
    f = font("body", 22)
    ty = H - 70
    for line in wrap(d, text, f, W - 140):
        d.text((70, ty), line, font=f, fill=MUTED)
        ty += 28


def canvas():
    img = Image.new("RGB", (W, H), WHITE)
    return img, ImageDraw.Draw(img)


def save(img, name):
    out = Path(__file__).resolve().parent / name
    img.save(out)
    print(out)


def stage1():
    img, d = canvas()
    header(d, 1, "The deterministic engine", "what rules alone can prove")
    top, tall = 165, 430

    box(d, COL[0], top, CW, 195, "Product repository",
        "pinned to one commit; every file stored once, with its path and SHA")
    box(d, COL[0], top + 235, CW, 195, "Test repository",
        "same commit discipline: features, step definitions, harness config")

    box(d, COL[1], top, CW, tall, "Readers, one per ecosystem",
        "Gherkin + step bindings (.NET, cucumber-js); Java/Spring routes from annotations; surface discovery. "
        "A language nobody wrote a reader for reports itself as unread, never as empty.",
        fill=GOLD_FILL, edge=GOLD)

    box(d, COL[2], top, CW, tall, "Evidence store",
        "SQLite plus content-addressed blobs. Artefact, claim, finding, decision: each a row with path, line and commit. "
        "Nothing a page shows is fetched live. Re-recording an unchanged arm costs rows, not bytes.")

    box(d, COL[3], top, CW, 210, "Level fitness",
        "is this assertion settled at the layer the test drives? a browser test reading a JSON field is 'review'; "
        "a claim only a browser could settle is 'gap'.", body_size=21)
    box(d, COL[3], top + 230, CW, 200, "Duplication",
        "the same assertion made twice, across suites and files - compared on the assertion's words, never the "
        "scenario title.", body_size=21)

    box(d, COL[4], top, CW, 250, "Case pages",
        "verdict, the test line, the product line and the proposed action - both sides shown as code, with file, line "
        "and commit, so a reader can disagree in ten seconds.", fill=GREEN_FILL, edge=GREEN)
    box(d, COL[4], top + 300, CW, 130, "Human decision",
        "resolved / false positive / needs fixing")

    arrow(d, COL[0] + CW, top + 97, COL[1], top + 97)
    arrow(d, COL[0] + CW, top + 332, COL[1], top + 332)
    arrow(d, COL[1] + CW, top + 215, COL[2], top + 215)
    arrow(d, COL[2] + CW, top + 110, COL[3], top + 110)
    arrow(d, COL[2] + CW, top + 320, COL[3], top + 320)
    arrow(d, COL[3] + CW, top + 105, COL[4], top + 95)
    arrow(d, COL[3] + CW, top + 330, COL[4], top + 200)
    arrow(d, COL[4] + CW / 2, top + 250, COL[4] + CW / 2, top + 300)

    band(d, 640, [
        ("Pure functions", "same rows in, same verdict out - no clock, no network, no model", GREEN_FILL, GREEN),
        ("No model in this picture", "every verdict can be rebuilt offline from stored rows", GOLD_FILL, GOLD),
        ("Absence is a state", "unread is reported as unread; skipped is never counted as consulted", FILL, LINE),
    ])
    footer(d, "What this stage cannot do: it only finds issue shapes its vocabulary names - tests that assert nothing, or "
              "assert their own fixture, or are satisfied by a mock, stay invisible. And a page that says 'distinct' reads "
              "as 'fine' when it means 'nothing my rules look for'.")
    save(img, "stage1-deterministic.png")


def stage2():
    img, d = canvas()
    header(d, 2, "The engine, plus an agentic narrator", "the model explains; it never decides")
    top = 150

    box(d, COL[0], top, CW, 125, "Repositories", "product + tests at one commit")
    box(d, COL[0], top + 160, CW, 125, "Readers", "one per ecosystem", fill=GOLD_FILL, edge=GOLD)
    box(d, COL[0], top + 320, CW, 125, "Evidence store", "rows and blobs, one commit")
    arrow(d, COL[0] + CW / 2, top + 125, COL[0] + CW / 2, top + 160)
    arrow(d, COL[0] + CW / 2, top + 285, COL[0] + CW / 2, top + 320)

    box(d, COL[1], top, CW, 125, "Analysers", "level fitness, duplication - pure functions")
    box(d, COL[1], top + 195, CW, 140, "Case page", "the verdict, and the rows behind it")
    arrow(d, COL[1] + CW / 2, top + 125, COL[1] + CW / 2, top + 195)

    box(d, COL[2], top, CW, 165, "Foundry hosted agent",
        "testops-narrator, own identity, model deepseek-flash. Asked only for agent=on.",
        fill=GOLD_FILL, edge=GOLD, title_size=26, body_size=21)
    box(d, COL[2], top + 195, CW, 165, "Citation guard",
        "every sentence must cite a stored row; an invented route or count discards the reply",
        fill=GREEN_FILL, edge=GREEN, title_size=26, body_size=21)
    arrow(d, COL[1] + CW, top + 62, COL[2], top + 62)
    arrow(d, COL[2] + CW / 2, top + 165, COL[2] + CW / 2, top + 195)

    box(d, COL[3], top + 195, CW, 165, "Rendered page",
        "explanation above the verdict, labelled commentary, or the honest fallback",
        title_size=26, body_size=21)
    arrow(d, COL[2] + CW, top + 277, COL[3], top + 277)

    box(d, COL[4], top, CW, 165, "What stays true",
        "the verdict is byte-identical to the agent-off page, over all 275 real pages",
        fill=GREEN_FILL, edge=GREEN, title_size=26, body_size=21)
    box(d, COL[4], top + 195, CW, 165, "Ledger and votes",
        "tokens, route, state; two vote links per explanation", title_size=26, body_size=21)
    arrow(d, COL[3] + CW, top + 277, COL[4], top + 277)

    band(d, 630, [
        ("The model is never asked", "it reacts only to findings the rules already made", GOLD_FILL, GOLD),
        ("Failure is visible", "unreachable, slow or rejected: the page says which", RED_FILL, RED),
        ("Cost is measured", "per call, per route, per state - the A/B answers whether it was worth it", FILL, LINE),
    ])
    footer(d, "What this stage does not do yet: the agent has no way to raise something the rules missed, because nothing "
              "asks it to look. That is stage three.")
    save(img, "stage2-with-narrator.png")


def stage3():
    img, d = canvas()
    header(d, 3, "Model proposes, rules dispose", "recall from the model, authority from the rules")
    top = 160

    box(d, COL[0], top, CW, 130, "Repositories", "product + tests at one commit")
    box(d, COL[0], top + 165, CW, 130, "Readers", "one per ecosystem", fill=GOLD_FILL, edge=GOLD)
    box(d, COL[0], top + 330, CW, 130, "Evidence store", "rows and blobs, one commit")
    arrow(d, COL[0] + CW / 2, top + 130, COL[0] + CW / 2, top + 165)
    arrow(d, COL[0] + CW / 2, top + 295, COL[0] + CW / 2, top + 330)

    box(d, COL[1], top, CW, 130, "Deterministic analysers",
        "what a rule can prove today - unchanged by this stage")
    box(d, COL[1], top + 200, CW, 260, "Proposal stage - model",
        "the agent reads an evidence pack and suggests candidates: wrong level, duplicate of product, asserts nothing. "
        "No authority, no page, no verdict.", fill=GOLD_FILL, edge=GOLD)
    arrow(d, COL[0] + CW, top + 395, COL[1], top + 330)
    arrow(d, COL[0] + CW, top + 340, COL[1], top + 70, color=(150, 160, 174), dashed=True)

    box(d, COL[2], top + 200, CW, 200, "Candidate store",
        "the suggestion, the rows it points at, agent version, prompt hash, tokens, raw reply - stored, never published")
    arrow(d, COL[1] + CW, top + 330, COL[2], top + 330)

    box(d, COL[3], top + 185, CW, 290, "The gate - rules",
        "route exists at that commit?  claim maps to that layer?  the duplicate really differs?  the assertion really "
        "empty?  No gate, no finding.", fill=GREEN_FILL, edge=GREEN)
    arrow(d, COL[2] + CW, top + 300, COL[3], top + 300)

    box(d, COL[4], top, CW, 190, "Accepted: a finding",
        "a case that says - proposed by agent v3, verified by rule X", fill=GREEN_FILL, edge=GREEN)
    box(d, COL[4], top + 240, CW, 130, "Rejected: the ledger",
        "why it failed, per candidate kind", fill=RED_FILL, edge=RED)
    box(d, COL[4], top + 380, CW, 100, "Cost per finding",
        "tokens and time, measured")
    arrow(d, COL[3] + CW, top + 210, COL[4], top + 150, color=GREEN)
    arrow(d, COL[3] + CW, top + 455, COL[4], top + 300, color=RED, dashed=True)
    arrow(d, COL[4] + CW / 2, top + 360, COL[4] + CW / 2, top + 380, dashed=True, color=LINE)

    band(d, 640, [
        ("Recall is measured, not assumed",
         "a blind gold set, plus a model-as-probe pass over cases we called distinct", GOLD_FILL, GOLD),
        ("Authority never moves",
         "every candidate rejected: the case set is byte-identical to proposals switched off", GREEN_FILL, GREEN),
        ("Provenance is on the page",
         "which agent proposed it, which rule verified it, which rows it rests on", FILL, LINE),
    ])
    footer(d, "Not true yet - this is the target, queued as TESTOPS-95 to 99. The trade in one line: the model buys recall we "
              "cannot write rules for, and pays for it in tokens and in a gate strict enough to keep every published finding "
              "checkable.")
    save(img, "stage3-propose-dispose.png")


if __name__ == "__main__":
    stage1()
    stage2()
    stage3()
