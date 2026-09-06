import html
import copy
import os
import re
import shutil
import subprocess
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple, List

from PyQt5.QtCore import Qt, QUrl, QSizeF, QRectF
from PyQt5.QtGui import QAbstractTextDocumentLayout, QBrush, QColor, QFont, QImage, QLinearGradient, QPainter, QPen, QTextCursor, QTextDocument
from PyQt5.QtPrintSupport import QPrinter

from .dialogs import PAGE_DIMENSIONS_MM


BODY_RE = re.compile(r"<body[^>]*>(.*?)</body>", re.I | re.S)
ASSET_RE = re.compile(r"asset://([0-9a-fA-F-]{8,})")
SCREEN_DPI = 96.0


def body_fragment(qt_html: str) -> str:
    if not qt_html:
        return ""
    m = BODY_RE.search(qt_html)
    return m.group(1) if m else qt_html


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9à-ÿ]+", "-", text, flags=re.I)
    text = text.strip("-")
    return text or "topico"


def ordered_topics(project):
    out = []

    def walk(parent_id, depth=0):
        for topic in project.children_of(parent_id):
            out.append((topic, depth))
            walk(topic.id, depth + 1)

    walk(None, 0)
    return out


def asset_filename(asset) -> str:
    ext = Path(asset.filename).suffix
    if not ext:
        ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/gif": ".gif",
            "image/webp": ".webp",
        }.get(asset.mime, ".bin")
    return asset.id + ext.lower()


def replace_asset_urls(fragment: str, project, prefix: str) -> str:
    def repl(match):
        aid = match.group(1)
        asset = project.assets.get(aid)
        if not asset:
            return ""
        return prefix + asset_filename(asset)
    return ASSET_RE.sub(repl, fragment)


