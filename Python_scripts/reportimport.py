import os
import json
import base64
import mimetypes
from datetime import date, datetime
import uuid
import requests  

RPTDESIGN_PATH = "birt.rptdesign"
STATE_PATH = "birt_state.json"

# Базовый скелет XML
HEADER_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<report xmlns="http://www.eclipse.org/birt/2005/design" version="3.2.23" id="1">
    <property name="createdBy">Проектировщик BIRT Eclipse</property>
    <html-property name="description">{description}</html-property>
    <property name="units">px</property>
    <property name="bidiLayoutOrientation">ltr</property>
    <property name="imageDPI">96</property>
    <page-setup>
        <simple-master-page name="Simple MasterPage" id="2">
            <page-footer>
                <text id="3">
                    <property name="contentType">html</property>
                    <text-property name="content"><![CDATA[<value-of>new Date()</value-of>]]></text-property>
                </text>
            </page-footer>
        </simple-master-page>
    </page-setup>

   <body>
"""

BODY_CLOSE_TAG = "\n   </body>"
REPORT_CLOSE_TAG = "\n</report>"

# Глобальная «память» о состоянии блоков и следующего id
_state = {
    "next_id": 1,
    "blocks": [],
    "image_structures": []
}

# Конфигурация API
API_CONFIG = {
    "base_url": "https://adm.rkd.on-dev.ru",
    "username": "admin",
    "password": "hOIo1RWulKRFNo8IOByMmA==",
    "user_uuid": None
}

def _get_header_description():
    today = date.today().strftime("%d.%m.%Y")
    return f"v 1.0 {today}"

def _load_state():
    global _state
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                _state["next_id"] = int(data.get("next_id", 1))
                _state["blocks"] = data.get("blocks", [])
                _state["image_structures"] = data.get("image_structures", [])
        except Exception:
            _state = {"next_id": 1, "blocks": [], "image_structures": []}

def _save_state():
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "next_id": _state["next_id"],
            "blocks": _state["blocks"],
            "image_structures": _state["image_structures"]
        }, f, ensure_ascii=False, indent=2)

def _get_next_id():
    nid = _state["next_id"]
    _state["next_id"] += 1
    _save_state()
    return str(nid)

def _build_full_xml():
    body_xml = "\n".join(_state.get("blocks", []))
    
    images_block = ""
    if _state.get("image_structures"):
        images_block_lines = ['<list-property name="images">']
        for img_data in _state["image_structures"]:
            images_block_lines.append("    <structure>")
            images_block_lines.append(f"        <property name=\"name\">{img_data['name']}</property>")
            images_block_lines.append(f"        <property name=\"type\">{img_data['type']}</property>")
            images_block_lines.append(f"        <property name=\"data\">{img_data['data']}</property>")
            images_block_lines.append("    </structure>")
        images_block_lines.append("</list-property>")
        images_block = "\n".join(images_block_lines)

    full_xml = HEADER_TEMPLATE.format(description=_get_header_description())
    full_xml += body_xml
    full_xml += BODY_CLOSE_TAG

    if _state.get("image_structures"):
        full_xml += "\n" + images_block
    
    full_xml += REPORT_CLOSE_TAG
    return full_xml

def _ensure_state_loaded():
    if not os.path.exists(STATE_PATH) and not _state.get("blocks"):
        _state["next_id"] = 1
        _state["blocks"] = []
        _state["image_structures"] = []
        _save_state()
    _load_state()

def _write_rptdesign():
    full_xml = _build_full_xml()
    with open(RPTDESIGN_PATH, "w", encoding="utf-8") as f:
        f.write(full_xml)

def _append_block(block_xml: str):
    _state["blocks"].append(block_xml)
    _save_state()
    _write_rptdesign()

def _generate_report_name():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_uuid = API_CONFIG["user_uuid"] or str(uuid.uuid4())
    return f"{timestamp}_{user_uuid}"

def _send_import_binary_plugin(report_name: str, report_content: str):
    """Отправка запроса importBinaryPlugin"""
    url = "https://adm.rkd.on-dev.ru/report_rkd/PluginsWS/importBinaryPlugin"
    
    # Первая часть тела - аутентификация
    auth_data = {
        "userName": API_CONFIG["username"],
        "password": API_CONFIG["password"],
        "clientIPAddress": "",
        "initiator": "Consumer web client 1.20.13"
    }
    
    # Вторая часть тела - данные плагина
    plugin_data = {
        "name": report_name,
        "mainClass": "birt.rptdesign",
        "version": "1.0",
        "versionDate": "2022-07-14T21:00:00Z",
        "type": "Отчеты BIRT"
    }
    
    # Третья часть - содержимое файла в виде массива байтов
    file_bytes = [ord(char) for char in report_content]
    
    # Собираем полное тело запроса
    request_body = [auth_data, plugin_data, file_bytes]
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    
    try:
        response = requests.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке importBinaryPlugin: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Статус: {e.response.status_code}")
            print(f"Ответ: {e.response.text}")
        return None

def _send_save_request(report_name: str):
    """Отправка запроса save"""
    url = "https://adm.rkd.on-dev.ru/report_rkd/ReportTuningWS/save"
    
    # Первая часть тела - аутентификация
    auth_data = {
        "userName": API_CONFIG["username"],
        "password": API_CONFIG["password"],
        "clientIPAddress": "",
        "initiator": "Consumer web client 1.20.13"
    }
    
    # Вторая часть тела - данные для сохранения
    save_data = {
        "typeReport": "7",
        "userList": [],
        "name": report_name,
        "className": report_name
    }
    
    # Собираем полное тело запроса
    request_body = [auth_data, save_data]
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    
    try:
        response = requests.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке save: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Статус: {e.response.status_code}")
            print(f"Ответ: {e.response.text}")
        return None

def send_report_to_api():
    """Отправляет отчет через два запроса: importBinaryPlugin и save"""
    if not os.path.exists(RPTDESIGN_PATH):
        print("Ошибка: Файл отчета не найден")
        return False
    
    report_name = _generate_report_name()
    
    try:
        # Читаем содержимое отчета
        with open(RPTDESIGN_PATH, "r", encoding="utf-8") as f:
            report_content = f.read()
        
        print(f"Отправка importBinaryPlugin для {report_name}...")
        import_result = _send_import_binary_plugin(report_name, report_content)
        
        if not import_result:
            print("Ошибка при загрузке отчета")
            return False
        
        print(f"Отправка save для {report_name}...")
        save_result = _send_save_request(report_name)
        
        if not save_result:
            print("Ошибка при сохранении отчета")
            return False
        
        print(f"Отчет {report_name} успешно отправлен и сохранен")
        return True
        
    except Exception as e:
        print(f"Ошибка при обработке отчета: {e}")
        return False

def configure_api(settings: dict):
    """Конфигурация параметров API"""
    global API_CONFIG
    API_CONFIG.update(settings)
    print("Конфигурация API обновлена")

def addTitle(title: str):
    """Добавить заголовок в отчёт."""
    _ensure_state_loaded()
    if title is None:
        title = ""
    _id = _get_next_id()

    block = f"""
