"""
Red Alerts Israel - Appdaemon Script for Home Assistant
-------------------------------------------------------
The script will create four Home Assistant sensors, using the name you choose (in sensor_name). As exemplified here, the value is ‘red_alert’:

binary_sensor.red_alert: This sensor will be on when there is an alarm anywhere in Israel.
binary_sensor.red_alert_city: This sensor will be on when there is an alarm in any city that is on the city_names list.
text_input.red_alert: This sensor will store all historical data for viewing in the Home Assistant logbook.
input_boolean.red_alert: This sensor will activate a fake alert design to test automations.

The script automatically generates two GeoJSON files that store the alert's geolocation data (accessible from the WWW folder inside the Home Assistant directory), which can be displayed on the Home Assistant map.
Additionally, the script can save the history of all alerts in dedicated TXT and CSV files, which will also be accessible from the WWW folder.

The sensor attributes contain several message formats for display or sending notifications. You also have the flexibility to display or use any of the attributes of the sensor to create more sub-sensors from the main binary_sensor.red_alert.

Configuration: 
1. Open appdaemon/apps/apps.yaml
2. Add the code line
3. Save the code after you choose the city names as exemplified. You can add as many cities as you want. 
* City names can be found here: https://github.com/idodov/RedAlert/blob/main/cities_name.md
---
red_alerts_israel:
  module: red_alerts_israel
  class: Red_Alerts_Israel
  interval: 5
  timer: 120
  sensor_name: "red_alert"
  save_2_file: True
  hours_to_show: 1
  city_names:
    - אזור תעשייה אכזיב מילואות
    - שלומי
    - כיסופים
"""

import requests
import re
import time
import json
import codecs
import traceback
import random
import os
import csv
from datetime import datetime, timedelta
from io import StringIO
from appdaemon.plugins.hass.hassapi import Hass

script_directory = os.path.dirname(os.path.realpath(__file__))

