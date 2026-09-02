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
    """Отправка запроса importBinaryPlugin с подробным логированием"""
    url = "https://adm.rkd.on-dev.ru/report_rkd/PluginsWS/importBinaryPlugin"
    
    # Первая часть тела - аутентификация
    auth_data = {
        "userName": API_CONFIG["username"],
        "password": API_CONFIG["password"],
        "clientIPAddress": "",
        "initiator": "Consumer web client 1.20.15"
    }
    
    # Вторая часть тела - данные плагина с fileBinary внутри
    file_bytes = [ord(char) for char in report_content]

    plugin_data = {
        "name": report_name,
        "mainClass": "birt.rptdesign",
        "version": "1.0",
        "versionDate": "September 17, 2025 12:00:00 AM",
        "fileBinary": file_bytes  # Прямой массив байтов
    }
    
    # Собираем полное тело запроса
    request_body = [auth_data, plugin_data]
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    
    # ВЫВОД СТРУКТУРЫ JSON КОТОРАЯ БУДЕТ ХРАНИТЬСЯ НА СЕРВЕРЕ
    print("=== JSON СТРУКТУРА ДЛЯ СЕРВЕРА ===")
    
    # Для вывода ограничиваем количество байтов для читаемости
    display_body = [
        auth_data.copy(),
        {
            **plugin_data.copy(),
            "fileBinary": file_bytes[:100]  # Показываем только первые 100 байтов для читаемости
        }
    ]
    
    print(json.dumps(display_body, ensure_ascii=False, indent=2))
    print(f"... и еще {len(file_bytes) - 100} байтов" if len(file_bytes) > 100 else "")
    print("=" * 60)
    
    try:
        response = requests.post(url, json=request_body, headers=headers, timeout=60)
        
        # Вывод ответа сервера
        print("=== ОТВЕТ СЕРВЕРА ===")
        print(f"Статус код: {response.status_code}")
        
        if response.status_code == 200:
            print("УСПЕШНЫЙ ОТВЕТ:")
            try:
                if "application/json" in response.headers.get('content-type', ''):
                    json_response = response.json()
                    print(json.dumps(json_response, ensure_ascii=False, indent=2))
                else:
                    print(response.text)
            except:
                print(response.text[:2000])
        else:
            print("ОШИБКА СЕРВЕРА:")
            print(response.text)
            
        print("=" * 60)
        
        response.raise_for_status()
        
        if "application/json" in response.headers.get('content-type', ''):
            return response.json()
        else:
            return response.text
            
    except requests.exceptions.Timeout:
        print("ТАЙМАУТ: Сервер не ответил в течение 60 секунд")
        return None
    except requests.exceptions.RequestException as e:
        print(f"ОШИБКА ПРИ ОТПРАВКЕ: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Статус ошибки: {e.response.status_code}")
        return None
    except Exception as e:
        print(f"НЕОЖИДАННАЯ ОШИБКА: {e}")
        return None
    
# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """Отправка запроса importBinaryPlugin с подробным логированием"""
#     url = "https://adm.rkd.on-dev.ru/report_rkd/PluginsWS/importBinaryPlugin"
    
#     # Первая часть тела - аутентификация
#     auth_data = {
#         "userName": API_CONFIG["username"],
#         "password": API_CONFIG["password"],
#         "clientIPAddress": "",
#         "initiator": "Consumer web client 1.20.13"
#     }
    
#     # Вторая часть тела - данные плагина
#     plugin_data = {
#         "name": report_name,
#         "mainClass": "birt.rptdesign",
#         "version": "1.0",
#         "versionDate": "2022-07-14T21:00:00Z",
#         "type": "Отчеты BIRT"
#     }
    
#     # Третья часть - содержимое файла в виде массива байтов
#     file_bytes = [ord(char) for char in report_content]
    
#     # Собираем полное тело запроса
#     request_body = [auth_data, plugin_data, file_bytes]
#     print(request_body)
    
#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json",
#     }
    
#     # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - что отправляется
#     print("=" * 80)
#     print("=== ДЕТАЛИ ОТПРАВЛЯЕМОГО ЗАПРОСА ===")
#     print("=" * 80)
#     print(f"URL: {url}")
#     print(f"Headers: {headers}")
#     print("\n--- ТЕЛО ЗАПРОСА (request_body) ---")
#     print(f"Тип: {type(request_body)}")
#     print(f"Длина массива: {len(request_body)} элементов")
    
#     print("\n[0] AUTH_DATA:")
#     print(f"   {auth_data}")
    
#     print("\n[1] PLUGIN_DATA:")
#     print(f"   {plugin_data}")
    
#     print("\n[2] FILE_BYTES:")
#     print(f"   Тип: {type(file_bytes)}")
#     print(f"   Длина массива: {len(file_bytes)} байтов")
#     print(f"   Первые 50 байтов: {file_bytes[:50]}")
#     print(f"   Последние 50 байтов: {file_bytes[-50:]}")
    
