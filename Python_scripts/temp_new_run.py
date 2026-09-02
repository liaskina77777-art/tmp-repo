import os
import numpy as np
import rioxarray
import rasterio
import matplotlib.pyplot as plt
from rasterio.enums import Resampling
import xarray as xr
import gc
import ctypes
import time

# --- Пути к файлам ---
tir_path = r'C:\Users\User\Downloads\produser\devdata\produser1\2024-04-16-1830\ETRIS.ARCM1.2024-04-16T1830.L2.TIR_3857.tif'
water_mask_path = r'C:\Users\User\Downloads\produser\devdata\produser1\2024-04-16-1830\watermask_zoom5.tif'

# --- Динамическое формирование путей к выходным файлам ---
output_dir = os.path.dirname(tir_path)
base_filename = os.path.basename(tir_path)
clean_filename = base_filename.replace(".L2.TIR", ".L2").replace(".tif", "")
if "TIR_" in clean_filename:
    clean_filename = clean_filename.split("TIR_")[0] + clean_filename.split("TIR_")[1]
elif ".TIR" in clean_filename:
    clean_filename = clean_filename.replace(".TIR", "")

cloud_mask_output_path = os.path.join(output_dir, f"{clean_filename}_cloud_mask.tif")
temperature_output_path = os.path.join(output_dir, f"{clean_filename}_temperature.tif")

# --- Функции ---

def extract_satellite_name(tir_path: str) -> str:
    """Извлекает имя спутника из имени TIR-файла."""
    fname = os.path.basename(tir_path)
    parts = fname.split(".")
    for part in parts:
        if part.startswith("EL") or part.startswith("ARCM"):
            return part
    return "UNKNOWN"

def generate_cloud_mask(tir_data_tir5: np.ndarray, tir_data_tir6: np.ndarray,
                        tir5_lower_threshold: int = 278, 
                        tir5_upper_threshold: int = 290, # точно не облако
                        btd_threshold: float = 0.5,
                        very_cold_threshold: int = 250) -> np.ndarray:
    """
    Создает бинарную маску облаков.
    Вход: TIR5 и TIR6 каналы (температура в Кельвинах).
    Выход: Маска (0 - безоблачно, 1 - облачно).
    """
    cloud_mask = np.zeros_like(tir_data_tir5, dtype=np.uint8)
    not_cloud_due_to_warmth = tir_data_tir5 > tir5_upper_threshold
    btd = tir_data_tir5 - tir_data_tir6
    btd[np.isnan(tir_data_tir5) | np.isnan(tir_data_tir6)] = np.nan
    is_very_cold_cloud = tir_data_tir5 < very_cold_threshold
    is_cold_and_high_btd_cloud = (tir_data_tir5 < tir5_lower_threshold) & (np.abs(btd) > btd_threshold)
    cloud_mask = (is_very_cold_cloud | is_cold_and_high_btd_cloud) & (~not_cloud_due_to_warmth) # либо очень холодный либо с большой разностью температур и обязательно не слишном теплый
    cloud_mask[np.isnan(tir_data_tir5) | np.isnan(tir_data_tir6)] = 0
    return cloud_mask.astype(np.uint8)

def reproject_water_mask_to_tir(water_mask_path: str, tir_crs: rasterio.crs.CRS,
                                tir_transform: rasterio.Affine, tir_shape: tuple) -> np.ndarray:
    """
    Перепроецирует маску воды под геометрию TIR-файла.
    Работает корректно даже в ортографической проекции.
    Вход: путь к маске воды, CRS, transform и форма (H, W) TIR.
    Выход: бинарная маска (1 — вода, 0 — суша).
    """
    height, width = tir_shape

    # Целевая трансформация и CRS
    dst_transform = tir_transform
    dst_crs = tir_crs

    # Открываем исходную маску воды
    with rasterio.open(water_mask_path) as src:
        src_data = src.read(1, masked=False)
        src_nodata = src.nodata
        if src_nodata is not None:
            src_data = np.where(src_data == src_nodata, np.nan, src_data)

        # Определяем границы целевого изображения в его CRS
        dst_bounds = rasterio.transform.array_bounds(height, width, dst_transform)

        # Перепроецируем маску воды
        water_mask_reprojected, _ = rasterio.warp.reproject(
            source=src_data,
            destination=np.zeros((height, width), dtype=np.float32),
            src_transform=src.transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=dst_crs,
            dst_bounds=dst_bounds,
            resampling=rasterio.enums.Resampling.nearest,
            src_nodata=np.nan,
            dst_nodata=np.nan
        )

    # Создаём бинарную маску: 1 — вода (включая NaN), 0 — суша
    water_mask_binary = np.zeros((height, width), dtype=np.uint8)
    water_mask_binary[np.isnan(water_mask_reprojected)] = 1  # NoData → вода
    water_mask_binary[water_mask_reprojected == 1] = 1        # Явная вода

    return water_mask_binary


