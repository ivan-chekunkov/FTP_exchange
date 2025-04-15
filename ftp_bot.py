import asyncio
import os
import sys
from ftplib import FTP
from pathlib import Path
import shutil
import aioftp
import yaml
from loguru import logger
from aioftp import StatusCodeError

logger.add(
    "Logfile.log",
    format="{time} {level} {message}",
    level="DEBUG",
    rotation="10 MB",
    compression="zip",
)


def get_basename_file() -> str:
    """Получить короткое имя скрипта"""
    return os.path.basename(__file__)


CONFIG: dict = {}

SYSTEM_VARIABLE: dict = {"basename_file": get_basename_file, "version": "0.4"}

HELP_DESCRIPTION: list = [
    "- Чтобы получить справку, наберите '{name} help'",
    "- При запуске программы без параметров она будет использовать "
    + "конфигурацию из файла config.yaml в папке со скриптом",
    "- Вы можете запустить программу и указать конфигурацию "
    + "например: '{name} my_conf.yaml'",
]

logger.debug("Запуск скрипта версии: {}".format(SYSTEM_VARIABLE["version"]))


def read_config(file_path: Path = Path("config.yaml")) -> dict:
    """Получение настроек из файла конфигурации"""
    if file_path.exists():
        with open(file_path, "r") as file:
            try:
                result = yaml.safe_load(file)
                logger.debug("File config '{}' loaded!".format(file_path))
                return result
            except Exception as error:
                logger.error(error)
                sys.exit()
    else:
        logger.error("File '{}' not found!".format(file_path))
        sys.exit()


def call_help():
    """Вызов справки"""
    logger.info("Call Help")
    print("\033[1;32;40m")
    print("\n" + "=" * 20 + "HELP!" + "=" * 20)
    for line_help in HELP_DESCRIPTION:
        print(line_help.format(name=SYSTEM_VARIABLE["basename_file"]()))
    input("\nНажмите Enter для выхода из программы!\n")
    sys.exit()


def parse_argv(argv: list) -> bool | Path | None:
    """Разбор возможных параметров запуска программы"""
    if len(argv) == 1:
        return False
    if argv[1].lower() in ("help", "h", "-help", "-h", "--help", "--h"):
        call_help()
    return Path(argv[1])


def ftp_connect():
    ftp = FTP(CONFIG["ftp"]["host"])
    ftp.login(user=CONFIG["ftp"]["user"], passwd=CONFIG["ftp"]["password"])
    # files = ftp.nlst()
    # print(files)
    # with open("out/outfile.txt", "rb") as file:
    #     ftp.storbinary("STOR out/outfile.txt", file)
    # with open("in/infile.txt", "wb") as file:
    #     ftp.retrbinary("RETR infile.txt", file.write)
    # files = ftp.nlst()
    # for ff in files:
    #     response = ftp.sendcmd(f"MLST {ff}")
    #     if "type=dir" in response:
    #         print("Это папка")
    #     elif "type=file" in response:
    #         print("Это файл")
    welcome_message = ftp.getwelcome()
    print(welcome_message)
    ftp.quit()


class FTPError(Exception):
    """Ошибка отсутствия FTP коннекта"""

    pass


def upload_file(ftp: FTP, local_file: Path, remote_path: str) -> bool:
    """Загрузка файла на FTP Server"""
    welcome_message = ftp.getwelcome()
    if welcome_message:
        logger.debug("FTP коннект!")
    else:
        raise FTPError
    ftp.cwd("/")
    try:
        ftp.cwd(remote_path)
    except Exception as err:
        logger.error("Ошибка входа в папку на FTP: {}".format(err))
        raise FTPError
    names = ftp.nlst()
    local_file_name = local_file.name
    if local_file_name in names:
        logger.error("{} уже существует на FTP".format(local_file_name))
        return False
    remote_file_name = remote_path + "/" + local_file_name
    with open(local_file, "rb") as file:
        ftp.storbinary(f"STOR {local_file_name}", file)
        logger.info(
            "Файл {} успешно загружен в {}".format(
                local_file, remote_file_name
            )
        )
    return True


def move_local_file(source: Path) -> None:
    """Перемещение файла в архив"""
    arh_path = source.parent.joinpath("arh")
    if not arh_path.exists():
        os.mkdir(arh_path)
        logger.info("Папка '{}' успешно создана!".format(arh_path))
    destination = arh_path.joinpath(source.name)
    try:
        shutil.move(source, destination)
        logger.info(f"Файл успешно перемещён в {destination}")
    except FileNotFoundError:
        logger.error("Файл не найден!")
        sys.exit()
    except PermissionError:
        logger.error("Нет прав на перемещение!")
        sys.exit()
    except Exception as err:
        logger.error("Ошибка: {}".format(err))
        sys.exit()


def upload(ftp: FTP, local_path: Path, remote_path: str):
    """Обработка схемы для загрузки файлов на FTP Server"""
    if not local_path.exists():
        logger.error("{} not found!".format(local_path))
        return
    if not local_path.is_dir():
        logger.error("{} not dir!".format(local_path))
        return
    local_files = list(filter(Path.is_file, local_path.iterdir()))
    if not local_files:
        logger.debug("{} empty!".format(local_path))
        return
    for loc_file in local_files:
        res_code = upload_file(
            ftp=ftp, local_file=loc_file, remote_path=remote_path
        )
        if res_code:
            move_local_file(source=loc_file)


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


async def download_multiple_files(client, files):
    tasks = []
    for remote, local in files.items():
        task = client.download(remote, local)
        tasks.append(task)
    await asyncio.gather(*tasks)


async def main():
    try:
        async with aioftp.Client.context(
            CONFIG["ftp"]["host"],
            user=CONFIG["ftp"]["user"],
            password=CONFIG["ftp"]["password"],
        ) as client:
            # await client.download("nonexistent.txt", "local.txt")
            pass
    except StatusCodeError as err:
        print(f"Ошибка FTP: {err}")
    except Exception as err:
        print(f"Общая ошибка: {err}")

        files_to_download = {
            "file1.txt": "local1.txt",
            "file2.txt": "local2.txt",
            "file3.txt": "local3.txt",
        }

        await download_multiple_files(client, files_to_download)
        print("All files downloaded concurrently")


if __name__ == "__main__":
    arg = parse_argv(sys.argv)
    if arg:
        CONFIG = read_config(arg)
    else:
        CONFIG = read_config()
    ftp = FTP(CONFIG["ftp"]["host"])
    ftp.login(user=CONFIG["ftp"]["user"], passwd=CONFIG["ftp"]["password"])
    upload(
        ftp=ftp,
        local_path=Path("C:\\Localpath\\files"),
        remote_path="remote/files",
    )
    # ftp_connect()
