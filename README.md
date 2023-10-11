# Israeli Red Alert Service for Home Assistant (AppDaemon)
This script creates a Home Assistant binary sensor to track the status of Red Alerts in Israel. The sensor can be used in automations or to create sub-sensors/binary sensors from it.

Installing this script will create a new Home Assistant entity called ***binary_sensor.oref_alert***. This sensor will be **on** if there is a Red Alert in Israel, and **off** otherwise. The sensor also contains attributes that can be used for various purposes, such as category, ID, title, data, and description.

*I tried different methods in Home Assistant, but this script worked best for my needs.*

This code is based on and inspired by https://gist.github.com/shahafc84/5e8b62cdaeb03d2dfaaf906a4fad98b9

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
The script updates the sensors every *3 seconds*, or more frequently if you specify a shorter scan interval. 
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

# Create or update binary_sensor with attributes
                            self.set_state(
                                "binary_sensor.oref_alert",
                                state="on",
                                attributes={
                                    "id": data.get('id', None),
                                    "cat": data.get('cat', None),
                                    "title": alert_title,
                                    "desc": data.get('desc', None),
                                    "data": alerts_data,
                                    "last_changed": datetime.now().isoformat(),
                                    "prev_cat": data.get('cat', None),
                                    "prev_title": alert_title,
                                    "prev_desc": data.get('desc', None),
                                    "prev_data": alerts_data,
                                    "prev_last_changed": datetime.now().isoformat(),
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
                                    "last_changed": datetime.now().isoformat(),
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

# Usage *binary_sensor.oref_alert* for Home Assistant
### Example data (when there is active alert / state is on)
*prev_* saving data of the latest information when the sensor was on
```
id: '133413399870000000'
cat: '1'
title: ירי רקטות וטילים
data: אזור תעשייה הדרומי אשקלון
desc: היכנסו למרחב המוגן ושהו בו 10 דקות
prev_cat: '1'
prev_title: ירי רקטות וטילים
prev_desc: היכנסו למרחב המוגן ושהו בו 10 דקות
prev_data: אזור תעשייה הדרומי אשקלון
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
prev_data: כרם שלום
```
## Display attributes
```
{{ state_attr('binary_sensor.oref_alert', 'title') }} #כותרת 
{{ state_attr('binary_sensor.oref_alert', 'data') }} #רשימת ישובים
{{ state_attr('binary_sensor.oref_alert', 'desc') }} #הסבר התגוננות
{{ state_attr('binary_sensor.oref_alert', 'cat') }} #קטגוריה
{{ state_attr('binary_sensor.oref_alert', 'id') }} #מספר ייחודי

{{ state_attr('binary_sensor.oref_alert', 'prev_title') }} #כותרת אחרונה שהיתה פעילה
{{ state_attr('binary_sensor.oref_alert', 'prev_data') }} #רשימת ישובים אחרונים
{{ state_attr('binary_sensor.oref_alert', 'prev_desc') }} #הסבר התגוננות אחרון
{{ state_attr('binary_sensor.oref_alert', 'prev_cat') }} #קטגוריה אחרונה
```
## lovelace card example
Shows if there is an alert and where
```
type: conditional
conditions:
  - entity: binary_sensor.oref_alert
    state: 'on'
card:
  type: markdown
  content: |-
    <center>
    <big>{{ state_attr('binary_sensor.oref_alert', 'data') }}</big>

    **{{ state_attr('binary_sensor.oref_alert', 'desc') }}**
    </center>
  title: Red Alert
```

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
## Creative ways to use the *binary_sensor.oref_alert*
* Send a notification to your TV (while watching Netflix), phone, or other device.
* Send a message to a LED matrix screen or other display.
* Turn on or off lights, fans, or other devices.
* Play a sound or music.
* You can be creative and come up with other ways to use the *binary_sensor.oref_alert* to protect yourself and your family in the event of a Red Alert.
