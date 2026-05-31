#!/usr/bin/env python3
"""
Extrahiert Sichtungsmeldungen aus einem Facebook-RSS-Feed.
Speichert Rohdaten als JSON-Lines (eine Zeile pro Post) in eine Datei.
"""

import feedparser
import re
import json
from datetime import datetime
from urllib.parse import urlparse

# Konfiguration
RSS_URL = "https://www.facebook.com/feeds/page.php?id=100069898876035&format=rss20"  # Beispiel HocusLocus? Anpassen!
OUTPUT_FILE = "sichtungen.jsonl"  # append-modus

# Regex für interessante Muster (sehr fuzzy)
TAG_PATTERN = r'#[a-zA-Z0-9]+'
SIG_PATTERN = r'\b[a-z]{3}\d{2,4}-\d{4}[a-z]?\b'  # z.B. bgb42-2026-pkt1/2 oder 2024A059-1
ACTION_PATTERN = r'\b(habe|gefunden|abgegeben|gebucht|verkauft|erledigt|deponiert)\b'
LOCATION_PATTERN = r'\b(Butzbach|Marburg|Gießen|Wetzlar|Frankfurt|Berlin)\b'

def extract_tags(text):
    return re.findall(TAG_PATTERN, text, re.IGNORECASE)

def extract_signatures(text):
    return re.findall(SIG_PATTERN, text)

def extract_actions(text):
    return re.findall(ACTION_PATTERN, text, re.IGNORECASE)

def extract_locations(text):
    return re.findall(LOCATION_PATTERN, text)

def parse_facebook_post(entry):
    title = entry.get('title', '')
    summary = entry.get('summary', '')
    link = entry.get('link', '')
    published = entry.get('published', '')
    # Volltext kombinieren
    full_text = f"{title}\n{summary}"
    
    # Daten sammeln (keine Interpretation, nur Rohfundstellen)
    return {
        "source": "facebook_rss",
        "url": link,
        "timestamp": published,
        "raw_text": full_text[:5000],  # Begrenzung
        "tags": extract_tags(full_text),
        "signatures": extract_signatures(full_text),
        "actions": extract_actions(full_text),
        "locations": extract_locations(full_text),
        "fetched_at": datetime.utcnow().isoformat()
    }

def main():
    print(f"Abrufe RSS: {RSS_URL}")
    feed = feedparser.parse(RSS_URL)
    print(f"Gefundene Einträge: {len(feed.entries)}")
    with open(OUTPUT_FILE, "a", encoding="utf-8") as out:
        for entry in feed.entries:
            record = parse_facebook_post(entry)
            # Nur speichern, wenn etwas Interessantes drin ist (z.B. tags oder signatures)
            if record["tags"] or record["signatures"] or record["actions"]:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
                print(f"Gespeichert: {record['url']}")
    print("Fertig.")

if __name__ == "__main__":
    main()
