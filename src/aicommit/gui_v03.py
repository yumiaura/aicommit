"""Optional bilingual aicommit desktop V0.3; never pushes to GitHub.

Untrusted LLM results are display only until explicit local approval.
"""

from __future__ import annotations

import ast
import hashlib
import sys
import time

from aicommit.gui_core import GitWorkspace, WorkspaceError
from aicommit.gui_v03_core import (
    CodeProposal,
    apply_proposal,
    localized_analysis_prompt,
    localized_commit_prompt,
    parse_proposal,
    proposal_prompt,
    read_python_target,
    remote_readonly,
)

STR = {
    "title": (
        "aicommit Desktop Lab V0.3 · Local AI Code Review",
        "aicommit Desktop Lab V0.3 · Revisión de código con IA local",
    ),
    "open": ("Open local Git project", "Abrir proyecto Git local"),
    "refresh": ("Refresh changes", "Actualizar cambios"),
    "language": ("Language", "Idioma"),
    "none": (
        "No repository selected. Choose a local Git project.",
        "Sin repositorio. Elegí un proyecto Git local.",
    ),
    "files": ("LOCAL FILE CHANGES", "CAMBIOS LOCALES DE ARCHIVOS"),
    "stage": ("Stage selected file (git add)", "Preparar archivo seleccionado (git add)"),
    "intent": (
        "Your goal (optional — AI can infer from diff)",
        "Tu objetivo (opcional — la IA puede inferirlo del diff)",
    ),
    "note_placeholder": (
        "Optional: describe what you want to change. AI will check it against the actual diff.",
        "Opcional: explicá qué querés cambiar. La IA lo contrastará con el diff real.",
    ),
    "settings": ("Local AI", "IA local"),
    "model": ("Model", "Modelo"),
    "server": ("Server", "Servidor"),
    "one_click": ("✨ ANALYZE EVERYTHING — 1 CLICK", "✨ ANALIZAR TODO — 1 CLIC"),
    "explain": ("Explain", "Explicar"),
    "risks": ("Review risks", "Revisar riesgos"),
    "tests": ("Design tests", "Diseñar pruebas"),
    "improve": ("Suggest improvement", "Proponer mejora"),
    "next": ("Next step", "Próximo paso"),
    "code": ("Design code proposal", "Diseñar propuesta de código"),
    "commit_suggest": ("Suggest STAGED commit", "Sugerir commit STAGED"),
    "audit": (
        "Inspect local/GitHub status (read-only)",
        "Inspeccionar estado local/GitHub (solo lectura)",
    ),
    "cancel": ("Cancel AI request", "Cancelar consulta IA"),
    "idle": (
        "Ready. No automatic writes or pushes.",
        "Listo. Sin escritura ni publicaciones automáticas.",
    ),
    "plan_tab": ("Analysis & evidence", "Análisis y evidencias"),
    "diff_tab": ("Git diff", "Diferencias Git"),
    "chat_tab": ("File conversation", "Conversación por archivo"),
    "proposals_tab": ("Code proposals / approval", "Propuestas de código / aprobación"),
    "ask": ("Ask about the file", "Preguntar sobre el archivo"),
    "question": ("Optional follow-up question", "Pregunta de seguimiento opcional"),
    "question_tests": ("What should I test?", "¿Qué debería probar?"),
    "question_better": ("How can I improve this?", "¿Cómo puedo mejorarlo?"),
    "question_next": ("What next?", "¿Qué sigue?"),
    "proposal_intro": (
        "Generated code is NOT applied. Review the diff first.",
        "El código generado NO se aplica. Revisá primero las diferencias.",
    ),
    "apply": (
        "Apply SELECTED code proposal LOCAL ONLY",
        "Aplicar propuesta de código SELECCIONADA SOLO LOCAL",
    ),
    "discard": ("Discard selected proposal", "Descartar propuesta seleccionada"),
    "verify": ("Validate proposal syntax", "Validar sintaxis de la propuesta"),
    "no_proposals": (
        "No proposed code yet. Use Design code proposal.",
        "Sin código propuesto. Usá Diseñar propuesta de código.",
    ),
    "commit_label": (
        "COMMIT DRAFT — editable; never pushed automatically",
        "BORRADOR DE COMMIT — editable; nunca se publica automáticamente",
    ),
    "confirm_commit": (
        "I reviewed STAGED diff and approve a LOCAL commit (no push)",
        "Revisé el diff STAGED y apruebo un commit LOCAL (sin push)",
    ),
    "commit": ("Create local commit with confirmation", "Crear commit local con confirmación"),
    "project": ("PROJECT", "PROYECTO"),
    "branch": ("BRANCH", "RAMA"),
    "origin": ("Origin (reference)", "Origin (referencia)"),
    "file_count": ("file(s)", "archivo(s)"),
    "staged": ("STAGED", "PREPARADO"),
    "unstaged": ("UNSTAGED", "SIN PREPARAR"),
    "no_diff": (
        "No readable diff. Stage newly created files first. Binary files are not analyzed.",
        "Sin diff legible. Prepará primero los archivos nuevos. No se analizan archivos binarios.",
    ),
    "busy": ("Generating locally with Qwen…", "Generando localmente con Qwen…"),
    "done": (
        "AI response completed. Suggestions and tests are NOT verified.",
        "Respuesta de IA completa. Sugerencias y pruebas NO verificadas.",
    ),
    "canceled": ("Canceled. No changes were applied.", "Cancelado. No se aplicaron cambios."),
    "error": ("Error", "Error"),
    "warning": ("Warning", "Atención"),
    "no_file": ("Select a modified file first.", "Seleccioná primero un archivo modificado."),
    "confirm_stage": ("Stage file", "Preparar archivo"),
    "stage_msg": (
        "Stage this file? Review it for secrets before continuing:",
        "¿Preparar este archivo? Revisá los secretos antes de continuar:",
    ),
    "check_remote": (
        "Check public GitHub origin via read-only git ls-remote? No push or fetch will be executed.",
        "¿Consultar GitHub público mediante git ls-remote de solo lectura? No se ejecutará push ni fetch.",
    ),
    "remote_title": (
        "Repository inspection (read-only)",
        "Inspección del repositorio (solo lectura)",
    ),
    "nothing": (
        "No modifications detected; nothing to analyze.",
        "No se detectaron modificaciones para analizar.",
    ),
    "no_staged": (
        "No safe staged changes available.",
        "No hay cambios preparados seguros disponibles.",
    ),
    "syntax_pass": (
        "The proposal passed Python syntax parsing. Tests were NOT executed.",
        "La propuesta pasó la validación de sintaxis Python. NO se ejecutaron pruebas.",
    ),
    "confirm_apply_title": ("CONFIRM LOCAL CODE CHANGE", "CONFIRMAR CAMBIO LOCAL DE CÓDIGO"),
    "confirm_apply": (
        "Replace the selected local .py file with this proposed version? This does NOT stage, commit, or push. A backup will be created in Git metadata. Review the diff.",
        "¿Reemplazar el archivo .py local por esta propuesta? No prepara, confirma ni publica. Se creará un respaldo en los metadatos de Git. Revisá las diferencias.",
    ),
    "applied": ("Local code applied. Backup:", "Código aplicado localmente. Respaldo:"),
    "commit_confirm": (
        "Create LOCAL Git commit? Existing Git hooks may execute code. No push will occur.",
        "¿Crear commit Git LOCAL? Los hooks de Git existentes podrían ejecutar código. No se realizará push.",
    ),
    "created": (
        "Local commit created; no push was performed.",
        "Commit local creado; no se realizó push.",
    ),
    "changed": (
        "Staged diff changed. Regenerate the commit suggestion.",
        "Cambió el diff preparado. Volvé a generar el commit sugerido.",
    ),
    "locked": (
        "An AI operation is running. Cancel and wait before closing.",
        "Hay una consulta IA en curso. Cancelala y esperá antes de cerrar.",
    ),
    "readonly_info": (
        "This inspection never writes to your GitHub account.",
        "Esta inspección nunca escribe en tu cuenta de GitHub.",
    ),
    "proposal_item": ("Proposal", "Propuesta"),
    "no_git_diff": (
        "No diff available for this selected file.",
        "No hay diff disponible para el archivo seleccionado.",
    ),
}