#     # Логируем размер данных
#     total_size = len(str(request_body))
#     print(f"\nОБЩИЙ РАЗМЕР ДАННЫХ: ~{total_size} символов")
    
#     # Преобразуем в JSON для просмотра структуры (ограничим размер для вывода)
#     import json
#     try:
#         # Создаем копию для логирования без полного file_bytes
#         log_body = [auth_data.copy(), plugin_data.copy(), {"file_bytes_size": (file_bytes)}]
#         json_str = json.dumps(log_body, ensure_ascii=False, indent=2)
#         print("\n--- СТРУКТУРА JSON ---")
#         print(json_str[:2000] + "..." if len(json_str) > 2000 else json_str)
#     except Exception as e:
#         print(f"Ошибка при сериализации JSON для логирования: {e}")
    
#     print("=" * 80)
    
#     try:
#         print("Отправка запроса...")
#         response = requests.post(url, json=request_body, headers=headers, timeout=60)
        
#         # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - что пришло в ответ
#         print("\n" + "=" * 80)
#         print("=== ОТВЕТ СЕРВЕРА ===")
#         print("=" * 80)
#         print(f"Статус код: {response.status_code}")
#         print(f"URL: {response.url}")
#         print(f"Headers ответа: {dict(response.headers)}")
        
#         print("\n--- ТЕЛО ОТВЕТА ---")
#         print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
#         print(f"Длина ответа: {len(response.text)} символов")
        
#         # Выводим полный ответ для анализа
#         if response.status_code == 200:
#             print("УСПЕШНЫЙ ОТВЕТ:")
#             try:
#                 if "application/json" in response.headers.get('content-type', ''):
#                     json_response = response.json()
#                     print(json.dumps(json_response, ensure_ascii=False, indent=2))
#                 else:
#                     print(response.text)
#             except:
#                 print(response.text[:5000])  # Ограничиваем вывод
#         else:
#             print("ОШИБКА СЕРВЕРА:")
#             print(response.text)  # Выводим полный текст ошибки
            
#         print("=" * 80)
        
#         response.raise_for_status()
        
#         # Обрабатываем успешный ответ
#         if "application/json" in response.headers.get('content-type', ''):
#             return response.json()
#         else:
#             return response.text
            
#     except requests.exceptions.Timeout:
#         print("ТАЙМАУТ: Сервер не ответил в течение 60 секунд")
#         return None
#     except requests.exceptions.RequestException as e:
#         print(f"ОШИБКА ПРИ ОТПРАВКЕ: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             print(f"Статус ошибки: {e.response.status_code}")
#             print(f"Текст ошибки: {e.response.text}")
#         return None
#     except Exception as e:
#         print(f"НЕОЖИДАННАЯ ОШИБКА: {e}")
#         return None 
    
    
    
#исправить массив на строку(два блока) - здес ПОЧТИ ТО ЧТО НАДО!
# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """Отправка запроса importBinaryPlugin с подробным логированием"""
#     url = "https://adm.rkd.on-dev.ru/report_rkd/PluginsWS/importBinaryPlugin"
    
#     # Первая часть тела - аутентификация
#     auth_data = {
#         "userName": API_CONFIG["username"],
#         "password": API_CONFIG["password"],
#         "clientIPAddress": "",
#         "initiator": "Consumer web client 1.20.15"  # Обновлено до 1.20.15
#     }
    
#     # Вторая часть тела - данные плагина с fileBinary внутри
#     file_bytes = [ord(char) for char in report_content]

    
#     plugin_data = {
#         "name": report_name,
#         "mainClass": "birt.rptdesign",  # Исправлено согласно примеру
#         "version": "1.0",
#         "versionDate": "September 17, 2025 12:00:00 AM",  # Исправлено согласно примеру
#         "fileBinary": file_bytes  # Байты внутри объекта, а не отдельным элементом
#     }
    
#     # Собираем полное тело запроса - теперь только 2 элемента!
#     request_body = [auth_data, plugin_data]
#     print(request_body)
    
#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json",
#     }
    
#     # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - что отправляется
#     print("=" * 80)
#     print("=== ДЕТАЛИ ОТПРАВЛЯЕМОГО ЗАПРОСА ===")
#     print("=" * 80)
#     print(f"URL: {url}")
#     print(f"Headers: {headers}")
#     print("\n--- СТРУКТУРА PAYLOAD (что будет храниться на сервере) ---")
#     print(f"Тип: {type(request_body)}")
#     print(f"Длина массива: {len(request_body)} элементов")
    
#     print("\n[0] AUTH_DATA:")
#     print(f"   {json.dumps(auth_data, ensure_ascii=False, indent=4)}")
    
