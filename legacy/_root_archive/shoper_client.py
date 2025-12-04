import logging
import os
import time
import json
from typing import Optional
import re

import requests


logger = logging.getLogger(__name__)


class ShoperClient:
    """Minimal wrapper for Shoper REST API."""

    def __init__(self, base_url=None, token=None, client_id=None):
        env_url = os.getenv("SHOPER_BASE_URL", "").strip()
        raw_url = (base_url or env_url).strip()
        self.base_url = self._normalize_base_url(raw_url)
        env_token = os.getenv("SHOPER_ACCESS_TOKEN", "").strip()
        env_client_id = os.getenv("SHOPER_CLIENT_ID", "").strip()
        self.client_id = (client_id or env_client_id).strip() or None
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        raw_token = token or env_token
        if not self.base_url or not raw_token:
            raise ValueError("SHOPER_BASE_URL or SHOPER_ACCESS_TOKEN not set")

        self._client_secret: Optional[str] = None
        self._token_expires_at: float = 0.0
        self.token: Optional[str] = None

        if self.client_id:
            self._client_secret = raw_token
            self._authenticate(force=True)
        else:
            self.token = raw_token
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}",
            })

        # Runtime flag to dump outgoing product payloads to terminal
        self.dump_payload = self._env_flag(
            "SHOPER_LOG_PRODUCT_PAYLOAD"
        ) or self._env_flag("SHOPER_LOG_PAYLOAD") or self._env_flag(
            "SHOPER_DEBUG_PAYLOAD"
        )
        self.sanitize_html = self._env_flag("SHOPER_SANITIZE_HTML") or True

    SENSITIVE_LOG_KEYS = {
        "password",
        "token",
        "authorization",
        "api_key",
        "client_secret",
        "secret",
        "access_token",
        "refresh_token",
    }

    def _request(self, method, endpoint, **kwargs):
        """Send a request to the Shoper API.

        Parameters are passed directly to ``requests.Session.request``.
        The returned value is the parsed JSON response or ``{}`` when the
        response body is empty. If the API responds with ``404`` the method
        also returns an empty dictionary instead of raising an exception.

        Any other HTTP error results in a ``RuntimeError`` being raised.
        """

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        method_upper = method.upper()
        if method_upper in {"POST", "PUT", "PATCH"}:
            body = kwargs.get("json")
            if body is not None:
                sanitized_body = self._redact_sensitive_for_logging(body)
                if logger.isEnabledFor(logging.DEBUG):
                    try:
                        body_dump = json.dumps(
                            sanitized_body, ensure_ascii=False, default=str
                        )
                    except TypeError:
                        body_dump = str(sanitized_body)
                    logger.debug(
                        "Shoper API %s request payload: %s", method_upper, body_dump
                    )
                # Optional human-friendly dump to terminal for product endpoints
                if self.dump_payload and str(endpoint).startswith("products"):
                    try:
                        pretty = json.dumps(
                            sanitized_body, ensure_ascii=False, indent=2, default=str
                        )
                    except TypeError:
                        pretty = str(sanitized_body)
                    logger.info(
                        "\n==== Shoper OUT %s %s payload ====:\n%s\n===============================",
                        method_upper,
                        endpoint,
                        pretty,
                    )
        self._ensure_token()
        attempt = 0
        while True:
            try:
                resp = self.session.request(method, url, timeout=15, **kwargs)
            except requests.RequestException as exc:
                raise RuntimeError(f"API request failed: {exc}") from exc

            if resp.status_code == 401 and self.client_id and attempt == 0:
                # Access token expired – refresh and retry once.
                self._authenticate(force=True)
                attempt += 1
                continue

            try:
                resp.raise_for_status()
            except requests.HTTPError as exc:
                response = exc.response
                if response is not None and response.status_code == 404:
                    return {}

                error_message = "API request failed"
                if response is not None:
                    error_message = f"API request failed ({response.status_code})"

                    detail_parts: list[str] = []
                    content_type = response.headers.get("Content-Type", "")
                    payload = None
                    if "json" in content_type:
                        try:
                            payload = response.json()
                        except ValueError:
                            payload = None
                    if isinstance(payload, dict):
                        base_detail = payload.get("error") or payload.get("message")
                        if isinstance(base_detail, str) and base_detail.strip():
                            detail_parts.append(base_detail.strip())

                        error_description = payload.get("error_description")
                        if isinstance(error_description, str) and error_description.strip():
                            detail_parts.append(error_description.strip())

                        localized = payload.get("error_descriptions") or payload.get(
                            "error_description_translations"
                        )
                        if isinstance(localized, dict):
                            for locale, description in localized.items():
                                if not description:
                                    continue
                                description_text = str(description).strip()
                                if description_text:
                                    detail_parts.append(f"{locale}: {description_text}")

                        errors = payload.get("errors")
                        if errors:
                            formatted_errors: list[str] = []
                            if isinstance(errors, dict):
                                for field, messages in errors.items():
                                    if messages is None:
                                        continue
                                    if isinstance(messages, (list, tuple, set)):
                                        msg_text = "; ".join(
                                            str(msg).strip()
                                            for msg in messages
                                            if str(msg).strip()
                                        )
                                    elif isinstance(messages, dict):
                                        msg_text = "; ".join(
                                            f"{key}: {value}"
                                            for key, value in messages.items()
                                            if value not in (None, "")
                                        )
                                    else:
                                        msg_text = str(messages).strip()
                                    if msg_text:
                                        formatted_errors.append(f"{field}: {msg_text}")
                                if formatted_errors:
                                    detail_parts.append(
                                        "errors: " + " | ".join(formatted_errors)
                                    )
                            else:
                                detail_parts.append(
                                    "errors: " + json.dumps(errors, ensure_ascii=False)
                                )

                        if not detail_parts:
                            detail_parts.append(json.dumps(payload, ensure_ascii=False))
                    elif isinstance(payload, list):
                        detail_parts.append(json.dumps(payload, ensure_ascii=False))

                    if not detail_parts:
                        text = response.text.strip()
                        if text:
                            detail_parts.append(text)

                    if detail_parts:
                        detail = " | ".join(detail_parts)[:2000]
                        error_message = f"{error_message}: {detail}"

                    # Extra diagnostic log with full body for POST/PUT/PATCH
                    if method_upper in {"POST", "PUT", "PATCH"}:
                        try:
                            dump = response.text or ""
                            if not dump and hasattr(response, "content"):
                                dump = str(response.content)
                            logger.error(
                                "Shoper API %s %s failed (%s). Body: %s",
                                method_upper,
                                url,
                                response.status_code,
                                (dump[:4000] if dump else "<empty>"),
                            )
                        except Exception:
                            pass

                raise RuntimeError(error_message) from exc

            logger.info(
                "Shoper API %s %s succeeded with status %s",
                method.upper(),
                url,
                resp.status_code,
            )

            if resp.text:
                return resp.json()
            return {}

    @classmethod
    def _redact_sensitive_for_logging(cls, payload):
        if isinstance(payload, dict):
            redacted: dict = {}
            for key, value in payload.items():
                key_text = str(key).lower()
                if key_text in cls.SENSITIVE_LOG_KEYS:
                    redacted[key] = "***REDACTED***"
                else:
                    redacted[key] = cls._redact_sensitive_for_logging(value)
            return redacted
        if isinstance(payload, list):
            return [cls._redact_sensitive_for_logging(item) for item in payload]
        return payload

    def get(self, endpoint, **kwargs):
        return self._request("GET", endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self._request("POST", endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        return self._request("PUT", endpoint, **kwargs)

    def patch(self, endpoint, **kwargs):
        return self._request("PATCH", endpoint, **kwargs)

    def add_product(self, data):
        try:
            # Always minimize translations for create: only default language + name
            create_payload = self._apply_create_minimal_translations(data)
            ret = self.post("products", json=create_payload)
            if not isinstance(ret, dict):
                ret = {}
            return ret
        except RuntimeError as exc:
            msg = str(exc)
            # Some Shoper installations intermittently return 500 on product create
            # when optional fields are present. Retry with a minimal payload.
            if "(500)" in msg or "server_error" in msg.lower():
                logger.warning(
                    "Shoper returned 500 on product create. Retrying with minimal payload."
                )
                try:
                    # Attempt ultra-minimal payload first (code + price + stock + active)
                    ultramin = self._build_ultramin_product_payload(data)
                    try:
                        pretty_u = json.dumps(ultramin, ensure_ascii=False, indent=2, default=str)
                    except TypeError:
                        pretty_u = str(ultramin)
                    logger.info(
                        "\n==== Shoper OUT RETRY POST products (ultramin) ====:\n%s\n===============================================",
                        pretty_u,
                    )
                    ret = self.post("products", json=ultramin)
                    if not isinstance(ret, dict):
                        ret = {}
                    return ret
                except Exception:
                    # Fall back to slightly richer minimal payload
                    minimal = self._build_minimal_product_payload(data)
                    # Log minimal payload unconditionally to aid debugging
                    try:
                        pretty = json.dumps(minimal, ensure_ascii=False, indent=2, default=str)
                    except TypeError:
                        pretty = str(minimal)
                    logger.info(
                        "\n==== Shoper OUT RETRY POST products (minimal) ====:\n%s\n===============================================",
                        pretty,
                    )
                    try:
                        ret = self.post("products", json=minimal)
                        if not isinstance(ret, dict):
                            ret = {}
                        return ret
                    except Exception:
                        # Continue to deeper fallbacks below
                        pass
                    # Fall back to original error for clarity
                    # If the product likely exists already, attempt update instead of create
                    try:
                        code = str((data or {}).get("product_code") or "").strip()
                    except Exception:
                        code = ""
                    if code:
                        try:
                            found = self.search_products(filters={"code": code}, page=1, per_page=1)
                        except Exception:
                            found = None
                        product_id = self._extract_product_id_by_code(found, code) or self._extract_first_product_id(found)
                        if product_id:
                            logger.warning(
                                "Create failed with 500; updating existing product %s instead.",
                                product_id,
                            )
                            # Try minimal update first (avoids HTML/SEO fields)
                            minimal_update = self._build_minimal_update_payload(data)
                            try:
                                pretty = json.dumps(minimal_update, ensure_ascii=False, indent=2, default=str)
                            except TypeError:
                                pretty = str(minimal_update)
                            logger.info(
                                "\n==== Shoper OUT PUT products/%s (minimal update) ====:\n%s\n===================================================",
                                product_id,
                                pretty,
                            )
                            try:
                                ret = self.update_product(product_id, minimal_update)
                                if not isinstance(ret, dict):
                                    ret = {}
                                ret.setdefault("product_id", product_id)
                                ret.setdefault("id", product_id)
                                # Best-effort activation and category assignment
                                self._post_update_visibility(product_id, data)
                                return ret
                            except RuntimeError:
                                # Fallback to full update
                                try:
                                    ret = self.update_product(product_id, data)
                                    if not isinstance(ret, dict):
                                        ret = {}
                                    ret.setdefault("product_id", product_id)
                                    ret.setdefault("id", product_id)
                                    self._post_update_visibility(product_id, data)
                                    return ret
                                except RuntimeError:
                                    # Final fallback: update only stock/price
                                    stock_only = {
                                        "stock": {
                                            "stock": (data.get("stock") or {}).get("stock") or 1,
                                            "price": data.get("price") or (data.get("stock") or {}).get("price") or 0,
                                        }
                                    }
                                    try:
                                        pretty2 = json.dumps(stock_only, ensure_ascii=False, indent=2, default=str)
                                    except TypeError:
                                        pretty2 = str(stock_only)
                                    logger.info(
                                        "\n==== Shoper OUT PUT products/%s (stock-only) ====:\n%s\n==============================================",
                                        product_id,
                                        pretty2,
                                    )
                                    ret = self.update_product(product_id, stock_only)
                                    if not isinstance(ret, dict):
                                        ret = {}
                                    ret.setdefault("product_id", product_id)
                                    ret.setdefault("id", product_id)
                                    # Even after stock-only, try to activate product
                                    self._post_update_visibility(product_id, data)
                                    return ret
                        # Product does not exist yet – last-resort: create via import API
                        try:
                            created_id = self._create_product_via_import(data)
                        except Exception as imp_exc:
                            logger.warning("Import-based creation failed: %s", imp_exc)
                            raise exc
                        # After import, best-effort staged update (taxonomy, translations, image, etc.)
                        try:
                            self._post_update_visibility(str(created_id), data)
                        except Exception:
                            pass
                        return {"product_id": str(created_id), "id": str(created_id)}
                    # As a last resort: optionally reuse pre-provisioned product IDs
                    reusable = os.getenv("SHOPER_REUSE_PRODUCT_IDS", "").strip()
                    if reusable:
                        ids: list[str] = [
                            i.strip() for i in reusable.replace(";", ",").split(",") if i.strip()
                        ]
                        for pid in ids:
                            try:
                                logger.warning(
                                    "Reusing product ID %s for code %s due to create/import failures.",
                                    pid,
                                    code or "",
                                )
                                # Try minimal update first
                                minimal_update = self._build_minimal_update_payload(data)
                                try:
                                    self.update_product(pid, minimal_update)
                                except Exception:
                                    # Fallback to full payload
                                    self.update_product(pid, data)
                                try:
                                    self._post_update_visibility(str(pid), data)
                                except Exception:
                                    pass
                                return {"product_id": str(pid), "id": str(pid)}
                            except Exception as reuse_exc:
                                logger.warning("Failed to reuse product %s: %s", pid, reuse_exc)
                    raise exc
            raise

    def _create_product_via_import(self, data: dict) -> str:
        """Create a product using the CSV import endpoint and return its id."""
        import csv
        import tempfile
        from pathlib import Path

        code = str(data.get("product_code") or "").strip()
        if not code:
            raise ValueError("product_code required for import-based creation")

        # Name: try translations[0].name or fallback to code
        name = ""
        try:
            translations = data.get("translations") or []
            if isinstance(translations, list) and translations and isinstance(translations[0], dict):
                name = str(translations[0].get("name") or "").strip()
        except Exception:
            name = ""
        if not name:
            name = code

        # Basic numeric fields
        price = data.get("price")
        if price in (None, ""):
            price = (data.get("stock") or {}).get("price") or 0
        stock_val = (data.get("stock") or {}).get("stock") or 1
        category_id = data.get("category_id") or ""

        # Try to get a human-readable category label for CSV 'categories' column
        def _category_label_from_id(cid: str | int) -> str:
            try:
                cid_int = int(float(str(cid)))
            except Exception:
                return ""
            try:
                # Fetch page by page and find the matching id; keep it lightweight
                resp = self.get("categories", params={"page": 1, "limit": 250})
            except Exception:
                resp = {}
            items = []
            if isinstance(resp, dict):
                items = resp.get("list") or []
            for it in items or []:
                if not isinstance(it, dict):
                    continue
                raw = it.get("category_id") or it.get("id")
                try:
                    rid = int(float(str(raw)))
                except Exception:
                    continue
                if rid == cid_int:
                    # Prefer pl_PL translation name
                    tr = it.get("translations")
                    if isinstance(tr, dict) and isinstance(tr.get("pl_PL"), dict):
                        nm = tr["pl_PL"].get("name")
                        if isinstance(nm, str) and nm.strip():
                            return nm.strip()
                    nm = it.get("name") or it.get("label")
                    if isinstance(nm, str) and nm.strip():
                        return nm.strip()
            return ""

        label = _category_label_from_id(category_id) if category_id else ""

        def _do_import(rows: list[dict], headers: list[str]) -> None:
            with tempfile.TemporaryDirectory() as tmpd:
                path = Path(tmpd) / "create_one.csv"
                with open(path, "w", encoding="utf-8", newline="") as fh:
                    writer = csv.DictWriter(fh, fieldnames=headers, delimiter=";")
                    writer.writeheader()
                    for r in rows:
                        writer.writerow(r)
                self.import_csv(str(path))

        # Attempt 1: include 'categories' (name) column if we have a label
        tried_variants = []
        try:
            if label:
                headers = ["code", "name", "price", "stock", "categories"]
                rows = [{"code": code, "name": name, "price": price, "stock": stock_val, "categories": label}]
                tried_variants.append(headers)
                _do_import(rows, headers)
            else:
                raise RuntimeError("no label for categories")
        except Exception:
            # Attempt 2: without categories at all
            headers2 = ["code", "name", "price", "stock"]
            rows2 = [{"code": code, "name": name, "price": price, "stock": stock_val}]
            tried_variants.append(headers2)
            _do_import(rows2, headers2)

        # Lookup id by code after import
        resp = self.search_products(filters={"code": code}, page=1, per_page=1)
        pid = self._extract_product_id_by_code(resp, code) or self._extract_first_product_id(resp)
        if not pid:
            raise RuntimeError("Import reported success but product id not found")
        return str(pid)

    def _build_minimal_update_payload(self, data: dict) -> dict:
        """Return a reduced update payload keeping safe fields only."""
        result: dict = {}
        # Only update price/stock here to avoid server 500 on taxonomy changes
        price = data.get("price")
        if price in (None, ""):
            price = (data.get("stock") or {}).get("price")
        if price not in (None, ""):
            result["price"] = price
        stock = {"stock": 1}
        try:
            stock_val = (data.get("stock") or {}).get("stock")
            if isinstance(stock_val, (int, float)):
                stock["stock"] = int(stock_val)
            elif isinstance(stock_val, str) and stock_val.strip():
                stock["stock"] = int(float(stock_val))
        except Exception:
            pass
        if price not in (None, ""):
            stock["price"] = price
        avail = None
        try:
            avail = (data.get("stock") or {}).get("availability_id") or data.get("availability_id")
        except Exception:
            pass
        if isinstance(avail, (int, float)):
            stock["availability_id"] = int(avail)
        result["stock"] = stock
        # Do not include translations or active in minimal update
        return result

    def _post_update_visibility(self, product_id: str, original: dict) -> None:
        """Best-effort activation and category assignment after a safe update.

        Runs in a fire-and-forget manner; any errors are logged and ignored to
        not break the main flow.
        """
        # Activate if requested
        try:
            desired_active = original.get("active")
            if desired_active in (None, ""):
                desired_active = 1
            active_payload = {"active": int(bool(desired_active))}
            self.update_product(product_id, active_payload)
        except Exception:
            pass

        # Assign category if provided
        try:
            category_id = original.get("category_id")
            if category_id not in (None, ""):
                self.update_product(product_id, {"category_id": int(category_id)})
        except Exception:
            pass

        # Perform staged update to push remaining fields safely
        try:
            staged_flag = os.getenv("SHOPER_API_STAGED_UPDATE")
            if staged_flag is None or str(staged_flag).strip().lower() in {"1", "true", "yes", "on", ""}:
                self._staged_full_update(product_id, original)
        except Exception:
            pass

    def _staged_full_update(self, product_id: str, data: dict) -> None:
        """Apply remaining product fields in small, safer chunks.

        Each step is independent; failures are logged but do not raise.
        """
        def _apply(payload: dict, label: str) -> None:
            if not payload:
                return
            try:
                pretty = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
            except TypeError:
                pretty = str(payload)
            logger.info(
                "\n==== Shoper OUT PUT products/%s (%s) ====:\n%s\n==============================================",
                product_id,
                label,
                pretty,
            )
            try:
                self.update_product(product_id, payload)
            except Exception as exc:
                logger.warning("Stage '%s' failed: %s", label, exc)

        # 1) Taxonomy ids
        taxonomy_keys = ("category_id", "producer_id", "tax_id", "unit_id")
        taxonomy_payload = {k: v for k, v in data.items() if k in taxonomy_keys and v not in (None, "")}
        _apply(taxonomy_payload, "taxonomy")

        # 2) Weight and misc numeric fields
        misc_keys = ("weight", "group_id", "pkwiu")
        misc_payload = {k: v for k, v in data.items() if k in misc_keys and v not in (None, "")}
        _apply(misc_payload, "misc")

        # 3) Tags, collections, additional_codes, dimensions
        list_like = {
            "tags": data.get("tags"),
            "collections": data.get("collections"),
            "additional_codes": data.get("additional_codes"),
        }
        dims = data.get("dimensions")
        if isinstance(dims, dict) and dims:
            list_like["dimensions"] = dims
        list_payload = {k: v for k, v in list_like.items() if v}
        _apply(list_payload, "lists")

        # 4) Translations staged and sanitized to avoid 500s
        translations = data.get("translations")
        if isinstance(translations, list) and translations:
            # a) name only
            name_only = []
            for t in translations:
                if not isinstance(t, dict):
                    continue
                lang_id = t.get("language_id") or t.get("lang_id")
                code = t.get("language_code") or t.get("locale")
                entry = {
                    "language_id": lang_id,
                    "lang_id": lang_id,
                    "language_code": code,
                    "locale": code,
                    "name": t.get("name") or (data.get("nazwa") if isinstance(data, dict) else None) or (data.get("product_code") if isinstance(data, dict) else None),
                }
                name_only.append(entry)
            _apply({"translations": name_only}, "translations-name")

            # b) add short_description + description (sanitized)
            def _sanitize(text: Optional[str]) -> Optional[str]:
                if not isinstance(text, str) or not text.strip():
                    return text
                if not self.sanitize_html:
                    return text
                s = text
                # remove script/style blocks
                s = re.sub(r"<\s*(script|style)[^>]*?>[\s\S]*?<\s*/\s*\1\s*>", "", s, flags=re.I)
                # remove img tags
                s = re.sub(r"<\s*img\b[^>]*>", "", s, flags=re.I)
                # strip on* attributes
                s = re.sub(r"\son\w+\s*=\s*\"[^\"]*\"", "", s, flags=re.I)
                s = re.sub(r"\son\w+\s*=\s*'[^']*'", "", s, flags=re.I)
                s = re.sub(r"\son\w+\s*=\s*[^\s>]+", "", s, flags=re.I)
                return s

            desc_tr = []
            for t in translations:
                if not isinstance(t, dict):
                    continue
                entry = {
                    "language_id": t.get("language_id") or t.get("lang_id"),
                    "lang_id": t.get("language_id") or t.get("lang_id"),
                    "language_code": t.get("language_code") or t.get("locale"),
                    "locale": t.get("language_code") or t.get("locale"),
                    "name": t.get("name") or (data.get("nazwa") if isinstance(data, dict) else None) or (data.get("product_code") if isinstance(data, dict) else None),
                }
                sd = _sanitize(t.get("short_description"))
                d = _sanitize(t.get("description"))
                if sd:
                    entry["short_description"] = sd
                if d:
                    entry["description"] = d
                if len(entry) > 2:
                    desc_tr.append(entry)
            if desc_tr:
                _apply({"translations": desc_tr}, "translations-descriptions")

            # c) SEO fields
            seo_tr = []
            for t in translations:
                if not isinstance(t, dict):
                    continue
                entry = {
                    "language_id": t.get("language_id") or t.get("lang_id"),
                    "lang_id": t.get("language_id") or t.get("lang_id"),
                    "language_code": t.get("language_code") or t.get("locale"),
                    "locale": t.get("language_code") or t.get("locale"),
                    "name": t.get("name") or (data.get("nazwa") if isinstance(data, dict) else None) or (data.get("product_code") if isinstance(data, dict) else None),
                }
                for key in ("seo_title", "seo_description", "seo_keywords", "permalink"):
                    val = t.get(key)
                    if isinstance(val, str) and val.strip():
                        entry[key] = val.strip()
                if len(entry) > 2:
                    seo_tr.append(entry)
            if seo_tr:
                _apply({"translations": seo_tr}, "translations-seo")

    @staticmethod
    def _extract_first_product_id(response) -> Optional[str]:
        def _iter_products(payload):
            if isinstance(payload, dict):
                for key in ("list", "items", "data", "results", "products"):
                    container = payload.get(key)
                    if isinstance(container, list):
                        for entry in container:
                            if isinstance(entry, dict):
                                yield entry
                    elif isinstance(container, dict):
                        # sometimes nested
                        yield from _iter_products(container)
                # also allow flat single entry
                if any(k in payload for k in ("product_id", "id", "code")):
                    yield payload
            elif isinstance(payload, list):
                for entry in payload:
                    if isinstance(entry, dict):
                        yield entry

        if not response:
            return None
        for entry in _iter_products(response):
            for key in ("product_id", "id"):
                raw = entry.get(key)
                if raw in (None, ""):
                    continue
                text = str(raw).strip()
                if text:
                    return text
        return None

    @staticmethod
    def _extract_product_id_by_code(response, desired_code: str) -> Optional[str]:
        code_norm = (str(desired_code or "").strip()).lower()
        if not code_norm:
            return None

        def _iter_products(payload):
            if isinstance(payload, dict):
                for key in ("list", "items", "data", "results", "products"):
                    container = payload.get(key)
                    if isinstance(container, list):
                        for entry in container:
                            if isinstance(entry, dict):
                                yield entry
                    elif isinstance(container, dict):
                        yield from _iter_products(container)
                if any(k in payload for k in ("product_id", "id", "code")):
                    yield payload
            elif isinstance(payload, list):
                for entry in payload:
                    if isinstance(entry, dict):
                        yield entry

        for entry in _iter_products(response):
            code = (entry.get("code") or entry.get("product_code") or entry.get("warehouse_code") or "")
            if str(code).strip().lower() == code_norm:
                raw = entry.get("product_id") or entry.get("id")
                if raw not in (None, ""):
                    text = str(raw).strip()
                    if text:
                        return text
        return None

    def _build_minimal_product_payload(self, data: dict) -> dict:
        """Construct a pared-down product payload likely to pass validation.

        Keeps only the essentials: product_code, active, price, translations, stock.
        Mirrors price both at top-level and inside stock for compatibility.
        """
        product_code = None
        try:
            raw = data.get("product_code")
            if isinstance(raw, str):
                product_code = raw.strip()
            elif raw is not None:
                product_code = str(raw).strip()
        except Exception:
            product_code = None

        # Price: prefer top-level, then stock.price, default 0.0
        price = None
        try:
            price = data.get("price")
        except Exception:
            price = None
        if price in (None, ""):
            try:
                price = (data.get("stock") or {}).get("price")
            except Exception:
                price = None
        if price in (None, ""):
            price = 0.0

        # Translations: keep only minimal fields (name + language ids)
        translations = []
        try:
            tr = data.get("translations")
            if isinstance(tr, (list, tuple)):
                translations = [t for t in tr if isinstance(t, dict)]
        except Exception:
            translations = []

        def _resolve_languages():
            try:
                resp = self.get("languages")
            except Exception:
                return []
            entries = []
            if isinstance(resp, dict):
                for key in ("list", "items", "languages"):
                    if isinstance(resp.get(key), list):
                        entries = [e for e in resp.get(key) if isinstance(e, dict)]
                        break
                if not entries:
                    entries = [e for e in resp.values() if isinstance(e, dict)]
            elif isinstance(resp, list):
                entries = [e for e in resp if isinstance(e, dict)]
            result = []
            for e in entries:
                lang = e.get("language") if isinstance(e.get("language"), dict) else None
                code = (
                    e.get("code")
                    or e.get("language_code")
                    or (lang.get("code") if lang else None)
                    or e.get("symbol")
                )
                lid = e.get("language_id") or e.get("id") or (lang.get("id") if lang else None)
                is_default = (
                    bool(e.get("default"))
                    or bool(e.get("is_default"))
                    or bool(e.get("main"))
                    or bool(e.get("is_main"))
                )
                if code and lid:
                    try:
                        lid = int(lid)
                    except Exception:
                        continue
                    result.append({"language_code": code, "language_id": lid, "is_default": is_default})
            return result

        def _pick_language_from_store():
            langs = _resolve_languages()
            if not langs:
                return {"language_code": "pl_PL", "language_id": 1}
            default = next((l for l in langs if l.get("is_default")), None)
            return default or langs[0]

        # If provided translations lack language identifiers, enrich them.
        # Keep only 'name', 'language_id', 'language_code' to avoid HTML/SEO quirks causing 500.
        normalized_translations = []
        if translations:
            for t in translations:
                entry = dict(t)
                lid = entry.get("language_id") or entry.get("id")
                code = entry.get("language_code") or entry.get("code")
                if not lid or not code:
                    store_lang = _pick_language_from_store()
                    entry.setdefault("language_id", store_lang["language_id"])
                    entry.setdefault("language_code", store_lang["language_code"])
                minimal_entry = {
                    "name": entry.get("name") or (product_code or ""),
                    "language_id": entry.get("language_id"),
                    "language_code": entry.get("language_code"),
                }
                normalized_translations.append(minimal_entry)
        else:
            store_lang = _pick_language_from_store()
            normalized_translations.append(
                {
                    "name": product_code or "",
                    "language_id": store_lang["language_id"],
                    "language_code": store_lang["language_code"],
                }
            )
        translations = normalized_translations

        # Stock block with minimal fields and default active/delivery
        stock = {"stock": 1, "price": price}
        # Intentionally skip availability on minimal create (can trigger 500)
        try:
            raw_stock = data.get("stock") or {}
            quantity = raw_stock.get("stock")
            if isinstance(quantity, (int, float)):
                stock["stock"] = int(quantity)
            elif isinstance(quantity, str) and quantity.strip():
                stock["stock"] = int(float(quantity))
        except Exception:
            pass
        # Defaults that many stores require
        stock["active"] = 1
        try:
            default_delivery = os.getenv("SHOPER_DEFAULT_DELIVERY_ID", "3").strip()
            if default_delivery:
                stock["delivery_id"] = int(float(default_delivery))
        except Exception:
            pass
        # Do not forward availability in minimal retry

        payload: dict = {
            "product_code": product_code,
            # Keep product active on create; some stores require this
            "active": 1,
            "price": price,
            "translations": translations,
            "stock": stock,
        }
        # Mirror code alongside product_code
        if product_code:
            payload["code"] = product_code
            try:
                payload["stock"]["code"] = product_code
            except Exception:
                pass

        # EAN defaults
        ean = (data.get("ean") or "").strip() if isinstance(data.get("ean"), str) else ""
        payload.setdefault("ean", ean)
        try:
            payload["stock"].setdefault("ean", ean)
        except Exception:
            pass

        # Include only category_id (required by some stores) and categories list
        def _coerce_optional_int(val):
            try:
                if val in (None, ""):
                    return None
                if isinstance(val, bool):
                    return int(val)
                if isinstance(val, (int, float)):
                    return int(val)
                if isinstance(val, str) and val.strip():
                    return int(float(val.strip()))
            except Exception:
                return None
            return None

        cat = _coerce_optional_int(data.get("category_id"))
        if cat is not None:
            payload["category_id"] = cat
            payload["categories"] = [cat]

        # Optionally include other taxonomy ids (producer_id/tax_id/unit_id) in minimal create
        # Enable via SHOPER_MIN_CREATE_TAXONOMY=1 for stores that require them
        import os as _os
        try:
            _inc_tax = str(_os.getenv("SHOPER_MIN_CREATE_TAXONOMY", "")).strip().lower() in {"1", "true", "yes", "on"}
        except Exception:
            _inc_tax = False
        if _inc_tax:
            for key in ("producer_id", "tax_id", "unit_id"):
                val = _coerce_optional_int(data.get(key))
                if val is not None:
                    payload[key] = val
        return payload

    def _build_ultramin_product_payload(self, data: dict) -> dict:
        """Return the most bare create payload: code + price + stock + active.

        Avoids taxonomy/translations to reduce 500s on strict stores.
        """
        code_raw = data.get("product_code")
        code = code_raw.strip() if isinstance(code_raw, str) else str(code_raw or "").strip()
        price = data.get("price") or (data.get("stock") or {}).get("price") or 0
        stock_val = (data.get("stock") or {}).get("stock") or 1
        try:
            stock_int = int(float(stock_val))
        except Exception:
            stock_int = 1
        # Minimal translations (server requires 'translations')
        def _pick_language():
            try:
                resp = self.get("languages")
                items = []
                if isinstance(resp, dict):
                    items = resp.get("list") or resp.get("items") or []
                if isinstance(items, list):
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        if it.get("default") or it.get("is_default") or it.get("main"):
                            lid = it.get("language_id") or it.get("id")
                            code = it.get("locale") or it.get("language_code") or it.get("code")
                            if lid and code:
                                return int(lid), str(code)
                    # fallback first item
                    if items:
                        it = items[0]
                        lid = it.get("language_id") or it.get("id")
                        code = it.get("locale") or it.get("language_code") or it.get("code")
                        if lid and code:
                            return int(lid), str(code)
            except Exception:
                pass
            return 1, "pl_PL"

        lang_id, lang_code = _pick_language()

        payload = {
            "product_code": code,
            "active": 1,
            "price": price,
            "stock": {"stock": stock_int, "price": price},
            "translations": [
                {
                    "name": data.get("nazwa") or (data.get("translations") or [{"name": code}])[0].get("name", code) if isinstance(data.get("translations"), list) else (data.get("nazwa") or code),
                    "language_id": lang_id,
                    "language_code": lang_code,
                }
            ],
        }
        # Mirror code field and ean defaults
        payload["code"] = code
        payload.setdefault("ean", (data.get("ean") or "") if isinstance(data.get("ean"), str) else "")
        try:
            payload["stock"]["code"] = code
            payload["stock"].setdefault("ean", payload["ean"])  
        except Exception:
            pass
        # Some stores require category_id even for a bare create; include if present
        cat_id = data.get("category_id")
        try:
            if cat_id not in (None, ""):
                cid = int(float(str(cat_id)))
                payload["category_id"] = cid
                payload["categories"] = [cid]
        except Exception:
            pass
        return payload

    def _default_language(self) -> tuple[int, str]:
        """Return store default language as (id, code)."""
        try:
            resp = self.get("languages")
            items = []
            if isinstance(resp, dict):
                items = resp.get("list") or resp.get("items") or []
            if isinstance(items, list):
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    if it.get("default") or it.get("is_default") or it.get("main"):
                        lid = it.get("language_id") or it.get("id")
                        code = it.get("locale") or it.get("language_code") or it.get("code")
                        if lid and code:
                            return int(lid), str(code)
                if items:
                    it = items[0]
                    lid = it.get("language_id") or it.get("id")
                    code = it.get("locale") or it.get("language_code") or it.get("code")
                    if lid and code:
                        return int(lid), str(code)
        except Exception:
            pass
        return 1, "pl_PL"

    def _apply_create_minimal_translations(self, data: dict) -> dict:
        """Return a copy of data with translations reduced to 'name' in default language.

        This avoids create-time 500s due to HTML/SEO fields in translations and ensures
        the server receives required 'translations' key.
        """
        # Shallow copy is enough for create
        cloned = dict(data or {})
        code_raw = cloned.get("product_code")
        code = code_raw.strip() if isinstance(code_raw, str) else str(code_raw or "").strip()
        # Pick default language
        lang_id, lang_code = self._default_language()
        # Name source: prefer translation matching default language with non-empty name,
        # then any translation with non-empty name, else 'name'/'nazwa', else code
        name = None
        try:
            tr = cloned.get("translations")
            if isinstance(tr, list):
                # First pass: exact language match
                for t in tr:
                    if not isinstance(t, dict):
                        continue
                    t_lid = t.get("language_id") or t.get("id")
                    t_code = t.get("language_code") or t.get("code")
                    nm = t.get("name")
                    if (t_lid == lang_id or t_code == lang_code) and isinstance(nm, str) and nm.strip():
                        name = nm.strip()
                        break
                # Second pass: any non-empty name
                if not name:
                    for t in tr:
                        if isinstance(t, dict):
                            nm = t.get("name")
                            if isinstance(nm, str) and nm.strip():
                                name = nm.strip()
                                break
        except Exception:
            name = None
        if not name:
            top_nm = cloned.get("name")
            if isinstance(top_nm, str) and top_nm.strip():
                name = top_nm.strip()
        if not name:
            nm2 = cloned.get("nazwa")
            if isinstance(nm2, str) and nm2.strip():
                name = nm2.strip()
        if not name:
            name = code or ""
        # Apply minimal translations
        cloned["translations"] = [{"name": name, "language_id": lang_id, "language_code": lang_code}]
        return cloned

    def update_product(self, product_id, data):
        if not product_id:
            raise ValueError("product_id is required")
        return self.put(f"products/{product_id}", json=data)

    def update_product_stock(self, product_id, stock, warn_level=None):
        try:
            stock_int = int(float(stock))
        except (TypeError, ValueError):
            raise ValueError("stock must be numeric") from None

        payload = {"stock": {"stock": stock_int}}
        if warn_level is not None:
            try:
                payload["stock"]["warn_level"] = int(float(warn_level))
            except (TypeError, ValueError):
                raise ValueError("warn_level must be numeric") from None
        return self.update_product(product_id, payload)

    def mark_products_sold(self, codes):
        codes_list = [str(code).strip() for code in (codes or []) if str(code).strip()]
        if not codes_list:
            return {"count": 0}
        return self.post("warehouse/sold", json={"codes": codes_list})

    def get_inventory(self, page=1, per_page=50):
        """Return products with optional pagination."""
        params = {"page": page, "per-page": per_page}
        return self.get("products", params=params)

    def search_products(self, filters=None, sort=None, page=1, per_page=50):
        """Search products with optional filters and sorting."""
        params = {"page": page, "per-page": per_page}
        if filters:
            # Build both legacy bracket params and JSON 'filters' to maximise compatibility.
            try:
                filt_map = dict(filters)
            except Exception:
                filt_map = {"search": str(filters)}

            # Bracket-style
            for key, val in filt_map.items():
                if val in (None, ""):
                    continue
                key_str = str(key)
                if key_str.startswith("filters["):
                    params[key_str] = val
                else:
                    params[f"filters[{key_str}]"] = val

            # JSON-style
            try:
                params["filters"] = json.dumps({k: v for k, v in filt_map.items() if v not in (None, "")}, ensure_ascii=False)
            except Exception:
                pass
        if sort:
            params["sort"] = sort
        return self.get("products", params=params)

    def list_orders(
        self,
        filters=None,
        page=1,
        per_page=20,
        include_products=True,
    ):
        """Return a list of orders filtered by status or other fields."""
        params = {"page": page}
        limit = self._coerce_limit(per_page)
        if limit is not None:
            params["limit"] = limit
        if filters:
            params.update(filters)
        if include_products:
            with_value = params.get("with")
            if isinstance(with_value, (list, tuple, set)):
                params["with"] = ",".join(
                    dict.fromkeys(str(value).strip() for value in with_value if value)
                )
            elif not with_value:
                params["with"] = "products,delivery_address,billing_address"
        self._normalise_status_filters(params)

        # Krok 1: Pobieramy podstawową listę zamówień
        response = self.get("orders", params=params)

        # Krok 2: Jeśli chcemy produkty, pobieramy je dla każdego zamówienia osobno
        if include_products and response and "list" in response:
            orders_list = response.get("list", [])
            for order in orders_list:
                order_id = order.get("order_id")
                if order_id:
                    try:
                        # Używamy naszej nowej, inteligentnej metody
                        products_response = self.get_order_products(order_id)
                        # Wstrzykujemy listę produktów do obiektu zamówienia
                        order["products"] = products_response.get("list", [])
                    except Exception as e:
                        logger.error(f"Nie udało się pobrać produktów dla zamówienia #{order_id}: {e}")
                        order["products"] = []

        return response

    def get_order(self, order_id):
        """Retrieve a single order by id."""
        # Dodajemy parametr "with", aby API dołączyło listę produktów i inne szczegóły
        params = {"with": "products,delivery_address,billing_address,status,user"}
        return self.get(f"orders/{order_id}", params=params)
    
    def get_order_products(self, order_id):
        """Pobiera listę WSZYSTKICH produktów dla konkretnego zamówienia, obsługując paginację."""
        all_products = []
        page = 1
        while True:
            filters = json.dumps({"order_id": order_id})
            params = {"filters": filters, "page": page, "limit": 50}

            response = self.get("order-products", params=params)

            products_on_page = response.get("list", [])
            if not products_on_page:
                break  # Koniec produktów, przerywamy pętlę

            all_products.extend(products_on_page)

            current_page = int(response.get("page", 1))
            total_pages = int(response.get("pages", 1))

            if current_page >= total_pages:
                break

            page += 1

        return {"list": all_products, "count": len(all_products)}

    # New helper methods for dashboard statistics
    def get_orders(self, status=None, filters=None, page=1, per_page=20):
        """Return orders optionally filtered by status and other criteria."""
        params = {"page": page}
        limit = self._coerce_limit(per_page)
        if limit is not None:
            params["limit"] = limit
        if filters:
            params.update(filters)
        if status:
            params["filters[status]"] = status
        self._normalise_status_filters(params)
        return self.get("orders", params=params)

    @staticmethod
    def _coerce_limit(value: Optional[int]) -> Optional[int]:
        """Return a Shoper-compatible ``limit`` value.

        The orders endpoint expects ``limit`` instead of ``per-page`` used by
        other API calls and caps it at ``50``.  The helper keeps the public
        ``per_page`` argument for backwards compatibility while ensuring the
        request complies with the documented contract.
        """

        if value is None:
            return None

        try:
            limit = int(value)
        except (TypeError, ValueError):
            return None

        if limit <= 0:
            return None

        return min(limit, 50)

    @staticmethod
    def _normalise_status_filters(params: dict) -> None:
        """Convert list-like status filters to the API ``[in]`` form."""

        if not params:
            return

        for base in ("filters[status]", "filters[status.type]"):
            if base in params:
                status_values = params.get(base)
                key_to_remove = base
            elif f"{base}[in]" in params:
                status_values = params.get(f"{base}[in]")
                key_to_remove = f"{base}[in]"
            else:
                continue

            if isinstance(status_values, (list, tuple, set)):
                values = [str(value) for value in status_values if value]
            elif isinstance(status_values, str):
                values = [part.strip() for part in status_values.split(",") if part.strip()]
            else:
                values = [str(status_values)] if status_values else []

            params.pop(key_to_remove, None)

            if not values:
                continue

            params[f"{base}[in]"] = ",".join(dict.fromkeys(values))

    def get_sales_stats(self, params=None):
        """Return sales statistics using the built-in Shoper endpoint."""
        try:
            return self.get("orders/stats", params=params or {})
        except RuntimeError:  # pragma: no cover - network failure
            print("[INFO] orders/stats unavailable")
            return {}

    def import_csv(self, file_path, poll_interval=2, timeout=120):
        """Upload a CSV file and wait for the import job to finish.

        Pass explicit delimiter/encoding hints to increase compatibility and
        log the full importer response body when the server returns 4xx/5xx
        to simplify troubleshooting formatter expectations.
        """
        url = f"{self.base_url}/products/import"
        with open(file_path, "rb") as fh:
            files = {"file": (os.path.basename(file_path), fh, "text/csv")}
            form = {"delimiter": ";", "encoding": "utf-8"}
            try:
                resp = self.session.post(url, files=files, data=form, timeout=30)
            except requests.RequestException as exc:  # pragma: no cover - network dependent
                raise RuntimeError(f"CSV import request failed: {exc}") from exc

        if resp.status_code >= 400:
            content_type = resp.headers.get("Content-Type", "")
            body_text = resp.text or ""
            try:
                body_json = resp.json()
            except ValueError:
                body_json = None
            if body_json is not None:
                try:
                    dump = json.dumps(body_json, ensure_ascii=False)[:4000]
                except Exception:
                    dump = str(body_json)[:4000]
            else:
                dump = (body_text or "").strip()[:4000]
            logger.error(
                "Shoper importer error: status=%s, content-type=%s, body=%s",
                resp.status_code,
                content_type,
                dump,
            )
            raise RuntimeError(f"Import failed ({resp.status_code}): {dump}")

        try:
            data = resp.json() if resp.text else {}
        except ValueError:
            data = {}
        job_id = data.get("job_id") or data.get("id")
        if job_id:
            return self._poll_import_job(job_id, poll_interval, timeout)
        return data

    def _poll_import_job(self, job_id, interval=2, timeout=120):
        """Poll the import job until completion or failure."""
        endpoint = f"products/import/{job_id}"
        end_time = time.time() + timeout
        while time.time() < end_time:
            status = self.get(endpoint)
            state = status.get("status") or status.get("state")
            if state in {"completed", "finished", "done", "success"}:
                errors = status.get("errors")
                if errors:
                    raise RuntimeError(f"Import completed with errors: {errors}")
                return status
            if state in {"failed", "error"}:
                raise RuntimeError(f"Import failed: {status}")
            time.sleep(interval)
        raise RuntimeError("Import job timed out")

    def get_attributes(self):
        """Return a list of product attributes."""
        return self.get("attributes")

    def add_product_attribute(self, product_id, attribute_id, values):
        """Assign a product attribute to a product."""
        payload = {
            "product_id": product_id,
            "attribute_id": attribute_id,
            "values": values,
        }
        return self.post("products-attributes", json=payload)

    # -------------------------
    # Images
    # -------------------------
    def upload_product_image(
        self,
        product_id: str,
        file_path: str,
        *,
        is_main: bool = True,
        language_id: Optional[int] = None,
        language_code: Optional[str] = None,
        alt: Optional[str] = None,
    ):
        """Upload a local image file and assign it to a product.

        Tries multiple Shoper endpoints for compatibility. Returns server response.
        """
        import mimetypes
        from pathlib import Path

        if not product_id:
            raise ValueError("product_id is required for image upload")
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(str(p))
        mime, _ = mimetypes.guess_type(str(p))
        mime = mime or "image/jpeg"

        # Common form fields
        base_data = {
            "product_id": str(product_id),
            "is_main": "1" if is_main else "0",
        }
        if language_id is not None:
            base_data["language_id"] = int(language_id)
        if language_code:
            base_data["language_code"] = language_code
        if alt:
            base_data["alt"] = alt

        endpoints = (
            ("products/images", "file"),            # preferred endpoint, file field 'file'
            ("products-images", "file"),            # legacy naming
            (f"products/{product_id}/images", "file"),  # product-scoped endpoint
            ("products/images", "image"),           # some installs expect 'image' as field name
        )
        last_error: Optional[Exception] = None
        for ep, file_field in endpoints:
            try:
                with open(p, "rb") as fh:
                    files = {file_field: (p.name, fh, mime)}
                    return self.post(ep, files=files, data=base_data)
            except Exception as exc:
                last_error = exc
                continue
        if last_error:
            raise last_error
        return {}

    # ------------------------------------------------------------------
    # Internal helpers

    def _ensure_token(self):
        """Refresh the OAuth token when using client credentials."""

        if not self.client_id:
            return
        if not self.token or time.time() >= (self._token_expires_at - 60):
            self._authenticate(force=True)

    def _authenticate(self, force=False):
        if not self.client_id or not self._client_secret:
            raise RuntimeError("Shoper client credentials are not configured")
        if not force and self.token and time.time() < (self._token_expires_at - 60):
            return

        url = f"{self.base_url}/auth"
        payload = {
            "client_id": self.client_id,
            "client_secret": self._client_secret,
            "grant_type": "client_credentials",
        }
        try:
            resp = self.session.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(f"Failed to authenticate with Shoper API: {exc}") from exc

        access_token = data.get("access_token")
        if not access_token:
            raise RuntimeError("Shoper API did not return an access token")

        expires_in = data.get("expires_in")
        try:
            expires = float(expires_in)
        except (TypeError, ValueError):
            expires = 3600.0

        self.token = access_token
        self._token_expires_at = time.time() + max(expires, 60.0)
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})

    @staticmethod
    def _normalize_base_url(url: str) -> str:
        """Return a URL that always points to ``/webapi/rest``.

        Users frequently copy the ``/webapi`` panel address instead of the REST
        entry point.  The API, however, requires requests to be sent to the
        ``/webapi/rest`` sub-path.  To make configuration more forgiving we
        detect such cases and automatically rewrite the URL so that subsequent
        calls hit the correct endpoint regardless of whether the user provided
        ``https://shop/webapi`` or ``https://shop``.
        """

        if not url:
            return ""

        stripped = url.rstrip("/")
        if not stripped:
            return ""

        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(stripped)
        path_parts = [segment for segment in parts.path.split("/") if segment]

        # Remove any trailing ``rest``/``webapi`` components so we can append a
        # single ``webapi/rest`` pair regardless of what the user supplied.
        while path_parts and path_parts[-1] == "rest":
            path_parts.pop()
        if path_parts and path_parts[-1] == "webapi":
            path_parts.pop()

        normalized_path = "/" + "/".join(path_parts + ["webapi", "rest"])

        return urlunsplit(
            parts._replace(path=normalized_path, query="", fragment="")
        )

    # -------------------------
    # Env helpers
    # -------------------------
    @staticmethod
    def _env_flag(name: str) -> bool:
        """Return True if the environment variable is set to a truthy value.

        Truthy examples: 1, true, yes, on (case-insensitive).
        """
        raw = os.getenv(name)
        if raw is None:
            return False
        value = str(raw).strip().lower()
        return value in {"1", "true", "yes", "on"}
