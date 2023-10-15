# Israeli Red Alert Service for Home Assistant (AppDaemon)
**This script creates a Home Assistant binary sensor to track the status of Red Alerts in Israel. The sensor can be used in automations or to create sub-sensors/binary sensors from it.**
The sensor provides a warning for all threats that the PIKUD HA-OREF alerts for, including red alerts (rocket and missile launches), unauthorized aircraft penetration, earthquakes, tsunami concerns, infiltration of terrorists, hazardous materials incidents, unconventional warfare, and any other threat. When the alert is received, the nature of the threat will appear at the beginning of the alert (e.g., 'ירי רקטות וטילים').

Installing this script will create a Home Assistant entity called ***binary_sensor.oref_alert***. This sensor will be **on** if there is a Red Alert in Israel, and **off** otherwise. The sensor also contains attributes that can be used for various purposes, such as category, ID, title, data, and description.

### Why did I choose this method and not REST sensor?
Until we all have an official Home Assistant add-on to handle 'Red Alert' situations, there are several approaches for implementing the data into Home Assistant. One of them is creating a REST sensor and adding the code to the *configuration.yaml* file. However, using a binary sensor (instead of a 'REST sensor') is a better choice because it accurately represents binary states (alerted or not alerted), is more compatible with Home Assistant tools, and simplifies automation and user configuration. It offers a more intuitive and standardized approach to monitoring alert status. 

While the binary sensor's state switches to 'on' when there is an active alert in Israel behavior may not suit everyone, the sensor is designed with additional attributes containing data such as cities, types of attacks and more. These attributes make it easy to create customized sub-sensors to meet individual requirements. For example, you can set up specific sensors that activate only when an alarm pertains to a particular city or area.

I tried various methods in Home Assistant, but this script worked best for my needs.

*This code is based on and inspired by https://gist.github.com/shahafc84/5e8b62cdaeb03d2dfaaf906a4fad98b9*