#     print("\n[1] PLUGIN_DATA (с fileBinary внутри):")
#     # Для логирования создаем копию без полного массива байтов
#     plugin_data_log = plugin_data.copy()
#     plugin_data_log["fileBinary"] = f"<массив из {len(file_bytes)} байтов>"
#     print(f"   {json.dumps(plugin_data_log, ensure_ascii=False, indent=4)}")
    
#     print("\n--- ДЕТАЛИ FILEBINARY ---")
#     print(f"   Тип: {type(file_bytes)}")
#     print(f"   Длина массива: {len(file_bytes)} байтов")
#     print(f"   Первые 50 байтов: {file_bytes[:50]}")
#     print(f"   Последние 50 байтов: {file_bytes[-50:]}")
    
#     # Полная структура payload для просмотра
#     print("\n--- ПОЛНАЯ СТРУКТУРА PAYLOAD (ограниченный вывод) ---")
#     payload_for_log = [
#         auth_data,
#         {
#             **plugin_data,
#             "fileBinary": f"<массив из {len(file_bytes)} байтов: {file_bytes[:100]}...>" if len(file_bytes) > 100 else file_bytes
#         }
#     ]
#     print(json.dumps(payload_for_log, ensure_ascii=False, indent=2)[:3000] + "..." if len(str(payload_for_log)) > 3000 else json.dumps(payload_for_log, ensure_ascii=False, indent=2))
    
#     # Логируем размер данных
#     total_size = len(str(request_body))
#     print(f"\nОБЩИЙ РАЗМЕР ДАННЫХ: ~{total_size} символов")
#     print("=" * 80)
    
#     try:
#         print("Отправка запроса...")
#         response = requests.post(url, json=request_body, headers=headers, timeout=60)
        
#         # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - ответ сервера
#         print("\n" + "=" * 80)
#         print("=== ОТВЕТ СЕРВЕРА ===")
#         print("=" * 80)
#         print(f"Статус код: {response.status_code}")
#         print(f"URL: {response.url}")
#         print(f"Headers ответа: {dict(response.headers)}")
        
#         print("\n--- ТЕЛО ОТВЕТА ---")
#         print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
#         print(f"Длина ответа: {len(response.text)} символов")
        
#         # Анализируем ответ сервера
#         if response.status_code == 200:
#             print(" УСПЕШНЫЙ ОТВЕТ:")
#             try:
#                 if "application/json" in response.headers.get('content-type', ''):
#                     json_response = response.json()
#                     print("Структура ответа:")
#                     print(json.dumps(json_response, ensure_ascii=False, indent=2))
                    
#                     # Анализируем что вернул сервер о сохраненных данных
#                     print("\n--- ИНФОРМАЦИЯ О СОХРАНЕННЫХ ДАННЫХ НА СЕРВЕРЕ ---")
#                     if isinstance(json_response, dict):
#                         if 'pluginId' in json_response:
#                             print(f" ID сохраненного плагина: {json_response['pluginId']}")
#                         if 'status' in json_response:
#                             print(f" Статус операции: {json_response['status']}")
#                         if 'message' in json_response:
#                             print(f" Сообщение сервера: {json_response['message']}")
#                 else:
#                     print("Текстовый ответ:")
#                     print(response.text[:5000])
#             except Exception as json_error:
#                 print(f"Ошибка парсинга JSON: {json_error}")
#                 print("Сырой ответ:")
#                 print(response.text[:5000])
#         else:
#             print(" ОШИБКА СЕРВЕРА:")
#             print(f"Статус: {response.status_code} - {response.reason}")
#             print("Текст ошибки:")
#             print(response.text)
            
#             # Пытаемся распарсить ошибку
#             try:
#                 error_json = response.json()
#                 print("Структура ошибки:")
#                 print(json.dumps(error_json, ensure_ascii=False, indent=2))
#             except:
#                 pass
            
#         print("=" * 80)
        
#         response.raise_for_status()
        
#         # Обрабатываем успешный ответ
#         if "application/json" in response.headers.get('content-type', ''):
#             return response.json()
#         else:
#             return response.text
            
#     except requests.exceptions.Timeout:
#         print(" ТАЙМАУТ: Сервер не ответил в течение 60 секунд")
#         return None
#     except requests.exceptions.RequestException as e:
#         print(f" ОШИБКА ПРИ ОТПРАВКЕ: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             print(f"Статус ошибки: {e.response.status_code}")
#             print(f"Текст ошибки: {e.response.text}")
#         return None
#     except Exception as e:
#         print(f" НЕОЖИДАННАЯ ОШИБКА: {e}")
#         return None

# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """Отправка запроса importBinaryPlugin с подробным логированием"""
#     url = "https://adm.rkd.on-dev.ru/report_rkd/PluginsWS/importBinaryPlugin"
    
