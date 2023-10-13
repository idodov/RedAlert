# Israeli Red Alert Service for Home Assistant (AppDaemon)
**This script creates a Home Assistant binary sensor to track the status of Red Alerts in Israel. The sensor can be used in automations or to create sub-sensors/binary sensors from it.**

Installing this script will create a new Home Assistant entity called ***binary_sensor.oref_alert***. This sensor will be **on** if there is a Red Alert in Israel, and **off** otherwise. The sensor also contains attributes that can be used for various purposes, such as category, ID, title, data, and description.

### Why did I choose this method?
Until we all have an official Home Assistant add-on to handle 'Red Alert' situations, there are several approaches for implementing the data into Home Assistant. One of them is creating a REST sensor and adding the code to the *configuration.yaml* file. However, using a binary sensor (instead of a 'REST sensor') is a better choice because it accurately represents binary states (alerted or not alerted), is more compatible with Home Assistant tools, and simplifies automation and user configuration. It offers a more intuitive and standardized approach to monitoring alert status. 

While the binary sensor's state switches to 'on' when there is an active alert in Israel behavior may not suit everyone, The sensor is designed with additional attributes containing data such as cities, types of attacks and more. These attributes make it easy to create customized sub-sensors to meet individual requirements. For example, you can set up specific sensors that activate only when an alarm pertains to a particular city or area.

I tried various methods in Home Assistant, but this script worked best for my needs.

*This code is based on and inspired by https://gist.github.com/shahafc84/5e8b62cdaeb03d2dfaaf906a4fad98b9*

![Capture](https://github.com/idodov/RedAlert/assets/19820046/79adf8ff-1369-472b-a463-0c1fe82a9c4d)
![Capture--](https://github.com/idodov/RedAlert/assets/19820046/2cdee4bb-0849-4dc1-bb78-c2e282300fdd)


The sensor's icon and name, which are displayed on the dashboard using the default entity card, are dynamic and will change every time there is an alert. For example, it may show a rocket icon during a rocket attack.

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


## Red Alert Trigger for Specific City or City-Area (*)
(*) In Israel, 11 cities have been divided into multiple alert zones, each of which receives a separate alert only when there is a danger to the population living in that area. In other words, an alert may be activated only in a specific part of the city, where there is a danger of rocket or missile fire, and the rest of the city will not receive an alert, in order to reduce the number of times residents are required to enter a safe room when there is no danger to them. The cities that have been divided into multiple alert zones are Ashkelon, Beersheba, Ashdod, Herzliya, Hadera, Haifa, Jerusalem, Netanya, Rishon Lezion, Ramat Gan, and Tel Aviv-Yafo.

**Example trigger or value template for binary sonsor - Tel Aviv city center:**

`
{{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב - מרכז העיר") }}
`

**Example trigger or value template for binary sonsor - Tel Aviv all areas:**

`
{{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב") }} 
`

For city names/areas: https://www.oref.org.il//12481-he/Pakar.aspx

# Usage *binary_sensor.oref_alert* for Home Assistant
### Example data (when there is active alert / state is on)
```
id: '133413399870000000'
cat: '1'
title: ירי רקטות וטילים
data: אזור תעשייה הדרומי אשקלון
desc: היכנסו למרחב המוגן ושהו בו 10 דקות
data_count: 1
```
## Example data (when there is no active alert / state is off):
```
id: null
cat: null
title: null
desc: null
data: null
prev_cat: '1'
prev_title: ירי רקטות וטילים
prev_desc: היכנסו למרחב המוגן ושהו בו 10 דקות
prev_data: מטולה
data_count: 0
prev_data_count: 1
```
"prev_*" stores the most recent information when the sensor was active. These attributes will become available after the first alert.
## Display attributes
```
{{ state_attr('binary_sensor.oref_alert', 'title') }} #כותרת 
{{ state_attr('binary_sensor.oref_alert', 'data') }} #רשימת ישובים
{{ state_attr('binary_sensor.oref_alert', 'desc') }} #הסבר התגוננות
{{ state_attr('binary_sensor.oref_alert', 'cat') }} #קטגוריה
{{ state_attr('binary_sensor.oref_alert', 'id') }} #מספר ייחודי
{{ state_attr('binary_sensor.oref_alert', 'data_count') }} #מספר התרעות פעילות

{{ state_attr('binary_sensor.oref_alert', 'prev_title') }} #כותרת אחרונה שהיתה פעילה
{{ state_attr('binary_sensor.oref_alert', 'prev_data') }} #רשימת ישובים אחרונים
{{ state_attr('binary_sensor.oref_alert', 'prev_desc') }} #הסבר התגוננות אחרון
{{ state_attr('binary_sensor.oref_alert', 'prev_cat') }} #קטגוריה אחרונה
{{ state_attr('binary_sensor.oref_alert', 'prev_data_count') }} # מספר התרעות בו זמנית קודמות
```
## lovelace card example
Shows if there is an alert, how many alerts are active and where
```
type: markdown
content: |-
    <center>
    {% if state_attr('binary_sensor.oref_alert', 'data_count') > 0 %}
      {% if state_attr('binary_sensor.oref_alert', 'data_count') > 1 %}
        {{ state_attr('binary_sensor.oref_alert', 'data_count') }} התרעות פעילות
      {% elif state_attr('binary_sensor.oref_alert', 'data_count') == 1 %}
        התרעה פעילה אחת
      {% endif %}
    {% else %}
      אין התרעות פעילות
    {% endif %}
     {% if state_attr('binary_sensor.oref_alert', 'data_count') > 0 %}
    <big>{{ state_attr('binary_sensor.oref_alert', 'data') }}</big>

    ** {{ state_attr('binary_sensor.oref_alert', 'desc') }}**
    {% endif %}
    </center>
title: Red Alert
```
## Automation examples
*Send notification when there is alert in Israel (all cities)*
```
alias: Notify attack
description: ""
trigger:
  - platform: state
    entity_id:
      - binary_sensor.oref_alert
    from: "off"
    to: "on"
condition: []
action:
  - service: notify.mobile_app_iphone15
    data:
      message: "{{ state_attr('binary_sensor.oref_alert', 'data') }}"
      title: "{{ state_attr('binary_sensor.oref_alert', 'title') }}"
mode: single
```
*Send notification when there is active alert in Tel Aviv (all areas)*
```
alias: Alert in TLV
description: ''
trigger:
  - platform: template
    id: "TLV"
    value_template: >-
      {{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב") }}
condition: []
action:
  - service: notify.mobile_app_iphone15
    data:
      message: "{{ state_attr('binary_sensor.oref_alert', 'data') }}"
      title: "{{ state_attr('binary_sensor.oref_alert', 'title') }}"
mode: single
```
You can create numerous automations triggered by the binary sensor or its associated sub-sensors. For instance, one of the possibilities is sending alert messages to an LED matrix screen. 

*As an example, forwarding all alerts to the Ulanzi Smart Clock, which is based on ESPHome32 and features a screen.*

![20231013_210149](https://github.com/idodov/RedAlert/assets/19820046/0f88c82c-c87a-4933-aec7-8db425f6515f)
