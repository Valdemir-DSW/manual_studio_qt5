import base64
import json
import mimetypes
import os
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


DEFAULT_META = {
    "title": "Novo Manual",
    "author": "",
    "version": "1.0",
    "language": "pt-BR",
    "languages": ["pt-BR"],
    # Fluxo multilíngue: o idioma padrão é a fonte editorial.
    "language_copy_on_add": True,
    "language_sync_untranslated_from_default": True,
    "language_seed_new_topics": True,
    "footer_text": "",
    "logo_asset": "",

    # Layout / impressão
    "page_size": "A4",
    "page_orientation": "portrait",
    "margin_top_mm": 16.0,
    "margin_bottom_mm": 16.0,
    "margin_left_mm": 18.0,
    "margin_right_mm": 18.0,
    "header_enabled": True,
    "footer_enabled": True,
    "header_height_mm": 8.0,
    "footer_height_mm": 9.0,
    "header_gap_mm": 3.0,
    "footer_gap_mm": 3.0,
    "footer_logo": False,
    "footer_logo_width_mm": 18.0,

    # Cabeçalho / rodapé avançados.
    "header_template_html": (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        '<td>{{category}}</td><td align="right">{{title}} · v{{version}}</td>'
        '</tr></table>'
    ),
    "footer_template_html": (
        '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
        '<td>{{footer_text}}</td><td align="right">Página {{page}} de {{pages}}</td>'
        '</tr></table>'
    ),
    "header_background_type": "none",
    "header_background_color1": "#ffffff",
    "header_background_color2": "#e9edf2",
    "header_gradient_direction": "horizontal",
    "header_background_asset": "",
    "header_background_fit": "cover",
    "header_background_opacity": 100,
    "header_separator_enabled": True,
    "header_separator_color": "#c8cdd3",
    "header_separator_width_pt": 0.8,
    "header_logo_width_mm": 18.0,
    "header_padding_left_mm": 2.0,
    "header_padding_right_mm": 2.0,
    "footer_background_type": "none",
    "footer_background_color1": "#ffffff",
    "footer_background_color2": "#e9edf2",
    "footer_gradient_direction": "horizontal",
    "footer_background_asset": "",
    "footer_background_fit": "cover",
    "footer_background_opacity": 100,
    "footer_separator_enabled": True,
    "footer_separator_color": "#c8cdd3",
    "footer_separator_width_pt": 0.8,
    "footer_padding_left_mm": 2.0,
    "footer_padding_right_mm": 2.0,

    # Tipografia
    "body_font_family": "Arial",
    "body_font_size_pt": 10.5,
    "heading1_size_pt": 20.0,
    "heading2_size_pt": 16.0,
    "heading3_size_pt": 13.0,
    "line_height_percent": 118,
    "paragraph_spacing_pt": 5.0,

    # Estrutura automática
    "cover_enabled": True,
    "toc_enabled": True,

    # PDF. O exportador usa composição independente por seção/tópico para
    # evitar que capítulos diferentes sejam "emendados" na mesma página.
    "pdf_cover_enabled": True,
    "pdf_toc_enabled": True,
    "pdf_toc_page_numbers": True,
    "pdf_toc_title": "Sumário",
    "pdf_toc_font_size_pt": 10.5,
    "pdf_topic_title_enabled": True,
    "pdf_topic_numbering": True,
    "pdf_topic_title_size_pt": 20.0,
    "pdf_reclaim_hidden_header_footer_space": True,
    "pdf_header_on_cover": False,
    "pdf_footer_on_cover": False,
    "pdf_header_on_toc": False,
    "pdf_footer_on_toc": False,
    "pdf_resolution_dpi": 300,
    "pdf_page_number_start": 1,

    # HTML / WebHelp. O CSS livre é acrescentado por último e pode sobrescrever
    # qualquer regra base sem alterar o conteúdo do manual.
    "html_accent": "#1769aa",
    "html_background": "#ffffff",
    "html_text": "#1f2933",
    "html_sidebar_background": "#f5f7fa",
    "html_topbar_background": "#ffffff",
    "html_sidebar_width_px": 300,
    "html_content_width_px": 900,
    "html_tree_lines": True,
    "html_tree_expand_default": True,
    "html_toc_enabled": True,
    "html_toc_title": "Sumário",
    "html_toc_description": "Navegue pelos tópicos deste manual.",
    "html_intro_enabled": True,
    "html_intro_title": "",
    "html_intro_subtitle": "Manual do usuário",
    "html_intro_show_logo": True,
    "html_intro_show_version": True,
    "html_intro_show_author": True,
    "html_intro_show_toc": True,
    "html_intro_body_html": "<p>Selecione um tópico na árvore de navegação para começar.</p>",
    "html_custom_css": "",
    "html_manual_icon_asset": "",
    "html_project_url": "https://github.com/Valdemir-DSW/manual_studio_qt5",
    "html_show_project_link": True,

    # Capa e sumário específicos do PDF.
    "pdf_cover_background_type": "none",
    "pdf_cover_background_color1": "#ffffff",
    "pdf_cover_background_color2": "#e9edf2",
    "pdf_cover_gradient_direction": "vertical",
    "pdf_cover_background_asset": "",
    "pdf_cover_background_fit": "cover",
    "pdf_cover_background_opacity": 100,
    "pdf_cover_background_scale_percent": 100,
    "pdf_cover_background_x_percent": 50,
    "pdf_cover_background_y_percent": 50,
    "pdf_cover_logo_asset": "",
    "pdf_cover_title_color": "#1f2933",
    "pdf_cover_logo_width_mm": 42.0,
    "pdf_cover_title_size_pt": 30.0,
    "pdf_cover_vertical_offset_mm": 42.0,
    "pdf_cover_alignment": "center",
    "pdf_cover_show_logo": True,
    "pdf_cover_show_title": True,
    "pdf_cover_show_author": True,
    "pdf_cover_show_version": True,
    "pdf_cover_show_language": True,
    "pdf_cover_title": "",
    "pdf_cover_subtitle": "",
    "pdf_toc_intro_html": "",
}


