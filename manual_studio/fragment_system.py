"""Portable topic fragments for Manual Studio.

A .mfrag file is a compact, single-file package that can carry one topic,
selected descendants, translations, embedded assets and optional style groups.
It deliberately does not translate content; language entries are copied as-is.
"""

from __future__ import annotations

import base64
import html as html_lib
import json
import re
import struct
import uuid
import zlib
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .model import Asset, ManualProject, Topic


FRAGMENT_EXTENSION = ".mfrag"
FRAGMENT_MAGIC = b"MSFRAG\x01\x00"
FRAGMENT_VERSION = 1
ASSET_REF_RE = re.compile(r"asset://([0-9A-Za-z_-]{6,})")
IMG_ASSET_RE = re.compile(
    r"<img\b[^>]*\bsrc\s*=\s*([\"'])asset://([0-9A-Za-z_-]{6,})\1[^>]*>",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"<[^>]+>")


STYLE_GROUPS: Dict[str, Tuple[str, Sequence[str]]] = {
    "typography": (
        "Tipografia do documento",
        (
            "body_font_family", "body_font_size_pt", "heading1_size_pt",
            "heading2_size_pt", "heading3_size_pt", "line_height_percent",
            "paragraph_spacing_pt",
        ),
    ),
    "page": (
        "Folha e margens",
        (
            "page_size", "page_orientation", "margin_top_mm", "margin_bottom_mm",
            "margin_left_mm", "margin_right_mm", "header_height_mm", "footer_height_mm",
            "header_gap_mm", "footer_gap_mm",
        ),
    ),
    "header_footer": (
        "Cabeçalho e rodapé",
        (
            "header_enabled", "footer_enabled", "footer_text", "logo_asset",
            "footer_logo", "footer_logo_width_mm", "header_template_html",
            "footer_template_html", "header_background_type", "header_background_color1",
            "header_background_color2", "header_gradient_direction", "header_background_asset",
            "header_background_fit", "header_background_opacity", "header_separator_enabled",
            "header_separator_color", "header_separator_width_pt", "header_logo_width_mm",
            "header_padding_left_mm", "header_padding_right_mm", "footer_background_type",
            "footer_background_color1", "footer_background_color2", "footer_gradient_direction",
            "footer_background_asset", "footer_background_fit", "footer_background_opacity",
            "footer_separator_enabled", "footer_separator_color", "footer_separator_width_pt",
            "footer_padding_left_mm", "footer_padding_right_mm",
        ),
    ),
    "html": (
        "Estilo HTML / CSS",
        (
            "html_accent", "html_background", "html_text", "html_sidebar_background",
            "html_topbar_background", "html_sidebar_width_px", "html_content_width_px",
            "html_tree_lines", "html_tree_expand_default", "html_toc_enabled", "html_toc_title",
            "html_toc_description", "html_intro_enabled", "html_intro_title",
            "html_intro_subtitle", "html_intro_show_logo", "html_intro_show_version",
            "html_intro_show_author", "html_intro_show_toc", "html_intro_body_html",
            "html_custom_css", "html_manual_icon_asset", "html_project_url",
            "html_show_project_link",
        ),
    ),
    "pdf": (
        "Configuração visual do PDF",
        tuple(),  # resolved dynamically: every pdf_* key
    ),
}


def _style_keys(project: ManualProject, group: str) -> List[str]:
    if group == "pdf":
        return sorted(k for k in project.meta if str(k).startswith("pdf_"))
    return list(STYLE_GROUPS[group][1])


def _plain_html(value: str) -> str:
    """Convert rich text into a small, safe paragraph while keeping line breaks."""
    text = str(value or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|li|tr|h[1-6])>", "\n", text)
    text = TAG_RE.sub("", text)
    text = html_lib.unescape(text)
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return "<p></p>"
    return "".join(f"<p>{html_lib.escape(line)}</p>" for line in lines)


def _without_embedded_images(value: str) -> str:
    return IMG_ASSET_RE.sub('<span style="color:#777;">[imagem não incluída no fragmento]</span>', str(value or ""))


