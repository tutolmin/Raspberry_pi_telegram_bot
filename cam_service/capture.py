#!/usr/bin/env python3
"""
Непрерывный захват фото с камеры Raspberry Pi как systemd сервис.
Сетка наносится на полное изображение, кроп применяется программно.
Все параметры (включая кроп) обновляются через SIGHUP.
"""

import os
import sys
import time
import signal
import logging
import subprocess
import configparser
from pathlib import Path
from PIL import Image, ImageDraw
from libcamera import controls
from picamera2 import Picamera2

# ========== ПУТИ И КОНСТАНТЫ ==========
CONFIG_DIR = Path.home() / ".config"
CONFIG_FILE = CONFIG_DIR / "cam_service.ini"

# Настройки по умолчанию
DEFAULTS = {
    'capture': {
        'photo_path': "/mnt/ram_cam/current.jpg",
        'temp_path': "/mnt/ram_cam/temp.jpg",
        'dest': "andrei@192.168.3.1:/mnt/ram_cam/",
        'interval': "1.0",
        'grid': "False",
        # Базовое разрешение сенсора (для сетки и захвата)
        'sensor_width': "4608",
        'sensor_height': "2592",
        # Параметры кропа (применяются программно после захвата)
        'crop_enabled': "False",
        'crop_x': "150",
        'crop_y': "100",
        'crop_width': "4400",
        'crop_height': "2400",
        'preview_enabled': "False",
    }
}

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

