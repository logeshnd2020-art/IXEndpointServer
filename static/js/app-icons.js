/**
 * Small local application-icon lookup, keyed by keyword match on the
 * application name reported by the agent. All glyphs are simple, generic
 * inline SVG shapes (browser/terminal/chat/mail/document/folder/camera)
 * -- not copies of any real application's actual logo/trademark, and no
 * external icon CDN/API is used. Anything unrecognized falls back to a
 * plain initials badge.
 */
const IXAppIcons = (() => {

    const GLYPHS = {
        browser: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 3 2.5 15 0 18M12 3c-2.5 3-2.5 15 0 18"/></svg>`,
        terminal: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/></svg>`,
        chat: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M21 12a8 8 0 1 1-3.4-6.5L21 4l-1 4.2A8 8 0 0 1 21 12Z"/></svg>`,
        mail: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>`,
        video: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="M16 10l5-3v10l-5-3"/></svg>`,
        document: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6 3h8l5 5v13H6z"/><path d="M14 3v5h5M9 13h6M9 17h6"/></svg>`,
        sheet: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M10 4v16"/></svg>`,
        folder: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/></svg>`,
        code: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M8 6l-5 6 5 6M16 6l5 6-5 6M14 4l-4 16"/></svg>`,
        note: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg>`,
        design: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 3a9 9 0 0 0 0 18 4.5 4.5 0 0 1 0-9 4.5 4.5 0 0 0 0-9Z"/></svg>`,
    };

    // Ordered keyword -> glyph rules; first match wins.
    const RULES = [
        [/chrome|safari|firefox|edge|browser|arc\b/i, "browser"],
        [/terminal|iterm|console|shell/i, "terminal"],
        [/slack|teams|discord|messages|imessage|whatsapp/i, "chat"],
        [/outlook|mail\b/i, "mail"],
        [/zoom|meet|webex|facetime/i, "video"],
        [/word\b|pages\b|docs/i, "document"],
        [/excel|numbers|sheets/i, "sheet"],
        [/finder|explorer/i, "folder"],
        [/code|xcode|intellij|pycharm|webstorm|sublime|vim|studio/i, "code"],
        [/notes|notion|obsidian/i, "note"],
        [/photoshop|illustrator|figma|sketch/i, "design"],
    ];

    function glyphFor(appName) {
        if (!appName) return null;
        for (const [pattern, key] of RULES) {
            if (pattern.test(appName)) return GLYPHS[key];
        }
        return null;
    }

    function initials(appName) {
        return (appName || "?")
            .split(/\s+/)
            .filter(Boolean)
            .map(w => w[0])
            .join("")
            .slice(0, 2)
            .toUpperCase();
    }

    // Returns an HTML string for the icon badge (caller wraps in
    // .ix-app-icon).
    function iconHtml(appName) {
        const glyph = glyphFor(appName);
        return glyph || initials(appName);
    }

    return { iconHtml, initials, glyphFor };
})();