def main() -> int:
    try:
        from PySide6.QtCore import Qt, QThread, QTimer, Signal
        from PySide6.QtGui import QTextCursor
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QGridLayout,
            QGroupBox,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QMessageBox,
            QPlainTextEdit,
            QPushButton,
            QSplitter,
            QTabWidget,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is required. Install it in the existing aicommit .venv.", file=sys.stderr)
        return 2
    from aicommit.llm.ollama import OllamaBackend

    class AiThread(QThread):
        partial = Signal(str)
        success = Signal(str)
        failure = Signal(str)
        canceled = Signal()

        def __init__(self, prompt: str, model: str, url: str, code_job: bool = False):
            super().__init__()
            self.prompt, self.model, self.url, self.code_job = prompt, model, url, code_job

        def run(self):
            try:
                llm = OllamaBackend(
                    url=self.url,
                    model=self.model,
                    timeout=55,
                    max_tokens=3800 if self.code_job else 1250,
                    temperature=0.1,
                )
                parts = []
                for token in llm.stream(self.prompt):
                    if self.isInterruptionRequested():
                        self.canceled.emit()
                        return
                    parts.append(token)
                    self.partial.emit(token)
                if self.isInterruptionRequested():
                    self.canceled.emit()
                elif not "".join(parts).strip():
                    self.failure.emit("Ollama returned no text.")
                else:
                    self.success.emit("".join(parts))
            except Exception as exc:
                if self.isInterruptionRequested():
                    self.canceled.emit()
                else:
                    self.failure.emit(str(exc))

    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.lang = "en"  # Default English, regardless of OS locale.
            self.ws: GitWorkspace | None = None
            self.rows = []
            self.messages: dict[str, list[str]] = {}
            self.proposals: list[CodeProposal] = []
            self.worker: AiThread | None = None
            self.working = ""
            self.operation = ""
            self.active_path = ""
            self.active_question = ""
            self.pending_before = ""
            self.pending_hash = ""
            self.commit_hash = ""
            self.elapsed_start = 0.0
            self.cancel_requested = False
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.tick)
            self.build()
            self.translate()
            self.update_controls()

        def t(self, key):
            val = STR.get(key)
            return val[0 if self.lang == "en" else 1] if val else key

        def show_error(self, err):
            QMessageBox.warning(self, self.t("error"), str(err))

        def show_info(self, title, msg):
            QMessageBox.information(self, title, msg)

        def build(self):
            self.resize(1320, 865)
            self.setStyleSheet("""QWidget{font-size:12px;}QMainWindow{background:#f4f5f7;}
                QPushButton{padding:6px 9px;min-height:25px;}
                QPushButton#primary{background:#f56b13;color:white;border-radius:6px;font-weight:bold;padding:11px;}
                QPushButton#primary:disabled{background:#a7a7a7;}
                QPlainTextEdit{font-family:Consolas,'Courier New',monospace;}
                QTabWidget::pane{background:white;border:1px solid #ccc;}""")
            main = QWidget()
            self.setCentralWidget(main)
            layout = QVBoxLayout(main)
            bar = QHBoxLayout()
            layout.addLayout(bar)
            self.open_btn = QPushButton()
            self.open_btn.clicked.connect(self.open_repo)
            self.location = QLineEdit()
            self.location.setReadOnly(True)
            self.refresh_btn = QPushButton()
            self.refresh_btn.clicked.connect(self.refresh)
            self.language_label = QLabel()
            self.language = QComboBox()
            self.language.addItem("English", "en")
            self.language.addItem("Español", "es")
            self.language.currentIndexChanged.connect(self.change_language)
            for widget in (
                self.open_btn,
                self.location,
                self.refresh_btn,
                self.language_label,
                self.language,
            ):
                bar.addWidget(widget, 1 if widget is self.location else 0)
            self.repo_info = QLabel()
            self.repo_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(self.repo_info)
            split = QSplitter(Qt.Horizontal)
            layout.addWidget(split, 1)
            lside = QWidget()
            left = QVBoxLayout(lside)
            split.addWidget(lside)
            self.files_label = QLabel()
            left.addWidget(self.files_label)
            self.filelist = QListWidget()
            self.filelist.currentRowChanged.connect(self.select_file)
            left.addWidget(self.filelist, 1)
            self.stage_btn = QPushButton()
            self.stage_btn.clicked.connect(self.stage_one)
            left.addWidget(self.stage_btn)
            self.intent_label = QLabel()
            left.addWidget(self.intent_label)
            self.notes = QPlainTextEdit()
            self.notes.setMaximumHeight(88)
            left.addWidget(self.notes)
            self.settings = QGroupBox()
            settings_form = QFormLayout(self.settings)
            self.model = QLineEdit("qwen2.5-coder:3b")
            self.url = QLineEdit("http://127.0.0.1:11434")
            self.model_label = QLabel()
            self.server_label = QLabel()
            settings_form.addRow(self.model_label, self.model)
            settings_form.addRow(self.server_label, self.url)
            left.addWidget(self.settings)
            rightwidget = QWidget()
            right = QVBoxLayout(rightwidget)
            split.addWidget(rightwidget)
            self.oneclick = QPushButton()
            self.oneclick.setObjectName("primary")
            right.addWidget(self.oneclick)
            self.oneclick.clicked.connect(lambda: self.request_analysis("plan"))
            grid = QGridLayout()
            right.addLayout(grid)
            self.quick = {}
            for i, key in enumerate(("explain", "risks", "tests", "improve", "next", "code")):
                btn = QPushButton()
                self.quick[key] = btn
                btn.clicked.connect(
                    lambda checked=False, k=key: (
                        self.make_code_proposal() if k == "code" else self.request_analysis(k)
                    )
                )
                grid.addWidget(btn, i // 3, i % 3)
            self.commit_suggest = QPushButton()
            self.commit_suggest.clicked.connect(self.request_commit)
            grid.addWidget(self.commit_suggest, 2, 0, 1, 3)
            self.audit_btn = QPushButton()
            self.audit_btn.clicked.connect(self.inspect_origin)
            right.addWidget(self.audit_btn)
            progress_row = QHBoxLayout()
            right.addLayout(progress_row)
            self.progress = QLabel()
            progress_row.addWidget(self.progress, 1)
            self.cancel_btn = QPushButton()
            self.cancel_btn.clicked.connect(self.cancel_work)
            progress_row.addWidget(self.cancel_btn)
            self.tabs = QTabWidget()
            right.addWidget(self.tabs, 1)
            self.analysis = QPlainTextEdit()
            self.analysis.setReadOnly(True)
            self.tabs.addTab(self.analysis, "")
            self.diff = QPlainTextEdit()
            self.diff.setReadOnly(True)
            self.tabs.addTab(self.diff, "")
            conversation = QWidget()
            conv_layout = QVBoxLayout(conversation)
            self.chat = QPlainTextEdit()
            self.chat.setReadOnly(True)
            conv_layout.addWidget(self.chat, 1)
            fastrow = QHBoxLayout()
            conv_layout.addLayout(fastrow)
            self.fast = {}
            for key in ("question_tests", "question_better", "question_next"):
                b = QPushButton()
                b.clicked.connect(lambda checked=False, k=key: self.ask_file(self.t(k)))
                self.fast[key] = b
                fastrow.addWidget(b)
            self.question = QLineEdit()
            self.question.returnPressed.connect(self.ask_file)
            conv_layout.addWidget(self.question)
            self.askbtn = QPushButton()
            self.askbtn.clicked.connect(self.ask_file)
            conv_layout.addWidget(self.askbtn)
            self.tabs.addTab(conversation, "")
            proposals_widget = QWidget()
            proposal_layout = QVBoxLayout(proposals_widget)
            self.proposal_intro = QLabel()
            proposal_layout.addWidget(self.proposal_intro)
            self.proposal_list = QListWidget()
            self.proposal_list.setMaximumHeight(95)
            self.proposal_list.currentRowChanged.connect(self.display_proposal)
            proposal_layout.addWidget(self.proposal_list)
            self.proposal_preview = QPlainTextEdit()
            self.proposal_preview.setReadOnly(True)
            proposal_layout.addWidget(self.proposal_preview, 1)
            proposal_row = QHBoxLayout()
            proposal_layout.addLayout(proposal_row)
            self.syntax_btn = QPushButton()
            self.syntax_btn.clicked.connect(self.validate_proposal)
            self.apply_btn = QPushButton()
            self.apply_btn.clicked.connect(self.approve_proposal)
            self.discard_btn = QPushButton()
            self.discard_btn.clicked.connect(self.discard_proposal)
            for btn in (self.syntax_btn, self.apply_btn, self.discard_btn):
                proposal_row.addWidget(btn)
            self.tabs.addTab(proposals_widget, "")
            self.commit_label = QLabel()
            right.addWidget(self.commit_label)
            self.commit_text = QPlainTextEdit()
            self.commit_text.setMaximumHeight(84)
            self.commit_text.textChanged.connect(self.update_controls)
            right.addWidget(self.commit_text)
            self.confirm = QCheckBox()
            self.confirm.stateChanged.connect(self.update_controls)
            right.addWidget(self.confirm)
            self.commit_btn = QPushButton()
            self.commit_btn.clicked.connect(self.commit)
            right.addWidget(self.commit_btn)
            split.setSizes([360, 930])
            self.statusBar().showMessage("Read-only by default — proposals require approval")

        def translate(self):
            self.setWindowTitle(self.t("title"))
            names = {
                "open_btn": "open",
                "refresh_btn": "refresh",
                "language_label": "language",
                "files_label": "files",
                "stage_btn": "stage",
                "intent_label": "intent",
                "commit_label": "commit_label",
                "commit_btn": "commit",
                "settings": "settings",
                "model_label": "model",
                "server_label": "server",
                "oneclick": "one_click",
                "commit_suggest": "commit_suggest",
                "audit_btn": "audit",
                "cancel_btn": "cancel",
                "progress": "idle",
                "askbtn": "ask",
                "proposal_intro": "proposal_intro",
                "syntax_btn": "verify",
                "apply_btn": "apply",
                "discard_btn": "discard",
                "confirm": "confirm_commit",
            }
            for attr, key in names.items():
                obj = getattr(self, attr)
                if isinstance(obj, QGroupBox):
                    obj.setTitle(self.t(key))
                else:
                    obj.setText(self.t(key))
            for key, btn in self.quick.items():
                btn.setText(self.t(key))
            for key, btn in self.fast.items():
                btn.setText(self.t(key))
            for i, key in enumerate(("plan_tab", "diff_tab", "chat_tab", "proposals_tab")):
                self.tabs.setTabText(i, self.t(key))
            self.notes.setPlaceholderText(self.t("note_placeholder"))
            self.question.setPlaceholderText(self.t("question"))
            self.location.setPlaceholderText(self.t("none"))
            if self.ws:
                self.update_repo_info()
            else:
                self.repo_info.setText(self.t("none"))
            if not self.proposals:
                self.proposal_preview.setPlainText(self.t("no_proposals"))

        def change_language(self, i):
            self.lang = self.language.itemData(i) or "en"
            self.translate()
            self.refresh_file_labels()

        def selected(self):
            i = self.filelist.currentRow()
            return self.rows[i].path if 0 <= i < len(self.rows) else ""

        def update_repo_info(self):
            if not self.ws:
                return
            self.repo_info.setText(
                f"{self.t('project')}: {self.ws.root.name}  |  {self.t('branch')}: {self.ws.branch()}\n"
                f"{self.t('origin')}: {self.ws.remote()}  |  {len(self.rows)} {self.t('file_count')}"
            )

        def refresh_file_labels(self):
            current = self.selected()
            self.filelist.blockSignals(True)
            self.filelist.clear()
            for f in self.rows:
                status = ("● " + self.t("staged") if f.staged else "") + (
                    "  ○ " + self.t("unstaged") if f.unstaged else ""
                )
                self.filelist.addItem(f"[{f.status}] {f.path}  {status}")
            self.filelist.blockSignals(False)
            if current in [x.path for x in self.rows]:
                self.filelist.setCurrentRow([x.path for x in self.rows].index(current))
            elif self.rows:
                self.filelist.setCurrentRow(0)
            self.update_repo_info()
            self.update_controls()

        def open_repo(self):
            folder = QFileDialog.getExistingDirectory(self, self.t("open"))
            if not folder:
                return
            try:
                self.ws = GitWorkspace(folder)
                self.location.setText(str(self.ws.root))
                self.messages.clear()
                self.proposals.clear()
                self.proposal_list.clear()
                self.notes.clear()
                self.refresh()
            except WorkspaceError as e:
                self.show_error(e)

        def refresh(self):
            if not self.ws:
                return
            try:
                self.rows = self.ws.files()
                self.analysis.clear()
                self.diff.clear()
                self.commit_text.clear()
                self.confirm.setChecked(False)
                self.commit_hash = ""
                self.refresh_file_labels()
                if self.rows:
                    self.select_file(self.filelist.currentRow())
                else:
                    self.chat.clear()
            except WorkspaceError as e:
                self.show_error(e)

        def select_file(self, index):
            if not self.ws or index < 0 or index >= len(self.rows):
                return
            try:
                a, b = self.ws.file_diff(self.selected())
                self.diff.setPlainText(
                    (
                        f"=== {self.t('staged')} ===\n{a or '(none)'}\n\n"
                        f"=== {self.t('unstaged')} ===\n{b or '(none)'}"
                    )
                    if a or b
                    else self.t("no_diff")
                )
                self.chat.setPlainText("\n\n".join(self.messages.get(self.selected(), [])[-6:]))
            except WorkspaceError as e:
                self.show_error(e)
            self.update_controls()

        def stage_one(self):
            if not self.ws or not self.selected():
                return
            path = self.selected()
            if (
                QMessageBox.question(
                    self,
                    self.t("confirm_stage"),
                    self.t("stage_msg") + "\n" + path,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                != QMessageBox.Yes
            ):
                return
            try:
                self.ws.stage_one(path)
                self.refresh()
            except WorkspaceError as e:
                self.show_error(e)

        def get_diff(self):
            if not self.ws or not self.selected():
                raise WorkspaceError(self.t("no_file"))
            a, b = self.ws.file_diff(self.selected())
            if not (a or b):
                raise WorkspaceError(self.t("no_git_diff"))
            return a or b

        def start_ai(self, job: str, prompt: str, *, code_job=False):
            if self.worker and self.worker.isRunning():
                return
            from aicommit.gui_core import assert_local_ollama

            try:
                url = assert_local_ollama(self.url.text())
            except WorkspaceError as e:
                self.show_error(e)
                return
            model = self.model.text().strip()
            if not model or len(model) > 120:
                self.show_error("Invalid model name.")
                return
            self.operation = job
            self.working = ""
            self.cancel_requested = False
            self.elapsed_start = time.monotonic()
            self.worker = AiThread(prompt, model, url, code_job)
            self.worker.partial.connect(self.partial)
            self.worker.success.connect(self.done)
            self.worker.failure.connect(self.failure)
            self.worker.canceled.connect(self.canceled)
            self.worker.finished.connect(self.finished)
            if job == "chat":
                self.tabs.setCurrentIndex(2)
                self.chat.appendPlainText("\nQUESTION: " + self.active_question + "\nANSWER:\n")
            elif job == "commit":
                self.commit_text.clear()
            else:
                self.tabs.setCurrentIndex(3 if job == "code" else 0)
                if job == "code":
                    self.proposal_preview.setPlainText(self.t("busy"))
                else:
                    self.analysis.setPlainText(self.t("busy") + "\n\n")
            self.timer.start(1000)
            self.worker.start()
            self.update_controls()

        def tick(self):
            if not self.worker:
                return
            self.progress.setText(
                f"{self.t('busy')} {int(time.monotonic() - self.elapsed_start)}s · {len(self.working)} chars"
            )

        def partial(self, text):
            if self.cancel_requested:
                return
            self.working += text
            if self.operation == "commit":
                self.commit_text.setPlainText(self.working[:5000])
                return
            target = (
                self.chat
                if self.operation == "chat"
                else self.proposal_preview
                if self.operation == "code"
                else self.analysis
            )
            cursor = target.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(text)
            target.setTextCursor(cursor)

        def done(self, result):
            if self.cancel_requested:
                return
            if self.operation == "code":
                try:
                    proposal = parse_proposal(
                        result, self.active_path, self.pending_before, self.pending_hash
                    )
                    self.proposals.append(proposal)
                    self.proposal_list.addItem(
                        f"{self.t('proposal_item')} {len(self.proposals)} · {proposal.path}"
                    )
                    self.proposal_list.setCurrentRow(len(self.proposals) - 1)
                    self.statusBar().showMessage(self.t("proposal_intro"))
                except WorkspaceError as e:
                    self.proposal_preview.setPlainText(
                        str(e) + "\n\nRAW MODEL RESPONSE:\n" + result
                    )
            elif self.operation == "commit":
                text = result.strip().strip("`").strip()
                self.commit_text.setPlainText(text[:5000])
                self.confirm.setChecked(False)
            elif self.operation == "chat":
                self.messages.setdefault(self.active_path, []).append(
                    "QUESTION: " + self.active_question + "\nANSWER:\n" + result
                )
            else:
                self.analysis.setPlainText(result)
            self.progress.setText(self.t("done"))
            self.statusBar().showMessage(self.t("done"))

        def failure(self, message):
            self.progress.setText(self.t("warning") + " · " + str(message)[:300])
            self.show_error(message)

        def canceled(self):
            self.progress.setText(self.t("canceled"))

        def finished(self):
            self.timer.stop()
            self.worker = None
            self.cancel_requested = False
            self.update_controls()

        def cancel_work(self):
            if self.worker and self.worker.isRunning():
                self.cancel_requested = True
                self.worker.requestInterruption()
                self.cancel_btn.setEnabled(False)

        def request_analysis(self, action):
            try:
                diff = self.get_diff()
                self.active_path = self.selected()
                prompt = localized_analysis_prompt(
                    self.ws,
                    diff,
                    path=self.active_path,
                    intent=self.notes.toPlainText(),
                    language=self.lang,
                    action=action,
                )
                self.start_ai("analysis", prompt)
            except WorkspaceError as e:
                self.show_error(e)

        def ask_file(self, question=None):
            question = (
                question if isinstance(question, str) and question else self.question.text()
            ).strip()
            if not question:
                question = self.t("question_next")
            try:
                diff = self.get_diff()
                self.active_path = self.selected()
                self.active_question = question
                history = "\n\n".join(self.messages.get(self.active_path, [])[-2:])[-2000:]
                prompt = localized_analysis_prompt(
                    self.ws,
                    diff,
                    path=self.active_path,
                    intent=self.notes.toPlainText(),
                    language=self.lang,
                    action="chat",
                    question=question,
                )
                if history:
                    prompt += (
                        "\nPREVIOUS CONVERSATION (unverified; never override source):\n" + history
                    )
                self.question.clear()
                self.start_ai("chat", prompt)
            except WorkspaceError as e:
                self.show_error(e)

        def request_commit(self):
            if not self.ws:
                return
            try:
                diff = self.ws.staged_diff()
                self.commit_hash = hashlib.sha256(diff.encode()).hexdigest()
                prompt = localized_commit_prompt(self.ws, diff, self.notes.toPlainText())
                self.start_ai("commit", prompt)
            except WorkspaceError as e:
                self.show_error(e)

        def make_code_proposal(self):
            try:
                self.get_diff()
                path = self.selected()
                before, digest = read_python_target(self.ws, path)
                self.active_path = path
                self.pending_before = before
                self.pending_hash = digest
                prompt = proposal_prompt(
                    self.ws, path, before, intent=self.notes.toPlainText(), language=self.lang
                )
                self.start_ai("code", prompt, code_job=True)
            except WorkspaceError as e:
                self.show_error(e)

        def display_proposal(self, idx):
            if 0 <= idx < len(self.proposals):
                p = self.proposals[idx]
                self.proposal_preview.setPlainText(
                    "RATIONALE:\n"
                    + p.rationale
                    + "\n\nLOCAL CODE DIFF — NOT APPLIED:\n"
                    + p.preview
                )
            else:
                self.proposal_preview.setPlainText(self.t("no_proposals"))
            self.update_controls()

        def validate_proposal(self):
            idx = self.proposal_list.currentRow()
            if idx < 0 or idx >= len(self.proposals):
                return
            try:
                ast.parse(self.proposals[idx].after)
            except SyntaxError as e:
                self.show_error(str(e))
                return
            self.show_info("Python syntax", self.t("syntax_pass"))

        def discard_proposal(self):
            idx = self.proposal_list.currentRow()
            if 0 <= idx < len(self.proposals):
                del self.proposals[idx]
                self.proposal_list.takeItem(idx)
                self.display_proposal(self.proposal_list.currentRow())

        def approve_proposal(self):
            idx = self.proposal_list.currentRow()
            if not self.ws or idx < 0 or idx >= len(self.proposals):
                return
            p = self.proposals[idx]
            self.tabs.setCurrentIndex(3)
            if (
                QMessageBox.warning(
                    self,
                    self.t("confirm_apply_title"),
                    self.t("confirm_apply") + "\n\n" + p.path + "\n\n" + p.preview[:1800],
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                != QMessageBox.Yes
            ):
                return
            try:
                backup = apply_proposal(self.ws, p, approved=True)
                self.show_info("Local proposal applied", self.t("applied") + "\n" + str(backup))
                self.proposals.pop(idx)
                self.proposal_list.takeItem(idx)
                self.refresh()
                self.display_proposal(self.proposal_list.currentRow())
            except (WorkspaceError, OSError) as e:
                self.show_error(e)

        def inspect_origin(self):
            if not self.ws:
                return
            answer = QMessageBox.question(
                self,
                self.t("remote_title"),
                self.t("check_remote"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            try:
                data = remote_readonly(self.ws, online=answer == QMessageBox.Yes)
                result = (
                    "\n".join(f"{k}: {v}" for k, v in data.items())
                    + "\n\n"
                    + self.t("readonly_info")
                )
                self.tabs.setCurrentIndex(0)
                self.analysis.setPlainText(result)
            except WorkspaceError as e:
                self.show_error(e)

        def commit(self):
            if not self.ws or not self.confirm.isChecked():
                return
            try:
                message = self.commit_text.toPlainText().strip()
                if not message:
                    raise WorkspaceError("Commit message is empty.")
                actual = hashlib.sha256(self.ws.staged_diff().encode()).hexdigest()
                if not self.commit_hash or actual != self.commit_hash:
                    self.confirm.setChecked(False)
                    raise WorkspaceError(self.t("changed"))
                if (
                    QMessageBox.warning(
                        self,
                        self.t("commit"),
                        self.t("commit_confirm") + "\n\n" + message[:300],
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No,
                    )
                    != QMessageBox.Yes
                ):
                    return
                result = self.ws.commit(message)
                self.show_info("LOCAL COMMIT", self.t("created") + "\n" + result)
                self.refresh()
            except WorkspaceError as e:
                self.show_error(e)

        def update_controls(self):
            busy = self.worker is not None and self.worker.isRunning()
            selected = bool(self.ws and self.selected())
            for item in [
                self.open_btn,
                self.refresh_btn,
                self.filelist,
                self.stage_btn,
                self.notes,
                self.model,
                self.url,
                self.oneclick,
                self.commit_suggest,
                self.audit_btn,
                self.askbtn,
                self.question,
                *self.quick.values(),
                *self.fast.values(),
                self.language,
                self.apply_btn,
                self.discard_btn,
                self.syntax_btn,
            ]:
                ready = not busy
                if item in [
                    self.oneclick,
                    self.askbtn,
                    self.question,
                    *self.quick.values(),
                    *self.fast.values(),
                    self.stage_btn,
                ]:
                    ready = ready and selected
                if item in [self.apply_btn, self.discard_btn, self.syntax_btn]:
                    ready = ready and 0 <= self.proposal_list.currentRow() < len(self.proposals)
                item.setEnabled(ready)
            self.cancel_btn.setEnabled(busy and not self.cancel_requested)
            self.commit_btn.setEnabled(
                bool(self.ws)
                and not busy
                and self.confirm.isChecked()
                and bool(self.commit_hash)
                and bool(self.commit_text.toPlainText().strip())
            )

        def closeEvent(self, event):
            if self.worker and self.worker.isRunning():
                self.show_error(self.t("locked"))
                event.ignore()
            else:
                event.accept()

    app = QApplication(sys.argv)
    app.setApplicationName("aicommit Desktop Lab")
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
