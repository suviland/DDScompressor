import sys
import os
import subprocess
import threading
from pathlib import Path
import winreg
from datetime import datetime
import urllib.parse
import tempfile
import shutil
import zipfile
import json
import re
import locale

# 可选：7z 支持
try:
    import py7zr
    HAS_7Z = True
except ImportError:
    HAS_7Z = False

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QProgressBar, QMessageBox, QFileDialog, 
    QCheckBox, QTextEdit, QDialog, QInputDialog
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QSettings, QTimer, QTranslator, QLocale
from PyQt5.QtGui import QFont, QIcon

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).resolve().parent
    return Path(base_path) / relative_path

# ========== 辅助函数 ==========
def get_unique_filename(base_name, extension=".zip"):
    base_path = Path(base_name).with_suffix("")
    candidate = base_path.with_suffix(extension)
    counter = 0
    while candidate.exists():
        counter += 1
        candidate = base_path.with_name(f"{base_path.name}_{counter}").with_suffix(extension)
    return candidate

def find_imagemagick_from_registry():
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\ImageMagick\Current") as key:
            path, _ = winreg.QueryValueEx(key, "BinPath")
            magick_path = os.path.join(path, "magick.exe")
            if os.path.isfile(magick_path):
                return magick_path
    except Exception:
        pass
    return None

def is_normal_map(filepath: Path) -> bool:
    stem = filepath.stem.lower()
    return stem.endswith('_n') or stem.endswith('_msn')

def extract_archive(archive_path: Path, temp_dir: Path):
    """解压 .zip 或 .7z 到 temp_dir，返回解压后的根目录列表"""
    extracted_roots = []
    archive_name = archive_path.stem
    extract_to = temp_dir / archive_name
    extract_to.mkdir(parents=True, exist_ok=True)

    try:
        if archive_path.suffix.lower() == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(extract_to)
        elif archive_path.suffix.lower() == '.7z':
            if not HAS_7Z:
                raise RuntimeError("py7zr not installed. Run: pip install py7zr")
            with py7zr.SevenZipFile(archive_path, mode='r') as z:
                z.extractall(path=extract_to)
        else:
            return extracted_roots  # 不支持

        # 获取顶级文件夹（可能有多个）
        for item in extract_to.iterdir():
            if item.is_dir():
                extracted_roots.append(item)
            else:
                # 如果没有顶层文件夹（平铺文件），则以 extract_to 为根
                extracted_roots.append(extract_to)
                break

        if not extracted_roots:
            extracted_roots.append(extract_to)
    except Exception as e:
        raise RuntimeError(f"Failed to extract {archive_path}: {e}")

    return list(set(extracted_roots))  # 去重