#     # Первая часть тела - аутентификация
#     auth_data = {
#         "userName": API_CONFIG["username"],
#         "password": API_CONFIG["password"],
#         "clientIPAddress": "",
#         "initiator": "Consumer web client 1.20.13"
#     }
    
#     # Вторая часть тела - данные плагина
#     plugin_data = {
#         "name": report_name,
#         "mainClass": "birt.rptdesign",
#         "version": "1.0",
#         "versionDate": "2022-07-14T21:00:00Z",
#         "type": "Отчеты BIRT"
#     }
    
#     # Третья часть - содержимое файла в виде массива байтов
#     file_bytes = [ord(char) for char in report_content]
    
#     # Собираем полное тело запроса
#     request_body = [auth_data, plugin_data, file_bytes]
    
#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json",
#     }
    
#     # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - что отправляется
#     print("=" * 80)
#     print("=== ДЕТАЛИ ОТПРАВЛЯЕМОГО ЗАПРОСА ===")
#     print("=" * 80)
#     print(f"URL: {url}")
#     print(f"Headers: {headers}")
#     print("\n--- ТЕЛО ЗАПРОСА (request_body) ---")
#     print(f"Тип: {type(request_body)}")
#     print(f"Длина массива: {len(request_body)} элементов")
    
#     print("\n[0] AUTH_DATA:")
#     print(f"   {auth_data}")
    
#     print("\n[1] PLUGIN_DATA:")
#     print(f"   {plugin_data}")
    
#     print("\n[2] FILE_BYTES:")
#     print(f"   Тип: {type(file_bytes)}")
#     print(f"   Длина массива: {len(file_bytes)} байтов")
#     print(f"   Первые 50 байтов: {file_bytes[:50]}")
#     print(f"   Последние 50 байтов: {file_bytes[-50:]}")
    
#     # Логируем размер данных
#     total_size = len(str(request_body))
#     print(f"\nОБЩИЙ РАЗМЕР ДАННЫХ: ~{total_size} символов")
    
#     # Преобразуем в JSON для просмотра структуры (ограничим размер для вывода)
#     import json
#     try:
#         # Создаем копию для логирования без полного file_bytes
#         log_body = [auth_data.copy(), plugin_data.copy(), {"file_bytes_size": len(file_bytes)}]
#         json_str = json.dumps(log_body, ensure_ascii=False, indent=2)
#         print("\n--- СТРУКТУРА JSON ---")
#         print(json_str[:2000] + "..." if len(json_str) > 2000 else json_str)
#     except Exception as e:
#         print(f"Ошибка при сериализации JSON для логирования: {e}")
    
#     print("=" * 80)
    
#     try:
#         print("Отправка запроса...")
#         response = requests.post(url, json=request_body, headers=headers, timeout=60)
        
#         # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - что пришло в ответ
#         print("\n" + "=" * 80)
#         print("=== ОТВЕТ СЕРВЕРА ===")
#         print("=" * 80)
#         print(f"Статус код: {response.status_code}")
#         print(f"URL: {response.url}")
#         print(f"Headers ответа: {dict(response.headers)}")
        
#         print("\n--- ТЕЛО ОТВЕТА ---")
#         print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
#         print(f"Длина ответа: {len(response.text)} символов")
        
#         # Выводим полный ответ для анализа
#         if response.status_code == 200:
#             print("УСПЕШНЫЙ ОТВЕТ:")
#             try:
#                 if "application/json" in response.headers.get('content-type', ''):
#                     json_response = response.json()
#                     print(json.dumps(json_response, ensure_ascii=False, indent=2))
#                 else:
#                     print(response.text)
#             except:
#                 print(response.text[:5000])  # Ограничиваем вывод
#         else:
#             print("ОШИБКА СЕРВЕРА:")
#             print(response.text)  # Выводим полный текст ошибки
            
#         print("=" * 80)
        
#         response.raise_for_status()
        
#         # Обрабатываем успешный ответ
#         if "application/json" in response.headers.get('content-type', ''):
#             return response.json()
#         else:
#             return response.text
            
#     except requests.exceptions.Timeout:
#         print("ТАЙМАУТ: Сервер не ответил в течение 60 секунд")
#         return None
#     except requests.exceptions.RequestException as e:
#         print(f"ОШИБКА ПРИ ОТПРАВКЕ: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             print(f"Статус ошибки: {e.response.status_code}")
#             print(f"Текст ошибки: {e.response.text}")
#         return None
#     except Exception as e:
#         print(f"НЕОЖИДАННАЯ ОШИБКА: {e}")
#         return None 
    
    
#     ##############################################################################################################!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Норм но не совсем тот формат  - нужный формат но не принимается сервером ошибка 500 
# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """Отправка запроса importBinaryPlugin с подробным логированием"""
#     url = "https://adm.rkd.on-dev.ru/report_rkd/PluginsWS/importBinaryPlugin"
    
