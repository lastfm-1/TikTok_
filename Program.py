"""
NAME = "TikTok Daily Streak Bot"
AUTHOR = "TimeNitch"
ORIGINAL_REPO = "https://github.com/TimeNitch/Tiktok-Streak-Bot-using-cookies"
"""

import json
from operator import index
import os
import re
import sys
import time
import random
import logging
import threading
import urllib.parse
import urllib.request
import uuid
import mimetypes
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (
    InvalidCookieDomainException,
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

BASE_DIR = Path(__file__).resolve().parent

CONFIG_FILE = BASE_DIR / "config.ini"
TEXT_FILE = BASE_DIR / "text.txt"
COOKIE_FILE = BASE_DIR / "cookie.txt"
EXCEPTION_FILE = BASE_DIR / "exception.txt"
LOG_FILE = BASE_DIR / "tiktok_bot.log"

DISCORD_WEBHOOK_FILE = BASE_DIR / "discord_webhook.txt"
TELEGRAM_BOT_TOKEN_FILE = BASE_DIR / "telegram_bot_token.txt"
TELEGRAM_CHAT_ID_FILE = BASE_DIR / "telegram_chat_id.txt"

BASE_URL = "https://www.tiktok.com/messages/?lang=en"
MESSAGES_URL = "https://www.tiktok.com/messages/?lang=en"

DISCORD_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/51.0.2704.103 Safari/537.36"
)


def load_config(path: Path) -> dict:
    config = {}

    if not path.exists():
        return config

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "#" in line:
            line = line.split("#", 1)[0].strip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        config[key.strip()] = value.strip()

    return config


def get_config_value(config: dict, key: str, default: str) -> str:
    return config.get(key, os.getenv(key, default)).strip()


def get_config_bool(config: dict, key: str, default: bool) -> bool:
    value = get_config_value(config, key, str(default)).strip().lower()

    if value in {"true", "1", "yes", "y", "on"}:
        return True

    if value in {"false", "0", "no", "n", "off"}:
        return False

    raise ValueError(f"Invalid boolean value for {key}: {value}. Use True or False.")


def get_config_int(config: dict, key: str, default: int) -> int:
    value = get_config_value(config, key, str(default))
    return int(value)


def get_config_timezone(config: dict, key: str, default: str):
    timezone_name = get_config_value(config, key, default)

    try:
        return ZoneInfo(timezone_name)
    except Exception as exc:
        raise ValueError(
            f"Invalid timezone: {timezone_name}. "
            "Use an IANA timezone name such as Asia/Bangkok. "
            "Timezone list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        ) from exc


def load_message_texts(path: Path, default: str) -> list[str]:
    env_text = os.getenv("TIKTOK_MESSAGE_TEXT", "").strip()

    if env_text:
        return [line.strip() for line in env_text.splitlines() if line.strip()]

    if not path.exists():
        return [default]

    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    if not lines:
        return [default]

    return lines


def get_random_message_text() -> str:
    return random.choice(MESSAGE_TEXTS)


CONFIG = load_config(CONFIG_FILE)

DEBUG_MODE = get_config_bool(CONFIG, "DEBUG_MODE", False)
ENABLE_NOTIFY = get_config_bool(CONFIG, "ENABLE_NOTIFY", True)

MESSAGE_TEXTS = load_message_texts(TEXT_FILE, "I'm here for the streak🔥")
WAIT_SECONDS = get_config_int(CONFIG, "TIKTOK_WAIT_SECONDS", 10)

WAIT_UNTIL_TARGET_TIME = get_config_bool(CONFIG, "WAIT_UNTIL_TARGET_TIME", True)
PRECHECK_BEFORE_WAIT = get_config_bool(CONFIG, "PRECHECK_BEFORE_WAIT", True)
PRECHECK_INTERVAL_MINUTES = get_config_int(CONFIG, "PRECHECK_INTERVAL_MINUTES", 10)
PRECHECK_STOP_WITHIN_MINUTES = get_config_int(CONFIG, "PRECHECK_STOP_WITHIN_MINUTES", 15)

TARGET_RUN_TIME = get_config_value(CONFIG, "TARGET_RUN_TIME", "06:00:00")
TARGET_TIMEZONE = get_config_timezone(CONFIG, "TARGET_TIMEZONE", "Asia/Bangkok")


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)


def load_cookie_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Cookie file not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("cookie.txt is empty. Paste cookies first, for example: sessionid=...; sid_tt=...")

    return text


def load_optional_secret_text(path: Path) -> str:
    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8").strip()
    return text


def normalize_name_for_compare(name: str) -> str:
    return " ".join(name.strip().casefold().split())


def load_exception_names(path: Path) -> set[str]:
    if not path.exists():
        return set()

    names = set()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        names.add(normalize_name_for_compare(line))

    return names