# ========== 多语言字典 ==========
LANGUAGES = {
    "zh": {
        "title": "上古卷轴DDS压缩工具",
        "language_label": "语言 Language",
        "material_folder": "材质文件夹或压缩包（每行一个路径）:",
        "image_magick": "ImageMagick (magick.exe):",
        "resolution": "分辨率:",
        "process_mode": "处理模式:",
        "mode_all": "全部处理",
        "mode_skip_normals": "跳过法线贴图 (*_n, *_msn)",
        "mode_only_normals": "仅处理法线贴图",
        "output_method": "输出方式:",
        "method_folder": "输出到文件夹",
        "method_zip": "输出为 ZIP 压缩包",
        "start_button": "开始压缩",
        "cancel_button": "取消压缩",
        "browse": "浏览...",
        "res_0.5k": "0.5K (512)",
        "res_1k": "1K (1024)",
        "res_2k": "2K (2048)",
        "res_4k": "4K (4096)",
        "error_input": "请输入有效的材质文件夹或压缩包路径！",
        "error_magick": "请选择有效的 magick.exe！",
        "no_dds": "未找到 .dds 文件！",
        "processing": "处理中... {current}/{total}",
        "success": "完成！\n成功处理: {success}/{total}\n输出路径:\n{output_dir}",
        "auto_not_found": "注册表未找到 ImageMagick，请手动选择路径。",
        "export_log": "导出日志",
        "view_log": "查看日志",
        "log_exported": "日志已导出至: {path}",
        "file_processed": "{filename} → {output_path}",
        "processing_time": "处理时间: {duration}s",
        "canceling": "取消中...",
        "cancelled": "已取消。",
        "magick_not_found_tip": "无法通过注册表找到 magick.exe，请手动选择。",
        "drag_hint": "↑ 可直接拖放文件夹、ZIP 或 7Z 到窗口",
        "select_zip_path": "选择 ZIP 保存文件夹",
        "zip_file": "ZIP 文件 (*.zip)",
        "compressing_to_zip": "正在写入 ZIP... {current}/{total}",
        "unsupported_archive": "不支持的压缩包格式: {ext}",
        "info": "信息",
        "no_log": "无日志内容可显示。",
        "log_export_success": "日志已导出至: {path}",
        "log_export_error": "导出日志失败: {error}",
        "success_title": "成功",
        "error_title": "错误",
        "cancel_confirm": "确定要取消当前操作吗？",
        "custom_translation": "自定义翻译(custom)",
        "select_custom_translation": "选择自定义翻译文件 (translate.json)",
        "custom_translation_loaded": "自定义翻译已加载: {filename}",
        "custom_translation_error": "加载自定义翻译失败: {error}",
        "custom_translation_invalid": "无效的翻译文件: 缺少必要字段 '{missing_key}'",
        "custom_translation_corrupted": "翻译文件损坏或格式不正确",
        "custom_translation_path_saved": "自定义翻译路径已保存",
        "custom_translation_not_found": "自定义翻译文件不存在: {path}",
        "custom_translation_reset": "自定义翻译已重置"
    },
    "en": {
        "title": "Skyrim DDS Compressor",
        "language_label": "Language",
        "material_folder": "Texture Folders or Archives (one per line):",
        "image_magick": "ImageMagick (magick.exe):",
        "resolution": "Resolution:",
        "process_mode": "Processing Mode:",
        "mode_all": "Process All",
        "mode_skip_normals": "Skip Normal Maps (*_n, *_msn)",
        "mode_only_normals": "Process Normals Only",
        "output_method": "Output Method:",
        "method_folder": "Output to Folder",
        "method_zip": "Output as ZIP Archive",
        "start_button": "Start Compression",
        "cancel_button": "Cancel Compression",
        "browse": "Browse...",
        "res_0.5k": "0.5K (512)",
        "res_1k": "1K (1024)",
        "res_2k": "2K (2048)",
        "res_4k": "4K (4096)",
        "error_input": "Please enter valid texture folders or archives!",
        "error_magick": "Please select a valid magick.exe!",
        "no_dds": "No .dds files found!",
        "processing": "Processing... {current}/{total}",
        "success": "Completed!\nSuccessfully processed: {success}/{total}\nOutput paths:\n{output_dir}",
        "auto_not_found": "ImageMagick not found in registry. Please select manually.",
        "export_log": "Export Log",
        "view_log": "View Log",
        "log_exported": "Log exported to: {path}",
        "file_processed": "{filename} → {output_path}",
        "processing_time": "Processing time: {duration}s",
        "canceling": "Canceling...",
        "cancelled": "Cancelled.",
        "magick_not_found_tip": "Could not find magick.exe via registry. Please select manually.",
        "drag_hint": "↑ Drag & drop folders, ZIP or 7Z directly onto the window",
        "select_zip_path": "Select ZIP Output Folder",
        "zip_file": "ZIP Files (*.zip)",
        "compressing_to_zip": "Writing to ZIP... {current}/{total}",
        "unsupported_archive": "Unsupported archive format: {ext}",
        "info": "Info",
        "no_log": "No log content to display.",
        "log_export_success": "Log exported to: {path}",
        "log_export_error": "Failed to export log: {error}",
        "success_title": "Success",
        "error_title": "Error",
        "cancel_confirm": "Are you sure you want to cancel the current operation?",
        "custom_translation": "Custom Translation",
        "select_custom_translation": "Select Custom Translation File (translate.json)",
        "custom_translation_loaded": "Custom translation loaded: {filename}",
        "custom_translation_error": "Failed to load custom translation: {error}",
        "custom_translation_invalid": "Invalid translation file: Missing required field '{missing_key}'",
        "custom_translation_corrupted": "Translation file corrupted or invalid format",
        "custom_translation_path_saved": "Custom translation path saved",
        "custom_translation_not_found": "Custom translation file not found: {path}",
        "custom_translation_reset": "Custom translation reset"
    },
    "ru": {
        "title": "Компрессор текстур Skyrim DDS",
        "language_label": "Язык",
        "material_folder": "Папки с текстурами или архивы (по одной на строку):",
        "image_magick": "ImageMagick (magick.exe):",
        "resolution": "Разрешение:",
        "process_mode": "Режим обработки:",
        "mode_all": "Обработать всё",
        "mode_skip_normals": "Пропустить карты нормалей (*_n, *_msn)",
        "mode_only_normals": "Только карты нормалей",
        "output_method": "Способ вывода:",
        "method_folder": "Вывод в папку",
        "method_zip": "Вывод в ZIP-архив",
        "start_button": "Начать сжатие",
        "cancel_button": "Отменить сжатие",
        "browse": "Обзор...",
        "res_0.5k": "0.5K (512)",
        "res_1k": "1K (1024)",
        "res_2k": "2K (2048)",
        "res_4k": "4K (4096)",
        "error_input": "Введите корректные пути к папкам или архивам!",
        "error_magick": "Выберите magick.exe!",
        "no_dds": "Файлы .dds не найдены!",
        "processing": "Обработка... {current}/{total}",
        "success": "Готово!\nУспешно: {success}/{total}\nПути вывода:\n{output_dir}",
        "auto_not_found": "ImageMagick не найден в реестре. Выберите вручную.",
        "export_log": "Экспорт журнала",
        "view_log": "Просмотр журнала",
        "log_exported": "Журнал экспортирован в: {path}",
        "file_processed": "{filename} → {output_path}",
        "processing_time": "Время обработки: {duration}s",
        "canceling": "Отмена...",
        "cancelled": "Отменено.",
        "magick_not_found_tip": "Не удалось найти magick.exe через реестр. Пожалуйста, выберите вручную.",
        "drag_hint": "↑ Перетащите папки, ZIP или 7Z прямо в окно",
        "select_zip_path": "Выберите папку для сохранения ZIP",
        "zip_file": "ZIP-файлы (*.zip)",
        "compressing_to_zip": "Запись в ZIP... {current}/{total}",
        "unsupported_archive": "Неподдерживаемый формат архива: {ext}",
        "info": "Информация",
        "no_log": "Нет содержимого журнала для отображения.",
        "log_export_success": "Журнал экспортирован в: {path}",
        "log_export_error": "Не удалось экспортировать журнал: {error}",
        "success_title": "Готово",
        "error_title": "Ошибка",
        "cancel_confirm": "Вы уверены, что хотите отменить текущую операцию?",
        "custom_translation": "Пользовательский перевод",
        "select_custom_translation": "Выберите файл пользовательского перевода (translate.json)",
        "custom_translation_loaded": "Пользовательский перевод загружен: {filename}",
        "custom_translation_error": "Ошибка загрузки пользовательского перевода: {error}",
        "custom_translation_invalid": "Неверный файл перевода: Отсутствует обязательное поле '{missing_key}'",
        "custom_translation_corrupted": "Файл перевода поврежден или имеет неверный формат",
        "custom_translation_path_saved": "Путь к пользовательскому переводу сохранен",
        "custom_translation_not_found": "Файл пользовательского перевода не найден: {path}",
        "custom_translation_reset": "Пользовательский перевод сброшен"
    },
    "fr": {
        "title": "Compresseur DDS Skyrim",
        "language_label": "Langue",
        "material_folder": "Dossiers de textures ou archives (un par ligne):",
        "image_magick": "ImageMagick (magick.exe):",
        "resolution": "Résolution:",
        "process_mode": "Mode de traitement:",
        "mode_all": "Tout traiter",
        "mode_skip_normals": "Ignorer les normales (*_n, *_msn)",
        "mode_only_normals": "Normales uniquement",
        "output_method": "Méthode de sortie:",
        "method_folder": "Exporter vers un dossier",
        "method_zip": "Exporter en archive ZIP",
        "start_button": "Commencer la compression",
        "cancel_button": "Annuler la compression",
        "browse": "Parcourir...",
        "res_0.5k": "0.5K (512)",
        "res_1k": "1K (1024)",
        "res_2k": "2K (2048)",
        "res_4k": "4K (4096)",
        "error_input": "Entrez des chemins valides !",
        "error_magick": "Sélectionnez magick.exe !",
        "no_dds": "Aucun fichier .dds trouvé !",
        "processing": "Traitement... {current}/{total}",
        "success": "Terminé!\nRéussi : {success}/{total}\nChemins sortie :\n{output_dir}",
        "auto_not_found": "ImageMagick non trouvé. Sélectionnez manuellement.",
        "export_log": "Exporter le journal",
        "view_log": "Voir le journal",
        "log_exported": "Journal exporté vers : {path}",
        "file_processed": "{filename} → {output_path}",
        "processing_time": "Temps d'exécution : {duration}s",
        "canceling": "Annulation...",
        "cancelled": "Annulé.",
        "magick_not_found_tip": "Impossible de trouver magick.exe via le registre. Veuillez sélectionner manuellement.",
        "drag_hint": "↑ Glissez-déposez des dossiers, ZIP ou 7Z directement dans la fenêtre",
        "select_zip_path": "Choisir le dossier de sortie ZIP",
        "zip_file": "Fichiers ZIP (*.zip)",
        "compressing_to_zip": "Écriture dans le ZIP... {current}/{total}",
        "unsupported_archive": "Format d'archive non pris en charge : {ext}",
        "info": "Info",
        "no_log": "Aucun contenu de journal à afficher.",
        "log_export_success": "Journal exporté vers : {path}",
        "log_export_error": "Échec de l'exportation du journal : {error}",
        "success_title": "Succès",
        "error_title": "Erreur",
        "cancel_confirm": "Voulez-vous vraiment annuler l'opération en cours ?",
        "custom_translation": "Traduction personnalisée",
        "select_custom_translation": "Sélectionner le fichier de traduction personnalisée (translate.json)",
        "custom_translation_loaded": "Traduction personnalisée chargée : {filename}",
        "custom_translation_error": "Échec du chargement de la traduction personnalisée : {error}",
        "custom_translation_invalid": "Fichier de traduction invalide : Champ requis manquant '{missing_key}'",
        "custom_translation_corrupted": "Fichier de traduction corrompu ou format invalide",
        "custom_translation_path_saved": "Chemin de la traduction personnalisée enregistré",
        "custom_translation_not_found": "Fichier de traduction personnalisée introuvable : {path}",
        "custom_translation_reset": "Traduction personnalisée réinitialisée"
    },
    "ko": {
        "title": "스카이림 DDS 압축기",
        "language_label": "언어",
        "material_folder": "텍스처 폴더 또는 압축파일 (한 줄에 하나씩):",
        "image_magick": "ImageMagick (magick.exe):",
        "resolution": "해상도:",
        "process_mode": "처리 모드:",
        "mode_all": "모두 처리",
        "mode_skip_normals": "노멀 맵 건너뛰기 (*_n, *_msn)",
        "mode_only_normals": "노멀 맵만 처리",
        "output_method": "출력 방식:",
        "method_folder": "폴더로 출력",
        "method_zip": "ZIP 압축파일로 출력",
        "start_button": "압축 시작",
        "cancel_button": "압축 취소",
        "browse": "찾아보기...",
        "res_0.5k": "0.5K (512)",
        "res_1k": "1K (1024)",
        "res_2k": "2K (2048)",
        "res_4k": "4K (4096)",
        "error_input": "유효한 텍스처 폴더 또는 압축파일 경로를 입력하세요!",
        "error_magick": "magick.exe를 선택하세요!",
        "no_dds": ".dds 파일을 찾을 수 없습니다!",
        "processing": "처리 중... {current}/{total}",
        "success": "완료!\n성공: {success}/{total}\n출력 경로:\n{output_dir}",
        "auto_not_found": "레지스트리에서 ImageMagick을 찾을 수 없습니다.",
        "export_log": "로그 내보내기",
        "view_log": "로그 보기",
        "log_exported": "로그가 내보내졌습니다: {path}",
        "file_processed": "{filename} → {output_path}",
        "processing_time": "처리 시간: {duration}s",
        "canceling": "취소 중...",
        "cancelled": "취소됨.",
        "magick_not_found_tip": "레지스트리를 통해 magick.exe를 찾을 수 없습니다. 직접 선택해 주세요.",
        "drag_hint": "↑ 폴더, ZIP 또는 7Z를 창 위로 직접 끌어다 놓으세요",
        "select_zip_path": "ZIP 저장 폴더 선택",
        "zip_file": "ZIP 파일 (*.zip)",
        "compressing_to_zip": "ZIP에 쓰는 중... {current}/{total}",
        "unsupported_archive": "지원되지 않는 압축 형식: {ext}",
        "info": "정보",
        "no_log": "표시할 로그 내용이 없습니다.",
        "log_export_success": "로그가 내보내졌습니다: {path}",
        "log_export_error": "로그 내보내기 실패: {error}",
        "success_title": "완료",
        "error_title": "오류",
        "cancel_confirm": "현재 작업을 취소하시겠습니까?",
        "custom_translation": "사용자 정의 번역",
        "select_custom_translation": "사용자 정의 번역 파일 선택 (translate.json)",
        "custom_translation_loaded": "사용자 정의 번역 로드됨: {filename}",
        "custom_translation_error": "사용자 정의 번역 로드 실패: {error}",
        "custom_translation_invalid": "잘못된 번역 파일: 필수 필드 '{missing_key}' 누락",
        "custom_translation_corrupted": "번역 파일 손상 또는 잘못된 형식",
        "custom_translation_path_saved": "사용자 정의 번역 경로 저장됨",
        "custom_translation_not_found": "사용자 정의 번역 파일을 찾을 수 없음: {path}",
        "custom_translation_reset": "사용자 정의 번역 재설정됨"
    },
    # "custom" 将在运行时动态加载
}

