"""Draw the deployed TestOps architecture as a PNG. Second pass: layout faults fixed."""
import math
from PIL import Image, ImageDraw, ImageFont

W, H = 1760, 1200
BG = (250, 250, 248)
INK = (26, 32, 44)
MUTED = (110, 118, 128)
NAVY = (15, 37, 64)
GOLD = (218, 160, 0)
BROWN = (140, 94, 44)
AZURE = (0, 120, 212)
GREEN = (22, 120, 80)
GREY = (150, 156, 164)

FONT_DIR = "C:/Windows/Fonts/"
def f(name, size):
    return ImageFont.truetype(FONT_DIR + name, size)

F_TITLE = f("segoeuib.ttf", 34)
F_SUB = f("segoeui.ttf", 19)
F_ZONE = f("segoeuib.ttf", 20)
F_BOX = f("segoeuib.ttf", 20)
F_BODY = f("segoeui.ttf", 16)
F_SMALL = f("segoeui.ttf", 14)
F_MONO = f("consola.ttf", 15)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def rbox(xy, r=14, fill=(255, 255, 255), outline=GREY, width=2, dash=False):
    x0, y0, x1, y1 = xy
    if dash:
        d.rounded_rectangle(xy, radius=r, fill=fill, outline=None)
        step, seg = 16, 9
        for x in range(x0, x1, step):
            d.line([(x, y0), (min(x + seg, x1), y0)], fill=outline, width=width)
            d.line([(x, y1), (min(x + seg, x1), y1)], fill=outline, width=width)
        for y in range(y0, y1, step):
            d.line([(x0, y), (x0, min(y + seg, y1))], fill=outline, width=width)
            d.line([(x1, y), (x1, min(y + seg, y1))], fill=outline, width=width)
    else:
        d.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def text(xy, s, font=F_BODY, fill=INK, anchor="la"):
    d.text(xy, s, font=font, fill=fill, anchor=anchor)


def wrap(s, font, maxw):
    words, lines, cur = s.split(), [], ""
    for wd in words:
        t = (cur + " " + wd).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            lines.append(cur); cur = wd
    if cur:
        lines.append(cur)
    return lines


def para(xy, s, font=F_BODY, fill=INK, maxw=420, lh=None):
    x, y = xy
    lh = lh or int(font.size * 1.35)
    for line in wrap(s, font, maxw):
        text((x, y), line, font, fill); y += lh
    return y


def arrow(x0, y0, x1, y1, color=INK, width=2, dash=False, head=True):
    if dash:
        length = math.hypot(x1 - x0, y1 - y0)
        if length:
            ux, uy = (x1 - x0) / length, (y1 - y0) / length
            t = 0
            while t < length - 10:
                a = (x0 + ux * t, y0 + uy * t)
                b = (x0 + ux * min(t + 12, length - 10), y0 + uy * min(t + 12, length - 10))
                d.line([a, b], fill=color, width=width); t += 20
    else:
        d.line([(x0, y0), (x1, y1)], fill=color, width=width)
    if head:
        ang = math.atan2(y1 - y0, x1 - x0)
        for s in (0.42, -0.42):
            d.line([(x1, y1), (x1 - 14 * math.cos(ang - s), y1 - 14 * math.sin(ang - s))], fill=color, width=width)


def label(xy, s, font=F_SMALL, fill=MUTED, bg=BG, anchor="la"):
    tw = d.textlength(s, font=font)
    x, y = xy
    if anchor == "ra":
        d.rectangle([x - tw - 6, y - 3, x + 4, y + font.size + 5], fill=bg)
        text((x, y), s, font, fill, anchor="ra")
    else:
        d.rectangle([x - 5, y - 3, x + tw + 5, y + font.size + 5], fill=bg)
        text((x, y), s, font, fill)


text((48, 34), "TestOps on Azure - what is actually running", F_TITLE, NAVY)
text((48, 80), "Traced from az resource list -g rg-testops-demo on 24 November 2026. Every box is a resource; every arrow is a direction of control, not a wish.",
     F_SUB, MUTED)

# outside
rbox((48, 132, 470, 246), fill=(255, 255, 255), outline=GREY, width=2, dash=True)
text((70, 148), "Your team", F_BOX, NAVY)
para((70, 178), "A browser, on any network. No VPN, no client, no login.", F_BODY, MUTED, 372)

rbox((1290, 132, 1712, 246), fill=(255, 255, 255), outline=GREY, width=2, dash=True)
text((1312, 148), "github.com", F_BOX, NAVY)
para((1312, 178), "Public repositories, opened by the reader's browser from the links on a page.", F_BODY, MUTED, 380)

arrow(486, 190, 690, 190, color=GREY, width=2, dash=True)
arrow(1274, 190, 1070, 190, color=GREY, width=2, dash=True)
label((706, 176), "hyperlinks to files at a commit - fetched by the browser, never by the app", F_SMALL, MUTED)

# subscription
SUB = (48, 292, 1712, 1100)
rbox(SUB, r=18, fill=(247, 249, 252), outline=AZURE, width=3)
text((70, 306), "Azure subscription: Foundry  ·  965a76e1-8fe3-405e-b484-4820aca954b1", F_ZONE, AZURE)

