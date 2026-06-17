# Lokale Python-Umgebung

Wenn du das Setup auf einem anderen Rechner oder spaeter erneut einrichten willst:

## 1. Virtuelle Umgebung anlegen

```bash
python3 -m venv .venv
```

## 2. Abhaengigkeiten installieren

```bash
.venv/bin/pip install -r requirements.txt
```

## 3. Transkript abrufen

```bash
python3 scripts/youtube_transcript.py "https://www.youtube.com/watch?v=YgX23uWEuOc" --langs ru,de,en --format md --timestamps
```

Hinweis:

- Das Skript findet die installierten Pakete aus `.venv` automatisch.
- Du musst die virtuelle Umgebung dafuer nicht zwingend aktivieren.