# 验证翻译文件所需的最小键集（关键界面元素）
REQUIRED_TRANSLATION_KEYS = {
    "title", "language_label", "material_folder", "image_magick", 
    "resolution", "process_mode", "output_method", "start_button", 
    "browse", "error_input", "error_magick", "success_title", "error_title"
}

class Worker(QObject):
    progress = pyqtSignal(int, int, int)
    log = pyqtSignal(str)
    finished = pyqtSignal(str, int, int, str)
    error = pyqtSignal(str)

    def __init__(self, input_items, magick_exec, resolution, process_mode, current_lang, output_method="folder", zip_output_path=None):
        super().__init__()
        self.input_items = input_items  # List of dicts
        self.magick_exec = magick_exec
        self.resolution = resolution
        self.process_mode = process_mode
        self.current_lang = current_lang
        self.output_method = output_method
        self.zip_output_path = Path(zip_output_path) if zip_output_path else None
        self._canceled = False

    def cancel(self):
        self._canceled = True

    def _(self, key):
        # 支持自定义翻译
        if self.current_lang == "custom" and "custom" in LANGUAGES:
            return LANGUAGES["custom"].get(key, LANGUAGES["en"].get(key, key))
        return LANGUAGES.get(self.current_lang, LANGUAGES["en"]).get(key, key)

    def run(self):
        total_files = []
        for item in self.input_items:
            work_dir = item["work_dir"]
            for p in work_dir.rglob("*.dds"):
                is_normal = is_normal_map(p)
                include = False
                if self.process_mode == "all":
                    include = True
                elif self.process_mode == "skip_normals":
                    include = not is_normal
                elif self.process_mode == "only_normals":
                    include = is_normal
                if include:
                    total_files.append((item, p))

        if not total_files:
            self.error.emit("no_dds")
            return

        success = 0
        total = len(total_files)

        temp_output_base = None
        if self.output_method == "zip":
            temp_output_base = Path(tempfile.mkdtemp())

        for i, (item, src) in enumerate(total_files):
            if self._canceled:
                return

            start_time = datetime.now()
            
            if self.output_method == "folder":
                if item["type"] == "folder":
                    mod_root = item["source_path"]
                    output_root = mod_root.parent / (mod_root.name + "_low_res")
                else:  # archive
                    mod_root = item["work_dir"]
                    original_name = item["source_path"].stem
                    output_root = item["source_path"].parent / (original_name + "_low_res")
                rel_path = src.relative_to(item["work_dir"])
                dst = output_root / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)
            else:  # zip mode
                safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in item["source_path"].stem)
                temp_mod_dir = temp_output_base / safe_name
                rel_path = src.relative_to(item["work_dir"])
                dst = temp_mod_dir / rel_path
                dst.parent.mkdir(parents=True, exist_ok=True)

            is_normal = is_normal_map(src)
            cmd = [self.magick_exec, str(src)]
            if is_normal:
                cmd += ["-blur", "0x1.0",  f"{self.resolution}x{self.resolution}>", "-define", "dds:compression=auto"]
            else:
                cmd += ["-blur", "0x1.0", "-filter", "Lanczos", f"{self.resolution}x{self.resolution}>", "-define", "dds:compression=auto"]
            cmd.append(str(dst))
            
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            try:
                # 不使用text=True，手动处理编码
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=60,
                    creationflags=creationflags
                )
                duration = (datetime.now() - start_time).total_seconds()

                # 安全处理stderr输出
                stderr_text = ""
                if result.stderr:
                    try:
                        # 尝试用UTF-8解码，失败时用系统默认编码
                        stderr_text = result.stderr.decode('utf-8', errors='replace')
                    except UnicodeDecodeError:
                        try:
                            # 获取系统默认编码
                            default_encoding = locale.getpreferredencoding()
                            stderr_text = result.stderr.decode(default_encoding, errors='replace')
                        except:
                            stderr_text = result.stderr.decode('latin1', errors='replace')
                
                if result.returncode == 0:
                    success += 1
                    msg = f"{self._('file_processed').format(filename=src.name, output_path=str(dst))}\n"
                    msg += f"{self._('processing_time').format(duration=round(duration, 2))}"
                    self.log.emit(msg)
                else:
                    # 安全截取错误信息，确保不会因NoneType出错
                    error_msg = stderr_text[:200] if stderr_text else "Unknown error"
                    self.log.emit(f"ERROR: {src.name}: {error_msg}")
            except subprocess.TimeoutExpired:
                duration = (datetime.now() - start_time).total_seconds()
                self.log.emit(f"TIMEOUT: {src.name} (after {duration:.1f}s)")
            except Exception as e:
                self.log.emit(f"EXCEPTION: {src.name}: {str(e)}")

            self.progress.emit(i + 1, total, success)

        # === 打包输出 ===
        if self.output_method == "zip" and not self._canceled:
            for item in self.input_items:
                if self._canceled:
                    break
                safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in item["source_path"].stem)
                zip_base = self.zip_output_path / (safe_name + "_low_res")
                zip_path = get_unique_filename(str(zip_base))
                temp_mod_dir = temp_output_base / safe_name
                if not temp_mod_dir.exists():
                    continue
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_STORED) as zf:
                    for root, _, files in os.walk(temp_mod_dir):
                        for file in files:
                            full_path = Path(root) / file
                            arcname = full_path.relative_to(temp_output_base)
                            zf.write(full_path, arcname)
                self.log.emit(f"📦 Created: {zip_path.name}")
            self.finished.emit("success", success, total, str(self.zip_output_path))
        elif self.output_method == "folder":
            output_dirs = []
            for item in self.input_items:
                if item["type"] == "folder":
                    mod_root = item["source_path"]
                    output_root = mod_root.parent / (mod_root.name + "_low_res")
                else:
                    original_name = item["source_path"].stem
                    output_root = item["source_path"].parent / (original_name + "_low_res")
                output_dirs.append(str(output_root))
            output_text = "\n".join(dict.fromkeys(output_dirs))
            self.finished.emit("success", success, total, output_text)

        # 清理临时目录
        for item in self.input_items:
            if item.get("is_temp") and item["work_dir"].exists():
                shutil.rmtree(item["work_dir"], ignore_errors=True)
        if temp_output_base and temp_output_base.exists():
            shutil.rmtree(temp_output_base, ignore_errors=True)

