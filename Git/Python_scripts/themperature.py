import concurrent
import concurrent.futures
import ctypes
import gc
from functools import partial

import numpy as np
import xarray
from rasterio.enums import Resampling
from skimage.filters.rank import mean_bilateral
from skimage.morphology import convex_hull_image, erosion


def upscale(array, new_size_array):
    # Функция рескейлит один одноканальный массив numpy в шейп другого одноканального массива numpy

    resampling = Resampling.nearest

    new_width = new_size_array.shape[0]
    new_height = new_size_array.shape[1]

    return xarray.DataArray(array, dims=['y', 'x'],
                            coords={'y': np.arange(0, -array.shape[0], -1),
                                    'x': np.arange(array.shape[1])}
                            ).rio.write_crs('EPSG:3857').rio.reproject(
        'EPSG:3857',
        shape=(new_width, new_height),
        resampling=resampling
    ).values


def mean_bil(slice, rr):
    print('******************')
    norm_gray = (255 * slice.copy() / np.nanmax(slice)).astype(np.uint8)
    return mean_bilateral(norm_gray, footprint=np.ones((rr, rr)))


def corr_outlines(ch, rr=15, nodata_value=0):
    # Функция делает маску для обрезки краев сцены температуры, с плохо интерполированными данными и лимбом

    hull = convex_hull_image(ch[::10, ::10], nodata_value)

    func = partial(erosion, footprint=np.ones((rr, rr)))
    with concurrent.futures.ProcessPoolExecutor() as executor:
        for k, img in enumerate(executor.map(func, [hull])):
            er = img

    er = upscale(er.astype(np.uint8), ch)
    return er


