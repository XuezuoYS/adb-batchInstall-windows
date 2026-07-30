"""
adb-batchInstall-windows — 批量通过 ADB 安装 APK 脚本。

在 Windows 上自动扫描脚本所在目录及其子目录下的所有 .apk 文件，
并通过 ADB 逐个安装到已连接的 Android 设备上。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Optional

# ── 颜色输出 ──────────────────────────────────────────────────────────


class Colors:
    """终端颜色常量，用于美化输出。"""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"


def color(text: str, *codes: str) -> str:
    """
    用指定的 ANSI 转义码包裹文本。

    :param text: 原始文本
    :type text: str
    :param codes: 一个或多个 ANSI 转义码
    :type codes: str
    :return: 带颜色标记的文本
    :rtype: str
    """
    return "".join(codes) + text + Colors.RESET


def printInfo(msg: str) -> None:
    """打印信息消息。"""
    print(color("[INFO]", Colors.CYAN, Colors.BOLD), msg)


def printOk(msg: str) -> None:
    """打印成功消息。"""
    print(color("[ OK ]", Colors.GREEN, Colors.BOLD), msg)


def printFail(msg: str) -> None:
    """打印失败消息。"""
    print(color("[FAIL]", Colors.RED, Colors.BOLD), msg)


def printWarn(msg: str) -> None:
    """打印警告消息。"""
    print(color("[WARN]", Colors.YELLOW, Colors.BOLD), msg)


def pauseAndExit(code: int = 0) -> None:
    """
    暂停并等待用户按 Enter 后退出。

    当以 --noconsole 编译为 exe 时，sys.stdin 不可用，
    此时跳过暂停直接退出。

    :param code: 退出码，0 正常退出，非 0 异常退出
    :type code: int
    """
    print()
    try:
        input(color("按 Enter 键退出...", Colors.DIM))
    except (RuntimeError, EOFError):
        # --noconsole 模式下 stdin 不可用，忽略暂停
        pass
    sys.exit(code)


# ── 核心功能 ──────────────────────────────────────────────────────────


def getScriptDir() -> Path:
    """
    获取脚本/可执行文件所在目录。
    无论是 .py 还是 .exe（PyInstaller 打包）均能正确返回。

    :return: 脚本所在目录的 Path 对象
    :rtype: Path
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包后的 .exe
        return Path(sys.executable).parent.resolve()
    return Path(__file__).parent.resolve()