#     # Первая часть тела - аутентификация
#     auth_data = {
#         "userName": API_CONFIG["username"],
#         "password": API_CONFIG["password"],
#         "clientIPAddress": "",
#         "initiator": "Consumer web client 1.20.13"
#     }
#      # Третья часть - содержимое файла в виде массива байтов
#     file_bytes = [ord(char) for char in report_content]
    
    
#     # Вторая часть тела - данные плагина
#     plugin_data = {
#         "name": report_name,
#         "mainClass": "birt.rptdesign",
#         "version": "1.0",
#         "versionDate": "2022-07-14T21:00:00Z",
#         "type": "Отчеты BIRT",
#         "fileBinary": file_bytes
          
#     }
    
    
#     # Собираем полное тело запроса
#     request_body = [auth_data, plugin_data]
    
#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json",
#     }
    
#     # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - что отправляется
#     print("=" * 80)
#     print("=== ДЕТАЛИ ОТПРАВЛЯЕМОГО ЗАПРОСА ===")
#     print("=" * 80)
#     print(f"URL: {url}")
#     print(f"Headers: {headers}")
#     print("\n--- ТЕЛО ЗАПРОСА (request_body) ---")
#     print(f"Тип: {type(request_body)}")
#     print(f"Длина массива: {len(request_body)} элементов")
    
#     print("\n[0] AUTH_DATA:")
#     print(f"   {auth_data}")
    
#     print("\n[1] PLUGIN_DATA:")
#     print(f"   {plugin_data}")
    
#     print("\n[2] FILE_BYTES:")
#     print(f"   Тип: {type(file_bytes)}")
#     print(f"   Длина массива: {len(file_bytes)} байтов")
#     print(f"   Первые 50 байтов: {file_bytes[:50]}")
#     print(f"   Последние 50 байтов: {file_bytes[-50:]}")
    
#     # Логируем размер данных
#     total_size = len(str(request_body))
#     print(f"\nОБЩИЙ РАЗМЕР ДАННЫХ: ~{total_size} символов")
    
#     # Преобразуем в JSON для просмотра структуры (ограничим размер для вывода)
#     import json
#     try:
#         # Создаем копию для логирования без полного file_bytes
#         log_body = [auth_data.copy(), plugin_data.copy(), {"file_bytes_size": len(file_bytes)}]
#         json_str = json.dumps(log_body, ensure_ascii=False, indent=2)
#         print("\n--- СТРУКТУРА JSON ---")
#         print(json_str[:2000] + "..." if len(json_str) > 2000 else json_str)
#     except Exception as e:
#         print(f"Ошибка при сериализации JSON для логирования: {e}")
    
#     print("=" * 80)
    
#     try:
#         print("Отправка запроса...")
#         response = requests.post(url, json=request_body, headers=headers, timeout=60)
        
#         # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ - что пришло в ответ
#         print("\n" + "=" * 80)
#         print("=== ОТВЕТ СЕРВЕРА ===")
#         print("=" * 80)
#         print(f"Статус код: {response.status_code}")
#         print(f"URL: {response.url}")
#         print(f"Headers ответа: {dict(response.headers)}")
        
#         print("\n--- ТЕЛО ОТВЕТА ---")
#         print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
#         print(f"Длина ответа: {len(response.text)} символов")
        
#         # Выводим полный ответ для анализа
#         if response.status_code == 200:
#             print("УСПЕШНЫЙ ОТВЕТ:")
#             try:
#                 if "application/json" in response.headers.get('content-type', ''):
#                     json_response = response.json()
#                     print(json.dumps(json_response, ensure_ascii=False, indent=2))
#                 else:
#                     print(response.text)
#             except:
#                 print(response.text[:5000])  # Ограничиваем вывод
#         else:
#             print("ОШИБКА СЕРВЕРА:")
#             print(response.text)  # Выводим полный текст ошибки
            
#         print("=" * 80)
        
#         response.raise_for_status()
        
#         # Обрабатываем успешный ответ
#         if "application/json" in response.headers.get('content-type', ''):
#             return response.json()
#         else:
#             return response.text
            
#     except requests.exceptions.Timeout:
#         print("ТАЙМАУТ: Сервер не ответил в течение 60 секунд")
#         return None
#     except requests.exceptions.RequestException as e:
#         print(f"ОШИБКА ПРИ ОТПРАВКЕ: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             print(f"Статус ошибки: {e.response.status_code}")
#             print(f"Текст ошибки: {e.response.text}")
#         return None
#     except Exception as e:
#         print(f"НЕОЖИДАННАЯ ОШИБКА: {e}")
#         return None

# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """
#     importBinaryPlugin c fileBinary в base64, без огромного массива чисел.
#     Функция последовательно пробует несколько форматов тела, потому что бэкенды
#     на Gson часто ожидают разные схемы:
#       A) [ auth, { ... , "fileBinary": "<base64>" } ]
#       B) [ auth, { ... }, "<base64>" ]      # fileBinary отдельным 3-м элементом
#       C) [ auth, { ... , "fileBinaryBase64": "<base64>" } ]  # альтернативное поле

#     На первой 2xx-ответе возвращает результат.
#     """

#     import base64
#     import json
#     from datetime import datetime
#     import requests

#     def _version_date_en(dt: datetime) -> str:
#         # Формат как в твоём эталоне: "September 17, 2025 12:00:00 AM"
#         months = [
#             "January","February","March","April","May","June",
#             "July","August","September","October","November","December"
#         ]
#         # без ведущего нуля у дня
#         return f"{months[dt.month - 1]} {dt.day}, {dt.year} 12:00:00 AM"

#     base_url = API_CONFIG.get("base_url", "https://adm.rkd.on-dev.ru").rstrip("/")
#     url = f"{base_url}/report_rkd/PluginsWS/importBinaryPlugin"

#     # Готовим base64 из XML
#     xml_bytes = report_content.encode("utf-8")
#     file_b64 = base64.b64encode(xml_bytes).decode("ascii")

#     # auth-часть всегда первая
#     auth = {
#         "userName": API_CONFIG["username"],
#         "password": API_CONFIG["password"],
#         "clientIPAddress": "",
#         "initiator": "Consumer web client 1.20.15",
#     }

    # metadata плагина (mainClass = имя основного файла)
    # Если у вас реально используется вариант с пробелами в имени файла,
    # можно подставить "birt (3).rptdesign"
#     main_filename = "birt.rptdesign"
#     plugin_common = {
#         "name": report_name,
#         "mainClass": main_filename,
#         "version": "1.0",
#         "versionDate": _version_date_en(datetime.now()),
#         # "type": "Отчеты BIRT",  # раскомментируй, если у бэка это обязательное поле
#     }

#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json; charset=utf-8",
#     }

#     attempts = [
#         ("A: fileBinary внутри второго объекта",
#          [auth, {**plugin_common, "fileBinary": file_b64}]),
#         ("B: base64 как третий элемент массива",
#          [auth, {**plugin_common}, file_b64]),
#         ("C: fileBinaryBase64 внутри второго объекта",
#          [auth, {**plugin_common, "fileBinaryBase64": file_b64}]),
#     ]

#     for label, body in attempts:
#         try:
#             print("=== ЗАПРОС importBinaryPlugin (JSON + base64) ===")
#             print(f"URL: {url}")
#             print(f"Report name: {report_name}")
#             print(f"Попытка: {label}")
#             # Короткий тех. лог, без вывода base64:
#             try:
#                 # безопасно покажем «форму» (ключи), но не значение base64
#                 body_preview = body
#                 if isinstance(body_preview, list) and len(body_preview) >= 2:
#                     b2 = body_preview[1]
#                     if isinstance(b2, dict) and "fileBinary" in b2:
#                         b2 = {**b2}
#                         b2["fileBinary"] = f"<base64 string of {len(file_b64)} chars>"
#                         body_preview = [body_preview[0], b2] + body_preview[2:]
#                     if isinstance(b2, dict) and "fileBinaryBase64" in b2:
#                         b2 = {**b2}
#                         b2["fileBinaryBase64"] = f"<base64 string of {len(file_b64)} chars>"
#                         body_preview = [body_preview[0], b2] + body_preview[2:]
#                 print("Body shape preview:", json.dumps(body_preview, ensure_ascii=False)[:800])
#             except Exception:
#                 pass
#             print("=" * 60)

#             resp = requests.post(url, json=body, headers=headers, timeout=300)
#             print(f"Статус ответа: {resp.status_code}")
#             ctype = resp.headers.get("Content-Type", "")
#             if resp.status_code >= 400:
#                 # Покажем фрагмент ответа для диагностики
#                 print("Ответ (фрагмент):", resp.text[:2000])

#             if 200 <= resp.status_code < 300:
#                 if "application/json" in ctype.lower():
#                     try:
#                         return resp.json()
#                     except Exception:
#                         return resp.text
#                 else:
#                     return resp.text

#             # если неуспех — пробуем следующий формат
#         except requests.exceptions.RequestException as e:
#             print(f"Ошибка при отправке (попытка {label}): {e}")
#             if getattr(e, "response", None) is not None:
#                 print(f"Статус: {e.response.status_code}")
#                 print(f"Ответ (фрагмент): {e.response.text[:2000]}")
#             # и идём к следующей попытке

#     # Ничего не взлетело
#     print("Все попытки importBinaryPlugin завершились ошибкой.")
#     return None


# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """
#     Отправка importBinaryPlugin с fileBinary = base64-строка.
#     """
#     import base64
#     import requests
#     from datetime import datetime

#     base_url = API_CONFIG.get("base_url", "https://adm.rkd.on-dev.ru").rstrip("/")
#     url = f"{base_url}/report_rkd/PluginsWS/importBinaryPlugin"

#     # Конвертируем xml в base64
#     binary_content = report_content.encode("utf-8")
#     file_b64 = base64.b64encode(binary_content).decode("ascii")

#     # формат даты — строго английский (September 24, 2025 12:00:00 AM)
#     def _version_date_en(dt: datetime) -> str:
#         months = [
#             "January", "February", "March", "April", "May", "June",
#             "July", "August", "September", "October", "November", "December"
#         ]
#         return f"{months[dt.month - 1]} {dt.day}, {dt.year} 12:00:00 AM"

#     auth = {
#         "userName": API_CONFIG["username"],
#         "password": API_CONFIG["password"],
#         "clientIPAddress": "",
#         "initiator": "Consumer web client 1.20.15",
#     }

#     plugin = {
#         "name": report_name,
#         "mainClass": "birt.rptdesign",
#         "version": "1.0",
#         "versionDate": _version_date_en(datetime.now()),
#         "fileBinary": file_b64,
#     }

#     body = [auth, plugin]

#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json",
#     }

#     print("=== ЗАПРОС importBinaryPlugin (JSON + base64) ===")
#     print(f"URL: {url}")
#     print(f"Report name: {report_name}")
#     print(f"fileBinary length: {len(file_b64)} chars (base64)")
#     print("=" * 60)

#     try:
#         resp = requests.post(url, json=body, headers=headers, timeout=300)
#         print(f"Статус ответа: {resp.status_code}")
#         print(f"Ответ (фрагмент): {resp.text[:500]}")
#         resp.raise_for_status()
#         if "application/json" in resp.headers.get("Content-Type", "").lower():
#             return resp.json()
#         return resp.text
#     except requests.exceptions.RequestException as e:
#         print(f"Ошибка при отправке: {e}")
#         if getattr(e, "response", None) is not None:
#             print(f"Статус: {e.response.status_code}")
#             print(f"Ответ: {e.response.text[:500]}")
#         return None

# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """
#     Упрощенная версия с прямой конвертацией в байты
#     """
#     base_url = API_CONFIG.get("base_url", "https://adm.rkd.on-dev.ru").rstrip("/")
#     url = f"{base_url}/report_rkd/PluginsWS/importBinaryPlugin"

#     # Конвертируем строку в байты и затем в массив чисел
#     binary_content = report_content.encode('utf-8')
#     file_bytes = list(binary_content)

#     # Если файл слишком большой, обрезаем для теста
#     if len(file_bytes) > 100000:
#         print(f"Файл слишком большой ({len(file_bytes)} bytes), обрезаем для теста")
#         file_bytes = file_bytes[:100000]

#     request_body = [
#         {
#             "userName": API_CONFIG["username"],
#             "password": API_CONFIG["password"],
#             "clientIPAddress": "",
#             "initiator": "Consumer web client 1.20.15"
#         },
#         {
#             "name": report_name,
#             "mainClass": "birt.rptdesign",
#             "version": "1.0",
#             "versionDate": date.today().strftime("%d.%m.%Y"),
#             "fileBinary": file_bytes
#         }
#     ]

#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json",
#     }

#     print("=== ЗАПРОС importBinaryPlugin ===")
#     print(f"URL: {url}")
#     print(f"File bytes: {file_bytes}")
#     print("=" * 60)

#     try:
#         resp = requests.post(url, json=request_body, headers=headers, timeout=120)
#         print(f"Статус ответа: {resp.status_code}")
#         print(f"Ответ: {resp.text}")
#         resp.raise_for_status()
#         return resp.json()

#     except requests.exceptions.RequestException as e:
#         print(f"Ошибка при отправке: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             print(f"Статус: {e.response.status_code}")
#             print(f"Ответ: {e.response.text}")
#         return None
    
    
# def _send_import_binary_plugin(report_name: str, report_content: str):
#     """
#     Отправка importBinaryPlugin в формате JSON с fileBinary = массив байт.
#     """

#     # конвертируем весь xml в массив байт
#     file_bytes = list(report_content.encode("utf-8"))


#     base_url = API_CONFIG.get("base_url", "https://adm.rkd.on-dev.ru").rstrip("/")
#     url = f"{base_url}/report_rkd/PluginsWS/importBinaryPlugin"

#     auth = {
#         "userName": API_CONFIG["username"],
#         "password": API_CONFIG["password"],
#         "clientIPAddress": "",
#         "initiator": "Consumer web client 1.20.15",
#     }

