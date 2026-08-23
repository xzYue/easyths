"""同花顺交易自动化器 - 核心GUI自动化类

基于 pywinauto 实现，优先使用 UIA backend，必要时自动回退到 win32。

Author: noimank
Email: noimank@163.com
"""

import threading
from pathlib import Path
from typing import List, Optional

import psutil
import structlog
from pywinauto.application import Application
from pywinauto import Desktop

from easyths.utils import project_config_instance

logger = structlog.get_logger(__name__)


class TonghuashunAutomator:
    """同花顺交易自动化器 - 核心GUI自动化类

    所有方法都是同步的，由调用方决定执行方式（直接调用或通过COM执行器）
    """
    # 修改为 正则匹配 网上股票交易系统.*  避免可能未来版本更新导致找不到窗口的问题
    # APP_TITLE_NAME = "网上股票交易系统5.0"

    def __init__(self):
        """初始化自动化器"""
        self.app_path = project_config_instance.trading_app_path
        self.app: Optional[Application] = None
        self.main_window = None
        self.main_window_wrapper_object = None
        self.backend = "uia"
        self.locator_backend = "uia"
        self._connected = False
        # 附着/重连串行化：防止看门狗线程与手动重连接口并发修改连接状态
        self._connect_lock = threading.RLock()
        self.logger = structlog.get_logger(__name__)

    def _window_kwargs(self, backend: str) -> dict:
        if backend == "uia":
            return {
                "title_re": "网上股票交易系统.*",
                "control_type": "Window",
                "visible_only": False,
                "depth": 1,
            }
        return {
            "title_re": "网上股票交易系统.*",
            "visible_only": False,
        }

    def _connect_with_backend(self, backend: str, pid: Optional[int] = None) -> bool:
        if pid is not None:
            self.app = Application(backend=backend).connect(process=pid, timeout=5)
        else:
            self.app = Application(backend=backend).connect(path=self.app_path, timeout=5)
        self.main_window = self.app.window(**self._window_kwargs(backend))
        self.main_window_wrapper_object = self.main_window.wrapper_object()
        self.backend = backend
        self.locator_backend = backend
        self._connected = True
        self.logger.info("连接到同花顺进程", backend=backend, locator_backend=backend, pid=pid)
        return True

    def _connect_via_win32_handle_to_uia(self, pid: Optional[int] = None) -> bool:
        if pid is not None:
            win32_app = Application(backend="win32").connect(process=pid, timeout=5)
        else:
            win32_app = Application(backend="win32").connect(path=self.app_path, timeout=5)
        win32_window = win32_app.window(**self._window_kwargs("win32"))
        win32_wrapper = win32_window.wrapper_object()
        handle = win32_wrapper.handle

        self.app = Application(backend="uia").connect(handle=handle, timeout=5)
        self.main_window = Desktop(backend="uia").window(handle=handle)
        self.main_window_wrapper_object = self.main_window.wrapper_object()
        self.backend = "uia"
        self.locator_backend = "win32"
        self._connected = True
        self.logger.info("通过 win32 定位句柄后切回 UIA 成功", backend="uia", locator_backend="win32", handle=handle)
        return True

    def connect(self) -> bool:
        """连接到同花顺交易客户端

        Returns:
            bool: 如果成功连接到同花顺应用返回 True，否则返回 False
        """
        try:
            self.logger.info("正在连接同花顺...")

            # 检查应用路径
            if not self.app_path or not Path(self.app_path).exists():
                self.logger.error("同花顺应用路径不存在", path=self.app_path)
                return False

            # 优先使用 uia，若窗口仅对 win32 可见则自动回退
            try:
                return self._connect_with_backend("uia")
            except Exception as ui_error:
                self.logger.warning("UIA 后端连接失败，尝试通过 win32 定位句柄后切回 UIA", error=str(ui_error))
                try:
                    return self._connect_via_win32_handle_to_uia()
                except Exception as hybrid_error:
                    self.logger.warning("win32 句柄桥接到 UIA 失败，回退到 win32", error=str(hybrid_error))
                    return self._connect_with_backend("win32")

        except Exception as e:
            self.logger.exception("连接同花顺失败", error=str(e))
            return False

    def _reset_state(self) -> None:
        """清除连接状态（不打印日志），供 disconnect/reconnect 复用"""
        self._connected = False
        self.main_window = None
        self.main_window_wrapper_object = None
        self.app = None
        self.backend = "uia"
        self.locator_backend = "uia"

    def _window_alive(self) -> bool:
        """探测已附着的主窗口句柄是否仍然有效"""
        try:
            if self.main_window is None:
                return False
            return bool(self.main_window.exists(timeout=1))
        except Exception:
            return False

    def _candidate_pids(self) -> List[int]:
        """枚举候选券商进程 pid

        精确匹配配置的进程名优先，其次允许同名前缀的相似进程（如 xiadan-plus.exe），
        由调用方通过主窗口标题筛选出真正的交易主窗口进程。
        """
        if not self.app_path:
            return []
        target_name = Path(self.app_path).name.lower()
        if not target_name:
            return []
        target_stem = target_name.rsplit(".", 1)[0]
        exact_pids: List[int] = []
        similar_pids: List[int] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                pid = proc.info.get("pid")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            if not name or not pid:
                continue
            if name == target_name:
                exact_pids.append(pid)
            elif target_stem and name.startswith(target_stem):
                similar_pids.append(pid)
        return exact_pids + similar_pids

    def reconnect(self) -> bool:
        """重新附着到同花顺交易客户端（可重复调用）

        遍历候选进程，只接受主窗口标题匹配 网上股票交易系统.* 的进程，
        避免误附着 xiadan-plus.exe 等无交易主窗口的同名/相似进程；
        保留 UIA → win32 句柄桥接 → win32 的回退顺序。

        Returns:
            bool: 重新附着成功返回 True，否则返回 False
        """
        with self._connect_lock:
            if self.is_connected() and self._window_alive():
                return True

            self._reset_state()

            if not self.app_path or not Path(self.app_path).exists():
                self.logger.error("重连失败：同花顺应用路径不存在", path=self.app_path)
                return False

            candidate_pids = self._candidate_pids()
            if not candidate_pids:
                self.logger.warning("重连失败：未发现候选券商进程", app_path=self.app_path)
                return False

            last_error = ""
            for pid in candidate_pids:
                try:
                    try:
                        return self._connect_with_backend("uia", pid=pid)
                    except Exception as ui_error:
                        self.logger.warning(
                            "候选进程 UIA 附着失败，尝试 win32 句柄桥接",
                            pid=pid, error=str(ui_error)
                        )
                        try:
                            return self._connect_via_win32_handle_to_uia(pid=pid)
                        except Exception as hybrid_error:
                            self.logger.warning(
                                "候选进程 win32 句柄桥接失败，回退 win32",
                                pid=pid, error=str(hybrid_error)
                            )
                            return self._connect_with_backend("win32", pid=pid)
                except Exception as pid_error:
                    # 主窗口不存在（wrapper_object 抛 ElementNotFound）等：换下一个候选进程
                    last_error = str(pid_error)
                    self.logger.warning(
                        "候选进程附着失败（无 网上股票交易系统 主窗口或句柄无效），尝试下一个",
                        pid=pid, error=last_error
                    )
                    self._reset_state()

            self.logger.error(
                "重连同花顺失败：所有候选进程均无可用交易主窗口",
                candidate_count=len(candidate_pids), last_error=last_error
            )
            return False

    def ensure_connected(self) -> bool:
        """确保处于有效连接状态：未连接或句柄失效时自动重新附着"""
        if self.is_connected():
            if self._window_alive():
                return True
            self.logger.warning("券商主窗口句柄已失效，尝试重新附着")
        return self.reconnect()

    def disconnect(self) -> None:
        """断开连接"""
        with self._connect_lock:
            self._reset_state()
        self.logger.info("已断开同花顺连接")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self.app is not None



