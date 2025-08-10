import logging
from logging import Formatter, FileHandler, StreamHandler 

def setup_logger(name: str) -> logging.Logger:
    """
    Настройка логгера с выводом файла в консоль с минимальным количеством деталей
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    file_formatter = Formatter(fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                               datefmt="%Y-%m-%d %H:%M:%S")
    
    console_formatter = Formatter(fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
                               datefmt="%H:%M:%S")
    
    # Обработчик для файла
    file_handler = FileHandler("example.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)

    # Обработчик консоли
    stream_handler = StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    logging.getLogger("urlib3").propagate = False

    return logger