### Sensor Capabilities
![Capture](https://github.com/idodov/RedAlert/assets/19820046/79adf8ff-1369-472b-a463-0c1fe82a9c4d)
![Capture--](https://github.com/idodov/RedAlert/assets/19820046/2cdee4bb-0849-4dc1-bb78-c2e282300fdd)
![000](https://github.com/idodov/RedAlert/assets/19820046/22c3336b-cb39-42f9-8b32-195d9b6447b2)

The icon and label of the sensor, presented on the dashboard via the default entity card, are subject to change dynamically with each new alert occurrence. To illustrate, in the event of a rocket attack, the icon might depict a rocket.

Additionally, there exists a distinct emoji associated with each type of alert, which can be displayed alongside the alert message.

### Important Notice
While it's not obligatory, you have the option to create the sensor from the UI Helper screen. The sensor resets its data after a Home Assistant Core restart, resulting in the loss of previous data. To address this, you can create a template binary sensor **before installation**. To do so, navigate to the Home Assistant menu, then proceed to '**Settings**,' '**Devices & Services**,' '**Helpers**,' and select '**Create a Helper**.' Choose '**Template**' and opt for a '**Template Binary Sensor**.' In the '**Name**' field, enter '**oref alert**,' and in the '**State template**' field, input '**off**.' **submit** your settings to save your new helper.

![b1](https://github.com/idodov/RedAlert/assets/19820046/e451fa8c-789b-4e88-ab98-4687b65f058e)
# Installation Instructions
1. Install the **AppDaemon** addon in Home Assistant.
2. Go to Settings > Add-ons > Ad-on-store and search for **AppDaemon**.
3. Once AppDaemon is installed, enable the **Auto-Start** and **Watchdog** options.
4. Go to the AppDaemon ***configuration*** page and add ```requests``` ***Python package*** under the Python Packages section.

![Capture1](https://github.com/idodov/RedAlert/assets/19820046/d4e3800a-a59b-4605-b8fe-402942c3525b)

5. Open **/config/appdaemon/appdaemon.yaml** and make this changes under *appdeamon* section for ```latitude: 31.9837528``` & 
  ```longitude: 34.7359077``` & ```elevation: 2``` & ```time_zone: Asia/Jerusalem```. 
```
---
appdaemon:
  latitude: 31.9837528
  longitude: 34.7359077
  elevation: 2
  time_zone: Asia/Jerusalem
  plugins:
    HASS:
      type: hass
http:
  url: http://127.0.0.1:5050
admin:
api:
hadashboard:
```
6. Create a file named **orefalert.py** in the **/config/appdaemon/apps/** directory.
7. Paste the script code into the **orefalert.py** file and save it.
The script updates the sensors every *3 seconds*, or more frequently if you specify a shorter scan ```interval```. 
```
import requests
import time
import json
import codecs
from datetime import datetime
from appdaemon.plugins.hass.hassapi import Hass

# Scan every 3 seconds
interval = 3 

class OrefAlert(Hass):
    def initialize(self):
        self.run_every(self.poll_alerts, datetime.now(), interval)

    def poll_alerts(self, kwargs):
        url = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': 'https://www.oref.org.il/',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        }
        icons = {
                    1: "mdi:rocket-launch",
                    2: "mdi:home-alert",
                    3: "mdi:earth-box",
                    4: "mdi:chemical-weapon",
                    5: "mdi:waves",
                    6: "mdi:airplane",
                    7: "mdi:skull",
                    8: "mdi:alert",
                    9: "mdi:alert",
                    10: "mdi:alert",
                    11: "mdi:alert",
                    12: "mdi:alert",
                    13: "mdi:run-fast",
                    }
        icon_alert = "mdi:alert"
        emojis = {
                    1: "🚀",
                    2: "⚠️",
                    3: "🌍",
                    4: "☢️",
                    5: "🌊",
                    6: "🛩️",
                    7: "💀",
                    8: "❗",
                    9: "❗",
                    10: "❗",
                    11: "❗",
                    12: "❗",
                    13: "👣👹",
                    }
        icon_emoji = "🚨"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                response_data = codecs.decode(response.content, 'utf-8-sig')
                if response_data.strip():  
                    try:
                        data = json.loads(response_data)
                        if 'data' in data and data['data']:
                            alert_title = data.get('title', '')
                            alerts_data = ', '.join(data['data'])
                            icon_alert = icons.get(int(data.get('cat', 1)), "mdi:alert")
                            icon_emoji = emojis.get(int(data.get('cat', 1)), "❗")
                            if isinstance(alerts_data, str):
                                data_count = len(alerts_data.split(','))
                            else:
                                data_count = 0
                            self.set_state(
                                "binary_sensor.oref_alert",
                                state="on",
                                attributes={
                                    "id": data.get('id', None),
                                    "cat": data.get('cat', None),
                                    "title": alert_title,
                                    "desc": data.get('desc', None),
                                    "data": alerts_data,
                                    "data_count": data_count,
                                    "last_changed": datetime.now().isoformat(),
                                    "prev_cat": data.get('cat', None),
                                    "prev_title": alert_title,
                                    "prev_desc": data.get('desc', None),
                                    "prev_data": alerts_data,
                                    "prev_last_changed": datetime.now().isoformat(),
                                    "icon": icon_alert,
                                    "emoji":  icon_emoji,
                                    "friendly_name": alert_title,
                                },
                            )
                        else:
# Clear the sensor if there is no data in the response
                            self.set_state(
                                "binary_sensor.oref_alert",
                                state="off",
                                attributes={
                                    "id": None,
                                    "cat": None,
                                    "title": None,
                                    "desc": None,
                                    "data": None,
                                    "data_count": 0,
                                    "last_changed": datetime.now().isoformat(),
                                    "icon": icon_alert,
                                    "emoji":  icon_emoji,
                                    "friendly_name": "אין התרעות",
                                },
                            )
                    except json.JSONDecodeError:
                        self.log("Error: Invalid JSON format in the response.")
                else:
# Clear the binary_sensor state to off if there is no data in the response
                    self.set_state(
                        "binary_sensor.oref_alert",
                        state="off",
                        attributes={
                            "id": None,
                            "cat": None,
                            "title": None,
                            "desc": None,
                            "data": None,
                            "data_count": 0,
                            "icon": icon_alert,
                            "emoji":  icon_emoji,
                            "friendly_name": "אין התרעות",
                        },
                    )
            else:
                self.log(f"Failed to retrieve data. Status code: {response.status_code}")
        except Exception as e:
            self.log(f"Error: {e}")
```
7. With a file editor, open the **/config/appdaemon/apps/apps.yaml** file and add/enter the following lines
```
orefalert:
  module: orefalert
  class: OrefAlert
```
8. Restart/Start the **AppDaemon** addon.

Once the AppDaemon addon is restarted, the new sensor *binary_sensor.oref_alert* will be created in Home Assistant. You can then use this sensor in automations or dashboards.

## Red Alert Trigger for Specific City, City Area*, or Cities with Similar Character Patterns:
(*) In Israel, 11 cities have been divided into multiple alert zones, each of which receives a separate alert only when there is a danger to the population living in that area. In other words, an alert may be activated only in a specific part of the city, where there is a danger of rocket or missile fire, and the rest of the city will not receive an alert, in order to reduce the number of times residents are required to enter a safe room when there is no danger to them. The cities that have been divided into multiple alert zones are Ashkelon, Beersheba, Ashdod, Herzliya, Hadera, Haifa, Jerusalem, Netanya, Rishon Lezion, Ramat Gan, and Tel Aviv-Yafo.
For city names/areas: https://www.oref.org.il//12481-he/Pakar.aspx

### Sample Trigger or Value Template for a Binary Sensor - Yavne city and not Gan-Yavne city:
To create a sensor that activates only when an attack occurs in a specific city that has similar character patterns in other city names, you should use the following approach. For example, if you want to create a sensor that activates when **only** "יבנה" and **not** "גן יבנה" is attacked, you can use the following code syntax.
```
{{ "יבנה" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
### Sample Trigger or Value Template for a Binary Sensor - Tel Aviv city center:
```
{{ "תל אביב - מרכז העיר" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
### Sample Trigger or Value Template for a Binary Sensor - Tel Aviv (all areas):
`
{{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב") }} 
`
## Red Alert Trigger for Particular Type of Alert:
The **'cat'** attribute defines the alert type, with a range from 1 to 13, where 1 represents a missile attack, 6 indicates unauthorized aircraft penetration and 13 indicates the infiltration of terrorists. You have the option to set up a binary sensor for a particular type of alert with or without any city or area of your choice.
### Sample trigger alert for unauthorized aircraft penetration
```
{{ state_attr('binary_sensor.oref_alert', 'cat') == '6' }}
```
### Sample trigger alert for unauthorized aircraft penetration in Nahal-Oz
```
{{ state_attr('binary_sensor.oref_alert', 'cat') == '6'
and "נחל עוז" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
You can generate a new binary sensor to monitor your city within the user interface under **'Settings' > 'Helpers' > 'Create' > 'Template' > 'Template binary sensor'** 

![b2](https://github.com/idodov/RedAlert/assets/19820046/ce3f4144-0051-40a5-ac2a-7e205e239c21)

## Usage *binary_sensor.oref_alert* for Home Assistant
### Lovelace Card Example
Displays whether there is an alert, the number of active alerts, and their respective locations.
![TILIM](https://github.com/idodov/RedAlert/assets/19820046/f8ad780b-7e64-4c54-ab74-79e7ff56b780)
```
type: markdown
content: >-
  <center><h3>{% if state_attr('binary_sensor.oref_alert', 'data_count') > 0 %}
  כרגע יש {% if state_attr('binary_sensor.oref_alert', 'data_count') > 1 %}{{
  state_attr('binary_sensor.oref_alert', 'data_count') }} התרעות פעילות{% elif
  state_attr('binary_sensor.oref_alert', 'data_count') == 1 %} התרעה פעילה אחת{%
  endif %}{% else %} אין התרעות פעילות{% endif %}</h3>

  {% if state_attr('binary_sensor.oref_alert', 'data_count') > 0 %}<h2>{{
  state_attr('binary_sensor.oref_alert', 'emoji') }} {{
  state_attr('binary_sensor.oref_alert', 'title') }}</h2>
  <h3>{{ state_attr('binary_sensor.oref_alert', 'data') }}</h3>
  **{{ state_attr('binary_sensor.oref_alert', 'desc') }}** {% endif %} </center>
title: Red Alert
```
## Automation Examples
You have the flexibility to generate various automated actions triggered by the binary sensor or its subsidiary sensors. As an example, one potential application is to dispatch alert messages to an LED matrix screen (for example, forwarding all alerts to the Ulanzi Smart Clock, which is based on ESPHome32 and features a screen).

![20231013_210149](https://github.com/idodov/RedAlert/assets/19820046/0f88c82c-c87a-4933-aec7-8db425f6515f)

### Send a notification to the phone (Home Assistant app) when there is an alert in Israel (all cities)
*(Change ```#your phone#``` to your entity name)*
```
alias: Notify attack
description: "Real-time Attack Notification"
trigger:
  - platform: state
    entity_id:
      - binary_sensor.oref_alert
    from: "off"
    to: "on"
condition: []
action:
  - service: notify.mobile_app_#your phone#
    data:
      message: "{{ state_attr('binary_sensor.oref_alert', 'data') }}"
      title: "{{ state_attr('binary_sensor.oref_alert', 'emoji') }} {{ state_attr('binary_sensor.oref_alert', 'title') }}"
mode: single
```
### Change the light color when there is an active alert in all areas of Tel Aviv
As another illustration, you can configure your RGB lights to change colors repeatedly while the alert is active.

![20231013_221552](https://github.com/idodov/RedAlert/assets/19820046/6e60d5ca-12a9-4fd2-9b10-bcb19bf38a6d)

*(Change ```light.#light-1#``` to your entity name)*
```
alias: Alert in TLV
description: "When an alert occurs in Tel Aviv, the lights will cyclically change to red and blue for a duration of 30 seconds, after which they will revert to their previous states"
trigger:
  - platform: template
    id: TLV
    value_template: >-
      {{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב") }}
condition: []
action:
  - service: scene.create
    data:
      scene_id: before_oref_alert
      snapshot_entities:
        - light.#light-1#
        - light.#light-2#
        - light.#light-3#
  - repeat:
      count: 30
      sequence:
        - service: light.turn_on
          data:
            color_name: blue
          target:
            entity_id: 
            - light.#light-1#
            - light.#light-2#
            - light.#light-3#
        - delay:
            hours: 0
            minutes: 0
            seconds: 0
            milliseconds: 500
        - service: light.turn_on
          data:
            color_name: red
          target:
            entity_id: 
            - light.#light-1#
            - light.#light-2#
            - light.#light-3#
        - delay:
            hours: 0
            minutes: 0
            seconds: 0
            milliseconds: 500
  - service: scene.turn_on
    data: {}
    target:
      entity_id: scene.before_oref_alert
mode: single
```

## Display Attributes
```
{{ state_attr('binary_sensor.oref_alert', 'title') }} #כותרת 
{{ state_attr('binary_sensor.oref_alert', 'data') }} #רשימת ישובים
{{ state_attr('binary_sensor.oref_alert', 'desc') }} #הסבר התגוננות
{{ state_attr('binary_sensor.oref_alert', 'cat') }} #קטגוריה
{{ state_attr('binary_sensor.oref_alert', 'id') }} #מספר ייחודי
{{ state_attr('binary_sensor.oref_alert', 'data_count') }} #מספר התרעות פעילות
{{ state_attr('binary_sensor.oref_alert', 'emoji') }} #אימוג'י עבור סוג התרעה

{{ state_attr('binary_sensor.oref_alert', 'prev_title') }} #כותרת אחרונה שהיתה פעילה
{{ state_attr('binary_sensor.oref_alert', 'prev_data') }} #רשימת ישובים אחרונים
{{ state_attr('binary_sensor.oref_alert', 'prev_desc') }} #הסבר התגוננות אחרון
{{ state_attr('binary_sensor.oref_alert', 'prev_cat') }} #קטגוריה אחרונה
{{ state_attr('binary_sensor.oref_alert', 'prev_data_count') }} #מספר התרעות בו זמנית קודמות
```

### Example Data (when there is active alert / state is on)
```
id: '133413399870000000'
cat: '1'
title: ירי רקטות וטילים
friendly_name:  ירי רקטות וטילים
data: אזור תעשייה הדרומי אשקלון
desc: היכנסו למרחב המוגן ושהו בו 10 דקות
data_count: 1
emoji: 🚀
```
### Example Data (when there is no active alert / state is off):
```
id: null
cat: null
title: null
desc: null
data: null
data_count: 0
icon: mdi:alert
friendly_name: אין התרעות
prev_cat: '1'
prev_title: ירי רקטות וטילים
prev_desc: היכנסו למרחב המוגן ושהו בו 10 דקות
prev_data: אזור תעשייה הדרומי אשקלון
prev_data_count: 1
emoji: 🚨
```
"prev_*" stores the most recent information when the sensor was active. These attributes will become available after the first alert.
