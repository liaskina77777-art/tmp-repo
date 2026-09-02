import asyncio
import aiohttp
import aiofiles
import json
import time
import uuid
import httpx
import subprocess
import os
from pathlib import Path
from typing import Any


BASE_HOST = "https://rkd.sa.on-dev.ru"
END_UPLOAD_FILE = f"{BASE_HOST}/api/repositoryrestful/upload/file?name={{name}}"
END_GET_URL_FOR_DOWNLOAD = f"{BASE_HOST}/api/repository/SecurityWS/getURLForDownload"
END_SAVE_TO_REGISTRY = f"{BASE_HOST}/api/repository/InformationObject4StorageWS/save"


class RuntimeConfig:
    def __init__(self):
        self.sso_uri = "https://sso.sa.on-dev.ru/sso-ws"
        self.client_id = "Notification"
        self.client_secret = "a73bb0b6-1331-4512-8980-5f88eebf6297"

runtime_config = RuntimeConfig()

# данные структуры для записи в реестр
PARTITION_DATA = {
    "parentId": None,
    "name": "Результаты исполнения моделей",
    "count": 0,
    "usersGroup": {
        "isRole": 0,
        "id": 5,
        "name": "ReadOnly Access",
        "type": 1,
        "createdById": 1,
        "createdDateTime": "Apr 16, 2021 3:24:56 PM",
        "changedById": 20261,
        "changedDateTime": "Sep 26, 2025 3:14:16 PM",
        "isDeleted": 0,
        "_$c$_": "ru.infor.ws.objects.core.entities.UsersGroup"
    },
    "path": "Результаты исполнения моделей",
    "id": 2336847,
    "isDeleted": 0,
    "_$c$_": "ru.infor.ws.objects.repository.entities.PartitionData"
}

STORAGE_OBJECT_TYPE = {
    "id": 104909,
    "code": "01",
    "description": "файл",
    "isDeleted": 0,
    "_$c$_": "ru.infor.ws.objects.repository.entities.StorageObjectType"
}

sso_api = None

async def get_token(login, passhash):
    #Получение токена из SSO
    global sso_api
    
    if not sso_api:
        sso_api = httpx.AsyncClient(
            base_url=runtime_config.sso_uri,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
    
    try:
        response = await sso_api.post(
            "/auth/openid-connect/token",
            data={
                "grant_type": "native_login",
                "client_id": runtime_config.client_id,
                "client_secret": runtime_config.client_secret,
                "login": login,
                "password": passhash
            }
        )
        response.raise_for_status()
        return response.json()["access_token"]
    finally:
        await sso_api.aclose()
        sso_api = None

async def _read_bytes(path: Path) -> bytes:
    # читаем файл как бинарные данные
    async with aiofiles.open(path, "rb") as f:
        return await f.read()

def _safe_json_dump(obj: Any) -> str:
    # преобразование в JSON
    return json.dumps(obj, ensure_ascii=False)

async def _post_with_token(session: aiohttp.ClientSession, url: str, data: Any, token: str) -> aiohttp.ClientResponse:
    # Отправляем POST запрос с данными как текст и токеном в Authorization header
    json_str = _safe_json_dump(data)
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {token}'
    }
    
    # ЛОГИРОВАНИЕ ТЕЛА ЗАПРОСА
    print(f"[DEBUG] === ЗАПРОС К {url} ===")
    print(f"[DEBUG] Заголовки: {headers}")
    print(f"[DEBUG] Тело: {json_str}")
    
    response = await session.post(url, data=json_str, headers=headers)
    
    # логирование
    print(f"[DEBUG] === ОТВЕТ ОТ {url} ===")
    print(f"[DEBUG] Статус: {response.status}")
    try:
        response_body = await response.text()
        print(f"[DEBUG] Тело ответа: {response_body}")
    except Exception as e:
        print(f"[DEBUG] Не удалось прочитать тело ответа: {e}")
    print(f"[DEBUG] =====================")
    
    return response