# resource group
RG = (70, 356, 1300, 1074)
rbox(RG, r=16, fill=(255, 255, 255), outline=NAVY, width=3)
text((1278, 372), "Resource group: rg-testops-demo  ·  eastus", F_ZONE, NAVY, anchor="ra")
text((1278, 400), "Created for this deployment. Deleting it removes everything below in one command.", F_SMALL, MUTED, anchor="ra")

# environment
ENV = (92, 442, 1220, 816)
rbox(ENV, r=14, fill=(252, 253, 255), outline=BROWN, width=3, dash=True)
text((1198, 456), "Container Apps environment: testops-env", F_ZONE, BROWN, anchor="ra")
text((1198, 482), "Shared network and logging boundary.", F_SMALL, MUTED, anchor="ra")

# ingress
ING = (116, 512, 500, 612)
rbox(ING, fill=(255, 251, 240), outline=GOLD, width=3)
text((136, 526), "External ingress", F_BOX, (120, 88, 0))
text((136, 556), "https :443  ->  container :8080", F_MONO, INK)
text((136, 580), "Public. No auth, no IP restriction.", F_SMALL, MUTED)

# container app
APP = (116, 644, 1196, 802)
rbox(APP, fill=(244, 249, 255), outline=AZURE, width=3)
text((136, 656), "Container app: testops", F_BOX, NAVY)
text((136, 682), "0.25 vCPU · 0.5 GiB · replicas 1..1  (min 1 for the demo, scaled to 0 after 12:30)", F_SMALL, MUTED)

IX, IY = 136, 708
boxes = [
    ("HTTP server", "Python 3.12 stdlib\nThreadingHTTPServer\n:8080, 0.0.0.0", 250),
    ("Page renderer", "reads records,\nrenders HTML\n~0.35 s a page", 250),
    ("Store (baked)", "testops.db 7.9 MB\nSQLite, read-mostly", 250),
    ("Blobs (baked)", "blobs/ 3.8 MB\nsnippets at commit", 250),
]
x = IX
for title_s, body_s, w in boxes:
    rbox((x, IY, x + w - 14, 794), r=10, fill=(255, 255, 255), outline=GREY, width=2)
    text((x + 14, IY + 6), title_s, F_BODY, NAVY)
    y = IY + 28
    for line in body_s.split("\n"):
        mono = line.startswith(("testops.db", "blobs/", "Python", ":8080"))
        text((x + 14, y), line, F_MONO if mono else F_SMALL, INK if mono else MUTED)
        y += 16
    x += w

# registry
ACR = (92, 836, 600, 952)
rbox(ACR, fill=(255, 255, 255), outline=NAVY, width=3)
text((112, 850), "Container registry: testopsdemo30562", F_BOX, NAVY)
text((112, 880), "Basic tier · admin credentials on", F_SMALL, MUTED)
text((112, 900), "testops:v1   (digest sha256:769a516e...)", F_MONO, INK)
text((112, 924), "Built in Azure by ACR Tasks - no local Docker needed.", F_SMALL, MUTED)

# log analytics
LA = (640, 836, 1220, 952)
rbox(LA, fill=(255, 255, 255), outline=NAVY, width=3)
text((660, 850), "Log Analytics: workspace-rgtestopsdemoTazJ", F_BOX, NAVY)
text((660, 880), "Auto-created with the environment (I did not name one).", F_SMALL, MUTED)
text((660, 900), "Container stdout: the place to look if a page errors.", F_SMALL, MUTED)
text((660, 924), "az containerapp logs show -n testops -g rg-testops-demo --tail 40", F_MONO, INK)

# untouched neighbour
FP = (1324, 356, 1690, 520)
rbox(FP, fill=(246, 246, 246), outline=GREY, width=3, dash=True)
text((1344, 372), "rg-foundry-prod", F_BOX, (90, 96, 104))
para((1344, 404), "FoundryVTT: the Pathfinder server. Not touched, not queried, not redeployed - separate resource group, separate registry.",
     F_SMALL, (110, 116, 124), 326)

# arrows
arrow(300, 246, 300, 510, color=NAVY, width=3)
label((312, 468), "HTTPS, public", F_SMALL, NAVY)
arrow(308, 612, 308, 642, color=GOLD, width=3)
label((320, 618), ":8080", F_SMALL, (120, 88, 0))
arrow(346, 836, 346, 804, color=NAVY, width=3)
label((358, 812), "image pulled at revision start", F_SMALL, NAVY)
arrow(1160, 802, 1160, 834, color=GREEN, width=3)
label((1148, 812), "container logs", F_SMALL, GREEN, anchor="ra")

text((48, 1124), "Not shown because it does not exist: no database server, no queue, no secrets manager, no outbound network path. The app is one process, one file, one directory of blobs.",
     F_SMALL, MUTED)

out = "C:/Users/Chester/Projects/testops/factory/reports/2026-11-24/testops-azure-components.png"
img.save(out)
print("saved", out)
