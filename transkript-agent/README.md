# Transkript Agent

Lokaler Python-Agent fuer dein bestehendes Transkript-Projekt. Er automatisiert
die festen Schritte, bevor eine KI ueberhaupt gebraucht wird:

- YouTube-Video-ID aus URL erkennen
- vorhandenes `scripts/youtube_transcript.py` nutzen
- Rohtranskript mit Zeitstempeln erzeugen
- Metadaten/Cardlink/Iframe vorbereiten
- Artikelskelett und KI-Handoff-Datei schreiben

Der Agent ruft selbst keine OpenAI-API auf. Dadurch entstehen beim normalen
Preflight keine Tokenkosten. KI wird erst im naechsten Redaktionsschritt
gebraucht, wenn du den erzeugten Handoff wirklich verwenden willst.

## Projekt pruefen

```bash
cd "/Users/alkaufimacbook/SynologyDrive/Informatik/Codex Projekte/Transkript"
python3 transkript-agent/transkript_agent.py inspect
```

## Neues Video vorbereiten

```bash
python3 transkript-agent/transkript_agent.py prepare "https://www.youtube.com/watch?v=VIDEO_ID"
```

Ergebnis:

- Rohtranskript im bestehenden Projekt unter `transcripts/`
- Artikelskelett unter `transkript-agent/drafts/VIDEO_ID.skeleton.md`
- KI-Handoff unter `transkript-agent/drafts/VIDEO_ID.handoff.md`
- vorlaeufige Redaktionsdatei im Handoff unter `Fertige Transkripte/VIDEO_ID.md`

Der Agent verwendet fuer Arbeitsdateien bewusst die stabile Video-ID. Den
finalen deutschen Dateinamen kann er vor der Uebersetzung noch nicht wissen.

Die Handoff-Datei arbeitet standardmaessig im Kontextsparmodus: Sie enthaelt
nur Dateipfade und kurze Anweisungen, nicht den kompletten Prompt und nicht das
komplette Rohtranskript. Wenn du wirklich alles einbetten willst:

```bash
python3 transkript-agent/transkript_agent.py prepare "https://www.youtube.com/watch?v=VIDEO_ID" --embed-content
```

## Ohne Netzwerk testen

Wenn ein Rohtranskript schon existiert, kann der Agent ohne Download arbeiten:

```bash
python3 transkript-agent/transkript_agent.py prepare "VIDEO_ID" --no-fetch --skip-metadata
```

## Fertige Datei finalisieren

Wenn die Markdown-Fassung fertig redigiert ist und der deutsche Haupttitel als
erste H1-Zeile gesetzt wurde, benennt der Agent die Datei aus diesem Titel um
und ergaenzt das Register:

```bash
python3 transkript-agent/transkript_agent.py finalize "Fertige Transkripte/VIDEO_ID.md"
```

Der Finalisierungsschritt liest:

- den deutschen Titel aus der ersten `# Titel`-Zeile
- die Video-ID aus Cardlink, Iframe oder optional aus `--video-id`

Danach liegt die Datei z. B. als
`Fertige Transkripte/psychologie-von-menschen-die-zu-viel-denken-sechs-merkmale.md`
vor.

## Was Python uebernimmt

Python uebernimmt alles, was regelbasiert und wiederholbar ist: Pfade, IDs,
Transkriptabruf, Skelett, Prompt-Zusammenbau, finaler Dateiname aus deutschem
H1-Titel und Registereintrag.

## Was KI weiter machen sollte

Die eigentliche Redaktion bleibt optional KI-Arbeit: vollstaendig ins Deutsche
uebersetzen, deutsche Transkripte sauber redigieren, Werbung entfernen,
Abschnitte sinnvoll strukturieren und finale Markdown-Datei schreiben.
Fertige Markdown-Dateien gehoeren in den Projektordner `Fertige Transkripte/`.
Die fertige Datei soll eine Langfassung nahe an der Originallaenge bleiben,
nicht eine Zusammenfassung.

Das ist absichtlich getrennt, damit nicht jeder kleine Schritt Tokens kostet.
