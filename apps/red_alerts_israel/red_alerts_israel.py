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
```yaml
red_alerts_israel:
  module: red_alerts_israel      # Python module name (don't change)
  class: Red_Alerts_Israel       # Class name (don't change)

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
     - "חיפה - מפרץ"			  # Example: Haifa Bay
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
                    # Attempt decoding with utf-8-sig first, then utf-8 as fallback
                    try:
                        return raw_data.decode('utf-8-sig')
                    except UnicodeDecodeError:
                        self._log("Failed decoding with utf-8-sig, trying utf-8.", level="DEBUG")
                        return raw_data.decode('utf-8')

            text = await self._fetch_with_retries(_do_fetch)

            if not text or not text.strip():
                return None

            try:
                # Remove BOM if present before loading JSON
                text = check_bom(text)
                return json.loads(text)
            except json.JSONDecodeError as e:
                log_text_preview = text[:1000].replace('\n', '\\n').replace('\r', '\\r') 
                if "Expecting value: line 1 column 1 (char 0)" in str(e) and len(text) > 0:
                    pass
                    #self._log(f"Invalid JSON: Received non-empty data that did not start with a valid JSON value. Content preview: '{log_text_preview}...'", level="WARNING")
                else:
                    self._log(f"Invalid JSON in live alerts: {e}. Raw text preview: '{log_text_preview}...'", level="WARNING")
                return None

        except aiohttp.ClientResponseError as e:
            self._log(f"HTTP error fetching live alerts: Status {e.status}, Message: {e.message}", level="WARNING")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e: # Combined network errors
            self._log(f"Network/Timeout error fetching live alerts: {e}", level="WARNING")
        except Exception as e:
            self._log(f"Unexpected error fetching live alerts: {e.__class__.__name__} - {e}", level="ERROR", exc_info=True)

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
                #if text.startswith('\ufeff'):
                #    text = text.lstrip('\ufeff')
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
            self._log(f"Unexpected error fetching history: {e}", level="ERROR", exc_info=True)
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
            #if text and text.startswith('\ufeff'):
            #    text = text.lstrip('\ufeff')
            return text
        except aiohttp.ClientResponseError as e:
            self._log(f"HTTP error downloading file {url}: Status {e.status}, Message: {e.message}", level="ERROR")
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self._log(f"Network/Timeout error downloading file {url}: {e}", level="ERROR")
        except Exception as e:
            self._log(f"Unexpected error downloading file {url}: {e}", level="ERROR", exc_info=True)
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
                if loaded and 'areas' in loaded: # Basic validation
                    pass
                else:
                    self._log("Local Lamas data invalid or empty. Will attempt download.", level="WARNING")
                    loaded = None # Force download if local file is bad
            except (json.JSONDecodeError, OSError, Exception) as e:
                self._log(f"Error reading local Lamas file '{self._local_file_path}': {e}. Will attempt download.", level="WARNING")
                loaded = None # Force download on error

        if loaded is None:
            self._log("Downloading Lamas data from GitHub.")
            text = await self._api_client.download_file(self._github_url)
            if text:
                try:
                    # Ensure BOM is removed if present
                    text = check_bom(text)
                    loaded = json.loads(text)
                    if loaded and 'areas' in loaded: # Basic validation
                        try:
                            os.makedirs(os.path.dirname(self._local_file_path), exist_ok=True)
                            with open(self._local_file_path, 'w', encoding='utf-8-sig') as f:
                                json.dump(loaded, f, ensure_ascii=False, indent=2) # Save downloaded JSON prettified
                            self._log("Lamas data downloaded and saved locally.")
                        except Exception as e:
                            self._log(f"Error saving Lamas data locally to '{self._local_file_path}': {e}", level="ERROR")
                    else:
                        self._log("Downloaded Lamas data is invalid (missing 'areas' key).", level="ERROR")
                        loaded = None # Indicate failure
                except json.JSONDecodeError as e:
                    self._log(f"Invalid Lamas JSON downloaded from '{self._github_url}': {e}", level="ERROR")
                    loaded = None # Indicate failure
            else:
                self._log("Failed to download Lamas data.", level="ERROR")


        # Process whatever data we ended up with (local or downloaded)
        if loaded and self._process_lamas_data(loaded):
            self._build_city_details_map()
            return True

        # Critical failure if we couldn't load from anywhere
        self._log("CRITICAL: Failed to load Lamas data from both local file and download.", level="CRITICAL")
        self._lamas_data = None
        self._city_details_map = {}
        return False

    def _process_lamas_data(self, raw_data):
        """Internal: Processes raw Lamas data into the internal structure."""
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
                    if not isinstance(details, dict): # Add check for detail type
                        self._log(f"Lamas Processing: Expected dict for city details of '{city}' in area '{area}', got {type(details)}. Skipping city.", level="WARNING")
                        continue
                    expected_keys_count += 1
                    std = standardize_name(city)
                    if not std: # Skip if standardized name becomes empty
                        self._log(f"Lamas Processing: City '{city}' resulted in empty standardized name. Skipping.", level="WARNING")
                        continue

                    entry = {"original_name": city}
                    # Safely extract lat/long
                    lat = details.get("lat")
                    lon = details.get("long") # Renamed from 'long' for clarity
                    try:
                        if lat is not None and lon is not None:
                            entry["lat"]  = float(lat)
                            entry["long"] = float(lon)
                        elif lat is not None or lon is not None:
                            self._log(f"Lamas Processing: City '{city}' has partial coordinates (lat: {lat}, long: {lon}). Skipping coords.", level="DEBUG")
                    except (ValueError, TypeError):
                        self._log(f"Lamas Processing: Invalid coordinate types for city '{city}' (lat: {lat}, long: {lon}). Skipping coords.", level="WARNING")

                    if std in std_cities: # Check for duplicate standardized names within the same area
                        self._log(f"Lamas Processing: Duplicate standardized name '{std}' found in area '{area}'. Original names: '{std_cities[std]['original_name']}', '{city}'. Overwriting.", level="WARNING")

                    std_cities[std] = entry
                    processed_keys_count += 1
                proc['areas'][area] = std_cities
            else:
                self._log(f"Lamas Processing: Expected dict for area '{area}', got {type(cities)}. Skipping area.", level="WARNING")
                proc['areas'][area] = {} # Ensure area exists but is empty
        self._lamas_data = proc
        if expected_keys_count != processed_keys_count:
            self._log(f"Lamas Processing: Mismatch - attempted {expected_keys_count} city entries, successfully processed {processed_keys_count}.", level="WARNING")
        #self._log(f"Lamas data processed: {len(proc['areas'])} areas, {processed_keys_count} cities.", level="INFO")
        return True

    def _build_city_details_map(self):
        """Internal: Builds the flat map for quick standardized name lookups."""
        self._city_details_map = {}
        if self._lamas_data and 'areas' in self._lamas_data:
            entries_built = 0
            duplicates = {} # Track potential duplicates across different areas
            for area, cities in self._lamas_data['areas'].items():
                if isinstance(cities, dict):
                    for std, details in cities.items():
                        if std in self._city_details_map:
                            # Log duplicate standardized names found across areas
                            if std not in duplicates: duplicates[std] = [self._city_details_map[std]['area']]
                            duplicates[std].append(area)

                            self._log(f"Lamas Map Build: Duplicate std name '{std}' found in areas: {duplicates[std]}. Using entry from area '{area}'.", level="WARNING")
                        # Combine details with area info, potentially overwriting previous entry
                        self._city_details_map[std] = {**details, "area": area}
                        entries_built += 1
                else:
                    self._log(f"Lamas Map Build: Area '{area}' has unexpected data type {type(cities)}. Skipping.", level="WARNING")

            if entries_built > 0:
                #self._log(f"Built city map ({len(self._city_details_map)} unique standardized entries).")
                pass
            else:
                self._log("Lamas Map Build: No valid city entries found to build map.", level="ERROR")
            if duplicates:
                self._log(f"Lamas Map Build: Found {len(duplicates)} standardized names duplicated across multiple areas.", level="WARNING")
        else:
            self._log("No Lamas data available to build map.", level="ERROR")

    @functools.lru_cache(maxsize=512) # Cache recent lookups
    def get_city_details(self, standardized_name: str):
        """Gets city details (original name, coords, area) from the map using the standardized name."""
        if not isinstance(standardized_name, str) or not standardized_name:
            return None
        return self._city_details_map.get(standardized_name) # Returns None if not found

# ----------------------------------------------------------------------
# Helper Class: AlertProcessor
# ----------------------------------------------------------------------
class AlertProcessor:
    def __init__(self, lamas_manager, icons_emojis_map, logger):
        self._lamas = lamas_manager
        self._icons = icons_emojis_map
        self._log   = logger
        # Define limits once
        self.max_msg_len = 700
        self.max_attr_len = 160000
        self.max_input_len = 255


    def extract_duration_from_desc(self, descr: str) -> int:
        """Extracts alert duration in seconds from description text."""
        if not isinstance(descr, str):
            return 0
        # Regex to find number followed by 'דקות' or 'דקה'
        m = re.search(r'(\d+)\s+(דקות|דקה)', descr)
        if m:
            try:
                minutes = int(m.group(1))
                return minutes * 60 # Return duration in seconds
            except ValueError:
                self._log(f"Could not parse number from duration string: '{m.group(1)}'", level="WARNING")
        return 0 # Return 0 if no match or conversion error

    def _check_len(self, text: str, count: int, areas: str, max_len: int, context: str = "message") -> str:
        """Truncates text if it exceeds max_len, adding a notice."""
        if not isinstance(text, str): return "" # Handle non-string input
        try:
            text_len = len(text)
            if text_len > max_len:
                small_text = f"מתקפה מורחבת על {count} ערים באזורים הבאים: {areas}"
                return small_text
        except Exception as e:
            self._log(f"Error during _check_len for {context}: {e}", level="ERROR")
        return text

    def process_alert_window_data(self, category, title, description, window_std_cities, window_alerts_grouped):
        """Processes the accumulated data for the current alert window to generate HA state attributes."""
        log_prefix = "[Alert Processor]"

        # --- 1. Basic processing based on LATEST alert info ---
        icon, emoji = self._icons.get(category, ("mdi:alert", "❗"))
        duration = self.extract_duration_from_desc(description)

        # --- 2. Handle Empty Input ---
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

        # --- 3. Process OVERALL accumulated cities ---
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

        overall_areas_list_sorted = sorted(list(overall_areas_set))
        overall_areas_str = ", ".join(overall_areas_list_sorted) if overall_areas_list_sorted else "ישראל"
        overall_cities_list_sorted = sorted(list(overall_orig_cities_set))
        overall_count = len(overall_cities_list_sorted)
        overall_cities_str = ", ".join(overall_cities_list_sorted)

        # --- 4. Generate Standard Message Components ---
        full_overall_lines = []
        for area, names_set in sorted(cities_by_area_overall.items()):
            sorted_cities_str_area = ", ".join(sorted(list(names_set)))
            full_overall_lines.append(f"{area}: {sorted_cities_str_area}")
        status_str_raw = f"{title} - {overall_areas_str}: {overall_cities_str}"
        full_message_str_raw = title + "\n * " + "\n * ".join(full_overall_lines)
        alert_txt_basic = " * ".join(full_overall_lines)

        # --- 5. Generate Grouped WhatsApp and Telegram Messages ---
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
            wa_grouped_lines.append(f"\n_{description}_")
            tg_grouped_lines.append(f"\n__{description}__")

        text_wa_grouped_raw = "\n".join(wa_grouped_lines)
        text_tg_grouped_raw = "\n".join(tg_grouped_lines)

        # --- 6. Truncate Results if Needed ---
        text_wa_grouped_checked = self._check_len(text_wa_grouped_raw, overall_count, overall_areas_str, self.max_msg_len, "Grouped WhatsApp Msg")
        text_tg_grouped_checked = self._check_len(text_tg_grouped_raw, overall_count, overall_areas_str, self.max_msg_len, "Grouped Telegram Msg")
        status_checked = self._check_len(status_str_raw, overall_count, overall_areas_str, self.max_attr_len, "Status Attribute")
        full_message_str_checked = self._check_len(full_message_str_raw, overall_count, overall_areas_str, self.max_attr_len, "Full Message Attribute")
        overall_cities_str_checked = self._check_len(overall_cities_str, overall_count, overall_areas_str, self.max_attr_len, "Cities String Attribute")
        input_state = self._check_len(status_str_raw, overall_count, overall_areas_str, self.max_input_len, "Input Text State")[:self.max_input_len]

        # --- 7. Return Final Attributes Dictionary ---
        return {
            "areas_alert_str": overall_areas_str,
            "cities_list_sorted": overall_cities_list_sorted,
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
        """Initializes the HistoryManager"""
        if not isinstance(timer_duration_seconds, (int, float)) or timer_duration_seconds <= 0:
            logger.log(f"Invalid timer_duration_seconds ({timer_duration_seconds}), using default 120.", level="WARNING")
            timer_duration_seconds = 120
        if not isinstance(hours_to_show, (int, float)) or hours_to_show <= 0:
            logger.log(f"Invalid hours_to_show ({hours_to_show}), using default 4.", level="WARNING")
            hours_to_show = 4

        self._hours_to_show = hours_to_show
        self._lamas = lamas_manager # Expects an instance of LamasDataManager
        self._log   = logger        # Expects an AppDaemon logger instance
        self._timer_duration_seconds = timer_duration_seconds # Store the duration in seconds
        self._history_list = [] # List of dicts {'title':.., 'city':.., 'area':.., 'time': datetime}
        self._added_in_current_poll = set() # Tracks (title, std_city, area) tuples added this poll cycle

    def clear_poll_tracker(self):
        """Clears the set tracking entries added during the last poll cycle."""
        self._added_in_current_poll.clear()

    def _parse_datetime_str(self, ds: str) -> datetime | None:
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
            # Last attempt with fromisoformat (less reliable for varied inputs)
            return datetime.fromisoformat(ds)
        except ValueError:
            return None
        except Exception as e:
            self._log(f"Unexpected error parsing datetime string '{ds}': {e}", level="WARNING")
            return None

    async def load_initial_history(self, api_client):
        """Loads initial history data from the API."""
        data = await api_client.get_alert_history() 
        if not isinstance(data, list):
            self._history_list = []
            self._log("Failed to load initial history or history was empty/invalid.\nIf no alerts in the past 24 hours that's normal and you can ignore this message", level="WARNING")
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
            alert_date_str = e.get('alertDate')
            t = self._parse_datetime_str(alert_date_str)

            if not isinstance(t, datetime):
                if alert_date_str: parse_errors += 1
                continue # Skip if parsing failed
            if t < cutoff:
                continue # Skip if older than cutoff

            city_raw = e.get('data','לא ידוע')
            std = standardize_name(city_raw)
            det = self._lamas.get_city_details(std)
            area = det["area"] if det else DEFAULT_UNKNOWN_AREA
            orig_name = det["original_name"] if det else city_raw

            if not det and std and std not in unknown_cities_logged:
                self._log(f"Initial History Load: City '{std}' (raw: '{city_raw}') not found. Area='{area}'.", level="DEBUG")
                unknown_cities_logged.add(std)

            temp_hist.append({
                'title': e.get('title','לא ידוע'),
                'city': orig_name,
                'area': area,
                'time': t # Keep as datetime object
            })

        if parse_errors > 0:
            self._log(f"Initial History Load: Encountered {parse_errors} entries with unparseable dates.", level="WARNING")

        # Sort by time, newest first
        temp_hist.sort(key=lambda x: x.get('time', datetime.min), reverse=True)
        self._history_list = temp_hist
        cities_in_period_raw = set(a['city'] for a in self._history_list)

        self._log(f"Initial history: Processed {loaded_count} raw alerts, kept {len(self._history_list)} within {self._hours_to_show}h ({len(cities_in_period_raw)} unique cities).")

    def update_history(self, title: str, std_payload_cities: set):
        """Updates the history list with new alerts from the current payload. Pruning now happens in get_history_attributes."""
        now = datetime.now()
        unknown_cities_logged = set()
        added_count_this_call = 0

        if not std_payload_cities:
            return

        for std in std_payload_cities:
            if not std: continue # Skip empty standardized names
            det = self._lamas.get_city_details(std)
            area = DEFAULT_UNKNOWN_AREA
            orig_city_name = std
            if det:
                area = det.get("area", DEFAULT_UNKNOWN_AREA)
                orig_city_name = det.get("original_name", std)
            elif std not in unknown_cities_logged:
                self._log(f"History Add: City '{std}' not found. Using Area='{area}'.", level="WARNING")
                unknown_cities_logged.add(std)

            history_key = (title, std, area) # Key for deduplication within this poll

            if history_key not in self._added_in_current_poll:
                self._history_list.append({
                    'title': title,
                    'city': orig_city_name, # Store original name
                    'area': area,
                    'time': now # Store current datetime object
                })
                self._added_in_current_poll.add(history_key)
                added_count_this_call += 1

        if added_count_this_call > 0:
            # Sort the entire list after adding, newest first.
            self._history_list.sort(key=lambda x: x.get('time', datetime.min), reverse=True)


    def restructure_alerts(self, alerts_list: list) -> dict:
        """Groups alerts by title, then area, including city and time (HH:MM:SS). Expects list with STRING times."""
        structured_data = {}
        if not alerts_list: return structured_data

        for alert in alerts_list:
            if not isinstance(alert, dict):
                self._log(f"Restructure: Skipping non-dict item: {type(alert)}", level="WARNING")
                continue
            
            original_title = alert.get('title', 'לא ידוע')
            area  = alert.get('area', DEFAULT_UNKNOWN_AREA)
            city  = alert.get('city', 'לא ידוע')
            time_str = alert.get('time', '') # String time from previous step

            title = "התרעות מקדימות" if original_title == "בדקות הקרובות צפויות להתקבל התרעות באזורך" else original_title

            time_display = "??:??:??" # Default
            if isinstance(time_str, str) and ' ' in time_str and ':' in time_str:
                try:
                    # Extract just the time part (HH:MM:SS)
                    time_display = time_str.split(' ')[1]
                except IndexError:
                    self._log(f"Restructure: Could not split time from string '{time_str}' for '{city}'. Using default.", level="DEBUG")
            elif isinstance(time_str, str) and time_str: # Log unexpected non-empty strings
                self._log(f"Restructure: Unexpected time string format '{time_str}' for '{city}'. Using default.", level="DEBUG")

            area_dict = structured_data.setdefault(title, {})
            city_list_in_area = area_dict.setdefault(area, [])
            # Current logic allows duplicates here if input list has them.
            city_list_in_area.append({'city': city, 'time': time_display})

        # Sort cities within each area alphabetically AFTER grouping
        for title_group in structured_data.values():
            for area_group in title_group.values():
                area_group.sort(key=lambda x: x.get('city', ''))

        return structured_data

        # Inside the HistoryManager class...

    def get_history_attributes(self) -> dict:
        """
        Generates attributes for history sensors, applying time-based pruning (hours_to_show)
        and merging duplicates based on a 10-minute window per city, keeping the latest entry.
        Returns data using the original expected keys: 'cities_past_24h', 'last_24h_alerts', 'last_24h_alerts_group'.
        """
        # === Step 1: Pruning based on 'hours_to_show' ===
        now = datetime.now()
        cutoff = now - timedelta(hours=self._hours_to_show)
        # Filter list, ensuring time is valid datetime and >= cutoff
        # Assumes self._history_list is sorted newest-first (maintained by update_history)
        pruned_history_list = [
            a for a in self._history_list
            if isinstance(a.get('time'), datetime) and a['time'] >= cutoff
        ]

        # === Step 2: Apply NEW merging logic (10-minute window per city, keep latest) ===
        merged_history_newest_first = [] # Stores dicts with datetime objects, newest first
        time_of_last_added_alert_for_city = {} # Tracks {'city_name'} -> last_kept_datetime
        merge_window = timedelta(minutes=50) # Define the 10-minute window

        # self._log(f"History Attrs Step 2: Applying 10-min merge logic (on {len(pruned_history_list)} entries)...", level="DEBUG")

        # Iterate newest first (list is already sorted this way)
        for alert in pruned_history_list:
            # Basic validation of the alert structure
            if not isinstance(alert, dict) or not all(k in alert for k in ['title', 'city', 'area', 'time']):
                self._log(f"Merge Logic: Skipping malformed/incomplete entry: {alert}", level="WARNING")
                continue
            if not isinstance(alert['time'], datetime):
                self._log(f"Merge Logic: Skipping entry with non-datetime time: {alert}", level="WARNING")
                continue

            city_name = alert['city'] # Use the original city name stored in history
            alert_time = alert['time']

            if city_name in time_of_last_added_alert_for_city:
                last_added_time = time_of_last_added_alert_for_city[city_name]
                # Check if this alert is within 10 minutes *before* the last one added
                if last_added_time - alert_time < merge_window:
                    # This alert is within 10 mins of the newer one already kept for this city.
                    # Discard this one (effectively removing duplicates/older categories within the window).
                    # self._log(f"Merge Logic: Discarding '{city_name}' at {alert_time} (within 10min of newer kept entry at {last_added_time})", level="DEBUG")
                    continue
                else:
                    # This alert is older than 10 mins from the last *added* one for this city.
                    # It represents a distinct event block. Keep it.
                    merged_history_newest_first.append(alert)
                    # Update the tracking time to this alert's time, as it's the latest for this older block
                    time_of_last_added_alert_for_city[city_name] = alert_time
                    # self._log(f"Merge Logic: Keeping '{city_name}' at {alert_time} (distinct block, older than 10min from {last_added_time})", level="DEBUG")

            else:
                # First time encountering this city in the iteration (i.e., the absolute newest entry for this city overall).
                # Keep it and record its time.
                merged_history_newest_first.append(alert)
                time_of_last_added_alert_for_city[city_name] = alert_time
                # self._log(f"Merge Logic: Keeping '{city_name}' at {alert_time} (newest encountered)", level="DEBUG")

        merged_history_with_dt = list(merged_history_newest_first)
        # self._log(f"History Attrs Step 2: Merge complete. Kept {len(merged_history_with_dt)} entries.", level="DEBUG")

        # === Step 3: Format the filtered/merged list for HA attributes ===
        final_history_list_for_ha = []
        final_cities_set = set() # Collect unique city names from the final list

        for a in merged_history_with_dt: # Iterate through the merged list
            time_str = "N/A"
            try:
                # Format the datetime object into 'YYYY-MM-DD HH:MM:SS'
                time_str = a['time'].strftime('%Y-%m-%d %H:%M:%S')
            except AttributeError: # Catch if 'time' isn't a datetime somehow
                self._log(f"History Formatting: Non-datetime object found: {a.get('time')}", level="WARNING")
                time_str = str(a.get('time', 'N/A'))
            except Exception as e:
                self._log(f"History Formatting: Error formatting time {a.get('time')}: {e}", level="WARNING")
                time_str = str(a.get('time', 'N/A'))

            city_name = a.get('city', 'לא ידוע')
            final_history_list_for_ha.append({
                'title': a.get('title', 'לא ידוע'),
                'city': city_name,
                'area': a.get('area', DEFAULT_UNKNOWN_AREA),
                'time': time_str # The formatted string time
            })
            final_cities_set.add(city_name) # Add the original city name

        # === Step 4: Restructure the formatted list for the grouped attribute ===
        # Uses the result of the merge+format process
        final_grouped_structure = self.restructure_alerts(final_history_list_for_ha)

        # === Step 5: Return the final attributes structure using ORIGINAL keys ===
        return {
            "cities_past_24h": sorted(list(final_cities_set)), # Key expected by sensor updates
            "last_24h_alerts": final_history_list_for_ha,      # Key expected by sensors & geojson
            "last_24h_alerts_group": final_grouped_structure   # Key expected by sensor updates
        }

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
        self._last_saved_alert_id = None # Track last ID saved to CSV/TXT

    def _parse_datetime_str(self, ds: str):
        """Parses various datetime string formats into datetime objects."""
        if not ds or not isinstance(ds, str): return None
        ds = ds.strip().strip('"')
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"
        ]
        for fmt in formats:
            try: return datetime.strptime(ds, fmt)
            except ValueError: pass
        try:
            if '+' in ds or 'Z' in ds:
                dt_str = ds.split('+')[0].split('Z')[0]
                for iso_fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]:
                    try: return datetime.strptime(dt_str, iso_fmt)
                    except ValueError: pass
            return datetime.fromisoformat(ds.replace('Z', '+00:00'))
        except ValueError:
            self._log(f"FileManager: Failed to parse datetime '{ds}'", level="WARNING")
            return None

    def get_from_json(self):
        """Loads the last alert state from the JSON backup file."""
        path = self._paths.get("json_backup")
        if not self._save_enabled or not path or not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding='utf-8-sig') as f:
                data = json.load(f)
            # Basic validation: Ensure it's a dict and has some expected keys
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
        except TypeError as e: # Catch non-serializable data
            self._log(f"Error writing JSON backup to {path}: Data not JSON serializable - {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing JSON backup to {path}: {e}", level="ERROR")

    def save_history_files(self, attrs):
        """Saves the summary of the completed alert window to TXT and CSV files."""
        if not self._save_enabled or not attrs:
            return

        alert_id = attrs.get('id', 0)
        # Prevent saving the same alert window summary multiple times if called rapidly after reset
        if alert_id == self._last_saved_alert_id and alert_id != 0:
            return

        txt_p, csv_p = self._paths.get("txt_history"), self._paths.get("csv")
        if not txt_p or not csv_p:
            self._log("History file saving skipped (TXT or CSV path missing).", level="WARNING")
            return


        # Determine timestamp details from the last update of the window
        fmt_time, fmt_date, day_name_he = "שגיאה", "שגיאה", "שגיאה"
        try:
            last_update_str = attrs.get("last_changed") # Should be ISO format string
            last_update_dt = self._parse_datetime_str(last_update_str) or datetime.now() # Fallback to now
            event_dt = last_update_dt

            fmt_time = event_dt.strftime('%H:%M:%S')
            fmt_date = event_dt.strftime('%d/%m/%Y')
            day_name_en = event_dt.strftime('%A')
            day_name_he = self._day_names.get(day_name_en, day_name_en)
            date_str = f"\n{day_name_he}, {fmt_date}, {fmt_time}"
        except Exception as e:
            self._log(f"Error processing time for history file context: {e}", level="ERROR")
            date_str = "\nשגיאה בעיבוד זמן"

        # --- Save to TXT ---
        try:
            os.makedirs(os.path.dirname(txt_p), exist_ok=True)
            with open(txt_p, 'a', encoding='utf-8-sig') as f:
                f.write(date_str + "\n")
                # Use the full message string if available, fallback to others
                message_to_write = attrs.get("full_message_str", attrs.get("alert_alt", attrs.get("text_status", "אין פרטים")))
                f.write(message_to_write + "\n")
        except PermissionError as e:
            self._log(f"Permission error writing TXT history to {txt_p}: {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing TXT history to {txt_p}: {e}", level="ERROR")

        # --- Save to CSV ---
        try:
            self.create_csv_header_if_needed() # Ensure header exists before appending

            csv_data = [
                str(alert_id),
                day_name_he,
                fmt_date,
                fmt_time,
                attrs.get('prev_title', 'N/A'),
                attrs.get('prev_data_count', 0),
                attrs.get('prev_areas_alert_str', ''),
                attrs.get('prev_alerts_cities_str', ''),
                attrs.get('prev_desc', ''),
                attrs.get('prev_alerts_count', 0) 
            ]

            output = StringIO()
            writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
            writer.writerow(csv_data)
            line = output.getvalue().strip() # Get the formatted line
            output.close()

            os.makedirs(os.path.dirname(csv_p), exist_ok=True)
            with open(csv_p, 'a', encoding='utf-8-sig', newline='') as f:
                f.write(line + "\n")

            self._last_saved_alert_id = alert_id # Mark this ID as saved

        except PermissionError as e:
            self._log(f"Permission error writing CSV history to {csv_p}: {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing CSV history to {csv_p}: {e}", level="ERROR", exc_info=True)

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

            # Adjust logging verbosity based on file type and content
            log_level = "DEBUG"
            if "latest" in path and num_features > 0: log_level = "INFO" # Log active alerts clearly
            elif "24h" in path and num_features > 0: log_level = "DEBUG" # History less critical
            elif "latest" in path and num_features == 0: log_level = "DEBUG" # Idle state less verbose

            # Log only if there are features or it's the history file (to confirm it updated)
            if num_features > 0 or "24h" in path :
                self._log(f"Successfully wrote GeoJSON ({num_features} features) to: {path}", level=log_level)

        except PermissionError as e:
            self._log(f"PERMISSION ERROR writing GeoJSON to {path}: {e}. Check permissions.", level="ERROR")
        except TypeError as e: # Catch non-serializable data
            self._log(f"Error writing GeoJSON to {path}: Data not JSON serializable - {e}", level="ERROR")
        except Exception as e:
            self._log(f"Error writing GeoJSON to {path}: {e}", level="ERROR", exc_info=True)

# ----------------------------------------------------------------------
# Main AppDaemon Class: Red_Alerts_Israel 
# ----------------------------------------------------------------------
class Red_Alerts_Israel(Hass):

    async def initialize(self):
        """Initializes the AppDaemon application."""
        self.log("--------------------------------------------------")
        self.log("       Initializing Red Alerts Israel App")
        self.log("--------------------------------------------------")
        #self.set_namespace("red_alert")
        global _IS_RAI_RUNNING
        if _IS_RAI_RUNNING:
            self.log("Red_Alerts_Israel is already running – skipping duplicate initialize.", level="WARNING")
            return
        _IS_RAI_RUNNING = True
        atexit.register(self._cleanup_on_exit) # Register cleanup function

        # --- Configuration Loading & Validation ---
        self.interval = self.args.get("interval", 5)
        self.timer_duration = self.args.get("timer", 120)
        self.save_2_file = self.args.get("save_2_file", True)
        self.sensor_name = self.args.get("sensor_name", "red_alert")
        self.city_names_config = self.args.get("city_names", [])
        self.hours_to_show = self.args.get("hours_to_show", 12) # Default history to 12 hours
        self.mqtt_topic = self.args.get("mqtt", False)
        self.ha_event = self.args.get("event", True)

        # Validate config types
        if not isinstance(self.interval, (int, float)) or self.interval <= 1: # Interval should be > 1 sec
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
            #self.log(f"File Paths: www={www_base}, lamas={self.file_paths['lamas_local']}", level="DEBUG")
            self._verify_www_writeable(www_base) # Verify write access
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
            'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Cache-Control': 'no-cache' # Try to avoid caching
        }
        timeout = ClientTimeout(total=15, connect=5, sock_connect=5, sock_read=10)
        connector = TCPConnector(limit_per_host=5, keepalive_timeout=30, enable_cleanup_closed=True)
        self.session = aiohttp.ClientSession(
            connector=connector, timeout=timeout, headers=headers, trust_env=False
        )

        api_urls = {
            "live":         f"https://www.oref.org.il/WarningMessages/alert/alerts.json", #?v={int(time.time())}", # Add timestamp to try and bypass cache
            "history":      f"https://www.oref.org.il/WarningMessages/alert/History/AlertsHistory.json", #?v={int(time.time())}",
            "lamas_github": "https://raw.githubusercontent.com/idodov/RedAlert/main/apps/red_alerts_israel/lamas_data.json"
        }
        self.api_client = OrefAPIClient(self.session, api_urls, self.log)

        # --- State Variables ---
        self.alert_sequence_count = 0
        self.no_active_alerts_polls = 0
        self.last_alert_time = None
        self.last_processed_alert_id = None # Initialize tracker for unique alerts
        self.window_alerts_grouped = {} # Stores alerts grouped by title/area within the current window
        self.prev_alert_final_attributes = None # Stores the full attribute set of the last update
        self.cities_past_window_std = set() # Stores all unique standardized cities for the current window
        self.test_alert_cycle_flag = 0 # 0: inactive, 1: active test window
        self.test_alert_start_time = 0
        self._poll_running = False
        self._terminate_event = asyncio.Event()
        self.last_active_payload_details = None

        # --- Helper Class Instantiation ---
        self.lamas_manager    = LamasDataManager(
                                self.file_paths["lamas_local"],
                                api_urls["lamas_github"], self.api_client, self.log
                            )
        self.alert_processor  = AlertProcessor(self.lamas_manager, ICONS_AND_EMOJIS, self.log)
        # Ensure HistoryManager gets the timer_duration for its deduplication
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
            _IS_RAI_RUNNING = False # Clear running flag
            await self.terminate() # Attempt graceful shutdown
            return # Stop initialization

        # --- Validate Configured City Names ---
        self._validate_configured_cities()

        # --- Initialize HA Entities and Load Initial Data ---
        #self.log("Ensuring HA entities exist and loading initial data...")
        await self._initialize_ha_sensors()
        await self._load_initial_data() # Loads history, sets initial 'off' states, saves initial GeoJSON

        # --- Register Test Boolean Listener ---
        try:
            self.listen_state(self._test_boolean_callback, self.activate_alert, new="on")
            self.log(f"Listening for test activation on {self.activate_alert}", level="INFO")
        except Exception as e:
            self.log(f"Error setting up listener for {self.activate_alert}: {e}", level="ERROR")


        # --- Start Polling Loop ---
        self.log("Scheduling first API poll.")
        self.run_in(self._poll_alerts_callback_sync, 5) # Start polling after 5 seconds

        # Update sensor status to running 
        running_attrs = {'script_status': 'running', 'timestamp': datetime.now().isoformat()}
        try:
            # Fetch current state to merge attributes if possible
            current_main_state = await self.get_state(self.main_sensor, attribute="all")
            if current_main_state and 'attributes' in current_main_state:
                # Preserve existing attributes unless they should be overwritten
                base_attrs = current_main_state.get('attributes', {})
                # Avoid overwriting important state if sensor was somehow active
                if current_main_state.get('state', 'off') == 'off':
                    merged_attrs = {**base_attrs, **running_attrs}
                else:
                    merged_attrs = {**base_attrs, 'script_status': 'running'} # Just update status
                await self.set_state(self.main_sensor, state=current_main_state.get('state', 'off'), attributes=merged_attrs)
            else:
                # Fallback if state couldn't be fetched or has no attributes
                await self.set_state(self.main_sensor, state='off', attributes=running_attrs)
        except Exception as e:
            self.log(f"Error setting running status attribute: {e}", level="WARNING")

        self.log("--------------------------------------------------")
        self.log("  Initialization Complete. Monitoring Red Alerts.")
        self.log("--------------------------------------------------")

    def _get_www_path(self):
        """Tries to determine the Home Assistant www path."""
        # Prefer HA config dir if available via AppDaemon context
        ha_config_dir_options = ["/homeassistant", "/config", "/usr/share/hassio/homeassistant", "/root/config"]
        for d in ha_config_dir_options:
            www_path = os.path.join(d, "www")
            if os.path.isdir(www_path):
                return www_path

        # Fallback to standard HA path
        ha_config_dir = getattr(self, 'config_dir', None)
        if ha_config_dir and os.path.isdir(os.path.join(ha_config_dir, 'www')):
            self.log(f"Using www path from HA config dir: {os.path.join(ha_config_dir, 'www')}", level="INFO")
            return os.path.join(ha_config_dir, 'www')

        # Last resort: relative to AppDaemon config dir? (Less reliable)
        ad_config_dir = getattr(self, 'config_dir', script_directory) # Use script dir if AD config unknown
        potential_ha_config = os.path.dirname(ad_config_dir) # Guess HA config is parent of AD config
        www_path_guess = os.path.join(potential_ha_config, "www")
        if os.path.isdir(www_path_guess):
            self.log(f"Using guessed www path relative to AppDaemon config: {www_path_guess}", level="WARNING")
            return www_path_guess

        self.log("Could not reliably determine www path.", level="ERROR")
        return None

    def _verify_www_writeable(self, www_base):
        """Checks if the www directory is writeable and logs errors."""
        if not self.save_2_file: return # Skip if saving is disabled
        try:
            os.makedirs(www_base, exist_ok=True)
            test_file = os.path.join(www_base, f".{self.sensor_name}_write_test_{random.randint(1000,9999)}")
            with open(test_file, 'w') as f: f.write("test")
            os.remove(test_file)
        except PermissionError as e:
            self.log(f"PERMISSION ERROR creating/writing to www directory '{www_base}': {e}. Check permissions for AppDaemon user/process. Disabling file saving.", level="ERROR")
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
        if not self.city_names_config: # Already checked it's a list
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
            self.log(f"Configured city_names validation complete. {len(self.city_names_self_std)} unique valid names processed. Some warnings issued (see above).", level="WARNING")

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
                return # Don't poll or schedule next if terminating

            await self.poll_alerts()

        except Exception as e:
            self.log(f"CRITICAL ERROR during poll_alerts execution: {e.__class__.__name__} - {e}", level="CRITICAL", exc_info=True)
            try:
                await self.set_state(self.main_sensor, attributes={'script_status': 'error', 'last_error': f"{e.__class__.__name__}: {e}", 'timestamp': datetime.now().isoformat()})
            except Exception as set_err:
                self.log(f"Error setting error status on sensor: {set_err}", level="ERROR")
        finally:
            self._poll_running = False # Release the lock
            end_time = time.monotonic()
            duration = end_time - start_time

            # Check again if termination is requested before scheduling next
            if not self._terminate_event.is_set():
                self.run_in(self._poll_alerts_callback_sync, self.interval)
            else:
                self.log("Termination signal received after poll, not scheduling next.", level="INFO")

    def terminate(self):
        """
        Synchronous callback invoked by AppDaemon when it’s shutting down.
        Schedules the async termination routine so we can still await Home Assistant calls.
        """
        self.log("AppDaemon shutdown detected: scheduling async termination...", level="INFO")

        # Wake up any poll waiting on _terminate_event
        if hasattr(self, "_terminate_event"):
            try:
                self._terminate_event.set()
            except Exception:
                pass

        # Schedule the real async cleanup
        self.create_task(self._async_terminate())

    async def _async_terminate(self):
        """
        Gracefully shut down: update your sensors to 'terminated', close HTTP session, etc.
        """
        self.log("--------------------------------------------------")
        self.log("Async Terminate: cleaning up Red Alerts Israel App")
        self.log("--------------------------------------------------")
        global _IS_RAI_RUNNING

        if not _IS_RAI_RUNNING:
            return

        # Prevent further polls
        _IS_RAI_RUNNING = False
        if hasattr(self, "_terminate_event"):
            self._terminate_event.set()

        # Give one iteration back to the loop
        await asyncio.sleep(0)

        # Mark your two binary_sensors as off/terminated
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

        # Finally, close your aiohttp session if it’s still open
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
        # If we’re not marked running, nothing to do
        if not _IS_RAI_RUNNING:
            return

        log_func = getattr(self, 'log', print)
        log_func("atexit: Script was running, attempting final cleanup steps.", level="INFO")
        _IS_RAI_RUNNING = False

        try:
            # Try to get the active event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # 1) wake up any poll that’s waiting on _terminate_event
                loop.call_soon_threadsafe(self._terminate_event.set)

                # 2) schedule the terminate() coroutine to actually run
                loop.call_soon_threadsafe(asyncio.create_task, self.terminate())
            else:
                # No loop to schedule on — run terminate() directly
                try:
                    asyncio.run(self.terminate())
                except Exception as e2:
                    log_func(f"atexit: Error running terminate() directly: {e2}", level="WARNING")

        except Exception as e:
            log_func(f"atexit: Error accessing/signalling loop: {e}", level="WARNING")



    def _parse_datetime_str(self, ds: str):
        """Delegates datetime parsing to the HistoryManager for consistency."""
        # Ensure history_manager exists before calling
        if hasattr(self, 'history_manager'):
            return self.history_manager._parse_datetime_str(ds)
        else:
            self.log("HistoryManager not initialized when parsing datetime.", level="ERROR")
            return None 

    def _is_iso_format(self, ds: str) -> str:
        """Parses a datetime string and returns it in ISO format with microseconds, or now() if invalid."""
        dt = self._parse_datetime_str(ds)
        now_fallback = datetime.now().isoformat(timespec='microseconds')
        if dt:
            try:
                return dt.isoformat(timespec='microseconds')
            except Exception as e: # Catch potential errors during formatting
                self.log(f"Error formatting datetime '{dt}' to ISO: {e}. Falling back to current time.", level="WARNING")
                return now_fallback
        else:
            return now_fallback

    async def _initialize_ha_sensors(self):
        """Ensures required HA entities exist with default states/attributes."""
        now_iso = datetime.now().isoformat(timespec='microseconds')

        # Attributes for idle state (used for init and reset)
        idle_attrs = {
            "active_now": False, "special_update": False, "id": 0, "cat": 0, "title": "אין התרעות", "desc": "טוען נתונים...",
            "areas": "", "cities": [], "data": "", "data_count": 0, "duration": 0,
            "icon": "mdi:timer-sand", "emoji": "⏳", "alerts_count": 0,
            "last_changed": now_iso,
            "my_cities": sorted(list(set(self.city_names_config))),
            "prev_cat": 0, "prev_title": "", "prev_desc": "", "prev_areas": "",
            "prev_cities": [], "prev_data": "", "prev_data_count": 0, "prev_duration": 0,
            "prev_last_changed": now_iso, "prev_alerts_count": 0,
            "alert_wa": "", "alert_tg": "", # Initialize WA/TG attributes
            "script_status": "initializing"
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
                else:
                    # Set initial state even if exists to ensure consistency on restart
                    init_tasks.append(self.set_state(entity_id, state=state, attributes=attrs))

            except Exception as e:
                self.log(f"Error preparing init task for entity {entity_id}: {e}", level="WARNING", exc_info=True)

        if init_tasks:
            results = await asyncio.gather(*init_tasks, return_exceptions=True)
            for i, res in enumerate(results):
                if isinstance(res, Exception):
                    self.log(f"Error initializing entity task {i}: {res}", level="ERROR")

        # Initialize input_text separately
        try:
            text_entity_exists = await self.entity_exists(self.main_text)
            text_attrs = {
                "min": 0, "max": 255, "mode": "text",
                "friendly_name": f"{self.sensor_name} Summary",
                "icon": "mdi:timer-sand"
            }
            if not text_entity_exists:
                self.log(f"Entity {self.main_text} not found. Creating with initial text 'טוען...'.", level="INFO")
                # Create with placeholder text
                await self.set_state(self.main_text, state="טוען...", attributes=text_attrs)
            # --- Do NOT update state here if it exists ---

            # Initialize test boolean
            bool_entity_exists = await self.entity_exists(self.activate_alert)
            bool_attrs = {"friendly_name": f"{self.sensor_name} Test Trigger"}
            if not bool_entity_exists:
                self.log(f"Entity {self.activate_alert} not found. Creating.", level="INFO")
                await self.set_state(self.activate_alert, state="off", attributes=bool_attrs)
            else:
                # Ensure it's off on restart
                await self.set_state(self.activate_alert, state="off", attributes=bool_attrs)


        except Exception as e:
            self.log(f"Error checking/initializing input/boolean entities: {e}", level="WARNING", exc_info=True)

        self.log("HA sensor entities initialization check complete.")

    async def _load_initial_data(self):
        """Loads history, gets backup, sets initial 'off' states with merged data, and saves initial files."""
        #self.log("Loading initial data (history & backup)...")

        # 1. Load historical alert data
        await self.history_manager.load_initial_history(self.api_client)
        # Get attributes AFTER loading
        history_attrs = self.history_manager.get_history_attributes()

        # 2. Try to load the last state from the JSON backup
        backup = self.file_manager.get_from_json()
        prev_attrs_formatted = {}
        if backup:
            prev_attrs_formatted = self._format_backup_data_as_prev(backup)
        else:
            # Define default prev attributes here
            prev_attrs_formatted = {
                "prev_cat": 0, "prev_special_update": False, "prev_title": "", "prev_desc": "", "prev_areas": "",
                "prev_cities": [], "prev_data": "", "prev_data_count": 0, "prev_duration": 0,
                "prev_last_changed": datetime.now().isoformat(timespec='microseconds'), "prev_alerts_count": 0
            }

        # 3. Define the initial 'off' state attributes for main/city sensors
        now_iso = datetime.now().isoformat(timespec='microseconds')
        initial_state_attrs = {
            "active_now": False, "special_update": False, "id": 0, "cat": 0, "title": "אין התרעות", "desc": "שגרה",
            "areas": "", "cities": [], "data": "", "data_count": 0, "duration": 0,
            "icon": "mdi:check-circle-outline", "emoji": "✅", "alerts_count": 0,
            "last_changed": now_iso,
            "my_cities": sorted(list(set(self.city_names_config))),
            **prev_attrs_formatted, # Merge the formatted previous state attributes
            "script_status": "running" # Update status after loading
        }

        # 4. Update main and city sensors with the initial 'off' state
        try:
            tasks = [
                # --- Do NOT update input_text here ---
                self.set_state(self.main_sensor, state="off", attributes=initial_state_attrs),
                self.set_state(self.city_sensor, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.main_sensor_pre_alert, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.city_sensor_pre_alert, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.main_sensor_active_alert, state="off", attributes=initial_state_attrs.copy()),
                self.set_state(self.city_sensor_active_alert, state="off", attributes=initial_state_attrs.copy()),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.log(f"Error setting initial 'off' states: {e}", level="WARNING", exc_info=True)

        # 5. Update the dedicated history sensors using the loaded history_attrs
        try:
            count_cities = len(history_attrs.get("cities_past_24h", []))
            count_alerts = len(history_attrs.get("last_24h_alerts", []))

            tasks = []
            hist_cities_attrs = {
                "cities_past_24h": history_attrs["cities_past_24h"],
                "script_status": "running" # Add status
            }
            tasks.append(self.set_state(self.history_cities_sensor, state=str(count_cities), attributes=hist_cities_attrs))

            history_list_attr = {
                "last_24h_alerts": history_attrs["last_24h_alerts"],
                "script_status": "running" # Add status
            }

            tasks.append(self.set_state(self.history_list_sensor, state=str(count_alerts), attributes=history_list_attr))

            history_group_attr = {
                "last_24h_alerts_group": history_attrs["last_24h_alerts_group"],
                "script_status": "running" # Add status
            }

            tasks.append(self.set_state(self.history_group_sensor, state=str(count_alerts), attributes=history_group_attr))

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                #self.log("Updated dedicated history sensors with loaded data.")
            else:
                self.log("No history update tasks were executed.", level="WARNING")

        except Exception as e:
            self.log(f"Error setting dedicated history sensor states in _load_initial_data: {e}", level="WARNING", exc_info=True)

        # 6. Save initial files (GeoJSON, ensure CSV header)
        if self.save_2_file:
            try:
                # Create empty latest file
                initial_latest_attrs = {
                    "title": "אין התרעות", "desc": "שגרה", "cat": 0, "cities": [],
                    "last_changed": datetime.now().isoformat(timespec='microseconds')
                }
                await self._save_latest_geojson(initial_latest_attrs)
                # Create history file based on loaded history
                await self._save_history_geojson(history_attrs) # Pass the loaded history attributes
                # Ensure CSV header exists
                self.file_manager.create_csv_header_if_needed()
            except Exception as file_err:
                self.log(f"Error during initial file creation: {file_err}", level="ERROR", exc_info=True)

        self.log("Initial data loading and state setting complete.")


    async def _process_active_alert(self, data, is_test=False):
        """
        Processes incoming alert data (real or test), updates state, history, and files.
        """
        alert_id_from_data = data.get("id", "N/A") # Get ID for logging
        log_prefix = "[Test Alert]" if is_test else "[Real Alert]"

        now_dt = datetime.now()
        now_iso = now_dt.isoformat(timespec='microseconds')

        # --- 1. Parse Incoming Data ---
        try:
            cat_str = data.get("cat", "1")
            cat = int(cat_str) if cat_str.isdigit() else 1
            aid = int(data.get("id", 0))
            desc = data.get("desc", "")
            title = data.get("title", "התרעה")
            raw_payload_cities = data.get("data", [])
            payload_cities_raw = []
            if isinstance(raw_payload_cities, str):
                payload_cities_raw = [c.strip() for c in raw_payload_cities.split(',') if c.strip()]
            elif isinstance(raw_payload_cities, list):
                payload_cities_raw = [str(city) for city in raw_payload_cities if isinstance(city, (str, int))]
            #stds_this_payload = set(standardize_name(n) for n in payload_cities_raw if n)
            #self.log(f"{log_prefix} Parsed Payload: ID={aid}, Cat={cat}, Title='{title}', Cities(Std)={len(stds_this_payload)}", level="DEBUG")

            # ===> FILTERING LOGIC <===
            forbidden_strings = ["בדיקה", "תרגיל"]
            filtered_cities_raw = []
            for city_name in payload_cities_raw:
                # Check if any forbidden string is present in the current city name
                if not any(forbidden in city_name for forbidden in forbidden_strings):
                    filtered_cities_raw.append(city_name)
                else: # Optional: Log if a city was filtered out
                    self.log(f"{log_prefix} Filtering out city: '{city_name}' due to forbidden string.", level="INFO")

            # If ALL cities were filtered out, skip processing this alert entirely
            if not filtered_cities_raw and payload_cities_raw: # Check if original list had cities but filtered list is empty
                self.log(f"{log_prefix} All cities in payload ID {data.get('id', 'N/A')} were filtered out. Skipping further processing for this payload.", level="INFO")
                return # Stop processing this specific alert payload

            stds_this_payload = set(standardize_name(n) for n in filtered_cities_raw if n)


        except Exception as e:
            self.log(f"{log_prefix} CRITICAL Error parsing alert data payload: {e}. Data: {data}", level="CRITICAL", exc_info=True)
            return # Stop processing this payload

        # ===> Check for identical payload <===
        if self.last_active_payload_details is not None and not is_test: # Apply only to real alerts for now
            is_identical = (
                self.last_active_payload_details['id'] == aid and
                self.last_active_payload_details['cat'] == cat and
                self.last_active_payload_details['title'] == title and
                self.last_active_payload_details['desc'] == desc and
                self.last_active_payload_details['stds'] == stds_this_payload # Compare sets
            )

            if is_identical:
                self.last_alert_time = time.time()
                return

        self.last_active_payload_details = {
            'id': aid,
            'cat': cat,
            'title': title,
            'desc': desc,
            'stds': stds_this_payload
        }

        # --- Check if sensor was previously off ---
        sensor_was_off = await self.get_state(self.main_sensor) == "off"
        if sensor_was_off:
            self.log(f"{log_prefix} Sensor was 'off'. Starting new alert window for ID: {aid}.", level="INFO")
            self.cities_past_window_std = set()
            self.alert_sequence_count = 0
            self.window_alerts_grouped = {}
            if self.file_manager: self.file_manager.clear_last_saved_id()
            self.history_manager.clear_poll_tracker()
            self.last_processed_alert_id = None
            self.last_active_payload_details = None


        # --- 2. Update History ---
        # Call update first, then get attributes
        self.history_manager.clear_poll_tracker()
        self.history_manager.update_history(title, stds_this_payload)
        # Get the latest history attributes AFTER updating
        hist_attrs = self.history_manager.get_history_attributes()
        # Ensure hist_attrs is valid for later steps
        if not isinstance(hist_attrs, dict):
            self.log(f"{log_prefix} Failed to get valid history attributes after update. Using fallback.", level="ERROR")
            hist_attrs = {"last_24h_alerts": [], "cities_past_24h": []}


        # --- 3. Accumulate Overall Cities ---
        newly_added_cities_overall = stds_this_payload - self.cities_past_window_std
        if newly_added_cities_overall:
            #self.log(f"{log_prefix} Adding {len(newly_added_cities_overall)} new unique cities to window (overall).", level="DEBUG")
            self.cities_past_window_std.update(newly_added_cities_overall)

        # --- 3b. Populate Grouped Window Data ---
        unknown_cities_logged_grouped = set()
        current_payload_title = title
        alert_group = self.window_alerts_grouped.setdefault(current_payload_title, {})
        populated_count_grouped = 0
        for std in stds_this_payload:
            det = self.lamas_manager.get_city_details(std)
            area = DEFAULT_UNKNOWN_AREA
            orig_city_name = std
            if det:
                area = det.get("area", DEFAULT_UNKNOWN_AREA)
                orig_city_name = det.get("original_name", std)
            elif std not in unknown_cities_logged_grouped:
                # Reduce noise: Log only once per window if Lamas is missing entries
                # self.log(f"{log_prefix} GroupedWindowData: City '{std}' not found. Area='{area}'.", level="WARNING")
                unknown_cities_logged_grouped.add(std)
            area_group = alert_group.setdefault(area, set())
            if orig_city_name not in area_group:
                area_group.add(orig_city_name)
                populated_count_grouped += 1
        if populated_count_grouped > 0:
            self.log(f"{log_prefix} Updated window_alerts_grouped for title '{current_payload_title}' with {populated_count_grouped} new entries.", level="DEBUG")

        # --- 4. Update Window State Variables ---
        self.alert_sequence_count += 1

        # --- 5. Reset the Idle Timer ---
        self.last_alert_time = time.time()

        # --- 6. Process Data for HA State ---
        try:
            info = self.alert_processor.process_alert_window_data(
                category=cat,
                title=title,
                description=desc,
                window_std_cities=self.cities_past_window_std, # Use accumulated set
                window_alerts_grouped=self.window_alerts_grouped # Pass grouped data
            )
        except Exception as e:
            self.log(f"{log_prefix} Error calling alert_processor.process_alert_window_data: {e}", level="CRITICAL", exc_info=True)
            # Create a minimal fallback info structure
            info = {
                "areas_alert_str": "Error", "cities_list_sorted": list(self.cities_past_window_std), "data_count": len(self.cities_past_window_std),
                "alerts_cities_str": "Error processing cities", "icon_alert": "mdi:alert-circle-outline", "icon_emoji": "🆘",
                "duration": 0, "text_wa_grouped": "שגיאה בעיבוד ההתרעה", "text_tg_grouped": "שגיאה בעיבוד ההתרעה",
                "text_status": "שגיאה בעיבוד", "full_message_str": "שגיאה", "alert_txt": "שגיאה",
                "full_message_list": [], "input_text_state": "שגיאה"
            }

        # --- 7. Get Previous State Attributes ---
        prev_state_attrs = {}
        try:
            prev_ha_state_data = await self.get_state(self.main_sensor, attribute="all")
            if prev_ha_state_data and 'attributes' in prev_ha_state_data:
                # Make a copy to avoid modifying the cached state? Or just read needed values.
                prev_state_attrs = prev_ha_state_data['attributes']
        except Exception as e:
            self.log(f"{log_prefix} Error fetching previous state attributes: {e}", level="WARNING")
        # Ensure essential prev keys exist, even if empty/default
        default_prev = {
            "cat": 0, "title": "", "desc": "", "areas": "", "cities": [], "data": "",
            "data_count": 0, "duration": 0, "alerts_count": 0, "last_changed": now_iso
        }
        for k, v in default_prev.items():
            prev_state_attrs.setdefault(k, v)


        # --- 8. Construct Final Attributes ---
        # Use info generated in step 6 and prev_state_attrs from step 7
        #special_update = True if cat == 13 else False
        # בדקות הקרובות צפויות להתקבל התרעות באזורך
        special_update = True if "בדקות הקרובות" in title or "עדכון" in title or "שהייה בסמיכות" in title else False

        final_attributes = {
            "active_now": True,
            "special_update": special_update, # Is it advanced alert
            "id": aid, # Latest ID
            "cat": cat, # Latest category
            "title": title, # Latest title
            "desc": desc, # Latest description
            "areas": info.get("areas_alert_str", ""), # Accumulated areas string
            "cities": info.get("cities_list_sorted", []), # Accumulated cities list
            "data": info.get("alerts_cities_str", ""), # Accumulated cities string (truncated if needed)
            "data_count": info.get("data_count", 0), # Accumulated unique city count
            "duration": info.get("duration", 0), # Latest duration
            "icon": info.get("icon_alert", "mdi:alert"), # Latest icon
            "emoji": info.get("icon_emoji", "❗"), # Latest emoji
            "alerts_count": self.alert_sequence_count, # Window sequence count
            "last_changed": now_iso, # Current update time
            "my_cities": sorted(list(set(self.city_names_config))), # Static config list
            "alert": info.get("text_status", ""), # Generated status text
            "alert_alt": info.get("full_message_str", ""), # Generated detailed text
            "alert_txt": info.get("alert_txt", ""), # Generated basic text
            "alert_wa": info.get("text_wa_grouped", ""), # Grouped WA message
            "alert_tg": info.get("text_tg_grouped", ""), # Grouped TG message
            # Previous state values:
            "prev_cat": prev_state_attrs.get("cat"),
            "prev_title": prev_state_attrs.get("title"),
            "prev_desc": prev_state_attrs.get("desc"),
            "prev_areas": prev_state_attrs.get("areas"),
            "prev_cities": prev_state_attrs.get("cities"),
            "prev_data": prev_state_attrs.get("data"),
            "prev_data_count": prev_state_attrs.get("data_count"),
            "prev_duration": prev_state_attrs.get("duration"),
            "prev_alerts_count": prev_state_attrs.get("alerts_count"),
            "prev_last_changed": prev_state_attrs.get("last_changed"),
            "prev_special_update": prev_state_attrs.get("special_update"),
            "prev_alert_wa": prev_state_attrs.get("alert_wa"),
            "prev_alert_tg": prev_state_attrs.get("alert_tg"),
            "prev_icon": prev_state_attrs.get("icon"),
            "prev_emoji": prev_state_attrs.get("emoji"),
            "script_status": "running"
        }

        if special_update:
            final_attributes["icon"] = "mdi:Alarm-Light-Outline"
            final_attributes["emoji"] = "🔜"

        # --- 9. Check Attribute Size Limit ---
        try:
            if len(final_attributes.get("data", "")) > self.alert_processor.max_attr_len:
                final_attributes["data"] = self.alert_processor._check_len(final_attributes["data"], final_attributes.get("data_count", 0), final_attributes.get("areas", ""), self.alert_processor.max_attr_len, "Final Data Attr Re-Check")
            # Repeat for alert_wa, alert_tg if needed, though AlertProcessor should handle this.
        except Exception as size_err:
            self.log(f"{log_prefix} Error during final attribute size re-check: {size_err}", level="ERROR")

        # --- 10. Store Final Attributes for potential next 'prev_' state ---
        # Store this state BEFORE updating HA, so the *next* alert sees this as previous
        self.prev_alert_final_attributes = final_attributes.copy()

        # --- 11. Determine City Sensor State ---
        city_sensor_should_be_on = bool(self.cities_past_window_std.intersection(self.city_names_self_std))
        if is_test and bool(self.city_names_self_std): city_sensor_should_be_on = True # Force on for test if cities configured
        city_state_final = "on" if city_sensor_should_be_on else "off"

        # --- 12. Update Home Assistant States ---
        try:
            await self._update_ha_state(
                main_state="on",
                city_state=city_state_final,
                text_state=info.get("input_text_state", "התרעה"), # Use state from 'info'
                attributes=final_attributes, # Pass the fully constructed attributes
                text_icon=info.get("icon_alert", "mdi:alert") # Use icon from 'info'
            )
        except Exception as e:
            self.log(f"{log_prefix} Error occurred during _update_ha_state call: {e}", level="ERROR", exc_info=True)

        # --- 13. Update Dedicated History Sensors ---
        # Use hist_attrs collected in Step 2
        try:
            count_cities = len(hist_attrs.get("cities_past_24h", []))
            count_alerts = len(hist_attrs.get("last_24h_alerts", []))
            tasks = []

            hist_cities_attrs = {
                "cities_past_24h": hist_attrs.get("cities_past_24h", []),
                "script_status": "running" # <-- Fix: Added script_status
            }
            tasks.append(self.set_state(self.history_cities_sensor, state=str(count_cities), attributes=hist_cities_attrs))

            history_list_attr = {
                "last_24h_alerts": hist_attrs.get("last_24h_alerts", []),
                "script_status": "running"
            }

            tasks.append(self.set_state(self.history_list_sensor, state=str(count_alerts), attributes=history_list_attr))


            history_group_attr = {
                "last_24h_alerts_group": hist_attrs.get("last_24h_alerts_group", {}),
                "script_status": "running"
            }

            tasks.append(self.set_state(self.history_group_sensor, state=str(count_alerts), attributes=history_group_attr))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

        except Exception as e:
            self.log(f"{log_prefix} Unexpected error setting history sensor states: {e}", level="WARNING", exc_info=True)


        # --- 14. Save Backup JSON & Update GeoJSON Files (Optimized) ---
        if self.save_2_file:
            # --- JSON Backup & Latest GeoJSON (Only if ID changed) ---
            current_alert_id = aid # Use the parsed ID for this payload
            if current_alert_id != self.last_processed_alert_id:
                # Prepare backup data using final_attributes
                backup_data = {
                    "id": final_attributes.get("id"),
                    "cat": str(final_attributes.get("cat")),
                    "title": final_attributes.get("title"),
                    "data": final_attributes.get("cities", []), # Backup uses 'cities' list
                    "desc": final_attributes.get("desc"),
                    "alertDate": final_attributes.get("last_changed"), # Use consistent time
                    "last_changed": final_attributes.get("last_changed"),
                    "alerts_count": final_attributes.get("alerts_count")
                }
                try:
                    self.file_manager.save_json_backup(backup_data)
                except Exception as e:
                    self.log(f"{log_prefix} Error during save_json_backup call: {e}", level="ERROR", exc_info=True)

                # Save Latest GeoJSON using final_attributes
                try:
                    await self._save_latest_geojson(final_attributes)
                except Exception as e:
                    self.log(f"{log_prefix} Error during _save_latest_geojson call: {e}", level="ERROR", exc_info=True)

                # Update the last processed ID tracker
                self.last_processed_alert_id = current_alert_id

            # --- History GeoJSON (Update every time active alert processed) ---
            try:
                # Pass hist_attrs collected in Step 2
                await self._save_history_geojson(hist_attrs)
            except Exception as e:
                self.log(f"{log_prefix} Error during _save_history_geojson call: {e}", level="ERROR", exc_info=True)

        # --- 15. Fire MQTT & Home Assistant Event ---
        event_data_dict = {
            "id": aid, "category": cat, "title": title,
            "cities": info.get("cities_list_sorted", []), # Use consistent accumulated list
            "areas": info.get("areas_alert_str", ""), # Use consistent accumulated areas
            "description": desc, "timestamp": now_iso,
            "alerts_count": self.alert_sequence_count, # Window alert count
            "is_test": is_test
        }
        if self.mqtt_topic:
            mqtt_base_topic = self.mqtt_topic if isinstance(self.mqtt_topic, str) and self.mqtt_topic.strip() else f"home/{self.sensor_name}"
            mqtt_topic_name = f"{mqtt_base_topic}/event"
            try:
                payload_to_publish = json.dumps(event_data_dict, ensure_ascii=False)
                await self.call_service("mqtt/publish", topic=mqtt_topic_name, payload=payload_to_publish, qos=0, retain=False)
            except Exception as e: self.log(f"{log_prefix} Error publishing MQTT event to {mqtt_topic_name}: {e}", level="ERROR")
        if self.ha_event:
            try:
                ha_event_name = f"{self.sensor_name}_event"
                await self.fire_event(ha_event_name, **event_data_dict) # Use await for fire_event
            except Exception as e: self.log(f"{log_prefix} Error firing HA event '{ha_event_name}': {e}", level="ERROR")

        self.log(f"{log_prefix} Finished processing alert ID: {aid}. Window payloads: {self.alert_sequence_count}, Total unique cities in window: {len(self.cities_past_window_std)}.", level="INFO" if not is_test else "WARNING")


    async def _check_reset_sensors(self):
        """
        Checks if the idle timer has expired and resets sensors if needed,
        saving history and updating files appropriately.
        """
        now = time.time()
        log_prefix = "[Sensor Reset Check]"

        # Check if main sensor exists before getting state
        main_sensor_exists = await self.entity_exists(self.main_sensor)
        if not main_sensor_exists:
            self.log(f"{log_prefix} Main sensor {self.main_sensor} not found. Cannot check state.", level="WARNING")
            return

        main_sensor_current_state = "unknown"
        try:
            main_sensor_current_state = await self.get_state(self.main_sensor)
        except Exception as e:
            self.log(f"{log_prefix} Error getting main sensor state: {e}. Assuming 'unknown'.", level="WARNING")

        # If already off and timer not active, just clear prev attributes if they linger
        if main_sensor_current_state == "off" and self.last_alert_time is None:
            if self.prev_alert_final_attributes:
                #self.log(f"{log_prefix} Sensor 'off', no timer active. Clearing stale prev_alert_final_attributes.", level="DEBUG")
                self.prev_alert_final_attributes = None
            return

        # If timer isn't running, nothing to reset
        if self.last_alert_time is None:
            return

        # Check timer expiration and confirmation polls
        time_since_last_alert = now - self.last_alert_time
        timer_expired = time_since_last_alert > self.timer_duration
        # Require at least one poll confirming no active alerts
        confirmed_idle = self.no_active_alerts_polls > 0
        can_reset = timer_expired and confirmed_idle

        if can_reset:
            self.log(f"{log_prefix} Alert timer expired ({time_since_last_alert:.1f}s > {self.timer_duration}s) & confirmed idle ({self.no_active_alerts_polls} poll(s)). Resetting sensors.")

            # --- 1. Save History Files (TXT/CSV) ---
            if self.save_2_file and self.file_manager: # Check file_manager exists
                if self.prev_alert_final_attributes:
                    last_alert_id = self.prev_alert_final_attributes.get('id', 'N/A')
                    self.log(f"{log_prefix} Saving history files (TXT/CSV) for last window (ID: {last_alert_id})...")
                    try:
                        # Pass the last known attributes from the active window
                        self.file_manager.save_history_files(self.prev_alert_final_attributes)
                    except Exception as e:
                        self.log(f"{log_prefix} Error during save_history_files: {e}", level="ERROR", exc_info=True)
                else:
                    self.log(f"{log_prefix} Cannot save history file on reset: prev_alert_final_attributes missing.", level="WARNING")

            # --- 2. Format Previous State for the new 'off' state ---
            fallback_time_iso = datetime.now().isoformat(timespec='microseconds')
            formatted_prev = {}
            last_alert_wa = "" # Keep last messages for display even when off
            last_alert_tg = ""

            if self.prev_alert_final_attributes:
                # Use the stored final attributes from the window that just ended
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
                # Fallback if somehow prev_alert_final_attributes is None
                self.log(f"{log_prefix} Previous alert attributes missing during reset. Using defaults for 'prev_'.", level="WARNING")
                formatted_prev = {
                    "prev_cat": 0, "prev_title": "", "prev_desc": "", "prev_areas": "", "prev_cities": [], "prev_data": "",
                    "prev_data_count": 0, "prev_duration": 0, "prev_last_changed": fallback_time_iso, "prev_alerts_count": 0
                }

            # --- 3. Clear Internal State Variables ---
            self.prev_alert_final_attributes = None # Clear the stored attributes
            self.last_alert_time = None # Stop the timer
            self.last_processed_alert_id = None # Reset ID tracker
            self.cities_past_window_std = set() # Clear accumulated cities
            self.window_alerts_grouped = {} # Clear grouped data
            self.alert_sequence_count = 0 # Reset sequence counter
            self.no_active_alerts_polls = 0 # Reset idle poll counter

            # --- 4. Get Final History & Define Reset Attributes ---
            hist_attrs = self.history_manager.get_history_attributes()
            reset_attrs = {
                "active_now": False, "special_update": False, "id": 0, "cat": 0, "title": "אין התרעות", "desc": "שגרה",
                "areas": "", "cities": [], "data": "", "data_count": 0, "duration": 0,
                "icon": "mdi:check-circle-outline", "emoji": "✅", "alerts_count": 0,
                "last_changed": datetime.now().isoformat(timespec='microseconds'), # Time of reset
                "my_cities": sorted(list(set(self.city_names_config))),
                **formatted_prev, # Include the 'prev_' state from the ended window
                "alert_wa": last_alert_wa, # Persist last messages
                "alert_tg": last_alert_tg, # Persist last messages
                "script_status": "running" # Set status to idle
            }

            # --- 5. Update HA States ---
            try:
                # Note: This call will NOT update main_text because main_state="off"
                await self._update_ha_state(
                    main_state="off", city_state="off", text_state="אין התרעות", # text_state is ignored here
                    attributes=reset_attrs, text_icon="mdi:check-circle-outline"
                )
            except Exception as e:
                self.log(f"{log_prefix} Error during _update_ha_state call on reset: {e}", level="ERROR", exc_info=True)

            # --- 6. Re-affirm History Sensor States ---
            # Ensure history sensors reflect the final state from hist_attrs
            try:
                count_cities = len(hist_attrs.get("cities_past_24h", []))
                count_alerts = len(hist_attrs.get("last_24h_alerts", []))
                tasks = []

                hist_cities_attrs = {
                    "cities_past_24h": hist_attrs.get("cities_past_24h", []),
                    "script_status": "running"
                }
                tasks.append(self.set_state(self.history_cities_sensor, state=str(count_cities), attributes=hist_cities_attrs))

                history_list_attr = {
                    "last_24h_alerts": hist_attrs.get("last_24h_alerts", []),
                    "script_status": "running"
                }

                tasks.append(self.set_state(self.history_list_sensor, state=str(count_alerts), attributes=history_list_attr))

                history_group_attr = {
                    "last_24h_alerts_group": hist_attrs.get("last_24h_alerts_group", {}),
                    "script_status": "running"
                }

                tasks.append(self.set_state(self.history_group_sensor, state=str(count_alerts), attributes=history_group_attr))

                if tasks:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                self.log(f"{log_prefix} Error re-affirming history sensors: {e}", level="ERROR", exc_info=True)

            # --- 7. Update GeoJSON Files for Idle State ---
            if self.save_2_file:
                try:
                    # Save History GeoJSON with the final history data from hist_attrs
                    await self._save_history_geojson(hist_attrs)

                    # Save Latest GeoJSON with idle/empty data based on reset_attrs
                    idle_geojson_attrs = {
                        "title": reset_attrs["title"], "desc": reset_attrs["desc"],
                        "cat": reset_attrs["cat"], "cities": [], # Empty list for idle
                        "last_changed": reset_attrs["last_changed"]
                    }
                    await self._save_latest_geojson(idle_geojson_attrs)
                except Exception as e:
                    self.log(f"{log_prefix} Error during GeoJSON update on reset: {e}", level="ERROR", exc_info=True)

            self.log(f"{log_prefix} Sensor reset complete. State is now 'off'.")

        elif timer_expired and not confirmed_idle:
            # Timer has run out, but the last poll still showed an alert (or poll failed)
            # Don't reset yet, wait for a poll cycle that confirms no active alerts.
            self.log(f"{log_prefix} Timer expired ({time_since_last_alert:.1f}s > {self.timer_duration}s), but last poll was not confirmed idle ({self.no_active_alerts_polls}). Awaiting confirmation poll.", level="DEBUG")

    async def _update_ha_state(self, main_state, city_state, text_state, attributes, text_icon="mdi:information"):
        """Updates the state and attributes of core HA entities."""
        attributes = attributes or {}
        # Ensure last_changed and script_status are always set/updated
        attributes["last_changed"] = datetime.now().isoformat(timespec='microseconds')
        # Determine status based on main state
        attributes["script_status"] = "running" #if main_state == "on" else "idle"
        #pre_alert = True if attributes["cat"] == 13 and "חדירת מחבלים" not in attributes["title"] else False :"שהייה בסמיכות למרחב מוגן"
        title_alert = attributes.get("title", "")
        #pre_alert = True if "בדקות הקרובות" in title_alert or "עדכון" in title_alert or title_alert == "שהייה בסמיכות למרחב מוגן" else False
        pre_alert = "שהייה בסמיכות למרחב מוגן" == title_alert or any(
                phrase in title_alert for phrase in ["בדקות הקרובות", "עדכון"])

        update_tasks = []
        log_prefix = "[HA Update]"

        # --- Prepare Main Sensor Update ---
        try:
            main_attrs = attributes.copy() # Use a copy for each sensor
            update_tasks.append(self.set_state(self.main_sensor, state=main_state, attributes=main_attrs))
            if pre_alert:
                update_tasks.append(self.set_state(self.main_sensor_pre_alert, state=main_state, attributes=main_attrs))
            else:
                update_tasks.append(self.set_state(self.main_sensor_active_alert, state=main_state, attributes=main_attrs))
                update_tasks.append(self.set_state(self.main_sensor_pre_alert, state="off", attributes=main_attrs))
        except Exception as e:
            self.log(f"{log_prefix} Error preparing task for {self.main_sensor}: {e}", level="ERROR")

        # --- Prepare City Sensor Update ---
        try:
            city_attrs = attributes.copy() # Use a copy for each sensor
            update_tasks.append(self.set_state(self.city_sensor, state=city_state, attributes=city_attrs))
            if pre_alert:
                update_tasks.append(self.set_state(self.city_sensor_pre_alert, state=city_state, attributes=main_attrs))
            else:
                update_tasks.append(self.set_state(self.city_sensor_active_alert, state=city_state, attributes=main_attrs))
                update_tasks.append(self.set_state(self.city_sensor_pre_alert, state="off", attributes=main_attrs))
        except Exception as e:
            self.log(f"{log_prefix} Error preparing task for {self.city_sensor}: {e}", level="ERROR")


        # --- Prepare Input Text Update ---
        try:
            # Only update input_text if main_state is 'on'
            if main_state == "on":
                safe_text_state = text_state[:255] if isinstance(text_state, str) else "Error"
                # Optional: Check if text differs from current state to avoid redundant updates
                current_text_state = await self.get_state(self.main_text)
                if safe_text_state != current_text_state:
                    update_tasks.append(self.set_state(self.main_text, state=safe_text_state, attributes={"icon": text_icon}))

        except Exception as e:
            self.log(f"{log_prefix} Error preparing/checking task for {self.main_text}: {e}", level="ERROR")

        # --- Execute Updates ---
        if update_tasks:
            #self.log(f"{log_prefix} Executing {len(update_tasks)} state update tasks...", level="DEBUG")
            try:
                results = await asyncio.gather(*update_tasks, return_exceptions=True)
                # Log any exceptions that occurred during the gather
                errors_found = False
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        errors_found = True
                        # Try to identify which task failed based on order (simplistic)
                        failed_entity_desc = f"Task {i+1}"
                        if i == 0: failed_entity_desc = self.main_sensor
                        elif len(update_tasks) > 1 and i == 1: failed_entity_desc = self.city_sensor
                        elif len(update_tasks) > 2 and i == 2: failed_entity_desc = self.main_text

                        self.log(f"{log_prefix} Error during HA state update task for {failed_entity_desc}: {result}", level="ERROR", exc_info=False) # Set exc_info=False for cleaner logs unless needed
                # if not errors_found: # Reduce log noise
                    # self.log(f"{log_prefix} State update tasks completed successfully.", level="DEBUG")

            except Exception as e:
                self.log(f"{log_prefix} Unexpected error executing HA state updates via asyncio.gather: {e}", level="ERROR", exc_info=True)


    async def poll_alerts(self):
        """Fetches alerts from API, processes them, or checks for sensor reset."""
        log_prefix = "[Poll Cycle]"

        # --- Poll Live API ---
        live_data = None
        api_error = False
        try:
            live_data = await self.api_client.get_live_alerts()
        except Exception as e:
            self.log(f"{log_prefix} Error fetching live alerts from Oref API: {e}", level="WARNING")
            live_data = None # Ensure it's None on error
            api_error = True # Flag that we couldn't get data

        # --- Process API Response ---
        try:
            # Check if the response contains valid alert data ('data' field non-empty is key)
            is_alert_active = isinstance(live_data, dict) and live_data.get("data")

            if is_alert_active:
                # self.log(f"{log_prefix} Active alert detected in payload.", level="DEBUG")
                self.no_active_alerts_polls = 0 # Reset idle poll counter
                await self._process_active_alert(live_data, is_test=False)

                # If a real alert comes during a test window, cancel the test
                if self.test_alert_cycle_flag > 0:
                    self.log(f"{log_prefix} Real alert detected during active test window. Cancelling test mode.", level="INFO")
                    self.test_alert_cycle_flag = 0
                    self.test_alert_start_time = 0
                    try:
                        if await self.get_state(self.activate_alert) == "on":
                            await self.call_service("input_boolean/turn_off", entity_id=self.activate_alert)
                            #self.log(f"{log_prefix} Turned off test input_boolean due to real alert interruption.", level="DEBUG")
                    except Exception as e_bool:
                        self.log(f"{log_prefix} Error turning off test boolean after interruption: {e_bool}", level="WARNING")

            else: # --- No Active Alert Found in Payload OR API Error ---
                if not api_error:
                    # self.log(f"{log_prefix} No active alert data in payload.", level="DEBUG")
                    self.no_active_alerts_polls += 1
                else:
                    # Don't increment poll count if API failed, might be temporary
                    self.log(f"{log_prefix} API error occurred, not incrementing idle poll count.", level="DEBUG")
                    # Let's proceed to check reset ONLY IF no test alert is running.

                # Update history sensors even when no active alert is detected in the current poll.
                try:
                    hist_attrs = self.history_manager.get_history_attributes()
                    if isinstance(hist_attrs, dict): # Ensure valid data structure
                        count_cities = len(hist_attrs.get("cities_past_24h", []))
                        count_alerts = len(hist_attrs.get("last_24h_alerts", []))
                        tasks = []
                        # Re-set state to trigger attribute update, even if state (count) is the same
                        hist_cities_attrs = {
                            "cities_past_24h": hist_attrs.get("cities_past_24h", []),
                            "script_status": "running" # Always include status
                        }
                        tasks.append(self.set_state(self.history_cities_sensor, state=str(count_cities), attributes=hist_cities_attrs))

                        history_list_attr = {
                            "last_24h_alerts": hist_attrs.get("last_24h_alerts", []),
                            "script_status": "running"
                        }
                        tasks.append(self.set_state(self.history_list_sensor, state=str(count_alerts), attributes=history_list_attr))

                        history_group_attr = {
                            "last_24h_alerts_group": hist_attrs.get("last_24h_alerts_group", {}),
                            "script_status": "running"
                        }
                        tasks.append(self.set_state(self.history_group_sensor, state=str(count_alerts), attributes=history_group_attr))

                        # Also update history GeoJSON file
                        if self.save_2_file and self.file_manager:
                            tasks.append(self._save_history_geojson(hist_attrs))


                        if tasks:
                            results = await asyncio.gather(*tasks, return_exceptions=True)
                            # self.log(f"{log_prefix} Updated history sensors & GeoJSON (idle poll).", level="DEBUG") # Optional debug log
                        else:
                            self.log(f"{log_prefix} No history update tasks prepared during idle poll.", level="WARNING")

                    else:
                        self.log(f"{log_prefix} Failed to get valid history attributes during idle poll update.", level="WARNING")
                except Exception as e:
                    self.log(f"{log_prefix} Error updating history sensors during idle poll: {e}", level="ERROR", exc_info=True)

                # Handle expiration of test alert window first
                if self.test_alert_cycle_flag > 0:
                    elapsed_test_time = time.time() - self.test_alert_start_time
                    if elapsed_test_time >= self.timer_duration:
                        self.log(f"{log_prefix} Test alert timer ({self.timer_duration}s) expired. Test window ended.", level="INFO")
                        self.test_alert_cycle_flag = 0
                        self.test_alert_start_time = 0
                        # Now that test window ended naturally, check for sensor reset
                        # Note: _check_reset_sensors will also update history sensors/geojson on reset
                        await self._check_reset_sensors()
                    else:
                        # Test window still active, do nothing else this cycle
                        # We already updated history sensors above, so we can just return
                        return # Exit poll cycle early
                else:
                    # No test window active, proceed normally to check if sensors should be reset
                    # Note: _check_reset_sensors will also update history sensors/geojson on reset
                    await self._check_reset_sensors()


        except Exception as e:
            self.log(f"{log_prefix} Error in poll_alerts processing/reset logic: {e}", level="ERROR", exc_info=True)
            if self.test_alert_cycle_flag > 0:
                self.log(f"{log_prefix} Clearing test flag due to error.", level="WARNING")
                self.test_alert_cycle_flag = 0


    # --- Test Alert Handling ---
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

        # --- Check if a real alert is already active ---
        current_state = await self.get_state(self.main_sensor)
        if current_state == 'on' and self.test_alert_cycle_flag == 0: # Ensure not already in test mode
            self.log(f"{log_prefix} Cannot start test alert: A real alert is currently active.", level= "WARNING")
            try: await self.call_service("input_boolean/turn_off", entity_id=self.activate_alert)
            except Exception: pass
            return

        # --- Start Test Sequence ---
        self.test_alert_cycle_flag = 1 # Mark test as active
        self.test_alert_start_time = time.time()
        self.log(f"--- {log_prefix} Initiating Test Alert Sequence ---", level="WARNING")

        test_cities_orig = []
        # Use the validated standardized list to find original names
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

        else: # No cities configured
            default_test_city = "תל אביב - מרכז העיר"
            self.log(f"{log_prefix} No valid 'city_names' configured. Using default '{default_test_city}' for test.", level="WARNING")
            test_cities_orig = [default_test_city]

        if not test_cities_orig: # Should not happen with default, but safety check
            test_cities_orig = ["תל אביב - מרכז העיר"]
            self.log(f"{log_prefix} Test city list was empty after processing, using fallback: {test_cities_orig}", level="WARNING")

        # Construct the test data payload
        test_alert_data = {
            "id": int(time.time() * 1000), # Use timestamp ms as unique ID
            "cat": "1", # Default category 1
            "title": "ירי רקטות וטילים (התרעת בדיקה)", # Test title
            "data": test_cities_orig, # List of original city names
            "desc": "התרעת בדיקה - כנסו למרחב המוגן לזמן קצר לבדיקה" # Test description
        }

        # Process this fake alert data using the main processing function
        try:
            await self._process_active_alert(test_alert_data, is_test=True)
        except Exception as test_proc_err:
            self.log(f"{log_prefix} Error during processing of test alert data: {test_proc_err}", level="ERROR", exc_info=True)
            self.test_alert_cycle_flag = 0
            self.test_alert_start_time = 0

        try:
            # Check state again in case it was turned off manually during processing
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
            self.log(f"Error saving Latest GeoJSON: {e}", level="ERROR", exc_info=True)

    async def _save_history_geojson(self, history_attributes):
        """Generates and saves only the history GeoJSON file."""
        if not self.save_2_file or not self.file_manager: return
        if not history_attributes or "last_24h_alerts" not in history_attributes:
            self.log("Skipping History GeoJSON save: History attributes missing or invalid.", level="WARNING")
            return
        try:
            # Generate history GeoJSON data (needs last_24h_alerts from history_attributes)
            history_geojson_data = self._generate_geojson_data(history_attributes, duration="history")
            path = self.file_paths.get("geojson_history")
            if path:
                self.file_manager.save_geojson_file(history_geojson_data, path)
            else:
                self.log("Skipping History GeoJSON save: Path not found.", level="WARNING")
        except Exception as e:
            self.log(f"Error saving History GeoJSON: {e}", level="ERROR", exc_info=True)

    def _generate_geojson_data(self, attributes, duration="latest"):
        """Generates the GeoJSON structure (FeatureCollection)."""
        geo = {"type": "FeatureCollection", "features": []}
        attrs = attributes or {} # Ensure attributes is a dict
        locations = {} # Key: "lat,lon", Value: {"coords": [lon, lat], "cities": set(), "details": []}
        unknown_cities_logged = set() # Track warnings per call

        if duration == "latest":
            # Uses 'cities' from attributes (accumulated list of original names)
            cities_to_process = attrs.get("cities", [])
            # Use latest alert info from attributes for properties
            alert_title = attrs.get("title", "אין התרעות")
            timestamp_str = attrs.get("last_changed", datetime.now().isoformat(timespec='microseconds'))
            category = attrs.get("cat", 0)
            description = attrs.get("desc", "")

            if not cities_to_process: return geo # Return empty structure if no cities

            # Map cities to coordinates
            for city_display_name in cities_to_process:
                if not isinstance(city_display_name, str) or not city_display_name.strip(): continue
                std = standardize_name(city_display_name)
                if not std: continue # Skip if name becomes empty after standardization
                det = self.lamas_manager.get_city_details(std)

                if det and "lat" in det and "long" in det:
                    try:
                        lat, lon = float(det["lat"]), float(det["long"])
                        key = f"{lat},{lon}" # Use coords as key
                        if key not in locations:
                            locations[key] = {"coords": [lon, lat], "cities": set()}
                        locations[key]["cities"].add(city_display_name) # Add original name
                    except (ValueError, TypeError) as e:
                        if std not in unknown_cities_logged: # Log coord error only once per city
                            self.log(f"GeoJSON ({duration}): Invalid coords for '{city_display_name}': {e}", level="WARNING")
                            unknown_cities_logged.add(std)
                elif std not in unknown_cities_logged: # Log missing city/coords only once
                    reason = "Not found in Lamas" if not det else "Missing coords"
                    self.log(f"GeoJSON ({duration}): SKIP city '{city_display_name}' (std: '{std}'). Reason: {reason}.", level="DEBUG") # Lowered level
                    unknown_cities_logged.add(std)

            # Create features from aggregated locations
            if locations:
                icon_mdi, emoji = ICONS_AND_EMOJIS.get(category, ("mdi:alert", "❗"))
                for key, loc_data in locations.items():
                    city_names_at_point = sorted(list(loc_data["cities"]))
                    # Create properties for the map point
                    props = {
                        "name": ", ".join(city_names_at_point), # All cities at this coord
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
            # Uses 'last_24h_alerts' from attributes (list of dicts with string times)
            history_list = attrs.get("last_24h_alerts", [])
            if not history_list: return geo # Return empty structure

            # Aggregate historical alerts by location
            for alert in history_list:
                if not isinstance(alert, dict): continue
                city_display_name = alert.get("city") # History should store original name
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
                        # Store the raw alert dict for this location
                        locations[key]["details"].append(alert)
                        # Also keep track of unique city names at this location
                        locations[key]["cities"].add(city_display_name)
                    except (ValueError, TypeError) as e:
                        if std not in unknown_cities_logged:
                            self.log(f"GeoJSON ({duration}): Invalid hist coords for '{city_display_name}': {e}", level="WARNING")
                            unknown_cities_logged.add(std)
                elif std not in unknown_cities_logged:
                    reason = "Not found in Lamas" if not det else "Missing coords"
                    self.log(f"GeoJSON ({duration}): SKIP hist city '{city_display_name}' (std: '{std}'). Reason: {reason}.", level="DEBUG") # Lowered level
                    unknown_cities_logged.add(std)

            # Create features from aggregated historical locations
            if locations:
                icon_mdi, emoji = ("mdi:history", "📜") # Use history icon
                for key, loc_data in locations.items():
                    if not loc_data.get("details"): continue # Skip if no details somehow

                    # Find the latest alert event *at this specific coordinate point*
                    try:
                        latest_alert_at_loc = max(
                            loc_data["details"],
                            # Use _parse_datetime_str for robust parsing, fallback to epoch min
                            key=lambda x: self._parse_datetime_str(x.get("time", "")) or datetime.min
                        )
                    except (ValueError, TypeError) as max_err:
                        self.log(f"GeoJSON ({duration}): Error finding latest alert time for location {key}: {max_err}", level="WARNING")
                        continue # Skip this feature if time parsing fails

                    city_names_at_point = sorted(list(loc_data["cities"]))
                    alert_time_str = latest_alert_at_loc.get('time', 'N/A') # String time 'YYYY-MM-DD HH:MM:SS'
                    alert_count = len(loc_data['details'])
                    # Create description string
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
                        "latest_alert_time": alert_time_str # Include time string
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
            return {} # Return empty if data is invalid

        # Extract data safely with defaults
        cat_str = data.get('cat', '0') # Expect string from backup? Check save format.
        cat = int(cat_str) if isinstance(cat_str, str) and cat_str.isdigit() else 0
        title = data.get('title', '')
        # Backup 'data' key holds list of city names (should be original names)
        raw_cities_data = data.get('data', [])
        cities_from_backup = []

        # Handle potential format variations in backup 'data' field
        if isinstance(raw_cities_data, str):
            # If it was mistakenly saved as a comma-separated string
            cities_from_backup = [c.strip() for c in raw_cities_data.split(',') if c.strip()]
        elif isinstance(raw_cities_data, list):
            # If it's already a list (preferred)
            cities_from_backup = [str(c) for c in raw_cities_data if isinstance(c, (str, int))] # Ensure strings

        desc = data.get('desc', '')
        # Use _is_iso_format to ensure consistency, check both possible keys
        last = self._is_iso_format(data.get('last_changed', data.get('alertDate', '')))
        # Recalculate duration from description
        dur = self.alert_processor.extract_duration_from_desc(desc) if self.alert_processor else 0

        # Reconstruct areas and original city names from the backup city list
        areas_set = set()
        orig_cities_set = set(cities_from_backup) # Start with the names from backup
        unknown_cities_logged = set() # Track warnings

        # Refine using Lamas if possible
        refined_orig_cities = set()
        if self.lamas_manager: # Check if LamasManager is initialized
            for city_name_from_backup in cities_from_backup:
                if not city_name_from_backup: continue
                std = standardize_name(city_name_from_backup)
                if not std:
                    refined_orig_cities.add(city_name_from_backup) # Keep original if std fails
                    continue

                det = self.lamas_manager.get_city_details(std)
                if det:
                    areas_set.add(det.get("area", DEFAULT_UNKNOWN_AREA))
                    # Prefer original name from Lamas if available
                    refined_orig_cities.add(det.get("original_name", city_name_from_backup))
                else:
                    # City not found in Lamas - use default area and the name from backup
                    areas_set.add(DEFAULT_UNKNOWN_AREA)
                    refined_orig_cities.add(city_name_from_backup)
                    if std not in unknown_cities_logged:
                        #self.log(f"Backup Format: City '{city_name_from_backup}' (std: '{std}') not in Lamas. Area='{DEFAULT_UNKNOWN_AREA}'.", level="DEBUG")
                        unknown_cities_logged.add(std)
            orig_cities_set = refined_orig_cities # Update with refined names

        sorted_orig_cities = sorted(list(orig_cities_set))
        areas_str = ", ".join(sorted(list(areas_set))) if areas_set else ""
        # 'prev_data' should be the comma-separated string of *original* names
        prev_data_str = ", ".join(sorted_orig_cities)

        return {
            "prev_cat": cat,
            "prev_title": title,
            "prev_desc": desc,
            "prev_areas": areas_str,
            "prev_cities": sorted_orig_cities, # List of original city names
            "prev_data": prev_data_str,        # Comma-separated string of original cities
            "prev_data_count": len(sorted_orig_cities),
            "prev_duration": dur,
            "prev_last_changed": last, # ISO formatted time string
            "prev_alerts_count": data.get('alerts_count', 0) # Get backup count, default 0
        }