async def _upload_single_file(session: aiohttp.ClientSession, file_path: Path, token: str) -> None:
    #Загружаем один файл любого формата на сервер с использованием токена
    
    # получаем оригинальное имя файла с расширением
    original_filename = file_path.name
    # создаем уникальное имя файла для сервера
    unique_id = str(uuid.uuid4())[:8]
    file_basename = f"{int(time.time())}_{unique_id}_{original_filename}"

    # читаем файл как бинарные данные
    try:
        file_bytes = await _read_bytes(file_path)
        print(f"[DEBUG] Прочитан файл {file_path}, размер: {len(file_bytes)} байт")
    except Exception as e:
        print(f"[ERROR] Не удалось прочитать файл {file_path}: {e}")
        return

    # POST запрос для загрузки файла
    try:
        upload_url = END_UPLOAD_FILE.format(name=file_basename)
        print(f"[DEBUG] Загрузка файла по URL: {upload_url}")
        print(f"[DEBUG] Размер файла: {len(file_bytes)} байт")
        print(f"[DEBUG] Имя файла: {file_basename}")
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/octet-stream'
        }
        
        async with session.post(upload_url, data=file_bytes, headers=headers) as upload_resp:
            # логирование
            print(f"[DEBUG] Статус ответа загрузки: {upload_resp.status}")
            if upload_resp.status not in (200, 201, 204):
                body = await upload_resp.text()
                print(f"[DEBUG] Тело ошибки: {body}")
            else:
                print(f"[DEBUG] Файл успешно загружен")
    except Exception as e:
        print(f"[ERROR] Загрузка файла не удалась: {e}")
        return

    # 2. Пробуем разные варианты получения URL для скачивания
    download_url = None
    
    # получаем URL через getURLForDownload с правильным форматом данных
    try:
        #  формат: [{}, "имя_файла"]
        download_payload = [{}, file_basename]
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        
        print(f"[DEBUG] Попытка 1: Отправка запроса getURLForDownload с данными: {download_payload}")
        
        async with session.put(END_GET_URL_FOR_DOWNLOAD, json=download_payload, headers=headers) as download_resp:
            if download_resp.status == 200:
                download_data = await download_resp.text()  # Изменено: читаем как текст, а не JSON
                print(f"[DEBUG] Ответ от getURLForDownload: {download_data}")
                
                # распарсим как JSON, если это возможно
                try:
                    parsed_data = json.loads(download_data)
                    if isinstance(parsed_data, dict):
                        download_url = parsed_data.get('url', '')
                    elif isinstance(parsed_data, list) and len(parsed_data) > 0:
                        if isinstance(parsed_data[0], dict):
                            download_url = parsed_data[0].get('url', '')
                        else:
                            download_url = parsed_data[0]  # Если это строка
                    else:
                        download_url = parsed_data  # Если это просто строка
                except json.JSONDecodeError:
                    # если ответ не JSON, используем его как есть
                    download_url = download_data
                
                if download_url:
                    print(f"[DEBUG] URL для скачивания получен: {download_url}")
                else:
                    print(f"[DEBUG] Не удалось извлечь URL из ответа")
    except Exception as e:
        print(f"[DEBUG] getURLForDownload не сработал: {e}")

    #  POST запрос для сохранения в реестр
    test_name = f"{original_filename}_{int(time.time())}"

    files_entry = [{
        "name": file_basename,
        "filename": download_url,
        "id": -1
    }]

    payload_to_save = {
        "objectSize": "0",
        "requestNum": "0",
        "downloadNum": "0",
        "timeDownloading": "0",
        "trackHistory": "1",
        "applicationArea": None,
        "files": files_entry,
        "name": test_name,
        "storageObjectType": STORAGE_OBJECT_TYPE,
        "partitionData": PARTITION_DATA
    }

    registry_body = [
        {},  
        payload_to_save
    ]

    try:
        resp = await _post_with_token(session, END_SAVE_TO_REGISTRY, registry_body, token)
        if resp.status != 200:
            text = await resp.text()
            print(f"[WARN] save to registry вернул статус {resp.status}: {text}")
        else:
            result_text = await resp.text()
            print(f"[INFO] Успешно сохранено: файл {original_filename}")
            print(f"[DEBUG] Ответ от save: {result_text}")
    except Exception as e:
        print(f"[ERROR] save to registry failed: {e}")
        return

async def _process_single_file(file_path: str, token: str) -> None:
    # обрабатываем один конкретный файл с использованием токена
    file_path_obj = Path(file_path)
    
    if not file_path_obj.exists():
        print(f"[ERROR] Файл не найден: {file_path}")
        return

    if not file_path_obj.is_file():
        print(f"[ERROR] Указанный путь не является файлом: {file_path}")
        return

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=300)
    ) as session:
        await _upload_single_file(session, file_path_obj, token)

async def _process_directory(directory_path: str, token: str) -> None:
    # обрабатываем все файлы с использованием токена
    dir_path_obj = Path(directory_path)
    
    if not dir_path_obj.exists():
        print(f"[ERROR] Директория не найдена: {directory_path}")
        return

    if not dir_path_obj.is_dir():
        print(f"[ERROR] Указанный путь не является директорией: {directory_path}")
        return

    # находим все файлы в директории 
    all_files = [f for f in dir_path_obj.rglob('*') if f.is_file()]
    
    if not all_files:
        print(f"[INFO] Не найдено файлов в директории {directory_path}")
        return

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=300)
    ) as session:
        tasks = []

        for file_path in all_files:
            tasks.append(_upload_single_file(session, file_path, token))

        print(f"[INFO] Найдено {len(tasks)} файлов для обработки в {directory_path}")
        await asyncio.gather(*tasks, return_exceptions=True)

