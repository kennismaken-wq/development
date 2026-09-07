"""Zet de lettertypen lokaal neer, zodat de app geen verbinding met Google
maakt. Eenmalig te draaien; de bestanden gaan mee in de repo."""
import re, urllib.request, pathlib

MODERN = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
CSS_URL = ("https://fonts.googleapis.com/css2?"
           "family=Fraunces:ital,wght@0,600;1,600;1,700&family=Inter:wght@400;500;600;700&display=swap")

doelmap = pathlib.Path("static/fonts")
verzoek = urllib.request.Request(CSS_URL, headers={"User-Agent": MODERN})
css = urllib.request.urlopen(verzoek, timeout=30).read().decode()

regels = []
for blok in re.findall(r"@font-face\s*\{(.*?)\}", css, re.S):
    bereik = re.search(r"unicode-range:\s*([^;]+);", blok)
    if not bereik or "U+0000-00FF" not in bereik.group(1):
        continue  # alleen het latijnse subset; de rest gebruiken we niet
    familie = re.search(r"font-family:\s*'([^']+)'", blok).group(1)
    stijl = (re.search(r"font-style:\s*(\w+)", blok) or [None, "normal"])[1]
    gewicht = (re.search(r"font-weight:\s*(\d+)", blok) or [None, "400"])[1]
    url = re.search(r"url\((https://[^)]+)\)", blok).group(1)

    naam = f"{familie}-{gewicht}{'-italic' if stijl == 'italic' else ''}.woff2"
    data = urllib.request.urlopen(url, timeout=30).read()
    (doelmap / naam).write_bytes(data)
    print(f"{naam:32} {len(data):6d} bytes")
    regels.append(
        "@font-face{font-family:'%s';font-style:%s;font-weight:%s;font-display:swap;"
        "src:url('../fonts/%s') format('woff2');}" % (familie, stijl, gewicht, naam)
    )

pathlib.Path("static/css/fonts.css").write_text("\n".join(regels) + "\n", encoding="utf-8")
print("static/css/fonts.css geschreven:", len(regels), "gezichten")
