"""
Red Alerts Israel - AppDaemon App for Home Assistant
===================================================

Monitors the official Israeli Home Front Command (Pikud HaOref) API for rocket alerts (Red Alerts / Tseva Adom) and makes the information available in Home Assistant.

**Configuration:**
1.  Open your AppDaemon `apps/apps.yaml` file.
2.  Add the configuration block below, adjusting the settings as needed.
3.  Choose your specific `city_names` from the list provided here: https://github.com/idodov/RedAlert/blob/main/cities_name.md
4.  Save `apps.yaml`.

**Example `apps.yaml` Configuration:**

red_alerts_israel:
  module: red_alerts_israel      # Python module name (don't change)
  class: Red_Alerts_Israel        # Class name (don't change)

  # --- Core Settings ---
  interval: 5                   # (Seconds) How often to check the API for alerts. Default: 5
  timer: 120                    # (Seconds) How long the sensor stays 'on' after the *last* alert activity. Default: 120
  sensor_name: "red_alert"      # Base name for all created entities. Choose a unique name.

  # --- History & Saving ---
  save_2_file: True             # Set to True to save history (.txt, .csv) and GeoJSON files to the 'www' folder. Default: True
  hours_to_show: 4              # (Hours) How far back the history sensors should track alerts. Default: 4

  # --- Optional Features ---
  mqtt: False                   # Set to True to publish alert details via MQTT to 'home/[sensor_name]/event'. Default: False
  event: True                   # Set to True to fire Home Assistant events named '[sensor_name]_event' when alerts occur. Default: True

  # --- Location Specific ---
  city_names:                   # List the exact city/area names you want to monitor for the city_sensor.
     - "אזור תעשייה צפוני אשקלון"  # Example: Ashkelon Industrial Zone North
     - "חיפה - מפרץ"             # Example: Haifa Bay
     - "תל אביב - מרכז העיר"        # Example: Tel Aviv - City Center

"""

import aiohttp
import asyncio
import re
import functools
import time
import json
import traceback
import random
import os
import csv
import atexit
from collections import defaultdict
from datetime import datetime, timedelta
from io import StringIO
from aiohttp import TCPConnector, ClientTimeout
from appdaemon.plugins.hass.hassapi import Hass

# ─── Singleton guard: prevents double‑initialisation ───
_IS_RAI_RUNNING = False

# Pre-compile regex once
CLEAN_NAME_REGEX = re.compile(r'[\(\)\'"]+')

# Determine the script's directory
script_directory = os.path.dirname(os.path.realpath(__file__))

# --- Module Level Constants ---
ICONS_AND_EMOJIS = {
    0: ("mdi:alert", "❗"),   1: ("mdi:rocket-launch", "🚀"), 2: ("mdi:home-alert", "⚠️"),
    3: ("mdi:earth-box", "🌍"), 4: ("mdi:chemical-weapon", "☢️"), 5: ("mdi:waves", "🌊"),
    6: ("mdi:airplane", "🛩️"), 7: ("mdi:skull", "💀"), 8: ("mdi:alert", "❗"),
    9: ("mdi:alert", "❗"),   10:("mdi:Home-Alert","⚠️"),   11:("mdi:alert","❗"),
    12:("mdi:alert","❗"),    13:("mdi:run-fast","👹"), 14:("mdi:alert", "❗"), 15: ("mdi:alert-circle-Outline", "⭕")
}
DAY_NAMES = {
    'Sunday': 'יום ראשון', 'Monday': 'יום שני', 'Tuesday': 'יום שלישי',
    'Wednesday': 'יום רביעי', 'Thursday': 'יום חמישי',
    'Friday': 'יום שישי', 'Saturday': 'יום שבת'
}
DEFAULT_UNKNOWN_AREA = "ישראל"

@functools.lru_cache(maxsize=None)
def standardize_name(name: str) -> str:
    """Return a city name stripped of parentheses / quotes and extra spaces, with special handling for ג'ת."""
    if not isinstance(name, str):
        return ""

    stripped_name = name.strip()

    # Special case: If the name is exactly "ג'ת" or "ח'וואלד", return it as is
    if stripped_name == "ג'ת" or stripped_name == "ח'וואלד":
        return stripped_name

    return CLEAN_NAME_REGEX.sub("", stripped_name) 

def check_bom(text: str) -> str:
    """Remove BOM if present"""
    if text.startswith('\ufeff'):
        text = text.lstrip('\ufeff')
    return text

def parse_datetime_str(ds: str, logger_func=None) -> datetime | None:
    """Parses various datetime string formats into datetime objects."""
    if not ds or not isinstance(ds, str): return None
    ds = ds.strip().strip('"')
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f", # ISO with microseconds
        "%Y-%m-%dT%H:%M:%S",    # ISO without microseconds
        "%Y-%m-%d %H:%M:%S.%f", # Space separated with microseconds
        "%Y-%m-%d %H:%M:%S"     # Space separated without microseconds
    ]
    for fmt in formats:
        try: return datetime.strptime(ds, fmt)
        except ValueError: pass
    try:
        # Handle ISO format with timezone (make naive for comparison)
        if '+' in ds: ds = ds.split('+')[0]
        if 'Z' in ds: ds = ds.split('Z')[0]
        # Try parsing again after stripping potential timezone info
        for iso_fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]:
            try: return datetime.strptime(ds, iso_fmt)
            except ValueError: pass
        # Last attempt with fromisoformat
        return datetime.fromisoformat(ds)
    except ValueError:
        return None
    except Exception as e:
        if logger_func:
            logger_func(f"Unexpected error parsing datetime string '{ds}': {e}", level="WARNING")
        return None

