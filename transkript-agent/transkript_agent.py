#!/usr/bin/env python3
"""Unified workflow helper for the Transkript project.

This script consolidates all YouTube caption fetching, workflow preparation,
formatting validation, and LaTeX number auto-formatting into a single program.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import warnings
from urllib.parse import urlparse, parse_qs
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from json import JSONDecoder
from pathlib import Path
from typing import Any, Iterable

DEFAULT_SOURCE = Path(
    "/Users/alkaufimacbook/SynologyDrive/Informatik/Antigravity Projekte/Transkript"
)
WATCH_URL = "https://www.youtube.com/watch?v={video_id}"
FINISHED_DIR_NAME = "Fertige Transkripte"
ARTICLE_EXCLUDE_NAMES = {
    "erinnerungsdatei.md",
    "prompt-uebersetzer-redaktor.md",
    "setup-python-venv.md",
    "youtube-transkript-setup.md",
    "AGENTS.md",
}
DEFAULT_ACCEPT_LANGUAGE = "de,en-US,en,ru"


class AgentError(RuntimeError):
    """Raised when the workflow cannot continue."""


def add_workspace_site_packages() -> None:
    """Allow using packages from the project's local .venv without activation."""
    root = DEFAULT_SOURCE
    for site_packages in root.glob(".venv/lib/python*/site-packages"):
        path = str(site_packages)
        if path not in sys.path:
            sys.path.insert(0, path)


add_workspace_site_packages()
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 v2 only supports OpenSSL 1\.1\.1\+",
)

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except Exception:
    YouTubeTranscriptApi = None


@dataclass(frozen=True)
class VideoMetadata:
    video_id: str
    url: str
    title: str
    description: str
    host: str
    favicon: str
    image: str


@dataclass
class CaptionTrack:
    language_code: str
    language_name: str
    base_url: str
    kind: str
    is_generated: bool


@dataclass
class TranscriptSegment:
    start: float
    duration: float
    text: str


@dataclass(frozen=True)
class ProcessedVideo:
    video_id: str
    title: str
    filename: str


# ==========================================
# YouTube Caption Fetching Engine (Merged)
# ==========================================

def http_get(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": DEFAULT_ACCEPT_LANGUAGE,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")
    except urllib.error.URLError as exc:
        raise AgentError(f"Netzwerkfehler beim Abrufen von {url}: {exc}") from exc


def extract_json_blob(page: str, marker: str) -> dict:
    idx = page.find(marker)
    if idx == -1:
        raise AgentError(f"Marker nicht gefunden: {marker}")

    start = page.find("{", idx)
    if start == -1:
        raise AgentError(f"JSON-Start nach Marker nicht gefunden: {marker}")

    decoder = JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(page[start:])
        return obj
    except json.JSONDecodeError as exc:
        raise AgentError(f"Fehler beim Parsen der YouTube-JSON-Daten: {exc}") from exc


def load_player_response(video_id: str) -> dict:
    page = http_get(WATCH_URL.format(video_id=video_id))
    markers = [
        "var ytInitialPlayerResponse = ",
        "ytInitialPlayerResponse = ",
        "window['ytInitialPlayerResponse'] = ",
        'window["ytInitialPlayerResponse"] = ',
    ]
    for marker in markers:
        try:
            return extract_json_blob(page, marker)
        except AgentError:
            continue
    raise AgentError(
        "Konnte die Player-Daten nicht aus der YouTube-Seite extrahieren. "
        "Moeglicherweise gibt es keine oeffentlichen Untertitel oder YouTube "
        "hat die Seitenstruktur geaendert."
    )


def parse_caption_tracks(player_response: dict) -> list[CaptionTrack]:
    tracklist = (
        player_response.get("captions", {})
        .get("playerCaptionsTracklistRenderer", {})
    )
    caption_tracks = tracklist.get("captionTracks", [])
    result: list[CaptionTrack] = []

    for track in caption_tracks:
        name = track.get("name", {}).get("simpleText")
        if not name:
            runs = track.get("name", {}).get("runs", [])
            name = "".join(run.get("text", "") for run in runs).strip()
        kind = track.get("kind", "")
        result.append(
            CaptionTrack(
                language_code=track.get("languageCode", ""),
                language_name=name or track.get("languageCode", "unbekannt"),
                base_url=track.get("baseUrl", ""),
                kind=kind,
                is_generated=(kind == "asr"),
            )
        )
    return result


def choose_track(tracks: Iterable[CaptionTrack], preferred_langs: list[str]) -> CaptionTrack:
    tracks = list(tracks)
    if not tracks:
        raise AgentError("Dieses Video hat keine oeffentlich verfuegbaren Untertitel.")

    normalized = [lang.strip().lower() for lang in preferred_langs if lang.strip()]
    for preferred in normalized:
        for track in tracks:
            if track.language_code.lower() == preferred and not track.is_generated:
                return track
        for track in tracks:
            if track.language_code.lower() == preferred:
                return track

    for track in tracks:
        if not track.is_generated:
            return track
    return tracks[0]


def fetch_segments_with_api(
    video_id: str,
    preferred_langs: list[str],
) -> tuple[CaptionTrack, list[TranscriptSegment]]:
    if YouTubeTranscriptApi is None:
        raise AgentError(
            "Die Bibliothek 'youtube-transcript-api' ist nicht installiert."
        )

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=preferred_langs)
    except Exception as exc:
        raise AgentError(f"Transcript-API Fehler: {exc}") from exc

    track = CaptionTrack(
        language_code=fetched.language_code,
        language_name=fetched.language,
        base_url="",
        kind="asr" if fetched.is_generated else "",
        is_generated=fetched.is_generated,
    )
    segments = [
        TranscriptSegment(
            start=snippet["start"],
            duration=snippet["duration"],
            text=normalize_caption_text(snippet["text"]),
        )
        for snippet in fetched
        if normalize_caption_text(snippet["text"])
    ]
    return track, segments


