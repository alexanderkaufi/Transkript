# Transkript-App-Plan

## Ziel

Eine lokale App fuer das Transkript-Projekt bauen, die moeglichst viel mit Code
erledigt und KI nur optional fuer die sprachliche Redaktion nutzt.

Die App soll YouTube-Links annehmen, Transkripte ueber mehrere Quellen suchen,
Rohtranskripte speichern, Text in sinnvolle Saetze und Abschnitte bringen,
Markdown im Projektformat erzeugen und fertige Dateien in
`Fertige Transkripte/` ablegen.

## Grundprinzipien

- Pipeline zuerst, KI nur als optionaler Transformationsschritt.
- Keine Duplikat-Sperre ueber `erinnerungsdatei.md`.
- `erinnerungsdatei.md` bleibt nur Register fertiger Dateien.
- Handoff-Dateien bleiben kurz und enthalten nur Pfade, keine kompletten
  Rohtranskripte.
- Standardausgabe bleibt eine Langfassung nahe am Original, keine
  Zusammenfassung.
- Jeder Pipeline-Schritt protokolliert, was versucht wurde und warum etwas
  geklappt oder nicht geklappt hat.

## Transkript-Fallbacks

Die App soll Transkriptquellen als Schleife behandeln. Wenn eine Quelle scheitert,
wird automatisch die naechste Quelle versucht.

Empfohlene Reihenfolge:

1. YouTube-Captions ueber `youtube-transcript-api`.
2. YouTube-Untertitel oder Auto-Captions ueber `yt-dlp`.
3. Audio mit `yt-dlp` herunterladen und lokal mit Whisper/OpenWhisper
   transkribieren.
4. Optional OpenAI Audio Transcription als Online-Fallback.
5. Optional Deepgram oder AssemblyAI als professionelle Speech-to-Text-API.

Jeder Versuch soll ein Ergebnisobjekt liefern:

```text
provider: youtube_transcript_api
status: success | failed | skipped
language: de | en | ...
reason: falls fehlgeschlagen
output_path: falls erfolgreich
```

## Textverarbeitung

Die App soll mehrere Strategien anbieten:

### Modus A: Deutsch redigieren

Wenn das Transkript bereits deutsch ist:

1. Rohsegmente zu Saetzen zusammenfuehren.
2. Saetze zu Abschnitten gruppieren.
3. Grammatik, Zeichensetzung und Lesbarkeit verbessern.
4. Keine inhaltliche Kuerzung.

### Modus B: Erst Satzbildung, dann Uebersetzung

Empfohlener Standard fuer fremdsprachige Auto-Captions:

1. Rohsegmente in der Originalsprache zu Saetzen formen.
2. Saetze zu Abschnittsbloecken gruppieren.
3. Abschnittsweise uebersetzen.
4. Danach deutsch redigieren.

Vorteil: Zeitstempel-Bruchstuecke werden zuerst stabilisiert, bevor uebersetzt
wird.

### Modus C: Erst Uebersetzung, dann Satzbildung

Fallback fuer einfache oder kurze Transkripte:

1. Rohtext abschnittsweise uebersetzen.
2. Deutsche Satzbildung und Absatzstruktur danach herstellen.

Vorteil: einfacher Ablauf. Nachteil: Fehler in Rohsegmenten koennen leichter
mituebersetzt werden.

### Modus D: Ohne KI

Nur Code:

1. Rohtranskript normalisieren.
2. Satzgrenzen mit Bibliothek erkennen.
3. Abschnitte nach Zeit oder Laenge gruppieren.
4. Markdown-Skelett fuellen.

Das Ergebnis ist weniger elegant, aber billig, lokal und kontrollierbar.

## Satzbildung ohne KI

Bibliotheken, die fuer Satzgrenzen infrage kommen:

- Python `pySBD`: regelbasierte Sentence Boundary Detection, mehrere Sprachen,
  gut fuer Abkuerzungen und robuste Satzgrenzen.
- Python `spaCy Sentencizer`: leichtgewichtig, regelbasiert, gut als schneller
  Standard.
- Python `NLTK Punkt`: klassischer Satz-Tokenizer, statistisch/regelbasiert,
  gut als Fallback.
- JavaScript `winkNLP`: Node.js-NLP mit Sentence Boundary Detection und
  `doc.sentences()`.

Empfohlener Start fuer diese App:

1. Python bleibt Hauptsprache.
2. Zuerst `pySBD` testen.
3. Danach spaCy Sentencizer als Fallback.
4. Eigene Reparaturregeln fuer typische YouTube-Caption-Probleme ergaenzen.

## Formatierung