async def _async_func(file_or_dir_path: str) -> None:
    # асинхронная реализация основной функции и получаем токен из SSO
    try:
        token = await get_token("admin", "9v3/5IyQjesPTDvTbAMucg==")
        print("[INFO] Токен успешно получен")
    except Exception as e:
        print(f"[ERROR] Не удалось получить токен: {str(e)}")
        return
    
    if not file_or_dir_path:
        file_or_dir_path = "."
    
    path_obj = Path(file_or_dir_path)
    
    if path_obj.is_file():
        print(f"[INFO] Обработка отдельного файла: {file_or_dir_path}")
        await _process_single_file(file_or_dir_path, token)
    elif path_obj.is_dir():
        print(f"[INFO] Обработка всех файлов в директории: {file_or_dir_path}")
        await _process_directory(file_or_dir_path, token)
    else:
        print(f"[ERROR] Указанный путь не существует: {file_or_dir_path}")

def saveToRepository(file_or_dir_path: str) -> None:
    # синхронная обертка для асинхронной функции
    return asyncio.run(_async_func(file_or_dir_path))

# новая функция для работы с gdal

async def _async_start_gdal(geojson_file_path: str, output_dir: str = "test/out_data") -> None:
    
    #асинхронная функция для выполнения ogr2ogr команды
    
    file_path = Path(geojson_file_path)
    
    # проверяем что файл существует и имеет правильное расширение
    if not file_path.exists():
        print(f"[ERROR] Файл не найден: {geojson_file_path}")
        return
    
    if file_path.suffix.lower() != '.geojson':
        print(f"[ERROR] Файл должен быть в формате GeoJSON: {geojson_file_path}")
        return
    
    # Параметры подключения к БД 
    db_params = {
        "dbname": "postgis",
        "user": "username", 
        "password": "password",
        "host": "10.10.10.106",
        "port": "5439"
    }
    
    # формируем строку подключения к PostgreSQL
    connection_string = f"PG:dbname={db_params['dbname']} user={db_params['user']} password={db_params['password']} host={db_params['host']} port={db_params['port']}"
    
    # формируем команду ogr2ogr
    cmd = [
        'ogr2ogr',
        '-f', 'PostgreSQL',
        connection_string,
        str(file_path),
        '-lco', 'GEOMETRY_NAME=geom',
        '-nln', f"table_{file_path.stem}",  
        '-overwrite'
    ]
    
    print(f"[INFO] Выполнение команды GDAL: {' '.join(cmd)}")
    
    try:
        # выполняем команду асинхронно
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print(f"[INFO] Успешно загружено в БД: {geojson_file_path}")
            if stdout:
                print(f"[DEBUG] stdout: {stdout.decode()}")
        else:
            print(f"[ERROR] Ошибка при загрузке в БД: {stderr.decode()}")
            
    except Exception as e:
        print(f"[ERROR] Ошибка выполнения GDAL команды: {e}")

def startGDAL(geojson_file_path: str, output_dir: str = "test/out_data") -> None:

    #синхронная обертка для асинхронной функции GDAL, Загружает GeoJSON файл в PostgreSQL/PostGIS базу данных
    
    return asyncio.run(_async_start_gdal(geojson_file_path, output_dir))

# альтернативная версия для работы с директорией
async def _async_process_geojson_directory(directory_path: str) -> None:
    """
    Обрабатывает все GeoJSON файлы в директории
    """
    dir_path = Path(directory_path)
    
    if not dir_path.exists() or not dir_path.is_dir():
        print(f"[ERROR] Директория не найдена: {directory_path}")
        return
    
    # Находим все GeoJSON файлы
    geojson_files = list(dir_path.rglob("*.geojson"))
    
    if not geojson_files:
        print(f"[INFO] GeoJSON файлы не найдены в директории: {directory_path}")
        return
    
    print(f"[INFO] Найдено {len(geojson_files)} GeoJSON файлов для обработки")
    
    # создаем задачи для каждого файла
    tasks = [_async_start_gdal(str(file_path)) for file_path in geojson_files]
    await asyncio.gather(*tasks, return_exceptions=True)

def processGeojsonDirectory(directory_path: str) -> None:
    
   # Синхронная обертка для обработки директории с GeoJSON файлами

    return asyncio.run(_async_process_geojson_directory(directory_path))