def split_targets_by_exception(targets: list[dict]) -> tuple[list[dict], list[dict]]:
    exception_names = load_exception_names(EXCEPTION_FILE)

    if not exception_names:
        return targets, []

    allowed_targets = []
    excluded_targets = []

    for target in targets:
        target_name = target.get("name", "")
        normalized_name = normalize_name_for_compare(target_name)

        if normalized_name in exception_names:
            excluded_targets.append(target)
        else:
            allowed_targets.append(target)

    return allowed_targets, excluded_targets


def normalize_cookie(cookie: dict) -> dict:
    name = cookie.get("name")
    value = cookie.get("value")
    if not name or value is None:
        raise ValueError(f"Invalid cookie: {cookie}")

    normalized = {
        "name": str(name),
        "value": str(value),
        "domain": cookie.get("domain") or ".tiktok.com",
        "path": cookie.get("path") or "/",
    }

    if "expirationDate" in cookie:
        normalized["expiry"] = int(cookie["expirationDate"])
    elif "expiry" in cookie:
        normalized["expiry"] = int(cookie["expiry"])
    elif "expires" in cookie and isinstance(cookie["expires"], (int, float)):
        normalized["expiry"] = int(cookie["expires"])

    if "secure" in cookie:
        normalized["secure"] = bool(cookie["secure"])

    if "httpOnly" in cookie:
        normalized["httpOnly"] = bool(cookie["httpOnly"])

    same_site = cookie.get("sameSite") or cookie.get("same_site")
    if same_site:
        same_site = str(same_site).capitalize()
        if same_site in {"Strict", "Lax", "None"}:
            normalized["sameSite"] = same_site

    return normalized


def parse_json_cookies(text: str) -> list[dict]:
    data = json.loads(text)

    if isinstance(data, dict):
        if isinstance(data.get("cookies"), list):
            data = data["cookies"]
        else:
            data = [data]

    if not isinstance(data, list):
        raise ValueError("JSON cookies must be a list, or an object with a cookies key")

    return [normalize_cookie(cookie) for cookie in data]


def parse_expiry(value: str) -> int | None:
    value = value.strip()
    if not value or value.lower() == "session":
        return None

    if value.isdigit():
        return int(value)

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return int(parsed.astimezone(timezone.utc).timestamp())
    except ValueError:
        return None


def is_checked(value: str) -> bool:
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
        "\u2713",
        "\u00e2\u0153\u201c",
    }


def parse_browser_table_cookies(text: str) -> list[dict]:
    cookies = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split("\t") if "\t" in line else re.split(r"\s{2,}", line)
        if len(parts) < 5:
            raise ValueError("Not a browser table cookie format")

        name, value, domain, path, expires = parts[:5]
        cookie = {
            "name": name,
            "value": value,
            "domain": domain or ".tiktok.com",
            "path": path or "/",
        }

        expiry = parse_expiry(expires)
        if expiry:
            cookie["expiry"] = expiry

        if len(parts) > 6 and is_checked(parts[6]):
            cookie["httpOnly"] = True

        if len(parts) > 7 and is_checked(parts[7]):
            cookie["secure"] = True

        if len(parts) > 8 and parts[8].strip() in {"Strict", "Lax", "None"}:
            cookie["sameSite"] = parts[8].strip()

        cookies.append(normalize_cookie(cookie))

    if not cookies:
        raise ValueError("No browser table cookies found")

    return cookies


def parse_netscape_cookies(text: str) -> list[dict]:
    cookies = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = line.split("\t")
        if len(parts) != 7:
            raise ValueError("Not a Netscape cookie format")

        domain, _flag, path, secure, expires, name, value = parts
        cookie = {
            "domain": domain,
            "path": path or "/",
            "secure": secure.upper() == "TRUE",
            "name": name,
            "value": value,
        }

        if expires and expires != "0":
            cookie["expiry"] = int(expires)

        cookies.append(normalize_cookie(cookie))

    if not cookies:
        raise ValueError("No Netscape cookies found")

    return cookies


def parse_header_cookies(text: str) -> list[dict]:
    cookies = []

    for item in text.replace("\n", ";").split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue

        name, value = item.split("=", 1)
        name = name.strip()
        value = value.strip()

        if name.lower() in {
            "domain",
            "path",
            "expires",
            "max-age",
            "secure",
            "httponly",
            "samesite",
        }:
            continue

        cookies.append(
            normalize_cookie(
                {
                    "name": name,
                    "value": value,
                    "domain": ".tiktok.com",
                    "path": "/",
                    "secure": True,
                }
            )
        )

    if not cookies:
        raise ValueError("No name=value cookies found")

    return cookies


def parse_cookies(text: str) -> list[dict]:
    if text.startswith("[") or text.startswith("{"):
        return parse_json_cookies(text)

    try:
        return parse_browser_table_cookies(text)
    except ValueError:
        pass

    try:
        return parse_netscape_cookies(text)
    except ValueError:
        return parse_header_cookies(text)