def _collect_asset_refs(values: Iterable[str]) -> Set[str]:
    out: Set[str] = set()
    for value in values:
        if not value:
            continue
        out.update(ASSET_REF_RE.findall(str(value)))
    return out


def _topic_descendants(project: ManualProject, root_id: str) -> List[Topic]:
    out: List[Topic] = []

    def walk(parent_id: str):
        for child in project.children_of(parent_id):
            out.append(child)
            walk(child.id)

    walk(root_id)
    return out


def _nearest_selected_parent(project: ManualProject, topic: Topic, selected: Set[str], root_id: str) -> Optional[str]:
    if topic.id == root_id:
        return None
    pid = topic.parent_id
    guard = 0
    while pid and guard < len(project.topics) + 2:
        guard += 1
        if pid in selected:
            return pid
        parent = project.topic_by_id(pid)
        pid = parent.parent_id if parent else None
    return root_id if root_id in selected else None


def build_fragment(
    project: ManualProject,
    root_topic_id: str,
    topic_ids: Iterable[str],
    languages: Iterable[str],
    *,
    include_rich_text: bool = True,
    include_assets: bool = True,
    include_topic_options: bool = True,
    style_groups: Iterable[str] = (),
) -> Dict[str, Any]:
    root = project.topic_by_id(root_topic_id)
    if not root:
        raise ValueError("O tópico raiz do fragmento não existe.")

    selected = {str(x) for x in topic_ids if project.topic_by_id(str(x))}
    selected.add(root_topic_id)
    langs = [lang for lang in project.languages() if lang in set(str(x) for x in languages)]
    if not langs:
        langs = [str(project.meta.get("language", "pt-BR"))]

    topics: List[Dict[str, Any]] = []
    html_values: List[str] = []
    ordered = [t for t in project.topics if t.id in selected]
    # Preserve hierarchy/order rather than the raw list order if a manually edited file differs.
    ordered.sort(key=lambda t: (0 if t.id == root_topic_id else 1, t.order, project.topic_title(t, langs[0]).lower()))

    for topic in ordered:
        content: Dict[str, Dict[str, str]] = {}
        for lang in langs:
            title = project.topic_title(topic, lang)
            body = project.topic_html(topic, lang)
            if not include_rich_text:
                body = _plain_html(body)
            if not include_assets:
                body = _without_embedded_images(body)
            content[lang] = {"title": title, "html": body}
            html_values.append(body)

        row: Dict[str, Any] = {
            "source_id": topic.id,
            "parent_source_id": _nearest_selected_parent(project, topic, selected, root_topic_id),
            "order": int(topic.order),
            "content": content,
        }
        if include_topic_options:
            row.update({
                "kind": topic.kind,
                "show_header": topic.show_header,
                "show_footer": topic.show_footer,
                "exclude_from_toc": bool(topic.exclude_from_toc),
            })
        topics.append(row)

    selected_style_groups = [g for g in style_groups if g in STYLE_GROUPS]
    style_meta: Dict[str, Any] = {}
    for group in selected_style_groups:
        for key in _style_keys(project, group):
            if key in project.meta:
                style_meta[key] = project.meta[key]
                if isinstance(project.meta[key], str):
                    html_values.append(project.meta[key])

    # Direct asset-id properties do not contain asset://, therefore collect them separately.
    direct_asset_keys = {
        "logo_asset", "header_background_asset", "footer_background_asset",
        "html_manual_icon_asset", "pdf_cover_background_asset", "pdf_cover_logo_asset",
    }
    direct_asset_ids = {
        str(style_meta.get(key)) for key in direct_asset_keys if style_meta.get(key)
    }
    asset_ids = _collect_asset_refs(html_values) | direct_asset_ids

    assets: Dict[str, Dict[str, Any]] = {}
    if include_assets:
        for aid in sorted(asset_ids):
            asset = project.assets.get(aid)
            if asset:
                assets[aid] = asdict(asset)

    fragment = {
        "fragment_format": "manual-studio-fragment",
        "fragment_version": FRAGMENT_VERSION,
        "source": {
            "manual_title": str(project.meta.get("title", "")),
            "manual_version": str(project.meta.get("version", "")),
            "default_language": str(project.meta.get("language", "pt-BR")),
            "root_topic_title": project.topic_title(root, langs[0]),
        },
        "languages": langs,
        "root_source_id": root_topic_id,
        "options": {
            "rich_text": bool(include_rich_text),
            "assets": bool(include_assets),
            "topic_options": bool(include_topic_options),
            "style_groups": selected_style_groups,
        },
        "style_meta": style_meta,
        "topics": topics,
        "assets": assets,
    }
    return fragment