def write_assets(project, folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    for asset in project.assets.values():
        (folder / asset_filename(asset)).write_bytes(asset.bytes())


def topic_file_map(project) -> Dict[str, str]:
    mapping = {}
    for idx, (topic, _depth) in enumerate(ordered_topics(project), 1):
        mapping[topic.id] = f"{idx:03d}-{slugify(topic.title)}.html"
    return mapping


def css_text(project=None) -> str:
    meta = project.meta if project else {}
    family = html.escape(str(meta.get("body_font_family", "Arial")), quote=True)
    body = float(meta.get("body_font_size_pt", 10.5))
    h1 = float(meta.get("heading1_size_pt", 20))
    h2 = float(meta.get("heading2_size_pt", 16))
    h3 = float(meta.get("heading3_size_pt", 13))
    line_height = max(90, int(meta.get("line_height_percent", 118))) / 100.0
    paragraph = float(meta.get("paragraph_spacing_pt", 5))
    accent = str(meta.get("html_accent", "#1769aa"))
    bg = str(meta.get("html_background", "#ffffff"))
    fg = str(meta.get("html_text", "#1f2933"))
    side = str(meta.get("html_sidebar_background", "#f5f7fa"))
    topbar = str(meta.get("html_topbar_background", "#ffffff"))
    sidebar = max(180, min(520, int(meta.get("html_sidebar_width_px", 300))))
    content = max(520, min(1600, int(meta.get("html_content_width_px", 900))))
    tree_lines = bool(meta.get("html_tree_lines", True))
    custom = str(meta.get("html_custom_css", "") or "")
    branch_guide = "border-left:1px solid var(--tree-line);padding-left:12px;margin-left:6px;" if tree_lines else "padding-left:12px;"
    base = f"""
:root {{ --bg:{bg}; --fg:{fg}; --muted:#697386; --line:#d8dee6; --tree-line:#cfd6dd; --accent:{accent}; --side:{side}; --topbar:{topbar}; }}
* {{ box-sizing:border-box; }}
html, body {{ min-height:100%; }}
body {{ margin:0; font-family:'{family}', Arial, Helvetica, sans-serif; font-size:{body}pt; color:var(--fg); background:var(--bg); line-height:{line_height:.2f}; }}
p {{ margin-top:0; margin-bottom:{paragraph}pt; overflow-wrap:anywhere; }}
a {{ color:var(--accent); }}
.site-shell {{ min-height:100vh; display:flex; flex-direction:column; }}
.topbar {{ flex:0 0 auto; min-height:58px; display:flex; align-items:center; justify-content:space-between; gap:18px; padding:9px 22px; background:var(--topbar); border-bottom:1px solid var(--line); }}
.topbar-brand {{ display:flex; align-items:center; gap:10px; min-width:0; color:var(--fg); text-decoration:none; font-weight:700; }}
.topbar-brand img {{ width:34px; height:34px; object-fit:contain; margin:0; }}
.topbar-title {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.language-control {{ display:flex; align-items:center; gap:7px; font-size:9pt; color:var(--muted); white-space:nowrap; }}
.language-control select {{ width:auto; min-width:118px; padding:7px 28px 7px 9px; border:1px solid var(--line); border-radius:7px; background:var(--bg); color:var(--fg); }}
.layout {{ display:flex; flex:1 1 auto; min-height:0; }}
.sidebar {{ width:{sidebar}px; flex:0 0 {sidebar}px; background:var(--side); border-right:1px solid var(--line); padding:20px 16px; overflow:auto; }}
.sidebar-head {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; font-weight:700; }}
.sidebar ul {{ list-style:none; margin:0; padding-left:0; }}
.sidebar li {{ margin:3px 0; min-width:0; }}
.sidebar a {{ color:var(--fg); text-decoration:none; border-radius:5px; padding:5px 7px; display:inline-block; max-width:100%; overflow-wrap:anywhere; }}
.sidebar a:hover {{ text-decoration:underline; }}
.sidebar a.current {{ color:var(--accent); font-weight:700; }}
.tree-branch {{ margin:2px 0; }}
.tree-branch > summary {{ cursor:pointer; list-style:none; display:flex; align-items:center; gap:4px; }}
.tree-branch > summary::-webkit-details-marker {{ display:none; }}
.tree-branch > summary::before {{ content:'›'; width:12px; color:var(--muted); }}
.tree-branch[open] > summary::before {{ transform:rotate(90deg); }}
.tree-children {{ {branch_guide} }}
.tree-leaf {{ padding-left:16px; }}
.auto-toc {{ margin-top:18px; }}
.auto-toc-row {{ padding:7px 0; border-bottom:1px dotted var(--line); }}
.auto-toc-row a {{ text-decoration:none; }}
.content {{ width:min({content}px, calc(100% - {sidebar}px)); max-width:{content}px; margin:0 auto; padding:34px 48px 24px; display:flex; flex-direction:column; min-height:100%; }}
.topic-main {{ flex:1 0 auto; }}
h1 {{ font-size:{h1}pt; margin:0 0 20px; border-bottom:1px solid var(--line); padding-bottom:12px; }}
h2 {{ font-size:{h2}pt; margin-top:30px; }}
h3 {{ font-size:{h3}pt; margin-top:24px; }}
img {{ max-width:100%; height:auto; }}
table {{ border-collapse:collapse; max-width:100%; }}
td, th {{ border:1px solid var(--line); padding:7px 9px; vertical-align:top; }}
pre {{ margin:12px 0 18px; padding:13px 15px; border:1px solid var(--line); border-radius:6px; background:var(--side); color:var(--fg); overflow:auto; white-space:pre; font-family:Consolas,'Cascadia Mono','Courier New',monospace; font-size:.94em; line-height:1.45; }}
code {{ font-family:Consolas,'Cascadia Mono','Courier New',monospace; }}
:not(pre) > code {{ padding:1px 4px; border-radius:4px; background:var(--side); }}
.footer, .site-footer, .footer-slot {{ margin-top:auto; padding:12px 0 0; border-top:1px solid var(--line); color:var(--muted); font-size:9pt; }}
.manual-hf {{ width:100%; display:block; overflow:hidden; flex:0 0 auto; }}
.manual-hf table {{ width:100%; border:0; }}
.manual-hf td, .manual-hf th {{ border:0; padding:0; vertical-align:middle; }}
.manual-header {{ margin-bottom:18px; }}
.manual-footer {{ margin-top:auto; padding-top:18px; }}
.intro-page {{ flex:1 1 auto; width:min({content}px, calc(100% - 36px)); max-width:{content}px; margin:0 auto; padding:48px 36px 24px; display:flex; flex-direction:column; }}
.intro-hero {{ padding:12px 0 26px; }}
.intro-hero img {{ max-height:90px; max-width:260px; margin-bottom:22px; }}
.intro-actions {{ margin:22px 0; display:flex; flex-wrap:wrap; gap:10px; }}
.intro-actions a {{ display:inline-block; padding:9px 13px; border-radius:7px; background:var(--accent); color:#fff; text-decoration:none; }}
.intro-tree {{ margin-top:10px; padding:18px; background:var(--side); border:1px solid var(--line); border-radius:8px; }}
.intro-tree .tree-list {{ list-style:none; padding-left:0; margin:0; }}
.intro-tree a {{ color:var(--fg); text-decoration:none; }}
.lang-content {{ display:none; }}
.lang-content.active {{ display:block; }}
span.lang-content.active {{ display:inline; }}
@media (max-width:800px) {{
  .topbar {{ padding:8px 12px; }} .lang-label {{ display:none; }} .language-control select{{min-width:96px}}
  .layout{{display:block}} .sidebar{{width:100%;border-right:0;border-bottom:1px solid var(--line);max-height:none}}
  .content{{width:100%;max-width:none;padding:26px 20px}} .intro-page{{width:100%;padding:30px 20px}}
}}
""".strip()
    return base + ("\n\n/* CSS personalizado */\n" + custom if custom.strip() else "")

def nav_html(project, mapping: Dict[str, str], current_id: Optional[str] = None, prefix: str = "topics/", multilingual: bool = False, toc_href: Optional[str] = None) -> str:
    languages = project.languages() if hasattr(project, "languages") else [project.meta.get("language", "pt-BR")]
    open_default = bool(project.meta.get("html_tree_expand_default", True))
    default_lang = str(project.meta.get("language", languages[0]))

    ancestors = set()
    if current_id:
        cur = project.topic_by_id(current_id)
        while cur is not None and cur.parent_id:
            ancestors.add(cur.parent_id)
            cur = project.topic_by_id(cur.parent_id)

    def label_for(t):
        if not multilingual or len(languages) <= 1:
            return html.escape(project.topic_title(t, languages[0]) if hasattr(project, "topic_title") else t.title)
        spans = []
        for lang in languages:
            title = project.topic_title(t, lang) if hasattr(project, "topic_title") else t.title
            cls = "lang-content active" if lang == default_lang else "lang-content"
            spans.append(f'<span class="{cls}" data-lang="{html.escape(lang)}">{html.escape(title)}</span>')
        return "".join(spans)

    def eligible(parent_id):
        return [t for t in project.children_of(parent_id) if getattr(t, "kind", "normal") != "toc"]

    def branch(parent_id):
        children = eligible(parent_id)
        if not children:
            return ""
        parts = ['<ul class="tree-list">']
        for t in children:
            href = prefix + mapping[t.id]
            current = ' current' if t.id == current_id else ''
            kids = eligible(t.id)
            if kids:
                open_attr = " open" if (open_default or t.id in ancestors or t.id == current_id) else ""
                parts.append(f'<li><details class="tree-branch"{open_attr}><summary><a class="tree-link{current}" href="{href}">{label_for(t)}</a></summary><div class="tree-children">{branch(t.id)}</div></details></li>')
            else:
                parts.append(f'<li class="tree-leaf"><a class="tree-link{current}" href="{href}">{label_for(t)}</a></li>')
        parts.append('</ul>')
        return "".join(parts)

    parts = ['<div class="sidebar-head"><span>Conteúdo</span></div>']
    if toc_href and bool(project.meta.get("html_toc_enabled", True)):
        parts.append(f'<div class="tree-leaf"><a class="tree-link" href="{toc_href}">☰ {html.escape(str(project.meta.get("html_toc_title", "Sumário")))}</a></div>')
    parts.append(branch(None))
    return "".join(parts)

def _web_band_html(project, section: str, topic=None, asset_prefix="../assets/", language=None) -> str:
    m = project.meta
    if not bool(m.get(f"{section}_enabled", True)):
        return ""
    if topic is not None:
        override = topic.show_header if section == "header" else topic.show_footer
        if override is False:
            return ""
    language = language or str(m.get("language", "pt-BR"))
    topic_title = project.topic_title(topic, language) if topic is not None and hasattr(project, "topic_title") else (topic.title if topic else "")
    ctx = {
        "title": str(m.get("title", "Manual")),
        "author": str(m.get("author", "")),
        "version": str(m.get("version", "")),
        "page": "1",
        "pages": "1",
        "topic": topic_title,
        "category": _topic_category(project, topic.id, language) if topic else "",
        "date": date.today().strftime("%d/%m/%Y"),
        "language": language,
        "footer_text": str(m.get("footer_text", "")),
    }
    fragment = body_fragment(str(m.get(f"{section}_template_html", "<p></p>")))
    if section == "footer" and bool(m.get("footer_logo", False)) and "{{logo}}" not in fragment:
        fragment = "{{logo}} &nbsp; " + fragment
    for key, value in ctx.items():
        fragment = fragment.replace("{{" + key + "}}", html.escape(str(value)))
    logo_id = m.get("logo_asset", "")
    if logo_id in project.assets:
        logo = project.assets[logo_id]
        width = float(m.get(f"{section}_logo_width_mm", m.get("footer_logo_width_mm", 18))) * 3.7795
        fragment = fragment.replace(
            "{{logo}}", f'<img src="{asset_prefix}{asset_filename(logo)}" style="width:{width:.0f}px;height:auto;vertical-align:middle">'
        )
    else:
        fragment = fragment.replace("{{logo}}", "")
    fragment = re.sub(r"\{\{[a-zA-Z0-9_]+\}\}", "", fragment)

    styles = [
        f"min-height:{float(m.get(f'{section}_height_mm', 8 if section == 'header' else 9)):.1f}mm",
        f"padding-left:{float(m.get(f'{section}_padding_left_mm', 2)):.1f}mm",
        f"padding-right:{float(m.get(f'{section}_padding_right_mm', 2)):.1f}mm",
    ]
    kind = str(m.get(f"{section}_background_type", "none"))
    c1 = str(m.get(f"{section}_background_color1", "#ffffff"))
    c2 = str(m.get(f"{section}_background_color2", "#e9edf2"))
    if kind == "solid":
        styles.append(f"background:{c1}")
    elif kind == "gradient":
        direction = {"vertical":"to bottom", "diagonal":"135deg"}.get(
            str(m.get(f"{section}_gradient_direction", "horizontal")), "to right"
        )
        styles.append(f"background:linear-gradient({direction},{c1},{c2})")
    elif kind == "image":
        aid = m.get(f"{section}_background_asset", "")
        if aid in project.assets:
            styles.append(f"background-image:url('{asset_prefix}{asset_filename(project.assets[aid])}')")
            fit = str(m.get(f"{section}_background_fit", "cover"))
            styles.append("background-position:center")
            styles.append("background-repeat:no-repeat")
            styles.append("background-size:100% 100%" if fit == "stretch" else ("contain" if fit == "contain" else "cover"))
    if bool(m.get(f"{section}_separator_enabled", True)):
        edge = "border-bottom" if section == "header" else "border-top"
        styles.append(
            f"{edge}:{float(m.get(f'{section}_separator_width_pt',0.8)):.1f}pt solid {m.get(f'{section}_separator_color','#c8cdd3')}"
        )
    return f'<div class="manual-hf manual-{section}" style="{";".join(styles)}">{fragment}</div>'


def _language_script(default_lang: str) -> str:
    return f"""(function(){{
  function apply(lang){{
    document.documentElement.setAttribute('lang', lang);
    document.querySelectorAll('.lang-content').forEach(function(el){{
      el.classList.toggle('active', el.getAttribute('data-lang') === lang);
    }});
    document.querySelectorAll('.language-select').forEach(function(sel){{ sel.value = lang; }});
    try {{ localStorage.setItem('manual-language', lang); }} catch(e) {{}}
  }}
  var initial = '{default_lang}';
  try {{ initial = localStorage.getItem('manual-language') || initial; }} catch(e) {{}}
  document.querySelectorAll('.language-select').forEach(function(sel){{
    sel.addEventListener('change', function(){{ apply(this.value); }});
  }});
  apply(initial);
}})();"""


def _language_select(project):
    languages = project.languages() if hasattr(project, "languages") else [project.meta.get("language", "pt-BR")]
    if len(languages) <= 1:
        return ""
    opts = ''.join(f'<option value="{html.escape(lang)}">{html.escape(lang)}</option>' for lang in languages)
    return '<label class="language-control" title="Selecionar idioma"><span class="lang-icon">🌐</span><span class="lang-label">Idioma</span><select class="language-select">' + opts + '</select></label>'


def _web_toc_html(project, mapping, language, prefix="topics/"):
    parts = ['<div class="auto-toc">']
    for topic, depth in ordered_topics(project):
        if bool(getattr(topic, "exclude_from_toc", False)) or getattr(topic, "kind", "normal") == "toc":
            continue
        title = project.topic_title(topic, language) if hasattr(project, "topic_title") else topic.title
        parts.append(
            f'<div class="auto-toc-row" style="padding-left:{depth*18}px"><a href="{prefix}{mapping[topic.id]}">{html.escape(title)}</a></div>'
        )
    parts.append('</div>')
    return ''.join(parts)


def _web_favicon(project, prefix="assets/"):
    aid = project.meta.get("html_manual_icon_asset", "") or project.meta.get("logo_asset", "")
    if aid in project.assets:
        return f'<link rel="icon" href="{prefix}{asset_filename(project.assets[aid])}">'
    return ""


def _web_brand(project, href, asset_prefix):
    title = html.escape(str(project.meta.get("title", "Manual")))
    aid = project.meta.get("logo_asset", "")
    logo = ""
    if aid in project.assets:
        logo = f'<img src="{asset_prefix}{asset_filename(project.assets[aid])}" alt="">'
    return f'<a class="topbar-brand" href="{href}">{logo}<span class="topbar-title">{title}</span></a>'



def _asset_data_uri(asset) -> str:
    mime = str(getattr(asset, "mime", "") or "application/octet-stream")
    data_b64 = str(getattr(asset, "data_b64", "") or "")
    return f"data:{mime};base64,{data_b64}"


def _inline_preview_assets(fragment: str, project) -> str:
    """Substitui referências de assets por data URIs para a prévia 100% em RAM."""
    if not fragment:
        return ""
    out = str(fragment)
    for aid, asset in project.assets.items():
        uri = _asset_data_uri(asset)
        out = out.replace(f"asset://{aid}", uri)
        filename = asset_filename(asset)
        for prefix in ("assets/", "../assets/", "../../assets/"):
            out = out.replace(prefix + filename, uri)
    return out


def build_html_preview_document(project, meta_override=None, current_topic_id=None, language=None) -> str:
    """Compila em memória um WebHelp navegável para QWebEngineView.

    Nenhuma pasta temporária é criada. CSS, JavaScript, árvore, cabeçalho,
    rodapé, tópicos e imagens são entregues no próprio HTML usando data URIs.
    """
    preview_project = copy.copy(project)
    preview_project.meta = dict(project.meta)
    if meta_override:
        preview_project.meta.update(dict(meta_override))

    languages = preview_project.languages() if hasattr(preview_project, "languages") else [preview_project.meta.get("language", "pt-BR")]
    default_lang = str(language or preview_project.meta.get("language", languages[0]))
    if default_lang not in languages:
        default_lang = str(preview_project.meta.get("language", languages[0]))
    ordered = [(t, d) for t, d in ordered_topics(preview_project) if getattr(t, "kind", "normal") != "toc"]
    current_topic = preview_project.topic_by_id(current_topic_id) if current_topic_id else None
    if current_topic is None or getattr(current_topic, "kind", "normal") == "toc":
        current_topic = ordered[0][0] if ordered else None

    def lang_spans(topic, content=False):
        bits = []
        for lang in languages:
            cls = "lang-content active" if lang == default_lang else "lang-content"
            if content:
                raw = preview_project.topic_html(topic, lang) if hasattr(preview_project, "topic_html") else topic.html
                value = _inline_preview_assets(body_fragment(raw), preview_project)
                bits.append(f'<div class="{cls}" data-lang="{html.escape(lang)}">{value}</div>')
            else:
                raw = preview_project.topic_title(topic, lang) if hasattr(preview_project, "topic_title") else topic.title
                value = html.escape(str(raw))
                bits.append(f'<span class="{cls}" data-lang="{html.escape(lang)}">{value}</span>')
        return "".join(bits)

    def eligible(parent_id):
        return [t for t in preview_project.children_of(parent_id) if getattr(t, "kind", "normal") != "toc"]

    def branch(parent_id):
        children = eligible(parent_id)
        if not children:
            return ""
        parts = ['<ul class="tree-list">']
        for t in children:
            kids = eligible(t.id)
            current = " current" if current_topic is not None and t.id == current_topic.id else ""
            link = f'<a class="tree-link preview-nav{current}" href="#" data-page="topic-{t.id}">{lang_spans(t)}</a>'
            if kids:
                open_attr = " open" if bool(preview_project.meta.get("html_tree_expand_default", True)) else ""
                parts.append(f'<li><details class="tree-branch"{open_attr}><summary>{link}</summary><div class="tree-children">{branch(t.id)}</div></details></li>')
            else:
                parts.append(f'<li class="tree-leaf">{link}</li>')
        parts.append('</ul>')
        return "".join(parts)

    toc_enabled = bool(preview_project.meta.get("html_toc_enabled", True))
    nav = ['<div class="sidebar-head"><span>Conteúdo</span></div>']
    if bool(preview_project.meta.get("html_intro_enabled", True)):
        nav.append('<div class="tree-leaf"><a class="tree-link preview-nav" href="#" data-page="intro">⌂ Início</a></div>')
    if toc_enabled:
        nav.append(f'<div class="tree-leaf"><a class="tree-link preview-nav" href="#" data-page="toc">☰ {html.escape(str(preview_project.meta.get("html_toc_title", "Sumário")))}</a></div>')
    nav.append(branch(None))

    title = html.escape(str(preview_project.meta.get("title", "Manual")))
    version = html.escape(str(preview_project.meta.get("version", "")))
    author = html.escape(str(preview_project.meta.get("author", "")))
    footer_text = html.escape(str(preview_project.meta.get("footer_text", "")))
    project_url = str(preview_project.meta.get("html_project_url", "") or "").strip()

    logo_id = preview_project.meta.get("logo_asset", "")
    brand_logo = ""
    if logo_id in preview_project.assets:
        brand_logo = f'<img src="{_asset_data_uri(preview_project.assets[logo_id])}" alt="">'
    brand = f'<a class="topbar-brand preview-nav" href="#" data-page="intro">{brand_logo}<span class="topbar-title">{title}</span></a>'
    language_select = _language_select(preview_project)

    pages = []
    intro_title = html.escape(str(preview_project.meta.get("html_intro_title", "") or preview_project.meta.get("title", "Manual")))
    subtitle = html.escape(str(preview_project.meta.get("html_intro_subtitle", "")))
    intro_body = _inline_preview_assets(body_fragment(str(preview_project.meta.get("html_intro_body_html", "") or "")), preview_project)
    intro_bits = []
    if bool(preview_project.meta.get("html_intro_show_logo", True)) and logo_id in preview_project.assets:
        intro_bits.append(f'<img src="{_asset_data_uri(preview_project.assets[logo_id])}" alt="Logo">')
    intro_bits.append(f'<h1>{intro_title}</h1>')
    if subtitle:
        intro_bits.append(f'<p class="intro-subtitle">{subtitle}</p>')
    if bool(preview_project.meta.get("html_intro_show_author", True)) and author:
        intro_bits.append(f'<p>{author}</p>')
    if bool(preview_project.meta.get("html_intro_show_version", True)) and version:
        intro_bits.append(f'<p>Versão {version}</p>')
    if intro_body:
        intro_bits.append(intro_body)
    if bool(preview_project.meta.get("html_intro_show_toc", True)) and toc_enabled:
        intro_bits.append(f'<div class="intro-actions"><a class="preview-nav" href="#" data-page="toc">{html.escape(str(preview_project.meta.get("html_toc_title", "Sumário")))}</a></div>')
    if project_url and bool(preview_project.meta.get("html_show_project_link", True)):
        intro_bits.append(f'<p class="project-link"><a target="_blank" rel="noopener" href="{html.escape(project_url, quote=True)}">Projeto / suporte</a></p>')
    pages.append('<section class="preview-page" data-page-id="intro"><div class="topic-main intro-hero">' + ''.join(intro_bits) + '</div><div class="site-footer">' + footer_text + '</div></section>')

    if toc_enabled:
        toc_rows = []
        for topic, depth in ordered:
            if bool(getattr(topic, "exclude_from_toc", False)):
                continue
            toc_rows.append(f'<div class="auto-toc-row" style="padding-left:{depth*18}px"><a class="preview-nav" href="#" data-page="topic-{topic.id}">{lang_spans(topic)}</a></div>')
        pages.append(f'<section class="preview-page" data-page-id="toc"><div class="topic-main"><h1>{html.escape(str(preview_project.meta.get("html_toc_title", "Sumário")))}</h1><p>{html.escape(str(preview_project.meta.get("html_toc_description", "")))}</p><div class="auto-toc">{"".join(toc_rows)}</div></div><div class="site-footer">{footer_text}</div></section>')

    for topic, _depth in ordered:
        headers = []
        footers = []
        for lang in languages:
            cls = "lang-content active" if lang == default_lang else "lang-content"
            h = _inline_preview_assets(_web_band_html(preview_project, "header", topic, "assets/", lang), preview_project)
            f = _inline_preview_assets(_web_band_html(preview_project, "footer", topic, "assets/", lang), preview_project)
            headers.append(f'<div class="{cls}" data-lang="{html.escape(lang)}">{h}</div>')
            footers.append(f'<div class="{cls} footer-slot" data-lang="{html.escape(lang)}">{f}</div>')
        pages.append(f'<section class="preview-page" data-page-id="topic-{topic.id}">{"".join(headers)}<div class="topic-main"><h1>{lang_spans(topic)}</h1>{lang_spans(topic, content=True)}</div>{"".join(footers)}</section>')

    initial = f"topic-{current_topic.id}" if current_topic is not None else ("intro" if bool(preview_project.meta.get("html_intro_enabled", True)) else "toc")
    preview_css = css_text(preview_project) + "\n.preview-page{display:none;flex:1 1 auto;min-height:calc(100vh - 88px);flex-direction:column}.preview-page.active{display:flex}.project-link{margin-top:18px}.preview-banner{font-size:8.5pt;color:var(--muted);padding:4px 10px;border-bottom:1px dashed var(--line);background:var(--side)}"
    script = _language_script(default_lang) + f"""
(function(){{
  function showPage(id){{
    document.querySelectorAll('.preview-page').forEach(function(p){{p.classList.toggle('active', p.getAttribute('data-page-id')===id);}});
    document.querySelectorAll('.preview-nav[data-page]').forEach(function(a){{a.classList.toggle('current', a.getAttribute('data-page')===id);}});
  }}
  document.querySelectorAll('.preview-nav[data-page]').forEach(function(a){{a.addEventListener('click',function(e){{e.preventDefault();showPage(this.getAttribute('data-page'));}});}});
  showPage({initial!r});
}})();
"""
    return f'''<!doctype html><html lang="{html.escape(default_lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>{preview_css}</style></head><body><div class="site-shell"><header class="topbar">{brand}{language_select}</header><div class="preview-banner">Pré-compilação em RAM • nenhuma pasta temporária é criada</div><div class="layout"><nav class="sidebar">{"".join(nav)}</nav><article class="content">{"".join(pages)}</article></div></div><script>{script}</script></body></html>'''

def export_html(project, output_dir: str, create_subfolder: bool = True):
    """Exporta o WebHelp.

    Na exportação normal, a pasta escolhida pelo usuário é sempre tratada como
    pasta-pai e o manual é colocado em uma subpasta própria. O modo interno do
    compilador CHM pode desativar isso para manter a estrutura esperada pelo HHC.
    """
    parent = Path(output_dir)
    if create_subfolder:
        folder_name = slugify(str(project.meta.get("title", "manual"))) + "_html"
        out = parent / folder_name
        if out.exists():
            shutil.rmtree(out)
    else:
        out = parent
    out.mkdir(parents=True, exist_ok=True)
    topics_dir = out / "topics"
    assets_dir = out / "assets"
    topics_dir.mkdir(exist_ok=True)
    write_assets(project, assets_dir)
    (out / "style.css").write_text(css_text(project), encoding="utf-8")

    languages = project.languages() if hasattr(project, "languages") else [project.meta.get("language", "pt-BR")]
    default_lang = str(project.meta.get("language", languages[0]))
    (out / "language.js").write_text(_language_script(default_lang), encoding="utf-8")
    mapping = topic_file_map(project)
    title_raw = str(project.meta.get("title", "Manual"))
    title = html.escape(title_raw)
    footer = html.escape(str(project.meta.get("footer_text", "")))
    version = html.escape(str(project.meta.get("version", "")))
    author = html.escape(str(project.meta.get("author", "")))
    logo_id = project.meta.get("logo_asset", "")
    logo_html = ""
    if logo_id in project.assets and bool(project.meta.get("html_intro_show_logo", True)):
        logo_html = f'<img src="assets/{asset_filename(project.assets[logo_id])}" alt="Logo">'

    toc_enabled = bool(project.meta.get("html_toc_enabled", True))
    toc_href_root = "sumario.html" if toc_enabled else None
    root_tree = nav_html(project, mapping, prefix="topics/", multilingual=True, toc_href=toc_href_root)
    topbar = f'<header class="topbar">{_web_brand(project, "index.html", "assets/")}{_language_select(project)}</header>'

    intro_title = html.escape(str(project.meta.get("html_intro_title", "") or title_raw))
    intro_subtitle = html.escape(str(project.meta.get("html_intro_subtitle", "")))
    intro_body = replace_asset_urls(body_fragment(str(project.meta.get("html_intro_body_html", "") or "")), project, "assets/")
    intro_bits = []
    if logo_html:
        intro_bits.append(logo_html)
    intro_bits.append(f'<h1>{intro_title}</h1>')
    if intro_subtitle:
        intro_bits.append(f'<p class="intro-subtitle">{intro_subtitle}</p>')
    if bool(project.meta.get("html_intro_show_author", True)) and author:
        intro_bits.append(f'<p>{author}</p>')
    if bool(project.meta.get("html_intro_show_version", True)) and version:
        intro_bits.append(f'<p>Versão {version}</p>')
    if intro_body:
        intro_bits.append(intro_body)
    if bool(project.meta.get("html_intro_show_toc", True)) and toc_enabled:
        intro_bits.append('<div class="intro-actions"><a href="sumario.html">' + html.escape(str(project.meta.get("html_toc_title", "Sumário"))) + '</a></div>')
    project_url = str(project.meta.get("html_project_url", "") or "").strip()
    if project_url and bool(project.meta.get("html_show_project_link", True)):
        intro_bits.append('<p class="project-link"><a target="_blank" rel="noopener" href="' + html.escape(project_url, quote=True) + '">Projeto / suporte</a></p>')

    if bool(project.meta.get("html_intro_enabled", True)):
        index_main = '<main class="intro-page"><section class="intro-hero">' + ''.join(intro_bits) + '</section><section class="intro-tree">' + root_tree + '</section>' + (f'<div class="site-footer">{footer}</div>' if footer else '<div class="site-footer"></div>') + '</main>'
    else:
        index_main = '<main class="intro-page"><section class="intro-tree">' + root_tree + '</section><div class="site-footer">' + footer + '</div></main>'
    index = f'''<!doctype html><html lang="{html.escape(default_lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>{_web_favicon(project, "assets/")}<link rel="stylesheet" href="style.css"></head>
<body><div class="site-shell">{topbar}{index_main}</div><script src="language.js"></script></body></html>'''
    (out / "index.html").write_text(index, encoding="utf-8")

    # Sumário HTML é sempre uma página gerada pelo exportador, não um tópico da árvore.
    if toc_enabled:
        legacy_toc = next((t for t in project.topics if getattr(t, "kind", "normal") == "toc"), None)
        toc_variants = []
        for lang in languages:
            cls = "lang-content active" if lang == default_lang else "lang-content"
            toc_title = html.escape(str(project.meta.get("html_toc_title", "Sumário")))
            desc = html.escape(str(project.meta.get("html_toc_description", "")))
            legacy = ""
            if legacy_toc is not None:
                legacy = replace_asset_urls(body_fragment(project.topic_html(legacy_toc, lang) if hasattr(project, "topic_html") else legacy_toc.html), project, "assets/")
            desc_html = f'<p>{desc}</p>' if desc else ''
            toc_variants.append(f'<div class="{cls}" data-lang="{html.escape(lang)}"><h1>{toc_title}</h1>{desc_html}{legacy}{_web_toc_html(project, mapping, lang, "topics/")}</div>')
        toc_page = f'''<!doctype html><html lang="{html.escape(default_lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(str(project.meta.get("html_toc_title", "Sumário")))} — {title}</title>{_web_favicon(project, "assets/")}<link rel="stylesheet" href="style.css"></head>
<body><div class="site-shell"><header class="topbar">{_web_brand(project, "index.html", "assets/")}{_language_select(project)}</header><div class="layout"><nav class="sidebar">{nav_html(project, mapping, prefix="topics/", multilingual=True, toc_href="sumario.html")}</nav><article class="content"><div class="topic-main">{''.join(toc_variants)}</div><div class="site-footer">{footer}</div></article></div></div><script src="language.js"></script></body></html>'''
        (out / "sumario.html").write_text(toc_page, encoding="utf-8")

    for topic, _depth in ordered_topics(project):
        if getattr(topic, "kind", "normal") == "toc":
            continue
        variants, headers, footers, titles = [], [], [], []
        for lang in languages:
            topic_title = project.topic_title(topic, lang) if hasattr(project, "topic_title") else topic.title
            fragment = replace_asset_urls(body_fragment(project.topic_html(topic, lang) if hasattr(project, "topic_html") else topic.html), project, "../assets/")
            cls = "lang-content active" if lang == default_lang else "lang-content"
            titles.append(f'<span class="{cls}" data-lang="{html.escape(lang)}">{html.escape(topic_title)}</span>')
            headers.append(f'<div class="{cls}" data-lang="{html.escape(lang)}">{_web_band_html(project, "header", topic, "../assets/", lang)}</div>')
            footers.append(f'<div class="{cls} footer-slot" data-lang="{html.escape(lang)}">{_web_band_html(project, "footer", topic, "../assets/", lang)}</div>')
            variants.append(f'<div class="{cls}" data-lang="{html.escape(lang)}">{fragment}</div>')
        page_title = project.topic_title(topic, default_lang) if hasattr(project, "topic_title") else topic.title
        sidebar = nav_html(project, mapping, current_id=topic.id, prefix="", multilingual=True, toc_href="../sumario.html" if toc_enabled else None)
        page = f'''<!doctype html><html lang="{html.escape(default_lang)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(page_title)} — {title}</title>{_web_favicon(project, "../assets/")}<link rel="stylesheet" href="../style.css"></head>
<body><div class="site-shell"><header class="topbar">{_web_brand(project, "../index.html", "../assets/")}{_language_select(project)}</header><div class="layout"><nav class="sidebar">{sidebar}</nav><article class="content">{''.join(headers)}<div class="topic-main"><h1>{''.join(titles)}</h1>{''.join(variants)}</div>{''.join(footers)}</article></div></div><script src="../language.js"></script></body></html>'''
        (topics_dir / mapping[topic.id]).write_text(page, encoding="utf-8")
    return str(out / "index.html")

def _register_assets(document: QTextDocument, project):
    for aid, asset in project.assets.items():
        img = QImage.fromData(asset.bytes())
        if not img.isNull():
            document.addResource(QTextDocument.ImageResource, QUrl("asset://" + aid), img)


def _toc_html(project, language):
    parts = []
    for topic, depth in ordered_topics(project):
        if bool(getattr(topic, "exclude_from_toc", False)) or getattr(topic, "kind", "normal") == "toc":
            continue
        indent = depth * 18
        weight = 600 if depth == 0 else 400
        title = project.topic_title(topic, language) if hasattr(project, "topic_title") else topic.title
        parts.append(f'<p style="margin-left:{indent}px; font-weight:{weight};">{html.escape(title)}</p>')
    return ''.join(parts)


def _combined_document_html(project, language=None, include_terminal_break=False) -> str:
    m = project.meta
    language = language or str(m.get("language", "pt-BR"))
    parts = [f'<a name="lang-{html.escape(language)}">&#8203;</a>']
    title = html.escape(str(m.get("pdf_cover_title", "") or m.get("title", "Manual")))
    author = html.escape(str(m.get("author", "")))
    version = html.escape(str(m.get("version", "")))
    logo_id = m.get("logo_asset", "")

    if bool(m.get("cover_enabled", True)):
        parts.append('<a name="section-cover">&#8203;</a>')
        parts.append('<div style="text-align:center; margin-top:55mm;">')
        if logo_id in project.assets:
            parts.append(f'<img src="asset://{logo_id}" width="210" style="max-height:90px;">')
        parts.append(f'<div style="font-size:{float(m.get("heading1_size_pt",20))*1.45:.1f}pt; font-weight:600; margin-top:24px;">{title}</div>')
        if author:
            parts.append(f'<p style="text-align:center; font-size:12pt; margin-top:16px;">{author}</p>')
        if version:
            parts.append(f'<p style="text-align:center; font-size:11pt;">Versão {version}</p>')
        if len(project.languages()) > 1:
            parts.append(f'<p style="text-align:center; font-size:10pt;">{html.escape(language)}</p>')
        parts.append('</div><div style="page-break-after:always"></div>')

    has_special_toc = any(getattr(t, "kind", "normal") == "toc" for t in project.topics)
    if bool(m.get("toc_enabled", True)) and not has_special_toc:
        parts.append('<a name="section-auto-toc">&#8203;</a>')
        parts.append(f'<div style="font-size:{float(m.get("heading1_size_pt",20))}pt; font-weight:700; margin-bottom:16px;">Sumário</div>')
        parts.append(_toc_html(project, language))
        parts.append('<div style="page-break-after:always"></div>')

    counters = [0, 0, 0, 0, 0]
    for topic, depth in ordered_topics(project):
        topic_title = project.topic_title(topic, language) if hasattr(project, "topic_title") else topic.title
        topic_body = project.topic_html(topic, language) if hasattr(project, "topic_html") else topic.html
        parts.append(f'<a name="topic-{topic.id}">&#8203;</a>')
        kind = getattr(topic, "kind", "normal")
        if kind == "toc":
            parts.append(f'<div style="font-size:{float(m.get("heading1_size_pt",20))}pt; font-weight:700; margin-bottom:16px;">{html.escape(topic_title)}</div>')
            parts.append(body_fragment(topic_body))
            parts.append(_toc_html(project, language))
            parts.append('<div style="page-break-after:always"></div>')
            continue
        d = min(depth, 4)
        counters[d] += 1
        for j in range(d + 1, len(counters)):
            counters[j] = 0
        num = ".".join(str(counters[j]) for j in range(d + 1) if counters[j] > 0)
        level = min(d + 1, 4)
        parts.append(f'<h{level}>{num} {html.escape(topic_title)}</h{level}>')
        parts.append(body_fragment(topic_body))

    if include_terminal_break:
        parts.append('<div style="page-break-after:always"></div>')

    family = html.escape(str(m.get("body_font_family", "Arial")), quote=True)
    body = float(m.get("body_font_size_pt", 10.5))
    h1 = float(m.get("heading1_size_pt", 20))
    h2 = float(m.get("heading2_size_pt", 16))
    h3 = float(m.get("heading3_size_pt", 13))
    line_height = int(m.get("line_height_percent", 118))
    paragraph = float(m.get("paragraph_spacing_pt", 5))
    css = (
        f"body{{font-family:'{family}';font-size:{body}pt;line-height:{line_height}%;color:#20252b;}}"
        f"p{{margin-top:0;margin-bottom:{paragraph}pt;}}"
        f"h1{{font-size:{h1}pt;margin-top:15pt;margin-bottom:8pt;}}"
        f"h2{{font-size:{h2}pt;margin-top:13pt;margin-bottom:7pt;}}"
        f"h3{{font-size:{h3}pt;margin-top:11pt;margin-bottom:6pt;}}"
        "h4{font-size:11pt;margin-top:10pt;margin-bottom:5pt;}"
        "img{max-width:100%;height:auto;} table{max-width:100%;}"
    )
    return f"<html><head><style>{css}</style></head><body>{''.join(parts)}</body></html>"

def _page_dimensions_mm(project):
    # QPrinter aplica a orientação depois do tamanho base do papel.
    m = project.meta
    return PAGE_DIMENSIONS_MM.get(str(m.get("page_size", "A4")), PAGE_DIMENSIONS_MM["A4"])


def _clamp_document_images(document: QTextDocument, project, max_width: float):
    """Limita imagens antigas/grandes à largura útil sem distorcer a proporção."""
    block = document.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid() and frag.charFormat().isImageFormat():
                fmt = frag.charFormat().toImageFormat()
                name = fmt.name()
                native = None
                if name.startswith("asset://"):
                    aid = name[len("asset://"):]
                    asset = project.assets.get(aid)
                    if asset:
                        native = QImage.fromData(asset.bytes())
                w = float(fmt.width()) if fmt.width() > 0 else (float(native.width()) if native and not native.isNull() else 0.0)
                h = float(fmt.height()) if fmt.height() > 0 else (float(native.height()) if native and not native.isNull() else 0.0)
                if w <= 0:
                    w = max_width * 0.7
                if h <= 0 and native and not native.isNull():
                    h = w * native.height() / float(max(1, native.width()))
                if w > max_width:
                    ratio = max_width / w
                    w = max_width
                    h = h * ratio if h > 0 else 0
                if h <= 0:
                    h = w * 0.65
                fmt.setWidth(w)
                fmt.setHeight(h)
                c = QTextCursor(document)
                c.setPosition(frag.position())
                c.setPosition(frag.position() + frag.length(), QTextCursor.KeepAnchor)
                c.setCharFormat(fmt)
            it += 1
        block = block.next()


def _topic_category(project, topic_id: str, language=None) -> str:
    topic = project.topic_by_id(topic_id) if topic_id else None
    if not topic:
        return ""
    current = topic
    seen = set()
    while current.parent_id and current.parent_id not in seen:
        seen.add(current.id)
        parent = project.topic_by_id(current.parent_id)
        if not parent:
            break
        current = parent
    return project.topic_title(current, language) if hasattr(project, "topic_title") and language else current.title


def _page_contexts(document: QTextDocument, project, logical_h: float, page_count: int):
    """Resolve idioma, tópico e regras de cabeçalho/rodapé por página através de âncoras."""
    anchors = []
    block = document.begin()
    while block.isValid():
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            if frag.isValid():
                fmt = frag.charFormat()
                if fmt.isAnchor():
                    for name in fmt.anchorNames():
                        if name.startswith("topic-") or name.startswith("section-") or name.startswith("lang-"):
                            y = float(document.documentLayout().blockBoundingRect(block).top())
                            anchors.append((max(0, int(y // max(1.0, logical_h))), name))
            it += 1
        block = block.next()
    anchors.sort(key=lambda item: item[0])

    out = []
    active_topic = ""
    active_language = str(project.meta.get("language", "pt-BR"))
    section = ""
    idx = 0
    for page in range(page_count):
        while idx < len(anchors) and anchors[idx][0] <= page:
            name = anchors[idx][1]
            if name.startswith("lang-"):
                active_language = name[len("lang-"):]
                active_topic = ""; section = ""
            elif name.startswith("section-"):
                section = name[len("section-"):]
                active_topic = ""
            elif name.startswith("topic-"):
                active_topic = name[len("topic-"):]
                section = "topic"
            idx += 1
        topic = project.topic_by_id(active_topic) if active_topic else None
        show_header = False if section in ("cover", "auto-toc") else True
        show_footer = False if section in ("cover", "auto-toc") else True
        if topic is not None:
            if topic.show_header is not None: show_header = bool(topic.show_header)
            if topic.show_footer is not None: show_footer = bool(topic.show_footer)
        out.append({
            "topic": project.topic_title(topic, active_language) if topic and hasattr(project, "topic_title") else (topic.title if topic else ""),
            "category": _topic_category(project, active_topic, active_language),
            "language": active_language,
            "show_header": show_header,
            "show_footer": show_footer,
        })
    return out

def _template_context(project, page_index, page_count, page_ctx=None):
    m = project.meta
    ctx = dict(page_ctx or {})
    page_language = ctx.get("language", str(m.get("language", "")))
    ctx.update({
        "title": str(m.get("title", "Manual")),
        "author": str(m.get("author", "")),
        "version": str(m.get("version", "")),
        "page": str(int(m.get("pdf_page_number_start", 1)) + page_index),
        "pages": str(int(m.get("pdf_page_number_start", 1)) + page_count - 1),
        "date": date.today().strftime("%d/%m/%Y"),
        "language": page_language,
        "footer_text": str(m.get("footer_text", "")),
    })
    return ctx


def _replace_template_tokens(template_html: str, project, section: str, ctx: dict) -> str:
    result = template_html or "<p></p>"
    # Compatibilidade com projetos da versão anterior, onde o logo do rodapé
    # era habilitado por uma caixa separada e não pelo token {{logo}}.
    if section == "footer" and bool(project.meta.get("footer_logo", False)) and "{{logo}}" not in result:
        body_match = BODY_RE.search(result)
        if body_match:
            body = "{{logo}} &nbsp; " + body_match.group(1)
            result = result[:body_match.start(1)] + body + result[body_match.end(1):]
        else:
            result = "{{logo}} &nbsp; " + result
    for key, value in ctx.items():
        result = result.replace("{{" + key + "}}", html.escape(str(value)))

    logo_id = project.meta.get("logo_asset", "")
    if logo_id in project.assets:
        logo_mm = float(project.meta.get(f"{section}_logo_width_mm", project.meta.get("footer_logo_width_mm", 18)))
        logo_logical_px = max(8.0, logo_mm * SCREEN_DPI / 25.4)
        logo_html = f'<img src="asset://{logo_id}" width="{logo_logical_px:.1f}">'
    else:
        logo_html = ""
    result = result.replace("{{logo}}", logo_html)
    # Remove tokens desconhecidos em vez de deixá-los impressos por acidente.
    result = re.sub(r"\{\{[a-zA-Z0-9_]+\}\}", "", result)
    return result


def _draw_band_background(painter, project, section: str, rect: QRectF):
    m = project.meta
    kind = str(m.get(f"{section}_background_type", "none"))
    if kind == "none":
        return
    opacity = max(0.0, min(1.0, float(m.get(f"{section}_background_opacity", 100)) / 100.0))
    painter.save()
    painter.setOpacity(opacity)
    if kind == "solid":
        painter.fillRect(rect, QColor(str(m.get(f"{section}_background_color1", "#ffffff"))))
    elif kind == "gradient":
        c1 = QColor(str(m.get(f"{section}_background_color1", "#ffffff")))
        c2 = QColor(str(m.get(f"{section}_background_color2", "#e9edf2")))
        direction = str(m.get(f"{section}_gradient_direction", "horizontal"))
        if direction == "vertical":
            grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        elif direction == "diagonal":
            grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        else:
            grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
        grad.setColorAt(0.0, c1)
        grad.setColorAt(1.0, c2)
        painter.fillRect(rect, QBrush(grad))
    elif kind == "image":
        aid = m.get(f"{section}_background_asset", "")
        asset = project.assets.get(aid)
        image = QImage.fromData(asset.bytes()) if asset else QImage()
        if not image.isNull():
            mode = str(m.get(f"{section}_background_fit", "cover"))
            if mode == "stretch":
                painter.drawImage(rect, image)
            else:
                keep_mode = Qt.KeepAspectRatioByExpanding if mode == "cover" else Qt.KeepAspectRatio
                scaled = image.scaled(
                    max(1, int(rect.width())), max(1, int(rect.height())), keep_mode, Qt.SmoothTransformation
                )
                x = rect.left() + (rect.width() - scaled.width()) / 2.0
                y = rect.top() + (rect.height() - scaled.height()) / 2.0
                painter.save()
                painter.setClipRect(rect)
                painter.drawImage(QRectF(x, y, scaled.width(), scaled.height()), scaled)
                painter.restore()
    painter.restore()


def _draw_template_document(painter, project, section: str, rect: QRectF, dpi: float, ctx: dict):
    """Renderiza HTML rico do cabeçalho/rodapé mantendo tipografia e tokens."""
    scale = dpi / SCREEN_DPI
    mm = dpi / 25.4
    pad_left = float(project.meta.get(f"{section}_padding_left_mm", 2)) * mm
    pad_right = float(project.meta.get(f"{section}_padding_right_mm", 2)) * mm
    inner = QRectF(rect.left() + pad_left, rect.top(), max(1.0, rect.width() - pad_left - pad_right), rect.height())
    logical_w = inner.width() / scale
    logical_h = inner.height() / scale

    doc = QTextDocument()
    body_font = QFont(str(project.meta.get("body_font_family", "Arial")))
    body_font.setPointSizeF(8.5)
    doc.setDefaultFont(body_font)
    doc.setDocumentMargin(0)
    doc.setDefaultStyleSheet(
        "body{margin:0;padding:0;} p{margin:0;} table{border-collapse:collapse;width:100%;} "
        "td{padding:0;vertical-align:middle;} img{vertical-align:middle;}"
    )
    _register_assets(doc, project)
    template = str(project.meta.get(f"{section}_template_html", "<p></p>"))
    doc.setHtml(_replace_template_tokens(template, project, section, ctx))
    _register_assets(doc, project)
    doc.setTextWidth(logical_w)
    doc_h = min(logical_h, max(1.0, float(doc.documentLayout().documentSize().height())))
    y_offset = max(0.0, (logical_h - doc_h) / 2.0)

    painter.save()
    painter.setClipRect(inner)
    painter.translate(inner.left(), inner.top())
    painter.scale(scale, scale)
    painter.translate(0, y_offset)
    doc.drawContents(painter, QRectF(0, 0, logical_w, logical_h))
    painter.restore()


def _draw_header_footer(painter, project, page_rect, page_index, page_count, dpi, content_left, content_right, page_ctx=None):
    m = project.meta
    mm = dpi / 25.4
    margin_top = float(m.get("margin_top_mm", 16)) * mm
    margin_bottom = float(m.get("margin_bottom_mm", 16)) * mm
    header_h = float(m.get("header_height_mm", 8)) * mm
    footer_h = float(m.get("footer_height_mm", 9)) * mm
    ctx = _template_context(project, page_index, page_count, page_ctx)

    if bool(m.get("header_enabled", True)) and bool((page_ctx or {}).get("show_header", True)):
        y = page_rect.top() + margin_top
        rect = QRectF(content_left, y, max(1, content_right - content_left), header_h)
        _draw_band_background(painter, project, "header", rect)
        _draw_template_document(painter, project, "header", rect, dpi, ctx)
        if bool(m.get("header_separator_enabled", True)):
            color = QColor(str(m.get("header_separator_color", "#c8cdd3")))
            width_px = max(1.0, float(m.get("header_separator_width_pt", 0.8)) * dpi / 72.0)
            painter.save()
            painter.setPen(QPen(color, width_px))
            painter.drawLine(int(rect.left()), int(rect.bottom()), int(rect.right()), int(rect.bottom()))
            painter.restore()

    if bool(m.get("footer_enabled", True)) and bool((page_ctx or {}).get("show_footer", True)):
        y = page_rect.bottom() - margin_bottom - footer_h
        rect = QRectF(content_left, y, max(1, content_right - content_left), footer_h)
        _draw_band_background(painter, project, "footer", rect)
        _draw_template_document(painter, project, "footer", rect, dpi, ctx)
        if bool(m.get("footer_separator_enabled", True)):
            color = QColor(str(m.get("footer_separator_color", "#c8cdd3")))
            width_px = max(1.0, float(m.get("footer_separator_width_pt", 0.8)) * dpi / 72.0)
            painter.save()
            painter.setPen(QPen(color, width_px))
            painter.drawLine(int(rect.left()), int(rect.top()), int(rect.right()), int(rect.top()))
            painter.restore()


def _pdf_topic_number_map(project):
    """Retorna a numeração estrutural sem contar o tópico especial de sumário."""
    counters = [0, 0, 0, 0, 0, 0]
    result = {}
    for topic, depth in ordered_topics(project):
        if getattr(topic, "kind", "normal") == "toc":
            continue
        d = min(max(0, int(depth)), len(counters) - 1)
        counters[d] += 1
        for i in range(d + 1, len(counters)):
            counters[i] = 0
        result[topic.id] = ".".join(str(counters[i]) for i in range(d + 1) if counters[i] > 0)
    return result


def _pdf_base_css(project):
    m = project.meta
    family = html.escape(str(m.get("body_font_family", "Arial")), quote=True)
    body = float(m.get("body_font_size_pt", 10.5))
    line_height = int(m.get("line_height_percent", 118))
    paragraph = float(m.get("paragraph_spacing_pt", 5))
    return (
        f"body{{font-family:'{family}';font-size:{body}pt;line-height:{line_height}%;color:#20252b;margin:0;padding:0;}}"
        f"p{{margin-top:0;margin-bottom:{paragraph}pt;}}"
        "img{max-width:100%;height:auto;}"
        "table{max-width:100%;border-collapse:collapse;}"
        "td,th{vertical-align:top;}"
        "pre{font-family:Consolas,'Courier New',monospace;font-size:9pt;white-space:pre-wrap;background:#f2f4f6;border:1px solid #d7dce2;padding:7pt;margin:7pt 0 10pt;}"
        "code{font-family:Consolas,'Courier New',monospace;}"
    )


def _pdf_cover_fragment(project, language):
    m = project.meta
    title = html.escape(str(m.get("pdf_cover_title", "") or m.get("title", "Manual")))
    author = html.escape(str(m.get("author", "")))
    version = html.escape(str(m.get("version", "")))
    subtitle = html.escape(str(m.get("pdf_cover_subtitle", "")))
    logo_id = m.get("pdf_cover_logo_asset", "") or m.get("logo_asset", "")
    align = str(m.get("pdf_cover_alignment", "center"))
    align_css = "left" if align == "left" else ("right" if align == "right" else "center")
    offset = max(0.0, float(m.get("pdf_cover_vertical_offset_mm", 42)))
    parts = [f'<div style="text-align:{align_css}; margin-top:{offset:.1f}mm;">']
    if bool(m.get("pdf_cover_show_logo", True)) and logo_id in project.assets:
        width_px = float(m.get("pdf_cover_logo_width_mm", 42)) / 25.4 * SCREEN_DPI
        parts.append(f'<img src="asset://{logo_id}" width="{width_px:.0f}">')
    if bool(m.get("pdf_cover_show_title", True)):
        title_color = html.escape(str(m.get("pdf_cover_title_color", "#1f2933")), quote=True)
        parts.append(f'<div style="font-size:{float(m.get("pdf_cover_title_size_pt",30)):.1f}pt; color:{title_color}; font-weight:600; margin-top:18px;">{title}</div>')
    if subtitle:
        parts.append(f'<p style="font-size:13pt; margin-top:12px;">{subtitle}</p>')
    if bool(m.get("pdf_cover_show_author", True)) and author:
        parts.append(f'<p style="font-size:12pt; margin-top:16px;">{author}</p>')
    if bool(m.get("pdf_cover_show_version", True)) and version:
        parts.append(f'<p style="font-size:11pt;">Versão {version}</p>')
    if bool(m.get("pdf_cover_show_language", True)) and len(project.languages()) > 1:
        parts.append(f'<p style="font-size:10pt;">{html.escape(language)}</p>')
    parts.append('</div>')
    return ''.join(parts)


def _draw_pdf_cover_background(painter, project, page_rect):
    m = project.meta
    kind = str(m.get("pdf_cover_background_type", "image" if m.get("pdf_cover_background_asset") else ("solid" if m.get("pdf_cover_background_color") else "none")))
    if kind == "none":
        return
    c1 = QColor(str(m.get("pdf_cover_background_color1", m.get("pdf_cover_background_color", "#ffffff"))))
    c2 = QColor(str(m.get("pdf_cover_background_color2", "#e9edf2")))
    painter.save()
    if kind == "solid":
        painter.fillRect(page_rect, c1)
    elif kind == "gradient":
        direction = str(m.get("pdf_cover_gradient_direction", "vertical"))
        if direction == "horizontal":
            grad = QLinearGradient(page_rect.left(), page_rect.top(), page_rect.right(), page_rect.top())
        elif direction == "diagonal":
            grad = QLinearGradient(page_rect.left(), page_rect.top(), page_rect.right(), page_rect.bottom())
        else:
            grad = QLinearGradient(page_rect.left(), page_rect.top(), page_rect.left(), page_rect.bottom())
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        painter.fillRect(page_rect, QBrush(grad))
    elif kind == "image":
        aid = m.get("pdf_cover_background_asset", "")
        asset = project.assets.get(aid)
        image = QImage.fromData(asset.bytes()) if asset else QImage()
        if not image.isNull():
            painter.fillRect(page_rect, c1)
            fit = str(m.get("pdf_cover_background_fit", "cover"))
            scale_pct = max(10.0, min(400.0, float(m.get("pdf_cover_background_scale_percent", 100)))) / 100.0
            xpos = max(0.0, min(100.0, float(m.get("pdf_cover_background_x_percent", 50)))) / 100.0
            ypos = max(0.0, min(100.0, float(m.get("pdf_cover_background_y_percent", 50)))) / 100.0
            opacity = max(0.0, min(100.0, float(m.get("pdf_cover_background_opacity", 100)))) / 100.0

            if fit == "stretch":
                base_w = page_rect.width()
                base_h = page_rect.height()
                scaled = image.scaled(max(1, int(base_w * scale_pct)), max(1, int(base_h * scale_pct)), Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            else:
                mode = Qt.KeepAspectRatioByExpanding if fit == "cover" else Qt.KeepAspectRatio
                base = image.scaled(max(1, int(page_rect.width())), max(1, int(page_rect.height())), mode, Qt.SmoothTransformation)
                scaled = base.scaled(max(1, int(base.width() * scale_pct)), max(1, int(base.height() * scale_pct)), Qt.KeepAspectRatio, Qt.SmoothTransformation)

            center_x = page_rect.left() + page_rect.width() * xpos
            center_y = page_rect.top() + page_rect.height() * ypos
            x = center_x - scaled.width() / 2.0
            y = center_y - scaled.height() / 2.0
            painter.setClipRect(page_rect)
            painter.setOpacity(opacity)
            painter.drawImage(QRectF(x, y, scaled.width(), scaled.height()), scaled)
    painter.restore()

def _pdf_toc_fragment(project, language, page_map, number_map, special_topic=None):
    m = project.meta
    title = str(m.get("pdf_toc_title", "Sumário"))
    title_size = float(m.get("pdf_topic_title_size_pt", m.get("heading1_size_pt", 20)))
    entry_size = float(m.get("pdf_toc_font_size_pt", m.get("body_font_size_pt", 10.5)))
    show_pages = bool(m.get("pdf_toc_page_numbers", True))
    parts = [
        f'<div style="font-size:{title_size:.1f}pt; font-weight:700; margin-bottom:16px;">{html.escape(title)}</div>'
    ]

    intro_html = str(m.get("pdf_toc_intro_html", "") or "")
    if intro_html.strip():
        parts.append(body_fragment(intro_html))
        parts.append('<div style="height:8pt"></div>')
    elif special_topic is not None:
        # Compatibilidade com projetos antigos: o antigo tópico especial de
        # sumário passa a servir apenas como texto introdutório da seção
        # automática, sem controlar sua posição ou paginação.
        body = project.topic_html(special_topic, language) if hasattr(project, "topic_html") else special_topic.html
        frag = body_fragment(body)
        if frag.strip():
            parts.append(frag)
            parts.append('<div style="height:8pt"></div>')

    parts.append('<table width="100%" border="0" cellspacing="0" cellpadding="3">')
    for topic, depth in ordered_topics(project):
        if bool(getattr(topic, "exclude_from_toc", False)) or getattr(topic, "kind", "normal") == "toc":
            continue
        t = project.topic_title(topic, language) if hasattr(project, "topic_title") else topic.title
        num = number_map.get(topic.id, "") if bool(m.get("pdf_topic_numbering", True)) else ""
        label = (num + " " if num else "") + t
        indent = "&nbsp;" * (max(0, int(depth)) * 4)
        page = page_map.get((language, topic.id), "—")
        parts.append(
            '<tr>'
            f'<td style="font-size:{entry_size:.1f}pt; padding-top:3px; padding-bottom:3px;">{indent}{html.escape(label)}</td>'
            + (f'<td width="54" align="right" style="font-size:{entry_size:.1f}pt; padding-top:3px; padding-bottom:3px;"><b>{page}</b></td>' if show_pages else '')
            + '</tr>'
        )
    parts.append('</table>')
    return ''.join(parts)

def _pdf_topic_fragment(project, topic, depth, language, number_map, show_header=False):
    """Monta o conteúdo de um tópico para PDF.

    O título grande é um fallback visual para páginas sem cabeçalho. Quando o
    cabeçalho efetivamente será desenhado, o nome do tópico já está presente na
    faixa superior e repetir o mesmo título no corpo deixa a página duplicada.
    """
    m = project.meta
    parts = []
    show_fallback_title = bool(m.get("pdf_topic_title_enabled", True)) and not bool(show_header)
    if show_fallback_title:
        title = project.topic_title(topic, language) if hasattr(project, "topic_title") else topic.title
        num = number_map.get(topic.id, "") if bool(m.get("pdf_topic_numbering", True)) else ""
        label = (num + " " if num else "") + title
        base_size = float(m.get("pdf_topic_title_size_pt", m.get("heading1_size_pt", 20)))
        size = max(12.0, base_size - min(max(0, int(depth)), 3) * 1.5)
        parts.append(
            f'<div style="font-size:{size:.1f}pt; font-weight:700; margin-bottom:12pt;">{html.escape(label)}</div>'
        )
    body = project.topic_html(topic, language) if hasattr(project, "topic_html") else topic.html
    parts.append(body_fragment(body))
    return ''.join(parts)


def _pdf_section_specs(project, languages):
    """Cria a ordem física. Capa, sumário e cada tópico começam em nova página."""
    m = project.meta
    ordered = ordered_topics(project)
    legacy_toc = next((topic for topic, _depth in ordered if getattr(topic, "kind", "normal") == "toc"), None)
    specs = []
    for language in languages:
        if bool(m.get("pdf_cover_enabled", m.get("cover_enabled", True))):
            specs.append({
                "kind": "cover", "language": language, "topic": None, "depth": 0,
                "show_header": bool(m.get("pdf_header_on_cover", False)),
                "show_footer": bool(m.get("pdf_footer_on_cover", False)),
            })
        if bool(m.get("pdf_toc_enabled", m.get("toc_enabled", True))):
            specs.append({
                "kind": "toc", "language": language, "topic": legacy_toc, "depth": 0,
                "show_header": bool(m.get("pdf_header_on_toc", False)),
                "show_footer": bool(m.get("pdf_footer_on_toc", False)),
            })
        for topic, depth in ordered:
            if getattr(topic, "kind", "normal") == "toc":
                continue
            show_h = True if topic.show_header is None else bool(topic.show_header)
            show_f = True if topic.show_footer is None else bool(topic.show_footer)
            specs.append({
                "kind": "topic", "language": language, "topic": topic, "depth": depth,
                "show_header": show_h, "show_footer": show_f,
            })
    return specs

def _pdf_section_geometry(project, page_rect, dpi, spec):
    m = project.meta
    mm = dpi / 25.4
    scale = dpi / SCREEN_DPI
    margin_left = float(m.get("margin_left_mm", 18)) * mm
    margin_right = float(m.get("margin_right_mm", 18)) * mm
    margin_top = float(m.get("margin_top_mm", 16)) * mm
    margin_bottom = float(m.get("margin_bottom_mm", 16)) * mm

    global_h = bool(m.get("header_enabled", True))
    global_f = bool(m.get("footer_enabled", True))
    actual_h = global_h and bool(spec.get("show_header", True))
    actual_f = global_f and bool(spec.get("show_footer", True))
    reclaim = bool(m.get("pdf_reclaim_hidden_header_footer_space", True))
    reserve_h = actual_h if reclaim else global_h
    reserve_f = actual_f if reclaim else global_f

    header_h = float(m.get("header_height_mm", 8)) * mm if reserve_h else 0.0
    footer_h = float(m.get("footer_height_mm", 9)) * mm if reserve_f else 0.0
    header_gap = float(m.get("header_gap_mm", 3)) * mm if reserve_h else 0.0
    footer_gap = float(m.get("footer_gap_mm", 3)) * mm if reserve_f else 0.0

    left = page_rect.left() + margin_left
    right = page_rect.right() - margin_right
    top = page_rect.top() + margin_top + header_h + header_gap
    bottom = page_rect.bottom() - margin_bottom - footer_h - footer_gap
    w = right - left
    h = bottom - top
    if w < 40 * mm or h < 50 * mm:
        raise ValueError("A configuração do PDF deixou pouca área útil. Revise margens, cabeçalho e rodapé.")
    return {
        "left": left, "right": right, "top": top, "bottom": bottom,
        "width_px": w, "height_px": h,
        "logical_w": w / scale, "logical_h": h / scale, "scale": scale,
        "actual_header": actual_h, "actual_footer": actual_f,
    }


def _pdf_make_document(project, fragment, logical_w, logical_h):
    doc = QTextDocument()
    family = str(project.meta.get("body_font_family", "Arial"))
    body_font = QFont(family)
    body_font.setPointSizeF(float(project.meta.get("body_font_size_pt", 10.5)))
    doc.setDefaultFont(body_font)
    doc.setDocumentMargin(0)
    doc.setDefaultStyleSheet(_pdf_base_css(project))
    _register_assets(doc, project)
    doc.setHtml(f'<html><head><meta charset="utf-8"></head><body>{fragment}</body></html>')
    _register_assets(doc, project)
    doc.setPageSize(QSizeF(logical_w, logical_h))
    _clamp_document_images(doc, project, logical_w)
    doc.setPageSize(QSizeF(logical_w, logical_h))
    return doc


def _pdf_render_layout(project, specs, page_rect, dpi, page_map):
    number_map = _pdf_topic_number_map(project)
    rendered = []
    new_page_map = {}
    page_cursor = int(project.meta.get("pdf_page_number_start", 1))
    for spec in specs:
        kind = spec["kind"]
        language = spec["language"]
        topic = spec.get("topic")
        if kind == "cover":
            fragment = _pdf_cover_fragment(project, language)
        elif kind == "toc":
            fragment = _pdf_toc_fragment(project, language, page_map, number_map, topic)
        else:
            # O título grande só entra quando NÃO há cabeçalho efetivo nesta seção.
            # Isso considera tanto a configuração global quanto a opção individual
            # do tópico, evitando o nome duplicado mostrado no PDF.
            actual_header = bool(project.meta.get("header_enabled", True)) and bool(spec.get("show_header", True))
            fragment = _pdf_topic_fragment(
                project, topic, spec.get("depth", 0), language, number_map,
                show_header=actual_header,
            )

        geom = _pdf_section_geometry(project, page_rect, dpi, spec)
        doc = _pdf_make_document(project, fragment, geom["logical_w"], geom["logical_h"])
        count = max(1, int(doc.documentLayout().pageCount()))
        if kind == "topic" and topic is not None:
            new_page_map[(language, topic.id)] = page_cursor
        rendered.append({**spec, "doc": doc, "geom": geom, "page_count": count})
        page_cursor += count
    total_pages = max(1, page_cursor - int(project.meta.get("pdf_page_number_start", 1)))
    return rendered, new_page_map, total_pages


def export_pdf(project, output_path: str, language=None, combined_languages: Optional[List[str]] = None):
    """Exporta PDF por seções independentes, com paginação real no sumário.

    A composição antiga usava um QTextDocument único. Isso permitia que o fim de
    um tópico e o começo do próximo caíssem na mesma página e tornava a
    paginação do sumário frágil. Aqui cada tópico possui seu próprio documento
    paginado e sempre começa numa nova folha física.
    """
    m = project.meta
    dpi = int(m.get("pdf_resolution_dpi", 300))
    dpi = 150 if dpi < 225 else (600 if dpi >= 450 else 300)

    printer = QPrinter(QPrinter.HighResolution)
    printer.setResolution(dpi)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(output_path)
    page_w_mm, page_h_mm = _page_dimensions_mm(project)
    printer.setPaperSize(QSizeF(page_w_mm, page_h_mm), QPrinter.Millimeter)
    printer.setOrientation(QPrinter.Landscape if m.get("page_orientation") == "landscape" else QPrinter.Portrait)
    printer.setFullPage(True)

    if combined_languages:
        languages = [str(x) for x in combined_languages if str(x)]
    else:
        languages = [str(language or m.get("language", "pt-BR"))]
    if not languages:
        languages = [str(m.get("language", "pt-BR"))]

    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("Não foi possível iniciar a geração do PDF.")

    try:
        page_rect = printer.paperRect(QPrinter.DevicePixel)
        specs = _pdf_section_specs(project, languages)
        if not specs:
            raise ValueError("O manual não possui conteúdo para exportar.")

        # Duas ou mais passagens: a primeira mede os tópicos; a seguinte já
        # escreve as páginas reais no sumário. Se o próprio sumário mudar de
        # tamanho, recalculamos até os números estabilizarem.
        page_map = {}
        rendered = []
        total_pages = 0
        for _ in range(6):
            rendered, new_page_map, total_pages = _pdf_render_layout(project, specs, page_rect, float(dpi), page_map)
            if new_page_map == page_map:
                page_map = new_page_map
                break
            page_map = new_page_map
        else:
            rendered, page_map, total_pages = _pdf_render_layout(project, specs, page_rect, float(dpi), page_map)

        global_page = 0
        for section in rendered:
            doc = section["doc"]
            geom = section["geom"]
            topic = section.get("topic")
            lang = section["language"]
            page_ctx = {
                "topic": project.topic_title(topic, lang) if topic is not None and hasattr(project, "topic_title") else (topic.title if topic else ""),
                "category": _topic_category(project, topic.id, lang) if topic is not None else "",
                "language": lang,
                "show_header": bool(section.get("show_header", True)),
                "show_footer": bool(section.get("show_footer", True)),
            }

            for local_page in range(section["page_count"]):
                if global_page > 0:
                    printer.newPage()

                if section.get("kind") == "cover":
                    _draw_pdf_cover_background(painter, project, page_rect)

                painter.save()
                _draw_header_footer(
                    painter, project, page_rect, global_page, total_pages, float(dpi),
                    geom["left"], geom["right"], page_ctx,
                )
                painter.restore()

                painter.save()
                painter.translate(geom["left"], geom["top"])
                painter.scale(geom["scale"], geom["scale"])
                painter.translate(0, -local_page * geom["logical_h"])
                context = QAbstractTextDocumentLayout.PaintContext()
                context.clip = QRectF(0, local_page * geom["logical_h"], geom["logical_w"], geom["logical_h"])
                doc.documentLayout().draw(painter, context)
                painter.restore()
                global_page += 1
    finally:
        painter.end()


def _chm_language_code(lang: str) -> str:
    return {
        "pt-BR": "0x416 Portuguese (Brazilian)",
        "en-US": "0x409 English (United States)",
        "es-ES": "0x40a Spanish (Traditional Sort)",
        "de-DE": "0x407 German (Germany)",
        "fr-FR": "0x40c French (France)",
    }.get(lang, "0x409 English (United States)")


def _hhc_tree(project, mapping):
    def branch(parent_id):
        children = [t for t in project.children_of(parent_id) if getattr(t, "kind", "normal") != "toc"]
        if not children:
            return ""
        items = ["<UL>"]
        for t in children:
            items.append('<LI><OBJECT type="text/sitemap">')
            items.append(f'<param name="Name" value="{html.escape(t.title, quote=True)}">')
            items.append(f'<param name="Local" value="topics/{mapping[t.id]}">')
            items.append('</OBJECT>')
            items.append(branch(t.id))
        items.append("</UL>")
        return "\n".join(items)
    return '<!DOCTYPE HTML PUBLIC "-//IETF//DTD HTML//EN"><HTML><BODY>\n' + branch(None) + '\n</BODY></HTML>'


def find_hhc(configured: str = "") -> Optional[str]:
    candidates = []
    if configured:
        candidates.append(configured)
    which = shutil.which("hhc.exe") or shutil.which("hhc")
    if which:
        candidates.append(which)
    candidates.extend([
        r"C:\Program Files (x86)\HTML Help Workshop\hhc.exe",
        r"C:\Program Files\HTML Help Workshop\hhc.exe",
    ])
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def export_chm(project, output_path: str, hhc_path: str = "") -> Tuple[bool, str, str]:
    out = Path(output_path)
    project_dir = out.with_suffix("").parent / (out.stem + "_chm_project")
    if project_dir.exists():
        shutil.rmtree(project_dir)
    export_html(project, str(project_dir), create_subfolder=False)

    mapping = topic_file_map(project)
    (project_dir / "contents.hhc").write_text(_hhc_tree(project, mapping), encoding="utf-8")
    (project_dir / "index.hhk").write_text(_hhc_tree(project, mapping), encoding="utf-8")

    ordered = [(t, d) for t, d in ordered_topics(project) if getattr(t, "kind", "normal") != "toc"]
    first = ordered[0][0] if ordered else None
    default_topic = f"topics/{mapping[first.id]}" if first else "index.html"
    files = ["index.html", "style.css", "language.js", "contents.hhc", "index.hhk"]
    if (project_dir / "sumario.html").exists():
        files.append("sumario.html")
    files += [f"topics/{mapping[t.id]}" for t, _d in ordered]
    files += [f"assets/{asset_filename(a)}" for a in project.assets.values()]
    hhp = f"""[OPTIONS]
Compatibility=1.1 or later
Compiled file={out.name}
Contents file=contents.hhc
Index file=index.hhk
Default topic={default_topic}
Display compile progress=Yes
Full-text search=Yes
Language={_chm_language_code(project.meta.get('language', 'pt-BR'))}
Title={project.meta.get('title', 'Manual')}

[FILES]
""" + "\n".join(files) + "\n"
    hhp_path = project_dir / (out.stem + ".hhp")
    hhp_path.write_text(hhp, encoding="utf-8")

    compiler = find_hhc(hhc_path)
    if not compiler:
        return False, "HTML Help Workshop (hhc.exe) não encontrado. O projeto CHM foi gerado e pode ser compilado depois.", str(hhp_path)

    proc = subprocess.run(
        [compiler, str(hhp_path)],
        cwd=str(project_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
    )
    generated = project_dir / out.name
    if generated.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(generated), str(out))
        return True, "CHM gerado com sucesso.", str(out)
    return False, "O compilador CHM terminou sem gerar o arquivo.\n\n" + proc.stdout[-4000:], str(hhp_path)