<text id="{_id}">
    <property name="fontSize">18px</property>
    <property name="fontWeight">bold</property>
    <property name="whiteSpace">nowrap</property>
    <property name="contentType">auto</property>
    <text-property name="content"><![CDATA[{title}]]></text-property>
</text>""".rstrip()
    _append_block(block)

def addText(text: str):
    """Добавить обычный текст/описание в отчёт."""
    _ensure_state_loaded()
    if text is None:
        text = ""
    _id = _get_next_id()

    block = f"""
<text id="{_id}">
    <property name="fontSize">14px</property>
    <property name="contentType">auto</property>
    <text-property name="content"><![CDATA[{text}]]></text-property>
</text>""".rstrip()
    _append_block(block)

def addImg(image_path: str, width: str = "150mm", height: str = "100mm"):
    """Добавляет изображение в отчет"""
    _ensure_state_loaded()
    if not image_path or not os.path.exists(image_path):
        print(f"Предупреждение: Файл изображения не найден: {image_path}")
        return

    mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
    image_name = os.path.basename(image_path)
    
    try:
        with open(image_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("ascii")
    except Exception as e:
        print(f"Ошибка при чтении изображения {image_path}: {e}")
        return

    unique_image_name = f"{os.path.splitext(image_name)[0]}_{_state['next_id']}{os.path.splitext(image_name)[1]}"
    
    _id_image_element = _get_next_id()
    image_element_block = f"""
<image id="{_id_image_element}">
    <property name="height">{height}</property>
    <property name="width">{width}</property>
    <property name="source">embed</property>
    <property name="imageName">{unique_image_name}</property>
</image>""".strip()
    _state["blocks"].append(image_element_block)

    _state.setdefault("image_structures", []).append({
        "name": unique_image_name,
        "type": mime_type,
        "data": b64_data
    })

    _save_state()
    _write_rptdesign()

def reset_report():
    """Сбрасывает состояние отчета"""
    global _state
    _state = {
        "next_id": 1,
        "blocks": [],
        "image_structures": []
    }
    _save_state()
    with open(RPTDESIGN_PATH, "w", encoding="utf-8") as f:
        f.write(HEADER_TEMPLATE.format(description=_get_header_description()) + BODY_CLOSE_TAG + REPORT_CLOSE_TAG)
    print("Отчет сброшен")

def finalize_and_send_report():
    """Финальная обработка и отправка отчета"""
    _write_rptdesign()
    success = send_report_to_api()
    
    if success:
        print("Отчет успешно сформирован и отправлен")
    else:
        print("Ошибка при отправке отчета")
    
    return success

# Инициализация
if not os.path.exists(STATE_PATH):
    _ensure_state_loaded()
    _write_rptdesign()


    