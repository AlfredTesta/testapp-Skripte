### 1. Projektziel

Entwicklung eines Python-Skripts, das alle Diskussionsseiten eines bestimmten Wikipedia-Artikels (inkl. aller zugehörigen Archivseiten) parst und die darin enthaltenen Diskussionsbeiträge als strukturierte JSONL-Datei exportiert. Die Ausgabe soll für die weitere Verarbeitung in einer "Loch-Matrix" geeignet sein – d.h. sie ist fragmentiert, unscharf und verweist auf ihre Quellen.

---

### 2. Anforderungen im Überblick

| Kategorie | Anforderung |
|-----------|-------------|
| **Eingabe** | Wikipedia-Artikeltitel (z. B. "Bibliothek") oder direkte URL der Diskussionsseite |
| **Ausgabe** | JSONL-Datei (eine Zeile pro Diskussionsbeitrag) |
| **Vollständigkeit** | Erfasst Hauptdiskussionsseite + alle Unterseiten mit `/Archiv/` im Pfad |
| **Struktur** | Extrahiert Hierarchie der Antworten (Threading) |
| **Metadaten** | Autor, Zeitstempel, Abschnittsüberschrift, Antworttiefe, Status (Erledigt, etc.) |
| **Netiquette** | Identifizierbarer User-Agent, Crawling-Verzögerung, conditional requests |
| **Fehlertoleranz** | Robust gegenüber fehlenden Signaturen, unsauberen Einrückungen, Vorlagen |

---

### 3. Detaillierte Funktionsbeschreibung

#### 3.1. Seitenfindung (Crawling)

1. **Ausgangspunkt:** Hauptdiskussionsseite (z. B. `https://de.wikipedia.org/wiki/Diskussion:Bibliothek`).
2. **Extraktion aller Links** auf dieser Seite.
3. **Filterung** auf Links, die:
   - auf Unterseiten der Diskussion verweisen (Pfad enthält `Diskussion:` und `/Archiv/`),
   - keine externen Links sind,
   - keine Anker (`#`) als einzigen Unterschied haben.
4. **Rekursives Verfolgen** dieser Archiv-Links, bis keine neuen mehr gefunden werden.
5. **Deduplikation** der gefundenen URLs.

#### 3.2. Parsing einer einzelnen Diskussionsseite

Für jede Seite werden die folgenden Schritte ausgeführt:

##### 3.2.1. HTML-Extraktion
- Abruf der Seite mit `requests.get(...)`.
- Setzen eines **User-Agent**-Headers (z. B. `WikipediaDiskussionParser/1.0 (Kontakt: ...)`).
- Verwendung von **BeautifulSoup** zur Navigation im DOM.

##### 3.2.2. Erkennung von Diskussionsabschnitten
- Jeder Diskussionsthread beginnt typischerweise mit einer **Überschrift** (`<h2>`, `<h3>` oder `<h4>` mit Klasse `mw-headline`). 
- Der Text unter der Überschrift bis zur nächsten Überschrift gleicher oder höherer Ebene gehört zum Abschnitt.

##### 3.2.3. Zerlegung eines Abschnitts in Beiträge
- Innerhalb eines Abschnitts werden **Beiträge** durch Einrückungen (im Wikitext: `:` oder `*`) getrennt. 
- Im geparsten HTML entsprechen diese oft `<dl>` (Definition List) oder `<ul>`/`<li>`-Strukturen.
- Die Einrückungstiefe (Anzahl der `:` oder der Verschachtelungsebene) bestimmt die **Antwort-Hierarchie**:

```
Tiefe 0: Neuer Thread / Erster Beitrag
Tiefe 1: Antwort auf den ersten Beitrag
Tiefe 2: Antwort auf eine Antwort
usw.
```

##### 3.2.4. Extraktion von Metadaten pro Beitrag

| Feld | Erkennungsmethode | Beispiel |
|------|-------------------|----------|
| **Autor** | Signatur am Ende des Beitrags, Muster `--[[Benutzer:Name\|Name]]` oder ` ~~~~` oder IP-Adresse | `--Nichtich 01:51, 14. Jul 2003 (CEST)` → `Nichtich` |
| **Datum** | Datums- und Zeitangabe innerhalb der Signatur | Umwandlung in ISO 8601: `2003-07-14T01:51:00+02:00` |
| **Beitragstext** | Alles zwischen Beginn des Beitrags und der Signatur (Signatur selbst wird entfernt) | – |
| **Status** | Erkennung von Vorlagen wie `Erledigt`, `Archiviert` am Anfang oder Ende des Beitrags | `{{Erledigt|1=~~~}}` |
| **Abschnitt** | Die Überschrift, unter der der Beitrag steht | `Seite für Begriffsdefinition einführen` |
| **Antworttiefe** | Zahl der Einrückungsebenen | `0`, `1`, `2`, ... |
| **Beitrags-ID** | Hash aus URL + Abschnitt + Autor + Datum + Tiefe (für spätere Verweise) | `a1b2c3d4` |

##### 3.2.5. Umgang mit Sonderfällen
- **Unsigned-Beiträge:** Wenn keine Signatur gefunden wird → Autor = `"unbekannt"`, Datum = `None`.
- **Gesperrte oder gelöschte Benutzer:** Der Benutzername wird dennoch als Text extrahiert.
- **Vorlagen:** Sie werden **nicht aufgelöst**, sondern als Roh-Text (`{{Erledigt}}`) im `raw_text` belassen. Zusätzlich wird eine `template`-Liste mit den gefundenen Vorlagennamen geführt.
- **Mehrere Signaturen in einem Beitrag:** Die **letzte** Signatur im Text wird als die des Autors gewertet (häufigste Praxis).
- **Beiträge ohne Einrückung:** Sie werden als neue Threads (Tiefe 0) behandelt.

