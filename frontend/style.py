"""Look and feel: CSS and pictures as plain strings. No I/O, no Streamlit.

The CSS targets elements by their Streamlit key: a widget or container created
with key="card-6" gets the CSS class "st-key-card-6".
"""

GREEN = "#2E7D32"
GREEN_DARK = "#1B5E20"
GREEN_SOFT = "#F1F7F1"
ORANGE = "#C2410C"  # dark enough for white text (WCAG AA)
ORANGE_DARK = "#9A3412"
ORANGE_BRIGHT = "#E8710A"

APP_CSS = f"""<style>
/* Page: a thin green-to-orange band on top, less empty space on phones. */
[data-testid="stHeader"] {{
  background-image: linear-gradient(90deg, {GREEN}, {ORANGE_BRIGHT});
  background-size: 100% 4px;
  background-repeat: no-repeat;
}}
[data-testid="stMainBlockContainer"] {{ padding-top: 2.5rem; padding-bottom: 4rem; }}
@media (max-width: 640px) {{
  [data-testid="stMainBlockContainer"] {{ padding: 1.75rem 0.85rem 3rem; }}
}}

/* Header: logo, name and the language toggle on one line when it fits. */
.st-key-header h1 {{
  color: {GREEN_DARK};
  font-size: 2.1rem;
  padding: 0;
}}
@media (max-width: 640px) {{ .st-key-header h1 {{ font-size: 1.7rem; }} }}
.st-key-header {{ padding-bottom: 0.75rem; border-bottom: 1px solid #DCE7DD; }}
/* On phones the language toggle wraps below the name instead of covering it. */
[data-testid="stLayoutWrapper"]:has(> .st-key-brand) {{ min-width: 12rem; }}
.st-key-brand h1 {{ line-height: 1.25; }}
/* Streamlit's heading box is shorter than the big title: keep the subtitle below. */
.st-key-brand [data-testid="stCaptionContainer"] {{ margin-top: 0.8rem; }}
/* The language switch reads English | עברית in both languages. */
.st-key-lang {{ direction: ltr; }}

/* Tabs: tighter on phones so all three fit without scrolling. */
@media (max-width: 640px) {{ [role="tablist"] {{ gap: 0.45rem; }} }}

/* My garden: a grid of cards, three per row, two on phones. */
.st-key-garden-grid {{
  display: grid !important;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1rem;
}}
@media (max-width: 640px) {{
  .st-key-garden-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.7rem; }}
}}
[class*="st-key-card-"] {{
  position: relative;
  background: #FFFFFF;
  box-shadow: 0 1px 3px rgba(27, 94, 32, 0.08);
  transition: box-shadow 0.15s ease, transform 0.15s ease;
}}
/* Same height for every card in a row, with the badge at the bottom. */
.st-key-garden-grid > [data-testid="stLayoutWrapper"] > [class*="st-key-card-"] {{
  height: 100%;
}}
[class*="st-key-card-"] > [data-testid="stElementContainer"]:nth-last-child(2) {{
  margin-top: auto;
}}
[class*="st-key-card-"] [data-testid="stCaptionContainer"] p {{
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
@media (hover: hover) {{
  [class*="st-key-card-"]:hover {{
    box-shadow: 0 8px 20px rgba(27, 94, 32, 0.16);
    transform: translateY(-2px);
  }}
}}
@media (max-width: 640px) {{ [class*="st-key-card-"] {{ padding: 0.55rem !important; }} }}
[class*="st-key-card-"] img {{
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  border-radius: 0.6rem;
}}

/* The whole card is one button: an invisible button stretched over it. */
[class*="st-key-open-"] {{ position: absolute !important; inset: 0; z-index: 1; margin: 0; }}
[class*="st-key-open-"] button {{
  width: 100%;
  height: 100%;
  opacity: 0;
  cursor: pointer;
  border-radius: 0.75rem;
}}
[class*="st-key-open-"] button:focus-visible {{
  opacity: 1;
  color: transparent;
  background: transparent;
  outline: 3px solid {ORANGE_BRIGHT};
  outline-offset: 2px;
}}

/* Plant details. */
.st-key-dlg-photo img {{
  width: 100%;
  max-height: 300px;
  object-fit: cover;
  border-radius: 0.75rem;
}}
.st-key-dlg-watering {{ background: {GREEN_SOFT}; }}
[class*="st-key-water-"] button {{
  background: {ORANGE};
  border-color: {ORANGE};
  color: #FFFFFF;
  font-weight: 600;
}}
[class*="st-key-water-"] button:hover,
[class*="st-key-water-"] button:active {{
  background: {ORANGE_DARK};
  border-color: {ORANGE_DARK};
  color: #FFFFFF;
}}
[class*="st-key-remove-"] button {{ color: #B71C1C; }}

/* Photo candidates: the photo stays small, also when columns stack on phones. */
.st-key-candidates img {{
  width: 100%;
  max-height: 220px;
  object-fit: cover;
  border-radius: 0.6rem;
}}

/* Empty garden. */
.st-key-empty-garden {{ background: {GREEN_SOFT}; padding: 2rem 1rem; }}
</style>"""

# 4:3, shown on cards that have no photo yet: a sprout in a terracotta pot.
PLACEHOLDER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
<rect width="400" height="300" fill="#EEF6EF"/>
<circle cx="200" cy="150" r="96" fill="#DCEDDD"/>
<ellipse cx="200" cy="236" rx="62" ry="8" fill="#C9DFCA"/>
<path d="M200 172 V108" stroke="#2E7D32" stroke-width="7" stroke-linecap="round" fill="none"/>
<path d="M199 138 C172 138 154 122 151 98 C176 98 196 112 199 138 Z" fill="#43A047"/>
<path d="M201 120 C204 94 222 78 248 76 C246 102 228 118 201 120 Z" fill="#2E7D32"/>
<path d="M158 180 H242 L230 232 H170 Z" fill="#E8710A"/>
<rect x="150" y="168" width="100" height="18" rx="5" fill="#C2410C"/>
</svg>"""

# Square logo for the header: the same sprout and pot on leaf green.
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<rect width="64" height="64" rx="16" fill="#2E7D32"/>
<path d="M32 40 V22" stroke="#FFFFFF" stroke-width="3.5" stroke-linecap="round"/>
<path d="M31.5 31 C24 31 19 26.5 18 19.5 C25 19.5 30.5 23.5 31.5 31 Z" fill="#A5D6A7"/>
<path d="M32.5 26 C33.5 19 38.5 14.5 46 14 C45.5 21 40.5 25.5 32.5 26 Z" fill="#FFFFFF"/>
<path d="M21 42 H43 L40 53 H24 Z" fill="#E8710A"/>
<rect x="19" y="38.5" width="26" height="5.5" rx="2" fill="#FFB74D"/>
</svg>"""