def save_fragment(fragment: Dict[str, Any], path: str) -> str:
    target = Path(path)
    if target.suffix.lower() not in {".mfrag", ".fragmento"}:
        target = target.with_suffix(FRAGMENT_EXTENSION)
    raw = json.dumps(fragment, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = zlib.compress(raw, level=9)
    crc = zlib.crc32(raw) & 0xFFFFFFFF
    header = FRAGMENT_MAGIC + struct.pack(">III", FRAGMENT_VERSION, len(raw), crc)
    target.write_bytes(header + compressed)
    return str(target)


def load_fragment(path: str) -> Dict[str, Any]:
    data = Path(path).read_bytes()
    header_len = len(FRAGMENT_MAGIC) + 12
    if len(data) < header_len or not data.startswith(FRAGMENT_MAGIC):
        raise ValueError("Este arquivo não é um fragmento válido do Manual Studio.")
    version, raw_len, expected_crc = struct.unpack(">III", data[len(FRAGMENT_MAGIC):header_len])
    if version > FRAGMENT_VERSION:
        raise ValueError(f"O fragmento usa uma versão mais nova ({version}).")
    try:
        raw = zlib.decompress(data[header_len:])
    except Exception as exc:
        raise ValueError("O fragmento está corrompido ou incompleto.") from exc
    if len(raw) != raw_len or (zlib.crc32(raw) & 0xFFFFFFFF) != expected_crc:
        raise ValueError("A verificação de integridade do fragmento falhou.")
    payload = json.loads(raw.decode("utf-8"))
    if payload.get("fragment_format") != "manual-studio-fragment":
        raise ValueError("Formato de fragmento não reconhecido.")
    return payload


def fragment_tree_rows(fragment: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(fragment.get("topics") or [])


def _rewrite_assets_in_text(value: Any, asset_map: Dict[str, str]) -> Any:
    if not isinstance(value, str) or not value:
        return value
    out = value
    for old, new in asset_map.items():
        out = out.replace(f"asset://{old}", f"asset://{new}")
    return out


def import_fragment_into_project(
    project: ManualProject,
    fragment: Dict[str, Any],
    *,
    selected_source_ids: Iterable[str],
    destination_parent_id: Optional[str],
    language_map: Dict[str, Optional[str]],
    apply_style_groups: Iterable[str] = (),
) -> Tuple[List[str], Dict[str, str]]:
    """Import a fragment and return (new topic ids, old->new asset id map)."""
    rows = fragment_tree_rows(fragment)
    selected = {str(x) for x in selected_source_ids}
    rows = [row for row in rows if str(row.get("source_id")) in selected]
    if not rows:
        raise ValueError("Nenhum tópico foi selecionado para importar.")

    # Import all packaged assets. The package only carries resources actually needed by the fragment.
    asset_map: Dict[str, str] = {}
    for old_id, raw in (fragment.get("assets") or {}).items():
        try:
            data = base64.b64decode(str(raw.get("data_b64", "")).encode("ascii"))
        except Exception:
            continue
        asset = project.add_asset_bytes(data, str(raw.get("filename") or "recurso.bin"), str(raw.get("mime") or "application/octet-stream"))
        asset_map[str(old_id)] = asset.id

    # Add mapped languages before creating the translations.
    target_langs = project.languages()
    for destination in language_map.values():
        if destination and destination not in target_langs:
            target_langs.append(destination)
    project.meta["languages"] = target_langs

    target_default = str(project.meta.get("language", "pt-BR"))
    fragment_default = str((fragment.get("source") or {}).get("default_language") or "")
    source_languages = list(fragment.get("languages") or [])
    fallback_source = fragment_default if fragment_default in source_languages else (source_languages[0] if source_languages else "")

    row_by_id = {str(row.get("source_id")): row for row in rows}
    new_topic_map: Dict[str, str] = {}
    imported_ids: List[str] = []

    # Process parents before children. Iterate until no unresolved row remains.
    pending = list(rows)
    safety = 0
    while pending and safety < len(rows) + 5:
        safety += 1
        progress = False
        rest = []
        for row in pending:
            source_id = str(row.get("source_id"))
            parent_source = row.get("parent_source_id")
            # The import dialog may deselect an intermediate topic. Walk upward until
            # the nearest still-selected ancestor is found; otherwise use the chosen
            # destination parent in the target project.
            resolved_parent_source = str(parent_source) if parent_source else None
            parent_guard = 0
            while resolved_parent_source and resolved_parent_source not in selected and parent_guard < len(row_by_id) + 2:
                parent_guard += 1
                parent_row = row_by_id.get(resolved_parent_source)
                resolved_parent_source = str(parent_row.get("parent_source_id")) if parent_row and parent_row.get("parent_source_id") else None
            if resolved_parent_source and resolved_parent_source not in new_topic_map:
                rest.append(row)
                continue

            content = row.get("content") or {}
            # Determine the base/default content. Prefer an explicit map into the target default;
            # otherwise use the fragment's editorial source as an editable draft.
            source_for_default = next((src for src, dst in language_map.items() if dst == target_default and src in content), None)
            if not source_for_default:
                source_for_default = fallback_source if fallback_source in content else (next(iter(content), ""))
            base = content.get(source_for_default, {}) if source_for_default else {}
            title = str(base.get("title") or "Tópico importado")
            body = _rewrite_assets_in_text(str(base.get("html") or "<p></p>"), asset_map)

            parent_new = new_topic_map.get(resolved_parent_source) if resolved_parent_source else destination_parent_id
            siblings = project.children_of(parent_new)
            topic = Topic(
                id=str(uuid.uuid4()),
                title=title,
                html=body,
                parent_id=parent_new,
                order=len(siblings),
                kind=str(row.get("kind") or "normal"),
                show_header=row.get("show_header") if "show_header" in row else None,
                show_footer=row.get("show_footer") if "show_footer" in row else None,
                exclude_from_toc=bool(row.get("exclude_from_toc", False)),
            )

            for source_lang, destination_lang in language_map.items():
                if not destination_lang or source_lang not in content:
                    continue
                item = content[source_lang]
                tr_title = str(item.get("title") or title)
                tr_html = _rewrite_assets_in_text(str(item.get("html") or "<p></p>"), asset_map)
                if destination_lang == target_default:
                    topic.title = tr_title
                    topic.html = tr_html
                else:
                    topic.translations[destination_lang] = {"title": tr_title, "html": tr_html}

            project.topics.append(topic)
            new_topic_map[source_id] = topic.id
            imported_ids.append(topic.id)
            progress = True
        if not progress and rest:
            # Broken parent reference inside a damaged/partially selected package: attach the rest
            # to the requested destination rather than losing content.
            for row in rest:
                row["parent_source_id"] = None
            pending = rest
        else:
            pending = rest

    # Optional global style groups. Never apply automatically; caller chooses them in the import dialog.
    style_meta = dict(fragment.get("style_meta") or {})
    allowed_keys: Set[str] = set()
    for group in apply_style_groups:
        if group in STYLE_GROUPS:
            if group == "pdf":
                allowed_keys.update(k for k in style_meta if str(k).startswith("pdf_"))
            else:
                allowed_keys.update(STYLE_GROUPS[group][1])
    direct_asset_keys = {
        "logo_asset", "header_background_asset", "footer_background_asset",
        "html_manual_icon_asset", "pdf_cover_background_asset", "pdf_cover_logo_asset",
    }
    for key in allowed_keys:
        if key not in style_meta:
            continue
        value = style_meta[key]
        if key in direct_asset_keys and value:
            value = asset_map.get(str(value), "")
        else:
            value = _rewrite_assets_in_text(value, asset_map)
        project.meta[key] = value

    return imported_ids, asset_map


class FragmentExportDialog(QDialog):
    def __init__(self, project: ManualProject, root_topic_id: str, current_language: str, parent=None):
        super().__init__(parent)
        self.project = project
        self.root_topic_id = root_topic_id
        self.current_language = current_language
        self.setWindowTitle("Exportar fragmento")
        self.resize(700, 720)

        root = project.topic_by_id(root_topic_id)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Crie um arquivo portátil a partir deste tópico. Você pode escolher os subtópicos, "
            "idiomas, imagens e quais estilos globais devem acompanhar o fragmento. O conteúdo "
            "não é traduzido automaticamente."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        topics_box = QGroupBox("Tópicos incluídos")
        topics_layout = QVBoxLayout(topics_box)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self._tree_items: Dict[str, QTreeWidgetItem] = {}

        def add_topic(topic: Topic, parent_item: Optional[QTreeWidgetItem] = None):
            item = QTreeWidgetItem([project.topic_title(topic, current_language)])
            item.setData(0, Qt.UserRole, topic.id)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(0, Qt.Checked)
            if topic.id == root_topic_id:
                item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
            if parent_item is None:
                self.tree.addTopLevelItem(item)
            else:
                parent_item.addChild(item)
            self._tree_items[topic.id] = item
            for child in project.children_of(topic.id):
                add_topic(child, item)

        if root:
            add_topic(root)
        self.tree.expandAll()
        topics_layout.addWidget(self.tree, 1)
        row = QHBoxLayout()
        all_btn = QPushButton("Todos os subtópicos")
        only_btn = QPushButton("Somente o tópico")
        all_btn.clicked.connect(lambda: self._set_descendants(Qt.Checked))
        only_btn.clicked.connect(lambda: self._set_descendants(Qt.Unchecked))
        row.addWidget(all_btn)
        row.addWidget(only_btn)
        row.addStretch(1)
        topics_layout.addLayout(row)
        layout.addWidget(topics_box, 1)

        lang_box = QGroupBox("Idiomas")
        lang_layout = QVBoxLayout(lang_box)
        self.language_checks: Dict[str, QCheckBox] = {}
        for lang in project.languages():
            cb = QCheckBox(lang + ("  — idioma atual" if lang == current_language else ""))
            cb.setChecked(lang == current_language)
            self.language_checks[lang] = cb
            lang_layout.addWidget(cb)
        all_lang = QPushButton("Selecionar todos os idiomas")
        all_lang.clicked.connect(lambda: [cb.setChecked(True) for cb in self.language_checks.values()])
        lang_layout.addWidget(all_lang)
        layout.addWidget(lang_box)

        content_box = QGroupBox("Conteúdo e recursos")
        content_layout = QVBoxLayout(content_box)
        self.rich_text = QCheckBox("Manter formatação rich-text (fontes, listas, tabelas, alinhamentos e links)")
        self.rich_text.setChecked(True)
        self.assets = QCheckBox("Incluir imagens e recursos usados pelos tópicos")
        self.assets.setChecked(True)
        self.topic_options = QCheckBox("Incluir propriedades dos tópicos (cabeçalho/rodapé, tipo especial e sumário)")
        self.topic_options.setChecked(True)
        content_layout.addWidget(self.rich_text)
        content_layout.addWidget(self.assets)
        content_layout.addWidget(self.topic_options)
        layout.addWidget(content_box)

        style_box = QGroupBox("Estilos globais opcionais")
        style_layout = QVBoxLayout(style_box)
        note = QLabel("Esses dados podem ser levados para outro projeto. Na importação, o usuário ainda escolhe se quer aplicá-los.")
        note.setWordWrap(True)
        style_layout.addWidget(note)
        self.style_checks: Dict[str, QCheckBox] = {}
        for key, (label, _) in STYLE_GROUPS.items():
            cb = QCheckBox(label)
            cb.setChecked(False)
            self.style_checks[key] = cb
            style_layout.addWidget(cb)
        layout.addWidget(style_box)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        self.buttons.button(QDialogButtonBox.Save).setText("Salvar fragmento...")
        self.buttons.accepted.connect(self._validate_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _set_descendants(self, state):
        for tid, item in self._tree_items.items():
            if tid != self.root_topic_id:
                item.setCheckState(0, state)

    def _validate_accept(self):
        if not any(cb.isChecked() for cb in self.language_checks.values()):
            QMessageBox.warning(self, "Fragmento", "Selecione pelo menos um idioma.")
            return
        self.accept()

    def values(self) -> Dict[str, Any]:
        topic_ids = [tid for tid, item in self._tree_items.items() if tid == self.root_topic_id or item.checkState(0) == Qt.Checked]
        languages = [lang for lang, cb in self.language_checks.items() if cb.isChecked()]
        styles = [key for key, cb in self.style_checks.items() if cb.isChecked()]
        return {
            "topic_ids": topic_ids,
            "languages": languages,
            "include_rich_text": self.rich_text.isChecked(),
            "include_assets": self.assets.isChecked(),
            "include_topic_options": self.topic_options.isChecked(),
            "style_groups": styles,
        }


class FragmentImportDialog(QDialog):
    def __init__(self, project: ManualProject, fragment: Dict[str, Any], selected_parent_id: Optional[str], current_language: str, parent=None):
        super().__init__(parent)
        self.project = project
        self.fragment = fragment
        self.current_language = current_language
        self.setWindowTitle("Importar fragmento")
        self.resize(760, 760)
        layout = QVBoxLayout(self)

        source = fragment.get("source") or {}
        info = QLabel(
            f"<b>{html_lib.escape(str(source.get('root_topic_title') or 'Fragmento'))}</b><br>"
            f"Origem: {html_lib.escape(str(source.get('manual_title') or 'manual desconhecido'))} "
            f"{html_lib.escape(str(source.get('manual_version') or ''))} · "
            f"{len(fragment.get('topics') or [])} tópico(s) · {len(fragment.get('assets') or {})} recurso(s)"
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        dest_box = QGroupBox("Destino")
        form = QFormLayout(dest_box)
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("Raiz do manual", None)
        # Hierarchical-looking labels in a flat combo.
        def add_children(parent_id: Optional[str], depth: int):
            for topic in project.children_of(parent_id):
                title = project.topic_title(topic, current_language)
                self.parent_combo.addItem(("   " * depth) + title, topic.id)
                add_children(topic.id, depth + 1)
        add_children(None, 0)
        idx = self.parent_combo.findData(selected_parent_id)
        if idx >= 0:
            self.parent_combo.setCurrentIndex(idx)
        form.addRow("Inserir como subtópico de:", self.parent_combo)
        layout.addWidget(dest_box)

        topics_box = QGroupBox("Tópicos do fragmento")
        tl = QVBoxLayout(topics_box)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.NoSelection)
        self._topic_items: Dict[str, QTreeWidgetItem] = {}
        rows = fragment_tree_rows(fragment)
        row_map = {str(r.get("source_id")): r for r in rows}
        pending = list(rows)
        item_map: Dict[str, QTreeWidgetItem] = {}
        guard = 0
        while pending and guard < len(rows) + 4:
            guard += 1
            rest = []
            progressed = False
            for row in pending:
                sid = str(row.get("source_id"))
                pid = row.get("parent_source_id")
                if pid and str(pid) not in item_map:
                    rest.append(row)
                    continue
                content = row.get("content") or {}
                src_default = str((fragment.get("source") or {}).get("default_language") or "")
                block = content.get(src_default) or (next(iter(content.values())) if content else {})
                item = QTreeWidgetItem([str(block.get("title") or "Tópico")])
                item.setData(0, Qt.UserRole, sid)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(0, Qt.Checked)
                if pid and str(pid) in item_map:
                    item_map[str(pid)].addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                item_map[sid] = item
                self._topic_items[sid] = item
                progressed = True
            if not progressed:
                for row in rest:
                    row["parent_source_id"] = None
            pending = rest
        self.tree.expandAll()
        tl.addWidget(self.tree, 1)
        row_buttons = QHBoxLayout()
        all_btn = QPushButton("Selecionar tudo")
        none_btn = QPushButton("Somente raiz")
        all_btn.clicked.connect(lambda: self._set_all_topics(True))
        none_btn.clicked.connect(lambda: self._set_only_root())
        row_buttons.addWidget(all_btn)
        row_buttons.addWidget(none_btn)
        row_buttons.addStretch(1)
        tl.addLayout(row_buttons)
        layout.addWidget(topics_box, 1)

        lang_box = QGroupBox("Mapeamento de idiomas")
        lang_form = QFormLayout(lang_box)
        self.language_combos: Dict[str, QComboBox] = {}
        existing = project.languages()
        for src in fragment.get("languages") or []:
            combo = QComboBox()
            combo.addItem("Ignorar este idioma", None)
            for dst in existing:
                combo.addItem(dst, dst)
            if src not in existing:
                combo.addItem(f"Adicionar {src} ao projeto", src)
            # Prefer same language, otherwise current editor language.
            idx = combo.findData(src)
            if idx < 0:
                idx = combo.findData(current_language)
            combo.setCurrentIndex(max(0, idx))
            self.language_combos[str(src)] = combo
            lang_form.addRow(str(src) + " →", combo)
        language_note = QLabel(
            "Se nenhum idioma for mapeado para o idioma padrão do projeto, o conteúdo principal "
            "do fragmento será usado como rascunho base para que o tópico nunca fique vazio."
        )
        language_note.setWordWrap(True)
        lang_form.addRow(language_note)
        layout.addWidget(lang_box)

        included_groups = list((fragment.get("options") or {}).get("style_groups") or [])
        self.style_checks: Dict[str, QCheckBox] = {}
        if included_groups:
            style_box = QGroupBox("Aplicar estilos globais que vieram no fragmento")
            sl = QVBoxLayout(style_box)
            warn = QLabel("Desmarcado por padrão para não alterar a aparência do projeto de destino.")
            warn.setWordWrap(True)
            sl.addWidget(warn)
            for key in included_groups:
                if key not in STYLE_GROUPS:
                    continue
                cb = QCheckBox(STYLE_GROUPS[key][0])
                cb.setChecked(False)
                self.style_checks[key] = cb
                sl.addWidget(cb)
            layout.addWidget(style_box)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        self.buttons.button(QDialogButtonBox.Ok).setText("Importar")
        self.buttons.accepted.connect(self._validate_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _set_all_topics(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for item in self._topic_items.values():
            item.setCheckState(0, state)

    def _set_only_root(self):
        root = str(self.fragment.get("root_source_id") or "")
        for sid, item in self._topic_items.items():
            item.setCheckState(0, Qt.Checked if sid == root else Qt.Unchecked)

    def _validate_accept(self):
        selected = self.selected_topic_ids()
        if not selected:
            QMessageBox.warning(self, "Fragmento", "Selecione pelo menos um tópico.")
            return
        destinations = [combo.currentData() for combo in self.language_combos.values() if combo.currentData()]
        if len(destinations) != len(set(destinations)):
            answer = QMessageBox.question(
                self, "Idiomas",
                "Dois idiomas do fragmento estão mapeados para o mesmo idioma de destino. O último pode sobrescrever o anterior. Continuar?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
        self.accept()

    def selected_topic_ids(self) -> List[str]:
        return [sid for sid, item in self._topic_items.items() if item.checkState(0) == Qt.Checked]

    def values(self) -> Dict[str, Any]:
        return {
            "selected_source_ids": self.selected_topic_ids(),
            "destination_parent_id": self.parent_combo.currentData(),
            "language_map": {src: combo.currentData() for src, combo in self.language_combos.items()},
            "apply_style_groups": [key for key, cb in self.style_checks.items() if cb.isChecked()],
        }