Die App erzeugt das bestehende Projektformat:

- `cardlink`
- YouTube-`iframe`
- deutscher Titel
- Inhaltsverzeichnis
- thematische Abschnitte
- Zeitstempel nur am Abschnittsanfang
- `[[# Inhaltsverzeichnis]]` nach jedem Abschnitt
- finale Datei in `Fertige Transkripte/`

## Ausgabe

Die App soll mehrere Ausgaben anbieten:

- Markdown-Datei speichern.
- Markdown im Browser anzeigen.
- Datei als Download anbieten.
- Rohtranskript anzeigen.
- Handoff-Datei anzeigen.
- Fehlerbericht anzeigen.

## Qualitaetschecks

Vor dem finalen Speichern:

- Zieldatei existiert.
- Titel ist vorhanden.
- `cardlink` ist vorhanden.
- `iframe` ist vorhanden.
- Inhaltsverzeichnis ist vorhanden.
- Abschnitte haben Ruecklinks `[[# Inhaltsverzeichnis]]`.
- Finale Datei ist nicht zu kurz gegenueber dem Rohtranskript.
- Warnung, wenn die finale Datei unter ca. 80 % des erwarteten Umfangs liegt.
- Warnung, wenn offensichtliche Sponsoring- oder Werbephrasen noch enthalten
  sind.

## App-Oberflaeche

MVP-Seiten:

1. Neues Video
   - Link-Eingabe
   - Sprache/Modus
   - Kostenmodus: kostenlos, sparsam, beste Qualitaet
   - Button: vorbereiten

2. Pipeline-Status
   - aktueller Schritt
   - versuchte Provider
   - Fehlermeldungen
   - erzeugte Dateien

3. Draft-Ansicht
   - Metadaten
   - Rohtranskript-Link
   - Handoff-Link
   - Zielpfad

4. Editor/Vorschau
   - links Rohtranskript
   - rechts Markdown-Vorschau oder Texteditor
   - Qualitaetswarnungen

5. Export
   - in `Fertige Transkripte/` speichern
   - als Markdown-Datei herunterladen
   - `erinnerungsdatei.md` als Register ergaenzen

## Technische Architektur

Vorschlag fuer Python:

```text
app/
  main.py            # FastAPI oder Flask Web-App
  pipeline.py        # Ablaufsteuerung
  providers/
    youtube_api.py
    yt_dlp.py
    local_whisper.py
    openai_audio.py
    deepgram.py
  text/
    sentence_split.py
    sectioning.py
    cleanup.py
    quality.py
  markdown/
    render.py
    registry.py
  settings.py
```

Bestehendes `transkript-agent/transkript_agent.py` kann als CLI-Kern bleiben
oder schrittweise in `app/pipeline.py` aufgeteilt werden.

## Online-Dienste Nur Optional

Die App soll ohne API-Key starten koennen.

Optionale Schalter:

- OpenAI Audio Transcription fuer schwierige Videos.
- OpenAI Textmodell fuer redigierte Langfassung.
- DeepL fuer reine Uebersetzung.
- Deepgram/AssemblyAI fuer Speech-to-Text.

Wenn kein API-Key gesetzt ist, werden diese Schritte uebersprungen und im
Fehlerbericht als `skipped` markiert.

## Ausbauphasen

### Phase 1: Pipeline-Kern

- Aktuellen CLI-Agenten in kleinere Funktionen aufteilen.
- Provider-Ergebnisobjekte einfuehren.
- Kontextsparendes Handoff beibehalten.
- Satzsegmentierung mit `pySBD` als Testfunktion einbauen.

### Phase 2: Lokale Web-App

- FastAPI/Flask-App mit Formular fuer YouTube-Link.
- Statusseite fuer Pipeline-Schritte.
- Datei-Links fuer Rohtranskript, Handoff und Zielpfad.

### Phase 3: Satzbildung und Formatierung

- Rohsegmente zu Saetzen formen.
- Abschnitte nach Zeit, Laenge und Themenwechsel gruppieren.
- Markdown-Grundformat automatisch erzeugen.

### Phase 4: Qualitaetskontrolle

- Laengencheck gegen Kuerzung.
- Strukturcheck fuer Markdown.
- Warnungen vor finalem Speichern.

### Phase 5: Optionale KI

- Abschnittsweise Uebersetzung/Redaktion.
- Keine Kompletttranskripte in den Chat kopieren.
- Kostenmodus und Provider-Auswahl.

### Phase 6: Batch-Verarbeitung

- Mehrere Links nacheinander.
- Wiederaufnahme nach Fehlern.
- Ergebnisuebersicht.