def fetch_segments(track: CaptionTrack) -> list[TranscriptSegment]:
    xml_payload = http_get(track.base_url + "&fmt=srv3")
    try:
        root = ET.fromstring(xml_payload)
    except ET.ParseError as exc:
        raise AgentError(f"Untertitel-XML konnte nicht geparst werden: {exc}") from exc

    segments: list[TranscriptSegment] = []
    for text_node in root.findall(".//text"):
        start = float(text_node.attrib.get("start", "0") or 0)
        duration = float(text_node.attrib.get("dur", "0") or 0)
        raw_text = "".join(text_node.itertext())
        clean_text = normalize_caption_text(raw_text)
        if clean_text:
            segments.append(
                TranscriptSegment(
                    start=start,
                    duration=duration,
                    text=clean_text,
                )
            )
    return segments


def normalize_caption_text(value: str) -> str:
    value = html.unescape(value)
    value = value.replace("\n", " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def format_timestamp(seconds: float) -> str:
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def is_potential_ad(text: str) -> bool:
    ad_keywords = [
        # German
        r"\bsponsor", r"\bgesponsert", r"\bwerbung\b", r"\brabatt", r"\bpromocode", 
        r"\bpromo-code", r"\blink in der beschreibung\b", r"\bpartner\b", r"\bunterstützt durch",
        # English
        r"\bsponsored\b", r"\bad\b", r"\bdiscount", r"\bpromo code\b",
        r"\blink in the description\b", r"\badvertisement\b", r"\bpatreon\b", r"\bsupport the channel\b",
        # Russian
        r"\bспонсор", r"\bреклам", r"\bскидк", r"\bпромокод\b", r"\bссылка в описании\b", r"\bподдержать канал\b",
        # Common VPN Brands
        r"\bnordvpn\b", r"\bexpressvpn\b", r"\bsurfshark\b"
    ]
    text_lower = text.lower()
    for kw in ad_keywords:
        if re.search(kw, text_lower):
            return True
    return False


def render_markdown_transcript(
    video_id: str,
    video_url: str,
    track: CaptionTrack,
    segments: list[TranscriptSegment],
    include_timestamps: bool,
) -> str:
    lines = [
        f"# YouTube-Transkript: {video_id}",
        "",
        f"- Quelle: {video_url}",
        f"- Sprache: {track.language_name} (`{track.language_code}`)",
        f"- Typ: {'automatisch erzeugt' if track.is_generated else 'manuell'}",
        "",
        "## Transkript",
        "",
    ]
    for segment in segments:
        text = segment.text
        if is_potential_ad(text):
            text = f"⚠️ [WERBUNG?] {text}"
        lines.append(f"**{format_timestamp(segment.start)}** {text}")
        lines.append("")
    return "\n".join(lines)


# ==========================================
# Original Workflow Manager Engine
# ==========================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automatisiert Vorarbeit und Post-Processing fuer das Transkript-Projekt."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help="Pfad zum bestehenden Transkript-Projekt.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Projekt pruefen und eine kurze Bestandsaufnahme ausgeben.",
    )
    inspect_parser.set_defaults(func=cmd_inspect)

    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Video pruefen, Transkript holen und Redaktionsdateien erzeugen.",
    )
    prepare_parser.add_argument("video", help="YouTube-URL oder Video-ID")
    prepare_parser.add_argument(
        "--langs",
        default="de,en,ru",
        help="Bevorzugte Transkriptsprachen, z. B. de,en,ru.",
    )
    prepare_parser.add_argument(
        "--drafts",
        type=Path,
        default=None,
        help="Zielordner fuer Handoff-Dateien. Standard: <source>/transkript-agent/drafts.",
    )
    prepare_parser.add_argument(
        "--transcript-output",
        type=Path,
        default=None,
        help="Zielordner fuer Rohtranskripte. Standard: <source>/transcripts.",
    )
    prepare_parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Kein Transkript herunterladen; nur vorhandene Dateien verwenden.",
    )
    prepare_parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="yt-dlp-Metadaten nicht abrufen und sichere Defaults nutzen.",
    )
    prepare_parser.add_argument(
        "--embed-content",
        action="store_true",
        help="Projektprompt und Rohtranskript vollstaendig in die Handoff-Datei schreiben.",
    )
    prepare_parser.add_argument(
        "--chunk-size",
        type=int,
        default=900,
        help="Größe der Chunks in Sekunden für lange Videos (Standard: 900s / 15 Min).",
    )
    prepare_parser.add_argument(
        "--chunk-threshold",
        type=int,
        default=2700,
        help="Schwelle in Sekunden, ab der ein Video aufgeteilt wird (Standard: 2700s / 45 Min).",
    )
    prepare_parser.set_defaults(func=cmd_prepare)

    finalize_parser = subparsers.add_parser(
        "finalize",
        help=(
            "Fertige Markdown-Datei aus deutschem H1-Titel umbenennen und "
            "erinnerungsdatei.md ergaenzen."
        ),
    )
    finalize_parser.add_argument(
        "file",
        type=Path,
        help=(
            "Pfad zur fertig redigierten Markdown-Datei, z. B. "
            "Fertige Transkripte/VIDEO_ID.md."
        ),
    )
    finalize_parser.add_argument(
        "--video-id",
        default=None,
        help="YouTube-Video-ID, falls sie nicht aus der Datei gelesen werden kann.",
    )
    finalize_parser.set_defaults(func=cmd_finalize)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Fertige Markdown-Datei auf Formatierungsregeln (Backlinks, LaTeX-Zahlen) prüfen.",
    )
    validate_parser.add_argument(
        "file",
        type=Path,
        help="Pfad zur Markdown-Datei.",
    )
    validate_parser.set_defaults(func=cmd_validate)

    latexify_parser = subparsers.add_parser(
        "latexify",
        help="Zahlen und Prozentangaben in einer fertigen Markdown-Datei automatisch in LaTeX formatieren.",
    )
    latexify_parser.add_argument(
        "file",
        type=Path,
        help="Pfad zur Markdown-Datei.",
    )
    latexify_parser.set_defaults(func=cmd_latexify)

    merge_parser = subparsers.add_parser(
        "merge",
        help="Abschnitte (Parts) eines aufgeteilten Videos zu einer fertigen Markdown-Datei zusammenführen.",
    )
    merge_parser.add_argument("video", help="YouTube-URL oder Video-ID des aufgeteilten Videos.")
    merge_parser.set_defaults(func=cmd_merge)

    return parser.parse_args()


