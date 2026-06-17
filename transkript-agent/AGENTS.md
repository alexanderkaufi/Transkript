# Transkript-Projektanweisung fuer Codex

Dieses Projekt verarbeitet YouTube-Videos zu deutschen Markdown-Wissensdateien.
Arbeite nicht direkt blind mit KI los. Nutze zuerst den lokalen Agenten unter
`transkript-agent/transkript_agent.py`, um die festen Vorarbeiten automatisch zu
erledigen.

## Standardablauf bei einem neuen YouTube-Link

1. Projektordner verwenden:

   ```bash
   cd "/Users/alkaufimacbook/SynologyDrive/Informatik/Codex Projekte/Transkript"
   ```

2. Zuerst den lokalen Agenten ausfuehren:

   ```bash
   python3 transkript-agent/transkript_agent.py prepare "HIER_YOUTUBE_LINK_EINFUEGEN"
   ```

3. Wenn der Agent neue Dateien erzeugt, die erzeugte Handoff-Datei in
   `transkript-agent/drafts/` als Grundlage fuer den Redaktionsschritt nutzen.
   Die Handoff-Datei ist absichtlich kurz. Rohtranskript und Projektprompt
   sollen bei Bedarf direkt aus den genannten Dateien gelesen werden, nicht
   komplett in den Chat kopiert werden.

4. Fuer den eigentlichen Redaktionsschritt gelten weiterhin:

   - `prompt-uebersetzer-redaktor.md` beachten.
   - `erinnerungsdatei.md` erst nach Abschluss als Register ergaenzen.
   - Keine Duplikatpruefung ueber `erinnerungsdatei.md` durchfuehren.
   - Nicht kuerzen.
   - Keine Zusammenfassung und keine kompakte Wissensnotiz erstellen.
   - Die fertige Fassung soll moeglichst nah an der Originallaenge des
     Rohtranskripts bleiben; normalerweise mindestens etwa 80 % des
     urspruenglichen Inhaltsumfangs, abgesehen von Werbung, Sponsoring und
     echter Dopplung.
   - Vollstaendig ins Deutsche uebersetzen oder, falls bereits deutsch, sauber
     redigieren.
   - Beispiele, Nebengedanken, Schrittfolgen, Begruendungen, Einwaende und
     konkrete Details erhalten.
   - Eingebaute Werbung, Sponsorings und Verkaufsstellen entfernen.
   - Alle Zahlen, Prozentangaben, Jahre und Maßeinheiten konsequent in LaTeX-Syntax formatieren (z. B. $$22\text{. Jahr}$$, $$1\text{\%}$$, $$98\text{\%}$$).
   - Sauberes Markdown mit Cardlink, Iframe (mit ins Deutsche übersetztem `title`-Attribut), Inhaltsverzeichnis, Abschnitten, Zeitangaben am Abschnittsanfang und `[[# Inhaltsverzeichnis]]` nach jedem Abschnitt erzeugen.
   - Die fertige Markdown-Datei immer im Ordner `Fertige Transkripte/` speichern, nicht mehr im Projektstamm.
   - Vor dem Eintragen in `erinnerungsdatei.md` eine Selbstkontrolle durchführen: Prüfen, ob alle Kapitelüberschriften im Inhaltsverzeichnis gelistet sind, alle Backlinks existieren und alle Zählwerte/Zahlen in LaTeX formatiert sind.
   - Neue Eintraege in `erinnerungsdatei.md` mit dem Pfad `Fertige Transkripte/DATEINAME.md` erfassen.

## Wichtige Projektdateien

- `transkript-agent/transkript_agent.py`: lokaler Automations-Agent
- `scripts/youtube_transcript.py`: bestehendes Transkript-Download-Script
- `erinnerungsdatei.md`: Register fertiger Dateien, keine Duplikat-Sperre
- `prompt-uebersetzer-redaktor.md`: redaktioneller Zielprompt
- `transcripts/`: Rohtranskripte
- `Fertige Transkripte/`: finale redigierte Markdown-Dateien

## Was Python automatisieren soll

- YouTube-ID erkennen
- Rohtranskript holen
- Cardlink/Iframe/Metadaten vorbereiten
- Artikelskelett erzeugen
- KI-Handoff-Datei erzeugen

## Was KI nur bei Bedarf machen soll

Die KI soll erst fuer die eigentliche Redaktion genutzt werden: vollstaendig
uebersetzen, deutsche Transkripte lesbar redigieren, Abschnittsstruktur bauen,
Werbung entfernen und die finale Markdown-Datei schreiben.
Die finale Datei soll eine Langfassung nahe am Original bleiben, keine
Zusammenfassung.

## Tests fuer den Agenten

Nach Aenderungen am lokalen Agenten:

```bash
cd "/Users/alkaufimacbook/SynologyDrive/Informatik/Codex Projekte/Transkript/transkript-agent"
PYTHONPYCACHEPREFIX=/private/tmp/transkript-agent-pycache python3 -m unittest discover -s tests
```

## Kurzanweisung fuer neue Chats

Wenn der Nutzer einen neuen Chat startet und einen YouTube-Link gibt, zuerst im
Transkript-Projekt arbeiten und diese Datei beachten. Danach den lokalen
`transkript-agent` benutzen, bevor ein KI-Redaktionsschritt gestartet wird.
Halte den Chat-Kontext kurz: keine kompletten Rohtranskripte in den Chat
einfuegen, solange Codex die Dateien lokal lesen kann.

### Optimierter Workflow (Ein-Klick-Freigabe für den Nutzer):
Um die Anzahl der Freigaben und Enter-Klicks für den Nutzer auf genau **eine** zu reduzieren:
1. **Schritt 1 (Start):** Führe den `prepare`-Befehl aus (der Nutzer genehmigt diesen einmal im Terminal).
2. **Schritt 2 (Automatisches Auslesen):** Sobald der Befehl durchgelaufen ist, frage den Nutzer **nicht** nach Bestätigung, sondern lies sofort die erzeugten Entwurfsdateien und das Rohtranskript lokal aus.
3. **Schritt 3 (Redaktion):** Übersetze / redigiere das Transkript vollständig im selben Durchgang.
4. **Schritt 4 (Speichern):** Schreibe die fertig redigierte Datei direkt unter dem finalen deutschen H1-Titel (z. B. `Fertige Transkripte/Mein neuer Titel.md`) per Dateitool (`write_to_file`).
5. **Schritt 5 (Register):** Trage das fertige Transkript direkt per Dateitool (`replace_file_content` oder `multi_replace_file_content`) am Ende der Tabelle in `erinnerungsdatei.md` ein. So entfällt der separate `finalize`-Befehl im Terminal komplett.