def save_mask(mask: np.ndarray, crs: rasterio.crs.CRS, transform: rasterio.Affine, path: str):
    """Сохраняет одноканальную маску в GeoTIFF."""
    profile = {
        "driver": "GTiff", "height": mask.shape[0], "width": mask.shape[1],
        "count": 1, "dtype": rasterio.uint8, "crs": crs, "transform": transform,
        "nodata": 0, "compress": "deflate", "tiled": True,
        "blockxsize": 256, "blockysize": 256
    }
    with rasterio.open(path, 'w', **profile) as dst:
        dst.write(mask, 1)
    print(f"Маска облаков сохранена: {path}")

def save_temperature(temperature_celsius: np.ndarray, crs: rasterio.crs.CRS, transform: rasterio.Affine, path: str):
    """Сохраняет трехканальный массив температуры в простой GeoTIFF (не COG)."""
    profile = {
        "driver": "GTiff", "dtype": "float32", "count": temperature_celsius.shape[0],
        "height": temperature_celsius.shape[1], "width": temperature_celsius.shape[2],
        "crs": crs, "transform": transform, "compress": "lzw",
        "tiled": True, "blockxsize": 256, "blockysize": 256, "nodata": np.nan
    }
    with rasterio.open(path, "w", **profile) as dst:
        for i in range(temperature_celsius.shape[0]):
            dst.write(temperature_celsius[i], i + 1)
    print(f"Итоговый файл температуры сохранен: {path}")

def visualize_mask(mask: np.ndarray, title: str, path: str):
    """Визуализирует маску и сохраняет ее в PNG."""
    plt.figure(figsize=(10, 8))
    plt.imshow(mask, cmap='gray')
    plt.title(title)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()

def visualize_temperature(temperature: np.ndarray, path: str, title: str = 'Температура SST/LST (°C)'):
    """Визуализирует массив температуры и сохраняет его в PNG."""
    plt.figure(figsize=(10, 8))
    valid_pixels = ~np.isnan(temperature)
    if np.any(valid_pixels):
        vmin = np.nanpercentile(temperature[valid_pixels], 2)
        vmax = np.nanpercentile(temperature[valid_pixels], 98)
        im = plt.imshow(temperature, cmap='inferno', vmin=vmin, vmax=vmax)
    else:
        im = plt.imshow(temperature, cmap='inferno')
    plt.colorbar(im, fraction=0.03, pad=0.04, label='Температура, °C')
    plt.title(title)
    plt.axis('off')
    plt.tight_layout()
    plt.savefig(path, dpi=200)
    plt.close()

