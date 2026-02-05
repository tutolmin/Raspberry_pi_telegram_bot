import subprocess

def get_system_info():
    return subprocess.check_output("uname -a", shell=True).decode()

def get_cpu_temperature():
    return subprocess.check_output("vcgencmd measure_temp", shell=True).decode().strip()

def get_ip_addresses():
    return subprocess.check_output("hostname -I", shell=True).decode().strip()

def get_cameras():
    return subprocess.check_output("rpicam-hello --list-cameras", shell=True).decode().strip()

def get_ram_usage() -> str:
    try:
        result = subprocess.check_output("free -m", shell=True)
        lines = result.decode('utf-8').splitlines()
        memory_info = lines[1].split()
        total = int(memory_info[1])
        used = int(memory_info[2])
        free = int(memory_info[3])
        used_percent = (used / total) * 100
        free_percent = (free / total) * 100
        return (f"Total RAM: {total} MB\n"
                f"Used RAM: {used} MB ({used_percent:.2f}%)\n"
                f"Free RAM: {free} MB ({free_percent:.2f}%)")
    except subprocess.CalledProcessError as e:
        return f"Error retrieving RAM usage: {e.output.decode('utf-8')}"


def get_cpu_usage() -> str:
    try:
        result = subprocess.check_output("top -bn1 | grep 'Cpu(s)'", shell=True)
        cpu_info = result.decode('utf-8').split()
        user = float(cpu_info[1])
        system = float(cpu_info[3])
        idle = float(cpu_info[7])
        used = 100 - idle
        return (f"User CPU Usage: {user:.2f}%\n"
                f"System CPU Usage: {system:.2f}%\n"
                f"Idle CPU Usage: {idle:.2f}%\n"
                f"Total CPU Usage: {used:.2f}%")
    except subprocess.CalledProcessError as e:
        return f"Error retrieving CPU usage: {e.output.decode('utf-8')}"


def get_disk_usage() -> str:
    try:
        result = subprocess.check_output("df -h --total", shell=True)
        lines = result.decode('utf-8').splitlines()
        disk_info = lines[-1].split()
        total = disk_info[1]
        used = disk_info[2]
        available = disk_info[3]
        used_percent = disk_info[4]
        return (f"Total Disk Space: {total}\n"
                f"Used Disk Space: {used} ({used_percent})\n"
                f"Available Disk Space: {available}")
    except subprocess.CalledProcessError as e:
        return f"Error retrieving disk usage: {e.output.decode('utf-8')}"


def get_uptime():
    return subprocess.check_output("uptime -p", shell=True).decode()

def get_loadavg() -> str:
    try:
        with open("/proc/loadavg", "r") as f:
            loadavg_line = f.read().strip()
        # Первые три значения — это 1, 5 и 15 минут
        loads = loadavg_line.split()[:3]
        load_1, load_5, load_15 = loads[0], loads[1], loads[2]
        return f"Load average: {load_1} (1m) | {load_5} (5m) | {load_15} (15m)"
    except Exception as e:
        return f"Error reading loadavg: {e}"

def get_services() -> str:
    try:
        result = subprocess.check_output("systemctl list-units --type=service --state=running", shell=True)
        return result.decode('utf-8')
    except subprocess.CalledProcessError as e:
        return f"Error retrieving services: {e.output.decode('utf-8')}"

def manage_service(action: str, service: str) -> str:
    try:
        if action not in ["start", "stop", "status", "restart"]:
            return "Invalid action. Use one of the following: start, stop, status, restart."

        result = subprocess.check_output(f"sudo systemctl {action} {service}", shell=True, stderr=subprocess.STDOUT)
        return result.decode('utf-8')
    except subprocess.CalledProcessError as e:
        return f"Error performing {action} on {service}: {e.output.decode('utf-8')}"

#def get_gpio_status():
#    return subprocess.check_output("gpio readall", shell=True).decode()

def get_gpio_status():
    try:
        # Используем gpioinfo из пакета gpiod
        result = subprocess.run(
            ["gpioinfo"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            # Ограничиваем вывод, чтобы не перегружать Telegram
            return '\n'.join(lines[:30]) + ("\n..." if len(lines) > 30 else "")
        else:
            return f"gpioinfo error: {result.stderr}"
    except FileNotFoundError:
        return "GPIO info not available. Install 'gpiod' package."
    except Exception as e:
        return f"Error reading GPIO: {e}"

def get_netinfo():
    return subprocess.check_output("ifconfig", shell=True).decode()

def ping_host(host):
    return subprocess.check_output(f"ping -c 4 {host}", shell=True).decode()


def get_failed_services() -> str:
    try:
        result = subprocess.check_output(
            "systemctl list-units --user --type=service --state=failed --no-legend --no-pager",
            shell=True, text=True
        )
        lines = result.strip().splitlines()
        if not lines:
            return "No running services found."

        output_lines = []
        for idx, line in enumerate(lines, 1):
            # Разделяем строку, но сохраняем описание как остаток
            parts = line.split(maxsplit=4)
            unit = parts[0] if len(parts) > 0 else "N/A"
            load = parts[1] if len(parts) > 1 else "N/A"
            active = parts[2] if len(parts) > 2 else "N/A"
            sub = parts[3] if len(parts) > 3 else "N/A"
            description = parts[4] if len(parts) > 4 else ""
            output_lines.append(f"{idx}. {unit} ({active}, {sub}) — {description}")

        return "\n".join(output_lines)
    except subprocess.CalledProcessError as e:
        return f"Error retrieving running services: {e.output}"



def get_running_services() -> str:
    try:
        result = subprocess.check_output(
            "systemctl list-units --user --type=service --state=running --no-legend --no-pager",
            shell=True, text=True
        )
        lines = result.strip().splitlines()
        if not lines:
            return "No running services found."

        output_lines = []
        for idx, line in enumerate(lines, 1):
            # Разделяем строку, но сохраняем описание как остаток
            parts = line.split(maxsplit=4)
            unit = parts[0] if len(parts) > 0 else "N/A"
            load = parts[1] if len(parts) > 1 else "N/A"
            active = parts[2] if len(parts) > 2 else "N/A"
            sub = parts[3] if len(parts) > 3 else "N/A"
            description = parts[4] if len(parts) > 4 else ""
            output_lines.append(f"{idx}. {unit} ({active}, {sub}) — {description}")

        return "\n".join(output_lines)
    except subprocess.CalledProcessError as e:
        return f"Error retrieving running services: {e.output}"


def get_all_services() -> str:
    try:
        result = subprocess.check_output("systemctl list-unit-files --type=service", shell=True)
        services = result.decode('utf-8').splitlines()
        services = [service for service in services if service.strip() != ""]
        formatted_services = "\n\n".join([f"{i+1}. {services[i]}" for i in range(len(services))])
        return formatted_services
    except subprocess.CalledProcessError as e:
        return f"Error retrieving all services: {e.output.decode('utf-8')}"

