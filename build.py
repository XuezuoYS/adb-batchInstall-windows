"""
ADB 批量安装工具 — 构建脚本。

通过 PyInstaller 将 main.py 编译为单文件 exe。
运行方式： python build.py  或  uv run build.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ── 颜色输出 ──────────────────────────────────────────────────────────


class Colors:
    """终端颜色常量。"""

    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    DIM = "\033[2m"


def color(text: str, *codes: str) -> str:
    """
    用 ANSI 转义码包裹文本。

    :param text: 原始文本
    :type text: str
    :param codes: ANSI 转义码
    :type codes: str
    :return: 带颜色标记的文本
    :rtype: str
    """
    return "".join(codes) + text + Colors.RESET


def info(msg: str) -> None:
    """打印信息消息。"""
    print(color("[INFO]", Colors.CYAN, Colors.BOLD), msg)


def ok(msg: str) -> None:
    """打印成功消息。"""
    print(color("[ OK ]", Colors.GREEN, Colors.BOLD), msg)


def fail(msg: str) -> None:
    """打印失败消息。"""
    print(color("[FAIL]", Colors.RED, Colors.BOLD), msg)


# ── 构建配置 ──────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
MAIN_SCRIPT = SCRIPT_DIR / "main.py"
OUTPUT_DIR = SCRIPT_DIR / "dist"
SPEC_NAME = "adb-batchInstall-windows"
ICON_PATH: Path | None = None  # 如果有 .ico 可改为 Path("icon.ico")

# ── 构建函数 ──────────────────────────────────────────────────────────


def checkPyInstaller() -> str | None:
    """
    检查 PyInstaller 是否可用。

    :return: 可执行命令名，不可用时返回 None
    :rtype: str | None
    """
    # 优先尝试 uv run pyinstaller，再尝试 pip 安装的版本
    candidates = [
        ["uv", "tool", "run", "pyinstaller", "--version"],
        ["pyinstaller", "--version"],
        ["python", "-m", "PyInstaller", "--version"],
        ["python3", "-m", "PyInstaller", "--version"],
    ]
    for cmd in candidates:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                ver = result.stdout.strip() or result.stderr.strip()
                info(f"PyInstaller: {ver}")
                return cmd[:2] if cmd[0] == "uv" else cmd[0]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return None


def ensureDependencies() -> None:
    """
    确保 PyInstaller 已安装。
    如果缺失，通过 uv tool install 自动安装。
    """
    if checkPyInstaller():
        return

    info("PyInstaller 未安装，正在自动安装...")
    try:
        subprocess.run(
            ["uv", "tool", "install", "pyinstaller"],
            check=True,
            timeout=120,
        )
        ok("PyInstaller 安装成功")
    except subprocess.CalledProcessError:
        fail("自动安装失败，请手动运行: uv tool install pyinstaller")
        sys.exit(1)


def build() -> None:
    """
    执行 PyInstaller 编译。

    生成单文件 exe，输出到 dist/ 目录。
    """
    info(f"源文件: {MAIN_SCRIPT}")
    info(f"输出目录: {OUTPUT_DIR}")

    # 基础命令
    cmd = ["uv", "tool", "run", "pyinstaller", "--onefile"]

    # 有控制台窗口，运行后显示输出并等待按 Enter 退出
    cmd.append("--console")

    # 输出目录
    cmd.append("--distpath")
    cmd.append(str(OUTPUT_DIR))

    # 临时构建目录
    cmd.append("--workpath")
    cmd.append(str(SCRIPT_DIR / "build_tmp"))

    # 清空 .spec 文件（避免干扰）
    cmd.append("--specpath")
    cmd.append(str(SCRIPT_DIR / "build_tmp"))

    # 指定主脚本
    cmd.append("--name")
    cmd.append(SPEC_NAME)
    cmd.append(str(MAIN_SCRIPT))

    # 图标（如果有）
    if ICON_PATH and ICON_PATH.exists():
        cmd.append("--icon")
        cmd.append(str(ICON_PATH))

    info("正在编译，请稍候...\n")
    print(color(f"    uv tool run pyinstaller --onefile --noconsole ...", Colors.DIM))
    print()

    result = subprocess.run(cmd, timeout=300)

    if result.returncode != 0:
        fail("编译失败，请检查上方错误信息")
        sys.exit(1)

    exePath = OUTPUT_DIR / f"{SPEC_NAME}.exe"
    if exePath.exists():
        sizeMb = exePath.stat().st_size / (1024 * 1024)
        ok("编译成功！")
        print()
        print(color(f"    📦 {exePath.name}", Colors.BOLD))
        print(color(f"    大小: {sizeMb:.1f} MB", Colors.DIM))
        print(color(f"    路径: {exePath}", Colors.DIM))
        print()
        info("使用方法：将生成的 exe 放到 APK 文件夹中，双击运行即可")
    else:
        fail("编译后未找到 exe 文件，请检查 dist/ 目录")


def clean() -> None:
    """
    清理临时构建文件（build_tmp/、.spec）。
    """
    import shutil

    tmpDir = SCRIPT_DIR / "build_tmp"
    if tmpDir.exists():
        shutil.rmtree(tmpDir)
        ok(f"已清理临时目录: {tmpDir}")

    specFile = SCRIPT_DIR / f"{SPEC_NAME}.spec"
    if specFile.exists():
        specFile.unlink()
        ok(f"已清理 spec 文件: {specFile}")


# ── 主入口 ──────────────────────────────────────────────────────────


def main() -> None:
    """
    主入口函数。

    流程：
        1. 确保 PyInstaller 已安装
        2. 执行编译
        3. 清理临时文件
    """
    print()
    print(color(" ╔══════════════════════════════════════════╗", Colors.CYAN))
    print(color(" ║     ADB 批量安装工具 - 构建脚本         ║", Colors.CYAN))
    print(color(" ╚══════════════════════════════════════════╝", Colors.CYAN))
    print()

    # 1. 检查 & 安装 PyInstaller
    info("检查 PyInstaller...")
    ensureDependencies()

    # 2. 先清理上次残留
    clean()

    # 3. 编译
    build()

    # 4. 清理临时文件
    clean()

    print()
    ok("一切就绪！")


if __name__ == "__main__":
    main()