def click_element(driver: webdriver.Chrome, element) -> None:
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(0.3)
    try:
        element.click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", element)


def find_visible_elements(driver: webdriver.Chrome, xpath: str) -> list:
    return [
        element
        for element in driver.find_elements(By.XPATH, xpath)
        if element.is_displayed()
    ]


def get_target_conversations(driver: webdriver.Chrome) -> list[dict]:
    targets = driver.execute_script(
        """
        const PIN_PATH_D = "M31.6 3.67a3 3 0 0 0-4.24 0l-.7.7";

        const TARGET_CLASS_KEY = "css-k8n8bd";
        const SKIP_CLASS_KEY = "css-rftu2f";

        function getConversationName(el) {
            return el.querySelector('[data-e2e="dm-new-conversation-nickname"]')
                ?.innerText
                ?.trim() || "";
        }

        function getConversationMessage(el) {
            return el.querySelector('[class*="SpanInfoExtract"]')
                ?.innerText
                ?.trim() || "";
        }

        function getConversationTime(el) {
            return el.querySelector('[class*="SpanInfoTime"]')
                ?.innerText
                ?.trim() || "";
        }

        function getConversationId(el) {
            return el.getAttribute("data-conv-id")
                || el.id
                || el.getAttribute("data-index")
                || "";
        }

        function findConversationItemFromPath(path) {
            return path.closest('[data-e2e="dm-new-conversation-item"]')
                || path.closest('[data-index]')
                || path.closest('div');
        }

        function addUniqueTarget(map, el, source) {
            if (!el) {
                return;
            }

            const name = getConversationName(el);

            if (!name) {
                return;
            }

            const convId = getConversationId(el);
            const dataIndex = el.getAttribute("data-index") || "";
            const key = convId || dataIndex || name;

            if (!map.has(key)) {
                map.set(key, {
                    el,
                    sources: new Set(),
                    name,
                    convId,
                    dataIndex,
                    message: getConversationMessage(el),
                    time: getConversationTime(el),
                });
            }

            map.get(key).sources.add(source);
        }

        const targetMap = new Map();

        // Method 1: detect pinned conversations by pin icon path.
        const pinnedItems = [...document.querySelectorAll("path")]
            .filter(path => path.getAttribute("d")?.startsWith(PIN_PATH_D))
            .map(path => findConversationItemFromPath(path))
            .filter(Boolean);

        for (const el of pinnedItems) {
            addUniqueTarget(targetMap, el, "pin");
        }

        // Method 2: detect target conversations by class key.
        const conversationItems = [...document.querySelectorAll('[data-e2e="dm-new-conversation-item"]')];

        for (const el of conversationItems) {
            const className = String(el.className || "");

            if (className.includes(TARGET_CLASS_KEY)) {
                addUniqueTarget(targetMap, el, "class");
            }
        }

        return [...targetMap.values()].map((item, index) => {
            return {
                index,
                id: item.el.id || "",
                convId: item.convId || "",
                dataIndex: item.dataIndex || "",
                name: item.name || "",
                message: item.message || "",
                time: item.time || "",
                source: [...item.sources].join("+"),
            };
        });
        """
    )

    return targets or []


def color_text(text: str, color_code: str) -> str:
    return f"\033[{color_code}m{text}\033[0m"


def log_collected_targets(targets: list[dict]) -> None:
    logging.info("Collected target count: %s", len(targets))

    print("")
    print(color_text("Collected targets:", "96;1"))
    print(color_text("------------------", "90"))

    for index, target in enumerate(send_targets, start=1):
        name = target.get("name", "")
        target_id = target.get("id", "")
        target_index = target.get("index", "")
        target_source = target.get("source", "")

        logging.info(
            "Target %s: name=%s id=%s index=%s source=%s",
            index,
            name,
            target_id,
            target_index,
            target_source,
        )

        number_part = color_text(f"{index}.", "93;1")
        name_part = color_text(name, "92;1")
        id_part = color_text(f"id={target_id}", "94")
        index_part = color_text(f"index={target_index}", "95")
        source_part = color_text(f"source={target_source}", "96")
        
        print(f"{number_part} {name_part} | {id_part} | {index_part} | {source_part}")

    print(color_text("------------------", "90"))
    print("")


