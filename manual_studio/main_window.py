import os
from pathlib import Path

from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QAbstractItemView,
    QComboBox,
    QMenu,
)

from .dialogs import ProjectPropertiesDialog, PageSetupDialog, HeaderFooterDesignerDialog
from .editor import RichTextEditor, create_format_toolbar
from .exporters import export_chm, export_html, export_pdf, find_hhc
from .model import ManualProject
from .help_system import open_help_file, choose_and_open_help, export_project_help
from .fragment_system import (
    FRAGMENT_EXTENSION, FragmentExportDialog, FragmentImportDialog,
    build_fragment, save_fragment, load_fragment, import_fragment_into_project,
)
from .ui_extras import (
    MarginRuler, NewProjectDialog, TopicPageOptionsDialog, LanguageManagerDialog,
    PdfLanguageExportDialog, PdfSettingsDialog, HtmlStyleDialog, PAGE_DIMS, LANG_NAMES,
)


ROLE_TOPIC_ID = Qt.UserRole + 1


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Manual Studio Qt5")
        self.resize(1280, 780)
        self.settings = QSettings()
        self.project = ManualProject.new()
        self.current_language = str(self.project.meta.get("language", "pt-BR"))
        self.project_path = ""
        self.current_topic_id = ""
        self.dirty = False
        self._loading_editor = False

        self._build_ui()
        self._build_menus()
        self.rebuild_tree()
        self.statusBar().showMessage("Pronto")

    def _build_ui(self):
        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)
        head = QHBoxLayout()
        head.addWidget(QLabel("Tópicos"))
        add_btn = QPushButton("+")
        add_btn.setFixedWidth(34)
        add_btn.setToolTip("Adicionar tópico")
        add_btn.clicked.connect(self.add_topic)
        child_btn = QPushButton("+ Sub")
        child_btn.setToolTip("Adicionar subtópico")
        child_btn.clicked.connect(self.add_subtopic)
        del_btn = QPushButton("−")
        del_btn.setFixedWidth(34)
        del_btn.setToolTip("Excluir tópico")
        del_btn.clicked.connect(self.delete_topic)
        head.addStretch(1)
        head.addWidget(add_btn)
        head.addWidget(child_btn)
        head.addWidget(del_btn)
        left_layout.addLayout(head)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tree.setDragDropMode(QAbstractItemView.InternalMove)
        self.tree.setDefaultDropAction(Qt.MoveAction)
        self.tree.setEditTriggers(QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)
        self.tree.currentItemChanged.connect(self.on_tree_selection_changed)
        self.tree.itemChanged.connect(self.on_item_changed)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_topic_context_menu)
        left_layout.addWidget(self.tree, 1)
        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 6, 8, 8)
        pagebar = QHBoxLayout()
        pagebar.addWidget(QLabel("Idioma:"))
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(145)
        self.language_combo.currentIndexChanged.connect(self.change_editor_language)
        pagebar.addWidget(self.language_combo)
        self.topic_page_status = QLabel("Página: padrão do documento")
        self.topic_page_status.setStyleSheet("color:#666;")
        pagebar.addWidget(self.topic_page_status, 1)
        topic_page_btn = QPushButton("Opções desta página...")
        topic_page_btn.clicked.connect(self.edit_current_topic_page_options)
        pagebar.addWidget(topic_page_btn)
        edit_header_btn = QPushButton("Editar cabeçalho")
        edit_header_btn.clicked.connect(lambda: self.edit_header_footer_direct("header"))
        pagebar.addWidget(edit_header_btn)
        edit_footer_btn = QPushButton("Editar rodapé")
        edit_footer_btn.clicked.connect(lambda: self.edit_header_footer_direct("footer"))
        pagebar.addWidget(edit_footer_btn)
        right_layout.addLayout(pagebar)

        self.ruler = MarginRuler(lambda: self.project, self, editor_getter=lambda: getattr(self, "editor", None))
        self.ruler.marginsChanging.connect(self.on_ruler_margins_changing)
        self.ruler.marginsCommitted.connect(self.on_ruler_margins_committed)
        right_layout.addWidget(self.ruler)

        self.editor = RichTextEditor(lambda: self.project)
        self.editor.textChanged.connect(self.on_editor_changed)
        right_layout.addWidget(self.editor, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([300, 980])

        self.addToolBar(create_format_toolbar(self, self.editor))
        self.refresh_language_combo()

    def _build_menus(self):
        file_menu = self.menuBar().addMenu("Arquivo")
        new_act = QAction("Novo", self)
        new_act.setShortcut("Ctrl+N")
        new_act.triggered.connect(self.new_project)
        file_menu.addAction(new_act)
        open_act = QAction("Abrir...", self)
        open_act.setShortcut("Ctrl+O")
        open_act.triggered.connect(self.open_project)
        file_menu.addAction(open_act)
        save_act = QAction("Salvar", self)
        save_act.setShortcut("Ctrl+S")
        save_act.triggered.connect(self.save_project)
        file_menu.addAction(save_act)
        save_as_act = QAction("Salvar como...", self)
        save_as_act.setShortcut("Ctrl+Shift+S")
        save_as_act.triggered.connect(self.save_project_as)
        file_menu.addAction(save_as_act)
        file_menu.addSeparator()
        export_fragment = QAction("Exportar tópico como fragmento...", self)
        export_fragment.setShortcut("Ctrl+Shift+E")
        export_fragment.triggered.connect(self.do_export_fragment)
        file_menu.addAction(export_fragment)
        import_fragment = QAction("Importar fragmento...", self)
        import_fragment.setShortcut("Ctrl+Shift+M")
        import_fragment.triggered.connect(self.do_import_fragment)
        file_menu.addAction(import_fragment)
        file_menu.addSeparator()

        exp_html = QAction("Exportar HTML...", self)
        exp_html.triggered.connect(self.do_export_html)
        file_menu.addAction(exp_html)
        pdf_settings_file = QAction("Configuração do PDF...", self)
        pdf_settings_file.triggered.connect(self.edit_pdf_settings)
        file_menu.addAction(pdf_settings_file)
        exp_pdf = QAction("Exportar PDF...", self)
        exp_pdf.triggered.connect(self.do_export_pdf)
        file_menu.addAction(exp_pdf)
        exp_chm = QAction("Exportar CHM...", self)
        exp_chm.triggered.connect(self.do_export_chm)
        file_menu.addAction(exp_chm)
        exp_ajuda = QAction("Exportar ajuda binária (.ajuda)...", self)
        exp_ajuda.triggered.connect(self.do_export_ajuda)
        file_menu.addAction(exp_ajuda)
        file_menu.addSeparator()
        exit_act = QAction("Sair", self)
        exit_act.triggered.connect(self.close)
        file_menu.addAction(exit_act)

        edit_menu = self.menuBar().addMenu("Editar")
        undo = QAction("Desfazer", self)
        undo.setShortcut("Ctrl+Z")
        undo.triggered.connect(self.editor.undo)
        edit_menu.addAction(undo)
        redo = QAction("Refazer", self)
        redo.setShortcut("Ctrl+Y")
        redo.triggered.connect(self.editor.redo)
        edit_menu.addAction(redo)
        edit_menu.addSeparator()
        add_topic = QAction("Novo tópico", self)
        add_topic.setShortcut("Ctrl+T")
        add_topic.triggered.connect(self.add_topic)
        edit_menu.addAction(add_topic)
        rename = QAction("Renomear tópico", self)
        rename.setShortcut("F2")
        rename.triggered.connect(self.rename_topic)
        edit_menu.addAction(rename)

        insert_menu = self.menuBar().addMenu("Inserir")
        insert_image = QAction("Imagem...", self)
        insert_image.setShortcut("Ctrl+Shift+I")
        insert_image.triggered.connect(self.editor.insert_image_from_file)
        insert_menu.addAction(insert_image)
        image_text = QAction("Imagem com texto ao lado...", self)
        image_text.triggered.connect(self.editor.insert_image_text_layout)
        insert_menu.addAction(image_text)
        adjust_image = QAction("Ajustar imagem selecionada...", self)
        adjust_image.triggered.connect(self.editor.edit_current_image)
        insert_menu.addAction(adjust_image)
        replace_image = QAction("Substituir imagem selecionada...", self)
        replace_image.triggered.connect(self.editor.replace_selected_image)
        insert_menu.addAction(replace_image)
        insert_menu.addSeparator()
        insert_table = QAction("Tabela...", self)
        insert_table.triggered.connect(self.editor.insert_table)
        insert_menu.addAction(insert_table)
        table_props = QAction("Propriedades da tabela atual...", self)
        table_props.triggered.connect(self.editor.edit_current_table)
        insert_menu.addAction(table_props)
        insert_link = QAction("Link...", self)
        insert_link.triggered.connect(self.editor.insert_link)
        insert_menu.addAction(insert_link)
        image_link = QAction("Link na imagem selecionada...", self)
        image_link.triggered.connect(self.editor.set_selected_image_link)
        insert_menu.addAction(image_link)
        code_block = QAction("Bloco de código...", self)
        code_block.triggered.connect(self.editor.insert_code_block)
        insert_menu.addAction(code_block)
        insert_menu.addSeparator()
        insert_rule = QAction("Linha horizontal", self)
        insert_rule.triggered.connect(self.editor.insert_horizontal_rule)
        insert_menu.addAction(insert_rule)
        insert_break = QAction("Quebra de página", self)
        insert_break.setShortcut("Ctrl+Enter")
        insert_break.triggered.connect(self.editor.insert_page_break)
        insert_menu.addAction(insert_break)
        insert_menu.addSeparator()
        special = insert_menu.addMenu("Tópico especial")
        special.addAction("Histórico de revisões", self.add_special_revisions_topic)

        format_menu = self.menuBar().addMenu("Formatar")
        font_act = QAction("Fonte...", self)
        font_act.triggered.connect(self.editor.choose_font_for_selection)
        format_menu.addAction(font_act)
        text_color = QAction("Cor do texto...", self)
        text_color.triggered.connect(self.editor.choose_text_color)
        format_menu.addAction(text_color)
        highlight = QAction("Realce...", self)
        highlight.triggered.connect(self.editor.choose_highlight_color)
        format_menu.addAction(highlight)
        format_menu.addSeparator()
        align_menu = format_menu.addMenu("Alinhamento")
        align_menu.addAction("Esquerda", lambda: self.editor.setAlignment(Qt.AlignLeft))
        align_menu.addAction("Centralizado", lambda: self.editor.setAlignment(Qt.AlignHCenter))
        align_menu.addAction("Direita", lambda: self.editor.setAlignment(Qt.AlignRight))
        align_menu.addAction("Justificado", lambda: self.editor.setAlignment(Qt.AlignJustify))
        list_menu = format_menu.addMenu("Listas")
        list_menu.addAction("Marcadores", self.editor.toggle_bullets)
        list_menu.addAction("Numeração", self.editor.toggle_numbering)

        table_menu = self.menuBar().addMenu("Tabela")
        table_menu.addAction("Propriedades / tamanho...", self.editor.edit_current_table)
        table_menu.addSeparator()
        table_menu.addAction("Inserir linha acima", lambda: self.editor.insert_table_row(False))
        table_menu.addAction("Inserir linha abaixo", lambda: self.editor.insert_table_row(True))
        table_menu.addAction("Inserir coluna à esquerda", lambda: self.editor.insert_table_column(False))
        table_menu.addAction("Inserir coluna à direita", lambda: self.editor.insert_table_column(True))
        table_menu.addSeparator()
        table_menu.addAction("Remover linha", self.editor.remove_table_row)
        table_menu.addAction("Remover coluna", self.editor.remove_table_column)

        project_menu = self.menuBar().addMenu("Manual")
        props = QAction("Propriedades...", self)
        props.triggered.connect(self.edit_properties)
        project_menu.addAction(props)
        page_setup = QAction("Configuração da página...", self)
        page_setup.triggered.connect(self.edit_page_setup)
        project_menu.addAction(page_setup)
        project_menu.addAction("Opções desta página/tópico...", self.edit_current_topic_page_options)
        project_menu.addSeparator()
        project_menu.addAction("Editar cabeçalho...", lambda: self.edit_header_footer_direct("header"))
        project_menu.addAction("Editar rodapé...", lambda: self.edit_header_footer_direct("footer"))
        project_menu.addSeparator()
        project_menu.addAction("Idiomas...", self.manage_languages)
        project_menu.addAction("Estilo HTML / CSS...", self.edit_html_style)
        project_menu.addAction("Configuração do PDF...", self.edit_pdf_settings)

        tools = self.menuBar().addMenu("Ferramentas")
        chm_compiler = QAction("Configurar compilador CHM...", self)
        chm_compiler.triggered.connect(self.configure_hhc)
        tools.addAction(chm_compiler)
        tools.addSeparator()
        tools.addAction("Remover fundo da imagem selecionada...", self.editor.remove_selected_image_background)

        help_menu = self.menuBar().addMenu("Ajuda")
        help_file = QAction("Ajuda do Manual Studio", self)
        help_file.setShortcut("F1")
        help_file.triggered.connect(lambda: open_help_file(self))
        help_menu.addAction(help_file)
        help_menu.addAction("Abrir arquivo .ajuda...", lambda: choose_and_open_help(self))
        help_menu.addSeparator()
        about = QAction("Sobre", self)
        about.triggered.connect(self.show_about)
        help_menu.addAction(about)

    def set_dirty(self, value=True):
        self.dirty = bool(value)
        name = Path(self.project_path).name if self.project_path else "Sem título.qmanual"
        self.setWindowTitle(f"{'*' if self.dirty else ''}{name} — Manual Studio Qt5")

    def sync_current_topic(self):
        if not self.current_topic_id:
            return
        topic = self.project.topic_by_id(self.current_topic_id)
        if topic:
            self.project.set_topic_translation(topic, self.current_language, html=self.editor.toHtml())

    def sync_tree_model(self):
        self.sync_current_topic()
        order_counter = {}

        def walk(parent_item, parent_id=None):
            count = parent_item.childCount() if parent_item else self.tree.topLevelItemCount()
            for i in range(count):
                item = parent_item.child(i) if parent_item else self.tree.topLevelItem(i)
                tid = item.data(0, ROLE_TOPIC_ID)
                topic = self.project.topic_by_id(tid)
                if topic:
                    self.project.set_topic_translation(topic, self.current_language, title=item.text(0).strip() or "Tópico")
                    topic.parent_id = parent_id
                    topic.order = i
                    walk(item, tid)
        walk(None, None)

    def rebuild_tree(self, select_id=None):
        self.tree.blockSignals(True)
        self.tree.clear()
        item_map = {}
        pending = list(self.project.topics)
        safety = 0
        while pending and safety < len(self.project.topics) + 5:
            safety += 1
            rest = []
            for topic in sorted(pending, key=lambda t: (t.order, self.project.topic_title(t, self.current_language).lower())):
                if topic.parent_id and topic.parent_id not in item_map:
                    rest.append(topic)
                    continue
                label = self.project.topic_title(topic, self.current_language)
                item = QTreeWidgetItem([label])
                if topic.kind == "toc":
                    item.setToolTip(0, "Tópico especial: sumário automático")
                elif topic.kind == "revisions":
                    item.setToolTip(0, "Tópico especial: histórico de revisões")
                item.setFlags(item.flags() | Qt.ItemIsEditable | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled)
                item.setData(0, ROLE_TOPIC_ID, topic.id)
                if topic.parent_id:
                    item_map[topic.parent_id].addChild(item)
                else:
                    self.tree.addTopLevelItem(item)
                item_map[topic.id] = item
            if len(rest) == len(pending):
                for topic in rest:
                    topic.parent_id = None
                pending = rest
            else:
                pending = rest
        self.tree.expandAll()
        self.tree.blockSignals(False)

        target = select_id or (self.project.topics[0].id if self.project.topics else "")
        if target in item_map:
            self.tree.setCurrentItem(item_map[target])

    def on_tree_selection_changed(self, current, previous):
        if previous is not None and self.current_topic_id:
            self.sync_current_topic()
        if not current:
            self.current_topic_id = ""
            self._loading_editor = True
            self.editor.clear()
            self._loading_editor = False
            self.refresh_topic_page_status()
            return
        tid = current.data(0, ROLE_TOPIC_ID)
        topic = self.project.topic_by_id(tid)
        if topic:
            self.current_topic_id = tid
            self._loading_editor = True
            self.editor.set_topic_html(self.project.topic_html(topic, self.current_language))
            self._loading_editor = False
            self.refresh_topic_page_status()

    def on_editor_changed(self):
        if not self._loading_editor:
            self.set_dirty(True)

    def on_item_changed(self, item, column):
        tid = item.data(0, ROLE_TOPIC_ID)
        topic = self.project.topic_by_id(tid)
        if topic:
            self.project.set_topic_translation(topic, self.current_language, title=item.text(0).strip() or "Tópico")
            self.set_dirty(True)

    def selected_topic_id(self):
        item = self.tree.currentItem()
        return item.data(0, ROLE_TOPIC_ID) if item else None

    def add_topic(self):
        title, ok = QInputDialog.getText(self, "Novo tópico", "Título:", text="Novo tópico")
        if not ok:
            return
        self.sync_tree_model()
        topic = self.project.add_topic(title.strip() or "Novo tópico", None)
        self.set_dirty(True)
        self.rebuild_tree(topic.id)

    def add_subtopic(self):
        parent = self.selected_topic_id()
        if not parent:
            self.add_topic()
            return
        title, ok = QInputDialog.getText(self, "Novo subtópico", "Título:", text="Novo subtópico")
        if not ok:
            return
        self.sync_tree_model()
        topic = self.project.add_topic(title.strip() or "Novo subtópico", parent)
        self.set_dirty(True)
        self.rebuild_tree(topic.id)

    def rename_topic(self):
        item = self.tree.currentItem()
        if item:
            self.tree.editItem(item, 0)

    def delete_topic(self):
        tid = self.selected_topic_id()
        if not tid:
            return
        topic = self.project.topic_by_id(tid)
        answer = QMessageBox.question(
            self,
            "Excluir tópico",
            f"Excluir '{self.project.topic_title(topic, self.current_language)}' e todos os subtópicos?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.project.delete_topic_recursive(tid)
        if not self.project.topics:
            self.project = ManualProject.new()
            self.current_language = str(self.project.meta.get("language", "pt-BR"))
            self.refresh_language_combo()
        self.current_topic_id = ""
        self.set_dirty(True)
        self.rebuild_tree()

    def show_topic_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is not None:
            self.tree.setCurrentItem(item)
        menu = QMenu(self)
        if item is not None:
            menu.addAction("Novo subtópico", self.add_subtopic)
            menu.addAction("Renomear", self.rename_topic)
            menu.addSeparator()
            menu.addAction("Exportar como fragmento...", self.do_export_fragment)
            menu.addSeparator()
            menu.addAction("Excluir tópico...", self.delete_topic)
        else:
            menu.addAction("Novo tópico", self.add_topic)
            menu.addAction("Importar fragmento...", self.do_import_fragment)
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def do_export_fragment(self):
        topic_id = self.selected_topic_id()
        if not topic_id:
            QMessageBox.information(self, "Fragmento", "Selecione o tópico que será a raiz do fragmento.")
            return
        self.sync_tree_model()
        topic = self.project.topic_by_id(topic_id)
        if not topic:
            return
        dlg = FragmentExportDialog(self.project, topic_id, self.current_language, self)
        if not dlg.exec_():
            return
        options = dlg.values()
        title = self.project.topic_title(topic, self.current_language).strip() or "fragmento"
        safe = slug_filename(title) or "fragmento"
        default = safe + FRAGMENT_EXTENSION
        path, _ = QFileDialog.getSaveFileName(
            self, "Salvar fragmento", default,
            "Fragmento do Manual Studio (*.mfrag);;Fragmento (*.fragmento);;Todos os arquivos (*.*)"
        )
        if not path:
            return
        try:
            fragment = build_fragment(
                self.project, topic_id, options["topic_ids"], options["languages"],
                include_rich_text=options["include_rich_text"],
                include_assets=options["include_assets"],
                include_topic_options=options["include_topic_options"],
                style_groups=options["style_groups"],
            )
            result = save_fragment(fragment, path)
            QMessageBox.information(
                self, "Fragmento",
                f"Fragmento criado com sucesso.\n\n{result}\n\n"
                f"Tópicos: {len(fragment.get('topics') or [])}\n"
                f"Idiomas: {', '.join(fragment.get('languages') or [])}\n"
                f"Recursos incorporados: {len(fragment.get('assets') or {})}"
            )
        except Exception as exc:
            QMessageBox.critical(self, "Fragmento", f"Falha ao criar o fragmento.\n\n{exc}")

    def do_import_fragment(self):
        self.sync_tree_model()
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar fragmento", "",
            "Fragmento do Manual Studio (*.mfrag *.fragmento);;Todos os arquivos (*.*)"
        )
        if not path:
            return
        try:
            fragment = load_fragment(path)
        except Exception as exc:
            QMessageBox.critical(self, "Fragmento", f"Não foi possível abrir o fragmento.\n\n{exc}")
            return
        dlg = FragmentImportDialog(
            self.project, fragment, self.selected_topic_id(), self.current_language, self
        )
        if not dlg.exec_():
            return
        values = dlg.values()
        try:
            imported_ids, asset_map = import_fragment_into_project(self.project, fragment, **values)
            self.refresh_language_combo()
            self.editor.register_project_assets()
            self.set_dirty(True)
            self.rebuild_tree(imported_ids[0] if imported_ids else None)
            applied = values.get("apply_style_groups") or []
            if applied:
                self.editor.refresh_project_layout()
                self.ruler.update()
            QMessageBox.information(
                self, "Fragmento",
                f"Fragmento importado com sucesso.\n\n"
                f"Tópicos adicionados: {len(imported_ids)}\n"
                f"Recursos adicionados: {len(asset_map)}" +
                (f"\nEstilos globais aplicados: {len(applied)}" if applied else "")
            )
        except Exception as exc:
            QMessageBox.critical(self, "Fragmento", f"Falha ao importar o fragmento.\n\n{exc}")

    def maybe_save(self):
        if not self.dirty:
            return True
        answer = QMessageBox.question(
            self,
            "Alterações não salvas",
            "Deseja salvar as alterações antes de continuar?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Cancel:
            return False
        if answer == QMessageBox.Yes:
            return self.save_project()
        return True

    def new_project(self):
        if not self.maybe_save():
            return
        dlg = NewProjectDialog(self)
        if not dlg.exec_():
            return
        self.project = ManualProject.new(dlg.template())
        self.current_language = str(self.project.meta.get("language", "pt-BR"))
        self.project_path = ""
        self.current_topic_id = ""
        self.editor.refresh_project_layout()
        self.refresh_language_combo()
        self.ruler.update()
        self.set_dirty(False)
        self.rebuild_tree()

    def open_project(self):
        if not self.maybe_save():
            return
        path, _ = QFileDialog.getOpenFileName(self, "Abrir manual", "", "Manual Studio (*.qmanual);;JSON (*.json);;Todos (*.*)")
        if not path:
            return
        try:
            self.project = ManualProject.load(path)
            self.current_language = str(self.project.meta.get("language", "pt-BR"))
            self.project_path = path
            self.current_topic_id = ""
            self.editor.refresh_project_layout()
            self.refresh_language_combo()
            self.ruler.update()
            self.set_dirty(False)
            self.rebuild_tree()
            self.statusBar().showMessage(f"Aberto: {path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Abrir", f"Não foi possível abrir o projeto.\n\n{e}")

    def save_project(self):
        if not self.project_path:
            return self.save_project_as()
        try:
            self.sync_tree_model()
            self.project.save(self.project_path)
            self.set_dirty(False)
            self.statusBar().showMessage(f"Salvo: {self.project_path}", 4000)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Salvar", f"Não foi possível salvar.\n\n{e}")
            return False

    def save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar manual", self.project_path or "manual.qmanual", "Manual Studio (*.qmanual)")
        if not path:
            return False
        if not Path(path).suffix:
            path += ".qmanual"
        self.project_path = path
        return self.save_project()

    def edit_properties(self):
        self.sync_current_topic()
        dlg = ProjectPropertiesDialog(self.project, self)
        if dlg.exec_():
            dlg.apply()
            self.editor.register_project_assets()
            self.editor.refresh_project_layout()
            if self.current_language not in self.project.languages():
                self.current_language = str(self.project.meta.get("language", "pt-BR"))
            self.refresh_language_combo()
            self.ruler.update()
            self.set_dirty(True)

    def edit_page_setup(self):
        dlg = PageSetupDialog(self.project, self)
        if dlg.exec_():
            dlg.apply()
            self.editor.refresh_project_layout()
            self.ruler.update()
            # Reaplica o HTML atual para a prévia usar a nova tipografia/largura,
            # sem alterar o conteúdo do tópico.
            if self.current_topic_id:
                topic = self.project.topic_by_id(self.current_topic_id)
                if topic:
                    self.sync_current_topic()
                    self._loading_editor = True
                    self.editor.set_topic_html(self.project.topic_html(topic, self.current_language))
                    self._loading_editor = False
            self.set_dirty(True)
            self.statusBar().showMessage(
                f"Página: {self.project.meta.get('page_size', 'A4')} • margens configuradas", 5000
            )

    def refresh_language_combo(self):
        if not hasattr(self, "language_combo"):
            return
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        default_lang = str(self.project.meta.get("language", "pt-BR"))
        for lang in self.project.languages():
            suffix = "  [padrão]" if lang == default_lang else ""
            self.language_combo.addItem(f"{LANG_NAMES.get(lang, lang)} — {lang}{suffix}", lang)
        idx = self.language_combo.findData(self.current_language)
        if idx < 0:
            self.current_language = str(self.project.meta.get("language", "pt-BR"))
            idx = self.language_combo.findData(self.current_language)
        self.language_combo.setCurrentIndex(max(0, idx))
        self.language_combo.blockSignals(False)

    def change_editor_language(self):
        lang = str(self.language_combo.currentData() or "") if hasattr(self, "language_combo") else ""
        if not lang or lang == self.current_language:
            return
        self.sync_current_topic()
        target = self.selected_topic_id()
        self.current_language = lang
        self.rebuild_tree(target)
        self.statusBar().showMessage(f"Editando idioma: {lang}", 3000)

    def manage_languages(self):
        self.sync_current_topic()
        old_default = str(self.project.meta.get("language", "pt-BR"))
        dlg = LanguageManagerDialog(self.project, self)
        if dlg.exec_():
            dlg.apply()
            new_default = str(self.project.meta.get("language", "pt-BR"))
            if new_default != old_default:
                # O idioma padrão é a fonte editorial; ao trocá-lo, já passa a
                # ser o idioma ativo para deixar claro o que está sendo editado.
                self.current_language = new_default
            elif self.current_language not in self.project.languages():
                self.current_language = new_default
            self.refresh_language_combo()
            self.rebuild_tree(self.current_topic_id)
            self.set_dirty(True)

    def edit_html_style(self):
        # Garante que a prévia WebHelp use o conteúdo que está atualmente no editor.
        self.sync_current_topic()
        dlg = HtmlStyleDialog(
            self.project, self,
            current_topic_id=self.current_topic_id,
            current_language=self.current_language,
        )
        if dlg.exec_():
            dlg.apply()
            self.set_dirty(True)

    def edit_pdf_settings(self):
        dlg = PdfSettingsDialog(self.project, self)
        if dlg.exec_():
            dlg.apply()
            self.set_dirty(True)
            self.statusBar().showMessage("Configuração específica do PDF atualizada.", 4000)

    def add_special_toc_topic(self):
        existing = next((t for t in self.project.topics if t.kind == "toc"), None)
        if existing:
            self.rebuild_tree(existing.id)
            QMessageBox.information(self, "Sumário", "Este manual já possui um tópico de sumário automático.")
            return
        self.sync_tree_model()
        topic = self.project.add_topic("Sumário", None, kind="toc")
        self.set_dirty(True)
        self.rebuild_tree(topic.id)

    def add_special_revisions_topic(self):
        self.sync_tree_model()
        topic = self.project.add_topic("Revisões", None, kind="revisions")
        self.set_dirty(True)
        self.rebuild_tree(topic.id)

    def edit_current_topic_page_options(self):
        tid = self.selected_topic_id()
        topic = self.project.topic_by_id(tid) if tid else None
        if not topic:
            QMessageBox.information(self, "Página", "Selecione um tópico primeiro.")
            return
        dlg = TopicPageOptionsDialog(topic, self)
        if dlg.exec_():
            dlg.apply()
            self.refresh_topic_page_status()
            self.set_dirty(True)

    def refresh_topic_page_status(self):
        if not hasattr(self, "topic_page_status"):
            return
        topic = self.project.topic_by_id(self.current_topic_id) if self.current_topic_id else None
        if not topic:
            self.topic_page_status.setText("Página: —")
            return
        def state(value):
            return "padrão" if value is None else ("sim" if value else "não")
        kind = "" if topic.kind == "normal" else f" • especial: {topic.kind}"
        self.topic_page_status.setText(f"Cabeçalho: {state(topic.show_header)} • Rodapé: {state(topic.show_footer)}{kind}")

    def edit_header_footer_direct(self, section):
        dlg = HeaderFooterDesignerDialog(self.project, section, self.project.meta, self)
        if dlg.exec_():
            dlg.apply()
            self.editor.register_project_assets()
            self.set_dirty(True)

    def on_ruler_margins_changing(self, left, right, dragging):
        m = self.project.meta
        page_w, page_h = PAGE_DIMS.get(str(m.get("page_size", "A4")), PAGE_DIMS["A4"])
        if m.get("page_orientation", "portrait") == "landscape":
            page_w, page_h = page_h, page_w
        # Aplica durante o arraste: o texto muda de largura junto com o marcador.
        self.editor.refresh_project_layout()
        self.editor.set_margin_guides(left / page_w, (page_w - right) / page_w, visible=dragging)
        self.statusBar().showMessage(f"Margens: esquerda {left:.1f} mm • direita {right:.1f} mm", 1500)

    def on_ruler_margins_committed(self, left, right):
        self.editor.set_margin_guides(visible=False)
        self.editor.refresh_project_layout()
        self.set_dirty(True)

    def do_export_html(self):
        self.sync_tree_model()
        folder = QFileDialog.getExistingDirectory(self, "Pasta para exportar HTML")
        if not folder:
            return
        try:
            index = export_html(self.project, folder)
            QMessageBox.information(self, "HTML", f"HTML exportado com sucesso.\n\n{index}")
        except Exception as e:
            QMessageBox.critical(self, "HTML", str(e))

    def do_export_pdf(self):
        self.sync_tree_model()
        mode, language = "single", self.current_language
        langs = self.project.languages()
        if len(langs) > 1:
            dlg = PdfLanguageExportDialog(self.project, self)
            if not dlg.exec_():
                return
            mode, language = dlg.values()
        default = slug_filename(self.project.meta.get("title", "manual")) + ".pdf"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar PDF", default, "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            if mode == "combined":
                export_pdf(self.project, path, combined_languages=langs)
                message = path
            elif mode == "separate":
                base = Path(path)
                made = []
                for lang in langs:
                    target = base.with_name(base.stem + "_" + lang.replace("-", "_") + base.suffix)
                    export_pdf(self.project, str(target), language=lang)
                    made.append(str(target))
                message = "\n".join(made)
            else:
                export_pdf(self.project, path, language=language or self.current_language)
                message = path
            QMessageBox.information(self, "PDF", f"PDF gerado com sucesso.\n\n{message}")
        except Exception as e:
            QMessageBox.critical(self, "PDF", f"Falha ao gerar PDF.\n\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def do_export_ajuda(self):
        self.sync_tree_model()
        default = slug_filename(self.project.meta.get("title", "manual")) + ".ajuda"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar ajuda binária", default, "Manual Studio Help (*.ajuda)"
        )
        if not path:
            return
        try:
            result = export_project_help(self.project, path)
            QMessageBox.information(
                self, "Ajuda binária",
                "Arquivo .ajuda gerado com sucesso.\n\n" + result +
                "\n\nO arquivo contém a estrutura do manual, idiomas e recursos de imagem em um único contêiner compactado."
            )
        except Exception as e:
            QMessageBox.critical(self, "Ajuda binária", f"Falha ao gerar .ajuda.\n\n{e}")

    def configure_hhc(self):
        current = self.settings.value("hhc_path", "", type=str)
        start = current if current else ""
        path, _ = QFileDialog.getOpenFileName(self, "Selecionar hhc.exe", start, "HTML Help Compiler (hhc.exe);;Executáveis (*.exe);;Todos (*.*)")
        if path:
            self.settings.setValue("hhc_path", path)
            QMessageBox.information(self, "CHM", "Compilador CHM configurado.")

    def do_export_chm(self):
        self.sync_tree_model()
        default = slug_filename(self.project.meta.get("title", "manual")) + ".chm"
        path, _ = QFileDialog.getSaveFileName(self, "Exportar CHM", default, "Compiled HTML Help (*.chm)")
        if not path:
            return
        if not path.lower().endswith(".chm"):
            path += ".chm"
        configured = self.settings.value("hhc_path", "", type=str)
        if not find_hhc(configured):
            answer = QMessageBox.question(
                self,
                "Compilador CHM",
                "O hhc.exe do Microsoft HTML Help Workshop não foi encontrado. Deseja selecionar o executável agora?\n\nSe escolher Não, o Manual Studio ainda gerará o projeto .hhp/.hhc para compilação posterior.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            if answer == QMessageBox.Yes:
                self.configure_hhc()
                configured = self.settings.value("hhc_path", "", type=str)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            ok, message, result = export_chm(self.project, path, configured)
            if ok:
                QMessageBox.information(self, "CHM", f"{message}\n\n{result}")
            else:
                QMessageBox.warning(self, "CHM", f"{message}\n\nProjeto: {result}")
        except Exception as e:
            QMessageBox.critical(self, "CHM", f"Falha ao exportar CHM.\n\n{e}")
        finally:
            QApplication.restoreOverrideCursor()

    def show_about(self):
        QMessageBox.about(
            self,
            "Manual Studio Qt5",
            "Manual Studio Qt5 — v7\n\nEditor de manuais técnicos em Python + PyQt5.\n"
            "Exporta HTML, PDF e projetos CHM e possui ajuda própria em formato .ajuda.\n\n"
            "O CHM é compilado pelo Microsoft HTML Help Workshop (hhc.exe) quando disponível.",
        )

    def closeEvent(self, event):
        self.sync_current_topic()
        if self.maybe_save():
            event.accept()
        else:
            event.ignore()


def slug_filename(text):
    import re
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip()).strip("_")
    return value or "manual"