def extract_video_id(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[\w-]{11}", value):
        return value

    parsed = urlparse(value)
    host = parsed.netloc.lower()
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.strip("/").split("/")[0]
        if re.fullmatch(r"[\w-]{11}", candidate):
            return candidate

    if "youtube.com" in host or "youtube-nocookie.com" in host:
        if parsed.path == "/watch":
            candidate = parse_qs(parsed.query).get("v", [""])[0]
            if re.fullmatch(r"[\w-]{11}", candidate):
                return candidate
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live"}:
            candidate = parts[1]
            if re.fullmatch(r"[\w-]{11}", candidate):
                return candidate

    raise AgentError(f"Ungueltige YouTube-URL oder Video-ID: {value}")


def parse_transcript_file(path: Path) -> list[tuple[float, str]]:
    if not path.exists():
        return []
    segments = []
    pattern = re.compile(r"^\*\*\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*\*\*(.*)$")
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        match = pattern.match(line)
        if match:
            g1, g2, g3 = match.group(1), match.group(2), match.group(3)
            if g3 is not None:
                seconds = int(g1) * 3600 + int(g2) * 60 + int(g3)
            else:
                seconds = int(g1) * 60 + int(g2)
            segments.append((float(seconds), line))
    return segments


def parse_memory_file(path: Path) -> dict[str, ProcessedVideo]:
    if not path.exists():
        return {}

    processed: dict[str, ProcessedVideo] = {}
    row_pattern = re.compile(
        r"^\|\s*`(?P<id>[\w-]{11})`\s*\|\s*(?P<title>.*?)\s*\|\s*`(?P<file>[^`]+)`\s*\|"
    )
    for line in path.read_text(encoding="utf-8").splitlines():
        match = row_pattern.match(line)
        if not match:
            continue
        processed[match.group("id")] = ProcessedVideo(
            video_id=match.group("id"),
            title=match.group("title").strip(),
            filename=match.group("file").strip(),
        )
    return processed


def slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "", value)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" .")
    return cleaned or fallback


