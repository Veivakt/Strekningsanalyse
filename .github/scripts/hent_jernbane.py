#!/usr/bin/env python3
"""Henter jernbanenettet (Banelenke) fra Bane NOR via Geonorge og lagrer en forenklet kopi som jernbane.json.

Kilde: Jernbane - Banenettverk, Bane NOR SF, levert gjennom Geonorge. Lisens: NLOD.
Koordinater lagres i EUREF89 UTM sone 33 (EPSG:25833), rundet til hele meter.
"""
import json, sys, urllib.request, datetime, xml.etree.ElementTree as ET

URL = ("https://wfs.geonorge.no/skwms1/wfs.banenettverk?service=WFS&version=2.0.0&request=GetFeature"
       "&typeNames=app:Banelenke&srsName=urn:ogc:def:crs:EPSG::25833")
TOLERANSE = 3.0  # meter, forenkling av linjene


def lokal(tag):
    return tag.rsplit('}', 1)[-1]


def forenkle(p, tol):
    if len(p) < 3:
        return p
    keep = [False] * len(p); keep[0] = keep[-1] = True
    stakk = [(0, len(p) - 1)]
    while stakk:
        a, b = stakk.pop()
        ax, ay = p[a]; bx, by = p[b]; dx, dy = bx - ax, by - ay; L2 = dx * dx + dy * dy
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            x, y = p[i]
            if L2 == 0:
                d = (x - ax) ** 2 + (y - ay) ** 2
            else:
                t = max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
                d = (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2
            if d > best:
                best, bi = d, i
        if bi > 0 and best > tol * tol:
            keep[bi] = True; stakk += [(a, bi), (bi, b)]
    return [q for q, k in zip(p, keep) if k]


def main(ut):
    req = urllib.request.Request(URL, headers={"User-Agent": "VeiVakt-strekningsanalyse"})
    with urllib.request.urlopen(req, timeout=600) as r:
        rot = ET.parse(r).getroot()
    lenker, eksempel, statuser, hoppet = [], None, {}, 0
    for el in rot.iter():
        if lokal(el.tag) != "Banelenke":
            continue
        felt, pos = {}, []
        for d in el.iter():
            n = lokal(d.tag)
            if n == "posList" and d.text:
                pos += [float(v) for v in d.text.split()]
            elif n == "pos" and d.text:
                pos += [float(v) for v in d.text.split()[:2]]
            elif len(d) == 0 and d.text and d.text.strip() and n not in felt:
                felt[n] = d.text.strip()
        if eksempel is None:
            eksempel = felt
        if len(pos) < 4:
            hoppet += 1; continue
        p = [(pos[i], pos[i + 1]) for i in range(0, len(pos) - 1, 2)]
        if p[0][0] > 3_000_000:  # nord først: bytt om
            p = [(y, x) for x, y in p]
        navn = next((v for k, v in felt.items() if "navn" in k.lower()), "")
        status = next((v for k, v in felt.items() if k.lower().endswith("status")), "")
        statuser[status] = statuser.get(status, 0) + 1
        if status.upper() == "P":  # planlagt bane, ikke i drift
            continue
        try:
            fra, til = float(felt.get("startposisjon", "nan")), float(felt.get("sluttposisjon", "nan"))
        except ValueError:
            fra = til = float("nan")
        q = forenkle(p, TOLERANSE)
        k = []
        for x, y in q:
            k += [round(x), round(y)]
        lenker.append({"n": navn, "f": None if fra != fra else round(fra, 3),
                       "t": None if til != til else round(til, 3), "s": status, "k": k})
    if len(lenker) < 50:
        sys.exit(f"For få banelenker ({len(lenker)}). Avbryter uten å lagre.")
    data = {"kilde": "Jernbane - Banenettverk, Bane NOR SF via Geonorge (NLOD)",
            "hentet": datetime.date.today().isoformat(), "koordinater": "EPSG:25833",
            "statuser": statuser, "eksempel": eksempel, "hoppet_over": hoppet, "lenker": lenker}
    with open(ut, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    print(len(lenker), "banelenker lagret.", statuser)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "jernbane.json")
