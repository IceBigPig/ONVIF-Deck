from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlsplit, urlunsplit

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage


def uri_with_credentials(uri: str, username: str, password: str) -> str:
    if not username:
        return uri
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError:
        return uri
    if not parsed.hostname:
        return uri
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if port:
        host = f"{host}:{port}"
    userinfo = f"{quote(username, safe='')}:{quote(password, safe='')}@"
    return urlunsplit(
        (parsed.scheme, userinfo + host, parsed.path, parsed.query, parsed.fragment)
    )


def safe_display_uri(uri: str) -> str:
    try:
        parsed = urlsplit(uri)
        port = parsed.port
    except ValueError:
        return uri
    if not parsed.hostname or parsed.username is None:
        return uri
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    if port:
        host = f"{host}:{port}"
    netloc = f"{parsed.username}:***@{host}"
    return urlunsplit(
        (parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment)
    )


class PreviewThread(QThread):
    frame_ready = Signal(QImage)
    preview_error = Signal(str)
    preview_state = Signal(str)

    def __init__(
        self, uri: str, username: str, password: str, parent: object | None = None
    ) -> None:
        super().__init__(parent)
        self.uri = uri_with_credentials(uri, username, password)
        self._process: subprocess.Popen[bytes] | None = None
        self._process_lock = threading.Lock()

    def stop(self) -> None:
        """Interrupt decoding and force an FFmpeg child out of a blocked connect/read."""

        self.requestInterruption()
        with self._process_lock:
            process = self._process
        if process and process.poll() is None:
            process.terminate()

    @staticmethod
    def _ffmpeg_executable() -> str:
        discovered = shutil.which("ffmpeg")
        if discovered:
            return discovered
        for candidate in (
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "C:/ffmpeg/bin/ffmpeg.exe",
        ):
            if Path(candidate).is_file():
                return candidate
        try:
            import imageio_ffmpeg

            bundled = imageio_ffmpeg.get_ffmpeg_exe()
            if Path(bundled).is_file():
                return bundled
        except (ImportError, RuntimeError, OSError):
            pass
        return ""

    def run(self) -> None:
        ffmpeg = self._ffmpeg_executable()
        if ffmpeg:
            self._run_ffmpeg(ffmpeg)
        else:
            self._run_opencv()

    def _run_ffmpeg(self, executable: str) -> None:
        command = [
            executable,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            self.uri,
            "-map",
            "0:v:0",
            "-an",
            "-sn",
            "-vf",
            "scale=1280:-2:force_original_aspect_ratio=decrease",
            "-q:v",
            "5",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "pipe:1",
        ]
        self.preview_state.emit("正在连接 RTSP（FFmpeg）…")
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            self.preview_error.emit(f"无法启动 FFmpeg：{exc}")
            return

        with self._process_lock:
            self._process = process

        buffer = bytearray()
        received_frame = False
        try:
            if process.stdout is None:
                self.preview_error.emit("FFmpeg 没有创建视频输出管道")
                return
            while not self.isInterruptionRequested():
                chunk = os.read(process.stdout.fileno(), 65536)
                if not chunk:
                    break
                buffer.extend(chunk)
                while True:
                    start = buffer.find(b"\xff\xd8")
                    if start < 0:
                        if len(buffer) > 1024 * 1024:
                            del buffer[:-2]
                        break
                    end = buffer.find(b"\xff\xd9", start + 2)
                    if end < 0:
                        if start:
                            del buffer[:start]
                        break
                    jpeg = bytes(buffer[start : end + 2])
                    del buffer[: end + 2]
                    image = QImage.fromData(jpeg, "JPG")
                    if image.isNull():
                        continue
                    if not received_frame:
                        received_frame = True
                        self.preview_state.emit("预览中 · FFmpeg")
                    self.frame_ready.emit(image)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1.5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1)
            stderr = b""
            if process.stderr is not None:
                stderr = process.stderr.read()
            with self._process_lock:
                self._process = None

        if self.isInterruptionRequested():
            return
        if not received_frame:
            detail = stderr.decode("utf-8", errors="replace").strip().splitlines()
            message = detail[-1] if detail else "设备未返回视频帧"
            message = message.replace(self.uri, safe_display_uri(self.uri))
            self.preview_error.emit(f"RTSP 连接失败：{message}")
        elif process.returncode not in (0, None):
            self.preview_error.emit("视频流已中断")

    def _run_opencv(self) -> None:
        try:
            import cv2
        except ImportError:
            self.preview_error.emit("缺少 opencv-python，无法启动 RTSP 预览")
            return

        os.environ.setdefault(
            "OPENCV_FFMPEG_CAPTURE_OPTIONS",
            "rtsp_transport;tcp|stimeout;5000000",
        )
        self.preview_state.emit("正在连接 RTSP（OpenCV）…")
        try:
            params: list[int] = []
            if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
                params += [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 6000]
            if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
                params += [cv2.CAP_PROP_READ_TIMEOUT_MSEC, 4000]
            capture = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG, params)
        except (cv2.error, TypeError):
            capture = cv2.VideoCapture(self.uri, cv2.CAP_FFMPEG)

        if not capture.isOpened():
            capture.release()
            self.preview_error.emit(
                "RTSP 连接失败，请检查账号、网络和摄像头的 RTSP 服务"
            )
            return

        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.preview_state.emit("预览中 · OpenCV")
        failures = 0
        last_emit = 0.0
        try:
            while not self.isInterruptionRequested():
                ok, frame = capture.read()
                if not ok:
                    failures += 1
                    if failures >= 20:
                        self.preview_error.emit("视频流已中断")
                        break
                    self.msleep(30)
                    continue
                failures = 0
                now = time.monotonic()
                if now - last_emit < 1 / 30:
                    continue
                last_emit = now
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                height, width, channels = rgb.shape
                image = QImage(
                    rgb.data,
                    width,
                    height,
                    channels * width,
                    QImage.Format.Format_RGB888,
                ).copy()
                self.frame_ready.emit(image)
        finally:
            capture.release()
