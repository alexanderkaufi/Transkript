import { GoogleGenerativeAI } from "@google/generative-ai";

// DOM elements
const apiKeyInput = document.getElementById("apiKey");
const toggleApiKeyBtn = document.getElementById("toggleApiKey");
const videoUrlInput = document.getElementById("videoUrl");
const videoTitleInput = document.getElementById("videoTitle");
const videoDescInput = document.getElementById("videoDesc");
const modelSelect = document.getElementById("modelSelect");
const modeSelect = document.getElementById("modeSelect");
const rawTranscriptInput = document.getElementById("rawTranscript");
const processBtn = document.getElementById("processBtn");
const downloadBtn = document.getElementById("downloadBtn");
const markdownEditor = document.getElementById("markdownEditor");
const linterErrorsList = document.getElementById("linterErrors");
const themeToggleBtn = document.getElementById("themeToggle");
const deleteApiKeyBtn = document.getElementById("deleteApiKey");

// State
let isApiKeyVisible = false;

// 1. Theme Toggle & Persistence (Apple style)
const htmlElement = document.documentElement;
const savedTheme = localStorage.getItem("theme") || (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
htmlElement.setAttribute("data-theme", savedTheme);

themeToggleBtn.addEventListener("click", () => {
    const currentTheme = htmlElement.getAttribute("data-theme");
    const newTheme = currentTheme === "dark" ? "light" : "dark";
    htmlElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
});

// 2. API Key show/hide and persistence
toggleApiKeyBtn.addEventListener("click", () => {
    isApiKeyVisible = !isApiKeyVisible;
    apiKeyInput.type = isApiKeyVisible ? "text" : "password";
    toggleApiKeyBtn.textContent = isApiKeyVisible ? "🔒" : "👁️";
});

// Load API Key from localStorage
const storedKey = localStorage.getItem("gemini_api_key");
if (storedKey) {
    apiKeyInput.value = storedKey;
}

// Save API Key on input change
apiKeyInput.addEventListener("input", () => {
    localStorage.setItem("gemini_api_key", apiKeyInput.value.trim());
});

// Delete API Key from localStorage
deleteApiKeyBtn.addEventListener("click", () => {
    if (confirm("Möchtest du deinen Gemini-API-Schlüssel wirklich aus dem Browser-Speicher löschen?")) {
        apiKeyInput.value = "";
        localStorage.removeItem("gemini_api_key");
        alert("API-Schlüssel gelöscht!");
    }
});

// 3. Video URL Parser & Auto-Fetch Title (CORS-free noembed.com)
function extractVideoId(url) {
    const trimmed = url.trim();
    if (/^[\w-]{11}$/.test(trimmed)) {
        return trimmed;
    }
    try {
        const parsed = new URL(trimmed);
        const host = parsed.hostname.toLowerCase();
        
        if (host === "youtu.be" || host === "www.youtu.be") {
            const parts = parsed.pathname.split("/").filter(p => p);
            if (parts.length > 0) return parts[0];
        }
        
        if (host.includes("youtube.com") || host.includes("youtube-nocookie.com")) {
            if (parsed.pathname === "/watch") {
                const v = parsed.searchParams.get("v");
                if (v) return v;
            }
            const parts = parsed.pathname.split("/").filter(p => p);
            if (parts.length >= 2 && ["embed", "shorts", "live"].includes(parts[0])) {
                return parts[1];
            }
        }
    } catch (e) {
        // Not a valid URL, ignore
    }
    return null;
}

videoUrlInput.addEventListener("input", async () => {
    const url = videoUrlInput.value.trim();
    const videoId = extractVideoId(url);
    if (videoId) {
        try {
            // Fetch video title via noembed.com oEmbed proxy (which allows CORS)
            const response = await fetch(`https://noembed.com/embed?url=https://www.youtube.com/watch?v=${videoId}`);
            if (response.ok) {
                const data = await response.json();
                if (data && data.title) {
                    videoTitleInput.value = data.title;
                    if (!videoDescInput.value.trim() && data.author_name) {
                        videoDescInput.value = `Video von ${data.author_name}`;
                    }
                }
            }
        } catch (error) {
            console.error("Fehler beim Laden der YouTube Metadaten:", error);
        }
    }
});

// 3. JS Linter
function runLinter(content) {
    const errors = [];
    if (!content.trim()) {
        return [{ type: 'info', text: "Warte auf Eingabe oder Verarbeitung..." }];
    }
    
    // 1. H1 title check
    const h1Match = content.match(/^#\s+(.+)$/m);
    if (!h1Match) {
        errors.push({ type: 'error', text: "Kein H1-Titel (# Titel) gefunden." });
    }
    
    // 2. Cardlink check
    if (!content.includes("```cardlink")) {
        errors.push({ type: 'error', text: "Kein ```cardlink Block gefunden." });
    }
    
    // 3. Iframe check
    if (!content.includes("<iframe ")) {
        errors.push({ type: 'error', text: "Kein <iframe>-Tag fuer das Video gefunden." });
    }
    
    // 4. Inhaltsverzeichnis check
    if (!content.includes("### Inhaltsverzeichnis")) {
        errors.push({ type: 'error', text: "Kein '### Inhaltsverzeichnis' Header gefunden." });
    }
    
    // 5. Chapters check
    const chapters = [];
    const chapterRegex = /^###\s+(.+)$/gm;
    let match;
    while ((match = chapterRegex.exec(content)) !== null) {
        const title = match[1].trim();
        if (title.toLowerCase() !== "inhaltsverzeichnis") {
            chapters.push(title);
        }
    }
    
    if (chapters.length === 0) {
        errors.push({ type: 'error', text: "Keine Kapitelüberschriften (### Kapitelname) gefunden." });
    }
    
    // 5a. Mismatched brackets
    const lines = content.split("\n");
    lines.forEach((line, index) => {
        const lineNo = index + 1;
        const openCount = (line.match(/\[\[/g) || []).length;
        const closeCount = (line.match(/\]\]/g) || []).length;
        if (openCount !== closeCount) {
            errors.push({ type: 'error', text: `Zeile ${lineNo}: Unvollständiger Obsidian-Link (Klammern stimmen nicht überein: '[[' vs ']]').` });
        }
    });
    
    // 5b. Chapter backlinks check
    const sections = content.split("### ");
    sections.forEach((section) => {
        const sectionLines = section.split("\n");
        if (sectionLines.length > 0) {
            const header = sectionLines[0].trim();
            if (header && header.toLowerCase() !== "inhaltsverzeichnis" && !content.startsWith(section)) {
                if (!section.includes("[[# Inhaltsverzeichnis]]")) {
                    errors.push({ type: 'error', text: `Kapitel "${header}" hat keinen Backlink zu '[[# Inhaltsverzeichnis]]'.` });
                }
            }
        }
    });
    
    // 5c. TOC links vs actual chapters check
    if (content.includes("### Inhaltsverzeichnis")) {
        const tocStart = content.indexOf("### Inhaltsverzeichnis");
        let rest = content.substring(tocStart);
        const nextH3 = rest.indexOf("### ", "### Inhaltsverzeichnis".length);
        const nextDiv = rest.indexOf("---");
        let endIdx = rest.length;
        if (nextH3 !== -1 && nextDiv !== -1) {
            endIdx = Math.min(nextH3, nextDiv);
        } else if (nextH3 !== -1) {
            endIdx = nextH3;
        } else if (nextDiv !== -1) {
            endIdx = nextDiv;
        }
        
        const tocBlock = rest.substring(0, endIdx);
        const tocLinkRegex = /\[\[#\s*([^\]]+)\]\]/g;
        const tocLinks = [];
        let tocMatch;
        while ((tocMatch = tocLinkRegex.exec(tocBlock)) !== null) {
            const link = tocMatch[1].trim();
            if (link.toLowerCase() !== "inhaltsverzeichnis") {
                tocLinks.push(link);
            }
        }
        
        chapters.forEach((ch) => {
            if (!tocLinks.includes(ch)) {
                errors.push({ type: 'error', text: `Kapitel "${ch}" fehlt im Inhaltsverzeichnis.` });
            }
        });
        tocLinks.forEach((lk) => {
            if (!chapters.includes(lk)) {
                errors.push({ type: 'error', text: `Inhaltsverzeichnis verweist auf nicht existierendes Kapitel: "${lk}".` });
            }
        });
    }
    
    // 6. LaTeX unformatted checks
    let cleanContent = content.replace(/```cardlink[\s\S]*?```/g, "");
    cleanContent = cleanContent.replace(/<[^>]+>/g, "");
    
    const parts = cleanContent.split("$$");
    parts.forEach((part, index) => {
        if (index % 2 === 0) {
            const pctMatches = part.match(/\b\d+\s*%/g);
            if (pctMatches) {
                errors.push({ type: 'warning', text: `Unformatierte Prozentangabe(n): ${pctMatches.join(", ")}. Bitte als $$86\\text{\\%}$$ formatieren.` });
            }
            
            const unitRegex = /\b\d+\s*(?:Jahre|Jahren|Wochen|Monate|Tage|Stunden|Minuten|Ohm|Uhr|Milliarden|Millionen)\b/g;
            const unitMatches = part.match(unitRegex);
            if (unitMatches) {
                errors.push({ type: 'warning', text: `Unformatierte Zahl mit Einheit: ${unitMatches.join(", ")}. Bitte als $$2000\\text{ Jahren}$$ formatieren.` });
            }
        }
    });
    
    if (errors.length === 0) {
        errors.push({ type: 'success', text: "✅ Qualitätsprüfung erfolgreich! Keine Formatierungsfehler gefunden." });
    }
    
    return errors;
}

function updateLinterUI() {
    const errors = runLinter(markdownEditor.value);
    linterErrorsList.innerHTML = "";
    errors.forEach(err => {
        const li = document.createElement("li");
        li.className = err.type;
        li.textContent = err.text;
        linterErrorsList.appendChild(li);
    });
}

// Attach linter to editor input
markdownEditor.addEventListener("input", updateLinterUI);

// 4. Processing logic (Call Gemini API)
processBtn.addEventListener("click", async () => {
    const apiKey = apiKeyInput.value.trim();
    if (!apiKey) {
        alert("Bitte gib einen gültigen Gemini-API-Key ein.");
        return;
    }
    
    const url = videoUrlInput.value.trim();
    const videoId = extractVideoId(url);
    if (!videoId) {
        alert("Bitte gib eine gültige YouTube URL oder 11-stellige Video-ID ein.");
        return;
    }
    
    const title = videoTitleInput.value.trim() || `YouTube-Video ${videoId}`;
    const desc = videoDescInput.value.trim();
    const rawText = rawTranscriptInput.value.trim();
    if (!rawText) {
        alert("Bitte füge das Rohtranskript ein.");
        return;
    }
    
    const modelName = modelSelect.value;
    const mode = modeSelect.value;
    
    // Set UI loading state
    processBtn.disabled = true;
    processBtn.querySelector(".btn-text").textContent = "Verarbeitung läuft...";
    processBtn.querySelector(".spinner").classList.remove("hidden");
    
    try {
        const genAI = new GoogleGenerativeAI(apiKey);
        const model = genAI.getGenerativeModel({ model: modelName });
        
        let systemInstruction = `Du bist ein hochpräziser Übersetzer und Redakteur für Video-Transkripte.
DEINE REGELN:
1. Kürze den Text auf keinen Fall. Erstelle KEINE Zusammenfassung oder kompakte Wissensnotiz. Halte mindestens 80% des Inhaltsumfangs.
2. Entferne jegliche Werbung und Sponsoren-Einblendungen (oft markiert mit "⚠️ [WERBUNG?]").
3. Konvertiere den Text in sauberes Markdown.
4. Formatiere ALLE Zahlen, Jahreszahlen, Maßeinheiten und Prozentsätze konsequent in mathematischer LaTeX-Syntax mit doppelten Dollarzeichen (z. B. $$86\\text{\\%}$$, $$2000\\text{ Jahren}$$, $$50\\text{ Ohm}$$, $$3\\text{,5 Jahre}$$, $$22\\text{. Jahr}$$, $$3\\text{ andere Züge}$$).
5. Erzeuge thematische Abschnitte (H3 Überschriften).
6. Setze genaue Zeitstempel (z. B. **05:12**) NUR an den Anfang jedes Abschnitts.
7. Am Ende jedes Abschnitts MUSS die Zeile "[[# Inhaltsverzeichnis]]" stehen.
8. Erzeuge am Anfang des Dokuments ein Inhaltsverzeichnis (TOC) unter "### Inhaltsverzeichnis" mit Links zu allen Abschnitten (z. B. "1. [[#Einführung]]").`;

        if (mode === "translate") {
            systemInstruction += "\n9. Übersetze den gesamten Text vollständig ins Deutsche.";
        } else {
            systemInstruction += "\n9. Der Text ist bereits deutsch. Redigiere ihn sauber auf Deutsch (Sätze glätten, Füllwörter raus, Grammatik korrigieren), aber kürze nichts inhaltlich.";
        }

        const prompt = `Hier ist das Rohtranskript zum Verarbeiten:
${rawText}

Bitte erstelle daraus den finalen Text ab dem H1-Titel (z. B. "# [Deutscher Titel]") gefolgt vom Inhaltsverzeichnis und den Kapiteln. Erzeuge KEINE Cardlinks oder Iframes, das übernehme ich selbst.`;

        const result = await model.generateContent({
            contents: [{ role: "user", parts: [{ text: prompt }] }],
            generationConfig: {
                systemInstruction: systemInstruction,
                temperature: 0.1
            }
        });
        
        const responseText = result.response.text();
        
        // Assemble Cardlink & Iframe
        const cardlink = `\`\`\`cardlink
url: https://www.youtube.com/watch?v=${videoId}
title: "${title.replace(/"/g, '\\"')}"
description: "${desc.replace(/"/g, '\\"')}"
host: www.youtube.com
favicon: https://www.youtube.com/favicon.ico
image: https://i.ytimg.com/vi_webp/${videoId}/maxresdefault.webp
\`\`\``;

        const cleanTitle = title.replace(/"/g, '\\"');
        const iframe = `<iframe title="${cleanTitle}" src="https://www.youtube.com/embed/${videoId}" height="113" width="200" style="aspect-ratio: 1.76991 / 1; width: 100%; height: 100%;" allowfullscreen="" allow="fullscreen"></iframe>`;
        
        const finalMarkdown = `${cardlink}\n${iframe}\n\n${responseText.trim()}`;
        
        markdownEditor.value = finalMarkdown;
        downloadBtn.disabled = false;
        updateLinterUI();
        
    } catch (error) {
        console.error(error);
        alert("Fehler bei der API-Verarbeitung: " + error.message);
    } finally {
        processBtn.disabled = false;
        processBtn.querySelector(".btn-text").textContent = "Verarbeitung starten";
        processBtn.querySelector(".spinner").classList.add("hidden");
    }
});

// 5. Exporter (Markdown Downloader)
downloadBtn.addEventListener("click", () => {
    const content = markdownEditor.value;
    if (!content.trim()) return;
    
    // Find Title for filename slug
    const h1Match = content.match(/^#\s+(.+)$/m);
    let filename = "transkript.md";
    if (h1Match) {
        const title = h1Match[1].trim();
        // slugify
        filename = title
            .toLowerCase()
            .replace(/[^\w\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            + ".md";
    }
    
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const downloadUrl = URL.createObjectURL(blob);
    
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(downloadUrl);
});
