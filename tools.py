import datetime
import os
from typing import Optional, Dict, List
import subprocess
import requests
import shlex
import threading
from langchain.agents import Tool

TAVILY_KEY = os.getenv("TAVILY_API_KEY")


def tavily_search(query, api_key=TAVILY_KEY, max_results=5, caller=""):
    url = "https://api.tavily.com/search"

    log_action(log_text=f"{caller}: SearchWeb: \n" + query)

    payload = {"api_key": api_key, "query": query, "max_results": max_results}

    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def log_action(logger_file="logs.txt", log_text=""):
    with open(logger_file, "a") as file:
        file.write("\n" + log_text + "\n")


def report(thought, caller="", *args):
    log_action(log_text=f"{caller}: Report: \n" + thought)
    return "success"


def _stream_reader(stream, output_list: List[str], prefix: str, log_file_path: str):
    """
    Читает строки из потока (stream) в реальном времени,
    добавляет их в список (output_list), выводит в консоль
    и записывает в лог-файл.
    """
    try:
        # iter(stream.readline, '') - это элегантный способ читать строки
        # до тех пор, пока поток не закроется (readline не вернет пустую строку).
        for line in iter(stream.readline, ""):
            # Добавляем в общий список для возврата из основной функции
            output_list.append(line)

            # Формируем сообщение с префиксом
            log_message = f"{prefix} {line}"

            # Выводим в консоль в реальном времени
            print(log_message, end="", flush=True)

            # Записываем в файл в реальном времени
            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(log_message)
    finally:
        stream.close()