#### 3.3. Ausgabedatei (JSONL)

Jeder Beitrag wird als ein **JSON-Objekt** in einer eigenen Zeile geschrieben. Beispiel:

```json
{
  "source_url": "https://de.wikipedia.org/wiki/Diskussion:Bibliothek",
  "archive": "Hauptseite",
  "section": "Seite für Begriffsdefinition einführen",
  "author": "Nichtich",
  "timestamp": "2003-07-14T01:51:00+02:00",
  "raw_text": "Welche Russische(n) Bibliothek(en) gehören Weltweit zu den wichtigsten? Müsste man noch hinzufügen.",
  "reply_depth": 0,
  "status": null,
  "templates": [],
  "contribution_id": "df8a3f2b"
}
```

Für einen archivierten Beitrag aus `Diskussion:Bibliothek/Archiv/001`:

```json
{
  "source_url": "https://de.wikipedia.org/wiki/Diskussion:Bibliothek/Archiv/001",
  "archive": "001",
  "section": "Alte Diskussion",
  "author": "Coolgretchen",
  "timestamp": "2005-09-16T11:44:00+02:00",
  "raw_text": "Dieser sehr umfangreiche, allerdings mächtig zerfahren Artikel bedarf dringend eines Relaunches.",
  "reply_depth": 0,
  "status": "erledigt",
  "templates": ["Erledigt"],
  "contribution_id": "7b9c3a1e"
}
```

#### 3.4. Fehlerbehandlung & Logging
- **Netzwerkfehler:** Bis zu 3 Wiederholungen mit exponentieller Backoff.
- **HTTP-404:** Seite wird ignoriert (gilt als nicht vorhanden).
- **Parsing-Fehler:** Beitrag wird ausgelassen, ein Eintrag im Logfile erstellt (ohne Abbruch des gesamten Prozesses).
- **Zeitüberschreitung:** Timeout nach 30 Sekunden pro Request.

---

### 4. Nicht-Funktionale Anforderungen

| Anforderung | Beschreibung |
|-------------|--------------|
| **Performance** | Crawling und Parsing von bis zu 100 Diskussionsseiten in unter 5 Minuten (abhängig von Serverantwortzeiten). |
| **Speichernutzung** | Keine vollständige Speicherung aller Seiten im RAM; Streaming-basierte Ausgabe der JSONL-Datei. |
| **Wartbarkeit** | Das Skript ist modular aufgebaut: Crawler, Parser, Exporter sind austauschbare Komponenten. |
| **Konfigurierbarkeit** | Über eine zentrale Konfigurationsdatei (z. B. `config.yaml`) einstellbar: <br> - `delay_seconds`: Wartezeit zwischen Requests <br> - `user_agent`: String <br> - `output_dir`: Pfad für JSONL-Datei <br> - `max_retries`: Zahl der Wiederholungen |
| **Dokumentation** | Das Skript enthält einen ausführlichen Docstring und Kommentare für komplexe Stellen. Eine Kurzanleitung (`README.md`) wird beigelegt. |

---

### 5. Abgrenzung (Was nicht gemacht wird)

- **Keine Authentifizierung:** Es werden nur öffentlich zugängliche Seiten gelesen (keine geschützten Seiten oder API-Zugänge mit Token).
- **Keine Live-Verarbeitung von Änderungen:** Das Skript ist für einmalige oder geplante Batch-Läufe gedacht.
- **Keine Erkennung von Bearbeitungskonflikten oder gelöschten Beiträgen:** Diese sind im aktuellen Seiten-HTML nicht enthalten.
- **Keine Auswertung der Diskussionsinhalte:** Der `raw_text` bleibt unbearbeitet, es findet keine semantische Analyse statt.

---

### 6. Mögliche Erweiterungen (optional, für später)

- **Unterstützung anderer Wikimedia-Projekte** (Wikisource, Wikiversity) – die Seitenstruktur ist ähnlich.
- **Inkrementelles Parsing** – nur neue oder seit einem bestimmten Datum geänderte Seiten abrufen.
- **Export als CSV** zusätzlich zu JSONL.
- **Integration mit deiner „Loch-Matrix“** – direkter POST der extrahierten Beiträge an einen Webserver.

---

### 7. Beispielaufruf (späteres Skript)

```bash
python wikipedia_diskussion_parser.py --article "Bibliothek" --output "bibliothek_diskussionen.jsonl"
```

Oder mit URL:

```bash
python wikipedia_diskussion_parser.py --url "https://de.wikipedia.org/wiki/Diskussion:Bibliothek" --output "bibliothek_diskussionen.jsonl"
```

---

### 8. Nächste Schritte

1. **Freigabe dieses Pflichtenhefts** durch dich.
2. **Implementierung des Skripts** in Python mit den Bibliotheken `requests`, `beautifulsoup4`, `re`, `json`, `time`, `hashlib`.
3. **Test** anhand der Diskussionsseite `Diskussion:Bibliothek` (deine Beispiel-URL).
4. **Übergabe** des fertigen Skripts inkl. Kurzanleitung.