def get_convex_hull(points):
    """Computes the convex hull of a set of points (Monotone Chain algorithm)."""
    n = len(points)
    if n <= 2: return points
    points.sort()
    def cross_product(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in points:
        while len(lower) >= 2 and cross_product(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(points):
        while len(upper) >= 2 and cross_product(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]

# ----------------------------------------------------------------------
# Helper Class: OrefAPIClient
# ----------------------------------------------------------------------
class OrefAPIClient:
    def __init__(self, session, urls, logger):
        self._session = session
        self._urls    = urls
        self._log     = logger

    async def _fetch_with_retries(self, fetch_func, retries: int = 2):
        """Retry on network errors with exponential backoff."""
        for attempt in range(retries + 1):
            try:
                return await fetch_func()
            except (aiohttp.ClientError, asyncio.TimeoutError):
                if attempt == retries:
                    self._log(f"Network error after {retries+1} attempts.", level="WARNING")
                    raise
                wait = 0.5 * (2 ** attempt) + random.uniform(0, 0.5) # Add jitter
                self._log(f"Network error (attempt {attempt+1}/{retries+1}). Retrying in {wait:.2f}s.", level="DEBUG")
                await asyncio.sleep(wait)

    async def get_live_alerts(self):
        """Fetch live alerts, return dict or None."""
        url = self._urls.get("live")
        if not url:
            self._log("Live alerts URL not configured.", level="ERROR")
            return None
        try:
            async def _do_fetch():
                async with self._session.get(url) as resp:
                    resp.raise_for_status()
                    if 'application/json' not in resp.headers.get('Content-Type', ''):
                        self._log(f"Warning: Expected JSON content type, got {resp.headers.get('Content-Type')}", level="WARNING")
                    raw_data = await resp.read()
                    try:
                        return raw_data.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        self._log("Failed decoding with utf-8-sig, trying utf-8.", level="DEBUG")
                        return raw_data.decode('utf-8')

            text = await self._fetch_with_retries(_do_fetch)

            if not text or not text.strip():
                return None

            try:
                text = check_bom(text)
                return json.loads(text)
            except json.JSONDecodeError as e:
                log_text_preview = text[:1000].replace('\n', '\\n').replace('\r', '\\r') 
                if "Expecting value: line 1 column 1 (char 0)" in str(e) and len(text) > 0:
                    pass
                else:
                    self._log(f"Invalid JSON in live alerts: {e}. Raw text preview: '{log_text_preview}...'", level="WARNING")
                return None

        except aiohttp.ClientResponseError as e:
            self._log(f"HTTP error fetching live alerts: Status {e.status}, Message: {e.message}", level="WARNING")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e: 
            self._log(f"Network/Timeout error fetching live alerts: {e}", level="WARNING")
        except Exception as e:
            self._log(f"Unexpected error fetching live alerts: {e.__class__.__name__} - {e}", level="ERROR")

        return None

    async def get_alert_history(self):
        """Fetch alert history, return list or None."""
        url = self._urls.get("history")
        if not url:
            self._log("History alerts URL not configured.", level="ERROR")
            return None
        try:
            async def _do_fetch():
                async with self._session.get(url) as resp:
                    resp.raise_for_status()
                    raw_data = await resp.read()
                    try:
                        return raw_data.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        return raw_data.decode('utf-8')

            text = await self._fetch_with_retries(_do_fetch)
            if not text or not text.strip():
                return None
            try:
                text = check_bom(text)
                data = json.loads(text)
                if isinstance(data, list):
                    return data
                self._log("History response is not a list", level="WARNING")
                return None
            except json.JSONDecodeError as e:
                log_text_preview = text[:5500].replace('\n', '\\n').replace('\r', '\\r')
                self._log(f"Invalid JSON in history alerts: {e}. Raw text preview: '{log_text_preview}...'", level="WARNING")
                return None
        except aiohttp.ClientResponseError as e:
            self._log(f"HTTP error fetching history: Status {e.status}, Message: {e.message}", level="WARNING")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self._log(f"Network/Timeout error fetching history: {e}", level="WARNING")
        except Exception as e:
            self._log(f"Unexpected error fetching history: {e}", level="ERROR")
        return None

    async def download_file(self, url: str):
        """Download text content (e.g. Lamas data), return str or None."""
        try:
            async def _do_fetch():
                async with self._session.get(url) as resp:
                    resp.raise_for_status()
                    raw_data = await resp.read()
                    try:
                        return raw_data.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        return raw_data.decode('utf-8')
            text = await self._fetch_with_retries(_do_fetch)
            text = check_bom(text)
            return text
        except aiohttp.ClientResponseError as e:
            self._log(f"HTTP error downloading file {url}: Status {e.status}, Message: {e.message}", level="ERROR")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self._log(f"Network/Timeout error downloading file {url}: {e}", level="ERROR")
        except Exception as e:
            self._log(f"Unexpected error downloading file {url}: {e}", level="ERROR")
        return None

# ----------------------------------------------------------------------
# Helper Class: LamasDataManager
# ----------------------------------------------------------------------
class LamasDataManager:
    def __init__(self, file_path, github_url, api_client, logger):
        self._local_file_path = file_path
        self._github_url      = github_url
        self._api_client      = api_client
        self._log             = logger
        self._lamas_data      = None
        self._city_details_map= {}

    async def load_data(self, force_download=False):
        """Loads Lamas data, preferring local file unless forced or missing/invalid."""
        loaded = None
        if not force_download and os.path.exists(self._local_file_path):
            try:
                with open(self._local_file_path, 'r', encoding='utf-8-sig') as f:
                    loaded = json.load(f)
                if loaded and 'areas' in loaded: 
                    pass
                else:
                    self._log("Local Lamas data invalid or empty. Will attempt download.", level="WARNING")
                    loaded = None 
            except (json.JSONDecodeError, OSError, Exception) as e:
                self._log(f"Error reading local Lamas file '{self._local_file_path}': {e}. Will attempt download.", level="WARNING")
                loaded = None 

        if loaded is None:
            self._log("Downloading Lamas data from GitHub.")
            text = await self._api_client.download_file(self._github_url)
            if text:
                try:
                    text = check_bom(text)
                    loaded = json.loads(text)
                    if loaded and 'areas' in loaded: 
                        try:
                            os.makedirs(os.path.dirname(self._local_file_path), exist_ok=True)
                            with open(self._local_file_path, 'w', encoding='utf-8-sig') as f:
                                json.dump(loaded, f, ensure_ascii=False, indent=2) 
                            self._log("Lamas data downloaded and saved locally.")
                        except Exception as e:
                            self._log(f"Error saving Lamas data locally to '{self._local_file_path}': {e}", level="ERROR")
                    else:
                        self._log("Downloaded Lamas data is invalid (missing 'areas' key).", level="ERROR")
                        loaded = None 
                except json.JSONDecodeError as e:
                    self._log(f"Invalid Lamas JSON downloaded from '{self._github_url}': {e}", level="ERROR")
                    loaded = None 
            else:
                self._log("Failed to download Lamas data.", level="ERROR")

        if loaded and self._process_lamas_data(loaded):
            self._build_city_details_map()
            return True

        self._log("CRITICAL: Failed to load Lamas data from both local file and download.", level="CRITICAL")
        self._lamas_data = None
        self._city_details_map = {}
        return False

    def _process_lamas_data(self, raw_data):
        if not raw_data or 'areas' not in raw_data:
            self._log("Lamas data missing 'areas' key during processing.", level="ERROR")
            return False
        proc = {'areas': {}}
        expected_keys_count = 0
        processed_keys_count = 0
        for area, cities in raw_data['areas'].items():
            if isinstance(cities, dict):
                std_cities = {}
                for city, details in cities.items():
                    if not isinstance(details, dict): 
                        self._log(f"Lamas Processing: Expected dict for city details of '{city}' in area '{area}', got {type(details)}. Skipping city.", level="WARNING")
                        continue
                    expected_keys_count += 1
                    std = standardize_name(city)
                    if not std: 
                        self._log(f"Lamas Processing: City '{city}' resulted in empty standardized name. Skipping.", level="WARNING")
                        continue

                    entry = {"original_name": city}
                    lat = details.get("lat")
                    lon = details.get("long") 
                    try:
                        if lat is not None and lon is not None:
                            entry["lat"]  = float(lat)
                            entry["long"] = float(lon)
                        elif lat is not None or lon is not None:
                            self._log(f"Lamas Processing: City '{city}' has partial coordinates (lat: {lat}, long: {lon}). Skipping coords.", level="DEBUG")
                    except (ValueError, TypeError):
                        self._log(f"Lamas Processing: Invalid coordinate types for city '{city}' (lat: {lat}, long: {lon}). Skipping coords.", level="WARNING")

                    if std in std_cities: 
                        self._log(f"Lamas Processing: Duplicate standardized name '{std}' found in area '{area}'. Original names: '{std_cities[std]['original_name']}', '{city}'. Overwriting.", level="WARNING")

                    std_cities[std] = entry
                    processed_keys_count += 1
                proc['areas'][area] = std_cities
            else:
                self._log(f"Lamas Processing: Expected dict for area '{area}', got {type(cities)}. Skipping area.", level="WARNING")
                proc['areas'][area] = {} 
        self._lamas_data = proc
        if expected_keys_count != processed_keys_count:
            self._log(f"Lamas Processing: Mismatch - attempted {expected_keys_count} city entries, successfully processed {processed_keys_count}.", level="WARNING")
        return True

    def _build_city_details_map(self):
        self._city_details_map = {}
        if self._lamas_data and 'areas' in self._lamas_data:
            entries_built = 0
            duplicates = {} 
            for area, cities in self._lamas_data['areas'].items():
                if isinstance(cities, dict):
                    for std, details in cities.items():
                        if std in self._city_details_map:
                            if std not in duplicates: duplicates[std] = [self._city_details_map[std]['area']]
                            duplicates[std].append(area)
                            self._log(f"Lamas Map Build: Duplicate std name '{std}' found in areas: {duplicates[std]}. Using entry from area '{area}'.", level="WARNING")
                        
                        self._city_details_map[std] = {**details, "area": area}
                        entries_built += 1
                else:
                    self._log(f"Lamas Map Build: Area '{area}' has unexpected data type {type(cities)}. Skipping.", level="WARNING")

            if entries_built == 0:
                self._log("Lamas Map Build: No valid city entries found to build map.", level="ERROR")
            if duplicates:
                self._log(f"Lamas Map Build: Found {len(duplicates)} standardized names duplicated across multiple areas.", level="WARNING")
        else:
            self._log("No Lamas data available to build map.", level="ERROR")

    @functools.lru_cache(maxsize=512) 
    def get_city_details(self, standardized_name: str):
        if not isinstance(standardized_name, str) or not standardized_name:
            return None
        return self._city_details_map.get(standardized_name) 

# ----------------------------------------------------------------------
# Helper Class: AlertProcessor
# ----------------------------------------------------------------------
class AlertProcessor:
    def __init__(self, lamas_manager, icons_emojis_map, logger):
        self._lamas = lamas_manager
        self._icons = icons_emojis_map
        self._log   = logger
        self.max_msg_len = 700
        self.max_attr_len = 4000
        self.max_input_len = 255

    def extract_duration_from_desc(self, descr: str) -> int:
        if not isinstance(descr, str):
            return 0
        m = re.search(r'(\d+)\s+(דקות|דקה)', descr)
        if m:
            try:
                minutes = int(m.group(1))
                return minutes * 60 
            except ValueError:
                self._log(f"Could not parse number from duration string: '{m.group(1)}'", level="WARNING")
        return 0 

    def _check_len(self, text: str, count: int, areas: str, max_len: int, context: str = "message", user_cities_str: str = "") -> str:
        if not isinstance(text, str): return "" 
        try:
            text_len = len(text)
            if text_len > max_len:
                if user_cities_str:
                    small_text = f"מתקפה מורחבת על {count} ישובים. התרעה אצלך ב: {user_cities_str} ועוד באזורים: {areas}"
                else:
                    small_text = f"מתקפה מורחבת על {count} ערים באזורים הבאים: {areas}"
                
                if len(small_text) > max_len:
                    if user_cities_str:
                        very_small = f"מתקפה מורחבת ({count} ישובים). אצלך ב: {user_cities_str} ועוד."
                        if len(very_small) > max_len:
                            return very_small[:max_len-3] + "..."
                        return very_small
                    return f"מתקפה מורחבת על {count} ישובים"
                return small_text
        except Exception as e:
            self._log(f"Error during _check_len for {context}: {e}", level="ERROR")
        return text

    def process_alert_window_data(self, category, title, description, window_std_cities, window_alerts_grouped, user_configured_stds=None):
        if user_configured_stds is None:
            user_configured_stds = set()
            
        log_prefix = "[Alert Processor]"

        icon, emoji = self._icons.get(category, ("mdi:alert", "❗"))
        duration = self.extract_duration_from_desc(description)

        if not window_std_cities:
            self._log(f"{log_prefix} Called with empty overall city set (window_std_cities). Returning default structure.", level="WARNING")
            input_text_state = title[:self.max_input_len] if title else "אין התרעות"
            return {
                "areas_alert_str": "", "cities_list_sorted": [], "data_count": 0,
                "alerts_cities_str": "", "icon_alert": icon, "icon_emoji": emoji,
                "duration": duration,
                "text_wa_grouped": f"{emoji} *{title}*\n_{description}_",
                "text_tg_grouped": f"{emoji} **{title}**\n__{description}__",
                "text_status": title, "full_message_str": title,
                "alert_txt": title, "full_message_list": [],
                "input_text_state": input_text_state
            }

        my_alarming_stds = window_std_cities.intersection(user_configured_stds)
        my_alarming_orig_names = []

        overall_areas_set = set()
        overall_orig_cities_set = set()
        cities_by_area_overall = {}
        unknown_cities_logged_overall = set()
        
        for std in window_std_cities:
            det = self._lamas.get_city_details(std)
            area = DEFAULT_UNKNOWN_AREA
            name = std
            if det:
                area = det.get("area", DEFAULT_UNKNOWN_AREA)
                name = det.get("original_name", std)
            elif std not in unknown_cities_logged_overall:
                self._log(f"{log_prefix} Overall Processing: City '{std}' not found in Lamas. Using Area='{area}'.", level="WARNING")
                unknown_cities_logged_overall.add(std)
                
            overall_areas_set.add(area)
            overall_orig_cities_set.add(name)
            cities_by_area_overall.setdefault(area, set()).add(name)
            
            if std in my_alarming_stds:
                my_alarming_orig_names.append(name)

        my_alarming_orig_names.sort()
        user_alarming_str = ", ".join(my_alarming_orig_names)

        overall_areas_list_sorted = sorted(list(overall_areas_set))
        overall_areas_str = ", ".join(overall_areas_list_sorted) if overall_areas_list_sorted else "ישראל"
        other_cities = sorted(list(overall_orig_cities_set - set(my_alarming_orig_names)))
        full_cities_list = my_alarming_orig_names + other_cities
        overall_count = len(full_cities_list)
        
        if overall_count > 50:
            display_cities_list = full_cities_list[:50] + [f"...ועוד {overall_count - 50} ישובים"]
        else:
            display_cities_list = full_cities_list

        overall_cities_str = ", ".join(display_cities_list)

        full_overall_lines = []
        for area, names_set in sorted(cities_by_area_overall.items()):
            sorted_cities_str_area = ", ".join(sorted(list(names_set)))
            full_overall_lines.append(f"{area}: {sorted_cities_str_area}")
            
        if len(full_overall_lines) > 20:
            full_overall_lines = full_overall_lines[:20] + ["...רשימה חלקית עקב עומס"]
            
        status_str_raw = f"{title} - {overall_areas_str}: {overall_cities_str}"
        full_message_str_raw = title + "\n * " + "\n * ".join(full_overall_lines)
        alert_txt_basic = " * ".join(full_overall_lines)

        wa_grouped_lines = []
        tg_grouped_lines = []
        num_alert_types_in_window = len(window_alerts_grouped)

        if num_alert_types_in_window > 1:
            wa_grouped_lines.append(f"{emoji} *התרעות פעילות ({num_alert_types_in_window} סוגים)*")
            tg_grouped_lines.append(f"{emoji} **התרעות פעילות ({num_alert_types_in_window} סוגים)**")
        elif num_alert_types_in_window == 1:
            single_title = next(iter(window_alerts_grouped.keys()))
            wa_grouped_lines.append(f"{emoji} *{single_title}*")
            tg_grouped_lines.append(f"{emoji} **{single_title}**")
        else:
            self._log(f"{log_prefix} Grouped data empty despite overall cities present. Using latest title for header.", level="WARNING")
            wa_grouped_lines.append(f"{emoji} *{title}*")
            tg_grouped_lines.append(f"{emoji} **{title}**")

        grouped_processed_count = 0
        for alert_title_group, areas_dict in sorted(window_alerts_grouped.items()):
            if num_alert_types_in_window > 1:
                group_icon, group_emoji = ("mdi:alert-decagram", "🚨")
                wa_grouped_lines.append(f"\n{group_emoji} *{alert_title_group}*")
                tg_grouped_lines.append(f"\n{group_emoji} **{alert_title_group}**")
            for area, cities_set in sorted(areas_dict.items()):
                if not cities_set: continue
                sorted_cities_str_group = ", ".join(sorted(list(cities_set)))
                wa_grouped_lines.append(f"> {area}\n{sorted_cities_str_group}")
                tg_grouped_lines.append(f"**__{area}__** — {sorted_cities_str_group}")
                grouped_processed_count += len(cities_set)

        if description:
            wa_grouped_lines.append(f"\n{description}")
            tg_grouped_lines.append(f"\n__{description}__")

        text_wa_grouped_raw = "\n".join(wa_grouped_lines)
        text_tg_grouped_raw = "\n".join(tg_grouped_lines)

        text_wa_grouped_checked = self._check_len(text_wa_grouped_raw, overall_count, overall_areas_str, self.max_msg_len, "Grouped WhatsApp Msg", user_alarming_str)
        text_tg_grouped_checked = self._check_len(text_tg_grouped_raw, overall_count, overall_areas_str, self.max_msg_len, "Grouped Telegram Msg", user_alarming_str)
        status_checked = self._check_len(status_str_raw, overall_count, overall_areas_str, self.max_attr_len, "Status Attribute", user_alarming_str)
        full_message_str_checked = self._check_len(full_message_str_raw, overall_count, overall_areas_str, self.max_attr_len, "Full Message Attribute", user_alarming_str)
        overall_cities_str_checked = self._check_len(overall_cities_str, overall_count, overall_areas_str, self.max_attr_len, "Cities String Attribute", user_alarming_str)
        input_state = self._check_len(status_str_raw, overall_count, overall_areas_str, self.max_input_len, "Input Text State", user_alarming_str)[:self.max_input_len]

        return {
            "areas_alert_str": overall_areas_str,
            "cities_list_sorted": full_cities_list,
            "data_count": overall_count,
            "alerts_cities_str": overall_cities_str_checked,
            "icon_alert": icon,
            "icon_emoji": emoji,
            "duration": duration,
            "text_wa_grouped": text_wa_grouped_checked,
            "text_tg_grouped": text_tg_grouped_checked,
            "text_status": status_checked,
            "full_message_str": full_message_str_checked,
            "alert_txt": alert_txt_basic,
            "full_message_list": full_overall_lines,
            "input_text_state": input_state
        }

# ----------------------------------------------------------------------
# Helper Class: HistoryManager
# ----------------------------------------------------------------------
class HistoryManager:
    def __init__(self, hours_to_show, lamas_manager, logger, timer_duration_seconds):
        if not isinstance(timer_duration_seconds, (int, float)) or timer_duration_seconds <= 0:
            logger.log(f"Invalid timer_duration_seconds ({timer_duration_seconds}), using default 120.", level="WARNING")
            timer_duration_seconds = 120
        if not isinstance(hours_to_show, (int, float)) or hours_to_show <= 0:
            logger.log(f"Invalid hours_to_show ({hours_to_show}), using default 4.", level="WARNING")
            hours_to_show = 4

        self._hours_to_show = hours_to_show
        self._lamas = lamas_manager 
        self._log   = logger        
        self._timer_duration_seconds = timer_duration_seconds 
        self._history_list = [] 
        self._added_in_current_poll = set() 
        self._max_history_events = 2000

    def clear_poll_tracker(self):
        """Clears the set tracking entries added during the last poll cycle."""
        self._added_in_current_poll.clear()

    def _prune_and_limit(self) -> bool:
        """
        Prunes old alerts from the internal history list to prevent memory leaks and slow loops.
        Returns True if items were actually removed.
        """
        original_len = len(self._history_list)
        now = datetime.now()
        cutoff = now - timedelta(hours=self._hours_to_show)

        # Filter out old items
        self._history_list = [
            a for a in self._history_list
            if isinstance(a.get('time'), datetime) and a['time'] >= cutoff
        ]

        # Limit to max events
        if len(self._history_list) > self._max_history_events:
            self._history_list = self._history_list[:self._max_history_events]

        return len(self._history_list) != original_len

    async def load_initial_history(self, api_client):
        """Loads initial history data from the API."""
        data = await api_client.get_alert_history() 
        if not isinstance(data, list):
            self._history_list = []
            self._log("Failed to load initial history.", level="WARNING")
            return

        now = datetime.now()
        cutoff = now - timedelta(hours=self._hours_to_show)
        temp_hist = []
        unknown_cities_logged = set()
        loaded_count = 0
        parse_errors = 0

        for e in data:
            loaded_count += 1
            if not isinstance(e, dict): continue
            title_raw = e.get('title', 'לא ידוע')
            
            if "האירוע הסתיים" in title_raw or "בדקות הקרובות" in title_raw:
                continue

            alert_date_str = e.get('alertDate')
            t = parse_datetime_str(alert_date_str, self._log)

            if not isinstance(t, datetime):
                if alert_date_str: parse_errors += 1
                continue 
            
            if t < cutoff:
                continue 

            city_raw = e.get('data','לא ידוע')
            std = standardize_name(city_raw)
            det = self._lamas.get_city_details(std)
            area = det["area"] if det else DEFAULT_UNKNOWN_AREA
            orig_name = det["original_name"] if det else city_raw

            temp_hist.append({
                'title': title_raw,
                'city': orig_name,
                'area': area,
                'time': t 
            })

        temp_hist.sort(key=lambda x: x.get('time', datetime.min), reverse=True)
        self._history_list = temp_hist
        
        self._prune_and_limit()

        unique_cities = len(set(a['city'] for a in self._history_list))
        self._log(f"Initial history: Processed {loaded_count} raw alerts, kept {len(self._history_list)} within {self._hours_to_show}h ({unique_cities} unique cities).")

    def update_history(self, title: str, std_payload_cities: set):
        """Updates the history list with new alerts from the current payload."""
        now = datetime.now()
        unknown_cities_logged = set()
        added_count_this_call = 0

        if not std_payload_cities:
            return

        for std in std_payload_cities:
            if not std: continue 
            det = self._lamas.get_city_details(std)
            area = DEFAULT_UNKNOWN_AREA
            orig_city_name = std
            if det:
                area = det.get("area", DEFAULT_UNKNOWN_AREA)
                orig_city_name = det.get("original_name", std)
            elif std not in unknown_cities_logged:
                self._log(f"History Add: City '{std}' not found. Using Area='{area}'.", level="WARNING")
                unknown_cities_logged.add(std)

            history_key = (title, std, area) 

            if history_key not in self._added_in_current_poll:
                self._history_list.append({
                    'title': title,
                    'city': orig_city_name, 
                    'area': area,
                    'time': now 
                })
                self._added_in_current_poll.add(history_key)
                added_count_this_call += 1

        if added_count_this_call > 0:
            self._history_list.sort(key=lambda x: x.get('time', datetime.min), reverse=True)
            self._prune_and_limit()

    def restructure_alerts(self, alerts_list: list) -> dict:
        """Groups alerts by title, then area, including city and time."""
        structured_data = defaultdict(lambda: defaultdict(list))
        if not alerts_list: return {}

        for alert in alerts_list:
            if not isinstance(alert, dict):
                self._log(f"Restructure: Skipping non-dict item: {type(alert)}", level="WARNING")
                continue
            
            title = alert.get('title', 'לא ידוע')
            area  = alert.get('area', DEFAULT_UNKNOWN_AREA)
            city  = alert.get('city', 'לא ידוע')
            time_str = alert.get('time', '') 

            time_display = "??:??:??" 
            if isinstance(time_str, str) and ' ' in time_str and ':' in time_str:
                try:
                    time_display = time_str.split(' ')[1]
                except IndexError:
                    self._log(f"Restructure: Could not split time from string '{time_str}' for '{city}'. Using default.", level="DEBUG")
            elif isinstance(time_str, str) and time_str: 
                self._log(f"Restructure: Unexpected time string format '{time_str}' for '{city}'. Using default.", level="DEBUG")

            structured_data[title][area].append({'city': city, 'time': time_display})

        for title_group in structured_data.values():
            for area_group in title_group.values():
                area_group.sort(key=lambda x: x.get('city', ''))

        # Return as a standard dict to prevent JSON serialization issues with defaultdict
        return {k: dict(v) for k, v in structured_data.items()}

    def get_history_attributes(self) -> dict:
        """
        Generates attributes for history sensors.
        We assume self._history_list is already pruned via _prune_and_limit().
        """
        city_event_blocks = defaultdict(list)
        merge_window = timedelta(minutes=50)

        for alert in self._history_list:
            if not all(k in alert for k in ['city', 'time']) or not isinstance(alert.get('time'), datetime):
                self._log(f"Merge Logic: Skipping malformed history entry: {alert}", level="WARNING")
                continue

            city_name = alert['city']
            alert_time = alert['time']

            if not city_event_blocks[city_name]:
                city_event_blocks[city_name].append([alert])
                continue

            latest_time_in_last_block = city_event_blocks[city_name][-1][0]['time']

            if latest_time_in_last_block - alert_time < merge_window:
                city_event_blocks[city_name][-1].append(alert)
            else:
                city_event_blocks[city_name].append([alert])

        merged_history_with_dt = []
        for city, blocks in city_event_blocks.items():
            for block in blocks:
                if not block: continue

                latest_alert_in_block = block[0]
                all_titles_in_block = set()
                for alert_in_block in block:
                    original_title = alert_in_block.get('title', 'לא ידוע')
                    translated_title = "התרעות מקדימות" if original_title == "בדקות הקרובות צפויות להתקבל התרעות באזורך" else original_title
                    all_titles_in_block.add(translated_title)

                final_title = " & ".join(sorted(list(all_titles_in_block)))
                merged_alert = {
                    'title': final_title,
                    'city': latest_alert_in_block['city'],
                    'area': latest_alert_in_block['area'],
                    'time': latest_alert_in_block['time']
                }
                merged_history_with_dt.append(merged_alert)

        merged_history_with_dt.sort(key=lambda x: x.get('time', datetime.min), reverse=True)

        final_history_list_for_ha = []
        final_cities_set = set()

        for a in merged_history_with_dt:
            time_str = "N/A"
            try:
                time_str = a['time'].strftime('%Y-%m-%d %H:%M:%S')
            except (AttributeError, Exception) as e:
                self._log(f"History Formatting: Error formatting time {a.get('time')}: {e}", level="WARNING")
                time_str = str(a.get('time', 'N/A'))

            city_name = a.get('city', 'לא ידוע')
            final_history_list_for_ha.append({
                'title': a.get('title', 'לא ידוע'),
                'city': city_name,
                'area': a.get('area', DEFAULT_UNKNOWN_AREA),
                'time': time_str
            })
            final_cities_set.add(city_name)

        final_grouped_structure = self.restructure_alerts(final_history_list_for_ha)

        return {
            "cities_past_24h": sorted(list(final_cities_set)),
            "last_24h_alerts": final_history_list_for_ha,
            "last_24h_alerts_group": final_grouped_structure
        }

    def get_last_alert_segment(self):
        """Returns recent alerts from history to form a proper polygon on startup."""
        if not self._history_list:
            return None
        
        latest_time = self._history_list[0]['time']
        
        cluster_window = timedelta(minutes=10)
        
        latest_cities = []
        for a in self._history_list:
            if latest_time - a['time'] <= cluster_window:
                latest_cities.append(a['city'])
            else:
                break 
        
        if not latest_cities:
            return None

        return [{
            "type": "active",
            "cities": list(set(latest_cities)), 
            "threat": self._history_list[0]['title']
        }]
    
# ----------------------------------------------------------------------
# Helper Class: FileManager
# ----------------------------------------------------------------------
class FileManager:
    def __init__(self, paths, save_enabled, day_names_map, timer_duration, logger):
        self._paths = paths
        self._save_enabled = save_enabled
        self._day_names = day_names_map
        self._timer_duration = timer_duration
        self._log = logger
        self._last_saved_alert_id = None 

    def get_from_json(self):
        """Loads the last alert state from the JSON backup file."""
        path = self._paths.get("json_backup")
        if not self._save_enabled or not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding='utf-8-sig') as f:
                data = json.load(f)
            if isinstance(data, dict) and ('id' in data or 'title' in data):
                return data
            self._log(f"JSON backup content invalid or empty: {path}", level="WARNING")
        except json.JSONDecodeError as e:
            self._log(f"Error decoding JSON backup {path}: {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error reading JSON backup {path}: {e}", level="ERROR")
        return None

    def create_csv_header_if_needed(self):
        """Creates the CSV history file with a header row if it doesn't exist or is empty."""
        path = self._paths.get("csv")
        if not self._save_enabled or not path: return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if not os.path.exists(path) or os.path.getsize(path) == 0:
                with open(path, 'w', encoding='utf-8-sig', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID","DAY","DATE","TIME","TITLE","COUNT","AREAS","CITIES","DESC","ALERTS_IN_SEQUENCE"])
                self._log(f"Created/ensured CSV header in: {path}")
        except PermissionError as e:
            self._log(f"Permission error creating/writing CSV header: {path} - {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error creating/checking CSV header: {path} - {e}", level="ERROR")

    def save_json_backup(self, data):
        """Saves the current alert state to the JSON backup file."""
        path = self._paths.get("json_backup")
        if not self._save_enabled or not path: return
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding='utf-8-sig') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except PermissionError as e:
            self._log(f"Permission error writing JSON backup to {path}: {e}", level="ERROR")
        except TypeError as e: 
            self._log(f"Error writing JSON backup to {path}: Data not JSON serializable - {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing JSON backup to {path}: {e}", level="ERROR")

    def save_history_files(self, attrs):
        """Saves the summary of the completed alert window to TXT and CSV files."""
        if not self._save_enabled or not attrs:
            return

        alert_id = attrs.get('id', 0)
        if alert_id == self._last_saved_alert_id and alert_id != 0:
            return

        txt_p, csv_p = self._paths.get("txt_history"), self._paths.get("csv")
        if not txt_p or not csv_p:
            self._log("History file saving skipped (TXT or CSV path missing).", level="WARNING")
            return

        fmt_time, fmt_date, day_name_he = "שגיאה", "שגיאה", "שגיאה"
        try:
            last_update_str = attrs.get("last_changed") 
            last_update_dt = parse_datetime_str(last_update_str, self._log) or datetime.now() 
            event_dt = last_update_dt

            fmt_time = event_dt.strftime('%H:%M:%S')
            fmt_date = event_dt.strftime('%d/%m/%Y')
            day_name_en = event_dt.strftime('%A')
            day_name_he = self._day_names.get(day_name_en, day_name_en)
            date_str = f"\n{day_name_he}, {fmt_date}, {fmt_time}"
        except Exception as e:
            self._log(f"Error processing time for history file context: {e}", level="ERROR")
            date_str = "\nשגיאה בעיבוד זמן"

        full_cities_list = attrs.get("cities", [])
        if isinstance(full_cities_list, list):
            full_cities_str = ", ".join(full_cities_list)
        else:
            full_cities_str = str(full_cities_list)
        # --------------------------------------------

        try:
            os.makedirs(os.path.dirname(txt_p), exist_ok=True)
            with open(txt_p, 'a', encoding='utf-8-sig') as f:
                f.write(date_str + "\n")
                title = attrs.get('title', 'אין כותרת')
                f.write(f"{title}\n{full_cities_str}\n")
        except PermissionError as e:
            self._log(f"Permission error writing TXT history to {txt_p}: {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing TXT history to {txt_p}: {e}", level="ERROR")

        try:
            self.create_csv_header_if_needed() 

            csv_data = [
                str(alert_id),
                day_name_he,
                fmt_date,
                fmt_time,
                attrs.get('title', 'N/A'),
                attrs.get('data_count', 0),
                attrs.get('areas', ''),
                full_cities_str, 
                attrs.get('desc', ''),
                attrs.get('alerts_count', 0) 
            ]

            output = StringIO()
            writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(csv_data)
            line = output.getvalue().strip() 
            output.close()

            os.makedirs(os.path.dirname(csv_p), exist_ok=True)
            with open(csv_p, 'a', encoding='utf-8-sig', newline='') as f:
                f.write(line + "\n")

            self._last_saved_alert_id = alert_id 

        except PermissionError as e:
            self._log(f"Permission error writing CSV history to {csv_p}: {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing CSV history to {csv_p}: {e}", level="ERROR")

    def clear_last_saved_id(self):
        """Resets the tracker for the last saved alert ID (called at window start)."""
        self._last_saved_alert_id = None

    def save_geojson_file(self, geojson_data, path):
        """Saves the provided GeoJSON data structure to the specified file path."""
        if not self._save_enabled: return
        if not path:
            self._log("Skipping GeoJSON save: Path is missing.", level="WARNING")
            return
        if not isinstance(geojson_data, dict) or "features" not in geojson_data:
            self._log(f"Skipping GeoJSON save to {path}: Invalid data structure.", level="WARNING")
            return

        num_features = len(geojson_data.get('features', []))
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'w', encoding='utf-8-sig') as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)

            log_level = "DEBUG"
            if "latest" in path and num_features > 0: log_level = "INFO" 
            elif "24h" in path and num_features > 0: log_level = "DEBUG" 
            elif "latest" in path and num_features == 0: log_level = "DEBUG" 

            if num_features > 0 or "24h" in path :
                self._log(f"Successfully wrote GeoJSON ({num_features} features) to: {path}", level=log_level)

        except PermissionError as e:
            self._log(f"PERMISSION ERROR writing GeoJSON to {path}: {e}. Check permissions.", level="ERROR")
        except TypeError as e: 
            self._log(f"Error writing GeoJSON to {path}: Data not JSON serializable - {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing GeoJSON to {path}: {e}", level="ERROR")


