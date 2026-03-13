"""同花顺交易自动化器 - 核心GUI自动化类

基于 pywinauto 实现，优先使用 UIA backend，必要时自动回退到 win32。

Author: noimank
Email: noimank@163.com
"""

from pathlib import Path
from typing import Optional

import structlog
from pywinauto.application import Application

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
        self._connected = False
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

    def _connect_with_backend(self, backend: str) -> bool:
        self.app = Application(backend=backend).connect(path=self.app_path, timeout=5)
        self.main_window = self.app.window(**self._window_kwargs(backend))
        self.main_window_wrapper_object = self.main_window.wrapper_object()
        self.backend = backend
        self._connected = True
        self.logger.info("连接到同花顺进程", backend=backend)
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
                self.logger.warning("UIA 后端连接失败，尝试回退到 win32", error=str(ui_error))
                return self._connect_with_backend("win32")

        except Exception as e:
            self.logger.exception("连接同花顺失败", error=str(e))
            return False

    def disconnect(self) -> None:
        """断开连接"""
        self._connected = False
        self.main_window = None
        self.main_window_wrapper_object = None
        self.app = None
        self.backend = "uia"
        self.logger.info("已断开同花顺连接")

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._connected and self.app is not None



