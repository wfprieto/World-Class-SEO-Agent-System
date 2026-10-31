"""Optional Playwright rendering with truthful dependency and browser states."""

from __future__ import annotations

import importlib.util
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from contracts.adapter import AdapterResult
from security.browser_capture import render_browser
from security.url_safety import validate_public_url

_WAIT_UNTIL = {"commit", "domcontentloaded", "load", "networkidle"}
_RESOURCE_TYPES = {
    "document",
    "stylesheet",
    "image",
    "media",
    "font",
    "script",
    "texttrack",
    "xhr",
    "fetch",
    "eventsource",
    "manifest",
    "other",
}


class BrowserNotConfigured(RuntimeError):
    """Playwright or its Chromium binary is unavailable."""


@dataclass(frozen=True)
class BrowserHealth:
    dependency: str
    browser: str
    executable: str | None
    state: str
    install_command: str
    uninstall_command: str


class BrowserRenderer(Protocol):
    def health(self) -> BrowserHealth: ...

    def render(self, url: str, **kwargs: Any) -> dict[str, Any]: ...


class PlaywrightRenderer:
    """Launch one isolated Chromium context for one bounded inspection."""

    @staticmethod
    def _commands() -> tuple[str, str]:
        return (
            "python -m playwright install chromium",
            "python -m playwright uninstall chromium",
        )

    def health(self) -> BrowserHealth:
        install, uninstall = self._commands()
        try:
            dependency = importlib.util.find_spec("playwright.sync_api")
        except (ImportError, ModuleNotFoundError, ValueError):
            dependency = None
        if dependency is None:
            return BrowserHealth(
                dependency="missing",
                browser="unknown",
                executable=None,
                state="NOT_CONFIGURED",
                install_command=install,
                uninstall_command=uninstall,
            )
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                executable = str(playwright.chromium.executable_path)
            installed = bool(executable and Path(executable).is_file())
            return BrowserHealth(
                dependency="installed",
                browser="installed" if installed else "missing",
                executable=executable or None,
                state="AVAILABLE" if installed else "NOT_CONFIGURED",
                install_command=install,
                uninstall_command=uninstall,
            )
        except Exception:  # noqa: BLE001
            return BrowserHealth(
                dependency="installed",
                browser="unavailable",
                executable=None,
                state="NOT_CONFIGURED",
                install_command=install,
                uninstall_command=uninstall,
            )

    def render(
        self,
        url: str,
        *,
        wait_until: str = "networkidle",
        timeout_ms: int = 30_000,
        width: int = 1440,
        height: int = 900,
        full_page: bool = False,
        include_screenshot: bool = False,
        block_resource_types: tuple[str, ...] = (),
        user_agent: str = "World-Class-SEO-Render/1.0",
    ) -> dict[str, Any]:
        health = self.health()
        if health.state != "AVAILABLE":
            raise BrowserNotConfigured(
                "Playwright Chromium is not installed. " + health.install_command
            )
        if wait_until not in _WAIT_UNTIL:
            raise ValueError(f"wait_until must be one of {sorted(_WAIT_UNTIL)}")
        if not isinstance(timeout_ms, int) or not 1_000 <= timeout_ms <= 120_000:
            raise ValueError("timeout_ms must be an integer from 1000 to 120000")
        if not isinstance(width, int) or not 320 <= width <= 7680:
            raise ValueError("width must be an integer from 320 to 7680")
        if not isinstance(height, int) or not 200 <= height <= 4320:
            raise ValueError("height must be an integer from 200 to 4320")
        blocked = tuple(block_resource_types)
        if any(resource not in _RESOURCE_TYPES for resource in blocked):
            raise ValueError(
                f"block_resource_types must use {sorted(_RESOURCE_TYPES)}"
            )
        safe_url = validate_public_url(url)

        return render_browser(
            safe_url, timeout_ms=timeout_ms, wait_until=wait_until,
            width=width, height=height, include_screenshot=include_screenshot,
            full_page=full_page, block_resource_types=blocked, user_agent=user_agent,
        )