# ----------------------------------------------------------------------
# Main AppDaemon Class: Red_Alerts_Israel 
# ----------------------------------------------------------------------
class Red_Alerts_Israel(Hass):

    async def initialize(self):
        """Initializes the AppDaemon application."""
        self.log("--------------------------------------------------")
        self.log("        Initializing Red Alerts Israel App")
        self.log("--------------------------------------------------")
        
        global _IS_RAI_RUNNING
        if _IS_RAI_RUNNING:
            self.log("Red_Alerts_Israel is already running – skipping duplicate initialize.", level="WARNING")
            return
        _IS_RAI_RUNNING = True
        atexit.register(self._cleanup_on_exit) 

        # --- Configuration Loading & Validation ---
        self.interval = self.args.get("interval", 5)
        self.timer_duration = self.args.get("timer", 120)
        self.current_timer_duration = self.timer_duration
        self.save_2_file = self.args.get("save_2_file", True)
        self.sensor_name = self.args.get("sensor_name", "red_alert")
        self.city_names_config = self.args.get("city_names", [])
        self.city_names_config.append("ברחבי הארץ")
        self.hours_to_show = self.args.get("hours_to_show", 1)
        self.mqtt_topic = self.args.get("mqtt", False)
        self.ha_event = self.args.get("event", False)
        

        # Validate config types
        if not isinstance(self.interval, (int, float)) or self.interval <= 1: 
            self.log(f"Invalid 'interval' ({self.interval}), must be > 1. Using default 5s.", level="WARNING")
            self.interval = 5
        if not isinstance(self.timer_duration, (int, float)) or self.timer_duration <= 0:
            self.log(f"Invalid 'timer' ({self.timer_duration}), must be > 0. Using default 120s.", level="WARNING")
            self.timer_duration = 120
        if not isinstance(self.hours_to_show, (int, float)) or self.hours_to_show <= 0:
            self.log(f"Invalid 'hours_to_show' ({self.hours_to_show}), must be > 0. Using default 4h.", level="WARNING")
            self.hours_to_show = 4
        if not isinstance(self.sensor_name, str) or not self.sensor_name.strip():
            self.log("Invalid 'sensor_name', using default 'red_alert'.", level="WARNING")
            self.sensor_name = "red_alert"
        if not isinstance(self.city_names_config, list):
            self.log(f"Invalid 'city_names' format (should be a list), got {type(self.city_names_config)}. Ignoring.", level="WARNING")
            self.city_names_config = []

        self.log(f"Config: Interval={self.interval}s, Timer={self.timer_duration}s, SaveFiles={self.save_2_file}, HistoryHours={self.hours_to_show}, MQTT={self.mqtt_topic}, Event={self.ha_event}")


        # --- Entity ID Setup ---
        base = self.sensor_name 
        self.main_sensor    = f"binary_sensor.{base}"
        self.city_sensor    = f"binary_sensor.{base}_city"
        self.main_sensor_pre_alert    = f"binary_sensor.{base}_pre_alert"
        self.city_sensor_pre_alert    = f"binary_sensor.{base}_city_pre_alert"
        self.main_sensor_active_alert    = f"binary_sensor.{base}_active_alert"
        self.city_sensor_active_alert    = f"binary_sensor.{base}_city_active_alert"
        self.main_text      = f"input_text.{base}"
        self.activate_alert = f"input_boolean.{base}_test"
        self.history_cities_sensor = f"sensor.{base}_history_cities"
        self.history_list_sensor = f"sensor.{base}_history_list"
        self.history_group_sensor = f"sensor.{base}_history_group"

        # --- File Path Setup ---
        www_base = self._get_www_path()
        if www_base:
            self.file_paths = {
                "txt_history":     os.path.join(www_base, f"{base}_history.txt"),
                "csv":             os.path.join(www_base, f"{base}_history.csv"),
                "json_backup":     os.path.join(www_base, f"{base}_history.json"),
                "geojson_latest":  os.path.join(www_base, f"{base}_latest.geojson"),
                "geojson_history": os.path.join(www_base, f"{base}_24h.geojson"),
                "lamas_local":     os.path.join(script_directory, "lamas_data.json")
            }
            self._verify_www_writeable(www_base) 
        else:
            self.log("Could not determine www path. File saving features will be disabled.", level="ERROR")
            self.save_2_file = False
            self.file_paths = {"lamas_local": os.path.join(script_directory, "lamas_data.json")}


        # --- HTTP Session Setup ---
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 AppDaemon/RAI',
            'Referer': 'https://www.oref.org.il/',
            'X-Requested-With': 'XMLHttpRequest', 'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br', 'Accept-Language': 'he,en;q=0.9',
            'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Cache-Control': 'no-cache' 
        }
        timeout = ClientTimeout(total=15, connect=5, sock_connect=5, sock_read=10)
        connector = TCPConnector(limit_per_host=5, keepalive_timeout=30, enable_cleanup_closed=True)
        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=headers, trust_env=False
        )

        api_urls = {
            "live":         f"https://www.oref.org.il/WarningMessages/alert/alerts.json", 
            "history":      f"https://www.oref.org.il/WarningMessages/alert/History/AlertsHistory.json", 
            "lamas_github": "https://raw.githubusercontent.com/idodov/RedAlert/main/apps/red_alerts_israel/lamas_data.json"
        }
        self.api_client = OrefAPIClient(self.session, api_urls, self.log)

        # --- State Variables ---
        self.alert_sequence_count = 0
        self.no_active_alerts_polls = 0
        self.last_alert_time = None
        self.last_processed_alert_id = None 
        self.window_alerts_grouped = defaultdict(lambda: defaultdict(set)) 
        self.prev_alert_final_attributes = None 
        self.cities_past_window_std = set() 
        self.test_alert_cycle_flag = 0 
        self.test_alert_start_time = 0
        self._poll_running = False
        self._terminate_event = asyncio.Event()
        self.last_active_payload_details = None
        self.last_history_attributes_cache = None 
        self.map_segments_history = []
        self.last_map_update = 0      

        # --- Helper Class Instantiation ---
        self.lamas_manager    = LamasDataManager(
                                self.file_paths["lamas_local"],
                                api_urls["lamas_github"], self.api_client, self.log
                            )
        self.alert_processor  = AlertProcessor(self.lamas_manager, ICONS_AND_EMOJIS, self.log)
        self.history_manager  = HistoryManager(self.hours_to_show, self.lamas_manager, self.log, self.timer_duration)
        self.file_manager     = FileManager(self.file_paths, self.save_2_file, DAY_NAMES, self.timer_duration, self.log)

        # --- Initial State Setup ---
        try:
            await self.set_state(self.main_sensor, state="off", attributes={'script_status': 'initializing', 'timestamp': datetime.now().isoformat()})
        except Exception as e:
            self.log(f"Error setting initial sensor state during init: {e}", level="WARNING")

        # --- Critical Dependency: Load Lamas Data ---
        if not await self.lamas_manager.load_data():
            self.log("FATAL: Lamas data load failed. Cannot map cities to areas. Aborting initialization.", level="CRITICAL")
            error_attrs = {'error': 'Lamas data failed to load', 'status': 'error', 'timestamp': datetime.now().isoformat()}
            try: await self.set_state(self.main_sensor, state="unavailable", attributes=error_attrs)
            except Exception as e_set: self.log(f"Error setting sensor to unavailable state after Lamas failure: {e_set}", level="ERROR")
            _IS_RAI_RUNNING = False 
            await self.terminate() 
            return 
        
        self._lamas_data = self.lamas_manager._lamas_data
        # --- Validate Configured City Names ---
        self._validate_configured_cities()

        # --- Initialize HA Entities and Load Initial Data ---
        await self._initialize_ha_sensors()
        await self._load_initial_data() 

        # --- Register Test Boolean Listener ---
        try:
            self.listen_state(self._test_boolean_callback, self.activate_alert, new="on")
            self.log(f"Listening for test activation on {self.activate_alert}", level="INFO")
        except Exception as e:
            self.log(f"Error setting up listener for {self.activate_alert}: {e}", level="ERROR")


        # --- Start Polling Loop ---
        self.log("Scheduling first API poll.")
        self.run_in(self._poll_alerts_callback_sync, 5) 

        # Update sensor status to running 
        running_attrs = {'script_status': 'running', 'timestamp': datetime.now().isoformat()}
        try:
            current_main_state = await self.get_state(self.main_sensor, attribute="all")
            if current_main_state and 'attributes' in current_main_state:
                base_attrs = current_main_state.get('attributes', {})
                if current_main_state.get('state', 'off') == 'off':
                    merged_attrs = {**base_attrs, **running_attrs}
                else:
                    merged_attrs = {**base_attrs, 'script_status': 'running'} 
                await self.set_state(self.main_sensor, state=current_main_state.get('state', 'off'), attributes=merged_attrs)
            else:
                await self.set_state(self.main_sensor, state='off', attributes=running_attrs)
        except Exception as e:
            self.log(f"Error setting running status attribute: {e}", level="WARNING")

        self.map_url = self.generate_smart_alert_map([], self._lamas_data)

        await self.history_manager.load_initial_history(self.api_client)
                
        last_segment = self.history_manager.get_last_alert_segment()
        if last_segment:
            if not hasattr(self, 'map_segments_history'):
                self.map_segments_history = []
            
            self.map_segments_history = [{
                "type": "active",
                "cities": last_segment[0]["cities"],
                "timestamp": time.time()
            }]
            
            self.map_url = self.generate_smart_alert_map(self.map_segments_history, self.lamas_manager._lamas_data)
        else:
            self.map_url = "https://static-maps.yandex.ru/1.x/?l=map&lang=he_IL&size=600,450&ll=34.8516,31.0461&z=7"
        await self._load_initial_data()
        self.log("--------------------------------------------------")
        self.log("  Initialization Complete. Monitoring Red Alerts.")
        self.log("--------------------------------------------------")


    def _get_www_path(self):
        """Tries to determine the Home Assistant www path."""
        ha_config_dir_options = ["/homeassistant", "/config", "/usr/share/hassio/homeassistant", "/root/config"]
        for d in ha_config_dir_options:
            www_path = os.path.join(d, "www")
            if os.path.isdir(www_path):
                return www_path

        ha_config_dir = getattr(self, 'config_dir', None)
        if ha_config_dir and os.path.isdir(os.path.join(ha_config_dir, 'www')):
            self.log(f"Using www path from HA config dir: {os.path.join(ha_config_dir, 'www')}", level="INFO")
            return os.path.join(ha_config_dir, 'www')

        ad_config_dir = getattr(self, 'config_dir', script_directory) 
        potential_ha_config = os.path.dirname(ad_config_dir) 
        www_path_guess = os.path.join(potential_ha_config, "www")
        if os.path.isdir(www_path_guess):
            self.log(f"Using guessed www path relative to AppDaemon config: {www_path_guess}", level="WARNING")
            return www_path_guess

        self.log("Could not reliably determine www path.", level="ERROR")
        return None

    def _verify_www_writeable(self, www_base):
        """Checks if the www directory is writeable and logs errors."""
        if not self.save_2_file: return 
        try:
            os.makedirs(www_base, exist_ok=True)
            test_file = os.path.join(www_base, f".{self.sensor_name}_write_test_{random.randint(1000,9999)}")
            with open(test_file, 'w') as f: f.write("test")
            os.remove(test_file)
        except PermissionError as e:
            self.log(f"PERMISSION ERROR creating/writing to www directory '{www_base}': {e}. Check permissions. Disabling file saving.", level="ERROR")
            self.save_2_file = False
        except OSError as e:
            self.log(f"OS ERROR accessing www directory '{www_base}': {e}. Disabling file saving.", level="ERROR")
            self.save_2_file = False
        except Exception as e:
            self.log(f"Unexpected error verifying write access to www directory '{www_base}': {e}. Disabling file saving.", level="ERROR")
            self.save_2_file = False

    def _validate_configured_cities(self):
        """Validates cities from config against loaded Lamas data."""
        self.city_names_self_std = set()
        if not self.city_names_config: 
            self.log("No 'city_names' provided in configuration.", level="INFO")
            return

        found_all = True
        processed_count = 0
        invalid_entries = 0
        for city_config_raw in self.city_names_config:
            if not isinstance(city_config_raw, str) or not city_config_raw.strip():
                self.log(f"Config WARNING: Invalid/empty value found in city_names: '{city_config_raw}'. Skipping.", level="WARNING")
                invalid_entries += 1
                continue

            processed_count += 1
            city_config_std = standardize_name(city_config_raw)
            if not city_config_std:
                self.log(f"Config WARNING: City '{city_config_raw}' resulted in empty standardized name. Skipping.", level="WARNING")
                invalid_entries += 1
                continue

            self.city_names_self_std.add(city_config_std)
            details = self.lamas_manager.get_city_details(city_config_std)
            if details is None:
                self.log(f"Config WARNING: City '{city_config_raw}' (standardized: '{city_config_std}') not found in Lamas data. The '{self.city_sensor}' may not trigger correctly for this entry.", level="WARNING")
                found_all = False

        valid_count = processed_count - invalid_entries
        if valid_count == 0 and processed_count > 0:
            self.log("No valid city_names found after processing configuration entries.", level="WARNING")
        elif found_all and valid_count > 0:
            self.log(f"All {valid_count} configured city_names validated successfully.", level="INFO")
        elif valid_count > 0:
            self.log(f"Configured city_names validation complete. {len(self.city_names_self_std)} unique valid names processed. Some warnings issued.", level="WARNING")

    def _poll_alerts_callback_sync(self, kwargs):
        """Callback trampoline to run the async poll function. Prevents overlapping runs."""
        if self._poll_running:
            return
        self._poll_running = True
        self.create_task(self._poll_and_schedule_next())

    async def _poll_and_schedule_next(self):
        """Runs the poll logic and schedules the next poll, ensuring no overlap."""
        start_time = time.monotonic()
        try:
            if self._terminate_event.is_set():
                self.log("Termination signal received, skipping poll.", level="INFO")
                return 

            await self.poll_alerts()

        except Exception as e:
            self.log(f"CRITICAL ERROR during poll_alerts execution: {e.__class__.__name__} - {e}", level="CRITICAL")
            try:
                await self.set_state(self.main_sensor, attributes={'script_status': 'error', 'last_error': f"{e.__class__.__name__}: {e}", 'timestamp': datetime.now().isoformat()})
            except Exception as set_err:
                self.log(f"Error setting error status on sensor: {set_err}", level="ERROR")
        finally:
            self._poll_running = False 
            
            if not self._terminate_event.is_set():
                self.run_in(self._poll_alerts_callback_sync, self.interval)
            else:
                self.log("Termination signal received after poll, not scheduling next.", level="INFO")

    def terminate(self):
        """
        Synchronous callback invoked by AppDaemon when it’s shutting down.
        """
        self.log("AppDaemon shutdown detected: scheduling async termination...", level="INFO")
        if hasattr(self, "_terminate_event"):
            try:
                self._terminate_event.set()
            except Exception:
                pass
        self.create_task(self._async_terminate())

    async def _async_terminate(self):
        """
        Gracefully shut down: update your sensors to 'terminated', close HTTP session.
        """
        self.log("--------------------------------------------------")
        self.log("Async Terminate: cleaning up Red Alerts Israel App")
        self.log("--------------------------------------------------")
        global _IS_RAI_RUNNING

        if not _IS_RAI_RUNNING:
            return

        _IS_RAI_RUNNING = False
        if hasattr(self, "_terminate_event"):
            self._terminate_event.set()

        await asyncio.sleep(0)

        term_attrs = {
            "script_status": "terminated",
            "timestamp": datetime.now().isoformat()
        }
        tasks = []
        for entity in (self.main_sensor, self.city_sensor, self.main_sensor_pre_alert, self.city_sensor_pre_alert, self.main_sensor_active_alert, self.city_sensor_active_alert):
            try:
                if await self.entity_exists(entity):
                    tasks.append(self.set_state(entity, state="off", attributes=term_attrs))
            except Exception as e:
                self.log(f"Error checking/setting {entity} on terminate: {e}", level="WARNING")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        session = getattr(self, "session", None)
        if session and not session.closed:
            try:
                await session.close()
            except Exception as e:
                self.log(f"Error closing HTTP session: {e}", level="WARNING")

        self.log("Red Alerts Israel App shutdown complete.")
        self.log("--------------------------------------------------")

    def _cleanup_on_exit(self):
        """Synchronous cleanup function called by atexit."""
        global _IS_RAI_RUNNING
        if not _IS_RAI_RUNNING:
            return

        log_func = getattr(self, 'log', print)
        log_func("atexit: Script was running, attempting final cleanup steps.", level="INFO")
        _IS_RAI_RUNNING = False

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                loop.call_soon_threadsafe(self._terminate_event.set)
                loop.call_soon_threadsafe(asyncio.create_task, self.terminate())
            else:
                try:
                    asyncio.run(self.terminate())
                except Exception as e2:
                    log_func(f"atexit: Error running terminate() directly: {e2}", level="WARNING")

        except Exception as e:
            log_func(f"atexit: Error accessing/signalling loop: {e}", level="WARNING")

    def _is_iso_format(self, ds: str) -> str:
        """Parses a datetime string and returns it in ISO format with microseconds, or now() if invalid."""
        dt = parse_datetime_str(ds, self.log)
        now_fallback = datetime.now().isoformat(timespec='microseconds')
        if dt:
            try:
                return dt.isoformat(timespec='microseconds')
            except Exception as e: 
                self.log(f"Error formatting datetime '{dt}' to ISO: {e}. Falling back to current time.", level="WARNING")
                return now_fallback
        else:
            return now_fallback

    async def _initialize_ha_sensors(self):
        """Ensures required HA entities exist with default states/attributes."""
        now_iso = datetime.now().isoformat(timespec='microseconds')

        idle_attrs = {
            "active_now": "false", "special_update": "false", "id": 0, "cat": 0, "title": "אין התרעות", "desc": "טוען נתונים...",
            "areas": "", "cities": [], "data": "", "data_count": 0, "duration": 0,
            "icon": "mdi:timer-sand", "emoji": "⏳", "alerts_count": 0,
            "last_changed": now_iso,
            "my_cities": sorted(list(set(self.city_names_config))),
            "prev_cat": 0, "prev_title": "", "prev_desc": "", "prev_areas": "",
            "prev_cities": [], "prev_data": "", "prev_data_count": 0, "prev_duration": 0,
            "prev_last_changed": now_iso, "prev_alerts_count": 0,
            "alert_wa": "", "alert_tg": "", 
            "script_status": "initializing",
            "map_url": self.generate_smart_alert_map([], self._lamas_data)
        }
        history_default_attrs = {
            "cities_past_24h": [],
            "last_24h_alerts": [],
            "last_24h_alerts_group": {},
            "script_status": "initializing" 
        }

        sensors_to_init = [
            (self.main_sensor, "off", idle_attrs),
            (self.city_sensor, "off", idle_attrs.copy()),
            (self.main_sensor_pre_alert, "off", idle_attrs.copy()),
            (self.city_sensor_pre_alert, "off", idle_attrs.copy()),
            (self.main_sensor_active_alert, "off", idle_attrs.copy()),
            (self.city_sensor_active_alert, "off", idle_attrs.copy()),
            (self.history_cities_sensor, "0", history_default_attrs.copy()),
            (self.history_list_sensor, "0", history_default_attrs.copy()),
            (self.history_group_sensor, "0", history_default_attrs.copy())
        ]

        init_tasks = []
        for entity_id, state, attrs in sensors_to_init:
            try:
                entity_exists = False
                try:
                    entity_exists = await self.entity_exists(entity_id)
                except Exception as check_err:
                    self.log(f"Error checking existence for {entity_id}: {check_err}", level="WARNING")

                if not entity_exists:
                    self.log(f"Entity {entity_id} not found. Creating with initial state.", level="INFO")
                
                init_tasks.append(self.set_state(entity_id, state=state, attributes=attrs))

            except Exception as e:
                self.log(f"Error preparing init task for entity {entity_id}: {e}", level="WARNING")

        if init_tasks:
            results = await asyncio.gather(*init_tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    self.log(f"Error initializing entity task {i}: {res}", level="ERROR")

        try:
            text_entity_exists = await self.entity_exists(self.main_text)
            text_attrs = {
                "min": 0, "max": 255, "mode": "text",
                "friendly_name": f"{self.sensor_name} Summary",
                "icon": "mdi:timer-sand"
            }
            if not text_entity_exists:
                self.log(f"Entity {self.main_text} not found. Creating with initial text 'טוען...'.", level="INFO")
                await self.set_state(self.main_text, state="טוען...", attributes=text_attrs)

            bool_entity_exists = await self.entity_exists(self.activate_alert)
            bool_attrs = {"friendly_name": f"{self.sensor_name} Test Trigger"}
            if not bool_entity_exists:
                self.log(f"Entity {self.activate_alert} not found. Creating.", level="INFO")
            await self.set_state(self.activate_alert, state="off", attributes=bool_attrs)

        except Exception as e:
            self.log(f"Error checking/initializing input/boolean entities: {e}", level="WARNING")

        self.log("HA sensor entities initialization check complete.")

    async def _load_initial_data(self):
        """Loads history, gets backup, sets initial states with map from history, and saves files."""
        await self.history_manager.load_initial_history(self.api_client)
        history_attrs = self.history_manager.get_history_attributes()

        initial_map_url = "https://static-maps.yandex.ru/1.x/?l=map&lang=he_IL&size=600,450&ll=34.8516,31.0461&z=7"
        try:
            last_segment = self.history_manager.get_last_alert_segment()
            if last_segment:
                initial_map_url = self.generate_smart_alert_map(last_segment, self.lamas_manager._lamas_data)
        except Exception as map_err:
            self.log(f"Error generating initial history map: {map_err}", level="WARNING")

        self.map_url = initial_map_url 

        backup = self.file_manager.get_from_json()
        prev_attrs_formatted = {}
        if backup:
            prev_attrs_formatted = self._format_backup_data_as_prev(backup)
        else:
            prev_attrs_formatted = {
                "prev_cat": 0, "prev_special_update": False, "prev_title": "", "prev_desc": "", "prev_areas": "",
                "prev_cities": [], "prev_data": "", "prev_data_count": 0, "prev_duration": 0,
                "prev_last_changed": datetime.now().isoformat(timespec='microseconds'), "prev_alerts_count": 0
            }

        now_iso = datetime.now().isoformat(timespec='microseconds')
        initial_state_attrs = {
            "active_now": "false", "special_update": "false", "id": 0, "cat": 0, "title": "אין התרעות", "desc": "שגרה",
            "areas": "", "cities": [], "data": "", "data_count": 0, "duration": 0,
            "icon": "mdi:check-circle-outline", "emoji": "✅", "alerts_count": 0,
            "last_changed": now_iso,
            "my_cities": sorted(list(set(self.city_names_config))),
            "map_url": initial_map_url,
            **prev_attrs_formatted, 
            "script_status": "running" 
        }

        try:
            tasks = [
                self.set_state(self.main_sensor, state="off", attributes=initial_state_attrs),
                self.set_state(self.city_sensor, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.main_sensor_pre_alert, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.city_sensor_pre_alert, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.main_sensor_active_alert, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.city_sensor_active_alert, state="off", attributes=initial_state_attrs.copy()),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.log(f"Error setting initial 'off' states: {e}", level="WARNING")

        try:
            count_cities = len(history_attrs.get("cities_past_24h", []))
            count_alerts = len(history_attrs.get("last_24h_alerts", []))
            tasks = []
            
            hist_cities_attrs = {
                "cities_past_24h": history_attrs.get("cities_past_24h", []),
                "script_status": "running" 
            }
            tasks.append(self.set_state(self.history_cities_sensor, state=str(count_cities), attributes=hist_cities_attrs))

            history_list_attr = {
                "last_24h_alerts": history_attrs.get("last_24h_alerts", []),
                "script_status": "running" 
            }
            tasks.append(self.set_state(self.history_list_sensor, state=str(count_alerts), attributes=history_list_attr))

            history_group_attr = {
                "last_24h_alerts_group": history_attrs.get("last_24h_alerts_group", {}),
                "script_status": "running" 
            }
            tasks.append(self.set_state(self.history_group_sensor, state=str(count_alerts), attributes=history_group_attr))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.log(f"Error setting history sensors: {e}", level="WARNING")

        if self.save_2_file:
            try:
                initial_latest_attrs = {
                    "title": "אין התרעות", "desc": "שגרה", "cat": 0, "cities": [],
                    "last_changed": now_iso,
                    "map_url": initial_map_url
                }
                await self._save_latest_geojson(initial_latest_attrs)
                await self._save_history_geojson(history_attrs) 
                self.file_manager.create_csv_header_if_needed()
            except Exception as file_err:
                self.log(f"Error during initial file creation: {file_err}", level="ERROR")

        self.log("Initial data loading complete. Map initialized from history.")
        
    async def _process_active_alert(self, data, is_test=False):
        """
        Processes incoming alert data (real or test), updates state, history, and maps.
        """
        alert_id_from_data = data.get("id", "N/A") 
        log_prefix = "[Test Alert]" if is_test else "[Real Alert]"

        now_dt = datetime.now()
        now_iso = now_dt.isoformat(timespec='microseconds')

        try:
            cat_str = data.get("cat", "1")
            cat = int(cat_str) if str(cat_str).isdigit() else 1
            aid = int(data.get("id", 0))
            desc = data.get("desc", "")
            title = data.get("title", "התרעה")
            raw_payload_cities = data.get("data", [])
            
            payload_cities_raw = []
            if isinstance(raw_payload_cities, str):
                payload_cities_raw = [c.strip() for c in raw_payload_cities.split(',') if c.strip()]
            elif isinstance(raw_payload_cities, list):
                payload_cities_raw = [str(city) for city in raw_payload_cities]

            forbidden_strings = ["בדיקה", "תרגיל"]
            filtered_cities_raw = [c for c in payload_cities_raw if not any(f in c for f in forbidden_strings)]

            if not filtered_cities_raw and payload_cities_raw: 
                return 

            stds_this_payload = set(standardize_name(n) for n in filtered_cities_raw if n)

        except Exception as e:
            self.log(f"{log_prefix} Error parsing alert data: {e}", level="ERROR")
            return 

        if self.last_active_payload_details and not is_test: 
            if self.last_active_payload_details['id'] == aid and self.last_active_payload_details['stds'] == stds_this_payload:
                self.last_alert_time = time.time()
                return

        self.last_active_payload_details = {'id': aid, 'cat': cat, 'title': title, 'desc': desc, 'stds': stds_this_payload}

        if await self.get_state(self.main_sensor) == "off":
            self.cities_past_window_std = set()
            self.alert_sequence_count = 0
            self.window_alerts_grouped.clear()
            self.history_manager.clear_poll_tracker()

        if "האירוע הסתיים" not in title and "בדקות הקרובות" not in title:
            self.history_manager.update_history(title, stds_this_payload)

        self.cities_past_window_std.update(stds_this_payload)
        
        for std in stds_this_payload:
            det = self.lamas_manager.get_city_details(std)
            area = det.get("area", DEFAULT_UNKNOWN_AREA) if det else DEFAULT_UNKNOWN_AREA
            orig_name = det.get("original_name", std) if det else std
            self.window_alerts_grouped[title][area].add(orig_name)

        self.alert_sequence_count += 1
        self.last_alert_time = time.time()
        self.current_timer_duration = 10 if ("האירוע הסתיים" in title or "בדקות הקרובות" in title) else self.timer_duration

        is_clearance = "האירוע הסתיים" in title
        is_pre = "בדקות הקרובות" in title or "עדכון" in title
        seg_type = "clear" if is_clearance else ("pre" if is_pre else "active")

        now_ts = time.time()
        map_retention_seconds = 900  # 15 דקות
        
        if not hasattr(self, 'map_segments_history'):
            self.map_segments_history = []

        if seg_type in ["active", "pre"]:
            self.map_segments_history = [
                s for s in self.map_segments_history if s["type"] != "clear"
            ]

        new_segment = {
            "type": seg_type,
            "cities": list(stds_this_payload),
            "timestamp": now_ts
        }
        self.map_segments_history.append(new_segment)
        
        self.map_segments_history = [
            s for s in self.map_segments_history 
            if now_ts - s["timestamp"] < map_retention_seconds
        ]

        try:
            current_map_url = self.generate_smart_alert_map(self.map_segments_history, self._lamas_data)
            self.map_url = current_map_url 
        except Exception as e:
            self.log(f"Map generation error: {e}")

        info = self.alert_processor.process_alert_window_data(
            category=cat, title=title, description=desc,
            window_std_cities=self.cities_past_window_std, 
            window_alerts_grouped=self.window_alerts_grouped,
            user_configured_stds=self.city_names_self_std
        )
        all_cities_display = []
        user_cities_display = []
        
        for std in self.cities_past_window_std:
            det = self.lamas_manager.get_city_details(std)
            name = det.get("original_name", std) if det else std
            
            if std in self.city_names_self_std:
                user_cities_display.append(name)
            else:
                all_cities_display.append(name)
        
        user_cities_display.sort()
        all_cities_display.sort()
        
        total_count = len(self.cities_past_window_std)
        areas_str = info.get("areas_alert_str", "ישראל")

        if total_count > 100:
            data_prefix = f"התרעה ב-{total_count} ישובים באזורים: {areas_str}."
            if user_cities_display:
                data_attr = f"{data_prefix} אצלך: {', '.join(user_cities_display)}."
            else:
                data_attr = data_prefix
        else:
            full_list = user_cities_display + all_cities_display
            data_attr = ", ".join(full_list)

        final_attributes = {
            "active_now": True, 
            "id": aid, "cat": cat, "title": title, "desc": desc, 
            "data": data_attr,
            "areas": info.get("areas_alert_str", ""), 
            "cities": info.get("cities_list_sorted", []), 
            "data_count": info.get("data_count", 0), 
            "emoji": info.get("icon_emoji", "❗"), 
            "alerts_count": self.alert_sequence_count, 
            "last_changed": now_iso, 
            "alert_wa": info.get("text_wa_grouped", ""), 
            "alert_tg": info.get("text_tg_grouped", ""),
            "map_url": current_map_url,
            "script_status": "running"
        }

        self.prev_alert_final_attributes = final_attributes.copy()

        city_sensor_on = bool(self.cities_past_window_std.intersection(self.city_names_self_std))
        if is_test and self.city_names_self_std: city_sensor_on = True 
        
        await self._update_ha_state(
            main_state="on", 
            city_state="on" if city_sensor_on else "off", 
            text_state=info.get("input_text_state", title), 
            attributes=final_attributes, 
            text_icon=info.get("icon_alert", "mdi:alert")
        )

        if self.save_2_file:
            await self._save_latest_geojson(final_attributes)
            await self._save_history_geojson(self.history_manager.get_history_attributes())

        self.log(f"{log_prefix} Alert processed. Map URL ready in attributes.", level="INFO")

    async def _check_reset_sensors(self):
        """
        Checks if the idle timer has expired and resets sensors if needed,
        saving history and updating files appropriately.
        """
        now = time.time()
        log_prefix = "[Sensor Reset Check]"

        main_sensor_exists = await self.entity_exists(self.main_sensor)
        if not main_sensor_exists:
            self.log(f"{log_prefix} Main sensor {self.main_sensor} not found. Cannot check state.", level="WARNING")
            return

        main_sensor_current_state = "unknown"
        try:
            main_sensor_current_state = await self.get_state(self.main_sensor)
        except Exception as e:
            self.log(f"{log_prefix} Error getting main sensor state: {e}. Assuming 'unknown'.", level="WARNING")

        if main_sensor_current_state == "off" and self.last_alert_time is None:
            if self.prev_alert_final_attributes:
                self.prev_alert_final_attributes = None
            return

        if self.last_alert_time is None:
            return

        time_since_last_alert = now - self.last_alert_time
        timer_expired = time_since_last_alert > self.current_timer_duration
        confirmed_idle = self.no_active_alerts_polls > 0
        can_reset = timer_expired and confirmed_idle

        if can_reset:
            self.log(f"{log_prefix} Alert timer expired ({time_since_last_alert:.1f}s > {self.current_timer_duration}s). Resetting sensors.")
            self.current_timer_duration = self.timer_duration # Reset back to normal

            if self.save_2_file and self.file_manager: 
                if self.prev_alert_final_attributes:
                    last_alert_id = self.prev_alert_final_attributes.get('id', 'N/A')
                    self.log(f"{log_prefix} Saving history files (TXT/CSV) for last window (ID: {last_alert_id})...")
                    try:
                        self.file_manager.save_history_files(self.prev_alert_final_attributes)
                    except Exception as e:
                        self.log(f"{log_prefix} Error during save_history_files: {e}", level="ERROR")
                else:
                    self.log(f"{log_prefix} Cannot save history file on reset: prev_alert_final_attributes missing.", level="WARNING")

            fallback_time_iso = datetime.now().isoformat(timespec='microseconds')
            formatted_prev = {}
            last_alert_wa = "" 
            last_alert_tg = ""

            if self.prev_alert_final_attributes:
                prev_data = self.prev_alert_final_attributes
                last_alert_wa = prev_data.get("alert_wa", "")
                last_alert_tg = prev_data.get("alert_tg", "")
                formatted_prev = {
                    "prev_cat": prev_data.get("cat", 0),
                    "prev_title": prev_data.get("title", ""),
                    "prev_desc": prev_data.get("desc", ""),
                    "prev_areas": prev_data.get("areas", ""),
                    "prev_cities": prev_data.get("cities", []),
                    "prev_data": prev_data.get("data", ""),
                    "prev_data_count": prev_data.get("data_count", 0),
                    "prev_duration": prev_data.get("duration", 0),
                    "prev_last_changed": prev_data.get("last_changed", fallback_time_iso),
                    "prev_alerts_count": prev_data.get("alerts_count", 0)
                }
            else:
                self.log(f"{log_prefix} Previous alert attributes missing during reset. Using defaults for 'prev_'.", level="WARNING")
                formatted_prev = {
                    "prev_cat": 0, "prev_title": "", "prev_desc": "", "prev_areas": "", "prev_cities": [], "prev_data": "",
                    "prev_data_count": 0, "prev_duration": 0, "prev_last_changed": fallback_time_iso, "prev_alerts_count": 0
                }

            self.prev_alert_final_attributes = None 
            self.last_alert_time = None 
            self.last_processed_alert_id = None 
            self.cities_past_window_std.clear() 
            self.window_alerts_grouped.clear() 
            self.alert_sequence_count = 0 
            self.no_active_alerts_polls = 0 

            hist_attrs = self.history_manager.get_history_attributes()
            reset_attrs = {
                "active_now": "false", "special_update": "false", "id": 0, "cat": 0, "title": "אין התרעות", "desc": "שגרה",
                "areas": "", "cities": [], "data": "", "data_count": 0, "duration": 0,
                "icon": "mdi:check-circle-outline", "emoji": "✅", "alerts_count": 0,
                "last_changed": datetime.now().isoformat(timespec='microseconds'), 
                "my_cities": sorted(list(set(self.city_names_config))),
                **formatted_prev, 
                "alert_wa": last_alert_wa, "alert_tg": last_alert_tg, 
                "script_status": "running"
            }

            try:
                await self._update_ha_state(
                    main_state="off", city_state="off", text_state="אין התרעות", 
                    attributes=reset_attrs, text_icon="mdi:check-circle-outline"
                )
            except Exception as e:
                self.log(f"{log_prefix} Error during _update_ha_state call on reset: {e}", level="ERROR")

            try:
                count_cities = len(hist_attrs.get("cities_past_24h", []))
                count_alerts = len(hist_attrs.get("last_24h_alerts", []))
                tasks = [
                    self.set_state(self.history_cities_sensor, state=str(count_cities), attributes={"cities_past_24h": hist_attrs.get("cities_past_24h", []), "script_status": "running"}),
                    self.set_state(self.history_list_sensor, state=str(count_alerts), attributes={"last_24h_alerts": hist_attrs.get("last_24h_alerts", []), "script_status": "running"}),
                    self.set_state(self.history_group_sensor, state=str(count_alerts), attributes={"last_24h_alerts_group": hist_attrs.get("last_24h_alerts_group", {}), "script_status": "running"})
                ]
                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                self.log(f"{log_prefix} Error re-affirming history sensors: {e}", level="ERROR")

            if self.save_2_file:
                try:
                    await self._save_history_geojson(hist_attrs)
                    idle_geojson_attrs = {
                        "title": reset_attrs["title"], "desc": reset_attrs["desc"],
                        "cat": reset_attrs["cat"], "cities": [], 
                        "last_changed": reset_attrs["last_changed"]
                    }
                    await self._save_latest_geojson(idle_geojson_attrs)
                except Exception as e:
                    self.log(f"{log_prefix} Error during GeoJSON update on reset: {e}", level="ERROR")

            self.log(f"{log_prefix} Sensor reset complete. State is now 'off'.")

        elif timer_expired and not confirmed_idle:
            self.log(f"{log_prefix} Timer expired ({time_since_last_alert:.1f}s > {self.timer_duration}s), but last poll was not confirmed idle ({self.no_active_alerts_polls}). Awaiting confirmation poll.", level="DEBUG")

    async def _update_ha_state(self, main_state, city_state, text_state, attributes, text_icon="mdi:information"):
        """Updates the state and attributes of core HA entities."""
        attributes = attributes or {}
        attributes["last_changed"] = datetime.now().isoformat(timespec='microseconds')
        attributes["script_status"] = "running" 
        title_alert = attributes.get("title", "")
        
        is_clearance = "האירוע הסתיים" in title_alert
        is_pre = "בדקות הקרובות" in title_alert or "עדכון" in title_alert or "שהייה בסמיכות" in title_alert

        current_cities_in_payload = attributes.get("cities", []) 
        city_in_current_payload = any(c in self.city_names_config for c in current_cities_in_payload)

        update_tasks = []
        log_prefix = "[HA Update]"

        try:
            main_attrs = attributes.copy() 
            update_tasks.append(self.set_state(self.main_sensor, state=main_state, attributes=main_attrs))
            
            if is_clearance:
                update_tasks.append(self.set_state(self.main_sensor_active_alert, state="off", attributes=main_attrs))
                update_tasks.append(self.set_state(self.main_sensor_pre_alert, state="off", attributes=main_attrs))
            elif is_pre:
                update_tasks.append(self.set_state(self.main_sensor_pre_alert, state=main_state, attributes=main_attrs))
                update_tasks.append(self.set_state(self.main_sensor_active_alert, state="off", attributes=main_attrs))
            else:
                update_tasks.append(self.set_state(self.main_sensor_active_alert, state=main_state, attributes=main_attrs))
                update_tasks.append(self.set_state(self.main_sensor_pre_alert, state="off", attributes=main_attrs))
        except Exception as e:
            self.log(f"{log_prefix} Error preparing task for {self.main_sensor}: {e}", level="ERROR")

        try:
            city_attrs = attributes.copy() 
            update_tasks.append(self.set_state(self.city_sensor, state=city_state, attributes=city_attrs))
            
            if is_clearance:
                update_tasks.append(self.set_state(self.city_sensor_active_alert, state="off", attributes=city_attrs))
                update_tasks.append(self.set_state(self.city_sensor_pre_alert, state="off", attributes=city_attrs))
            elif is_pre:
                new_state = main_state if city_in_current_payload else "off"
                update_tasks.append(self.set_state(self.city_sensor_pre_alert, state=new_state, attributes=city_attrs))
            else:
                new_state = main_state if city_in_current_payload else "off"
                update_tasks.append(self.set_state(self.city_sensor_active_alert, state=new_state, attributes=city_attrs))
        except Exception as e:
            self.log(f"{log_prefix} Error preparing task for {self.city_sensor}: {e}", level="ERROR")

        try:
            if main_state == "on":
                safe_text_state = text_state[:255] if isinstance(text_state, str) else "Error"
                current_text_state = await self.get_state(self.main_text)
                if safe_text_state != current_text_state:
                    update_tasks.append(self.set_state(self.main_text, state=safe_text_state, attributes={"icon": text_icon}))

        except Exception as e:
            self.log(f"{log_prefix} Error preparing/checking task for {self.main_text}: {e}", level="ERROR")

        if update_tasks:
            try:
                results = await asyncio.gather(*update_tasks, return_exceptions=True)
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        self.log(f"{log_prefix} Error during HA state update task: {result}", level="ERROR", exc_info=False) 

            except Exception as e:
                self.log(f"{log_prefix} Unexpected error executing HA state updates via asyncio.gather: {e}", level="ERROR")

    async def poll_alerts(self):
        """Fetches alerts from API, processes them, or checks for sensor reset."""
        log_prefix = "[Poll Cycle]"

        live_data = None
        api_error = False
        try:
            live_data = await self.api_client.get_live_alerts()
        except Exception as e:
            self.log(f"{log_prefix} Error fetching live alerts from Oref API: {e}", level="WARNING")
            live_data = None 
            api_error = True 

        try:
            is_alert_active = isinstance(live_data, dict) and live_data.get("data")

            if is_alert_active:
                self.no_active_alerts_polls = 0 
                await self._process_active_alert(live_data, is_test=False)

                if self.test_alert_cycle_flag > 0:
                    self.log(f"{log_prefix} Real alert detected during active test window. Cancelling test mode.", level="INFO")
                    self.test_alert_cycle_flag = 0
                    self.test_alert_start_time = 0
                    try:
                        if await self.get_state(self.activate_alert) == "on":
                            await self.call_service("input_boolean/turn_off", entity_id=self.activate_alert)
                    except Exception as e_bool:
                        self.log(f"{log_prefix} Error turning off test boolean after interruption: {e_bool}", level="WARNING")

            else:  
                if not api_error:
                    self.no_active_alerts_polls += 1
                else:
                    self.log(f"{log_prefix} API error occurred, not incrementing idle poll count.", level="DEBUG")

                try:
                    if self.history_manager._prune_and_limit():
                        self.log(f"{log_prefix} Old alerts aged out. Updating history sensors.", level="DEBUG")
                        current_hist_attrs = self.history_manager.get_history_attributes()

                        count_alerts = len(current_hist_attrs.get("last_24h_alerts", []))
                        tasks = [
                            self.set_state(self.history_cities_sensor, state=str(len(current_hist_attrs.get("cities_past_24h", []))), attributes={"cities_past_24h": current_hist_attrs["cities_past_24h"], "script_status": "running"}),
                            self.set_state(self.history_list_sensor, state=str(count_alerts), attributes={"last_24h_alerts": current_hist_attrs["last_24h_alerts"], "script_status": "running"}),
                            self.set_state(self.history_group_sensor, state=str(count_alerts), attributes={"last_24h_alerts_group": current_hist_attrs["last_24h_alerts_group"], "script_status": "running"})
                        ]
                        if self.save_2_file and self.file_manager:
                            tasks.append(self._save_history_geojson(current_hist_attrs))
                        
                        await asyncio.gather(*tasks, return_exceptions=True)
                        self.last_history_attributes_cache = current_hist_attrs
                        
                except Exception as e:
                    self.log(f"{log_prefix} Error updating history sensors during idle poll: {e}", level="ERROR")

                if self.test_alert_cycle_flag > 0:
                    if time.time() - self.test_alert_start_time >= self.timer_duration:
                        self.log(f"{log_prefix} Test alert timer expired. Ending test window.", level="INFO")
                        self.test_alert_cycle_flag = 0
                        self.test_alert_start_time = 0
                        await self._check_reset_sensors()
                    else:
                        return 
                else:
                    await self._check_reset_sensors()

        except Exception as e:
            self.log(f"{log_prefix} Error in poll_alerts processing/reset logic: {e}", level="ERROR")
            if self.test_alert_cycle_flag > 0:
                self.log(f"{log_prefix} Clearing test flag due to error.", level="WARNING")
                self.test_alert_cycle_flag = 0

    def _test_boolean_callback(self, entity, attribute, old, new, kwargs):
        """Callback when the test input_boolean is turned on."""
        if new == 'on':
            self.log(f"Test input_boolean {entity} turned on. Initiating test alert sequence.", level="WARNING")
            self.create_task(self._handle_test_alert())

    async def _handle_test_alert(self):
        """Initiates a test alert sequence using configured or default cities."""
        log_prefix = "[Test Sequence]"
        if self.test_alert_cycle_flag != 0:
            try: await self.call_service("input_boolean/turn_off", entity_id=self.activate_alert)
            except Exception: pass
            return

        current_state = await self.get_state(self.main_sensor)
        if current_state == 'on' and self.test_alert_cycle_flag == 0: 
            self.log(f"{log_prefix} Cannot start test alert: A real alert is currently active.", level= "WARNING")
            try: await self.call_service("input_boolean/turn_off", entity_id=self.activate_alert)
            except Exception: pass
            return

        self.test_alert_cycle_flag = 1 
        self.test_alert_start_time = time.time()
        self.log(f"--- {log_prefix} Initiating Test Alert Sequence ---", level="WARNING")

        test_cities_orig = []
        if self.city_names_self_std:
            found_cities = []
            missing_cities = []
            for std_name in self.city_names_self_std:
                details = self.lamas_manager.get_city_details(std_name)
                if details and details.get("original_name"):
                    found_cities.append(details["original_name"])
                else:
                    found_cities.append(std_name)
                    missing_cities.append(std_name)
            test_cities_orig = found_cities
            if missing_cities:
                self.log(f"{log_prefix} Using configured cities for test. Lamas lookup missing for: {missing_cities}", level="DEBUG")

        else: 
            default_test_city = "תל אביב - מרכז העיר"
            self.log(f"{log_prefix} No valid 'city_names' configured. Using default '{default_test_city}' for test.", level="WARNING")
            test_cities_orig = [default_test_city]

        if not test_cities_orig: 
            test_cities_orig = ["תל אביב - מרכז העיר"]
            self.log(f"{log_prefix} Test city list was empty after processing, using fallback: {test_cities_orig}", level="WARNING")

        test_alert_data = {
            "id": int(time.time() * 1000), 
            "cat": "1", 
            "title": "ירי רקטות וטילים (התרעת בדיקה)", 
            "data": test_cities_orig, 
            "desc": "התרעת בדיקה - כנסו למרחב המוגן לזמן קצר לבדיקה" 
        }

        try:
            await self._process_active_alert(test_alert_data, is_test=True)
        except Exception as test_proc_err:
            self.log(f"{log_prefix} Error during processing of test alert data: {test_proc_err}", level="ERROR")
            self.test_alert_cycle_flag = 0
            self.test_alert_start_time = 0

        try:
            if await self.get_state(self.activate_alert) == 'on':
                await self.call_service("input_boolean/turn_off", entity_id=self.activate_alert)
                self.log(f"{log_prefix} Test alert processed. Turned off input_boolean: {self.activate_alert}", level="INFO")
        except Exception as e:
            self.log(f"{log_prefix} Error turning off test input_boolean ({self.activate_alert}): {e}", level="WARNING")


    async def _save_latest_geojson(self, attributes):
        """Generates and saves only the latest GeoJSON file."""
        if not self.save_2_file or not self.file_manager: return
        if not attributes:
            self.log("Skipping Latest GeoJSON save: Attributes missing.", level="WARNING")
            return
        try:
            latest_geojson_data = self._generate_geojson_data(attributes, duration="latest")
            path = self.file_paths.get("geojson_latest")
            if path:
                self.file_manager.save_geojson_file(latest_geojson_data, path)
            else:
                self.log("Skipping Latest GeoJSON save: Path not found.", level="WARNING")
        except Exception as e:
            self.log(f"Error saving Latest GeoJSON: {e}", level="ERROR")

    async def _save_history_geojson(self, history_attributes):
        """Generates and saves only the history GeoJSON file."""
        if not self.save_2_file or not self.file_manager: return
        if not history_attributes or "last_24h_alerts" not in history_attributes:
            self.log("Skipping History GeoJSON save: History attributes missing or invalid.", level="WARNING")
            return
        try:
            history_geojson_data = self._generate_geojson_data(history_attributes, duration="history")
            path = self.file_paths.get("geojson_history")
            if path:
                self.file_manager.save_geojson_file(history_geojson_data, path)
            else:
                self.log("Skipping History GeoJSON save: Path not found.", level="WARNING")
        except Exception as e:
            self.log(f"Error saving History GeoJSON: {e}", level="ERROR")

    def _generate_geojson_data(self, attributes, duration="latest"):
        """Generates the GeoJSON structure (FeatureCollection)."""
        geo = {"type": "FeatureCollection", "features": []}
        attrs = attributes or {} 
        locations = {} 
        unknown_cities_logged = set() 

        if duration == "latest":
            cities_to_process = attrs.get("cities", [])
            alert_title = attrs.get("title", "אין התרעות")
            timestamp_str = attrs.get("last_changed", datetime.now().isoformat(timespec='microseconds'))
            category = attrs.get("cat", 0)
            description = attrs.get("desc", "")

            if not cities_to_process: return geo 

            for city_display_name in cities_to_process:
                if not isinstance(city_display_name, str) or not city_display_name.strip(): continue
                std = standardize_name(city_display_name)
                if not std: continue 
                det = self.lamas_manager.get_city_details(std)

                if det and "lat" in det and "long" in det:
                    try:
                        lat, lon = float(det["lat"]), float(det["long"])
                        key = f"{lat},{lon}" 
                        if key not in locations:
                            locations[key] = {"coords": [lon, lat], "cities": set()}
                        locations[key]["cities"].add(city_display_name) 
                    except (ValueError, TypeError) as e:
                        if std not in unknown_cities_logged: 
                            self.log(f"GeoJSON ({duration}): Invalid coords for '{city_display_name}': {e}", level="WARNING")
                            unknown_cities_logged.add(std)
                elif std not in unknown_cities_logged: 
                    reason = "Not found in Lamas" if not det else "Missing coords"
                    self.log(f"GeoJSON ({duration}): SKIP city '{city_display_name}' (std: '{std}'). Reason: {reason}.", level="DEBUG") 
                    unknown_cities_logged.add(std)

            if locations:
                icon_mdi, emoji = ICONS_AND_EMOJIS.get(category, ("mdi:alert", "❗"))
                for key, loc_data in locations.items():
                    city_names_at_point = sorted(list(loc_data["cities"]))
                    props = {
                        "name": ", ".join(city_names_at_point), 
                        "icon": icon_mdi,
                        "label": emoji,
                        "description": f"{alert_title}\n{description}\n({timestamp_str})",
                        "alert_type": alert_title,
                        "timestamp": timestamp_str,
                        "category": category
                    }
                    geo["features"].append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": loc_data["coords"]},
                        "properties": props
                    })

        elif duration == "history":
            history_list = attrs.get("last_24h_alerts", [])
            if not history_list: return geo 

            for alert in history_list:
                if not isinstance(alert, dict): continue
                city_display_name = alert.get("city") 
                if not city_display_name or not isinstance(city_display_name, str): continue

                std = standardize_name(city_display_name)
                if not std: continue
                det = self.lamas_manager.get_city_details(std)

                if det and "lat" in det and "long" in det:
                    try:
                        lat, lon = float(det["lat"]), float(det["long"])
                        key = f"{lat},{lon}"
                        if key not in locations:
                            locations[key] = {"coords": [lon, lat], "cities": set(), "details": []}
                        locations[key]["details"].append(alert)
                        locations[key]["cities"].add(city_display_name)
                    except (ValueError, TypeError) as e:
                        if std not in unknown_cities_logged:
                            self.log(f"GeoJSON ({duration}): Invalid hist coords for '{city_display_name}': {e}", level="WARNING")
                            unknown_cities_logged.add(std)
                elif std not in unknown_cities_logged:
                    reason = "Not found in Lamas" if not det else "Missing coords"
                    self.log(f"GeoJSON ({duration}): SKIP hist city '{city_display_name}' (std: '{std}'). Reason: {reason}.", level="DEBUG") 
                    unknown_cities_logged.add(std)

            if locations:
                icon_mdi, emoji = ("mdi:history", "📜") 
                for key, loc_data in locations.items():
                    if not loc_data.get("details"): continue 

                    try:
                        latest_alert_at_loc = max(
                            loc_data["details"],
                            key=lambda x: parse_datetime_str(x.get("time", ""), self.log) or datetime.min
                        )
                    except (ValueError, TypeError) as max_err:
                        self.log(f"GeoJSON ({duration}): Error finding latest alert time for location {key}: {max_err}", level="WARNING")
                        continue 

                    city_names_at_point = sorted(list(loc_data["cities"]))
                    alert_time_str = latest_alert_at_loc.get('time', 'N/A') 
                    alert_count = len(loc_data['details'])
                    desc = f"{latest_alert_at_loc.get('title', 'התרעה היסטורית')}\n" \
                        f"{', '.join(city_names_at_point)}\n" \
                        f"זמן אחרון: {alert_time_str}\n" \
                        f"סה״כ: {alert_count} אירועים"

                    props = {
                        "name": ", ".join(city_names_at_point),
                        "area": latest_alert_at_loc.get("area", ""),
                        "icon": icon_mdi,
                        "label": emoji,
                        "description": desc,
                        "alert_count_at_location": alert_count,
                        "latest_alert_time": alert_time_str 
                    }
                    geo["features"].append({
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": loc_data["coords"]},
                        "properties": props
                    })
        else:
            self.log(f"GeoJSON: Unknown duration type '{duration}'.", level="WARNING")

        return geo


    def _format_backup_data_as_prev(self, data):
        """Formats data loaded from JSON backup into the 'prev_*' attribute structure."""
        if not isinstance(data, dict):
            self.log("Backup data is not a dictionary, cannot format.", level="WARNING")
            return {} 

        cat_str = data.get('cat', '0') 
        cat = int(cat_str) if isinstance(cat_str, str) and cat_str.isdigit() else 0
        title = data.get('title', '')
        raw_cities_data = data.get('data', [])
        cities_from_backup = []

        if isinstance(raw_cities_data, str):
            cities_from_backup = [c.strip() for c in raw_cities_data.split(',') if c.strip()]
        elif isinstance(raw_cities_data, list):
            cities_from_backup = [str(c) for c in raw_cities_data if isinstance(c, (str, int))] 

        desc = data.get('desc', '')
        last = self._is_iso_format(data.get('last_changed', data.get('alertDate', '')))
        dur = self.alert_processor.extract_duration_from_desc(desc) if self.alert_processor else 0

        areas_set = set()
        orig_cities_set = set(cities_from_backup) 
        unknown_cities_logged = set() 

        if self.lamas_manager: 
            refined_orig_cities = set()
            for city_name_from_backup in cities_from_backup:
                if not city_name_from_backup: continue
                std = standardize_name(city_name_from_backup)
                if not std:
                    refined_orig_cities.add(city_name_from_backup) 
                    continue

                det = self.lamas_manager.get_city_details(std)
                if det:
                    areas_set.add(det.get("area", DEFAULT_UNKNOWN_AREA))
                    refined_orig_cities.add(det.get("original_name", city_name_from_backup))
                else:
                    areas_set.add(DEFAULT_UNKNOWN_AREA)
                    refined_orig_cities.add(city_name_from_backup)
                    if std not in unknown_cities_logged:
                        unknown_cities_logged.add(std)
            orig_cities_set = refined_orig_cities 

        sorted_orig_cities = sorted(list(orig_cities_set))
        areas_str = ", ".join(sorted(list(areas_set))) if areas_set else ""
        prev_data_str = ", ".join(sorted_orig_cities)

        return {
            "prev_cat": cat,
            "prev_title": title,
            "prev_desc": desc,
            "prev_areas": areas_str,
            "prev_cities": sorted_orig_cities, 
            "prev_data": prev_data_str,        
            "prev_data_count": len(sorted_orig_cities),
            "prev_duration": dur,
            "prev_last_changed": last, 
            "prev_alerts_count": data.get('alerts_count', 0) 
        }

    def generate_smart_alert_map(self, alert_segments, lamas_data):
        """
        Final Tactical Map Engine:
        1. Priority Layering: Clear > Active > Pre.
        2. Clustering with Containment Check: Prevents redundant polygons of the same color.
        3. 3-Decimal Precision & Decimated Hull: Optimized for Yandex 2048 char limit.
        """
        import math
        from collections import defaultdict
        
        COLORS = {"pre": "ff9800", "active": "f44336", "clear": "4caf50"}
        yandex_paths = []
        all_coords_for_center = []
        ignore_list = ["ברחבי הארץ", "כל הארץ", "ישראל", "לא ידוע"]

        if not alert_segments:
            return "https://static-maps.yandex.ru/1.x/?l=map&lang=he_IL&size=600,450&ll=34.852,31.046&z=7"

        def is_point_in_poly(x, y, poly):
            n = len(poly)
            inside = False
            if n < 3: return False
            p1x, p1y = poly[0]
            for i in range(n + 1):
                p2x, p2y = poly[i % n]
                if y > min(p1y, p2y):
                    if y <= max(p1y, p2y):
                        if x <= max(p1x, p2x):
                            if p1y != p2y:
                                xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                            if p1x == p2x or x <= xints:
                                inside = not inside
                p1x, p1y = p2x, p2y
            return inside

        merged_cities = defaultdict(set)
        for segment in alert_segments:
            seg_type = segment.get("type", "active")
            for city in segment.get("cities", []):
                if city not in ignore_list:
                    merged_cities[seg_type].add(city)

        coords_by_type = defaultdict(set)
        for seg_type, cities in merged_cities.items():
            if lamas_data and "areas" in lamas_data:
                for area_cities in lamas_data["areas"].values():
                    for city_name in cities:
                        if city_name in area_cities:
                            d = area_cities[city_name]
                            if "lat" in d and "long" in d:
                                p = (float(d["long"]), float(d["lat"]))
                                coords_by_type[seg_type].add(p)
                                all_coords_for_center.append(p)

        if "clear" in coords_by_type:
            coords_by_type["active"] -= coords_by_type["clear"]
            coords_by_type["pre"] -= coords_by_type["clear"]
        if "active" in coords_by_type:
            coords_by_type["pre"] -= coords_by_type["active"]

        DIST_THRESHOLD = 0.30
        
        for seg_type in ["pre", "active", "clear"]:
            points = list(coords_by_type[seg_type])
            if not points: continue
            
            clusters = []
            for p in points:
                found = False
                for cluster in clusters:
                    if any(math.sqrt((p[0]-cp[0])**2 + (p[1]-cp[1])**2) < DIST_THRESHOLD for cp in cluster):
                        cluster.append(p)
                        found = True
                        break
                if not found: clusters.append([p])

            hulls_candidates = []
            for cluster in clusters:
                expanded = []
                for lon, lat in cluster:
                    for angle in range(0, 360, 72): 
                        rad = math.radians(angle)
                        expanded.append((lon + 0.015 * math.cos(rad), lat + 0.015 * math.sin(rad)))
                h = get_convex_hull(expanded)
                if h: hulls_candidates.append({'hull': h, 'cluster': cluster})

            hulls_candidates.sort(key=lambda x: len(x['cluster']), reverse=True)
            
            color_hex = COLORS.get(seg_type, "f44336")
            final_type_paths = []

            for i, data in enumerate(hulls_candidates):
                is_contained = False
                for j, target in enumerate(hulls_candidates):
                    if i <= j: continue 
                    
                    c_lon = sum(p[0] for p in data['cluster']) / len(data['cluster'])
                    c_lat = sum(p[1] for p in data['cluster']) / len(data['cluster'])
                    
                    if is_point_in_poly(c_lon, c_lat, target['hull']):
                        is_contained = True
                        break
                
                if not is_contained:
                    hull = data['hull']
                    if len(hull) > 12: hull = hull[::len(hull)//12 + 1]
                    
                    path_pts = [f"{round(p[0], 3)},{round(p[1], 3)}" for p in hull]
                    path_pts.append(path_pts[0])
                    final_type_paths.append(f"c:{color_hex}ff,f:{color_hex}66,w:2,{','.join(path_pts)}")

            yandex_paths.extend(final_type_paths)

        if not all_coords_for_center:
            return "https://static-maps.yandex.ru/1.x/?l=map&lang=he_IL&size=600,450&ll=34.852,31.046&z=7"

        lons, lats = [p[0] for p in all_coords_for_center], [p[1] for p in all_coords_for_center]
        avg_lon, avg_lat = round(sum(lons)/len(lons), 3), round(sum(lats)/len(lats), 3)
        lat_diff, lon_diff = max(lats)-min(lats), max(lons)-min(lons)
        
        if lat_diff > 1.2 or lon_diff > 1.2: z = 7
        elif lat_diff > 0.5 or lon_diff > 0.5: z = 8
        elif lat_diff > 0.2 or lon_diff > 0.2: z = 9
        elif lat_diff > 0.05 or lon_diff > 0.05: z = 10
        else: z = 11

        url = f"https://static-maps.yandex.ru/1.x/?l=map&lang=he_IL&size=600,450&ll={avg_lon},{avg_lat}&z={z}"
        if yandex_paths:
            url += "&pl=" + "~".join(yandex_paths[:7])
            
        return url
        