# ========== 主窗口类 ==========
class DDSCompressorApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.settings = QSettings("MyCompany", "DDSCompressor")
        self.current_lang = self.settings.value("language", "zh")
        
        # 处理自定义翻译的持久化
        if self.current_lang == "custom":
            custom_path = self.settings.value("custom_translation_path", "")
            if custom_path and Path(custom_path).exists():
                if self.load_custom_translation_from_path(custom_path):
                    # 成功加载，保留"custom"设置
                    pass
                else:
                    # 加载失败，回退到中文（标准汉语）
                    self.current_lang = "zh"
                    self.settings.setValue("language", "zh")
            else:
                # 路径不存在，回退到中文（标准汉语）
                self.current_lang = "zh"
                self.settings.setValue("language", "zh")
                if custom_path:
                    self.show_message(
                        self._("error_title"),
                        self._("custom_translation_not_found").format(path=custom_path),
                        QMessageBox.Warning
                    )
        
        if self.current_lang not in LANGUAGES:
            self.current_lang = "zh"
        
        self.tr_dict = LANGUAGES[self.current_lang]
        self.log_content = ""
        self.worker_thread = None
        self.worker = None
        self.init_ui()
        self.apply_stylesheet()
        self.load_settings()
        self.check_magick_auto()
        app_icon_path = resource_path("app_icon.ico")
        if app_icon_path.exists():
            self.setWindowIcon(QIcon(str(app_icon_path)))
        else:
            print(f"Warning: Icon not found at {app_icon_path}")

    def _(self, key):
        # 安全获取翻译，支持自定义翻译
        if self.current_lang == "custom" and "custom" in LANGUAGES:
            return LANGUAGES["custom"].get(key, LANGUAGES["en"].get(key, key))
        return self.tr_dict.get(key, LANGUAGES["en"].get(key, key))

    def init_ui(self):
        self.setWindowTitle(self._("title"))
        self.resize(700, 650)
        self.setMinimumSize(600, 500)
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # ===== 语言选择区域 =====
        lang_layout = QHBoxLayout()
        lang_label = QLabel(self._("language_label"))
        lang_label.setObjectName("lang_label")
        lang_label.setStyleSheet("font-weight: bold;")
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("lang_combo")
        
        # 语言映射（包含自定义选项）
        self.lang_map = ["zh", "en", "ru", "fr", "ko", "custom"]
        lang_names = [
            "中文（标准汉语）",
            "English",
            "Русский",
            "Français",
            "한국어",
            self._("custom_translation")  # 动态获取"自定义翻译"的翻译
        ]
        self.lang_combo.addItems(lang_names)
        
        # 设置当前语言索引
        if self.current_lang in self.lang_map:
            self.lang_combo.setCurrentIndex(self.lang_map.index(self.current_lang))
        else:
            self.lang_combo.setCurrentIndex(0)  # 默认中文（标准汉语）
        
        self.lang_combo.currentIndexChanged.connect(self.change_language)
        lang_layout.addStretch()
        lang_layout.addWidget(lang_label)
        lang_layout.addWidget(self.lang_combo)
        layout.addLayout(lang_layout)
        
        # ===== 材质输入区域 =====
        folder_label = QLabel(self._("material_folder"))
        folder_label.setObjectName("folder_label")
        folder_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(folder_label)
        
        self.input_edit = QTextEdit()
        self.input_edit.setObjectName("input_edit")
        self.input_edit.setPlaceholderText(self._("material_folder"))
        self.input_edit.setMaximumHeight(100)
        self.input_edit.setAcceptRichText(False)
        
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_edit)
        
        self.input_btn = QPushButton(self._("browse"))
        self.input_btn.setObjectName("input_btn")
        self.input_btn.clicked.connect(self.browse_input)
        input_layout.addWidget(self.input_btn)
        layout.addLayout(input_layout)
        
        self.drag_hint = QLabel(self._("drag_hint"))
        self.drag_hint.setObjectName("drag_hint")
        self.drag_hint.setStyleSheet("font-size: 8pt; color: gray; margin-top: -4px;")
        layout.addWidget(self.drag_hint)
        
        # ===== ImageMagick 路径 =====
        magick_label = QLabel(self._("image_magick"))
        magick_label.setObjectName("magick_label")
        magick_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(magick_label)
        
        magick_layout = QHBoxLayout()
        self.magick_edit = QLineEdit()
        self.magick_edit.setObjectName("magick_edit")
        self.magick_btn = QPushButton(self._("browse"))
        self.magick_btn.setObjectName("magick_btn")
        self.magick_btn.clicked.connect(self.browse_magick)
        magick_layout.addWidget(self.magick_edit)
        magick_layout.addWidget(self.magick_btn)
        layout.addLayout(magick_layout)
        
        self.magick_tip_label = QLabel(self._("magick_not_found_tip"))
        self.magick_tip_label.setObjectName("magick_tip_label")
        self.magick_tip_label.setStyleSheet("color: #d32f2f; font-size: 9pt; margin-top: 4px;")
        self.magick_tip_label.setVisible(False)
        layout.addWidget(self.magick_tip_label)
        
        # ===== 分辨率选择 =====
        res_label = QLabel(self._("resolution"))
        res_label.setObjectName("res_label")
        res_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(res_label)
        
        self.res_combo = QComboBox()
        self.res_combo.setObjectName("res_combo")
        self.res_combo.addItems([
            self._("res_0.5k"),
            self._("res_1k"),
            self._("res_2k"),
            self._("res_4k")
        ])
        self.res_combo.setCurrentIndex(0)
        layout.addWidget(self.res_combo)
        
        # ===== 处理模式 =====
        mode_label = QLabel(self._("process_mode"))
        mode_label.setObjectName("mode_label")
        mode_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(mode_label)
        
        self.mode_combo = QComboBox()
        self.mode_combo.setObjectName("mode_combo")
        self.mode_combo.addItems([
            self._("mode_all"),
            self._("mode_skip_normals"),
            self._("mode_only_normals")
        ])
        layout.addWidget(self.mode_combo)
        
        # ===== 输出方式 =====
        output_method_label = QLabel(self._("output_method"))
        output_method_label.setObjectName("output_method_label")
        output_method_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(output_method_label)
        
        self.output_method_combo = QComboBox()
        self.output_method_combo.setObjectName("output_method_combo")
        self.output_method_combo.addItems([
            self._("method_folder"),
            self._("method_zip")
        ])
        layout.addWidget(self.output_method_combo)
        
        # ===== 按钮区域 =====
        button_layout = QHBoxLayout()
        self.export_btn = QPushButton(self._("export_log"))
        self.export_btn.setObjectName("export_btn")
        self.view_log_btn = QPushButton(self._("view_log"))
        self.view_log_btn.setObjectName("view_log_btn")
        self.start_btn = QPushButton(self._("start_button"))
        self.start_btn.setObjectName("start_btn")
        
        self.export_btn.clicked.connect(self.export_log)
        self.view_log_btn.clicked.connect(self.view_log)
        self.start_btn.clicked.connect(self.start_compression)
        
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.view_log_btn)
        button_layout.addWidget(self.start_btn)
        layout.addLayout(button_layout)
        
        # ===== 进度与状态 =====
        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("progress_bar")
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QLabel("")
        self.status_label.setObjectName("status_label")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)
        
        self.setLayout(layout)

    def apply_stylesheet(self):
        font = QFont("Segoe UI", 9)
        font.setStyleHint(QFont.SansSerif)
        QApplication.setFont(font)
        
        common_style = """
        QWidget {
            background-color: #e8e8e8;
            font-family: sans-serif;
            font-size: 9pt;
        }
        QLineEdit, QComboBox, QTextEdit {
            background-color: white;
            border: none;
            border-radius: 4px;
            padding: 6px;
        }
        QComboBox::drop-down {
            border: none;
            width: 20px;
            background: white;
            border-radius: 4px;
        }
        QComboBox::down-arrow {
            image: url();
            width: 12px;
            height: 12px;
            margin: 4px;
            background: #ccc;
            border-radius: 2px;
        }
        QPushButton {
            background-color: white;
            color: #333;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
        }
        QPushButton:hover {
            background-color: #f5f5f5;
        }
        QPushButton:pressed {
            background-color: #e0e0e0;
        }
        QPushButton#start_btn {
            background-color: #6A0DAD;
            color: white;
            font-weight: bold;
        }
        QPushButton#start_btn:hover {
            background-color: #7B1FA2;
        }
        QPushButton#start_btn:pressed {
            background-color: #512DA8;
        }
        QProgressBar {
            border: none;
            border-radius: 4px;
            background-color: #f5f5f5;
            height: 20px;
            text-align: center;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 4px;
        }
        QLabel {
            font-size: 9pt;
        }
        """
        self.setStyleSheet(common_style)

    def parse_input_lines(self, lines):
        """解析输入行，返回标准化的输入项列表"""
        items = []
        temp_dirs = []
        try:
            for line in lines:
                p = line.strip()
                if not p:
                    continue
                if p.startswith("file:///"):
                    p = p[8:]
                try:
                    p = urllib.parse.unquote(p)
                except:
                    pass
                p = Path(os.path.normpath(p))
                if not p.exists():
                    continue
                
                if p.is_dir():
                    items.append({
                        "type": "folder",
                        "source_path": p,
                        "work_dir": p,
                        "is_temp": False
                    })
                elif p.is_file():
                    suffix = p.suffix.lower()
                    if suffix in ('.zip', '.7z'):
                        temp_dir = Path(tempfile.mkdtemp())
                        temp_dirs.append(temp_dir)
                        roots = extract_archive(p, temp_dir)
                        for root in roots:
                            items.append({
                                "type": "archive",
                                "source_path": p,
                                "work_dir": root,
                                "is_temp": True
                            })
                    else:
                        pass
            return items, temp_dirs
        except Exception as e:
            for td in temp_dirs:
                shutil.rmtree(td, ignore_errors=True)
            raise e

    def get_input_items(self):
        text = self.input_edit.toPlainText().strip()
        if not text:
            return [], []
        lines = text.splitlines()
        return self.parse_input_lines(lines)

    def load_settings(self):
        last_input = self.settings.value("last_input", "")
        last_magick = self.settings.value("last_magick", "")
        output_method = self.settings.value("output_method", 0, type=int)
        
        if isinstance(last_input, str):
            self.input_edit.setPlainText(last_input)
        self.magick_edit.setText(last_magick)
        self.output_method_combo.setCurrentIndex(output_method)

    def save_settings(self):
        paths = "\n".join([str(Path(line.strip())) for line in self.input_edit.toPlainText().splitlines() if line.strip()])
        self.settings.setValue("last_input", paths)
        self.settings.setValue("last_magick", self.magick_edit.text())
        self.settings.setValue("output_method", self.output_method_combo.currentIndex())
        
        # 保存当前语言（如果是custom，同时保存路径）
        self.settings.setValue("language", self.current_lang)
        if self.current_lang == "custom" and "custom" in LANGUAGES:
            # 尝试从最近加载的自定义翻译中获取路径（简化处理）
            # 实际上我们不在内存中保存路径，所以这里不保存
            # 路径保存在load_custom_translation成功时
            pass

    def check_magick_auto(self):
        auto_magick = find_imagemagick_from_registry()
        if auto_magick:
            self.magick_edit.setText(auto_magick)
            self.magick_tip_label.setVisible(False)
        else:
            self.magick_tip_label.setText(self._("magick_not_found_tip"))
            self.magick_tip_label.setVisible(True)

    def validate_translation_dict(self, trans_dict, filepath):
        """验证翻译字典是否包含所有必需的键"""
        # 检查是否为字典
        if not isinstance(trans_dict, dict):
            raise ValueError(self._("custom_translation_corrupted"))
        
        # 检查必需键
        missing_keys = [key for key in REQUIRED_TRANSLATION_KEYS if key not in trans_dict]
        if missing_keys:
            raise ValueError(self._("custom_translation_invalid").format(missing_key=missing_keys[0]))
        
        # 检查标题是否存在（额外验证）
        if "title" not in trans_dict or not isinstance(trans_dict["title"], str):
            raise ValueError(self._("custom_translation_invalid").format(missing_key="title"))
        
        return True

    def load_custom_translation(self):
        """交互式加载自定义翻译文件"""
        # 记住当前语言用于回退
        previous_lang = self.current_lang
        previous_index = self.lang_combo.currentIndex()
        
        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self._("select_custom_translation"),
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            # 用户取消，回退到之前的选择
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(previous_index)
            self.lang_combo.blockSignals(False)
            return False
        
        return self.load_custom_translation_from_path(file_path, show_success=True)

    def load_custom_translation_from_path(self, file_path, show_success=False):
        """从指定路径加载自定义翻译"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                trans_dict = json.load(f)
            
            # 验证翻译文件
            self.validate_translation_dict(trans_dict, file_path)
            
            # 保存到LANGUAGES
            LANGUAGES["custom"] = trans_dict
            
            # 保存路径到设置（用于启动时自动加载）
            self.settings.setValue("custom_translation_path", file_path)
            self.settings.setValue("custom_translation_path_saved", True)
            
            if show_success:
                filename = Path(file_path).name
                self.show_message(
                    self._("success_title"),
                    self._("custom_translation_loaded").format(filename=filename),
                    QMessageBox.Information
                )
            
            return True
        except json.JSONDecodeError as e:
            error_msg = f"JSON syntax error: {str(e)}"
            self.show_message(
                self._("error_title"),
                self._("custom_translation_error").format(error=error_msg),
                QMessageBox.Critical
            )
        except ValueError as e:
            self.show_message(
                self._("error_title"),
                str(e),
                QMessageBox.Critical
            )
        except Exception as e:
            self.show_message(
                self._("error_title"),
                self._("custom_translation_error").format(error=str(e)),
                QMessageBox.Critical
            )
        
        return False

    def show_message(self, title, text, icon=QMessageBox.Information):
        """统一的消息显示方法"""
        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setText(text)
        msg.setIcon(icon)
        msg.exec_()

    def change_language(self, index):
        new_lang = self.lang_map[index]
        
        # 如果选择的是自定义翻译
        if new_lang == "custom":
            # 如果已经加载过自定义翻译，直接切换
            if "custom" in LANGUAGES:
                self.current_lang = "custom"
                self.settings.setValue("language", "custom")
                self.tr_dict = LANGUAGES["custom"]
                self.update_texts()
                return
            else:
                # 尝试从设置中加载
                custom_path = self.settings.value("custom_translation_path", "")
                if custom_path and Path(custom_path).exists():
                    if self.load_custom_translation_from_path(custom_path):
                        self.current_lang = "custom"
                        self.settings.setValue("language", "custom")
                        self.tr_dict = LANGUAGES["custom"]
                        self.update_texts()
                        return
                # 需要用户选择文件
                if not self.load_custom_translation():
                    # 加载失败，回退到之前语言
                    prev_lang = self.settings.value("language", "zh")
                    if prev_lang in self.lang_map:
                        self.lang_combo.blockSignals(True)
                        self.lang_combo.setCurrentIndex(self.lang_map.index(prev_lang))
                        self.lang_combo.blockSignals(False)
                    return
        
        # 处理其他语言
        if new_lang == self.current_lang:
            return
        
        # 保存当前输入内容（避免切换时丢失）
        current_input = self.input_edit.toPlainText()
        
        # 更新语言设置
        self.current_lang = new_lang
        self.settings.setValue("language", self.current_lang)
        
        # 更新翻译字典
        if new_lang == "custom" and "custom" in LANGUAGES:
            self.tr_dict = LANGUAGES["custom"]
        else:
            self.tr_dict = LANGUAGES.get(new_lang, LANGUAGES["en"])
        
        # 完整更新UI
        self.update_texts()
        
        # 恢复输入内容（避免因UI重建丢失）
        self.input_edit.setPlainText(current_input)
        
        # 重新检查magick路径提示（不同语言提示文本不同）
        if not self.magick_edit.text().strip():
            self.magick_tip_label.setVisible(True)
        else:
            self.magick_tip_label.setVisible(False)

    def update_texts(self):
        """安全更新所有可翻译控件的文本"""
        # 窗口标题
        self.setWindowTitle(self._("title"))
        
        # 标签更新（通过objectName精确查找）
        labels = [
            ("lang_label", "language_label"),
            ("folder_label", "material_folder"),
            ("magick_label", "image_magick"),
            ("res_label", "resolution"),
            ("mode_label", "process_mode"),
            ("output_method_label", "output_method"),
            ("magick_tip_label", "magick_not_found_tip"),
            ("drag_hint", "drag_hint")
        ]
        for obj_name, text_key in labels:
            label = self.findChild(QLabel, obj_name)
            if label:
                label.setText(self._(text_key))
        
        # 按钮更新
        buttons = [
            ("input_btn", "browse"),
            ("magick_btn", "browse"),
            ("export_btn", "export_log"),
            ("view_log_btn", "view_log"),
            ("start_btn", "start_button")  # 注意：运行时会动态改为cancel_button
        ]
        for obj_name, text_key in buttons:
            btn = self.findChild(QPushButton, obj_name)
            if btn:
                btn.setText(self._(text_key))
        
        # 组合框：分辨率
        res_combo = self.findChild(QComboBox, "res_combo")
        if res_combo:
            current_idx = res_combo.currentIndex()
            items = ["res_0.5k", "res_1k", "res_2k", "res_4k"]
            for i, key in enumerate(items):
                if i < res_combo.count():
                    res_combo.setItemText(i, self._(key))
            if 0 <= current_idx < res_combo.count():
                res_combo.setCurrentIndex(current_idx)
        
        # 组合框：处理模式
        mode_combo = self.findChild(QComboBox, "mode_combo")
        if mode_combo:
            current_idx = mode_combo.currentIndex()
            items = ["mode_all", "mode_skip_normals", "mode_only_normals"]
            for i, key in enumerate(items):
                if i < mode_combo.count():
                    mode_combo.setItemText(i, self._(key))
            if 0 <= current_idx < mode_combo.count():
                mode_combo.setCurrentIndex(current_idx)
        
        # 组合框：输出方式
        output_combo = self.findChild(QComboBox, "output_method_combo")
        if output_combo:
            current_idx = output_combo.currentIndex()
            items = ["method_folder", "method_zip"]
            for i, key in enumerate(items):
                if i < output_combo.count():
                    output_combo.setItemText(i, self._(key))
            if 0 <= current_idx < output_combo.count():
                output_combo.setCurrentIndex(current_idx)
        
        # 语言选择框：更新"自定义翻译"选项的文本（使其能被翻译）
        lang_combo = self.findChild(QComboBox, "lang_combo")
        if lang_combo and lang_combo.count() > 5:  # 确保有"自定义"选项
            # 更新第6项（索引5）的文本为当前语言下的"自定义翻译"
            lang_combo.setItemText(5, self._("custom_translation"))
        
        # 更新语言选择框当前显示（不影响选项文本，保持原生语言名）
        # 仅更新当前选中项的显示文本（通过设置索引自动更新）
        if self.current_lang in self.lang_map:
            lang_combo.setCurrentIndex(self.lang_map.index(self.current_lang))

    def browse_input(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self._("material_folder"),
            "",
            "All Supported (*.zip *.7z);;ZIP Archives (*.zip);;7z Archives (*.7z);;All Files (*)"
        )
        if not files:
            folder = QFileDialog.getExistingDirectory(self, self._("material_folder"), "")
            if folder:
                files = [folder]
        if files:
            current = self.input_edit.toPlainText().strip()
            new_text = "\n".join(files)
            if current:
                self.input_edit.setPlainText(current + "\n" + new_text)
            else:
                self.input_edit.setPlainText(new_text)
            self.save_settings()

    def browse_magick(self):
        file, _ = QFileDialog.getOpenFileName(
            self,
            self._("image_magick"),
            "",
            "Executable Files (*.exe);;All Files (*)"
        )
        if file:
            self.magick_edit.setText(file)
            self.settings.setValue("last_magick", file)
            self.magick_tip_label.setVisible(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        paths = []
        for url in urls:
            raw_path = url.toLocalFile()
            p = Path(raw_path)
            if p.suffix.lower() in ('.zip', '.7z') or p.is_dir():
                paths.append(str(p))
        if paths:
            current = self.input_edit.toPlainText().strip()
            new_text = "\n".join(paths)
            if current:
                self.input_edit.setPlainText(current + "\n" + new_text)
            else:
                self.input_edit.setPlainText(new_text)
            self.save_settings()

    def start_compression(self):
        # 如果已在运行，处理取消逻辑
        if self.worker_thread is not None and self.worker_thread.isRunning():
            reply = QMessageBox.question(
                self,
                self._("cancel_confirm"),
                self._("cancel_confirm"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                if self.worker:
                    self.worker.cancel()
                self.start_btn.setEnabled(False)
                self.status_label.setText(self._("canceling"))
                self.progress_bar.setStyleSheet("""
                    QProgressBar::chunk {
                        background-color: #ff9800;
                    }
                """)
                return
        
        try:
            input_items, temp_dirs = self.get_input_items()
        except Exception as e:
            QMessageBox.critical(self, self._("error_title"), f"Failed to parse input: {e}")
            return
        
        if not input_items:
            QMessageBox.critical(self, self._("error_title"), self._("error_input"))
            return
        
        magick_exec = self.magick_edit.text().strip()
        if not magick_exec or not os.path.isfile(magick_exec):
            QMessageBox.critical(self, self._("error_title"), self._("error_magick"))
            return
        
        resolutions = ["512", "1024", "2048", "4096"]
        resolution = resolutions[self.res_combo.currentIndex()]
        
        mode_index = self.mode_combo.currentIndex()
        mode_map = ["all", "skip_normals", "only_normals"]
        process_mode = mode_map[mode_index]
        
        output_method_index = self.output_method_combo.currentIndex()
        output_method = "folder" if output_method_index == 0 else "zip"
        
        zip_output_path = None
        if output_method == "zip":
            zip_dir = QFileDialog.getExistingDirectory(
                self,
                self._("select_zip_path"),
                ""
            )
            if not zip_dir:
                return
            zip_output_path = Path(zip_dir)
        
        self.log_content = ""
        self.start_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText(self._("processing").format(current="0", total="..."))
        self.progress_bar.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        
        self.worker = Worker(
            input_items=input_items,
            magick_exec=magick_exec,
            resolution=resolution,
            process_mode=process_mode,
            current_lang=self.current_lang,
            output_method=output_method,
            zip_output_path=zip_output_path
        )
        self.thread = QThread()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
        self.worker_thread = self.thread
        self.start_btn.setText(self._("cancel_button"))
        self.start_btn.setEnabled(True)

    def reset_cancel_state(self):
        """修复：使用翻译文本替代硬编码"""
        self.progress_bar.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        self.status_label.setText(self._("cancelled"))
        self.start_btn.setText(self._("start_button"))
        self.start_btn.setEnabled(True)

    def append_log(self, msg):
        self.log_content += msg + "\n"

    def update_progress(self, current, total, success):
        progress = int((current / total) * 100)
        self.progress_bar.setValue(progress)
        self.status_label.setText(self._("processing").format(current=current, total=total))

    def on_finished(self, msg_type, success, total, extra_info):
        tr = LANGUAGES.get(self.current_lang, LANGUAGES["en"])
        msg = tr["success"].format(success=success, total=total, output_dir=extra_info)
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(self._("success_title"))
        msg_box.setText(msg)
        msg_box.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg_box.exec_()
        self.worker_thread = None
        self.worker = None
        self.start_btn.setText(self._("start_button"))
        self.start_btn.setEnabled(True)

    def on_error(self, error_key):
        self.start_btn.setEnabled(True)
        tr = LANGUAGES.get(self.current_lang, LANGUAGES["en"])
        msg = tr.get(error_key, error_key) if error_key in tr else str(error_key)
        QMessageBox.critical(self, self._("error_title"), msg)
        self.worker_thread = None
        self.worker = None
        self.start_btn.setText(self._("start_button"))  # 重置进度条样式
        self.progress_bar.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)

    def export_log(self):
        if not self.log_content.strip():
            QMessageBox.information(self, self._("info"), self._("no_log"))
            return
        
        exe_dir = os.path.dirname(sys.executable)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = os.path.join(exe_dir, f"DDS_Compression_Log_{timestamp}.txt")
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(self.log_content)
            QMessageBox.information(self, self._("success_title"), self._("log_export_success").format(path=log_file))
        except Exception as e:
            QMessageBox.critical(self, self._("error_title"), self._("log_export_error").format(error=str(e)))

    def view_log(self):
        if not self.log_content.strip():
            QMessageBox.information(self, self._("info"), self._("no_log"))
            return
        
        dialog = LogDialog(self.log_content, self.current_lang, self.tr_dict, self)
        dialog.exec_()

class LogDialog(QDialog):
    def __init__(self, log_content, current_lang, tr_dict, parent=None):
        super().__init__(parent)
        self.current_lang = current_lang
        self.tr_dict = tr_dict
        self.setWindowTitle(self.tr_text("Compression Log"))
        self.resize(600, 400)
        
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(log_content)
        layout.addWidget(self.text_edit)
        
        close_btn = QPushButton(self.tr_text("Close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
    
    def tr_text(self, text):
        """使用主窗口的翻译字典进行翻译"""
        # 映射对话框特定文本到翻译键
        key_map = {
            "Compression Log": "view_log",  # 复用"查看日志"的翻译
            "Close": "browse"  # 复用"浏览"的翻译（在多数语言中"关闭"和"浏览"不同，但作为后备）
        }
        
        # 尝试使用映射的键
        if text in key_map:
            key = key_map[text]
            if key in self.tr_dict:
                return self.tr_dict[key]
        
        # 后备：尝试直接匹配
        if text in self.tr_dict:
            return self.tr_dict[text]
        
        # 最终后备：返回原文
        return text

if hasattr(Qt, 'AA_EnableHighDpiScaling'):
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)

if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DDSCompressorApp()
    window.show()
    sys.exit(app.exec_())