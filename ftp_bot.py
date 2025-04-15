import asyncio
import os
import shutil
import sys
from ftplib import FTP
from pathlib import Path
from typing import NoReturn

import aioftp
import yaml
from aioftp import StatusCodeError
from loguru import logger

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

SYSTEM_VARIABLE: dict = {"basename_file": get_basename_file, "version": "0.5"}

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
                logger.debug(
                    "Файл конфигураций '{}' загружен!".format(file_path)
                )
                return result
            except Exception as error:
                logger.error(error)
                sys.exit()
    else:
        logger.error("Файл конфигураций '{}' не обнаружен!".format(file_path))
        sys.exit()


def call_help() -> NoReturn:
    """Вызов справки"""
    logger.info("Call Help")
    print("\033[1;32;40m")
    print("\n" + "=" * 20 + "HELP!" + "=" * 20)
    for line_help in HELP_DESCRIPTION:
        print(line_help.format(name=SYSTEM_VARIABLE["basename_file"]()))
    input("\nНажмите Enter для выхода из программы!\n")
    sys.exit()


def parse_argv(argv: list) -> bool | Path | NoReturn:
    """Разбор возможных параметров запуска программы"""
    if len(argv) == 1:
        return False
    if argv[1].lower() in ("help", "h", "-help", "-h", "--help", "--h"):
        call_help()
    return Path(argv[1])


class FTPError(Exception):
    """Ошибка отсутствия FTP коннекта"""

    pass


def upload_file(
    ftp: FTP, local_file: Path, remote_path: str
) -> bool | NoReturn:
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


def move_local_file(source: Path) -> None | NoReturn:
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


def upload(ftp: FTP, local_path: Path, remote_path: str) -> None:
    """Обработка схемы для загрузки файлов на FTP Server"""
    if not local_path.exists():
        logger.error("{} несуществует!".format(local_path))
        return None
    if not local_path.is_dir():
        logger.error("{} не является директорией!".format(local_path))
        return None
    local_files = list(filter(Path.is_file, local_path.iterdir()))
    if not local_files:
        logger.debug("{} пуста!".format(local_path))
        return None
    for loc_file in local_files:
        res_code = upload_file(
            ftp=ftp, local_file=loc_file, remote_path=remote_path
        )
        if res_code:
            move_local_file(source=loc_file)


def download_file(ftp: FTP, local_path: Path, remote_file: str) -> bool:
    """Загрузка файла с FTP в локальную директорию"""
    if not local_path.exists():
        logger.error("{} несуществует!".format(local_path))
        return None
    if not local_path.is_dir():
        logger.error("{} не является директорией!".format(local_path))
        return None
    local_files = list(
        map(
            lambda x: x.name,
            filter(Path.is_file, local_path.iterdir()),
        )
    )
    if remote_file in local_files:
        logger.error(
            "Файл {} уже существует в локальной директории".format(remote_file)
        )
        return False
    local_file = local_path.joinpath(remote_file)
    with open(local_file, "wb") as f:
        ftp.retrbinary(f"RETR {remote_file}", f.write)
        logger.info(
            "Файл {} успешно скачан как {}".format(remote_file, local_file)
        )
        return True


def get_files_ftp(ftp: FTP) -> list[str] | None:
    """Получение списка файлов из директории FTP"""
    result = []
    for name, facts in ftp.mlsd():
        if facts["type"] == "file":
            result.append(name)
    return result


def delete_file_ftp(ftp: FTP, file_to_delete: str) -> None | NoReturn:
    """Удаление файла на FTP"""
    try:
        ftp.delete(file_to_delete)
        logger.info("Файл {} успешно удален".format(file_to_delete))
    except Exception as err:
        logger.error("Ошибка при удалении файла: {}".format(err))
        sys.exit()


def download(ftp: FTP, local_path: Path, remote_path: str) -> None:
    """Обработка схемы загрузки файлов с FTP в локальную директорию"""
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
    files = get_files_ftp(ftp=ftp)
    if not files:
        return None
    for remote_file in files:
        res_code = download_file(
            ftp=ftp, local_path=local_path, remote_file=remote_file
        )
        if res_code:
            delete_file_ftp(ftp=ftp, file_to_delete=remote_file)


def read_and_run_exchange() -> tuple[Path, str]:
    


if __name__ == "__main__":
    arg = parse_argv(sys.argv)
    if arg:
        CONFIG = read_config(arg)
    else:
        CONFIG = read_config()
    try:
        ftp = FTP(CONFIG["ftp"]["host"])
        ftp.login(user=CONFIG["ftp"]["user"], passwd=CONFIG["ftp"]["password"])
    except Exception as err:
        logger.error("Ошибка создания FTP {}".format(err))
    upload(
        ftp=ftp,
        local_path=Path("C:\\Localpath\\files"),
        remote_path="remote/files",
    )
    download(
        ftp=ftp,
        local_path=Path("C:\\Localpath\\ftp"),
        remote_path="local",
    )
    # ftp_connect()


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