class Red_Alerts_Israel(Hass):

    def initialize(self):
        self.url = "https://www.oref.org.il/warningMessages/alert/alerts.json"
        self.history_url = "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json"
        self.headers = { 
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': 'https://www.oref.org.il/',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        }
        self.icons_and_emojis = {
            0: ("mdi:alert", "❗"), 1: ("mdi:rocket-launch", "🚀"), 2: ("mdi:home-alert", "⚠️"),
            3: ("mdi:earth-box", "🌍"), 4: ("mdi:chemical-weapon", "☢️"), 5: ("mdi:waves", "🌊"),
            6: ("mdi:airplane", "🛩️"), 7: ("mdi:skull", "💀"), 8: ("mdi:alert", "❗"),
            9: ("mdi:alert", "❗"), 10: ("mdi:alert", "❗"), 11: ("mdi:alert", "❗"),
            12: ("mdi:alert", "❗"), 13: ("mdi:run-fast", "👹")
        }
        self.day_names = {
            'Sunday': 'יום ראשון', 'Monday': 'יום שני', 'Tuesday': 'יום שלישי', 
            'Wednesday': 'יום רביעי', 'Thursday': 'יום חמישי', 'Friday': 'יום שישי', 
            'Saturday': 'יום שבת'
        }
        self.false_data_json = {
            "id": 0, "cat": "1", "title": "ירי רקטות וטילים", "data": ["עזה"],
            "alertDate": f"{datetime.now().isoformat()}"
        }
        self.interval = self.args.get("interval", 2)
        self.timer = self.args.get("timer", 120)
        self.save_2_file = self.args.get("save_2_file", True)
        #self.hacs = self.args.get("hacs", True)
        self.sensor_name = self.args.get("sensor_name", "red_alert")
        self.city_names = self.args.get("city_names", [])
        self.hours_to_show = self.args.get("hours_to_show", 4)

        self.def_attributes = {
            "active_now": "off", "id": 0, "cat": 0, "title": "אין התרעות", "desc": "", "data": "", "areas": "",
            "data_count": 0, "duration": 0, "icon": "mdi:alert", "emoji": "⚠️", "cities": [],
            "alerts_count": 0, "my_cities": list(set(self.city_names))
        }

        self.main_sensor = f"binary_sensor.{self.sensor_name}"
        self.main_sensor_history = f"sensor.{self.sensor_name}_daily_history"
        self.city_sensor = f"binary_sensor.{self.sensor_name}_city"
        self.main_text = f"input_text.{self.sensor_name}"
        self.activate_alert = f"input_boolean.{self.sensor_name}_test"
        self.history_file = f"/homeassistant/www/{self.sensor_name}_history.txt"
        self.history_file_csv = f"/homeassistant/www/{self.sensor_name}_history.csv"
        self.history_file_json = f"/homeassistant/www/{self.sensor_name}_history.json"
        self.history_file_json_error = f"/homeassistant/www/{self.sensor_name}_error.txt"
        self.past_2min_file = f"/homeassistant/www/{self.sensor_name}_latest.geojson"
        self.past_24h_file = f"/homeassistant/www/{self.sensor_name}_24h.geojson"

        self.lamas = self.load_lamas_data()
        if not self.lamas:
            self.log("Failed to load Lamas data.")
            return

        self.city_names_self = set(self.city_names)
        
        self.on_time1 = self.on_time2 = time.time() + self.timer
        self.alert_id = 12345
        self.t_value = 0
        self.c_value = 1
        self.massive = 0
        self.no_active_alerts = 0
        self.test_time = time.time()
        self.last_alert_time = None
        self.prev_alert_attributes = None
        self.cities_past_24h = []
        self.cities_past_2min = []
        self.last_24_alerts = []
        self.last_title = False

        self.initialize_sensors()
        self.load_initial_alert_data()
        self.load_alert_history()
        self.create_csv()
        self.save_geojson_files()

        self.run_every(self.poll_alerts, datetime.now(), self.interval, timeout=30)

    def standardize_name(self, name):
        return re.sub(r'[\(\)\'\"]+', '', name).strip()

    def create_csv(self):
        if self.save_2_file and not os.path.exists(self.history_file_csv):
            with open(self.history_file_csv, 'w', encoding='utf-8-sig') as csv_file:
                print("ID, DAY, DATE, TIME, TITLE, COUNT, AREAS, CITIES, DESC, ALERTS", file=csv_file)

    def load_lamas_data(self):
        #file_path = '/homeassistant/appdaemon/apps/RedAlert/lamas_data.json' if self.hacs else '/homeassistant/addon_configs/a0d7b954_appdaemon/apps/RedAlert/lamas_data.json'
        file_path = f"{script_directory}/lamas_data.json"
        github_url = "https://raw.githubusercontent.com/idodov/RedAlert/main/apps/red_alerts_israel/lamas_data.json"

        try:
            with open(file_path, 'r', encoding='utf-8-sig') as file:
                lamas_data = json.load(file)
            self.log("Lamas data loaded from local file")

        except FileNotFoundError:
            self.log(f"Error: Lamas data file not found at {file_path}, attempting to download from GitHub")
            lamas_data = self.download_lamas_data(github_url, file_path)

        except json.JSONDecodeError:
            self.log("Error: Invalid JSON in Lamas data file, attempting to download from GitHub")
            lamas_data = self.download_lamas_data(github_url, file_path)

        except Exception as e:
            self.log(f"Error loading Lamas data from local file: {e}")
            lamas_data = self.download_lamas_data(github_url, file_path)

        if 'areas' not in lamas_data:
            self.log("Unexpected JSON structure in Lamas data")
            return None

        # Process the areas and cities
        for area, cities in lamas_data['areas'].items():
            if isinstance(cities, dict):
                standardized_cities = {}
                for city, details in cities.items():
                    standardized_city_name = self.standardize_name(city)

                    # Check for lat and long in the details and add them if present
                    if isinstance(details, dict) and 'lat' in details and 'long' in details:
                        standardized_cities[standardized_city_name] = {
                            "lat": details["lat"],
                            "long": details["long"]
                        }
                    else:
                        # If no lat/long, just add an empty entry
                        standardized_cities[standardized_city_name] = {}

                lamas_data['areas'][area] = standardized_cities

            else:
                self.log(f"Unexpected cities structure in area {area}: {cities}")
                lamas_data['areas'][area] = {}

        return lamas_data

    def download_lamas_data(self, url, file_path):
        try:
            response = requests.get(url)
            response.raise_for_status()
            lamas_data = response.json()
            with open(file_path, 'w', encoding='utf-8-sig') as file:
                json.dump(lamas_data, file, ensure_ascii=False, indent=2)
            self.log(f"Lamas data downloaded from GitHub and saved to {file_path}")
            return lamas_data
        except requests.exceptions.RequestException as e:
            self.log(f"Error downloading Lamas data from GitHub: {e}")
            return None
        except json.JSONDecodeError as e:
            self.log(f"Error decoding Lamas data from GitHub: {e}")
            return None
        except Exception as e:
            self.log(f"Unexpected error: {e}")
            return None

    def initialize_sensors(self):
        if not self.entity_exists(self.main_sensor):
            self.set_state(self.main_sensor, state="off", attributes=self.def_attributes)
        if not self.entity_exists(self.city_sensor):
            self.set_state(self.city_sensor, state="off", attributes=self.def_attributes)
        if not self.entity_exists(self.main_text):
            self.set_state(self.main_text, state="אין התרעות", attributes={"min": 0, "max": 255, "mode": "text", "friendly_name": "Last Red Alert in Israel"})
        if not self.entity_exists(self.activate_alert):
            self.set_state(self.activate_alert, state="off", attributes={"friendly_name": "Test Red Alert"})

    def load_initial_alert_data(self):
        first_alert_data = self.get_from_json()
        if not first_alert_data:
            first_alert_data = self.get_first_alert_data()

        if first_alert_data:
            last_data = self.check_backup_data(first_alert_data)
        else:
            self.log("Failed to retrieve initial data.")
            last_data = self.check_backup_data(self.false_data_json)
        
        self.set_state(self.main_sensor, state="off", attributes=last_data)

    def get_from_json(self):
        try:
            with open(self.history_file_json, "r", encoding='utf-8-sig') as json_file:
                data = json.load(json_file)
                return data
        except Exception as e:
            self.log(f"Error loading backup data from JSON: {e}")
            return None

    def get_first_alert_data(self):
        try:
            response = requests.get(self.history_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            if data and isinstance(data, list):
                return data[0]
            else:
                return self.false_data_json
        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching initial alert data: {e}")
            return self.false_data_json

    def load_alert_history(self):
        try:
            response = requests.get(self.history_url, headers=self.headers, timeout=30)
            response.raise_for_status()
            history_data = response.json()

            now = datetime.now()
            twenty_four_hours_ago = now - timedelta(hours=self.hours_to_show) 
            self.cities_past_24h = []
            self.cities_past_24h = [
                entry['data'] for entry in history_data 
                if datetime.strptime(entry['alertDate'], '%Y-%m-%d %H:%M:%S') >= twenty_four_hours_ago
            ]
            self.cities_past_24h = list(set(self.cities_past_24h))  # Remove duplicates

            self.last_24_alerts = [
            {
                'title': entry['title'],
                'city': entry['data'],
                'area': next((area for area, cities in self.lamas['areas'].items() if self.standardize_name(entry['data']) in cities), "ישראל"),
                'time': datetime.strptime(entry['alertDate'], '%Y-%m-%d %H:%M:%S')
            }
            for entry in history_data
                if datetime.strptime(entry['alertDate'], '%Y-%m-%d %H:%M:%S') >= twenty_four_hours_ago
            ]

            self.set_state(self.main_sensor, attributes={
                "cities_past_24h": self.cities_past_24h,
                "last_24h_alerts": self.last_24_alerts,
                "last_24h_alerts_group": self.restructure_alerts(self.last_24_alerts)
            })

        except requests.exceptions.RequestException as e:
            self.log(f"Error fetching alert history data: {e}")

    def poll_alerts(self, kwargs):
        try:
            response = requests.get(self.url, headers=self.headers, timeout=30)
            response.raise_for_status()
            response_data = codecs.decode(response.content, 'utf-8-sig')

            if self.get_state(self.activate_alert) == "on":
                self.handle_test_alert()
            elif response_data.strip():
                data = json.loads(response_data)
                if data.get('data'):
                    self.check_data(data)
                else:
                    self.no_active_alerts +=1
                    self.reset_sensors_if_needed()
            else:
                self.no_active_alerts +=1
                self.reset_sensors_if_needed()

            self.c_value += 1
            self.set_state(self.main_sensor, attributes={"count": self.c_value})

        except requests.exceptions.RequestException as e:
            self.log(f"Error polling alerts: {e}")
            self.reset_sensors_if_needed()
            
        except json.JSONDecodeError as e:
            self.log("Error decoding JSON response.")
            self.reset_sensors_if_needed()

        except Exception as e:
            self.log(f"Unexpected error: {e}\n{traceback.format_exc()}")
            self.reset_sensors_if_needed()

    def handle_test_alert(self):
        self.t_value += 1
        if self.t_value == 1:
            self.test_time = time.time()
            data = {
                'id': random.randint(123450000000000000, 123456789123456789),
                'cat': '1', 'title': 'ירי רקטות וטילים (התרעה לצורך בדיקה)',
                'data': list(self.city_names_self), 'desc': 'אין צורך לשהות במרחב מוגן 10 דקות'
            }
            self.check_data(data)
            #self.set_state(self.city_sensor, state="off", attributes=self.def_attributes)
            self.set_state(self.activate_alert, state="off")

        if time.time() - self.test_time >= self.timer:
            self.t_value = 0

    def reset_sensors_if_needed(self):
        current_time = time.time()
        if self.no_active_alerts < 1:
            self.set_state(self.main_sensor, attributes={"active_now": "off"})
            self.set_state(self.city_sensor, attributes={"active_now": "off"})
        if self.last_alert_time and current_time - self.last_alert_time > self.timer:
            self.set_state(self.main_sensor, state="off", attributes=self.def_attributes)
            self.set_state(self.city_sensor, state="off", attributes=self.def_attributes)
            if self.save_2_file:
                self.save_alert_data_to_csv()
            self.last_alert_time = None
            self.prev_alert_attributes = None
            self.cities_past_2min = []
            self.last_title = False
            self.massive = 0
            self.no_active_alerts = 0
            self.load_alert_history()

    def check_backup_data(self, data):
        category = int(data.get('cat', 0))
        alert_title = data.get('title', 'לא היו התרעות ביממה האחרונה')
        city_names = data.get('data', [])
        descr = data.get('desc', 'מצב שגרה')
        last_time = self.is_iso_format(data.get('alertDate', datetime.now().isoformat()))
        icon_alert, icon_emoji = self.icons_and_emojis.get(category, ("mdi:alert", "❗"))
        
        if isinstance(city_names, str):
            city_names = [city_names]
        
        standardized_names = set([self.standardize_name(name) for name in city_names])
        areas = []
        for area, cities in self.lamas['areas'].items():
            if standardized_names.intersection(set(self.standardize_name(city) for city in cities)):
                areas.append(area)
        
        areas_alert = ", ".join(areas) if areas else "ישראל"
        sensor_attributes = {
            "count": 0, "id": 0, "cat": 0, "title": "אין התרעות", "desc": "שגרה",
            "areas": "", "cities": [], "data": None,
            "data_count": 0, "duration": 0, "icon": "mdi:alert",
            "emoji": "⚠️", "last_changed": datetime.now().isoformat(), "prev_cat": category, 
            "prev_title": alert_title, "prev_desc": descr, 
            "prev_areas": areas_alert, "prev_cities": city_names, "prev_data": ", ".join(city_names),
            "prev_data_count": len(city_names), "prev_duration": 600, "prev_last_changed": last_time,
        }
        self.active_alerts = 0
        return sensor_attributes

    def check_data(self, data):
        areas, full_message, full_message_wa, full_message_tg = [], [], [], []
        category = int(data.get('cat', 1))
        alert_c_id = int(data.get('id', 0))
        descr = data.get('desc', 'שגרה')
        title_org = data.get('title', 'אין התרעות')

        if self.last_title:
            if not title_org in self.last_title:
                self.last_title = f"{self.last_title} / {title_org}"
        else:
            self.last_title = title_org
        
        alert_title = self.last_title
        city_names = data.get('data', [])
        icon_alert, icon_emoji = self.icons_and_emojis.get(category, ("mdi:alert", "❗"))
        duration = int(re.findall(r'\d+', descr)[0]) * 60 if re.findall(r'\d+', descr) else 0
        if isinstance(city_names, str):
            city_names = [city_names]

        self.cities_past_2min.extend(city_names)
        self.cities_past_2min = list(set(self.cities_past_2min))  # Remove duplicates
    
        city_names = self.cities_past_2min
        data_count = len(city_names)
        standardized_names = set([self.standardize_name(name) for name in city_names])

        for area, cities in self.lamas['areas'].items():
            intersecting_cities = standardized_names.intersection(cities)
            if intersecting_cities:
                areas.append(area)
                original_cities = [name for name in city_names if self.standardize_name(name) in intersecting_cities]
                full_message.append(f"{area}: {', '.join(original_cities)}")
                full_message_wa.append(f"> {area}\n{', '.join(original_cities)}\n")
                full_message_tg.append(f"**__{area}__** — {', '.join(original_cities)}\n")
        
        areas_alert = ", ".join(areas) if areas else "ישראל"
        joined_wa = '\n'.join(full_message_wa)
        joined_tg = '\n'.join(full_message_tg)
        text_wa = f"{icon_emoji} *{alert_title}*\n{joined_wa}\n_{descr}_"
        text_tg = f"{icon_emoji} **{alert_title}**\n{joined_tg}\n__{descr}__"
        text_status = f"{alert_title} - {areas_alert}: {', '.join(city_names)}"
        full_message_str = alert_title + '\n * ' + '\n * '.join(full_message)

        self.cities_past_24h.extend(city_names)
        self.cities_past_24h = list(set(self.cities_past_24h))  # Remove duplicates
        self.cities_past_24h.sort()

        current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for city_name in city_names:
            self.last_24_alerts.append({'title': title_org, 'area': areas_alert, 'city': city_name, 'time': current_time_str})

        sensor_attributes = {
            "id": alert_c_id, "cat": category, "alert": text_status, "alert_alt": full_message_str,
            "alert_txt": ' * '.join(full_message), "alert_wa": text_wa, "alert_tg": text_tg, "title": alert_title,
            "desc": descr, "areas": areas_alert, "cities": city_names, "data": ', '.join(city_names), "data_count": data_count,
            "duration": duration, "icon": icon_alert, "emoji": icon_emoji, "last_changed": datetime.now().isoformat(),
            "prev_cat": category, "prev_title": alert_title, "prev_desc": descr, "prev_areas": areas_alert, "prev_cities": city_names,
            "prev_data": ', '.join(city_names), "prev_data_count": data_count, "prev_duration": duration,
            "prev_last_changed": datetime.now().isoformat(),
            "cities_past_24h": self.cities_past_24h,
            "last_24h_alerts": self.last_24_alerts,
            "last_24h_alerts_group": self.restructure_alerts(self.last_24_alerts)
        }

        #if len(text_status) > 255:
        #    text_status = f"{areas_alert} - {', '.join(city_names)}" if alert_title in text_status else f"{', '.join(city_names)}"

        if len(text_status) > 255:
            text_status = f"{data_count} התרעות שונות ב־{areas_alert}"
        
        if len(text_status) > 255:
            text_status = f"{data_count} התרעות שונות"

        if alert_c_id != self.alert_id:
            self.massive += 1
            self.alert_id = alert_c_id
            self.on_time1 = time.time()
            sensor_attributes["alerts_count"] = self.massive
            sensor_attributes["prev_alerts_count"] = self.massive
            sensor_attributes["active_now"] = "on"
            areas_set = set()
            for city in sensor_attributes["cities"]:
                for area, cities in self.lamas['areas'].items():
                    if self.standardize_name(city) in cities:
                        areas_set.add(area)
            sensor_attributes["areas"] = ", ".join(areas_set)

            self.cities_past_24h.extend(city_names)
            self.cities_past_24h = list(set(self.cities_past_24h))  # Remove duplicates
            sensor_attributes["cities_past_24h"] = self.cities_past_24h
            
            self.set_state(self.main_sensor, state="on", attributes=sensor_attributes)
            self.set_state(self.main_text, state=text_status, attributes={"icon": icon_alert})
            self.save_geojson_files()
            with open(self.history_file_json, "w", encoding='utf-8-sig') as json_file:
                data.update({'alertDate': datetime.now().isoformat()})
                data["data"] = self.cities_past_2min

                json.dump(data, json_file, indent=2)

            if standardized_names.intersection(self.city_names_self):
                self.on_time2 = time.time()
                self.set_state(self.city_sensor, state="on", attributes=sensor_attributes)
            
            self.prev_alert_attributes = sensor_attributes
            self.last_alert_time = time.time()
            self.active_alerts = 0

    def save_alert_data_to_csv(self):
        if not self.prev_alert_attributes:
            return

        alert_data = self.prev_alert_attributes
        formatted_new_time = (datetime.now() - timedelta(seconds=110)).strftime('%H:%M')
        formatted_new_date = (datetime.now() - timedelta(seconds=110)).strftime('%d/%m/%Y')
        now = datetime.now()
        day_name_hebrew = self.day_names[now.strftime('%A')]
        date_time_str = f"\nהתרעה נשלחה ב{day_name_hebrew} ה-{now.strftime('%d/%m/%Y')} בשעה {formatted_new_time}"

        # Prepare CSV data
        csv_data = [
            int(alert_data['id'] / 10000000),
            day_name_hebrew,
            formatted_new_date,
            formatted_new_time,
            alert_data['title'],
            alert_data['data_count'],
            alert_data['areas'],
            alert_data['data'],
            alert_data['desc'],
            self.massive
        ]

        # Use StringIO to write CSV data into a string
        output = StringIO()
        csv_writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        csv_writer.writerow(csv_data)
        csv_string = output.getvalue().strip()

        with open(self.history_file, 'a', encoding='utf-8-sig') as f:
            print(date_time_str, file=f)
            print(alert_data["alert_alt"], file=f)

        with open(self.history_file_csv, 'a', encoding='utf-8-sig') as f3:
            print(csv_string, file=f3)

        self.prev_alert_attributes = None


    def is_iso_format(self, last_time):
        try:
            parsed_time = datetime.fromisoformat(last_time)
            return parsed_time.strftime("%Y-%m-%dT%H:%M:%S.%f")
        except ValueError:
            try:
                parsed_time = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
                return parsed_time.strftime("%Y-%m-%dT%H:%M:%S.%f")
            except ValueError:
                return datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")

    def restructure_alerts(self, alerts):
        new_structure = {}
    
        for alert in alerts:
            title = alert['title']
            area = alert['area']
            city = alert['city']
            
            try:
                time = alert['time'].strftime('%Y-%m-%d %H:%M:%S')
            except:
                time = alert['time']
            if title not in new_structure:
                new_structure[title] = {}
        
            if area not in new_structure[title]:
                new_structure[title][area] = []
        
            new_structure[title][area].append({'city': city, 'time': time})
    
        return new_structure
    
    def create_geojson(self, attributes, file_path, duration="latest"):
        geojson = {
            "type": "FeatureCollection",
            "features": []
        }

        sensor_attributes = attributes.get("attributes", {})

        if duration == "latest":
            cities_data = sensor_attributes.get("prev_cities", [])
        else:
            cities_data = self.cities_past_24h
            last_alerts = self.last_24_alerts

        if duration == "latest":
            coordinates = []
            city_names = []

            added_cities = set()

            for city_name in cities_data:
                standardized_city_name = self.standardize_name(city_name)

                if standardized_city_name in added_cities:
                    continue

                for area, cities in self.lamas['areas'].items():
                    if standardized_city_name in cities:
                        lat = cities[standardized_city_name].get("lat")
                        lon = cities[standardized_city_name].get("long")

                        if lat and lon:
                            coordinates.append([lon, lat])
                            city_names.append(city_name)

                            added_cities.add(standardized_city_name)

            if coordinates:
                feature = {
                    "type": "Feature",
                    "geometry": {
                        "type": "MultiPoint",
                        "coordinates": coordinates
                    },
                    "properties": {
                        "cities": city_names,
                    }
                }
                geojson["features"].append(feature)

        else:
            last_alerts = self.last_24_alerts
            added_cities = set()

            for alert in last_alerts:
                city_name = alert['city']
                area_name = alert['area']
                alert_type = alert.get('cat', 1)  
                alert_title = alert['title']

                standardized_city_name = self.standardize_name(city_name)

                if standardized_city_name in added_cities:
                    continue

                for area, cities in self.lamas['areas'].items():
                    if standardized_city_name in cities:
                        lat = cities[standardized_city_name].get("lat")
                        lon = cities[standardized_city_name].get("long")

                        if lat and lon:
                            icon, emoji = self.icons_and_emojis.get(alert_type, ("mdi:alert", "❗"))

                            feature = {
                                "type": "Feature",
                                "geometry": {
                                    "type": "Point",
                                    "coordinates": [lon, lat]
                                },
                                "properties": {
                                    "name": city_name,
                                    "area": area_name,
                                    "icon": "bubble",
                                    "label": emoji,
                                    "description": alert_title
                                }
                            }
                            geojson["features"].append(feature)

                            added_cities.add(standardized_city_name)

        with open(file_path, 'w', encoding='utf-8-sig') as f:
            json.dump(geojson, f, ensure_ascii=False, indent=2)

        self.log(f"GeoJSON {duration} alerts file saved to {file_path}")

    def save_geojson_files(self):
        attributes = self.get_state(self.main_sensor, attribute='all')
        self.create_geojson(attributes, self.past_2min_file, duration="latest")
        self.create_geojson(attributes, self.past_24h_file, duration="24h")
