import os
import sys
from ftplib import FTP
from pathlib import Path

import yaml
from loguru import logger

logger.add(
    "Logfile.log",
    format="{time} {level} {message}",
    level="DEBUG",
    rotation="10 MB",
    compression="zip",
)


def get_basename_file() -> str:
    return os.path.basename(__file__)


CONFIG: dict = {}

SYSTEM_VARIABLE: dict = {"basename_file": get_basename_file, "version": "0.3"}

HELP_DESCRIPTION: list = [
    "- To call for help, dial ={name} help=",
    "- Running the program without parameters will force it to take the "
    + "configuration from the config.yaml in the script folder",
    "- You can run the program and force it to specify a configuration "
    + "like: ={name} my_conf.yaml=",
]

logger.debug("Run version script: {}".format(SYSTEM_VARIABLE["version"]))


def read_config(file_path: Path = Path("config.yaml")) -> dict:
    if file_path.exists():
        with open(file_path, "r") as file:
            try:
                result = yaml.safe_load(file)
                logger.debug("File config {} loaded!".format(file_path))
                return result
            except Exception as error:
                logger.error(error)
                sys.exit()
    else:
        logger.error("File '{}' not found!".format(file_path))
        sys.exit()


def call_help():
    logger.info("Call Help")
    print("\033[1;32;40m Bright Green")
    print("\n" + "=" * 20 + "HELP!" + "=" * 20)
    for line_help in HELP_DESCRIPTION:
        print(line_help.format(name=SYSTEM_VARIABLE["basename_file"]()))
    input("\nPress any key for Exit!\n")
    sys.exit()


def parse_argv(argv: list) -> bool | Path | None:
    if len(argv) == 1:
        return False
    if argv[1].lower() in ("help", "h", "-help", "-h", "--help", "--h"):
        call_help()
    return Path(argv[1])


def ftp_connect():
    ftp = FTP(CONFIG["ftp"]["host"])
    ftp.login(user=CONFIG["ftp"]["user"], passwd=CONFIG["ftp"]["password"])
    files = ftp.nlst()
    print(files)
    with open("out/outfile.txt", "rb") as file:
        ftp.storbinary("STOR out/outfile.txt", file)
    with open("in/infile.txt", "wb") as file:
        ftp.retrbinary("RETR infile.txt", file.write)
    files = ftp.nlst()
    for ff in files:
        response = ftp.sendcmd(f"MLST {ff}")
        if "type=dir" in response:
            print("Это папка")
        elif "type=file" in response:
            print("Это файл")
    welcome_message = ftp.getwelcome()
    print(welcome_message)
    ftp.quit()


def upload_file():
    """
    Проверяем существование локальной директории
    Проверяем наличие файлов
    1 Файлов нет -> выходим
    2 Файлы есть работаем с файлами
    Проверяем коненкт к FTP
    Проверяем папку на FTP
    Смотрим наличие такого же файла на FTP
    1 Если есть то не копируем и игнорируем данный файл
    2 Если файла нет, то копируем его на FTP
    Если копирование удачное, то перемещаем наш файл в локальный архив
    """
    pass


def download_file():
    """
    Проверяем коненкт к FTP
    Проверяем папку на FTP
    Смотрим наличе файлов на FTP
    1 Файлов нет -> выходим
    2 Файлы есть работаем с файлами
    Проверяем существование локальной директории
    Смотрим наличие такого же файла в локальной папке
    1 Если есть то не копируем и игнорируем данный файл
    2 Если файла нет, то копируем его с FTP
    Если копирование удачное, то удаляем файл с FTP
    """
    pass


if __name__ == "__main__":
    arg = parse_argv(sys.argv)
    if arg:
        CONFIG = read_config(arg)
    else:
        CONFIG = read_config()
    logger.info(CONFIG)
    ftp_connect()
