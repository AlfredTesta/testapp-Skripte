#!/usr/bin/env python3
"""
Parser für alle Beiträge eines Blogs (Blogspot/Blogger).
Extrahiert Metadaten, Signaturen, Tags und Orte.
"""

import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin, urlparse
import time
from typing import List, Dict, Set

# ========== KONFIGURATION ==========
BLOG_URL = "https://atestabib.blogspot.com/"  # Hier deine Blog-URL einfügen
OUTPUT_FILE = "blog_sichtungen.jsonl"
REQUEST_DELAY = 1.0  # Sekunden zwischen Requests (höflich bleiben)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ========== REGEX-MUSTER ==========
TAG_PATTERN = r'#[a-zA-Z0-9]+'
SIG_PATTERN = r'\b\d{4}[A-Za-z]?\d{3}-\d+[a-z]?\b'  # z.B. 2025D042-10c
ACTION_PATTERN = r'\b(abgabe|deponiert|platziert|gelegt|gestellt|gefunden|entnommen)\b'
LOCATION_PATTERN = r'\b(Butzbach|Marburg|Gießen|Wetzlar|Frankfurt|Mittelhessen|Pazifik|Atlantis)\b'

# ========== FUNKTIONEN ==========
def get_page_soup(url: str) -> BeautifulSoup:
    """Lädt eine URL und gibt ein BeautifulSoup-Objekt zurück."""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        # Blogspot liefert oft Windows-1252 kodierte Seiten, aber wir dekodieren automatisch
        response.encoding = response.apparent_encoding or 'utf-8'
        return BeautifulSoup(response.text, 'lxml')
    except Exception as e:
        print(f"Fehler beim Laden von {url}: {e}")
        return None

def extract_post_links_from_index(soup: BeautifulSoup, base_url: str) -> Set[str]:
    """Extrahiert alle Links zu einzelnen Blog-Posts aus der Hauptseite oder Archiv-Seite."""
    links = set()
    # Blogspot-spezifische Selektoren für Post-Links
    for a in soup.find_all('a', href=True):
        href = a['href']
        # Typische Blogspot-Post-Links enthalten Jahreszahl/Monat im Pfad
        if '/2026/' in href or '/2025/' in href or '/2024/' in href:
            full_url = urljoin(base_url, href)
            # Normalisiere: entferne Anker, Query-Parameter
            full_url = full_url.split('#')[0].split('?')[0]
            if full_url not in links:
                links.add(full_url)
    # Alternative: Alle Links, die nicht auf die Hauptseite oder Label-Seiten zeigen
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href.startswith('http'):
            href = urljoin(base_url, href)
        # Ignoriere Label- und Archiv-Seiten
        if '/search/label/' in href or '/search?updated' in href or '/feeds/' in href:
            continue
        if href.startswith(BLOG_URL) and '#' not in href and '?q=' not in href:
            if '/202' in href:  # Jahreszahl im Pfand
                links.add(href.split('?')[0].split('#')[0])
    return links

def extract_metadata(soup: BeautifulSoup, url: str) -> Dict:
    """Extrahiert Titel, Datum und Textinhalt eines Blog-Posts."""
    metadata = {
        "url": url,
        "title": "",
        "date": "",
        "text": ""
    }
    
    # Titel extrahieren: verschiedene Blogspot-Möglichkeiten
    title_tag = soup.find('h3', class_='post-title')
    if not title_tag:
        title_tag = soup.find('h1', class_='title')
    if not title_tag:
        title_tag = soup.find('h2')
    if title_tag:
        metadata["title"] = title_tag.get_text().strip()
    
    # Datum extrahieren (Blogspot: oft im <h2> oder <span> mit Klasse 'date-header')
    date_tag = soup.find('h2', class_='date-header')
    if not date_tag:
        date_tag = soup.find('span', class_='publishdate')
    if not date_tag:
        # Suche nach Text mit Datumsmuster
        for tag in soup.find_all(['span', 'div', 'h2']):
            text = tag.get_text()
            if re.search(r'\b(Donnerstag|Freitag|Samstag|Mittwoch),\s+\d{1,2}\.\s+\w+\s+\d{4}\b', text):
                metadata["date"] = text.strip()
                break
    else:
        metadata["date"] = date_tag.get_text().strip()
    
    # Textinhalt extrahieren: Blogspot-Container für Post-Body
    body = soup.find('div', class_='post-body')
    if not body:
        body = soup.find('div', class_='entry-content')
    if not body:
        body = soup.find('article') or soup.find('main')
    if body:
        metadata["text"] = body.get_text().strip()
    else:
        # Fallback: gesamter Body-Text
        metadata["text"] = soup.get_text()
    
    return metadata

