import logging
import os

class LineRotatingFileHandler(logging.FileHandler):
    """
    Кастомный обработчик логов, который гарантирует, 
    что файл лога никогда не превысит заданное количество строк.
    """
    def __init__(self, filename, max_lines=100, mode='a', encoding='utf-8'):
        self.max_lines = max_lines
        super().__init__(filename, mode, encoding=encoding)

    def emit(self, record):
        # Сначала записываем новую строку лога
        super().emit(record)
        # Затем сразу обрезаем файл
        self._truncate_lines()

    def _truncate_lines(self):
        try:
            with open(self.baseFilename, 'r', encoding=self.encoding, errors='ignore') as f:
                lines = f.readlines()
            
            # Если строк больше разрешенного, перезаписываем файл
            if len(lines) > self.max_lines:
                with open(self.baseFilename, 'w', encoding=self.encoding) as f:
                    f.writelines(lines[-self.max_lines:])
        except Exception:
            pass

# Инициализация логгера
logger = logging.getLogger('pkg-sender')
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

# Очищаем любые обработчики по умолчанию, чтобы избежать дублирования
if logger.hasHandlers():
    logger.handlers.clear()

# Вывод ТОЛЬКО в файл app.log (максимум 100 строк)
log_path = os.path.join(os.path.dirname(__file__), 'app.log')
fh = LineRotatingFileHandler(log_path, max_lines=100)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)

logger.addHandler(fh)
# Отключаем передачу логов корневому логгеру (который может писать в консоль)
logger.propagate = False