def click_chat_by_target(driver: webdriver.Chrome, target: dict) -> None:
    target_id = target.get("id", "")
    target_conv_id = target.get("convId", "")
    target_name = target.get("name", "")
    target_data_index = target.get("dataIndex", "")

    clicked = driver.execute_script(
        """
        const targetId = arguments[0];
        const targetConvId = arguments[1];
        const targetName = arguments[2];
        const targetDataIndex = arguments[3];

        const PIN_PATH_D = "M31.6 3.67a3 3 0 0 0-4.24 0l-.7.7";

        const TARGET_CLASS_KEY = "css-k8n8bd";

        function getConversationName(el) {
            return el.querySelector('[data-e2e="dm-new-conversation-nickname"]')
                ?.innerText
                ?.trim() || "";
        }

        function getConversationId(el) {
            return el.getAttribute("data-conv-id")
                || el.id
                || el.getAttribute("data-index")
                || "";
        }

        function findConversationItemFromPath(path) {
            return path.closest('[data-e2e="dm-new-conversation-item"]')
                || path.closest('[data-index]')
                || path.closest('div');
        }

        function addUniqueItem(map, el) {
            if (!el) {
                return;
            }

            const name = getConversationName(el);

            if (!name) {
                return;
            }

            const convId = getConversationId(el);
            const dataIndex = el.getAttribute("data-index") || "";
            const key = convId || dataIndex || name;

            if (!map.has(key)) {
                map.set(key, el);
            }
        }

        const itemMap = new Map();

        // Method 1: pinned icon.
        const pinnedItems = [...document.querySelectorAll("path")]
            .filter(path => path.getAttribute("d")?.startsWith(PIN_PATH_D))
            .map(path => findConversationItemFromPath(path))
            .filter(Boolean);

        for (const el of pinnedItems) {
            addUniqueItem(itemMap, el);
        }

        // Method 2: class key.
        const conversationItems = [...document.querySelectorAll('[data-e2e="dm-new-conversation-item"]')];

        for (const el of conversationItems) {
            const className = String(el.className || "");

            if (className.includes(TARGET_CLASS_KEY)) {
                addUniqueItem(itemMap, el);
            }
        }

        const items = [...itemMap.values()];

        let item = null;

        if (targetId) {
            item = items.find(el => el.id === targetId);
        }

        if (!item && targetConvId) {
            item = items.find(el => el.getAttribute("data-conv-id") === targetConvId);
        }

        if (!item && targetDataIndex) {
            item = items.find(el => el.getAttribute("data-index") === targetDataIndex);
        }

        if (!item && targetName) {
            item = items.find(el => getConversationName(el) === targetName);
        }

        if (!item) {
            return false;
        }

        item.scrollIntoView({ block: "center" });

        item.dispatchEvent(new MouseEvent("mouseover", {
            bubbles: true,
            cancelable: true,
            view: window
        }));

        item.dispatchEvent(new MouseEvent("mousedown", {
            bubbles: true,
            cancelable: true,
            view: window
        }));

        item.dispatchEvent(new MouseEvent("mouseup", {
            bubbles: true,
            cancelable: true,
            view: window
        }));

        item.click();

        return true;
        """,
        target_id,
        target_conv_id,
        target_name,
        target_data_index,
    )

    if not clicked:
        raise TimeoutException(f"Could not click target chat: {target_name}")

    time.sleep(1)


def find_message_box(driver: webdriver.Chrome):
    wait = WebDriverWait(driver, WAIT_SECONDS)
    composer_xpaths = [
        "//*[@contenteditable='true' and not(ancestor::*[@role='search'])]",
        "//*[@role='textbox' and not(self::input) and not(ancestor::*[@role='search'])]",
        "//textarea[not(ancestor::*[@role='search'])]",
    ]

    end_time = time.time() + WAIT_SECONDS
    while time.time() < end_time:
        for xpath in composer_xpaths:
            elements = find_visible_elements(driver, xpath)
            if elements:
                return elements[-1]
        time.sleep(1)

    return wait.until(EC.visibility_of_element_located((By.XPATH, composer_xpaths[0])))


def element_text_and_labels(element) -> str:
    values = []
    for attr in ("aria-label", "title", "data-e2e", "data-testid"):
        value = element.get_attribute(attr)
        if value:
            values.append(value)

    text = element.text
    if text:
        values.append(text)

    return " ".join(values).strip().lower()


def is_upload_or_attach_button(element) -> bool:
    if element.find_elements(
        By.XPATH,
        ".//input[@type='file'] | ./ancestor-or-self::label[.//input[@type='file']]",
    ):
        return True

    label_text = element_text_and_labels(element)
    blocked_terms = (
        "upload",
        "attach",
        "attachment",
        "file",
        "image",
        "photo",
        "video",
        "media",
    )
    return any(term in label_text for term in blocked_terms)


def is_send_button(element) -> bool:
    if is_upload_or_attach_button(element):
        return False

    label_text = element_text_and_labels(element)
    send_terms = ("message-send", "send")
    return any(term in label_text for term in send_terms)


