# YouTube-Transkript-Setup

Mit diesem kleinen Setup kannst du YouTube-Transkripte lokal als Markdown- oder Textdatei herunterladen.

## Datei

- Skript: `scripts/youtube_transcript.py`

## Voraussetzungen

- Python 3
- Oeffentliche Untertitel oder automatisch erzeugte Untertitel beim Video

## Beispiele

Verfuegbare Untertitelsprachen anzeigen:

```bash
python3 scripts/youtube_transcript.py "https://www.youtube.com/watch?v=YgX23uWEuOc" --list-langs
```

Markdown-Transkript mit Zeitstempeln erzeugen:

```bash
python3 scripts/youtube_transcript.py "https://www.youtube.com/watch?v=YgX23uWEuOc" --langs de,en,ru --format md --timestamps
```

Plain-Text-Transkript erzeugen:

```bash
python3 scripts/youtube_transcript.py "https://www.youtube.com/watch?v=YgX23uWEuOc" --format txt
```

## Ausgabe

Standardmaessig werden Dateien hier gespeichert:

- `transcripts/<VIDEO_ID>.transcript.md`
- `transcripts/<VIDEO_ID>.transcript.txt`

## Sammelworkflow fuer eine Themen-Datei

Wenn aus vielen Videos eine einzige Wissensdatei entstehen soll, empfiehlt sich dieser Ablauf:

1. Jedes Video zuerst als eigenes Transkript in `transcripts/` speichern.
2. Danach nur die inhaltlich relevanten Punkte in die Themen-Datei uebernehmen.
3. Bereits vorhandene Aussagen nicht erneut aufnehmen.
4. Nur neue, konkrete und brauchbare Details ergaenzen.
5. Bei Widerspruechen die Unterschiede kurz notieren statt die Aussagen zu vermischen.

Empfohlene Trennung:

- `transcripts/` enthaelt das Rohmaterial.
- Eine Datei wie `wie-man-buecher-schreibt.md` enthaelt nur die verdichteten Inhalte.

So bleibt die Sammeldatei kompakt und wiederholt sich nicht unnoetig.

## Hinweise

- Wenn kein deutsches Transkript verfuegbar ist, versucht das Skript automatisch die naechste Sprache aus `--langs`.
- Das Skript funktioniert ohne zusaetzliche Python-Pakete.
- Wenn YouTube keine oeffentlichen Untertitel bereitstellt, kann auch das Skript kein Transkript abrufen.
