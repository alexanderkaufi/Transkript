from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import transkript_agent as agent


class TranskriptAgentTests(unittest.TestCase):
    def test_extract_video_id_from_common_urls(self) -> None:
        self.assertEqual(
            agent.extract_video_id("https://www.youtube.com/watch?v=VVXj6UHcNzs"),
            "VVXj6UHcNzs",
        )
        self.assertEqual(
            agent.extract_video_id("https://youtu.be/VVXj6UHcNzs"),
            "VVXj6UHcNzs",
        )
        self.assertEqual(
            agent.extract_video_id("https://www.youtube.com/shorts/VVXj6UHcNzs"),
            "VVXj6UHcNzs",
        )
        self.assertEqual(agent.extract_video_id("VVXj6UHcNzs"), "VVXj6UHcNzs")

    def test_parse_memory_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = Path(tmp) / "erinnerungsdatei.md"
            memory.write_text(
                "| Video-ID | Name der Wissensdatei | Datei |\n"
                "|---|---|---|\n"
                "| `VVXj6UHcNzs` | Beispiel Titel | `beispiel.md` |\n",
                encoding="utf-8",
            )

            processed = agent.parse_memory_file(memory)

        self.assertIn("VVXj6UHcNzs", processed)
        self.assertEqual(processed["VVXj6UHcNzs"].filename, "beispiel.md")

    def test_render_skeleton_contains_embed_and_toc(self) -> None:
        metadata = agent.default_metadata("VVXj6UHcNzs")
        skeleton = agent.render_skeleton(metadata)

        self.assertTrue(skeleton.startswith("```cardlink"))
        self.assertIn("```cardlink", skeleton)
        self.assertIn("https://www.youtube.com/embed/VVXj6UHcNzs", skeleton)
        self.assertIn("[[#Einfuehrung]]", skeleton)

    def test_finished_transcript_path_uses_finished_folder(self) -> None:
        path = agent.finished_transcript_path(
            Path("/tmp/transkript"),
            "Mein fertiges Transkript",
            "VVXj6UHcNzs",
        )

        self.assertEqual(
            path,
            Path("/tmp/transkript/Fertige Transkripte/Mein fertiges Transkript.md"),
        )

    def test_render_handoff_defaults_to_reference_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            prompt = source / "prompt-uebersetzer-redaktor.md"
            transcript = source / "transcripts" / "VVXj6UHcNzs.transcript.md"
            skeleton = source / "transkript-agent" / "drafts" / "video.skeleton.md"
            working_output = source / "Fertige Transkripte" / "VVXj6UHcNzs.md"
            prompt.write_text("GEHEIMER LANGER PROMPT", encoding="utf-8")
            transcript.parent.mkdir()
            transcript.write_text("SEHR LANGES ROHTRANSKRIPT", encoding="utf-8")

            handoff = agent.render_handoff(
                source,
                agent.default_metadata("VVXj6UHcNzs"),
                transcript,
                skeleton,
                working_output,
            )

        self.assertIn("Kontextsparmodus", handoff)
        self.assertIn("prompt-uebersetzer-redaktor.md", handoff)
        self.assertIn("VVXj6UHcNzs.transcript.md", handoff)
        self.assertIn("Vorlaeufige Redaktionsdatei", handoff)
        self.assertIn("finalize", handoff)
        self.assertNotIn("GEHEIMER LANGER PROMPT", handoff)
        self.assertNotIn("SEHR LANGES ROHTRANSKRIPT", handoff)

    def test_prepare_does_not_stop_on_memory_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "scripts").mkdir()
            (source / "transcripts").mkdir()
            (source / "transkript-agent" / "drafts").mkdir(parents=True)
            (source / "scripts" / "youtube_transcript.py").write_text(
                "# placeholder\n",
                encoding="utf-8",
            )
            (source / "prompt-uebersetzer-redaktor.md").write_text(
                "Prompt",
                encoding="utf-8",
            )
            (source / "erinnerungsdatei.md").write_text(
                "| Video-ID | Name der Wissensdatei | Datei |\n"
                "|---|---|---|\n"
                "| `VVXj6UHcNzs` | Alt | `Fertige Transkripte/alt.md` |\n",
                encoding="utf-8",
            )
            (source / "transcripts" / "VVXj6UHcNzs.transcript.md").write_text(
                "# Rohtranskript\n",
                encoding="utf-8",
            )
            args = mock.Mock(
                source=source,
                video="VVXj6UHcNzs",
                transcript_output=None,
                no_fetch=True,
                skip_metadata=True,
                drafts=None,
                embed_content=False,
            )

            result = agent.cmd_prepare(args)

            handoffs = list((source / "transkript-agent" / "drafts").glob("*.handoff.md"))
            handoff = source / "transkript-agent" / "drafts" / "VVXj6UHcNzs.handoff.md"
            handoff_exists = handoff.exists()
        self.assertEqual(result, 0)
        self.assertEqual(len(handoffs), 1)
        self.assertTrue(handoff_exists)

    def test_prepare_uses_video_id_drafts_for_non_ascii_titles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "scripts").mkdir()
            (source / "transcripts").mkdir()
            (source / "transkript-agent" / "drafts").mkdir(parents=True)
            (source / "scripts" / "youtube_transcript.py").write_text(
                "# placeholder\n",
                encoding="utf-8",
            )
            (source / "prompt-uebersetzer-redaktor.md").write_text(
                "Prompt",
                encoding="utf-8",
            )
            (source / "erinnerungsdatei.md").write_text("", encoding="utf-8")
            (source / "transcripts" / "NJOwr06GW8M.transcript.md").write_text(
                "# Rohtranskript\n",
                encoding="utf-8",
            )
            args = mock.Mock(
                source=source,
                video="NJOwr06GW8M",
                transcript_output=None,
                no_fetch=True,
                skip_metadata=False,
                drafts=None,
                embed_content=False,
            )
            metadata = agent.VideoMetadata(
                video_id="NJOwr06GW8M",
                url="https://www.youtube.com/watch?v=NJOwr06GW8M",
                title="Психология Людей, Которые Много Думают 6 черт",
                description="",
                host="www.youtube.com",
                favicon="https://www.youtube.com/favicon.ico",
                image="https://i.ytimg.com/vi_webp/NJOwr06GW8M/maxresdefault.webp",
            )

            with mock.patch.object(agent, "load_metadata", return_value=metadata):
                result = agent.cmd_prepare(args)

            drafts = source / "transkript-agent" / "drafts"
            handoff_exists = (drafts / "NJOwr06GW8M.handoff.md").exists()
            skeleton_exists = (drafts / "NJOwr06GW8M.skeleton.md").exists()
            old_handoff_exists = (drafts / "6.handoff.md").exists()

        self.assertEqual(result, 0)
        self.assertTrue(handoff_exists)
        self.assertTrue(skeleton_exists)
        self.assertFalse(old_handoff_exists)

    def test_slugify_uses_ascii_fallback(self) -> None:
        self.assertEqual(
            agent.slugify("Der große Test: KI & Ökonomie!", "fallback"),
            "Der große Test KI & Ökonomie!",
        )
        self.assertEqual(agent.slugify("???", "fallback"), "fallback")

    def test_render_cardlink_escapes_quotes(self) -> None:
        metadata = agent.VideoMetadata(
            video_id="VVXj6UHcNzs",
            url="https://www.youtube.com/watch?v=VVXj6UHcNzs",
            title='Titel mit "Zitat"',
            description='Beschreibung mit "Zitat"',
            host="www.youtube.com",
            favicon="https://www.youtube.com/favicon.ico",
            image="https://i.ytimg.com/vi_webp/VVXj6UHcNzs/maxresdefault.webp",
        )

        cardlink = agent.render_cardlink(metadata, metadata.title)

        self.assertIn('title: "Titel mit \\"Zitat\\""', cardlink)
        self.assertIn('description: "Beschreibung mit \\"Zitat\\""', cardlink)

    def test_finalize_renames_from_german_h1_and_updates_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            final_dir = source / "Fertige Transkripte"
            final_dir.mkdir()
            (source / "scripts").mkdir()
            (source / "scripts" / "youtube_transcript.py").write_text(
                "# placeholder\n",
                encoding="utf-8",
            )
            (source / "prompt-uebersetzer-redaktor.md").write_text(
                "Prompt",
                encoding="utf-8",
            )
            (source / "erinnerungsdatei.md").write_text(
                "| Video-ID | Name der Wissensdatei | Datei |\n"
                "|---|---|---|\n",
                encoding="utf-8",
            )
            draft = final_dir / "NJOwr06GW8M.md"
            draft.write_text(
                "```cardlink\n"
                "url: https://www.youtube.com/watch?v=NJOwr06GW8M\n"
                "```\n\n"
                "# Psychologie von Menschen, die zu viel denken: sechs Merkmale\n\n"
                "Text.\n",
                encoding="utf-8",
            )
            args = mock.Mock(source=source, file=draft, video_id=None)

            result = agent.cmd_finalize(args)

            target = (
                final_dir
                / "Psychologie von Menschen, die zu viel denken sechs Merkmale.md"
            )
            target_exists = target.exists()
            draft_exists = draft.exists()
            memory = (source / "erinnerungsdatei.md").read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertTrue(target_exists)
        self.assertFalse(draft_exists)
        self.assertIn("`NJOwr06GW8M`", memory)
        self.assertIn(
            "`Fertige Transkripte/Psychologie von Menschen, die zu viel denken sechs Merkmale.md`",
            memory,
        )

    def test_finalize_adds_memory_table_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            final_dir = source / "Fertige Transkripte"
            final_dir.mkdir()
            (source / "scripts").mkdir()
            (source / "scripts" / "youtube_transcript.py").write_text(
                "# placeholder\n",
                encoding="utf-8",
            )
            (source / "prompt-uebersetzer-redaktor.md").write_text(
                "Prompt",
                encoding="utf-8",
            )
            (source / "erinnerungsdatei.md").write_text(
                "# Erinnerungsdatei\n\nNur Regeln, noch kein Register.\n",
                encoding="utf-8",
            )
            draft = final_dir / "VVXj6UHcNzs.md"
            draft.write_text(
                "# Deutscher Testtitel\n\n"
                "https://www.youtube.com/watch?v=VVXj6UHcNzs\n",
                encoding="utf-8",
            )
            args = mock.Mock(source=source, file=draft, video_id=None)

            result = agent.cmd_finalize(args)

            memory = (source / "erinnerungsdatei.md").read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertIn("| Video-ID | Name der Wissensdatei | Datei |", memory)
        self.assertIn("| `VVXj6UHcNzs` | Deutscher Testtitel |", memory)

    def test_finalize_repairs_existing_memory_rows_without_header(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            final_dir = source / "Fertige Transkripte"
            final_dir.mkdir()
            (source / "scripts").mkdir()
            (source / "scripts" / "youtube_transcript.py").write_text(
                "# placeholder\n",
                encoding="utf-8",
            )
            (source / "prompt-uebersetzer-redaktor.md").write_text(
                "Prompt",
                encoding="utf-8",
            )
            (source / "erinnerungsdatei.md").write_text(
                "# Erinnerungsdatei\n\n"
                "6. Rohtranskripte nach Abschluss wieder loeschen.\n"
                "| `8_HGtUGIl5Q` | Alt | `Fertige Transkripte/alt.md` |\n",
                encoding="utf-8",
            )
            draft = final_dir / "VVXj6UHcNzs.md"
            draft.write_text(
                "# Deutscher Testtitel\n\n"
                "https://www.youtube.com/watch?v=VVXj6UHcNzs\n",
                encoding="utf-8",
            )
            args = mock.Mock(source=source, file=draft, video_id=None)

            result = agent.cmd_finalize(args)

            memory = (source / "erinnerungsdatei.md").read_text(encoding="utf-8")

        self.assertEqual(result, 0)
        self.assertIn("| Video-ID | Name der Wissensdatei | Datei |", memory)
        self.assertIn("| `8_HGtUGIl5Q` | Alt |", memory)
        self.assertIn("| `VVXj6UHcNzs` | Deutscher Testtitel |", memory)

    def test_validate_markdown_file_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "test.md"
            file_path.write_text(
                "```cardlink\n"
                "url: https://www.youtube.com/watch?v=VVXj6UHcNzs\n"
                "title: \"Test Title\"\n"
                "```\n\n"
                "<iframe src=\"https://youtube.com/embed/VVXj6UHcNzs\" title=\"Test\"></iframe>\n\n"
                "# Test Title\n\n"
                "### Inhaltsverzeichnis\n\n"
                "1. [[#Einführung]]\n\n"
                "---\n\n"
                "### Einführung\n\n"
                "Das ist ein Test mit $$86\\text{\\%}$$ Erfolg und $$2\\text{ Jahren}$$ Laufzeit.\n\n"
                "[[# Inhaltsverzeichnis]]\n",
                encoding="utf-8"
            )
            errors = agent.validate_markdown_file(file_path)
        self.assertEqual(errors, [])

    def test_validate_markdown_file_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "test_invalid.md"
            file_path.write_text(
                "# Test Title\n\n"
                "Das ist ein Test mit 86% Erfolg und 2 Jahren Laufzeit.\n",
                encoding="utf-8"
            )
            errors = agent.validate_markdown_file(file_path)
        self.assertTrue(len(errors) > 0)
        self.assertTrue(any("cardlink" in e for e in errors))
        self.assertTrue(any("iframe" in e for e in errors))
        self.assertTrue(any("Inhaltsverzeichnis" in e for e in errors))
        self.assertTrue(any("Prozentangabe" in e for e in errors))
        self.assertTrue(any("Einheiten" in e for e in errors))

    def test_prepare_chunks_long_video(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            (source / "transcripts").mkdir()
            (source / "transkript-agent" / "drafts").mkdir(parents=True)
            (source / "Fertige Transkripte").mkdir()
            (source / "prompt-uebersetzer-redaktor.md").write_text("Prompt Content", encoding="utf-8")
            (source / "erinnerungsdatei.md").write_text("Memory\n", encoding="utf-8")
            
            transcript_content = (
                "# YouTube-Transkript: LongVideoID\n\n"
                "- Quelle: https://www.youtube.com/watch?v=LongVideoID\n"
                "- Sprache: Russian\n"
                "- Typ: automatisch\n\n"
                "## Transkript\n\n"
                "**00:00** Hallo Welt\n\n"
                "**15:00** Zweiter Teil\n\n"
                "**30:00** Dritter Teil\n\n"
                "**48:00** Letzter Teil\n"
            )
            transcript_path = source / "transcripts" / "LongVideoID.transcript.md"
            transcript_path.write_text(transcript_content, encoding="utf-8")
            
            args = mock.Mock(
                source=source,
                video="LongVideoID",
                transcript_output=None,
                no_fetch=True,
                skip_metadata=True,
                drafts=None,
                embed_content=False,
                chunk_threshold=2700,
                chunk_size=900,
            )
            
            result = agent.cmd_prepare(args)
            
            drafts_dir = source / "transkript-agent" / "drafts"
            part1_skeleton = drafts_dir / "LongVideoID.part1.skeleton.md"
            part4_skeleton = drafts_dir / "LongVideoID.part4.skeleton.md"
            part1_handoff = drafts_dir / "LongVideoID.part1.handoff.md"
            part4_handoff = drafts_dir / "LongVideoID.part4.handoff.md"
            
            self.assertEqual(result, 0)
            self.assertTrue(part1_skeleton.exists())
            self.assertTrue(part4_skeleton.exists())
            self.assertTrue(part1_handoff.exists())
            self.assertTrue(part4_handoff.exists())
            
            part4_transcript = source / "transcripts" / "LongVideoID.part4.transcript.md"
            self.assertTrue(part4_transcript.exists())
            part4_txt = part4_transcript.read_text(encoding="utf-8")
            self.assertIn("# YouTube-Transkript: LongVideoID (Teil 4)", part4_txt)

    def test_merge_recombines_parts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)
            finished_dir = source / "Fertige Transkripte"
            finished_dir.mkdir()
            (source / "erinnerungsdatei.md").write_text("Memory", encoding="utf-8")
            (source / "prompt-uebersetzer-redaktor.md").write_text("Prompt Content\n", encoding="utf-8")
            
            part1_content = (
                "```cardlink\n"
                "url: https://www.youtube.com/watch?v=LongVideoID\n"
                "title: \"Video Title (Teil 1)\"\n"
                "description: \"Desc\"\n"
                "```\n"
                "<iframe src=\"https://youtube.com/embed/LongVideoID\" title=\"Video\"></iframe>\n\n"
                "# Video Title (Teil 1)\n\n"
                "### Inhaltsverzeichnis\n\n"
                "1. [[#Einführung]]\n\n"
                "---\n\n"
                "### Einführung\n\n"
                "Teil 1 Text\n\n"
                "[[# Inhaltsverzeichnis]]\n"
            )
            part2_content = (
                "```cardlink\n"
                "url: https://www.youtube.com/watch?v=LongVideoID\n"
                "title: \"Video Title (Teil 2)\"\n"
                "description: \"Desc\"\n"
                "```\n"
                "<iframe src=\"https://youtube.com/embed/LongVideoID\" title=\"Video\"></iframe>\n\n"
                "# Video Title (Teil 2)\n\n"
                "### Inhaltsverzeichnis\n\n"
                "1. [[#Hauptteil]]\n\n"
                "---\n\n"
                "### Hauptteil\n\n"
                "Teil 2 Text\n\n"
                "[[# Inhaltsverzeichnis]]\n"
            )
            
            (finished_dir / "LongVideoID.part1.md").write_text(part1_content, encoding="utf-8")
            (finished_dir / "LongVideoID.part2.md").write_text(part2_content, encoding="utf-8")
            
            args = mock.Mock(
                source=source,
                video="LongVideoID",
            )
            
            result = agent.cmd_merge(args)
            
            merged_file = finished_dir / "LongVideoID.md"
            self.assertEqual(result, 0)
            self.assertTrue(merged_file.exists())
            
            merged_txt = merged_file.read_text(encoding="utf-8")
            self.assertIn("# Video Title", merged_txt)
            self.assertNotIn("# Video Title (Teil 1)", merged_txt)
            
            self.assertIn("1. [[#Einführung]]", merged_txt)
            self.assertIn("1. [[#Hauptteil]]", merged_txt)
            
            self.assertIn("### Einführung", merged_txt)
            self.assertIn("Teil 1 Text", merged_txt)
            self.assertIn("### Hauptteil", merged_txt)
            self.assertIn("Teil 2 Text", merged_txt)

    def test_is_potential_ad_detects_keywords(self) -> None:
        self.assertTrue(agent.is_potential_ad("Dieser Teil wird von NordVPN gesponsert."))
        self.assertTrue(agent.is_potential_ad("Use discount code FOO for 10% off."))
        self.assertTrue(agent.is_potential_ad("Поддержите канал на спонсор."))
        self.assertTrue(agent.is_potential_ad("Вот наша реклама."))
        self.assertFalse(agent.is_potential_ad("Dies ist ein ganz normaler Satz über das Gehirn."))

    def test_render_markdown_transcript_flags_ads(self) -> None:
        track = agent.CaptionTrack("ru", "Russian", "http://url", "kind", is_generated=True)
        segments = [
            agent.TranscriptSegment(0.0, 5.0, "Hallo zusammen"),
            agent.TranscriptSegment(5.0, 10.0, "Holt euch den Rabattcode in der Beschreibung"),
        ]
        markdown = agent.render_markdown_transcript("VVXj6UHcNzs", "http://url", track, segments, include_timestamps=True)
        self.assertIn("**00:00** Hallo zusammen", markdown)
        self.assertIn("**00:05** ⚠️ [WERBUNG?] Holt euch den Rabattcode in der Beschreibung", markdown)

    def test_validate_detects_unmatched_brackets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "test.md"
            file_path.write_text(
                "```cardlink\n"
                "url: https://www.youtube.com/watch?v=VVXj6UHcNzs\n"
                "```\n"
                "<iframe src=\"https://youtube.com/embed/VVXj6UHcNzs\" title=\"Test\"></iframe>\n\n"
                "# Title\n\n"
                "### Inhaltsverzeichnis\n\n"
                "1. [[#Einführung]]\n\n"
                "---\n\n"
                "### Einführung\n\n"
                "Hier ist ein fehlerhafter [[Link ohne Ende.\n\n"
                "[[# Inhaltsverzeichnis]]\n",
                encoding="utf-8"
            )
            errors = agent.validate_markdown_file(file_path)
            self.assertTrue(any("Unvollständiger Obsidian-Link" in e for e in errors))

    def test_validate_detects_missing_section_backlink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "test.md"
            file_path.write_text(
                "```cardlink\n"
                "url: https://www.youtube.com/watch?v=VVXj6UHcNzs\n"
                "```\n"
                "<iframe src=\"https://youtube.com/embed/VVXj6UHcNzs\" title=\"Test\"></iframe>\n\n"
                "# Title\n\n"
                "### Inhaltsverzeichnis\n\n"
                "1. [[#Einführung]]\n\n"
                "---\n\n"
                "### Einführung\n\n"
                "Kein Backlink hier.\n",
                encoding="utf-8"
            )
            errors = agent.validate_markdown_file(file_path)
            self.assertTrue(any("keinen Backlink zu '[[# Inhaltsverzeichnis]]'" in e for e in errors))

    def test_validate_detects_toc_inconsistencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            file_path = Path(tmp) / "test.md"
            file_path.write_text(
                "```cardlink\n"
                "url: https://www.youtube.com/watch?v=VVXj6UHcNzs\n"
                "```\n"
                "<iframe src=\"https://youtube.com/embed/VVXj6UHcNzs\" title=\"Test\"></iframe>\n\n"
                "# Title\n\n"
                "### Inhaltsverzeichnis\n\n"
                "1. [[#Einführung]]\n"
                "2. [[#Alt]]\n\n"
                "---\n\n"
                "### Einführung\n\n"
                "Text\n\n"
                "[[# Inhaltsverzeichnis]]\n\n"
                "### Hauptteil\n\n"
                "Text\n\n"
                "[[# Inhaltsverzeichnis]]\n",
                encoding="utf-8"
            )
            errors = agent.validate_markdown_file(file_path)
            self.assertTrue(any("fehlt im Inhaltsverzeichnis" in e for e in errors))
            self.assertTrue(any("verweist auf nicht existierendes Kapitel" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