#     plugin = {
#         "name": report_name,
#         "mainClass": "birt.rptdesign",   # или "birt (3).rptdesign", если так нужно
#         "version": "1.0",
#         "versionDate": _version_date_en(datetime.now()),
#         "fileBinary": file_bytes,
#     }

#     body = [auth, plugin]

#     headers = {
#         "accept": "application/json",
#         "content-type": "application/json",
#     }

#     print("=== ЗАПРОС importBinaryPlugin (JSON + байты) ===")
#     print(f"URL: {url}")
#     print(f"Report name: {report_name}")
#     print(f"fileBinary: {(file_bytes)}")
#     print("=" * 60)

#     try:
#         resp = requests.post(url, json=body, headers=headers, timeout=300)
#         print(f"Статус ответа: {resp.status_code}")
#         print(f"Ответ (фрагмент): {resp.text[:1000]}")
#         resp.raise_for_status()
#         return resp.json()
#     except requests.exceptions.RequestException as e:
#         print(f"Ошибка при отправке: {e}")
#         if getattr(e, "response", None) is not None:
#             print(f"Статус: {e.response.status_code}")
#             print(f"Ответ: {e.response.text[:1000]}")
#         return None

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

def _send_ui_module_save(report_name: str):
    """Отправка запроса UIModuleWS/save"""
    url = "https://adm.rkd.on-dev.ru/report_rkd/UIModuleWS/save"
    
    # Первая часть тела - аутентификация
    auth_data = {
        "userName": API_CONFIG["username"],
        "password": API_CONFIG["password"],
        "clientIPAddress": "",
        "initiator": "Consumer web client 1.20.15"
    }
    
    # Вторая часть тела - данные модуля UI
    module_data = {
        "name": report_name,
        "description": report_name,
        "groupName": "report module",
        "type": 2,
        "className": report_name,
        "keyView": ""
    }
    
    # Собираем полное тело запроса
    request_body = [auth_data, module_data]
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    
    try:
        response = requests.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке UIModuleWS/save: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Статус: {e.response.status_code}")
            print(f"Ответ: {e.response.text}")
        return None
    
def _send_set_report_for_user_list(user_list: list, report_id: int):
    """Отправка запроса setReport4UserList"""
    url = "https://adm.rkd.on-dev.ru/template_rkd/ReportMethodWS/setReport4UserList"
    
    # Первая часть тела - аутентификация
    auth_data = {
        "userName": API_CONFIG["username"],
        "password": API_CONFIG["password"],
        "clientIPAddress": "",
        "initiator": "Consumer web client 1.20.15"
    }
    
    # Собираем полное тело запроса (третьим элементом - report_id)
    request_body = [auth_data, user_list, report_id]
    
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    
    try:
        response = requests.post(url, json=request_body, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при отправке setReport4UserList: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Статус: {e.response.status_code}")
            print(f"Ответ: {e.response.text}")
        return None

def send_report_to_api(user_list: list = None):
    """Отправляет отчет через API"""
    if not os.path.exists(RPTDESIGN_PATH):
        print("Ошибка: Файл отчета не найден")
        return False
    
    report_name = _generate_report_name()
    
    try:
        # Читаем файл в бинарном режиме
        with open(RPTDESIGN_PATH, "rb") as f:
            binary_content = f.read()
        
        # Конвертируем в строку для обработки
        report_content = binary_content.decode('utf-8')
        
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
        
        # Извлекаем report_id из ответа save
        report_id = None
        if isinstance(save_result, list) and len(save_result) > 0:
            # Предполагаем, что report_id находится в первом элементе ответа
            report_id = save_result[0]
        elif isinstance(save_result, dict) and 'id' in save_result:
            report_id = save_result['id']
        
        if not report_id:
            print("Не удалось извлечь report_id из ответа save")
            return False
        
        print(f"Отправка UIModuleWS/save для {report_name}...")
        ui_module_result = _send_ui_module_save(report_name)
        
        if not ui_module_result:
            print("Ошибка при сохранении UI модуля")
            return False
        
        # Если передан список пользователей, отправляем запрос setReport4UserList
        if user_list:
            print(f"Отправка setReport4UserList для report_id {report_id}...")
            set_report_result = _send_set_report_for_user_list(user_list, report_id)
            
            if not set_report_result:
                print("Ошибка при настройке прав доступа для пользователей")
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

def finalize_and_send_report(user_list: list = None):
    """Финальная обработка и отправка отчета"""
    _write_rptdesign()
    success = send_report_to_api(user_list)
    
    if success:
        print("Отчет успешно сформирован и отправлен")
    else:
        print("Ошибка при отправке отчета")
    
    return success

# Инициализация
if not os.path.exists(STATE_PATH):
    _ensure_state_loaded()
    _write_rptdesign()