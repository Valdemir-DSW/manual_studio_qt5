from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QImage, QTextCharFormat, QTextCursor, QTextLength
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QColorDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QToolButton,
    QWidget,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
)

from .ui_extras import BandPreview, HtmlStyleDialog


PAGE_DIMENSIONS_MM = {
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Carta": (215.9, 279.4),
    "Ofício": (215.9, 355.6),
}


def _dspin(value, minimum=0.0, maximum=100.0, decimals=1, suffix=" mm"):
    w = QDoubleSpinBox()
    w.setRange(minimum, maximum)
    w.setDecimals(decimals)
    w.setSingleStep(1.0)
    w.setSuffix(suffix)
    w.setValue(float(value))
    return w


class ProjectPropertiesDialog(QDialog):
    """Metadados do manual e acesso ao designer avançado de cabeçalho/rodapé."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Propriedades do manual")
        self.resize(760, 520)
        self.project = project
        self._new_logo_path = None
        self._draft_meta = dict(project.meta)

        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        general_tab = QWidget()
        general_layout = QVBoxLayout(general_tab)
        form = QFormLayout()
        self.title_edit = QLineEdit(project.meta.get("title", ""))
        self.author_edit = QLineEdit(project.meta.get("author", ""))
        self.version_edit = QLineEdit(project.meta.get("version", ""))
        self.language_combo = QComboBox()
        self.language_combo.addItems(["pt-BR", "en-US", "es-ES", "de-DE", "fr-FR"])
        current_lang = project.meta.get("language", "pt-BR")
        idx = self.language_combo.findText(current_lang)
        if idx < 0 and current_lang:
            self.language_combo.addItem(current_lang)
            idx = self.language_combo.findText(current_lang)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)
        self.footer_edit = QLineEdit(project.meta.get("footer_text", ""))

        form.addRow("Título:", self.title_edit)
        form.addRow("Autor/empresa:", self.author_edit)
        form.addRow("Versão do manual:", self.version_edit)
        form.addRow("Idioma:", self.language_combo)
        form.addRow("Texto livre do rodapé:", self.footer_edit)

        logo_row = QHBoxLayout()
        self.logo_label = QLabel(self._logo_text())
        logo_btn = QPushButton("Selecionar logo...")
        logo_btn.clicked.connect(self.select_logo)
        clear_btn = QPushButton("Remover")
        clear_btn.clicked.connect(self.clear_logo)
        logo_row.addWidget(self.logo_label, 1)
        logo_row.addWidget(logo_btn)
        logo_row.addWidget(clear_btn)
        form.addRow("Logo principal:", logo_row)

        general_layout.addLayout(form)
        version_note = QLabel(
            "A versão configurada aqui é a fonte única do campo dinâmico {{version}}. "
            "Ao alterar a versão, cabeçalhos e rodapés que usam esse item são atualizados automaticamente na próxima exportação."
        )
        version_note.setWordWrap(True)
        version_note.setStyleSheet("color:#666; padding-top:8px;")
        general_layout.addWidget(version_note)
        general_layout.addStretch(1)
        tabs.addTab(general_tab, "Geral")

        hf_tab = QWidget()
        hf_layout = QVBoxLayout(hf_tab)
        info = QLabel(
            "Cabeçalho e rodapé podem ter texto rico, fontes diferentes, logo, cores, gradiente, "
            "imagem de fundo e itens dinâmicos como página, total de páginas, versão, tópico e categoria."
        )
        info.setWordWrap(True)
        hf_layout.addWidget(info)

        header_group = QGroupBox("Cabeçalho")
        header_box = QVBoxLayout(header_group)
        self.header_status = QLabel()
        header_box.addWidget(self.header_status)
        self.header_preview = BandPreview(self.project, "header", self._preview_meta, self)
        header_box.addWidget(self.header_preview)
        header_btn = QPushButton("Editar cabeçalho...")
        header_btn.clicked.connect(lambda: self.edit_header_footer("header"))
        header_box.addWidget(header_btn)
        hf_layout.addWidget(header_group)

        footer_group = QGroupBox("Rodapé")
        footer_box = QVBoxLayout(footer_group)
        self.footer_status = QLabel()
        footer_box.addWidget(self.footer_status)
        self.footer_preview = BandPreview(self.project, "footer", self._preview_meta, self)
        footer_box.addWidget(self.footer_preview)
        footer_btn = QPushButton("Editar rodapé...")
        footer_btn.clicked.connect(lambda: self.edit_header_footer("footer"))
        footer_box.addWidget(footer_btn)
        hf_layout.addWidget(footer_group)

        tokens = QLabel(
            "Itens dinâmicos disponíveis: {{title}}, {{author}}, {{version}}, {{page}}, {{pages}}, "
            "{{topic}}, {{category}}, {{date}}, {{language}}, {{footer_text}} e {{logo}}."
        )
        tokens.setWordWrap(True)
        tokens.setStyleSheet("color:#666; padding-top:6px;")
        hf_layout.addWidget(tokens)
        hf_layout.addStretch(1)
        tabs.addTab(hf_tab, "Cabeçalho e rodapé")

        html_tab = QWidget()
        html_layout = QVBoxLayout(html_tab)
        html_info = QLabel(
            "A exportação HTML possui ajustes rápidos e uma folha CSS livre. O CSS personalizado é aplicado por último, "
            "então pode sobrescrever o estilo base sem alterar os tópicos."
        )
        html_info.setWordWrap(True)
        html_layout.addWidget(html_info)
        html_btn = QPushButton("Editar estilo HTML / CSS...")
        html_btn.clicked.connect(self.edit_html_style)
        html_layout.addWidget(html_btn)
        html_layout.addStretch(1)
        tabs.addTab(html_tab, "HTML / CSS")

        self._refresh_hf_status()
        for widget in (self.title_edit, self.author_edit, self.version_edit, self.footer_edit):
            widget.textChanged.connect(lambda _=None: (self.header_preview.update(), self.footer_preview.update()))
        self.language_combo.currentTextChanged.connect(lambda _=None: (self.header_preview.update(), self.footer_preview.update()))

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _preview_meta(self):
        data = dict(self._draft_meta)
        data["title"] = self.title_edit.text().strip() or "Manual"
        data["author"] = self.author_edit.text().strip()
        data["version"] = self.version_edit.text().strip()
        data["language"] = self.language_combo.currentText()
        data["footer_text"] = self.footer_edit.text().strip()
        if self._new_logo_path is not None:
            data["_preview_logo_path"] = self._new_logo_path
        return data

    def _logo_text(self):
        aid = self.project.meta.get("logo_asset", "")
        if aid and aid in self.project.assets:
            return self.project.assets[aid].filename
        return "Nenhum"

    def _refresh_hf_status(self):
        h_bg = str(self._draft_meta.get("header_background_type", "none"))
        f_bg = str(self._draft_meta.get("footer_background_type", "none"))
        self.header_status.setText(
            f"{'Ativo' if self._draft_meta.get('header_enabled', True) else 'Desativado'} • "
            f"{float(self._draft_meta.get('header_height_mm', 8)):.1f} mm • fundo: {h_bg}"
        )
        self.footer_status.setText(
            f"{'Ativo' if self._draft_meta.get('footer_enabled', True) else 'Desativado'} • "
            f"{float(self._draft_meta.get('footer_height_mm', 9)):.1f} mm • fundo: {f_bg}"
        )
        if hasattr(self, "header_preview"):
            self.header_preview.update()
        if hasattr(self, "footer_preview"):
            self.footer_preview.update()

    def edit_header_footer(self, section):
        dlg = HeaderFooterDesignerDialog(self.project, section, self._draft_meta, self)
        if dlg.exec_():
            dlg.apply()
            self._refresh_hf_status()

    def edit_html_style(self):
        dlg = HtmlStyleDialog(self.project, self, meta=self._draft_meta)
        if dlg.exec_():
            dlg.apply()

    def select_logo(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar logo", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self._new_logo_path = path
            self.logo_label.setText(path.split("/")[-1].split("\\")[-1])
            self.header_preview.update(); self.footer_preview.update()

    def clear_logo(self):
        self._new_logo_path = ""
        self.logo_label.setText("Nenhum")
        self.header_preview.update(); self.footer_preview.update()

    def apply(self):
        # Primeiro aplica o rascunho visual; em seguida os metadados gerais,
        # garantindo que {{version}} e demais tokens usem sempre o valor final.
        self.project.meta.update(self._draft_meta)
        self.project.meta["title"] = self.title_edit.text().strip() or "Manual"
        self.project.meta["author"] = self.author_edit.text().strip()
        self.project.meta["version"] = self.version_edit.text().strip()
        new_language = self.language_combo.currentText()
        if hasattr(self.project, "change_default_language"):
            self.project.change_default_language(new_language)
        else:
            self.project.meta["language"] = new_language
        langs = self.project.meta.get("languages") or [new_language]
        if new_language not in langs:
            langs.insert(0, new_language)
        self.project.meta["languages"] = langs
        self.project.meta["footer_text"] = self.footer_edit.text().strip()
        if self._new_logo_path == "":
            self.project.meta["logo_asset"] = ""
        elif self._new_logo_path:
            asset = self.project.add_asset_from_file(self._new_logo_path)
            self.project.meta["logo_asset"] = asset.id


class _ColorButton(QPushButton):
    def __init__(self, color="#ffffff", parent=None):
        super().__init__(parent)
        self._color = QColor(color if QColor(color).isValid() else "#ffffff")
        self.clicked.connect(self._choose)
        self._sync()

    def color_name(self):
        return self._color.name()

    def set_color(self, color):
        c = QColor(color)
        if c.isValid():
            self._color = c
            self._sync()

    def _sync(self):
        fg = "#000000" if self._color.lightness() > 145 else "#ffffff"
        self.setText(self._color.name().upper())
        self.setStyleSheet(
            f"QPushButton{{background:{self._color.name()};color:{fg};border:1px solid #777;padding:5px 10px;}}"
        )

    def _choose(self):
        c = QColorDialog.getColor(self._color, self, "Selecionar cor")
        if c.isValid():
            self._color = c
            self._sync()


class _TemplateEditor(QWidget):
    TOKENS = [
        ("Título", "{{title}}"),
        ("Autor", "{{author}}"),
        ("Versão", "{{version}}"),
        ("Página", "{{page}}"),
        ("Total de páginas", "{{pages}}"),
        ("Tópico atual", "{{topic}}"),
        ("Categoria", "{{category}}"),
        ("Data", "{{date}}"),
        ("Idioma", "{{language}}"),
        ("Texto livre do rodapé", "{{footer_text}}"),
        ("Logo", "{{logo}}"),
    ]

    def __init__(self, html_text="", parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        bar = QHBoxLayout()
        self.font = QComboBox()
        self.font.setEditable(True)
        self.font.addItems(QFontDatabase().families())
        self.font.setCurrentText("Arial")
        self.font.setMinimumWidth(150)
        self.size = QSpinBox()
        self.size.setRange(6, 48)
        self.size.setValue(9)
        self.size.setSuffix(" pt")
        bar.addWidget(self.font)
        bar.addWidget(self.size)

        for text, tip, callback in (
            ("B", "Negrito", self._bold),
            ("I", "Itálico", self._italic),
            ("U", "Sublinhado", self._underline),
        ):
            b = QToolButton()
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(callback)
            bar.addWidget(b)

        color_btn = QToolButton()
        color_btn.setText("A▾")
        color_btn.setToolTip("Cor do texto")
        color_btn.clicked.connect(self._text_color)
        bar.addWidget(color_btn)

        for text, align in (("≡←", Qt.AlignLeft), ("≡", Qt.AlignHCenter), ("→≡", Qt.AlignRight)):
            b = QToolButton()
            b.setText(text)
            b.clicked.connect(lambda _=False, a=align: self.edit.setAlignment(a))
            bar.addWidget(b)
        bar.addStretch(1)
        root.addLayout(bar)

        token_bar = QHBoxLayout()
        token_bar.addWidget(QLabel("Inserir item dinâmico:"))
        self.token_combo = QComboBox()
        for label, token in self.TOKENS:
            self.token_combo.addItem(label, token)
        insert = QPushButton("Inserir")
        insert.clicked.connect(self.insert_token)
        token_bar.addWidget(self.token_combo, 1)
        token_bar.addWidget(insert)
        root.addLayout(token_bar)

        self.edit = QTextEdit()
        self.edit.setAcceptRichText(True)
        self.edit.setMinimumHeight(135)
        self.edit.setHtml(html_text or "<p></p>")
        root.addWidget(self.edit, 1)

        self.font.currentTextChanged.connect(self._font_family)
        self.size.valueChanged.connect(self._font_size)

    def toHtml(self):
        return self.edit.toHtml()

    def setHtml(self, value):
        self.edit.setHtml(value or "<p></p>")

    def insert_token(self):
        token = str(self.token_combo.currentData() or "")
        self.edit.textCursor().insertText(token)
        self.edit.setFocus()

    def _merge(self, fmt):
        cursor = self.edit.textCursor()
        if not cursor.hasSelection():
            self.edit.mergeCurrentCharFormat(fmt)
        else:
            cursor.mergeCharFormat(fmt)
        self.edit.setFocus()

    def _font_family(self, family):
        fmt = QTextCharFormat()
        fmt.setFontFamily(family)
        self._merge(fmt)

    def _font_size(self, size):
        fmt = QTextCharFormat()
        fmt.setFontPointSize(float(size))
        self._merge(fmt)

    def _bold(self):
        fmt = QTextCharFormat()
        fmt.setFontWeight(QFont.Bold if self.edit.fontWeight() != QFont.Bold else QFont.Normal)
        self._merge(fmt)

    def _italic(self):
        fmt = QTextCharFormat()
        fmt.setFontItalic(not self.edit.fontItalic())
        self._merge(fmt)

    def _underline(self):
        fmt = QTextCharFormat()
        fmt.setFontUnderline(not self.edit.fontUnderline())
        self._merge(fmt)

    def _text_color(self):
        c = QColorDialog.getColor(self.edit.textColor(), self, "Cor do texto")
        if c.isValid():
            fmt = QTextCharFormat()
            fmt.setForeground(c)
            self._merge(fmt)


class HeaderFooterDesignerDialog(QDialog):
    """Designer rico e persistente para uma faixa de cabeçalho ou rodapé."""

    def __init__(self, project, section, meta, parent=None):
        super().__init__(parent)
        self.project = project
        self.section = "header" if section == "header" else "footer"
        self.meta = meta
        self._new_bg_path = None
        label = "Cabeçalho" if self.section == "header" else "Rodapé"
        self.setWindowTitle(f"Personalizar {label.lower()}")
        self.resize(820, 700)

        root = QVBoxLayout(self)

        top = QHBoxLayout()
        self.enabled = QCheckBox(f"Exibir {label.lower()}")
        self.enabled.setChecked(bool(meta.get(f"{self.section}_enabled", True)))
        self.height = _dspin(meta.get(f"{self.section}_height_mm", 8 if self.section == "header" else 9), 4, 45)
        self.gap = _dspin(meta.get(f"{self.section}_gap_mm", 3), 0, 20)
        top.addWidget(self.enabled)
        top.addStretch(1)
        top.addWidget(QLabel("Altura:"))
        top.addWidget(self.height)
        top.addWidget(QLabel("Distância do conteúdo:"))
        top.addWidget(self.gap)
        root.addLayout(top)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Modelo:"))
        self.preset = QComboBox()
        self.preset.addItems(["Manter atual", "Técnico limpo", "Faixa escura", "Minimalista"])
        preset_row.addWidget(self.preset, 1)
        apply_preset = QPushButton("Aplicar modelo")
        apply_preset.clicked.connect(self._apply_preset)
        preset_row.addWidget(apply_preset)
        root.addLayout(preset_row)

        self.preview = BandPreview(self.project, self.section, self._preview_meta, self)
        root.addWidget(self.preview)

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # Conteúdo rico
        content_tab = QWidget()
        content_layout = QVBoxLayout(content_tab)
        self.template = _TemplateEditor(str(meta.get(f"{self.section}_template_html", "")))
        content_layout.addWidget(self.template, 1)

        logo_form = QFormLayout()
        self.logo_width = _dspin(
            meta.get(f"{self.section}_logo_width_mm", meta.get("footer_logo_width_mm", 18)), 5, 60
        )
        logo_form.addRow("Largura de {{logo}}:", self.logo_width)
        content_layout.addLayout(logo_form)
        note = QLabel(
            "Os itens entre {{chaves}} são resolvidos somente na exportação. "
            "Assim, {{version}} sempre acompanha a versão definida nas Propriedades do manual."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#666;")
        content_layout.addWidget(note)
        tabs.addTab(content_tab, "Conteúdo")

        # Fundo
        bg_tab = QWidget()
        bg_layout = QVBoxLayout(bg_tab)
        bg_group = QGroupBox("Fundo da faixa")
        bg_form = QFormLayout(bg_group)
        self.bg_type = QComboBox()
        self.bg_type.addItem("Sem fundo", "none")
        self.bg_type.addItem("Cor sólida", "solid")
        self.bg_type.addItem("Gradiente", "gradient")
        self.bg_type.addItem("Imagem", "image")
        idx = self.bg_type.findData(meta.get(f"{self.section}_background_type", "none"))
        self.bg_type.setCurrentIndex(max(0, idx))
        self.color1 = _ColorButton(meta.get(f"{self.section}_background_color1", "#ffffff"))
        self.color2 = _ColorButton(meta.get(f"{self.section}_background_color2", "#e9edf2"))
        self.gradient_direction = QComboBox()
        self.gradient_direction.addItem("Horizontal", "horizontal")
        self.gradient_direction.addItem("Vertical", "vertical")
        self.gradient_direction.addItem("Diagonal", "diagonal")
        gidx = self.gradient_direction.findData(meta.get(f"{self.section}_gradient_direction", "horizontal"))
        self.gradient_direction.setCurrentIndex(max(0, gidx))
        self.opacity = QSpinBox()
        self.opacity.setRange(0, 100)
        self.opacity.setSuffix(" %")
        self.opacity.setValue(int(meta.get(f"{self.section}_background_opacity", 100)))
        bg_form.addRow("Tipo:", self.bg_type)
        bg_form.addRow("Cor 1:", self.color1)
        bg_form.addRow("Cor 2:", self.color2)
        bg_form.addRow("Direção do gradiente:", self.gradient_direction)
        bg_form.addRow("Opacidade:", self.opacity)

        image_row = QHBoxLayout()
        self.bg_image_label = QLabel(self._asset_label(meta.get(f"{self.section}_background_asset", "")))
        choose_img = QPushButton("Selecionar...")
        choose_img.clicked.connect(self._select_bg_image)
        remove_img = QPushButton("Remover")
        remove_img.clicked.connect(self._remove_bg_image)
        image_row.addWidget(self.bg_image_label, 1)
        image_row.addWidget(choose_img)
        image_row.addWidget(remove_img)
        bg_form.addRow("Imagem:", image_row)

        self.bg_fit = QComboBox()
        self.bg_fit.addItem("Cobrir a faixa", "cover")
        self.bg_fit.addItem("Conter inteira", "contain")
        self.bg_fit.addItem("Esticar", "stretch")
        fit_idx = self.bg_fit.findData(meta.get(f"{self.section}_background_fit", "cover"))
        self.bg_fit.setCurrentIndex(max(0, fit_idx))
        bg_form.addRow("Ajuste da imagem:", self.bg_fit)
        bg_layout.addWidget(bg_group)
        bg_layout.addStretch(1)
        tabs.addTab(bg_tab, "Fundo")

        # Espaçamento e separador
        detail_tab = QWidget()
        detail_layout = QVBoxLayout(detail_tab)
        pad_group = QGroupBox("Espaçamento interno")
        pad_form = QFormLayout(pad_group)
        self.pad_left = _dspin(meta.get(f"{self.section}_padding_left_mm", 2), 0, 30)
        self.pad_right = _dspin(meta.get(f"{self.section}_padding_right_mm", 2), 0, 30)
        pad_form.addRow("Esquerda:", self.pad_left)
        pad_form.addRow("Direita:", self.pad_right)
        detail_layout.addWidget(pad_group)

        sep_group = QGroupBox("Linha separadora")
        sep_form = QFormLayout(sep_group)
        self.separator = QCheckBox("Exibir linha separadora")
        self.separator.setChecked(bool(meta.get(f"{self.section}_separator_enabled", True)))
        self.separator_color = _ColorButton(meta.get(f"{self.section}_separator_color", "#c8cdd3"))
        self.separator_width = _dspin(meta.get(f"{self.section}_separator_width_pt", 0.8), 0.2, 6, 1, " pt")
        sep_form.addRow(self.separator)
        sep_form.addRow("Cor:", self.separator_color)
        sep_form.addRow("Espessura:", self.separator_width)
        detail_layout.addWidget(sep_group)
        detail_layout.addStretch(1)
        tabs.addTab(detail_tab, "Detalhes")

        # Prévia ao vivo: mudanças visuais simples são refletidas imediatamente.
        self.template.edit.textChanged.connect(lambda: self.preview.update())
        for widget in (self.enabled, self.separator):
            widget.toggled.connect(lambda _=False: self.preview.update())
        for widget in (self.bg_type, self.gradient_direction, self.bg_fit):
            widget.currentIndexChanged.connect(lambda _=0: self.preview.update())
        for widget in (self.opacity, self.height, self.logo_width, self.pad_left, self.pad_right, self.separator_width):
            widget.valueChanged.connect(lambda _=0: self.preview.update())
        self.color1.clicked.connect(lambda _=False: self.preview.update())
        self.color2.clicked.connect(lambda _=False: self.preview.update())
        self.separator_color.clicked.connect(lambda _=False: self.preview.update())

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _preview_meta(self):
        data = dict(self.meta)
        prefix = self.section
        data[f"{prefix}_enabled"] = self.enabled.isChecked()
        data[f"{prefix}_height_mm"] = self.height.value()
        data[f"{prefix}_gap_mm"] = self.gap.value()
        data[f"{prefix}_template_html"] = self.template.toHtml()
        data[f"{prefix}_background_type"] = self.bg_type.currentData()
        data[f"{prefix}_background_color1"] = self.color1.color_name()
        data[f"{prefix}_background_color2"] = self.color2.color_name()
        data[f"{prefix}_gradient_direction"] = self.gradient_direction.currentData()
        data[f"{prefix}_background_fit"] = self.bg_fit.currentData()
        data[f"{prefix}_background_opacity"] = self.opacity.value()
        data[f"{prefix}_separator_enabled"] = self.separator.isChecked()
        data[f"{prefix}_separator_color"] = self.separator_color.color_name()
        data[f"{prefix}_separator_width_pt"] = self.separator_width.value()
        data[f"{prefix}_logo_width_mm"] = self.logo_width.value()
        data[f"{prefix}_padding_left_mm"] = self.pad_left.value()
        data[f"{prefix}_padding_right_mm"] = self.pad_right.value()
        if self._new_bg_path is not None:
            data[f"{prefix}_preview_background_path"] = self._new_bg_path
        return data

    def _asset_label(self, aid):
        if aid and aid in self.project.assets:
            return self.project.assets[aid].filename
        return "Nenhuma"

    def _select_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar imagem de fundo", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if path:
            self._new_bg_path = path
            self.bg_image_label.setText(path.split("/")[-1].split("\\")[-1])
            self.bg_type.setCurrentIndex(max(0, self.bg_type.findData("image")))
            self.preview.update()

    def _remove_bg_image(self):
        self._new_bg_path = ""
        self.bg_image_label.setText("Nenhuma")
        self.preview.update()

    def _apply_preset(self):
        name = self.preset.currentText()
        if name == "Técnico limpo":
            if self.section == "header":
                self.template.setHtml(
                    '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                    '<td><span style="font-size:9pt;font-weight:600">{{category}}</span></td>'
                    '<td align="right"><span style="font-size:8pt">{{title}} · v{{version}}</span></td>'
                    '</tr></table>'
                )
            else:
                self.template.setHtml(
                    '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                    '<td><span style="font-size:8pt">{{logo}} &nbsp; {{title}}</span></td>'
                    '<td align="right"><span style="font-size:8pt">Página {{page}} de {{pages}}</span></td>'
                    '</tr></table>'
                )
            self.bg_type.setCurrentIndex(self.bg_type.findData("none"))
            self.separator.setChecked(True)
            self.separator_color.set_color("#b9c0c8")
        elif name == "Faixa escura":
            if self.section == "header":
                self.template.setHtml(
                    '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                    '<td><span style="font-size:9pt;font-weight:600;color:#ffffff">{{logo}} &nbsp; {{category}}</span></td>'
                    '<td align="right"><span style="font-size:8pt;color:#ffffff">v{{version}}</span></td>'
                    '</tr></table>'
                )
            else:
                self.template.setHtml(
                    '<table width="100%" cellspacing="0" cellpadding="0"><tr>'
                    '<td><span style="font-size:8pt;color:#ffffff">{{topic}}</span></td>'
                    '<td align="right"><span style="font-size:8pt;color:#ffffff">{{page}} / {{pages}}</span></td>'
                    '</tr></table>'
                )
            self.bg_type.setCurrentIndex(self.bg_type.findData("gradient"))
            self.color1.set_color("#20262d")
            self.color2.set_color("#3a424c")
            self.gradient_direction.setCurrentIndex(self.gradient_direction.findData("horizontal"))
            self.separator.setChecked(False)
        elif name == "Minimalista":
            self.template.setHtml(
                '<p style="margin:0;text-align:right"><span style="font-size:8pt;color:#5f6872">'
                + ("{{title}} · v{{version}}" if self.section == "header" else "{{category}} · {{page}}")
                + '</span></p>'
            )
            self.bg_type.setCurrentIndex(self.bg_type.findData("none"))
            self.separator.setChecked(False)
        self.preview.update()

    def apply(self):
        prefix = self.section
        self.meta[f"{prefix}_enabled"] = self.enabled.isChecked()
        self.meta[f"{prefix}_height_mm"] = self.height.value()
        self.meta[f"{prefix}_gap_mm"] = self.gap.value()
        self.meta[f"{prefix}_template_html"] = self.template.toHtml()
        self.meta[f"{prefix}_background_type"] = self.bg_type.currentData()
        self.meta[f"{prefix}_background_color1"] = self.color1.color_name()
        self.meta[f"{prefix}_background_color2"] = self.color2.color_name()
        self.meta[f"{prefix}_gradient_direction"] = self.gradient_direction.currentData()
        self.meta[f"{prefix}_background_fit"] = self.bg_fit.currentData()
        self.meta[f"{prefix}_background_opacity"] = self.opacity.value()
        self.meta[f"{prefix}_separator_enabled"] = self.separator.isChecked()
        self.meta[f"{prefix}_separator_color"] = self.separator_color.color_name()
        self.meta[f"{prefix}_separator_width_pt"] = self.separator_width.value()
        self.meta[f"{prefix}_logo_width_mm"] = self.logo_width.value()
        self.meta[f"{prefix}_padding_left_mm"] = self.pad_left.value()
        self.meta[f"{prefix}_padding_right_mm"] = self.pad_right.value()
        if self._new_bg_path == "":
            self.meta[f"{prefix}_background_asset"] = ""
        elif self._new_bg_path:
            asset = self.project.add_asset_from_file(self._new_bg_path)
            self.meta[f"{prefix}_background_asset"] = asset.id


class PageSetupDialog(QDialog):
    """Configura o papel, margens, cabeçalho/rodapé e tipografia do projeto."""

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("Configuração da página")
        self.resize(650, 520)

        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # Página
        page_tab = QDialog()
        page_layout = QVBoxLayout(page_tab)
        paper_group = QGroupBox("Papel")
        paper_form = QFormLayout(paper_group)
        self.page_size = QComboBox()
        self.page_size.addItems(list(PAGE_DIMENSIONS_MM.keys()))
        self.page_size.setCurrentText(str(project.meta.get("page_size", "A4")))
        self.orientation = QComboBox()
        self.orientation.addItem("Retrato", "portrait")
        self.orientation.addItem("Paisagem", "landscape")
        idx = self.orientation.findData(project.meta.get("page_orientation", "portrait"))
        self.orientation.setCurrentIndex(max(0, idx))
        paper_form.addRow("Tamanho:", self.page_size)
        paper_form.addRow("Orientação:", self.orientation)
        page_layout.addWidget(paper_group)

        margin_group = QGroupBox("Margens do conteúdo")
        margin_grid = QGridLayout(margin_group)
        self.margin_top = _dspin(project.meta.get("margin_top_mm", 16))
        self.margin_bottom = _dspin(project.meta.get("margin_bottom_mm", 16))
        self.margin_left = _dspin(project.meta.get("margin_left_mm", 18))
        self.margin_right = _dspin(project.meta.get("margin_right_mm", 18))
        margin_grid.addWidget(QLabel("Superior"), 0, 0)
        margin_grid.addWidget(self.margin_top, 0, 1)
        margin_grid.addWidget(QLabel("Inferior"), 0, 2)
        margin_grid.addWidget(self.margin_bottom, 0, 3)
        margin_grid.addWidget(QLabel("Esquerda"), 1, 0)
        margin_grid.addWidget(self.margin_left, 1, 1)
        margin_grid.addWidget(QLabel("Direita"), 1, 2)
        margin_grid.addWidget(self.margin_right, 1, 3)
        page_layout.addWidget(margin_group)

        structure = QGroupBox("Estrutura automática")
        structure_layout = QVBoxLayout(structure)
        self.cover_enabled = QCheckBox("Gerar capa automaticamente")
        self.cover_enabled.setChecked(bool(project.meta.get("cover_enabled", True)))
        self.toc_enabled = QCheckBox("Gerar sumário automaticamente")
        self.toc_enabled.setChecked(bool(project.meta.get("toc_enabled", True)))
        structure_layout.addWidget(self.cover_enabled)
        structure_layout.addWidget(self.toc_enabled)
        page_layout.addWidget(structure)
        page_layout.addStretch(1)
        tabs.addTab(page_tab, "Página")

        # Cabeçalho / rodapé
        hf_tab = QDialog()
        hf_layout = QVBoxLayout(hf_tab)
        h_group = QGroupBox("Cabeçalho")
        h_form = QFormLayout(h_group)
        self.header_enabled = QCheckBox("Exibir título e versão no cabeçalho")
        self.header_enabled.setChecked(bool(project.meta.get("header_enabled", True)))
        self.header_height = _dspin(project.meta.get("header_height_mm", 8), 4, 30)
        self.header_gap = _dspin(project.meta.get("header_gap_mm", 3), 0, 15)
        h_form.addRow(self.header_enabled)
        h_form.addRow("Altura:", self.header_height)
        h_form.addRow("Distância do texto:", self.header_gap)
        hf_layout.addWidget(h_group)

        f_group = QGroupBox("Rodapé")
        f_form = QFormLayout(f_group)
        self.footer_enabled = QCheckBox("Exibir rodapé e número da página")
        self.footer_enabled.setChecked(bool(project.meta.get("footer_enabled", True)))
        self.footer_height = _dspin(project.meta.get("footer_height_mm", 9), 4, 30)
        self.footer_gap = _dspin(project.meta.get("footer_gap_mm", 3), 0, 15)
        self.footer_logo = QCheckBox("Mostrar o logo do manual no rodapé")
        self.footer_logo.setChecked(bool(project.meta.get("footer_logo", False)))
        self.footer_logo_width = _dspin(project.meta.get("footer_logo_width_mm", 18), 6, 50)
        f_form.addRow(self.footer_enabled)
        f_form.addRow("Altura:", self.footer_height)
        f_form.addRow("Distância do texto:", self.footer_gap)
        f_form.addRow(self.footer_logo)
        f_form.addRow("Largura do logo:", self.footer_logo_width)
        hf_layout.addWidget(f_group)
        hf_layout.addStretch(1)
        tabs.addTab(hf_tab, "Cabeçalho e rodapé")

        # Tipografia
        type_tab = QDialog()
        type_layout = QVBoxLayout(type_tab)
        type_group = QGroupBox("Tipografia padrão")
        type_form = QFormLayout(type_group)
        self.font_family = QComboBox()
        self.font_family.setEditable(True)
        self.font_family.addItems(QFontDatabase().families())
        self.font_family.setCurrentText(str(project.meta.get("body_font_family", "Arial")))
        self.body_size = _dspin(project.meta.get("body_font_size_pt", 10.5), 7, 24, 1, " pt")
        self.h1_size = _dspin(project.meta.get("heading1_size_pt", 20), 10, 42, 1, " pt")
        self.h2_size = _dspin(project.meta.get("heading2_size_pt", 16), 9, 36, 1, " pt")
        self.h3_size = _dspin(project.meta.get("heading3_size_pt", 13), 8, 30, 1, " pt")
        self.line_height = QSpinBox()
        self.line_height.setRange(90, 200)
        self.line_height.setSuffix(" %")
        self.line_height.setValue(int(project.meta.get("line_height_percent", 118)))
        self.paragraph_spacing = _dspin(project.meta.get("paragraph_spacing_pt", 5), 0, 30, 1, " pt")
        type_form.addRow("Fonte:", self.font_family)
        type_form.addRow("Texto:", self.body_size)
        type_form.addRow("Título H1:", self.h1_size)
        type_form.addRow("Título H2:", self.h2_size)
        type_form.addRow("Título H3:", self.h3_size)
        type_form.addRow("Entrelinhas:", self.line_height)
        type_form.addRow("Espaço após parágrafo:", self.paragraph_spacing)
        type_layout.addWidget(type_group)
        type_layout.addStretch(1)
        tabs.addTab(type_tab, "Tipografia")

        note = QLabel("As medidas são usadas diretamente no PDF. Imagens inseridas também podem ser dimensionadas em milímetros para manter o mesmo tamanho físico na folha.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#666; padding:4px 2px;")
        root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_validated)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _accept_validated(self):
        w, h = PAGE_DIMENSIONS_MM.get(self.page_size.currentText(), PAGE_DIMENSIONS_MM["A4"])
        if self.orientation.currentData() == "landscape":
            w, h = h, w
        usable_w = w - self.margin_left.value() - self.margin_right.value()
        reserved_h = self.margin_top.value() + self.margin_bottom.value()
        if self.header_enabled.isChecked():
            reserved_h += self.header_height.value() + self.header_gap.value()
        if self.footer_enabled.isChecked():
            reserved_h += self.footer_height.value() + self.footer_gap.value()
        usable_h = h - reserved_h
        if usable_w < 40.0:
            QMessageBox.warning(self, "Margens", "As margens esquerda e direita deixam menos de 40 mm de área útil. Reduza as margens.")
            return
        if usable_h < 60.0:
            QMessageBox.warning(self, "Margens", "Margens, cabeçalho e rodapé deixam pouca altura útil na página. Revise as medidas.")
            return
        self.accept()

    def apply(self):
        m = self.project.meta
        m["page_size"] = self.page_size.currentText()
        m["page_orientation"] = self.orientation.currentData()
        m["margin_top_mm"] = self.margin_top.value()
        m["margin_bottom_mm"] = self.margin_bottom.value()
        m["margin_left_mm"] = self.margin_left.value()
        m["margin_right_mm"] = self.margin_right.value()
        m["header_enabled"] = self.header_enabled.isChecked()
        m["footer_enabled"] = self.footer_enabled.isChecked()
        m["header_height_mm"] = self.header_height.value()
        m["footer_height_mm"] = self.footer_height.value()
        m["header_gap_mm"] = self.header_gap.value()
        m["footer_gap_mm"] = self.footer_gap.value()
        m["footer_logo"] = self.footer_logo.isChecked()
        m["footer_logo_width_mm"] = self.footer_logo_width.value()
        m["body_font_family"] = self.font_family.currentText().strip() or "Arial"
        m["body_font_size_pt"] = self.body_size.value()
        m["heading1_size_pt"] = self.h1_size.value()
        m["heading2_size_pt"] = self.h2_size.value()
        m["heading3_size_pt"] = self.h3_size.value()
        m["line_height_percent"] = self.line_height.value()
        m["paragraph_spacing_pt"] = self.paragraph_spacing.value()
        m["cover_enabled"] = self.cover_enabled.isChecked()
        m["toc_enabled"] = self.toc_enabled.isChecked()


class ImageInsertDialog(QDialog):
    def __init__(self, image: QImage, usable_width_mm: float, parent=None, title="Inserir imagem", initial_width_mm=None, initial_alignment=Qt.AlignHCenter):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(480, 280)
        self._syncing = False
        self.usable_width_mm = max(20.0, float(usable_width_mm))
        self.aspect = image.width() / float(max(1, image.height()))

        root = QVBoxLayout(self)
        info = QLabel(f"Imagem: {image.width()} × {image.height()} px   •   largura útil da página: {self.usable_width_mm:.1f} mm")
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        default_width = min(self.usable_width_mm * 0.70, 140.0) if initial_width_mm is None else float(initial_width_mm)
        self.width_mm = _dspin(max(5.0, min(self.usable_width_mm, default_width)), 5, self.usable_width_mm, 1)
        self.width_percent = QSpinBox()
        self.width_percent.setRange(5, 100)
        self.width_percent.setSuffix(" %")
        self.width_percent.setValue(round(self.width_mm.value() / self.usable_width_mm * 100))
        self.alignment = QComboBox()
        self.alignment.addItem("Esquerda", Qt.AlignLeft)
        self.alignment.addItem("Centralizada", Qt.AlignHCenter)
        self.alignment.addItem("Direita", Qt.AlignRight)
        align_idx = self.alignment.findData(initial_alignment)
        self.alignment.setCurrentIndex(align_idx if align_idx >= 0 else 1)
        form.addRow("Largura física:", self.width_mm)
        form.addRow("Largura da área útil:", self.width_percent)
        form.addRow("Posição:", self.alignment)
        root.addLayout(form)

        presets = QHBoxLayout()
        presets.addWidget(QLabel("Atalhos:"))
        for pct in (25, 50, 75, 100):
            btn = QPushButton(f"{pct}%")
            btn.clicked.connect(lambda _=False, p=pct: self._set_percent(p))
            presets.addWidget(btn)
        presets.addStretch(1)
        root.addLayout(presets)

        note = QLabel("A proporção original é preservada. O tamanho é salvo no documento e será respeitado no PDF, HTML e CHM.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#666;")
        root.addWidget(note)

        self.width_mm.valueChanged.connect(self._mm_changed)
        self.width_percent.valueChanged.connect(self._percent_changed)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _set_percent(self, pct):
        self.width_percent.setValue(pct)

    def _mm_changed(self, value):
        if self._syncing:
            return
        self._syncing = True
        self.width_percent.setValue(max(5, min(100, round(value / self.usable_width_mm * 100))))
        self._syncing = False

    def _percent_changed(self, value):
        if self._syncing:
            return
        self._syncing = True
        self.width_mm.setValue(self.usable_width_mm * value / 100.0)
        self._syncing = False

    def result_values(self):
        return self.width_mm.value(), self.alignment.currentData()


class ImageTextLayoutDialog(QDialog):
    """Configura um bloco de duas colunas: imagem de um lado e texto do outro."""

    def __init__(self, image: QImage, usable_width_mm: float, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Imagem com texto ao lado")
        self.resize(520, 300)
        self.usable_width_mm = max(40.0, float(usable_width_mm))

        root = QVBoxLayout(self)
        info = QLabel(
            f"Imagem: {image.width()} × {image.height()} px. "
            "O bloco usa duas colunas sem borda e acompanha a largura útil da página."
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        self.side = QComboBox()
        self.side.addItem("Imagem à esquerda / texto à direita", "left")
        self.side.addItem("Texto à esquerda / imagem à direita", "right")

        self.image_column = QSpinBox()
        self.image_column.setRange(25, 75)
        self.image_column.setValue(50)
        self.image_column.setSuffix(" %")

        self.image_fill = QSpinBox()
        self.image_fill.setRange(20, 100)
        self.image_fill.setValue(92)
        self.image_fill.setSuffix(" %")

        form.addRow("Distribuição:", self.side)
        form.addRow("Largura da coluna da imagem:", self.image_column)
        form.addRow("Imagem dentro da coluna:", self.image_fill)
        root.addLayout(form)

        presets = QHBoxLayout()
        presets.addWidget(QLabel("Divisão rápida:"))
        for pct in (40, 50, 60):
            btn = QPushButton(f"{pct}/{100-pct}")
            btn.clicked.connect(lambda _=False, p=pct: self.image_column.setValue(p))
            presets.addWidget(btn)
        presets.addStretch(1)
        root.addLayout(presets)

        note = QLabel(
            "Depois de inserir, o cursor ficará na coluna de texto. "
            "A imagem continua podendo ser redimensionada pela alça ou pelo menu de contexto."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#666;")
        root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def result_values(self):
        return self.side.currentData(), self.image_column.value(), self.image_fill.value()


class TableInsertDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Inserir tabela")
        self.resize(430, 310)

        root = QVBoxLayout(self)
        form = QFormLayout()
        self.rows = QSpinBox()
        self.rows.setRange(1, 100)
        self.rows.setValue(3)
        self.columns = QSpinBox()
        self.columns.setRange(1, 20)
        self.columns.setValue(3)
        self.width = QSpinBox()
        self.width.setRange(20, 100)
        self.width.setValue(100)
        self.width.setSuffix(" %")
        self.border = _dspin(0.8, 0.0, 6.0, 1, " px")
        self.padding = _dspin(5.0, 0.0, 30.0, 1, " px")
        self.header = QCheckBox("Primeira linha em negrito")
        self.header.setChecked(False)

        form.addRow("Linhas:", self.rows)
        form.addRow("Colunas:", self.columns)
        form.addRow("Largura da página:", self.width)
        form.addRow("Espessura da borda:", self.border)
        form.addRow("Espaço interno das células:", self.padding)
        form.addRow(self.header)
        root.addLayout(form)

        note = QLabel(
            "Imagens podem ser inseridas normalmente dentro de qualquer célula. "
            "Clique com o botão direito dentro da tabela para alterar tamanho, borda, espaçamento e proporção das colunas."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#666;")
        root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def result_values(self):
        return (
            self.rows.value(),
            self.columns.value(),
            self.width.value(),
            self.border.value(),
            self.padding.value(),
            self.header.isChecked(),
        )


class TablePropertiesDialog(QDialog):
    def __init__(self, table, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Propriedades da tabela")
        self.resize(520, 360)
        self._column_count = max(1, table.columns())
        fmt = table.format()

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.width = QSpinBox()
        self.width.setRange(10, 100)
        self.width.setSuffix(" %")
        width = fmt.width()
        width_pct = width.rawValue() if width.type() == QTextLength.PercentageLength and width.rawValue() > 0 else 100
        self.width.setValue(int(round(max(10, min(100, width_pct)))))

        self.border = _dspin(fmt.border(), 0.0, 8.0, 1, " px")
        self.padding = _dspin(fmt.cellPadding(), 0.0, 40.0, 1, " px")
        self.spacing = _dspin(fmt.cellSpacing(), 0.0, 30.0, 1, " px")

        constraints = fmt.columnWidthConstraints()
        values = []
        if constraints and len(constraints) == self._column_count:
            for c in constraints:
                if c.type() == QTextLength.PercentageLength and c.rawValue() > 0:
                    values.append(float(c.rawValue()))
        if len(values) != self._column_count:
            values = [100.0 / self._column_count] * self._column_count

        self.columns_edit = QLineEdit(", ".join(f"{v:.1f}" for v in values))
        self.columns_edit.setPlaceholderText("Ex.: 30, 70")
        equal_btn = QPushButton("Distribuir igualmente")
        equal_btn.clicked.connect(self._equal_columns)

        form.addRow("Largura total:", self.width)
        form.addRow("Borda:", self.border)
        form.addRow("Espaço interno:", self.padding)
        form.addRow("Espaço entre células:", self.spacing)
        form.addRow("Larguras das colunas (%):", self.columns_edit)
        form.addRow("", equal_btn)
        root.addLayout(form)

        self.validation = QLabel("")
        self.validation.setWordWrap(True)
        self.validation.setStyleSheet("color:#a33;")
        root.addWidget(self.validation)

        note = QLabel(
            f"Esta tabela possui {self._column_count} coluna(s). Informe exatamente {self._column_count} valores separados por vírgula. "
            "Eles serão normalizados para totalizar 100%."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#666;")
        root.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_validated)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._parsed_columns = values

    def _equal_columns(self):
        values = [100.0 / self._column_count] * self._column_count
        self.columns_edit.setText(", ".join(f"{v:.1f}" for v in values))

    def _parse_columns(self):
        raw = self.columns_edit.text().strip()
        # Com ponto decimal, use vírgula como separador: 33.3, 66.7.
        # Com vírgula decimal, use ponto-e-vírgula: 33,3; 66,7.
        if ";" in raw:
            parts = [p.strip().replace(",", ".") for p in raw.split(";") if p.strip()]
        else:
            parts = [p.strip() for p in raw.split(",") if p.strip()]
        if len(parts) != self._column_count:
            raise ValueError(f"Informe {self._column_count} valor(es) de largura.")
        values = []
        for part in parts:
            try:
                value = float(part)
            except ValueError:
                raise ValueError("As larguras das colunas precisam ser números.")
            if value <= 0:
                raise ValueError("Todas as larguras precisam ser maiores que zero.")
            values.append(value)
        total = sum(values)
        if total <= 0:
            raise ValueError("A soma das larguras é inválida.")
        return [v * 100.0 / total for v in values]

    def _accept_validated(self):
        try:
            self._parsed_columns = self._parse_columns()
        except ValueError as exc:
            self.validation.setText(str(exc))
            return
        self.validation.clear()
        self.accept()

    def apply_to_table(self, table):
        fmt = table.format()
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, self.width.value()))
        fmt.setBorder(self.border.value())
        fmt.setCellPadding(self.padding.value())
        fmt.setCellSpacing(self.spacing.value())
        fmt.setColumnWidthConstraints([
            QTextLength(QTextLength.PercentageLength, value) for value in self._parsed_columns
        ])
        table.setFormat(fmt)