def click_send_button_if_available(driver: webdriver.Chrome) -> bool:
    send_xpaths = [
        "//*[@data-e2e='message-send' and not(@disabled)]",
        "//button[not(@disabled) and contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send')]",
        "//*[@role='button' and not(@aria-disabled='true') and contains(translate(@aria-label, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'send')]",
    ]

    for xpath in send_xpaths:
        for button in find_visible_elements(driver, xpath):
            if is_send_button(button):
                click_element(driver, button)
                return True

    return False


def set_message_text(driver: webdriver.Chrome, element, message: str) -> None:
    driver.execute_script(
        """
        const editor = arguments[0];
        const text = arguments[1];

        if (!editor) {
            throw new Error("Editor not found");
        }

        const block =
            editor.querySelector(".public-DraftStyleDefault-block") ||
            editor.querySelector("[data-block='true']") ||
            editor;

        if (!block) {
            throw new Error("Draft block not found");
        }

        block.innerHTML = "";

        const span = document.createElement("span");
        span.setAttribute(
            "data-offset-key",
            block.getAttribute("data-offset-key") || "selenium-0-0"
        );
        span.textContent = text;

        block.appendChild(span);

        editor.focus();

        editor.dispatchEvent(
            new InputEvent("input", {
                bubbles: true,
                inputType: "insertText",
                data: text,
            })
        );

        editor.dispatchEvent(new Event("change", { bubbles: true }));
        """,
        element,
        message,
    )


def send_message(driver: webdriver.Chrome, message: str) -> None:
    message_box = find_message_box(driver)
    click_element(driver, message_box)

    logging.info("Setting message text using JavaScript.")
    set_message_text(driver, message_box, message)
    time.sleep(1)

    if click_send_button_if_available(driver):
        logging.info("Clicked send button.")
        time.sleep(1)
        return

    logging.warning("Send button not found, trying Enter key.")
    message_box.send_keys(Keys.ENTER)
    time.sleep(1)


def quit_driver(driver: webdriver.Chrome | None) -> None:
    if not driver:
        return

    def shutdown():
        try:
            driver.quit()
        except Exception:
            pass

    thread = threading.Thread(target=shutdown, daemon=True)
    thread.start()
    thread.join(timeout=8)

    if thread.is_alive():
        logging.warning("driver.quit() timed out; continuing shutdown")


def create_tiktok_driver_with_cookies(cookies: list[dict], log_prefix: str = ""):
    driver = None
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        driver = webdriver.Chrome(options=options)

        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })

        wait = WebDriverWait(driver, WAIT_SECONDS)

        logging.info("%sStarting TikTok...", log_prefix)
        driver.get(BASE_URL)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        logging.info("%sDeleting all cookies...", log_prefix)
        driver.delete_all_cookies()
        time.sleep(1)

        added = 0
        for cookie in cookies:
            if cookie.get("expiry") and cookie["expiry"] <= int(time.time()):
                logging.warning("%sSkipped expired cookie %s", log_prefix, cookie.get("name"))
                continue

            try:
                driver.add_cookie(cookie)
                added += 1
            except (InvalidCookieDomainException, WebDriverException) as exc:
                logging.warning(
                    "%sSkipped cookie name=%s domain=%s path=%s reason=%s",
                    log_prefix,
                    cookie.get("name"),
                    cookie.get("domain"),
                    cookie.get("path"),
                    exc,
                )

        logging.info("%sAdded cookies: %s/%s", log_prefix, added, len(cookies))

        logging.info("%sRefreshing webpage...", log_prefix)
        driver.refresh()
        time.sleep(10)

        logging.info("%sDirecting to message: %s", log_prefix, MESSAGES_URL)
        driver.get(MESSAGES_URL)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        logging.info("%sWaiting 10 seconds for conversations to load...", log_prefix)
        time.sleep(10)

        return driver, wait

    except Exception:
        if driver:
            quit_driver(driver)
        raise


def precheck_tiktok_cookies(
    cookies: list[dict],
    notify_success: bool = False,
    keep_driver: bool = False,
) -> tuple[list[dict], webdriver.Chrome | None]:
    if not PRECHECK_BEFORE_WAIT:
        logging.info("PRECHECK_BEFORE_WAIT=False, cookie precheck skipped.")
        return [], None

    driver = None
    should_quit_driver = True

    try:
        logging.info("Starting TikTok cookie precheck...")
        driver, _wait = create_tiktok_driver_with_cookies(cookies, "Precheck ")

        logging.info("Precheck collecting target conversations...")
        targets = get_target_conversations(driver)

        if not targets:
            screenshot_path = "precheck_no_targets.png"

            try:
                driver.save_screenshot(screenshot_path)
                logging.info("Saved precheck_no_targets.png")
            except Exception as screenshot_err:
                logging.warning(f"Could not save precheck screenshot: {screenshot_err}")

            notify(
                "❌ TikTok cookie problem\n"
                "Could not find any target conversations.\n"
                "The session may be logged out or the cookie may be invalid.",
                screenshot_path,
            )

            raise RuntimeError("Cookie precheck failed: no target conversations found")

        logging.info("Cookie precheck passed. Target count: %s", len(targets))

        if notify_success:
            notify(
                "✅ First TikTok precheck passed\n"
                f"Targets: {len(targets)}"
            )

        if DEBUG_MODE:
            log_collected_targets(targets)

        try:
            driver.save_screenshot("precheck_success.png")
            logging.info("Saved precheck_success.png")
        except Exception as screenshot_err:
            logging.warning(f"Could not save precheck screenshot: {screenshot_err}")

        if keep_driver:
            should_quit_driver = False
            logging.info("Returning precheck browser for reuse decision.")
            return targets, driver

        return targets, None

    except Exception as e:
        logging.error(f"Precheck failed: {str(e)}", exc_info=True)
        raise

    finally:
        if driver and should_quit_driver:
            quit_driver(driver)