class CameraService:
    def __init__(self):
        self.picam2 = None
        self.config = {}
        self.exif_data = None
        self.reload_requested = False
        self.running = True
        
        signal.signal(signal.SIGHUP, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Обработчик сигнала SIGHUP."""
        logger.info("Получен сигнал SIGHUP. Перечитка конфигурации...")
        self.reload_requested = True

    def load_config(self):
        """Чтение конфигурации из INI файла."""
        if not CONFIG_FILE.exists():
            logger.error(f"Файл конфигурации не найден: {CONFIG_FILE}")
            self._write_default_config()
            return False

        parser = configparser.ConfigParser()
        parser.read(CONFIG_FILE)
        
        new_config = {}
        section = 'capture'
        
        if section not in parser:
            logger.error(f"Секция [{section}] не найдена в конфиге.")
            return False

        # Чтение параметров
        new_config['photo_path'] = parser.get(section, 'photo_path', fallback=DEFAULTS['capture']['photo_path'])
        new_config['temp_path'] = parser.get(section, 'temp_path', fallback=DEFAULTS['capture']['temp_path'])
        new_config['dest'] = parser.get(section, 'dest', fallback=DEFAULTS['capture']['dest'])
        new_config['interval'] = float(parser.get(section, 'interval', fallback=DEFAULTS['capture']['interval']))
        new_config['grid'] = parser.getboolean(section, 'grid', fallback=DEFAULTS['capture']['grid'])
        
        # Разрешение сенсора (используется для захвата и расчета сетки)
        new_config['sensor_width'] = int(parser.get(section, 'sensor_width', fallback=DEFAULTS['capture']['sensor_width']))
        new_config['sensor_height'] = int(parser.get(section, 'sensor_height', fallback=DEFAULTS['capture']['sensor_height']))
        
        # Параметры кропа
        new_config['crop_enabled'] = parser.getboolean(section, 'crop_enabled', fallback=DEFAULTS['capture']['crop_enabled'])
        new_config['crop_x'] = int(parser.get(section, 'crop_x', fallback=DEFAULTS['capture']['crop_x']))
        new_config['crop_y'] = int(parser.get(section, 'crop_y', fallback=DEFAULTS['capture']['crop_y']))
        new_config['crop_width'] = int(parser.get(section, 'crop_width', fallback=DEFAULTS['capture']['crop_width']))
        new_config['crop_height'] = int(parser.get(section, 'crop_height', fallback=DEFAULTS['capture']['crop_height']))
        new_config['preview_enabled'] = parser.getboolean(section, 'preview_enabled', fallback=DEFAULTS['capture']['preview_enabled'])

        # Проверка изменений для логирования
        if self.config:
            if self.config['sensor_width'] != new_config['sensor_width'] or self.config['sensor_height'] != new_config['sensor_height']:
                logger.warning("Изменено разрешение сенсора! Требуется полный перезапуск сервиса (systemctl restart).")
            else:
                logger.info("Параметры кропа и сетки обновлены без перезапуска камеры.")

        self.config = new_config
        return True

    def _write_default_config(self):
        """Создает файл конфигурации по умолчанию."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        parser = configparser.ConfigParser()
        parser['capture'] = DEFAULTS['capture']
        with open(CONFIG_FILE, 'w') as f:
            parser.write(f)
        logger.info(f"Создан файл конфигурации: {CONFIG_FILE}")

    def draw_grid(self, image):
        """
        Наносит сетку с шагом 10% относительно полного сенсора.
        Принимает и возвращает объект PIL Image.
        """
        draw = ImageDraw.Draw(image)
        w, h = image.size
        color = (255, 255, 255) 
        width = 3 # Толщина линии
        
        # Шаг сетки относительно полного сенсора (из конфига)
        step_x = self.config['sensor_width'] * 0.1
        step_y = self.config['sensor_height'] * 0.1
        
        # Вертикальные линии
        for i in range(1, 10):
            x = int(i * step_x)
            # Рисуем линию, если она попадает в границы текущего изображения
            if 0 < x < w:
                draw.line([(x, 0), (x, h)], fill=color, width=width)
        
        # Горизонтальные линии
        for i in range(1, 10):
            y = int(i * step_y)
            if 0 < y < h:
                draw.line([(0, y), (w, y)], fill=color, width=width)
        
        return image

    def apply_crop(self, image):
        """
        Программно обрезает изображение согласно настройкам кропа.
        """
        if not self.config.get('crop_enabled', False):
            return image
            
        x = self.config['crop_x']
        y = self.config['crop_y']
        w = self.config['crop_width']
        h = self.config['crop_height']
        
        # Проверка границ, чтобы не было ошибок PIL
        img_w, img_h = image.size
        # Ограничиваем кроп размерами изображения
        x = max(0, min(x, img_w))
        y = max(0, min(y, img_h))
        w = min(w, img_w - x)
        h = min(h, img_h - y)
        
        if w <= 0 or h <= 0:
            logger.warning("Некорректные параметры кропа, пропускаю обрезку.")
            return image

        return image.crop((x, y, x + w, y + h))

    def sync_photo(self):
        """Синхронизирует фото с удаленным хостом."""
        src = self.config['photo_path']
        dest = self.config['dest']
        
        if not os.path.exists(src):
            return False

        try:
            result = subprocess.run(
                ["rsync", "-a", "--timeout=5", src, dest],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                logger.debug("Photo synced")
                return True
            else:  
                logger.warning(f"Sync failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return False

    def init_camera(self):
        """Инициализация камеры на полное разрешение сенсора."""
        logger.info("Инициализация камеры...")
        self.picam2 = Picamera2()

        # Важно: захватываем ПОЛНОЕ разрешение сенсора
        # ScalerCrop здесь НЕ используем, чтобы сохранить все пиксели для сетки
        capture_config = self.picam2.create_still_configuration(
            main={"size": (self.config['sensor_width'], self.config['sensor_height'])},
            buffer_count=1
        )

        self.picam2.configure(capture_config)
        self.picam2.start()

        # Применяем ручные настройки фокуса и экспозиции
        # Эквивалент команды: --autofocus-mode manual --lens-position 8 --shutter 200000 --awb daylight --analoggain 1.5
        self.picam2.set_controls({
            "AfMode": controls.AfModeEnum.Manual,  # --autofocus-mode manual
            "LensPosition": 8.0,                   # --lens-position 8
            "ExposureTime": 200000,                # --shutter 200000 (в микросекундах)
            "AwbMode": controls.AwbModeEnum.Daylight,  # --awb daylight
            "AnalogueGain": 1.5                    # --analoggain 1.5
        })

        logger.info(f"Камера запущена. Сенсор: {self.config['sensor_width']}x{self.config['sensor_height']}")
        logger.info("Настройки: ручной фокус (8 диоптрий), выдержка 200000 мкс, усиление 1.5, баланс белого Daylight")

#        self.picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})

#        logger.info(f"Камера запущена. Сенсор: {self.config['sensor_width']}x{self.config['sensor_height']}")

    def create_preview(self, image):
        """Создаёт уменьшенную копию изображения для превью."""
        if not self.config.get('preview_enabled', False):
            return
        
        try:
            # Уменьшаем до 640x360 (или пропорционально)
            preview_size = (640, 360)
            image.thumbnail(preview_size, Image.Resampling.LANCZOS)
            
            preview_path = Path(self.config['photo_path']).parent / "preview.jpg"
            image.save(preview_path, quality=80, exif=self.exif_data)
            logger.debug(f"Preview saved to {preview_path}")
        except Exception as e:
            logger.error(f"Error creating preview: {e}")

    def run(self):
        """Основной цикл сервиса."""
        if not self.load_config():
            sys.exit(1)

        self.init_camera()
        Path(self.config['photo_path']).parent.mkdir(parents=True, exist_ok=True)

        logger.info("Сервис запущен. SIGHUP для обновления настроек.")

        try:
            while self.running:
                if self.reload_requested:
                    self.load_config()
                    self.reload_requested = False
                
                start_time = time.time()

                # 1. Захват ПОЛНОГО изображения во временный файл
                self.picam2.capture_file(self.config['temp_path'])

                capture_time = time.time() - start_time
                logger.info(f"Captured in {capture_time:.2f}s")

                # 2. Открываем для обработки в памяти
                with Image.open(self.config['temp_path']) as img:
                    
                    # Keep EXIF data
                    self.exif_data = img.info.get('exif')  # Сохраняем EXIF

                    # 3. Наносим сетку (на полном изображении)
                    if self.config.get('grid', False):
                        img = self.draw_grid(img)
                    
                    # 4. Применяем кроп (если включен)
                    # Сетка уже нарисована, поэтому на обрезанном кадре 
                    # она будет соответствовать координатам полного сенсора
                    img = self.apply_crop(img)
                    
                    # 5. Сохраняем результат в финальный путь
                    img.save(self.config['photo_path'], 'JPEG', exif=self.exif_data)

                    # 6. Создаём превью если режим включён
                    if self.config.get('preview_enabled', False):
                        logger.info(f"Saving preview")
                        # Открываем ещё раз для создания превью (чтобы не портить основное)
                        with Image.open(self.config['photo_path']) as preview_img:
                            self.create_preview(preview_img)

                # Убираем временный файл, если остался (на случай ошибок)
                if os.path.exists(self.config['temp_path']):
                    os.remove(self.config['temp_path'])

                crop_time = time.time() - start_time
                logger.info(f"Cropped in {crop_time:.2f}s")

                self.sync_photo()

                sleep_time = max(0, self.config['interval'] - (time.time() - start_time))
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("Остановка по Ctrl+C...")
        finally:   
            if self.picam2:
                self.picam2.stop()
                logger.info("Камера остановлена.")

if __name__ == "__main__":
    service = CameraService()
    service.run()