def proc_temperature(file_tir_path: str, water_mask_path: str, cloud_mask_output_path: str):
    """
    Основная функция для обработки TIR-данных.
    Возвращает: temperature_result_celsius, crs, transform
    Сохранение файлов не происходит внутри этой функции.
    """
    # Загрузка TIR-файла
    tir = rioxarray.open_rasterio(file_tir_path, parse_coordinates=True, dtype=np.float32)
    output_crs = tir.rio.crs
    output_transform = tir.rio.transform()
    full_matrix = tir.data
    sat_id = extract_satellite_name(file_tir_path)

    # Каналы TIR5 и TIR6
    tir5_channel = full_matrix[5]
    tir6_channel = full_matrix[6]

    # Перепроецирование маски воды (используем только (H, W), а не (C, H, W))
    water_mask = reproject_water_mask_to_tir(
        water_mask_path,
        output_crs,
        output_transform,
        (tir.shape[1], tir.shape[2])  # ← Вот это важно: (высота, ширина)
    )

    # Генерация маски облаков
    cloud_mask = generate_cloud_mask(tir5_channel, tir6_channel,
                                     tir5_lower_threshold=268, # если меньше то возможно облако
                                     tir5_upper_threshold=290, # точно не облако
                                     btd_threshold=0.9,
                                     very_cold_threshold=240) # 

    # Сохранение маски облаков (визуализация для отладки)
    visualize_mask(cloud_mask, "Маска облаков (1 - облако, 0 - без облаков)", cloud_mask_output_path.replace(".tif", "_visualization.png"))
    save_mask(cloud_mask, output_crs, output_transform, cloud_mask_output_path)


    # Инициализация массива температуры
    temperature_arr_celsius = np.full((3, tir.shape[1], tir.shape[2]), np.nan, dtype=np.float32)
    clear_pixels_mask = (cloud_mask == 0)

    # Коэффициенты для спутников
    coeff_data = {
        "EL2": {"sea": {"channel": tir6_channel, "offset": -0.5, "scale": 1.0}, "land": {"channel": tir5_channel, "offset": 0.5, "scale": 1.0}},
        "EL3": {"sea": {"channel": tir6_channel, "offset": -0.2, "scale": 1.0}, "land": {"channel": tir5_channel, "offset": 0.8, "scale": 1.0}},
        "EL4": {"sea": {"channel": tir6_channel, "offset": 0.0, "scale": 0.99}, "land": {"channel": tir5_channel, "offset": 1.0, "scale": 0.98}},
        "ARCM1": {"sea": {"channel": tir6_channel, "offset": -0.8, "scale": 1.0}, "land": {"channel": tir5_channel, "offset": 0.2, "scale": 1.0}},
        "ARCM2": {"sea": {"channel": tir6_channel, "offset": -0.6, "scale": 0.99}, "land": {"channel": tir5_channel, "offset": 0.8, "scale": 0.97}}
    }
    current_coeffs = coeff_data.get(sat_id, coeff_data["ARCM1"])
    if sat_id not in coeff_data:
        print(f"Внимание: Коэффициенты для спутника {sat_id} не найдены. Используются по умолчанию (ARCM1).")

    # Маски
    sea_clear_mask = (water_mask == 1) & clear_pixels_mask
    land_clear_mask = (water_mask == 0) & clear_pixels_mask

    # Расчет SST (с коррекцией: температура моря не может быть ниже 0°C)
    if np.any(sea_clear_mask):
        sea_channel_values = current_coeffs["sea"]["channel"][sea_clear_mask]
        offset_sea, scale_sea = current_coeffs["sea"]["offset"], current_coeffs["sea"]["scale"]
        temperature_kelvin_sea = offset_sea + scale_sea * sea_channel_values
        temperature_celsius = temperature_kelvin_sea - 273.15
        temperature_celsius[temperature_celsius < -100.0] = np.nan  # шум
        temperature_celsius[temperature_celsius < 0.0] = 0.0  # Температура моря не может быть ниже 0°C
        temperature_arr_celsius[0][sea_clear_mask] = temperature_celsius
        if np.any(~np.isnan(temperature_arr_celsius[0])):
            print(f"SST рассчитана. Диапазон: {np.nanmin(temperature_arr_celsius[0]):.2f}°C - {np.nanmax(temperature_arr_celsius[0]):.2f}°C")
        else:
            print("SST рассчитана, но все пиксели стали NaN (возможно, из-за NaN в исходных данных или маске).")
    else:
        print("Нет безоблачных пикселей воды для расчета SST.")

    # Расчет LST
    if np.any(land_clear_mask):
        land_channel_values = current_coeffs["land"]["channel"][land_clear_mask]
        offset_land, scale_land = current_coeffs["land"]["offset"], current_coeffs["land"]["scale"]
        temperature_kelvin_land = offset_land + scale_land * land_channel_values
        temperature_celsius = temperature_kelvin_land - 273.15
        temperature_celsius[temperature_celsius < -100.0] = np.nan
        temperature_arr_celsius[1][land_clear_mask] = temperature_celsius
        if np.any(~np.isnan(temperature_arr_celsius[1])):
            print(f"LST рассчитана. Диапазон: {np.nanmin(temperature_arr_celsius[1]):.2f}°C - {np.nanmax(temperature_arr_celsius[1]):.2f}°C")
        else:
            print("LST рассчитана, но все пиксели стали NaN (возможно, из-за NaN в исходных данных или маске).")
    else:
        print("Нет безоблачных пикселей суши для расчета LST.")

    # Комбинированная температура
    if np.any(sea_clear_mask):
        temperature_arr_celsius[2][sea_clear_mask] = temperature_arr_celsius[0][sea_clear_mask]
    if np.any(land_clear_mask):
        temperature_arr_celsius[2][land_clear_mask] = temperature_arr_celsius[1][land_clear_mask]

    # Очистка памяти
    del full_matrix, tir5_channel, tir6_channel, cloud_mask, water_mask
    gc.collect()
    try:
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except (OSError, AttributeError, FileNotFoundError):
        pass

    return temperature_arr_celsius, output_crs, output_transform

# --- Запуск ---
if __name__ == "__main__":
    start_time = time.time()
    # Вызов основной функции
    temperature_result_celsius, crs, transform = proc_temperature(tir_path, water_mask_path, cloud_mask_output_path)
    
    # Визуализация температуры (для отладки)
    visualize_temperature(temperature_result_celsius[2], cloud_mask_output_path.replace(".tif", "_temperature_visualization.png"), title='Температура (SST/LST) °C')
    
    # Сохранение температуры в GeoTIFF
    save_temperature(temperature_result_celsius, crs, transform, temperature_output_path)
    
    end_time = time.time()
    print(f"Общее время выполнения: {end_time - start_time:.2f} секунд")