def proc_temperature(full_matrix, sat_id, water_mask):
    # Считает температуру по нескольким тепловым каналам по заранее найденным коэффициентам, алгоритм как AVHHR по совету С.Дьякова, работает сразу для дня и ночи .

    #     Создаем пустой массив для будущей температуры

    # upscale_matrix = np.full((full_matrix.shape[1], full_matrix.shape[2]),
                             # 0., np.float32)

    # water_mask = upscale(water_mask, upscale_matrix)

    water_mask[water_mask == 255] = 1  # nodata = 255, sea
    water_mask[water_mask == 200] = 0  # land

    # берем маски из full_matrix, маска облачности = к каждому классу прибавлено 5
    ch_masks = full_matrix[13]
    ch_masks[np.isnan(ch_masks)] = 0

    ch_first = full_matrix[8]
    ch_first[np.isnan(ch_first)] = 0

    # берем канал 8 (основной) 9.8 мкм
    ch_second = full_matrix[4]
    ch_second[np.isnan(ch_second)] = 0

    temperature_arr = np.full((3, ch_first.shape[0], ch_first.shape[1]), 0.,
                              np.float32)

    # Выбираем коэффициенты для каждого аппарата отдельно, найдены заранее. При перекалибровке каналов могут меняться
    if sat_id == "EL2":

        try:
            er = corr_outlines(ch_second.copy(), rr=60)
            ch_second[er != 1] = 0

            del er
            gc.collect()
            ctypes.CDLL("libc.so.6").malloc_trim(0)

            # ch_first[ch_first> 140] = 0
            # ch_second[ch_second> 140] = 0

            # Считает температуру океана ch8 format y = 10.0 + 5.0 * x

            coeff_sea = [8,
                         1.08]  # [-160.80890450603113+273.15, 0.6502799136241736] #[20, 1.05]
            coeff_land = [8,
                          1.08]  # [-160.80890450603113+273.15, 0.6502799136241736] #[20, 1.05]

            temperature_arr[0][water_mask == 1] = coeff_sea[0] + coeff_sea[1] * \
                                                  ch_second[water_mask == 1]

            # Считает температуру суши format y = 1.0 * x ** 2 + 2.0 * x + 3.0/
            # temperature_arr[1][water_mask==0] = coeff_land[0] + coeff_land[1]*(ch_second[water_mask==0]-ch_first[water_mask==0])
            temperature_arr[1][water_mask == 0] = coeff_land[0] + coeff_land[
                1] * ch_second[water_mask == 0]

            # Нормируем для колормепа
            # temperature_arr[0][np.bitwise_and(temperature_arr[0]<265,temperature_arr[0]>0)] = 265
            # temperature_arr[1][np.bitwise_and(temperature_arr[1]<250,temperature_arr[1]>0)] = 250

            # temperature_arr[0][temperature_arr[0]>315] = 315
            # temperature_arr[1][temperature_arr[1]>315] = 315

        except:

            print('temperature passed...')

        # Маска качества
        temperature_arr[0][np.bitwise_and(water_mask == 1, ch_second == 0)] = 0
        temperature_arr[1][np.bitwise_and(water_mask == 0, ch_second == 0)] = 0

        # temperature_arr[1][np.bitwise_and(water_mask==0, ch_first==0)] = 0

    elif sat_id == "EL3":

        try:
            er = corr_outlines(ch_second.copy(), rr=60)
            ch_second[er != 1] = 0

            del er
            gc.collect()
            ctypes.CDLL("libc.so.6").malloc_trim(0)

            # ch_first[ch_first> 140] = 0
            # ch_second[ch_second> 140] = 0

            coeff_sea = [47,
                         1]  # [26.94518311119458+273.15, 0.6052455065600127] #[47,1]
            coeff_land = [47,
                          1]  # [26.94518311119458+273.15, 0.6052455065600127] #[47,1]

            # Считает температуру океана ch8 format y = 10.0 + 5.0 * x
            temperature_arr[0][water_mask == 1] = coeff_sea[0] + coeff_sea[1] * \
                                                  ch_second[water_mask == 1]
            # Считает температуру суши format y = 1.0 * x ** 2 + 2.0 * x + 3.0/}
            temperature_arr[1][water_mask == 0] = coeff_land[0] + coeff_land[
                1] * ch_second[water_mask == 0]

        except:

            print('temperature passed...')

        # Маска качества
        temperature_arr[0][np.bitwise_and(water_mask == 1, ch_second == 0)] = 0
        temperature_arr[1][np.bitwise_and(water_mask == 0, ch_second == 0)] = 0

        # temperature_arr[1][np.bitwise_and(water_mask==0, ch_first==0)] = 0

    elif sat_id == "EL4":

        try:

            er = corr_outlines(ch_second.copy(), rr=80)
            ch_second[er != 1] = 0

            del er
            gc.collect()
            ctypes.CDLL("libc.so.6").malloc_trim(0)

            coeff_sea = [55,
                         0.95]  # [-0.3126662694897391+273.15, 0.7464864860863596] #[53,0.95]
            coeff_land = [55,
                          0.95]  # [-0.3126662694897391+273.15, 0.7464864860863596] #[53,0.95]

            # Считает температуру океана split window ch8 - ch5 format y = 1.0 * x ** 2 + 2.0 * x + 3.0/}
            temperature_arr[0][water_mask == 1] = coeff_sea[0] + coeff_sea[
                1] * (ch_second[water_mask == 1])
            # Считает температуру суши split window ch8 - ch5 format y = 1.0 * x ** 2 + 2.0 * x + 3.0/}
            temperature_arr[1][water_mask == 0] = coeff_land[0] + coeff_land[
                1] * ch_second[water_mask == 0]

        except:

            print('temperature passed...')

        # Маска качества
        temperature_arr[0][np.bitwise_and(water_mask == 1, ch_second == 0)] = 0
        temperature_arr[1][np.bitwise_and(water_mask == 0, ch_second == 0)] = 0


    elif sat_id == "ARCM1":

        try:

            er = corr_outlines(ch_second.copy(), rr=80)
            ch_second[er != 1] = 0

            del er
            gc.collect()
            ctypes.CDLL("libc.so.6").malloc_trim(0)

            coeff_sea = [35,
                         1]  # [-196.59160364511416+273.15, 0.7582812583555232] #[35,1]
            coeff_land = [35,
                          1]  # [-196.59160364511416+273.15, 0.7582812583555232] #[35,1]

            # Считает температуру океана ch8 format y = 10.0 + 5.0 * x
            temperature_arr[0][water_mask == 1] = coeff_sea[0] + coeff_sea[1] * \
                                                  ch_second[water_mask == 1]
            # Считает температуру суши ch8 format y = 10.0 + 5.0 * x
            temperature_arr[1][water_mask == 0] = coeff_land[0] + coeff_land[
                1] * ch_second[water_mask == 0]


            # Маска качества
            temperature_arr[0][
                np.bitwise_and(water_mask == 1, ch_second == 0)] = 0
            temperature_arr[1][
                np.bitwise_and(water_mask == 0, ch_second == 0)] = 0

        except:

            print('temperature passed...')

    temperature_arr[2][np.isnan(temperature_arr[1])]=np.nan
    temperature_arr[2][ch_masks==20] = 200 #достаем маску день-ночь без сумерек и облаков
    temperature_arr[2][ch_masks==25] = 200 #достаем ночные облака чтобы получить цельную маску день-ночь
    temperature_arr[2][temperature_arr[2]!=1] = 100

    return temperature_arr