def open_tiktok_with_cookies(
    cookies: list[dict],
    driver: webdriver.Chrome | None = None,
) -> None:
    try:
        if driver:
            logging.info("Using existing TikTok browser from final precheck.")
            try:
                wait = WebDriverWait(driver, WAIT_SECONDS)
                logging.info("Refreshing existing messages page before final run...")
                driver.get(MESSAGES_URL)
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                driver.refresh()
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(10)
            except WebDriverException as exc:
                logging.warning(
                    "Existing TikTok browser could not be reused: %s. Opening a new browser.",
                    exc,
                )
                quit_driver(driver)
                driver = None
                driver, wait = create_tiktok_driver_with_cookies(cookies)
        else:
            driver, wait = create_tiktok_driver_with_cookies(cookies)

        logging.info("Collecting target conversations...")
        targets = get_target_conversations(driver)

        if not targets:
            screenshot_path = "no_targets_final.png"

            try:
                driver.save_screenshot(screenshot_path)
                logging.info("Saved no_targets_final.png")
            except Exception as screenshot_err:
                logging.warning(f"Could not save no target screenshot: {screenshot_err}")

            notify(
                "❌ TikTok cookie problem\n"
                "Could not find any target conversations during the final run.\n"
                "The session may be logged out or the cookie may be invalid.",
                screenshot_path,
            )

            raise TimeoutException("No target conversations found")

        send_targets, excluded_targets = split_targets_by_exception(targets)
        
        if excluded_targets:
            excluded_names = ", ".join(target.get("name", "") for target in excluded_targets)
            logging.info(
                "Excluded target count: %s. Names: %s",
                len(excluded_targets),
                excluded_names,
            )
        
        if DEBUG_MODE:
            log_collected_targets(targets)
        
            target_names = ", ".join(target.get("name", "") for target in targets)
            send_names = ", ".join(target.get("name", "") for target in send_targets) or "(none)"
            excluded_names = ", ".join(target.get("name", "") for target in excluded_targets) or "(none)"
        
            notify(
                "Target collection succeeded.\n"
                f"Pinned targets: {len(targets)}\n"
                f"Will send: {len(send_targets)}\n"
                f"Excluded: {len(excluded_targets)}\n"
                f"Target names: {target_names}\n"
                f"Send names: {send_names}\n"
                f"Excluded names: {excluded_names}"
            )
        
            logging.info("DEBUG_MODE=True, message sending skipped.")
            return
        
        if not send_targets:
            notify(
                "✅ TikTok bot completed\n"
                "No messages were sent because all pinned targets are in exception.txt."
            )
            logging.info("All pinned targets are excluded. No messages will be sent.")
            return

        for index, target in enumerate(send_targets, start=1):
            logging.info(
                "Opening target conversation %s/%s: %s",
                index,
                len(send_targets),
                target["name"],
            )

            click_chat_by_target(driver, target)

            message_text = get_random_message_text()

            logging.info("Sending message to %s: '%s'", target["name"], message_text)
            send_message(driver, message_text)
            logging.info("Sent message to %s", target["name"])

            time.sleep(1)

    except Exception as e:
        logging.error(f"Error during execution: {str(e)}", exc_info=True)
        raise

    finally:
        if driver:
            try:
                driver.save_screenshot("final_screenshot.png")
                logging.info("Saved final screenshot successfully.")
            except Exception as screenshot_err:
                logging.warning(f"Could not save final screenshot: {screenshot_err}")

            quit_driver(driver)


def get_target_datetime() -> datetime:
    parts = TARGET_RUN_TIME.split(":")

    if len(parts) == 2:
        target_hour = int(parts[0])
        target_minute = int(parts[1])
        target_second = 0
    elif len(parts) == 3:
        target_hour = int(parts[0])
        target_minute = int(parts[1])
        target_second = int(parts[2])
    else:
        raise ValueError(f"Invalid TARGET_RUN_TIME format: {TARGET_RUN_TIME}. Use HH:MM or HH:MM:SS")

    now = datetime.now(TARGET_TIMEZONE)

    return now.replace(
        hour=target_hour,
        minute=target_minute,
        second=target_second,
        microsecond=0,
    )