def ensure_source(source: Path) -> None:
    required = [
        source / "erinnerungsdatei.md",
        source / "prompt-uebersetzer-redaktor.md",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        details = "\n".join(f"- {path}" for path in missing)
        raise AgentError(f"Transkript-Projekt unvollstaendig:\n{details}")


def load_prompt(source: Path) -> str:
    return (source / "prompt-uebersetzer-redaktor.md").read_text(encoding="utf-8")


def transcript_path(output_dir: Path, video_id: str) -> Path:
    return output_dir / f"{video_id}.transcript.md"


def finished_transcript_path(source: Path, title: str, video_id: str) -> Path:
    return source / FINISHED_DIR_NAME / f"{slugify(title, video_id)}.md"


def working_transcript_path(source: Path, video_id: str) -> Path:
    return source / FINISHED_DIR_NAME / f"{video_id}.md"


def fetch_transcript(
    source: Path,
    video: str,
    langs: str,
    output_dir: Path,
) -> Path:
    video_id = extract_video_id(video)
    video_url = WATCH_URL.format(video_id=video_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    preferred_langs = [lang.strip() for lang in langs.split(",") if lang.strip()]
    try:
        if YouTubeTranscriptApi is not None:
            track, segments = fetch_segments_with_api(video_id, preferred_langs)
        else:
            player_response = load_player_response(video_id)
            tracks = parse_caption_tracks(player_response)
            track = choose_track(tracks, preferred_langs)
            segments = fetch_segments(track)

        if not segments:
            raise AgentError("Es wurden keine Untertitel-Segmente gefunden.")

        content = render_markdown_transcript(
            video_id=video_id,
            video_url=video_url,
            track=track,
            segments=segments,
            include_timestamps=True,
        )

        output_path = output_dir / f"{video_id}.transcript.md"
        output_path.write_text(content, encoding="utf-8")
        return output_path
    except Exception as exc:
        raise AgentError(f"Transkript konnte nicht geholt werden: {exc}")


def safe_description(value: str, limit: int = 260) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def default_metadata(video_id: str) -> VideoMetadata:
    url = WATCH_URL.format(video_id=video_id)
    return VideoMetadata(
        video_id=video_id,
        url=url,
        title=f"YouTube-Video {video_id}",
        description="",
        host="www.youtube.com",
        favicon="https://www.youtube.com/favicon.ico",
        image=f"https://i.ytimg.com/vi_webp/{video_id}/maxresdefault.webp",
    )


def load_metadata(source: Path, video_url: str, skip_metadata: bool) -> VideoMetadata:
    video_id = extract_video_id(video_url)
    if skip_metadata:
        return default_metadata(video_id)

    try:
        player_response = load_player_response(video_id)
        details = player_response.get("videoDetails", {})
        title = details.get("title", f"YouTube-Video {video_id}")
        desc = details.get("shortDescription", "")
        return VideoMetadata(
            video_id=video_id,
            url=video_url,
            title=title,
            description=safe_description(desc),
            host="www.youtube.com",
            favicon="https://www.youtube.com/favicon.ico",
            image=f"https://i.ytimg.com/vi_webp/{video_id}/maxresdefault.webp",
        )
    except Exception:
        return default_metadata(video_id)


def render_cardlink(metadata: VideoMetadata, title: str) -> str:
    escaped_title = title.replace('"', '\\"')
    escaped_description = metadata.description.replace('"', '\\"')
    return (
        "```cardlink\n"
        f"url: {metadata.url}\n"
        f'title: "{escaped_title}"\n'
        f'description: "{escaped_description}"\n'
        f"host: {metadata.host}\n"
        f"favicon: {metadata.favicon}\n"
        f"image: {metadata.image}\n"
        "```"
    )


def render_skeleton(metadata: VideoMetadata) -> str:
    lines = [
        render_cardlink(metadata, metadata.title),
        "",
        (
            f'<iframe title="{metadata.title}" '
            f'src="https://www.youtube.com/embed/{metadata.video_id}" '
            'height="113" width="200" style="aspect-ratio: 1.76991 / 1; '
            'width: 100%; height: 100%;" allowfullscreen="" '
            'allow="fullscreen"></iframe>'
        ),
        "",
        f"# {metadata.title}",
        "",
        "### Inhaltsverzeichnis",
        "",
        "1. [[#Einfuehrung]]",
        "",
        "---",
        "",
        "### Einfuehrung",
        "",
        "**00:00**",
        "",
        "TODO: Hier beginnt die redigierte oder uebersetzte Fassung.",
        "",
        "[[# Inhaltsverzeichnis]]",
        "",
    ]
    return "\n".join(lines)


def render_handoff(
    source: Path,
    metadata: VideoMetadata,
    transcript: Path,
    skeleton: Path,
    working_output: Path,
    embed_content: bool = False,
) -> str:
    rel_prompt = relative_project_path(source, source / "prompt-uebersetzer-redaktor.md")
    rel_transcript = relative_project_path(source, transcript)
    rel_skeleton = relative_project_path(source, skeleton)
    rel_working = relative_project_path(source, working_output)

    lines = [
        f"# Redaktions-Handoff: {metadata.title}",
        "",
        "## Status",
        "",
        f"- Video-ID: `{metadata.video_id}`",
        f"- Quelle: {metadata.url}",
        f"- Projektprompt: `{rel_prompt}`",
        f"- Rohtranskript: `{rel_transcript}`",
        f"- Artikelskelett: `{rel_skeleton}`",
        f"- Vorlaeufige Redaktionsdatei: `{rel_working}`",
        "- Finale Zieldatei: wird nach der Uebersetzung aus dem deutschen H1-Titel abgeleitet.",
        "",
        "## Naechster KI-Schritt",
        "",
        "Lies den Projektprompt und das Rohtranskript direkt aus den oben genannten",
        "Dateien. Ziel ist die vollstaendige deutsche Markdown-Fassung im Stil der",
        "bestehenden Dateien.",
        "Erstelle keine Zusammenfassung. Die fertige Fassung soll moeglichst",
        "nah an der Originallaenge des Rohtranskripts bleiben.",
        "Ersetze den H1-Titel im Skelett durch den endgueltigen deutschen Titel.",
        f"Speichere die fertig redigierte Datei zuerst unter `{rel_working}`.",
        "",
        "Wenn die Datei fertig ist, fuehre danach aus:",
        "",
        f'`python3 transkript-agent/transkript_agent.py finalize "{rel_working}"`',
        "",
        "Der Finalisierungsschritt liest den deutschen H1-Titel, benennt die Datei",
        "im Ordner `Fertige Transkripte/` passend um und ergaenzt `erinnerungsdatei.md`.",
        "",
    ]

    if embed_content:
        lines.extend(
            [
                "## Inhalt fuer Inline-Kompaktierung",
                "",
                "### Projekt-Prompt",
                "",
                "```markdown",
                load_prompt(source),
                "```",
                "",
                "### Rohtranskript",
                "",
                "```markdown",
                transcript.read_text(encoding="utf-8"),
                "```",
                "",
            ]
        )
    else:
        lines.extend(
            [
                "## Kontextsparmodus",
                "",
                "Diese Handoff-Datei enthaelt absichtlich nicht den kompletten Prompt und",
                "nicht das komplette Transkript. Das haelt neue Codex-Chats klein und",
                "vermeidet unnoetige Kontext-Kompaktierungen.",
                "",
            ]
        )

    return "\n".join(lines)


def relative_project_path(source: Path, path: Path) -> str:
    path = path.expanduser().resolve()
    source = source.expanduser().resolve()
    try:
        return str(path.relative_to(source))
    except ValueError:
        return str(path)


def resolve_project_path(source: Path, path: Path) -> Path:
    path = path.expanduser()
    if path.is_absolute():
        return path
    return source / path


def extract_markdown_h1(content: str) -> str:
    for line in content.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return match.group(1).strip()
    raise AgentError("Keine H1-Ueberschrift (# Titel) im Dokument gefunden.")


def extract_video_id_from_text(content: str) -> str | None:
    match = re.search(r"youtube\.com/embed/([\w-]{11})", content)
    if match:
        return match.group(1)
    match = re.search(r"youtube\.com/watch\?v=([\w-]{11})", content)
    if match:
        return match.group(1)
    return None


def escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def memory_table_lines() -> list[str]:
    return [
        "| Video-ID | Name der Wissensdatei | Datei |",
        "|---|---|---|",
    ]


def ensure_memory_table(lines: list[str]) -> list[str]:
    first_row_index = -1
    for index, line in enumerate(lines):
        if line.startswith("|") and "Video-ID" in line:
            first_row_index = index
            break

    if first_row_index == -1:
        prefix = [line for line in lines if line.strip()]
        if prefix and prefix[-1].startswith("#"):
            prefix.append("")
        return [*prefix, "", *memory_table_lines()]

    table_lines = lines[first_row_index:]
    if len(table_lines) < 2 or not table_lines[1].startswith("|---"):
        prefix = lines[:first_row_index]
        while prefix and prefix[-1] == "":
            prefix.pop()
        return [*prefix, "", *memory_table_lines(), *lines[first_row_index:]]

    while lines and lines[-1] == "":
        lines.pop()
    if lines:
        lines.append("")
    lines.extend(memory_table_lines())
    return lines


def upsert_memory_entry(source: Path, video_id: str, title: str, final_path: Path) -> None:
    memory = source / "erinnerungsdatei.md"
    relative_file = relative_project_path(source, final_path)
    new_row = (
        f"| `{video_id}` | {escape_table_cell(title)} | "
        f"`{escape_table_cell(relative_file)}` |"
    )

    if not memory.exists():
        memory.write_text(
            "\n".join(
                [
                    "# Erinnerungsdatei fuer YouTube-Transkriptarbeit",
                    "",
                    *memory_table_lines(),
                    new_row,
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return

    lines = ensure_memory_table(memory.read_text(encoding="utf-8").splitlines())
    row_pattern = re.compile(rf"^\|\s*`{re.escape(video_id)}`\s*\|")
    for index, line in enumerate(lines):
        if row_pattern.match(line):
            lines[index] = new_row
            memory.write_text("\n".join(lines) + "\n", encoding="utf-8")
            return

    while lines and lines[-1] == "":
        lines.pop()

    lines.append(new_row)
    memory.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_markdown_file(path: Path) -> list[str]:
    errors = []
    content = path.read_text(encoding="utf-8")
    
    # 1. H1 title check
    h1_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if not h1_match:
        errors.append("Kein H1-Titel (# Titel) gefunden.")
    
    # 2. Cardlink check
    if "```cardlink" not in content:
        errors.append("Kein ```cardlink Block gefunden.")
        
    # 3. Iframe check
    if "<iframe " not in content:
        errors.append("Kein <iframe>-Tag fuer das Video gefunden.")
        
    # 4. Inhaltsverzeichnis check
    toc_match = re.search(r"### Inhaltsverzeichnis", content)
    if not toc_match:
        errors.append("Kein '### Inhaltsverzeichnis' Header gefunden.")
        
    # 5. Check H3 chapters & Inhaltsverzeichnis links & backlinks
    chapters = re.findall(r"^###\s+(.+)$", content, re.MULTILINE)
    chapters = [c.strip() for c in chapters if c.lower().strip() != "inhaltsverzeichnis"]
    
    if not chapters:
        errors.append("Keine Kapitelüberschriften (### Kapitelname) gefunden.")
        
    # 5a. Mismatched bracket check
    for line_no, line in enumerate(content.splitlines(), start=1):
        open_count = line.count("[[")
        close_count = line.count("]]")
        if open_count != close_count:
            errors.append(f"Zeile {line_no}: Unvollständiger Obsidian-Link (Klammern stimmen nicht überein: '[[' vs ']]').")

    # 5b. Section-by-section backlink check
    sections = content.split("### ")
    for section in sections[1:]:
        lines = section.splitlines()
        if not lines:
            continue
        header = lines[0].strip()
        if header.lower() == "inhaltsverzeichnis":
            continue
        if "[[# Inhaltsverzeichnis]]" not in section:
            errors.append(f"Kapitel \"{header}\" hat keinen Backlink zu '[[# Inhaltsverzeichnis]]'.")

    # 5c. TOC links vs actual chapters check
    if toc_match:
        toc_start = content.find("### Inhaltsverzeichnis")
        rest = content[toc_start:]
        next_h3 = rest.find("### ", len("### Inhaltsverzeichnis"))
        next_div = rest.find("---")
        end_idx = len(rest)
        if next_h3 != -1 and next_div != -1:
            end_idx = min(next_h3, next_div)
        elif next_h3 != -1:
            end_idx = next_h3
        elif next_div != -1:
            end_idx = next_div
            
        toc_block = rest[:end_idx]
        toc_links = re.findall(r"\[\[#\s*([^\]]+)\]\]", toc_block)
        toc_links = [l.strip() for l in toc_links if l.strip() != "Inhaltsverzeichnis"]
        
        for ch in chapters:
            if ch not in toc_links:
                errors.append(f"Kapitel \"{ch}\" fehlt im Inhaltsverzeichnis.")
        for lk in toc_links:
            if lk not in chapters:
                errors.append(f"Inhaltsverzeichnis verweist auf nicht existierendes Kapitel: \"{lk}\".")
        
    # 6. Check for unformatted percentages/numbers outside of LaTeX
    clean_content = re.sub(r"```cardlink.*?```", "", content, flags=re.DOTALL)
    clean_content = re.sub(r"<[^>]+>", "", clean_content)
    
    parts = clean_content.split("$$")
    for i, part in enumerate(parts):
        if i % 2 == 0:  # Outside LaTeX math blocks
            unformatted_pct = re.findall(r"\b\d+\s*%", part)
            if unformatted_pct:
                errors.append(
                    f"Unformatierte Prozentangabe(n) außerhalb von LaTeX gefunden: {unformatted_pct}. "
                    "Bitte als LaTeX formatieren (z. B. $$86\\text{\\%}$$)."
                )
            unformatted_unit = re.findall(r"\b\d+\s*(?:Jahre|Jahren|Wochen|Monate|Tage|Stunden|Minuten|Ohm|Uhr|Milliarden|Millionen)\b", part)
            if unformatted_unit:
                errors.append(
                    f"Unformatierte Zahl(en) mit Einheiten/Zeiträumen außerhalb von LaTeX gefunden: {unformatted_unit}. "
                    "Bitte als LaTeX formatieren (z. B. $$2000\\text{ Jahren}$$)."
                )
                
    return errors


def auto_latexify_text(content: str) -> str:
    parts = content.split("$$")
    for i in range(len(parts)):
        if i % 2 == 0:  # Outside LaTeX math blocks
            part = parts[i]
            
            # Formate Prozentsätze (z.B. "86%" oder "86 %" -> "$$86\text{\%}$$")
            part = re.sub(r'\b(\d+)\s*%', r'$$\1\\text{\%}$$', part)
            
            # Formate Zahlen mit Einheiten (z.B. "2 Jahre" -> "$$2\text{ Jahre}$$")
            unit_pattern = r'\b(\d+)\s*(Jahre|Jahren|Wochen|Monate|Tage|Stunden|Minuten|Ohm|Uhr|Milliarden|Millionen|Prozent|Dinge|Züge|Teile)\b'
            part = re.sub(unit_pattern, r'$$\1\\text{ \2}$$', part)
            
            parts[i] = part
            
    return "$$".join(parts)


def cleanup_processed_transcripts(source: Path, transcript_dir: Path, drafts_dir: Path, exclude_id: str | None = None) -> None:
    memory_file = source / "erinnerungsdatei.md"
    if not memory_file.exists():
        return
    
    processed_ids = parse_memory_file(memory_file)
    if not processed_ids:
        return
        
    # Clean transcripts
    if transcript_dir.exists():
        for file in transcript_dir.glob("*.transcript.md"):
            video_id = file.name.split(".")[0]
            if video_id in processed_ids and video_id != exclude_id:
                try:
                    file.unlink()
                    print(f"🧹 Bereinigung: Veraltetes Rohtranskript {file.name} gelöscht (bereits registriert).")
                except Exception:
                    pass
                    
    # Clean drafts
    if drafts_dir.exists():
        for file in drafts_dir.glob("*"):
            if file.is_file():
                video_id = file.name.split(".")[0]
                if video_id in processed_ids and video_id != exclude_id:
                    try:
                        file.unlink()
                        print(f"🧹 Bereinigung: Veralteter Entwurf {file.name} gelöscht.")
                    except Exception:
                        pass


def cmd_inspect(args: argparse.Namespace) -> int:
    source = args.source.expanduser()
    ensure_source(source)
    
    transcript_dir = source / "transcripts"
    drafts_dir = source / "transkript-agent" / "drafts"
    cleanup_processed_transcripts(source, transcript_dir, drafts_dir)
    
    processed = parse_memory_file(source / "erinnerungsdatei.md")
    transcripts = list(transcript_dir.glob("*.transcript.md"))
    finished_dir = source / FINISHED_DIR_NAME
    finished_articles = list(finished_dir.glob("*.md")) if finished_dir.exists() else []
    legacy_articles = [
        path for path in source.glob("*.md") if path.name not in ARTICLE_EXCLUDE_NAMES
    ]

    print(f"Projekt: {source}")
    print(f"Eintraege in Erinnerungsdatei: {len(processed)}")
    print(f"Rohtranskripte: {len(transcripts)}")
    print(f"Fertige Transkripte: {len(finished_articles)}")
    print(f"Artikel im Projektstamm (alt): {len(legacy_articles)}")
    print(f"Zielordner fuer neue fertige Dateien: {finished_dir}")
    print(f"Transcript-Engine: Integriert")
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    source = args.source.expanduser()
    ensure_source(source)
    
    video_id = extract_video_id(args.video)
    video_url = WATCH_URL.format(video_id=video_id)
    
    transcript_dir = args.transcript_output or (source / "transcripts")
    drafts_dir = (
        args.drafts.expanduser()
        if args.drafts
        else source / "transkript-agent" / "drafts"
    )
    
    cleanup_processed_transcripts(source, transcript_dir, drafts_dir, exclude_id=video_id)

    transcript = transcript_path(transcript_dir, video_id)
    if not transcript.exists():
        if args.no_fetch:
            raise AgentError(
                f"Kein vorhandenes Transkript gefunden: {transcript}\n"
                "Ohne --no-fetch kann der Agent es herunterladen."
            )
        transcript = fetch_transcript(source, video_url, args.langs, transcript_dir)

    metadata = load_metadata(source, video_url, args.skip_metadata)
    
    segments = parse_transcript_file(transcript)
    chunk_threshold = getattr(args, "chunk_threshold", 2700)
    chunk_size = getattr(args, "chunk_size", 900)
    
    is_long_video = False
    if segments:
        duration = segments[-1][0]
        if duration > chunk_threshold:
            is_long_video = True
            
    if is_long_video:
        chunks: dict[int, list[str]] = {}
        for start_sec, line in segments:
            idx = int(start_sec // chunk_size) + 1
            chunks.setdefault(idx, []).append(line)
            
        main_lines = transcript.read_text(encoding="utf-8").splitlines()
        header_lines = []
        for line in main_lines:
            header_lines.append(line)
            if line.strip() == "## Transkript":
                break
                
        print(f"Video ist länger als {chunk_threshold // 60} Minuten. Automatisches Chunking aktiviert:")
        print(f"Erzeuge {len(chunks)} Teile (je {chunk_size // 60} Minuten)...")
        
        for idx in sorted(chunks.keys()):
            part_title = f"{metadata.title} (Teil {idx})"
            part_metadata = VideoMetadata(
                video_id=metadata.video_id,
                url=metadata.url,
                title=part_title,
                description=metadata.description,
                host=metadata.host,
                favicon=metadata.favicon,
                image=metadata.image
            )
            
            part_transcript = transcript_dir / f"{video_id}.part{idx}.transcript.md"
            part_header_lines = list(header_lines)
            if part_header_lines and part_header_lines[0].startswith("# "):
                part_header_lines[0] = f"{part_header_lines[0]} (Teil {idx})"
            part_transcript_content = "\n".join(part_header_lines) + "\n\n" + "\n\n".join(chunks[idx]) + "\n"
            part_transcript.write_text(part_transcript_content, encoding="utf-8")
            
            part_skeleton = drafts_dir / f"{video_id}.part{idx}.skeleton.md"
            part_handoff = drafts_dir / f"{video_id}.part{idx}.handoff.md"
            part_working = source / FINISHED_DIR_NAME / f"{video_id}.part{idx}.md"
            
            part_skeleton.write_text(render_skeleton(part_metadata), encoding="utf-8")
            part_handoff.write_text(
                render_handoff(
                    source,
                    part_metadata,
                    part_transcript,
                    part_skeleton,
                    part_working,
                    embed_content=args.embed_content,
                ),
                encoding="utf-8"
            )
            
            print(f"  - Teil {idx}:")
            print(f"    Rohtranskript: {part_transcript}")
            print(f"    Artikelskelett: {part_skeleton}")
            print(f"    KI-Handoff: {part_handoff}")
            print(f"    Vorlaeufige Redaktionsdatei: {part_working}")
            
        print("\nBitte bearbeite alle Teile nacheinander. Wenn alle fertig sind, führe Folgendes aus:")
        print(f"python3 transkript-agent/transkript_agent.py merge {video_id}")
        return 0
    else:
        working_output = working_transcript_path(source, video_id)
        working_output.parent.mkdir(parents=True, exist_ok=True)

        skeleton = drafts_dir / f"{video_id}.skeleton.md"
        handoff = drafts_dir / f"{video_id}.handoff.md"
        skeleton.write_text(render_skeleton(metadata), encoding="utf-8")
        handoff.write_text(
            render_handoff(
                source,
                metadata,
                transcript,
                skeleton,
                working_output,
                embed_content=args.embed_content,
            ),
            encoding="utf-8",
        )

        print("Vorarbeit abgeschlossen.")
        print(f"Video-ID: {video_id}")
        print(f"Rohtranskript: {transcript}")
        print(f"Artikelskelett: {skeleton}")
        print(f"KI-Handoff: {handoff}")
        print(f"Vorlaeufige Redaktionsdatei: {working_output}")
        print("Finale Zieldatei: wird nach finalize aus dem deutschen H1-Titel abgeleitet.")
        return 0


def parse_finished_part(content: str) -> tuple[str, str, list[tuple[str, str]]]:
    title = ""
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        
    parts = content.split("### ")
    cardlink_and_iframe = parts[0]
    if title_match:
        h1_line = title_match.group(0)
        idx = cardlink_and_iframe.find(h1_line)
        if idx != -1:
            cardlink_and_iframe = cardlink_and_iframe[:idx]
            
    sections = []
    for p in parts[1:]:
        lines = p.splitlines()
        if not lines:
            continue
        header = lines[0].strip()
        if header.lower() == "inhaltsverzeichnis":
            continue
        body = "\n".join(lines[1:])
        sections.append((header, body))
        
    return cardlink_and_iframe, title, sections


def cmd_merge(args: argparse.Namespace) -> int:
    source = args.source.expanduser()
    ensure_source(source)
    
    video_id = extract_video_id(args.video)
    
    finished_dir = source / FINISHED_DIR_NAME
    if not finished_dir.exists():
        raise AgentError(f"Ordner nicht gefunden: {finished_dir}")
        
    part_pattern = re.compile(rf"^{re.escape(video_id)}\.part(\d+)\.md$")
    part_files = []
    for file in finished_dir.glob("*.md"):
        match = part_pattern.match(file.name)
        if match:
            part_files.append((int(match.group(1)), file))
            
    if not part_files:
        raise AgentError(f"Keine übersetzten Abschnitte für Video-ID {video_id} gefunden (z. B. {video_id}.part1.md).")
        
    part_files.sort(key=lambda x: x[0])
    
    expected_parts = list(range(1, len(part_files) + 1))
    actual_parts = [p[0] for p in part_files]
    if actual_parts != expected_parts:
        missing = set(expected_parts) - set(actual_parts)
        raise AgentError(f"Nicht alle Abschnitte sind vorhanden. Gefunden: {actual_parts}, Fehlend: {list(missing)}.")
        
    cardlink_and_iframe = ""
    german_title = ""
    all_sections = []
    
    for idx, path in part_files:
        content = path.read_text(encoding="utf-8")
        part_header, part_title, part_sections = parse_finished_part(content)
        
        if idx == 1:
            cardlink_and_iframe = part_header.strip()
            german_title = re.sub(r"\s+\(Teil\s+\d+\)$", "", part_title).strip()
            
        all_sections.extend(part_sections)
        
    if not all_sections:
        raise AgentError("Keine Kapitel-Abschnitte in den fertigen Abschnitten gefunden.")
        
    lines = []
    if cardlink_and_iframe:
        lines.append(cardlink_and_iframe)
        lines.append("")
        
    lines.append(f"# {german_title}")
    lines.append("")
    lines.append("### Inhaltsverzeichnis")
    lines.append("")
    
    for header, _ in all_sections:
        lines.append(f"1. [[#{header}]]")
        lines.append("")
        
    lines.append("---")
    lines.append("")
    
    for header, body in all_sections:
        lines.append(f"### {header}")
        lines.append(body.strip())
        lines.append("")
        
    merged_content = "\n".join(lines)
    
    merged_path = working_transcript_path(source, video_id)
    merged_path.write_text(merged_content, encoding="utf-8")
    
    print(f"Kapitel erfolgreich zusammengeführt!")
    print(f"Teile kombiniert: {actual_parts}")
    print(f"Zieldatei geschrieben: {merged_path}")
    
    print("\nFühre Qualitätsprüfung für die zusammengeführte Datei aus...")
    validation_errors = validate_markdown_file(merged_path)
    if validation_errors:
        print("⚠️ Warnung: Validierungsfehler in der Datei gefunden:", file=sys.stderr)
        for err in validation_errors:
            print(f"  - {err}", file=sys.stderr)
    else:
        print("✅ Qualitätsprüfung erfolgreich! Keine Fehler gefunden.")
        
    print(f"\nNächster Schritt zur Registrierung:")
    rel_merged = relative_project_path(source, merged_path)
    print(f"python3 transkript-agent/transkript_agent.py finalize \"{rel_merged}\"")
    
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    source = args.source.expanduser()
    ensure_source(source)
    file_path = resolve_project_path(source, args.file)
    if not file_path.exists():
        raise AgentError(f"Datei nicht gefunden: {file_path}")
        
    errors = validate_markdown_file(file_path)
    if errors:
        print("❌ Validierung fehlgeschlagen mit folgenden Fehlern/Warnungen:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    else:
        print("✅ Validierung erfolgreich! Alle Regeln (H1, Inhaltsverzeichnis, Backlinks, LaTeX-Zahlen) eingehalten.")
        return 0


def cmd_latexify(args: argparse.Namespace) -> int:
    source = args.source.expanduser()
    ensure_source(source)
    file_path = resolve_project_path(source, args.file)
    if not file_path.exists():
        raise AgentError(f"Datei nicht gefunden: {file_path}")
        
    content = file_path.read_text(encoding="utf-8")
    new_content = auto_latexify_text(content)
    
    if content != new_content:
        file_path.write_text(new_content, encoding="utf-8")
        print(f"✅ Datei wurde erfolgreich automatisch formatiert: {file_path}")
    else:
        print("ℹ️ Keine Änderungen vorgenommen (Zahlen sind bereits in LaTeX).")
    return 0


def cmd_finalize(args: argparse.Namespace) -> int:
    source = args.source.expanduser()
    ensure_source(source)

    input_path = resolve_project_path(source, args.file)
    if not input_path.exists():
        raise AgentError(f"Fertige Markdown-Datei nicht gefunden: {input_path}")

    # Auto-validate and print warnings before finalization
    errors = validate_markdown_file(input_path)
    if errors:
        print("⚠️ Warnung: Validierungsfehler in der Datei gefunden:")
        for err in errors:
            print(f"  - {err}")
        print("Setze Finalisierung trotzdem fort...")

    content = input_path.read_text(encoding="utf-8")
    title = extract_markdown_h1(content)
    video_id = (
        extract_video_id(args.video_id)
        if args.video_id
        else extract_video_id_from_text(content)
    )
    if not video_id:
        raise AgentError(
            "Keine YouTube-Video-ID in der Datei gefunden. "
            "Bitte mit --video-id VIDEO_ID erneut ausfuehren."
        )

    final_path = finished_transcript_path(source, title, video_id)
    final_path.parent.mkdir(parents=True, exist_ok=True)

    if input_path.resolve() != final_path.resolve():
        if final_path.exists():
            raise AgentError(f"Zieldatei existiert bereits: {final_path}")
        input_path.rename(final_path)

    upsert_memory_entry(source, video_id, title, final_path)

    print("Finalisierung abgeschlossen.")
    print(f"Video-ID: {video_id}")
    print(f"Deutscher Titel: {title}")
    print(f"Finale Zieldatei: {final_path}")
    print(f"Register aktualisiert: {source / 'erinnerungsdatei.md'}")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return args.func(args)
    except AgentError as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