def checkAdb() -> Optional[str]:
    """
    检查 ADB 是否可用。

    :return: ADB 可执行路径（如 "adb"），若不可用则返回 None
    :rtype: Optional[str]
    """
    try:
        result = subprocess.run(
            ["adb", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            firstLine = result.stdout.splitlines()[0] if result.stdout else "adb found"
            printInfo(f"ADB: {firstLine}")
            return "adb"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def getDevices() -> List[str]:
    """
    获取已连接的 ADB 设备列表。

    :return: 设备序列号列表
    :rtype: List[str]
    """
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = result.stdout.strip().splitlines()
        devices: List[str] = []
        for line in lines[1:]:  # 跳过第一行 "List of devices attached"
            if line.strip() and "\tdevice" in line:
                serial = line.split("\t")[0].strip()
                devices.append(serial)
        return devices
    except Exception:
        return []


def findApkFiles(directory: Path) -> List[Path]:
    """
    递归扫描目录下所有 .apk 文件。

    :param directory: 要扫描的目录
    :type directory: Path
    :return: 按文件名排序的 APK 文件路径列表
    :rtype: List[Path]
    """
    apks = list(directory.rglob("*.apk"))
    apks.sort(key=lambda p: p.name)
    return apks


def _runAdbInstall(cmd: List[str], apkName: str) -> tuple[bool, str]:
    """
    执行单次 adb install 命令并解析结果。

    ADB 输出可能包含 UTF-8 字符，Windows 简体中文系统默认编码为
    GBK，需显式指定 UTF-8 解码以避免 UnicodeDecodeError。

    :param cmd: adb 命令列表
    :type cmd: List[str]
    :param apkName: APK 文件名（仅用于日志）
    :type apkName: str
    :return: (是否成功, 原始输出)
    :rtype: tuple[bool, str]
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        # 合并 stdout + stderr 以防 ADB 将进度写到不同流
        output = (result.stdout + result.stderr).strip()
        # returncode == 0 即表示安装成功，无需依赖 "Success" 字符串
        # （ADB 有时将进度写在 stdout，结果写在 stderr，或反之）
        if result.returncode == 0:
            return True, output
        return False, output
    except subprocess.TimeoutExpired:
        return False, "安装超时"
    except Exception as e:
        return False, str(e)


def _promptDowngrade(apkName: str) -> bool:
    """
    询问用户是否降级/重新安装。

    :param apkName: APK 文件名
    :type apkName: str
    :return: True 表示用户同意降级，False 表示跳过
    :rtype: bool
    """
    try:
        ans = input(
            f"    {color('是否降级安装？(y/N): ', Colors.YELLOW)}"
        )
        return ans.strip().lower() == "y"
    except (RuntimeError, EOFError):
        return False


def installApk(apkPath: Path, serial: Optional[str] = None) -> bool:
    """
    通过 ADB 安装单个 APK。

    首次尝试 adb install -r，若遇到版本降级或已存在错误，
    则询问用户是否使用 -d（降级）标记重试。

    :param apkPath: APK 文件的完整路径
    :type apkPath: Path
    :param serial: 设备序列号，为 None 时安装到唯一设备
    :type serial: Optional[str]
    :return: 安装是否成功
    :rtype: bool
    """
    apkName = apkPath.name

    # 构建基础命令
    baseCmd = ["adb"]
    if serial:
        baseCmd += ["-s", serial]

    # ── 第一次尝试: adb install -r ──
    ok, output = _runAdbInstall(
        baseCmd + ["install", "-r", str(apkPath)], apkName
    )
    if ok:
        return True

    # ── 检查是否需要降级 ──
    needDowngrade = (
        "INSTALL_FAILED_VERSION_DOWNGRADE" in output
        or "INSTALL_FAILED_ALREADY_EXISTS" in output
    )
    if not needDowngrade:
        printFail(f"  {apkName} — {output[:200]}")
        return False

    # ── 降级 / 已存在 → 询问用户 ──
    if "INSTALL_FAILED_VERSION_DOWNGRADE" in output:
        printWarn(f"  版本降级: {apkName}")
    else:
        printWarn(f"  已存在: {apkName}")

    if not _promptDowngrade(apkName):
        print(f"    {color('跳过', Colors.DIM)}")
        return True  # 用户选择跳过，视为成功

    # ── 用户同意 → 使用 -d 降级标记重试 ──
    print(f"    {color('尝试降级安装...', Colors.CYAN)}")
    ok, output = _runAdbInstall(
        baseCmd + ["install", "-r", "-d", str(apkPath)], apkName
    )
    if ok:
        printOk(f"  ✓ {apkName} (降级成功)")
        return True

    printFail(f"  {apkName} — {output[:200]}")
    return False


def batchInstall(apkFiles: List[Path], serial: Optional[str] = None) -> None:
    """
    批量安装 APK 文件。

    :param apkFiles: APK 文件路径列表
    :type apkFiles: List[Path]
    :param serial: 目标设备序列号
    :type serial: Optional[str]
    """
    total = len(apkFiles)
    if total == 0:
        printWarn("未找到任何 .apk 文件")
        return

    printInfo(f"共找到 {color(str(total), Colors.BOLD)} 个 APK 文件，开始安装...\n")

    successCount = 0
    failCount = 0
    skipCount = 0

    for i, apk in enumerate(apkFiles, 1):
        sizeMb = apk.stat().st_size / (1024 * 1024)
        label = f"[{i}/{total}] {apk.name} ({sizeMb:.1f} MB)"
        print(color(label, Colors.CYAN), end=" ", flush=True)

        ok = installApk(apk, serial)
        if ok:
            successCount += 1
            printOk(f"  ✓ {apk.name}")
        else:
            failCount += 1

    # ── 输出汇总 ──
    print()
    printInfo("=" * 48)
    printInfo(
        f"安装完成: "
        f"{color('成功', Colors.GREEN)}{successCount} / "
        f"{color('失败', Colors.RED)}{failCount} / "
        f"总计 {total}"
    )
    if failCount > 0:
        printWarn("部分 APK 安装失败，请检查上方错误信息")
    else:
        printOk("全部安装成功！")


# ── 主入口 ──────────────────────────────────────────────────────────


def main() -> None:
    """
    主入口函数。

    执行流程：
        1. 检查 ADB 是否可用
        2. 获取已连接的设备列表
        3. 扫描脚本所在目录的 .apk 文件
        4. 选择设备并批量安装
    """
    print()
    print(color(" ╔══════════════════════════════════════════╗", Colors.CYAN))
    print(color(" ║     ADB 批量 APK 安装工具 v1.0          ║", Colors.CYAN))
    print(color(" ╚══════════════════════════════════════════╝", Colors.CYAN))
    print()

    # 1. 检查 ADB
    printInfo("正在检查 ADB 环境...")
    adbPath = checkAdb()
    if adbPath is None:
        printFail(
            "ADB 未找到！请确保:\n"
            "  1. Android SDK Platform-Tools 已安装\n"
            "  2. adb 已添加到系统 PATH 环境变量\n"
            "  3. 或在此目录下放置 adb.exe"
        )
        # 尝试在当前目录找 adb.exe
        localAdb = getScriptDir() / "adb.exe"
        if localAdb.exists():
            printInfo(f"发现本地 {localAdb.name}，正在尝试使用...")
            adbPath = str(localAdb)
        else:
            pauseAndExit(1)

    # 2. 获取设备
    printInfo("正在检测连接的 Android 设备...")
    devices = getDevices()
    if not devices:
        printFail("未检测到任何 Android 设备，请确认：")
        printFail("  1. 设备已通过 USB 连接")
        printFail("  2. 已开启 USB 调试模式")
        printFail(f"  3. 运行 {color('adb devices', Colors.YELLOW)} 确认设备状态")
        pauseAndExit(1)

    printInfo(f"检测到 {color(str(len(devices)), Colors.BOLD)} 台设备:")
    for d in devices:
        print(f"    {color(d, Colors.CYAN)}")

    # 多设备选择
    selectedSerial: Optional[str] = None
    if len(devices) > 1:
        print()
        printWarn("检测到多台设备，默认安装到第一台.")
        printInfo(f"将安装到: {color(devices[0], Colors.CYAN)}")
        selectedSerial = devices[0]
    else:
        selectedSerial = devices[0]
        printInfo(f"将安装到: {color(selectedSerial, Colors.CYAN)}")

    # 3. 扫描 APK
    scriptDir = getScriptDir()
    printInfo(f"正在扫描目录: {scriptDir}")
    apkFiles = findApkFiles(scriptDir)

    printInfo(f"找到 {color(str(len(apkFiles)), Colors.BOLD)} 个 APK 文件")
    if apkFiles:
        for apk in apkFiles:
            sizeMb = apk.stat().st_size / (1024 * 1024)
            print(color(f"    {apk.name} ({sizeMb:.1f} MB)", Colors.DIM))

    print()

    # 4. 开始安装
    batchInstall(apkFiles, selectedSerial)

    # 最后暂停，防止双击 exe 时窗口闪退
    pauseAndExit(0)


if __name__ == "__main__":
    main()