def extract_entities(text: str) -> Dict:
    """Extrahiert Tags, Signaturen, Aktionen, Orte aus dem Text."""
    return {
        "tags": list(set(re.findall(TAG_PATTERN, text, re.IGNORECASE))),
        "signatures": list(set(re.findall(SIG_PATTERN, text))),
        "actions": list(set(re.findall(ACTION_PATTERN, text, re.IGNORECASE))),
        "locations": list(set(re.findall(LOCATION_PATTERN, text)))
    }

def process_single_post(url: str) -> Dict:
    """Verarbeitet einen einzelnen Blog-Post: Lädt, parst, extrahiert."""
    print(f"Verarbeite: {url}")
    soup = get_page_soup(url)
    if not soup:
        return None
    
    metadata = extract_metadata(soup, url)
    entities = extract_entities(metadata["text"] + " " + metadata["title"])
    
    # Ergebnis zusammenbauen
    result = {
        "source": "blog",
        "url": metadata["url"],
        "title": metadata["title"],
        "date": metadata["date"],
        "raw_text": metadata["text"][:5000],  # Begrenzung
        "tags": entities["tags"],
        "signatures": entities["signatures"],
        "actions": entities["actions"],
        "locations": entities["locations"],
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }
    return result

def get_all_post_urls(start_url: str = BLOG_URL) -> Set[str]:
    """Sammelt alle Post-URLs eines Blogs, indem es die Hauptseite und ggf. Archive navigiert."""
    all_urls = set()
    soup = get_page_soup(start_url)
    if not soup:
        return all_urls
    
    # Links von der Hauptseite
    urls = extract_post_links_from_index(soup, start_url)
    all_urls.update(urls)
    
    # Gibt es "Ältere Posts" Links? (Blogspot-Pagination)
    older_link = soup.find('a', class_='blog-pager-older-link')
    if older_link and older_link.get('href'):
        older_url = older_link['href']
        if older_url.startswith('/'):
            older_url = urljoin(start_url, older_url)
        # Vermeide Endlosschleife: nur wenn die URL noch nicht verarbeitet wurde
        if older_url not in all_urls and not older_url.endswith('#comments'):
            print(f"Folge Paginierung: {older_url}")
            time.sleep(REQUEST_DELAY)
            older_urls = get_all_post_urls(older_url)
            all_urls.update(older_urls)
    return all_urls

def main():
    print(f"Starte Parsing des Blogs: {BLOG_URL}")
    all_post_urls = get_all_post_urls()
    print(f"Gefundene Blog-Posts: {len(all_post_urls)}")
    
    with open(OUTPUT_FILE, "w", encoding="utf-8") as out_f:
        for idx, url in enumerate(all_post_urls):
            print(f"({idx+1}/{len(all_post_urls)})")
            result = process_single_post(url)
            if result:
                out_f.write(json.dumps(result, ensure_ascii=False) + "\n")
                out_f.flush()
            time.sleep(REQUEST_DELAY)
    
    print(f"Fertig. Ergebnisse gespeichert in {OUTPUT_FILE}")

if __name__ == "__main__":
    main()