def run_cmd(
    input_str: str,
    timeout: Optional[float] = None,
    cwd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
    shell: bool = True,
    delim: str = "$$$",
    sudo_pass: str = "",
    log_file: str = "cmd_output.log",
    add_security_header=True,
) -> str:
    """
    Выполняет одну или несколько команд.

    Args:
        cmd_str (str): Строка с командой или командами, разделенными `delim`.
        daemon (bool): Если True, запускает команду в новом окне терминала
                       (используя `x-terminal-emulator`) и немедленно возвращает управление.
                       Агент получает только подтверждение о запуске.
                       Если False (по умолчанию), выполняет команду в текущем процессе,
                       ожидает завершения и возвращает полный вывод.
        ... (остальные параметры)

    Returns:
        str: В обычном режиме - код возврата и полный вывод.
             В режиме daemon - статус запуска и PID нового процесса терминала.
    """

    try:

        cmd_str, daemon_str = input_str.split("^^^")
        cmd_str, daemon_str = cmd_str.strip(), daemon_str.strip()

        daemon = False
        if daemon_str == "True" or daemon_str == "true":
            daemon = True
    except ValueError:
        return "Value Error. Most probably you did not provide a second argument, remember that the function takes in one string with two parts separated by ^^^ sign, the first one is the command to be executed itself and the second one is a bool starting from capital letter"
    except Exception as e:
        return f"Cmd run tool call ended with exception: {e}."

    print(daemon)
    if add_security_header:
        command_prefix = (
            f"echo {sudo_pass} | sudo -S proxychains4 "
            if sudo_pass
            else "proxychains4 "
        )
    else:
        command_prefix = f"echo {sudo_pass} | sudo -S " if sudo_pass else ""

    if daemon:
        # --- ЛОГИКА ДЛЯ РЕЖИМА "ДЕМОНА" (ЗАПУСК В НОВОМ ОКНЕ) ---
        log_action("RunCmd (Daemon)", cmd_str)
        try:
            # Команда-обертка, которая выполнит основную команду, а затем будет ждать
            # нажатия Enter, чтобы окно терминала не закрылось сразу.
            # Это позволяет увидеть результат выполнения.
            full_command_to_run = (
                f"{command_prefix}{cmd_str}; "
                'echo ""; '
                'echo "---"; '
                'echo "Процесс-демон завершен. Нажмите Enter, чтобы закрыть это окно."; '
                "read"
            )

            # Используем x-terminal-emulator, чтобы запустить терминал по умолчанию
            # Опция -e выполняет команду внутри нового терминала.
            cmd_list = ["x-terminal-emulator", "-e", f'bash -c "{full_command_to_run}"']

            # Popen запускает процесс и не ждет его завершения.
            # Это именно то, что нужно для режима "демона".
            process = subprocess.Popen(cmd_list)

            # Возвращаем агенту сообщение об успехе и PID нового терминала
            return (
                f"0 Daemon process launched in new terminal with PID: {process.pid}. "
                f"Check the new terminal window for command status."
            )

        except FileNotFoundError:
            # Эта ошибка возникнет, если `x-terminal-emulator` по какой-то причине не найден.
            return (
                "-1 Exception: Required command 'x-terminal-emulator' not found. "
                "Please ensure you are on a standard Linux Mint desktop."
            )
        except Exception as e:
            return f"-1 Exception: Failed to start daemon process: {e}"

    # --- ИСХОДНАЯ ЛОГИКА, ЕСЛИ DAEMON=FALSE ---
    log_action("RunCmd (Standard)", cmd_str)
    if not isinstance(cmd_str, str):
        return "-1 Exception: cmd_str must be a string"

    print(command_prefix)
    print(cmd_str)

    parts = [(f"{command_prefix} " + p) for p in cmd_str.split(delim) if p.strip()]
    print(parts)
    if not parts:
        return "-1 "

    # Очищаем лог-файл перед запуском ('w' - write)
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(f"--- Log started for command: {cmd_str} ---\n")

    combined_stdout = []
    combined_stderr = []
    last_returncode = 0

    try:
        for part in parts:
            print(f"\n--- Running command: {part} ---\n")
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n--- Running command: {part} ---\n")

            current_stdout_list = []
            current_stderr_list = []

            process_args = {
                "stdout": subprocess.PIPE,
                "stderr": subprocess.PIPE,
                "text": True,
                "encoding": "utf-8",
                "cwd": cwd,
                "env": env,
                "shell": shell,
            }

            command_to_run = shlex.split(part) if not shell else part
            process = subprocess.Popen(command_to_run, **process_args)

            stdout_thread = threading.Thread(
                target=_stream_reader,
                args=(process.stdout, current_stdout_list, "[stdout]", log_file),
            )
            stderr_thread = threading.Thread(
                target=_stream_reader,
                args=(process.stderr, current_stderr_list, "[stderr]", log_file),
            )
            stdout_thread.start()
            stderr_thread.start()

            try:
                process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                timeout_msg = f"\n[timeout] Command timed out after {timeout}s and was terminated.\n"
                print(timeout_msg)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(timeout_msg)
                current_stderr_list.append(timeout_msg)
                last_returncode = -1

            stdout_thread.join()
            stderr_thread.join()

            last_returncode = process.returncode
            combined_stdout.extend(current_stdout_list)
            combined_stderr.extend(current_stderr_list)

            if last_returncode != 0:
                error_msg = f"\n--- Command failed with code {last_returncode}. Halting execution. ---\n"
                print(error_msg)
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(error_msg)
                break

        return f"Console run ended with code {last_returncode} \n{''.join(combined_stdout)}{''.join(combined_stderr)}"

    except Exception as e:
        error_msg = f"\n[exception] An unexpected error occurred: {e}\n"
        print(error_msg)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(error_msg)
        return f"-1 Exception: {e}"


log_action(log_text="_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _")
log_action(
    log_text=f"ЗАПУСК ОТ {str(datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}"
)
log_action(log_text="_ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _ _")

REPORTTOOL = Tool(
    name="Report",
    func=lambda thought, *args: report(thought=thought, caller="Active Agent"),
    description="Use this tools after every action to describe what you have done and why it is essential to understand your motives.",
)
SEARCHTOOL = Tool(
    name="SearchWeb",
    func=lambda query, *args: tavily_search(query=query, caller="Active Agent"),
    description="Uses web browser to get search results for the provided input. Use in order to get extra data when needed.",
)
# timeout=None, cwd=None, env=None, shell=True, delim="$$$", sudo_pass=""
RUNCMDTOOL = Tool(
    name="RunCmd",
    func=lambda cmd_str, *args, **kwargs: run_cmd(
        cmd_str,
        timeout=None,
        cwd=None,
        env=None,
        shell=True,
        delim="^^^",
        sudo_pass=os.getenv("SUDO_PASS"),
    ),
    description=f"Takes in one string with two parts separated by ^^^ sign, the first one is the command to be executed itself and the second one is a bool starting from capital letter. Only run as daemons those commands that need to run in background and you do not need output from them. For example if you need to set up a localhost application, then run it as daemon, if you want to get something from a website then don't run it as a daemon.",
)