class RenderedPageService:
    name = "rendered_page"

    def __init__(self, *, renderer: BrowserRenderer | None = None) -> None:
        self.renderer = renderer or PlaywrightRenderer()

    def health(self) -> BrowserHealth:
        return self.renderer.health()

    def render(
        self,
        url: str,
        *,
        wait_until: str = "networkidle",
        timeout_ms: int = 30_000,
        width: int = 1440,
        height: int = 900,
        block_resource_types: tuple[str, ...] = (),
        **_: Any,
    ) -> AdapterResult:
        safe_url = validate_public_url(url)
        try:
            result = self.renderer.render(
                safe_url,
                wait_until=wait_until,
                timeout_ms=timeout_ms,
                width=width,
                height=height,
                include_screenshot=False,
                block_resource_types=block_resource_types,
            )
        except BrowserNotConfigured as exc:
            return AdapterResult(
                source=self.name,
                status="not_configured",
                data={
                    "url": safe_url,
                    "rendered": False,
                    "data_state": "NOT_CONFIGURED",
                    "health": asdict(self.health()),
                    "html": None,
                    "text": None,
                },
                warnings=[str(exc)],
            )
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(
                source=self.name,
                status="failed",
                data={
                    "url": safe_url,
                    "rendered": False,
                    "data_state": "FAILED",
                    "html": None,
                    "text": None,
                },
                warnings=[f"render_failed: {type(exc).__name__}: {exc}"],
            )
        data = {
            key: value
            for key, value in result.items()
            if key != "screenshot_bytes"
        }
        data.update(
            {
                "rendered": True,
                "data_state": "AVAILABLE",
                "evidence": {
                    "rendered_html": "VERIFIED",
                    "screenshot": "NOT_RUN",
                },
            }
        )
        return AdapterResult(
            source=self.name,
            status="ok",
            data=data,
            warnings=[],
        )

    def screenshot(
        self,
        url: str,
        *,
        output: str | os.PathLike[str],
        full_page: bool = False,
        wait_until: str = "networkidle",
        timeout_ms: int = 30_000,
        width: int = 1440,
        height: int = 900,
        block_resource_types: tuple[str, ...] = (),
        **_: Any,
    ) -> AdapterResult:
        safe_url = validate_public_url(url)
        path = Path(output).expanduser()
        if path.suffix.lower() != ".png":
            raise ValueError("screenshot output must use a .png extension")
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            result = self.renderer.render(
                safe_url,
                wait_until=wait_until,
                timeout_ms=timeout_ms,
                width=width,
                height=height,
                full_page=full_page,
                include_screenshot=True,
                block_resource_types=block_resource_types,
            )
        except BrowserNotConfigured as exc:
            return AdapterResult(
                source=self.name,
                status="not_configured",
                data={
                    "url": safe_url,
                    "path": str(path),
                    "rendered": False,
                    "data_state": "NOT_CONFIGURED",
                    "health": asdict(self.health()),
                },
                warnings=[str(exc)],
            )
        except Exception as exc:  # noqa: BLE001
            return AdapterResult(
                source=self.name,
                status="failed",
                data={
                    "url": safe_url,
                    "path": str(path),
                    "rendered": False,
                    "data_state": "FAILED",
                },
                warnings=[f"screenshot_failed: {type(exc).__name__}: {exc}"],
            )
        return self._persist_screenshot(result, safe_url, path, full_page)

    def _persist_screenshot(
        self, result: dict[str, Any], safe_url: str, path: Path, full_page: bool,
    ) -> AdapterResult:
        screenshot = result.get("screenshot_bytes")
        if (
            not isinstance(screenshot, (bytes, bytearray))
            or not bytes(screenshot).startswith(b"\x89PNG")
        ):
            return AdapterResult(
                source=self.name,
                status="invalid_response",
                data={
                    "url": safe_url,
                    "path": str(path),
                    "rendered": True,
                    "data_state": "INVALID_RESPONSE",
                },
                warnings=[
                    "Browser renderer did not return a valid PNG screenshot."
                ],
            )
        if len(screenshot) > 25_000_000:
            return AdapterResult(
                source=self.name,
                status="invalid_response",
                data={
                    "url": safe_url,
                    "path": str(path),
                    "rendered": True,
                    "data_state": "INVALID_RESPONSE",
                },
                warnings=["Screenshot exceeds the 25 MB output ceiling."],
            )
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(bytes(screenshot))
        temporary.replace(path)
        return AdapterResult(
            source=self.name,
            status="ok",
            data={
                "url": safe_url,
                "final_url": result.get("final_url"),
                "path": str(path),
                "bytes": len(screenshot),
                "full_page": bool(full_page),
                "viewport": result.get("viewport"),
                "render_engine": result.get("render_engine"),
                "render_ms": result.get("render_ms"),
                "rendered": True,
                "data_state": "AVAILABLE",
                "evidence": {
                    "rendered_html": "VERIFIED",
                    "screenshot": "VERIFIED",
                },
            },
            warnings=[],
        )