@dataclass
class Topic:
    id: str
    title: str
    html: str = ""
    parent_id: Optional[str] = None
    order: int = 0
    # normal | toc | revisions. Tipos especiais continuam editáveis, mas o
    # exportador injeta o conteúdo automático correspondente.
    kind: str = "normal"
    # None = herdar do documento. False/True substitui só neste tópico.
    show_header: Optional[bool] = None
    show_footer: Optional[bool] = None
    exclude_from_toc: bool = False
    # Traduções adicionais. O idioma padrão continua em title/html para manter
    # compatibilidade com os projetos antigos.
    translations: Dict[str, Dict[str, str]] = field(default_factory=dict)


@dataclass
class Asset:
    id: str
    filename: str
    mime: str
    data_b64: str

    def bytes(self) -> bytes:
        return base64.b64decode(self.data_b64.encode("ascii"))


@dataclass
class ManualProject:
    format_version: int = 8
    meta: Dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_META))
    topics: List[Topic] = field(default_factory=list)
    assets: Dict[str, Asset] = field(default_factory=dict)

    @classmethod
    def new(cls, template: str = "blank"):
        p = cls()
        template = (template or "blank").lower()
        if template == "technical":
            p.meta["title"] = "Manual Técnico"
            intro = Topic(str(uuid.uuid4()), "Introdução", "<p>Apresente o produto, objetivo e escopo deste manual.</p>", show_header=False, show_footer=False)
            safety = Topic(str(uuid.uuid4()), "Segurança", "<p>Registre avisos, riscos e requisitos de segurança.</p>", order=1)
            install = Topic(str(uuid.uuid4()), "Instalação", "<p>Descreva pré-requisitos, montagem e primeira instalação.</p>", order=2)
            operation = Topic(str(uuid.uuid4()), "Operação", "<p>Explique a operação normal passo a passo.</p>", order=3)
            diag = Topic(str(uuid.uuid4()), "Diagnóstico", "<p>Inclua sintomas, causas prováveis e verificações.</p>", order=4)
            maint = Topic(str(uuid.uuid4()), "Manutenção", "<p>Defina inspeções, intervalos e procedimentos.</p>", order=5)
            specs = Topic(str(uuid.uuid4()), "Especificações", "<p>Inclua limites, tabelas e dados técnicos.</p>", order=6)
            rev = Topic(str(uuid.uuid4()), "Revisões", cls._revision_template_html(), order=7, kind="revisions", exclude_from_toc=True)
            p.topics.extend([intro, safety, install, operation, diag, maint, specs, rev])
        elif template == "software":
            p.meta["title"] = "Manual do Usuário"
            rows = [
                ("Introdução", "<p>Apresente o software e o público-alvo.</p>"),
                ("Instalação", "<p>Explique instalação, requisitos e ativação.</p>"),
                ("Primeiros passos", "<p>Crie um roteiro curto para a primeira utilização.</p>"),
                ("Interface", "<p>Descreva menus, telas e principais comandos.</p>"),
                ("Configurações", "<p>Documente preferências e parâmetros.</p>"),
                ("Solução de problemas", "<p>Liste problemas comuns e correções.</p>"),
            ]
            for i, (title, body) in enumerate(rows):
                p.topics.append(Topic(str(uuid.uuid4()), title, body, order=i, show_header=False if i == 0 else None, show_footer=False if i == 0 else None))
            p.topics.append(Topic(str(uuid.uuid4()), "Revisões", cls._revision_template_html(), order=len(rows), kind="revisions", exclude_from_toc=True))
        else:
            p.topics.append(Topic(
                id=str(uuid.uuid4()),
                title="Introdução",
                html="<p>Comece a escrever o manual aqui.</p>",
                parent_id=None,
                order=0,
                show_header=False,
                show_footer=False,
            ))
        return p

    @staticmethod
    def _revision_template_html():
        return (
            '<p>Registre as alterações relevantes entre versões.</p>'
            '<table border="1" cellspacing="0" cellpadding="5" width="100%">'
            '<tr><td><b>Versão</b></td><td><b>Data</b></td><td><b>Descrição</b></td><td><b>Responsável</b></td></tr>'
            '<tr><td>1.0</td><td></td><td>Emissão inicial.</td><td></td></tr>'
            '</table>'
        )

    def languages(self) -> List[str]:
        langs = self.meta.get("languages") or [self.meta.get("language", "pt-BR")]
        if isinstance(langs, str):
            langs = [langs]
        out = []
        for lang in langs:
            lang = str(lang).strip()
            if lang and lang not in out:
                out.append(lang)
        default = str(self.meta.get("language", "pt-BR"))
        if default not in out:
            out.insert(0, default)
        return out or ["pt-BR"]

    def change_default_language(self, new_default: str):
        new_default = str(new_default or "").strip()
        old_default = str(self.meta.get("language", "pt-BR"))
        if not new_default or new_default == old_default:
            return
        for topic in self.topics:
            old_entry = topic.translations.setdefault(old_default, {})
            old_entry["title"] = topic.title
            old_entry["html"] = topic.html
            old_entry.pop("_source_title", None)
            old_entry.pop("_source_html", None)
            incoming = topic.translations.pop(new_default, None)
            if incoming:
                topic.title = str(incoming.get("title") or topic.title)
                topic.html = str(incoming.get("html") or topic.html)
        langs = self.languages()
        if new_default not in langs:
            langs.append(new_default)
        if old_default not in langs:
            langs.append(old_default)
        self.meta["language"] = new_default
        self.meta["languages"] = [new_default] + [x for x in langs if x != new_default]
        # A troca da fonte editorial invalida marcadores da fonte anterior.
        for topic in self.topics:
            for lang, entry in topic.translations.items():
                entry.pop("_source_title", None)
                entry.pop("_source_html", None)
                if lang != new_default and entry.get("title") == topic.title:
                    entry["_source_title"] = topic.title
                if lang != new_default and entry.get("html") == topic.html:
                    entry["_source_html"] = topic.html

    def topic_title(self, topic: Topic, language: Optional[str] = None) -> str:
        language = language or str(self.meta.get("language", "pt-BR"))
        default = str(self.meta.get("language", "pt-BR"))
        if language == default:
            return topic.title
        tr = topic.translations.get(language, {}) if topic.translations else {}
        return str(tr.get("title") or topic.title)

    def topic_html(self, topic: Topic, language: Optional[str] = None) -> str:
        language = language or str(self.meta.get("language", "pt-BR"))
        default = str(self.meta.get("language", "pt-BR"))
        if language == default:
            return topic.html
        tr = topic.translations.get(language, {}) if topic.translations else {}
        return str(tr.get("html") or topic.html)

    def set_topic_translation(self, topic: Topic, language: str, title: Optional[str] = None, html: Optional[str] = None):
        """Atualiza um idioma sem sobrescrever traduções já alteradas.

        Quando o idioma padrão é editado, cópias ainda intactas (criadas pelo
        gerenciador de idiomas) podem acompanhar a fonte automaticamente. Uma
        tradução que já divergiu da última cópia-fonte é considerada editada e
        nunca é substituída silenciosamente.
        """
        default = str(self.meta.get("language", "pt-BR"))
        if language == default:
            old_title, old_html = topic.title, topic.html
            if title is not None:
                topic.title = title
            if html is not None:
                topic.html = html

            if bool(self.meta.get("language_sync_untranslated_from_default", True)):
                for lang in self.languages():
                    if lang == default:
                        continue
                    entry = topic.translations.get(lang)
                    if not entry:
                        continue
                    if title is not None and entry.get("_source_title") == old_title and entry.get("title") == old_title:
                        entry["title"] = topic.title
                        entry["_source_title"] = topic.title
                    if html is not None and entry.get("_source_html") == old_html and entry.get("html") == old_html:
                        entry["html"] = topic.html
                        entry["_source_html"] = topic.html
            return

        entry = topic.translations.setdefault(language, {})
        if title is not None:
            entry["title"] = title
        if html is not None:
            entry["html"] = html

    def copy_language(self, source: str, target: str, overwrite: bool = True, mark_seeded: bool = True):
        """Copia títulos e textos entre idiomas; a árvore/estrutura é sempre compartilhada."""
        source, target = str(source or "").strip(), str(target or "").strip()
        if not source or not target or source == target:
            return
        default = str(self.meta.get("language", "pt-BR"))
        for topic in self.topics:
            src_title = self.topic_title(topic, source)
            src_html = self.topic_html(topic, source)
            if target == default:
                if overwrite or not topic.title:
                    topic.title = src_title
                if overwrite or not topic.html:
                    topic.html = src_html
                continue
            entry = topic.translations.setdefault(target, {})
            if overwrite or not entry.get("title"):
                entry["title"] = src_title
            if overwrite or not entry.get("html"):
                entry["html"] = src_html
            if mark_seeded and source == default:
                entry["_source_title"] = src_title
                entry["_source_html"] = src_html
            else:
                entry.pop("_source_title", None)
                entry.pop("_source_html", None)

    def seed_language_from_default(self, target: str, overwrite: bool = False):
        default = str(self.meta.get("language", "pt-BR"))
        self.copy_language(default, target, overwrite=overwrite, mark_seeded=True)

    def topic_by_id(self, topic_id: str) -> Optional[Topic]:
        for topic in self.topics:
            if topic.id == topic_id:
                return topic
        return None

    def children_of(self, parent_id: Optional[str]) -> List[Topic]:
        return sorted(
            [t for t in self.topics if t.parent_id == parent_id],
            key=lambda t: (t.order, t.title.lower()),
        )

    def add_topic(self, title: str, parent_id: Optional[str] = None, kind: str = "normal") -> Topic:
        siblings = self.children_of(parent_id)
        topic = Topic(
            id=str(uuid.uuid4()),
            title=title,
            html="<p></p>",
            parent_id=parent_id,
            order=len(siblings),
            kind=kind,
        )
        if kind == "toc":
            topic.html = "<p>Você pode escrever uma introdução acima ou abaixo do sumário automático.</p>"
            topic.exclude_from_toc = True
            topic.show_header = False
            topic.show_footer = False
        elif kind == "revisions":
            topic.html = self._revision_template_html()
            topic.exclude_from_toc = True
        self.topics.append(topic)
        if bool(self.meta.get("language_seed_new_topics", True)):
            default = str(self.meta.get("language", "pt-BR"))
            for lang in self.languages():
                if lang == default:
                    continue
                topic.translations[lang] = {
                    "title": topic.title, "html": topic.html,
                    "_source_title": topic.title, "_source_html": topic.html,
                }
        return topic

    def delete_topic_recursive(self, topic_id: str):
        descendants = []
        stack = [topic_id]
        while stack:
            current = stack.pop()
            descendants.append(current)
            stack.extend(t.id for t in self.topics if t.parent_id == current)
        self.topics = [t for t in self.topics if t.id not in descendants]

    def add_asset_from_file(self, path: str) -> Asset:
        with open(path, "rb") as f:
            raw = f.read()
        return self.add_asset_bytes(raw, os.path.basename(path), mimetypes.guess_type(path)[0])

    def replace_asset_from_file(self, asset_id: str, path: str) -> Optional[Asset]:
        asset = self.assets.get(asset_id)
        if not asset:
            return None
        with open(path, "rb") as f:
            raw = f.read()
        asset.filename = os.path.basename(path)
        asset.mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        asset.data_b64 = base64.b64encode(raw).decode("ascii")
        return asset

    def add_asset_bytes(self, raw: bytes, filename: str, mime: Optional[str] = None) -> Asset:
        asset_id = str(uuid.uuid4())
        mime = mime or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        asset = Asset(
            id=asset_id,
            filename=filename,
            mime=mime,
            data_b64=base64.b64encode(raw).decode("ascii"),
        )
        self.assets[asset_id] = asset
        return asset

    def to_dict(self):
        return {
            "format_version": self.format_version,
            "meta": dict(self.meta),
            "topics": [asdict(t) for t in self.topics],
            "assets": {k: asdict(v) for k, v in self.assets.items()},
        }

    @classmethod
    def from_dict(cls, data):
        p = cls()
        p.format_version = max(8, int(data.get("format_version", 1)))
        p.meta.update(data.get("meta", {}))
        p.meta.setdefault("languages", [p.meta.get("language", "pt-BR")])
        p.topics = []
        for raw in data.get("topics", []):
            allowed = {k: raw[k] for k in Topic.__dataclass_fields__.keys() if k in raw}
            p.topics.append(Topic(**allowed))
        p.assets = {k: Asset(**v) for k, v in data.get("assets", {}).items()}
        if not p.topics:
            p.topics.append(Topic(id=str(uuid.uuid4()), title="Introdução", html="<p></p>", show_header=False, show_footer=False))
        return p

    def save(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(json.load(f))