def precheck_until_near_target_time(cookies: list[dict]) -> webdriver.Chrome | None:
    if DEBUG_MODE:
        logging.info("DEBUG_MODE=True, skipping precheck.")
        return None

    if not PRECHECK_BEFORE_WAIT:
        logging.info("PRECHECK_BEFORE_WAIT=False, periodic precheck skipped.")
        return None

    if not WAIT_UNTIL_TARGET_TIME:
        logging.info("WAIT_UNTIL_TARGET_TIME=False, skipping precheck and starting immediately.")
        return None

    interval_seconds = PRECHECK_INTERVAL_MINUTES * 60
    stop_within_seconds = PRECHECK_STOP_WITHIN_MINUTES * 60

    first_precheck_start = datetime.now(TARGET_TIMEZONE)
    precheck_round = 0

    while True:
        now = datetime.now(TARGET_TIMEZONE)
        target = get_target_datetime()
        remaining_seconds = int((target - now).total_seconds())

        if remaining_seconds <= 0:
            logging.info(
                "Target time already passed before precheck loop. Now=%s Target=%s. Starting immediately.",
                now.strftime("%Y-%m-%d %H:%M:%S %Z"),
                target.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )
            return None

        if remaining_seconds <= stop_within_seconds:
            logging.info(
                "Target time is near. Remaining=%s seconds, stop precheck threshold=%s seconds. Skipping further precheck.",
                remaining_seconds,
                stop_within_seconds,
            )
            return None

        precheck_round += 1
        precheck_start = datetime.now(TARGET_TIMEZONE)

        logging.info(
            "Running periodic precheck round %s. Now=%s Target=%s Remaining=%s seconds.",
            precheck_round,
            precheck_start.strftime("%Y-%m-%d %H:%M:%S %Z"),
            target.strftime("%Y-%m-%d %H:%M:%S %Z"),
            remaining_seconds,
        )

        _targets, precheck_driver = precheck_tiktok_cookies(
            cookies,
            notify_success=(precheck_round == 1),
            keep_driver=True,
        )

        precheck_end = datetime.now(TARGET_TIMEZONE)
        precheck_duration_seconds = int((precheck_end - precheck_start).total_seconds())

        now = precheck_end
        target = get_target_datetime()
        remaining_seconds = int((target - now).total_seconds())

        logging.info(
            "Precheck round %s passed. Duration=%s seconds. Remaining=%s seconds.",
            precheck_round,
            precheck_duration_seconds,
            remaining_seconds,
        )

        if remaining_seconds <= stop_within_seconds:
            logging.info(
                "Target time is now near. Remaining=%s seconds. Keeping browser open for target time.",
                remaining_seconds,
            )
            return precheck_driver

        next_precheck_time = first_precheck_start + timedelta(
            seconds=precheck_round * interval_seconds
        )

        latest_allowed_precheck_time = target - timedelta(seconds=stop_within_seconds)

        if next_precheck_time > latest_allowed_precheck_time:
            logging.info(
                "Next precheck time would be too close to target. Next=%s LatestAllowed=%s. Keeping browser open for target time.",
                next_precheck_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
                latest_allowed_precheck_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
            )
            return precheck_driver

        quit_driver(precheck_driver)

        sleep_seconds = int((next_precheck_time - datetime.now(TARGET_TIMEZONE)).total_seconds())

        if sleep_seconds <= 0:
            logging.info(
                "Next precheck time already reached or passed. Continuing immediately."
            )
            continue

        logging.info(
            "Sleeping %s seconds until next fixed precheck time: %s",
            sleep_seconds,
            next_precheck_time.strftime("%Y-%m-%d %H:%M:%S %Z"),
        )

        time.sleep(sleep_seconds)


def wait_until_scheduled_time() -> None:
    if DEBUG_MODE:
        logging.info("DEBUG_MODE=True, skipping target time wait.")
        return

    if not WAIT_UNTIL_TARGET_TIME:
        logging.info("WAIT_UNTIL_TARGET_TIME=False, starting immediately.")
        return

    now = datetime.now(TARGET_TIMEZONE)
    target = get_target_datetime()

    if now >= target:
        logging.info(
            "Target time already passed. Now=%s Target=%s. Starting immediately.",
            now.strftime("%Y-%m-%d %H:%M:%S %Z"),
            target.strftime("%Y-%m-%d %H:%M:%S %Z"),
        )
        return

    wait_seconds = int((target - now).total_seconds())

    logging.info(
        "Waiting until target time. Now=%s Target=%s Wait=%s seconds.",
        now.strftime("%Y-%m-%d %H:%M:%S %Z"),
        target.strftime("%Y-%m-%d %H:%M:%S %Z"),
        wait_seconds,
    )

    remaining = wait_seconds

    while remaining > 0:
        sleep_seconds = min(10, remaining)
        time.sleep(sleep_seconds)
        remaining -= sleep_seconds

    logging.info("Target time reached. Starting bot.")


