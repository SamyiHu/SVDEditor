"""后台 SVD 解析 worker。

把耗时的 SVD 解析（minidom 解析 + 数据模型构建 + 继承解析 deepcopy）移出 GUI
线程，避免多文档打开时主线程被阻塞导致卡顿。

设计：
- SVDLoaderWorker(QObject) 持有信号，affinity 在主线程（构造它的线程）。
- _ParseRunnable(QRunnable) 在 QThreadPool 线程里跑纯数据解析（不碰任何 Qt 控件），
  完成后通过 worker 的信号把结果回传到主线程（Qt 自动用 QueuedConnection 派发）。
- 主线程收到信号后在槽里做"装配"（更新 state_manager、重建树、注册文档），
  装配逻辑天然串行（信号槽在主线程执行），避免多文件装配交错的数据竞争。

用法：
    worker = SVDLoaderWorker()
    worker.parsed.connect(self._on_file_parsed)   # 主线程槽
    worker.failed.connect(self._on_file_failed)
    worker.load_files([path1, path2, ...])         # 并发提交到 QThreadPool
"""
import logging
from typing import List

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

from .svd_parser import SVDParser

logger = logging.getLogger("svd_tool.core.SVDLoaderWorker")


class _ParseRunnable(QRunnable):
    """单个 SVD 文件的解析任务（在 QThreadPool 线程执行）。纯数据，不碰 Qt 控件。"""

    def __init__(self, file_path: str, worker: "SVDLoaderWorker"):
        super().__init__()
        self._file_path = file_path
        self._worker = worker

    def run(self):
        try:
            parser = SVDParser()
            device_info = parser.parse_file(self._file_path)
            warnings = list(getattr(parser, "warnings", []) or [])
            # 发信号回主线程；device_info 是纯 Python 数据对象，跨线程传递安全。
            self._worker.parsed.emit(self._file_path, device_info, warnings)
        except Exception as e:
            logger.error(f"后台解析失败: {self._file_path} - {e}", exc_info=True)
            self._worker.failed.emit(self._file_path, str(e))


class SVDLoaderWorker(QObject):
    """后台并发解析 SVD 文件的协调器。

    信号（均在主线程派发，因为本对象 affinity 在主线程）：
        started(int): 提交了 N 个文件开始解析
        parsed(str, object, list): (file_path, device_info, warnings) 解析成功
        failed(str, str): (file_path, error_message) 解析失败
        all_done(): 所有已提交文件都完成（成功或失败）
    """

    parsed = pyqtSignal(str, object, list)
    failed = pyqtSignal(str, str)
    started = pyqtSignal(int)
    all_done = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pending = 0  # 尚未返回的文件数（线程安全的增减由主线程信号槽串行驱动）
        self._pool = QThreadPool.globalInstance()

    def load_files(self, file_paths: List[str]) -> None:
        """并发提交多个文件解析。可多次调用，_pending 累加。"""
        paths = [p for p in file_paths if p]
        if not paths:
            return
        self._pending += len(paths)
        self.started.emit(len(paths))
        for path in paths:
            runnable = _ParseRunnable(path, self)
            # autoDelete=True（默认）：run 跑完自动回收 runnable。
            self._pool.start(runnable)

    def has_pending(self) -> bool:
        return self._pending > 0

    def _mark_one_done(self):
        """由调用方/槽在处理完一个 parsed/failed 后调用，维护计数并决定是否 all_done。"""
        if self._pending > 0:
            self._pending -= 1
        if self._pending == 0:
            self.all_done.emit()
