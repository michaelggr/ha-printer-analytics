"""图片下载管理模块"""
import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import aiohttp

from .const import (
    HTTP_REQUEST_TIMEOUT_SECS,
    IMAGE_MIN_SIZE_BYTES,
)
from .utils import SecureFileHandler

if TYPE_CHECKING:
    from .coordinator import PrinterAnalyticsCoordinator

LOGGER = logging.getLogger(__name__)


class ImageManager:
    """图片下载管理器"""

    _PLACEHOLDER_IMAGE_HASHES: set[str] = {
        "5a52bcafb0656745b398b5a811640c90",
        "c1aad0332d82134d188d487939f7e978",
        "2cd67ef2c163fa3cb59ac22fbee5d738",  # Bambu Cloud 默认占位图 (512x512 PNG, 4530B)
    }

    def __init__(self, coordinator: "PrinterAnalyticsCoordinator") -> None:
        self.coordinator = coordinator
        self.hass = coordinator.hass
        self._images_dir = coordinator._images_dir
        self._entity_map = coordinator._entity_map
        self.printer_name = coordinator.printer_name

    def detect_placeholder_images(self) -> int:
        """扫描已有封面图，自动检测并删除占位图，返回清理数量"""
        if not os.path.isdir(self._images_dir):
            return 0

        hash_counts: dict[str, int] = {}
        hash_to_files: dict[str, list[str]] = {}
        for fname in os.listdir(self._images_dir):
            if not fname.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            fpath = os.path.join(self._images_dir, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                with open(fpath, "rb") as f:
                    h = hashlib.md5(f.read()).hexdigest()
                hash_counts[h] = hash_counts.get(h, 0) + 1
                hash_to_files.setdefault(h, []).append(fname)
            except OSError:
                pass

        cleaned = 0
        for h, count in hash_counts.items():
            if count >= 3 or h in self._PLACEHOLDER_IMAGE_HASHES:
                self._PLACEHOLDER_IMAGE_HASHES.add(h)
                LOGGER.info("Detected placeholder image hash %s (%d identical files)", h[:12], count)
                # 删除占位图文件
                for fname in hash_to_files.get(h, []):
                    fpath = os.path.join(self._images_dir, fname)
                    try:
                        os.remove(fpath)
                        cleaned += 1
                    except OSError:
                        pass

        if cleaned > 0:
            LOGGER.info("Cleaned %d placeholder image files", cleaned)
        return cleaned

    @classmethod
    def _is_placeholder_image(cls, content: bytes) -> bool:
        """检查图片是否为占位图"""
        if not cls._PLACEHOLDER_IMAGE_HASHES:
            return False
        return hashlib.md5(content).hexdigest() in cls._PLACEHOLDER_IMAGE_HASHES

    def _get_bambu_cloud_client(self):
        """获取Bambu Cloud客户端"""
        bambu_domain = "bambu_lab"
        if bambu_domain not in self.hass.data:
            return None

        for entry_id, coord in self.hass.data[bambu_domain].items():
            if entry_id == "service_call_future":
                continue
            client = getattr(coord, "client", None)
            if client and hasattr(client, "bambu_cloud"):
                cloud = client.bambu_cloud
                if getattr(cloud, "bambu_connected", False):
                    serial = getattr(client, "_serial", "")
                    if serial.upper() == self._get_printer_serial().upper():
                        return cloud

        for entry_id, coord in self.hass.data[bambu_domain].items():
            if entry_id == "service_call_future":
                continue
            client = getattr(coord, "client", None)
            if client and hasattr(client, "bambu_cloud"):
                cloud = client.bambu_cloud
                if getattr(cloud, "bambu_connected", False):
                    return cloud

        return None

    def _get_printer_serial(self) -> str:
        """从实体ID中提取打印机序列号"""
        serial_entity = self._entity_map.get("serial_number", "")
        if serial_entity:
            state = self.hass.states.get(serial_entity)
            if state and state.state not in {"unknown", "unavailable", ""}:
                return state.state

        cover_entity = self._entity_map.get("cover_image", "")
        if cover_entity:
            match = re.search(r'image\.\w+_(\w+)_cover_image', cover_entity)
            if match:
                return match.group(1).upper()

        return ""

    async def _download_cover_from_cloud(self, task_name: str, end_time: str, start_time: str = "") -> str | None:
        """从云端下载封面"""
        try:
            cloud = self._get_bambu_cloud_client()
            if not cloud:
                LOGGER.warning("No Bambu Cloud client available")
                return None

            serial = self._get_printer_serial()
            if not serial:
                LOGGER.warning("Cannot determine printer serial")
                return None

            def _get_cloud_tasks():
                return cloud.get_tasklist_for_printer(serial)

            tasks = await self.hass.async_add_executor_job(_get_cloud_tasks)
            if not tasks:
                LOGGER.info("No cloud tasks found")
                return None

            end_dt = self.coordinator._normalize_to_utc(end_time) if end_time else None
            start_dt = self.coordinator._normalize_to_utc(start_time) if start_time else None

            best_match = None
            best_score = 999999
            for task in tasks:
                task_end = task.get("endTime", "")
                task_start = task.get("startTime", "")
                if not task_end:
                    continue
                try:
                    task_end_dt = datetime.fromisoformat(task_end.replace("Z", "+00:00"))
                    if not end_dt:
                        continue
                    end_diff = abs((task_end_dt - end_dt).total_seconds())
                    if end_diff > 600:
                        continue
                    score = end_diff
                    task_start_dt = datetime.fromisoformat(task_start.replace("Z", "+00:00")) if task_start else None
                    if task_start_dt and start_dt:
                        start_diff = abs((task_start_dt - start_dt).total_seconds())
                        score = end_diff + start_diff
                    if score < best_score:
                        best_score = score
                        cover_url = task.get("cover", "")
                        if cover_url:
                            best_match = {"cover_url": cover_url, "score": score, "title": task.get("designTitle", "")}
                except (ValueError, TypeError):
                    continue

            if not best_match or not best_match["cover_url"]:
                return None

            if best_score > 600:
                LOGGER.info("Cloud task match too imprecise (score=%d)", best_score)
                return None

            cover_url = best_match["cover_url"]

            safe_task_name = SecureFileHandler.sanitize_filename(task_name or "unknown")
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}.jpg"

            def _ensure_dir():
                os.makedirs(self._images_dir, exist_ok=True)
            await self.hass.async_add_executor_job(_ensure_dir)

            filepath = SecureFileHandler.safe_join(self._images_dir, filename)
            if not filepath:
                return None

            def _download():
                return cloud.download(cover_url)

            content = await self.hass.async_add_executor_job(_download)
            if not content or len(content) < IMAGE_MIN_SIZE_BYTES:
                LOGGER.warning("Cloud cover download failed")
                return None

            if self._is_placeholder_image(content):
                LOGGER.warning("Cloud cover is a placeholder")
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/{filename}"
            LOGGER.info("Cloud cover saved: %s (%d bytes)", local_path, len(content))
            return local_path

        except Exception as err:
            LOGGER.error("Failed to download cover from cloud: %s", err)
            return None

    async def _download_cover_image(self, image_url: str, task_name: str, end_time: str, prefer_http: bool = False) -> str | None:
        """下载封面图片

        prefer_http: 为 True 时跳过 HA 实体获取，直接用 HTTP 下载
                     （用于 backfill 历史记录，避免用当前打印的封面）
        """
        try:
            content = None

            # 优先 HTTP 下载（历史记录场景）
            if prefer_http and image_url:
                content = await self._download_image_via_http(image_url)
                if not content or len(content) < IMAGE_MIN_SIZE_BYTES or self._is_placeholder_image(content):
                    content = None

            # 从 HA 实体获取（当前打印场景）
            if not content and not prefer_http:
                cover_entity = self._entity_map.get("cover_image")
                if not cover_entity:
                    prefix = self.printer_name.lower()
                    image_entities = list(self.hass.states.async_entity_ids("image"))
                    for eid in image_entities:
                        if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                            cover_entity = eid
                            break

                if cover_entity:
                    try:
                        from homeassistant.components.image import async_get_image as async_get_cover_image
                        img = await async_get_cover_image(self.hass, cover_entity)
                        content = img.content
                        LOGGER.debug("Cover obtained via image API (%d bytes)", len(content))
                    except Exception as img_err:
                        LOGGER.debug("image async_get_image failed: %s, trying HTTP", img_err)
                        content = None

            # HTTP 下载回退
            if not content:
                download_url = image_url
                if not prefer_http:
                    cover_entity = self._entity_map.get("cover_image") or ""
                    if not cover_entity:
                        prefix = self.printer_name.lower()
                        for eid in self.hass.states.async_entity_ids("image"):
                            if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                                cover_entity = eid
                                break
                    if cover_entity:
                        state = self.hass.states.get(cover_entity)
                        if state:
                            entity_picture = state.attributes.get("entity_picture", "")
                            if entity_picture:
                                download_url = entity_picture
                content = await self._download_image_via_http(download_url)
                if not content:
                    return None

            if len(content) < IMAGE_MIN_SIZE_BYTES:
                LOGGER.warning("Cover image too small (%d bytes)", len(content))
                return None

            if self._is_placeholder_image(content):
                LOGGER.warning("Cover image is a placeholder")
                return None

            safe_task_name = SecureFileHandler.sanitize_filename(task_name)
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}.jpg"

            def _ensure_dir():
                os.makedirs(self._images_dir, exist_ok=True)
            await self.hass.async_add_executor_job(_ensure_dir)

            filepath = SecureFileHandler.safe_join(self._images_dir, filename)
            if not filepath:
                LOGGER.error("Invalid file path (path traversal blocked)")
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/{filename}"
            LOGGER.info("Cover saved: %s (%d bytes)", local_path, len(content))
            return local_path

        except Exception as err:
            LOGGER.error("Failed to download cover image: %s", err)
            return None

    async def _try_get_cover_from_entity(self, task_name: str, end_time: str) -> str | None:
        """从实体获取封面（最后手段）"""
        try:
            cover_entity = self._entity_map.get("cover_image")
            if not cover_entity:
                prefix = self.printer_name.lower()
                for eid in self.hass.states.async_entity_ids("image"):
                    if eid.startswith(f"image.{prefix}_") and eid.endswith("_cover_image"):
                        cover_entity = eid
                        break
            if not cover_entity:
                return None

            from homeassistant.components.image import async_get_image as async_get_cover_image
            img = await async_get_cover_image(self.hass, cover_entity)
            content = img.content
            if not content or len(content) < IMAGE_MIN_SIZE_BYTES:
                return None
            if self._is_placeholder_image(content):
                return None

            safe_task_name = SecureFileHandler.sanitize_filename(task_name)
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}.jpg"

            def _ensure_dir():
                os.makedirs(self._images_dir, exist_ok=True)
            await self.hass.async_add_executor_job(_ensure_dir)

            filepath = SecureFileHandler.safe_join(self._images_dir, filename)
            if not filepath:
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/{filename}"
            LOGGER.info("Cover from entity fallback: %s (%d bytes)", local_path, len(content))
            return local_path

        except Exception as err:
            LOGGER.debug("Entity cover fallback failed: %s", err)
            return None

    async def _download_image_via_http(self, download_url: str) -> bytes | None:
        """通过HTTP下载图片，自动附加access_token认证"""
        try:
            if not download_url:
                return None

            if download_url.startswith("http://") or download_url.startswith("https://"):
                full_url = download_url
            else:
                base_url = self.coordinator._get_ha_base_url()
                full_url = f"{base_url}{download_url}"

            # 如果URL中已有token参数，直接使用；否则尝试从实体获取
            if "?token=" not in full_url:
                # 尝试从cover_image实体获取access_token
                cover_entity = self._entity_map.get("cover_image", "")
                if cover_entity:
                    state = self.hass.states.get(cover_entity)
                    if state:
                        at = state.attributes.get("access_token", "")
                        if at:
                            sep = "&" if "?" in full_url else "?"
                            full_url = f"{full_url}{sep}token={at}"

            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            session = async_get_clientsession(self.hass)
            headers = self.coordinator._get_auth_headers()
            async with session.get(full_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=HTTP_REQUEST_TIMEOUT_SECS)) as resp:
                if resp.status != 200:
                    LOGGER.warning("HTTP download failed: HTTP %d", resp.status)
                    return None
                return await resp.read()
        except Exception as err:
            LOGGER.warning("HTTP download error: %s", err)
            return None

    async def _download_print_snapshot(self, end_time: str, task_name: str) -> str | None:
        """下载打印快照

        抓取前自动打开舱内灯（如果关闭），抓取后恢复原状态
        """
        # 记录舱内灯原始状态，抓取前打开
        light_entity = self._entity_map.get("chamber_light")
        light_was_on = True  # 默认认为灯是开着的，不需要恢复
        if light_entity:
            light_state = self.hass.states.get(light_entity)
            light_was_on = light_state is not None and light_state.state == "on"
            if not light_was_on:
                await self.hass.services.async_call(
                    "light", "turn_on",
                    {"entity_id": light_entity},
                    blocking=True,
                )
                # 等待灯亮起后再抓取，给摄像头适应时间
                await asyncio.sleep(2)

        try:
            return await self._do_download_snapshot(end_time, task_name)
        finally:
            # 恢复舱内灯原始状态
            if light_entity and not light_was_on:
                await self.hass.services.async_call(
                    "light", "turn_off",
                    {"entity_id": light_entity},
                    blocking=False,
                )

    async def _do_download_snapshot(self, end_time: str, task_name: str) -> str | None:
        """实际下载快照逻辑"""
        try:
            camera_entity = self._entity_map.get("camera")
            if not camera_entity:
                prefix = self.printer_name.lower()
                camera_entities = list(self.hass.states.async_entity_ids("camera"))
                for eid in camera_entities:
                    if eid.startswith(f"camera.{prefix}_") and eid.endswith("_camera"):
                        camera_entity = eid
                        break

            if not camera_entity:
                LOGGER.warning("No camera entity found")
                return None

            from homeassistant.components.camera import async_get_image
            try:
                image = await async_get_image(self.hass, camera_entity)
                content = image.content
            except Exception as cam_err:
                LOGGER.warning("Camera async_get_image failed for %s: %s", camera_entity, cam_err)
                content = await self._snapshot_http_fallback(camera_entity)

            if not content or len(content) < IMAGE_MIN_SIZE_BYTES:
                LOGGER.warning("Snapshot too small (%s bytes)", len(content) if content else 0)
                return None

            safe_task_name = SecureFileHandler.sanitize_filename(task_name or "unknown")
            safe_time = re.sub(r'[^\dT]', '_', (end_time or '')[:19])
            filename = f"{safe_task_name}_{safe_time}_snapshot.jpg"

            def _ensure_dir():
                snapshots_dir = os.path.join(self._images_dir, "snapshots")
                os.makedirs(snapshots_dir, exist_ok=True)
                return snapshots_dir

            snapshots_dir = await self.hass.async_add_executor_job(_ensure_dir)
            filepath = SecureFileHandler.safe_join(snapshots_dir, filename)
            if not filepath:
                return None

            def _write():
                with open(filepath, "wb") as f:
                    f.write(content)
            await self.hass.async_add_executor_job(_write)

            local_path = f"/local/printer_analytics/snapshots/{filename}"
            LOGGER.info("Snapshot saved: %s (%d bytes)", local_path, len(content))
            return local_path

        except Exception as err:
            LOGGER.error("Failed to download snapshot: %s", err)
            return None

    async def _snapshot_http_fallback(self, camera_entity: str) -> bytes | None:
        """HTTP方式获取快照（备用），优先使用实体access_token认证"""
        try:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession
            session = async_get_clientsession(self.hass)
            base_url = self.coordinator._get_ha_base_url()

            # 优先从摄像头实体获取 access_token（HA自动生成的短期令牌）
            cam_state = self.hass.states.get(camera_entity)
            access_token = ""
            if cam_state:
                access_token = cam_state.attributes.get("access_token", "")

            if access_token:
                snapshot_url = f"{base_url}/api/camera_proxy/{camera_entity}?token={access_token}"
            else:
                snapshot_url = f"{base_url}/api/camera_proxy/{camera_entity}"

            headers = self.coordinator._get_auth_headers()
            async with session.get(snapshot_url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=HTTP_REQUEST_TIMEOUT_SECS)) as resp:
                if resp.status != 200:
                    LOGGER.warning("HTTP snapshot fallback failed: HTTP %d", resp.status)
                    return None
                return await resp.read()
        except Exception as err:
            LOGGER.warning("HTTP snapshot fallback error: %s", err)
            return None

    async def _delete_image_file(self, local_path: str) -> None:
        """删除本地图片文件"""
        if not local_path:
            return
        try:
            full_path = os.path.join(self.hass.config.path("www"), local_path.lstrip("/"))
            if os.path.isfile(full_path):
                os.remove(full_path)
        except OSError:
            pass

    async def backfill_cover_images(self, full_scan: bool = False) -> int:
        """补全缺失的封面图

        full_scan=True 时直接从文件读取全量数据（用于 Cloud 同步后批量补图），
        默认 False 只处理内存缓存中的记录。

        full_scan 模式下：
        - 不使用 HA 实体回退（实体只返回当前打印的封面，历史记录用会全部相同）
        - 增加批量重复检测：同一张图片被用于超过 3 条记录时视为可疑默认图
        """
        updated = 0
        cleaned = 0

        # 全量模式：从文件读取所有记录
        if full_scan:
            records = self._load_all_records()
            save_after = True
        else:
            records = self.coordinator.history
            save_after = False

        # 批量重复检测：记录每张下载图片的 MD5，超过阈值视为默认图
        batch_md5_counts: dict[str, int] = {}
        BATCH_DUPLICATE_THRESHOLD = 3  # 同一图片超过此数量视为可疑

        for record in records:
            existing = record.get("cover_image_local")
            if existing:
                local_file = os.path.join(
                    self.hass.config.path("www"),
                    existing.lstrip("/"),
                )
                if os.path.isfile(local_file):
                    try:
                        with open(local_file, "rb") as f:
                            h = hashlib.md5(f.read()).hexdigest()
                        if h in self._PLACEHOLDER_IMAGE_HASHES:
                            os.remove(local_file)
                            record["cover_image_local"] = None
                            cleaned += 1
                            LOGGER.info("Removed placeholder cover: %s", existing)
                            continue
                    except OSError:
                        pass
                    continue
                record["cover_image_local"] = None

            cover_url = record.get("cover_image_url", "")
            task_name = record.get("task_name", "unknown")
            end_time = record.get("end_time", "")
            start_time = record.get("start_time", "")

            # 下载优先级：
            # 1. CDN/OSS URL 直接 HTTP 下载
            # 2. Bambu Cloud API 按任务名查找
            # 3. 原始 URL HTTP 下载（非 /api/ 开头的内部地址）
            # full_scan 模式不使用实体回退（避免所有历史记录都用当前打印封面）
            local_path = None
            if cover_url and ("bblmw.cn" in cover_url or "bbl-prod-model" in cover_url):
                local_path = await self._download_cover_image(cover_url, task_name or "unknown", end_time or "", prefer_http=True)
            if not local_path:
                local_path = await self._download_cover_from_cloud(task_name or "unknown", end_time or "", start_time or "")
            if not local_path and cover_url and not cover_url.startswith("/api/"):
                # 跳过 HA 内部代理 URL（/api/image_proxy/...），这些无法直接 HTTP 下载
                local_path = await self._download_cover_image(cover_url, task_name or "unknown", end_time or "", prefer_http=True)
            if not local_path and not full_scan:
                # 仅非全量模式才回退到实体获取
                local_path = await self._try_get_cover_from_entity(task_name or "unknown", end_time or "")

            if local_path:
                # 全量模式下检测批量重复
                if full_scan:
                    try:
                        full_path = os.path.join(self.hass.config.path("www"), local_path.lstrip("/"))
                        with open(full_path, "rb") as f:
                            img_md5 = hashlib.md5(f.read()).hexdigest()
                        count = batch_md5_counts.get(img_md5, 0) + 1
                        batch_md5_counts[img_md5] = count
                        if count > BATCH_DUPLICATE_THRESHOLD:
                            # 超过阈值：删除刚下载的可疑图片，视为默认图
                            os.remove(full_path)
                            LOGGER.warning(
                                "Batch dup: md5=%s used %dx (>%d), treating as default image: %s",
                                img_md5[:12], count, BATCH_DUPLICATE_THRESHOLD,
                                task_name[:30],
                            )
                            local_path = None
                    except OSError:
                        pass

                if local_path:
                    record["cover_image_local"] = local_path
                    updated += 1

        if batch_md5_counts:
            dup_info = {k: v for k, v in batch_md5_counts.items() if v > BATCH_DUPLICATE_THRESHOLD}
            if dup_info:
                LOGGER.warning("Batch dup detection: %d image(s) used >%d times as covers",
                               len(dup_info), BATCH_DUPLICATE_THRESHOLD)

        if updated > 0 or cleaned > 0:
            if full_scan and save_after:
                # 全量模式：直接保存到文件（records 是从文件读取的引用）
                self._save_all_records(records)
            else:
                self.hass.async_create_task(self.coordinator._save_history())
            LOGGER.info("Backfilled %d, cleaned %d covers (full_scan=%s)", updated, cleaned, full_scan)

        return updated

    def _load_all_records(self) -> list[dict]:
        """从年份文件读取全量历史记录（供 full_scan 模式使用）"""
        import json as _json
        import os as _os

        if not self.coordinator or not self.coordinator.storage:
            return []

        history_dir = self.coordinator.storage._history_dir
        if not _os.path.isdir(history_dir):
            return []

        storage_key = self.coordinator.storage._storage_key
        all_records: list[dict] = []

        for f in sorted(_os.listdir(history_dir)):
            if f.startswith(f"{storage_key}_") and f.endswith(".json") and not f.endswith("_stats.json"):
                file_path = _os.path.join(history_dir, f)
                try:
                    with open(file_path, "r", encoding="utf-8") as fh:
                        data = _json.load(fh)
                    records = data.get("history", []) if isinstance(data, dict) else data
                    all_records.extend(records)
                except Exception as err:
                    LOGGER.warning("_load_all_records: 读取文件失败 %s: %s", f, err)

        LOGGER.info("_load_all_records: 从文件读取 %d 条记录", len(all_records))
        return all_records

    def _save_all_records(self, records: list[dict]) -> None:
        """将全量记录按年份分组写回文件（供 full_scan 模式使用）"""
        import json as _json
        import os as _os

        if not self.coordinator or not self.coordinator.storage:
            return

        history_dir = self.coordinator.storage._history_dir
        storage_key = self.coordinator.storage._storage_key

        # 按年份分组
        records_by_year: dict[int, list[dict]] = {}
        for record in records:
            year = self.coordinator.storage._extract_year_from_end_time(record.get("end_time", ""))
            if year not in records_by_year:
                records_by_year[year] = []
            records_by_year[year].append(record)

        saved = 0
        for year, year_records in records_by_year.items():
            file_path = _os.path.join(history_dir, f"{storage_key}_{year}.json")
            try:
                with open(file_path, "w", encoding="utf-8") as fh:
                    _json.dump({"history": year_records}, fh, ensure_ascii=False, indent=2)
                saved += len(year_records)
            except Exception as err:
                LOGGER.error("_save_all_records: 写入失败 %s: %s", file_path, err)

        # 更新内存缓存（只保留最近50条）
        records.sort(key=lambda x: x.get("end_time", ""))
        self.coordinator.history = records[-50:] if len(records) > 50 else records
        self.coordinator._total_records = len(records)

        LOGGER.info("_save_all_records: 写入 %d 个年份文件, 共 %d 条记录 (缓存 %d)",
                     len(records_by_year), saved, len(self.coordinator.history))

    async def backfill_snapshots(self) -> int:
        """补全缺失的快照"""
        updated = 0

        for record in self.coordinator.history:
            existing = record.get("snapshot_image_local")
            if existing:
                local_file = os.path.join(
                    self.hass.config.path("www"),
                    existing.lstrip("/"),
                )
                if os.path.isfile(local_file):
                    continue
                record["snapshot_image_local"] = None

            task_name = record.get("task_name", "unknown")
            end_time = record.get("end_time", "")
            local_path = await self._download_print_snapshot(end_time or "", task_name or "unknown")

            if local_path:
                record["snapshot_image_local"] = local_path
                updated += 1

        if updated > 0:
            self.hass.async_create_task(self.coordinator._save_history())
            LOGGER.info("Backfilled %d snapshots", updated)

        return updated