def post_multipart(url: str, fields: dict, files: list[tuple[str, str]]) -> None:
    boundary = uuid.uuid4().hex
    body = bytearray()

    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        body.extend(str(value).encode("utf-8"))
        body.extend(b"\r\n")

    for field_name, file_path in files:
        path = Path(file_path)
        filename = path.name
        content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(
            f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8")
        )
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        body.extend(path.read_bytes())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    request = urllib.request.Request(
        url,
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": DISCORD_USER_AGENT,
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()


def format_discord_message(message: str) -> str:
    lines = message.splitlines()

    if len(lines) <= 1:
        return message

    first_line = lines[0]
    rest_lines = lines[1:]

    formatted_rest = "\n".join(
        f"> {line}" if line.strip() else ">"
        for line in rest_lines
    )

    return f"{first_line}\n{formatted_rest}"


def notify(message: str, image_path: str | None = None) -> None:
    if not ENABLE_NOTIFY:
        return

    discord_webhook_url = load_optional_secret_text(DISCORD_WEBHOOK_FILE)
    telegram_bot_token = load_optional_secret_text(TELEGRAM_BOT_TOKEN_FILE)
    telegram_chat_id = load_optional_secret_text(TELEGRAM_CHAT_ID_FILE)

    sent = False
    image_exists = bool(image_path and Path(image_path).exists())

    if discord_webhook_url:
        try:
            if image_exists:
                post_multipart(
                    discord_webhook_url,
                    {"payload_json": json.dumps({"content": format_discord_message(message)}, ensure_ascii=False)},
                    [("file", image_path)],
                )
            else:
                payload = json.dumps({"content": format_discord_message(message)}, ensure_ascii=False).encode("utf-8")
                request = urllib.request.Request(
                    discord_webhook_url,
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": DISCORD_USER_AGENT,
                    },
                    method="POST",
                )

                with urllib.request.urlopen(request, timeout=15) as response:
                    response.read()

            logging.info("Discord notification sent.")
            sent = True
        except Exception as exc:
            logging.warning("Discord notification failed: %s", exc)

    if telegram_bot_token and telegram_chat_id:
        try:
            if image_exists:
                url = f"https://api.telegram.org/bot{telegram_bot_token}/sendPhoto"
                post_multipart(
                    url,
                    {
                        "chat_id": telegram_chat_id,
                        "caption": message,
                    },
                    [("photo", image_path)],
                )
            else:
                url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
                data = urllib.parse.urlencode(
                    {
                        "chat_id": telegram_chat_id,
                        "text": message,
                    }
                ).encode("utf-8")

                request = urllib.request.Request(url, data=data, method="POST")

                with urllib.request.urlopen(request, timeout=15) as response:
                    response.read()

            logging.info("Telegram notification sent.")
            sent = True
        except Exception as exc:
            logging.warning("Telegram notification failed: %s", exc)

    if not sent:
        logging.info("Notification skipped because no valid notify channel is configured.")


def main() -> int:
    logging.info("Starting TikTok Automation Bot...")

    try:
        cookie_text = load_cookie_text(COOKIE_FILE)
        cookies = parse_cookies(cookie_text)

        driver = precheck_until_near_target_time(cookies)

        wait_until_scheduled_time()

        open_tiktok_with_cookies(cookies, driver=driver)

        logging.info("Bot executed successfully.")

        if not DEBUG_MODE:
            notify("✅ TikTok messages sent successfully.")

        return 0

    except FileNotFoundError as e:
        logging.critical(f"Bot failed: {str(e)}")

        if str(COOKIE_FILE) in str(e) or "cookie" in str(e).lower():
            notify(
                "❌ TikTok cookie file not found\n"
                f"Missing file: {COOKIE_FILE}\n"
                "Please check that the COOKIE secret exists and that cookie.txt is created before running Program.py."
            )
        else:
            notify(
                "❌ Required file not found\n"
                f"Error: {str(e)}"
            )

        return 1

    except ValueError as e:
        logging.critical(f"Bot failed: {str(e)}")

        if "cookie.txt is empty" in str(e).lower() or "cookie" in str(e).lower():
            notify(
                "❌ TikTok cookie file is empty\n"
                f"File found: {COOKIE_FILE}\n"
                "cookie.txt exists, but it does not contain any cookie data.\n"
                "Please check that the COOKIE secret is not empty."
            )
        else:
            notify(
                "❌ TikTok bot configuration error\n"
                f"Error: {str(e)}"
            )

        return 1

    except Exception as e:
        logging.critical(f"Bot failed: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
