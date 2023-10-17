# Israeli Red Alert Service for Home Assistant (AppDaemon)
***Not Official Pikud Ha-Oref***. Short Hebrew version can be found here: https://github.com/idodov/RedAlert/blob/main/hebrew.md

**This script creates a Home Assistant binary sensor to track the status of Red Alerts in Israel. The sensor can be used in automations or to create sub-sensors/binary sensors from it.**

The sensor provides a warning for all threats that the PIKUD HA-OREF alerts for, including red alerts rocket and missile launches, unauthorized aircraft penetration, earthquakes, tsunami concerns, infiltration of terrorists, hazardous materials incidents, unconventional warfare, and any other threat. When the alert is received, the nature of the threat will appear at the beginning of the alert (e.g., 'ירי רקטות וטילים').

Installing this script will create a Home Assistant entity called ***binary_sensor.oref_alert***. This sensor will be **on** if there is a Red Alert in Israel, and **off** otherwise. The sensor also includes attributes that can serve various purposes, including category, ID, title, data, description, the number of active alerts, and emojis.

### Why did I choose this method and not REST sensor?
Until we all have an official Home Assistant add-on to handle 'Red Alert' situations, there are several approaches for implementing the data into Home Assistant. One of them is creating a REST sensor and adding the code to the *configuration.yaml* file. However, using a binary sensor (instead of a 'REST sensor') is a better choice because it accurately represents binary states (alerted or not alerted), is more compatible with Home Assistant tools, and simplifies automation and user configuration. It offers a more intuitive and standardized approach to monitoring alert status. 

While the binary sensor's state switches to 'on' when there is an active alert in Israel behavior may not suit everyone, the sensor is designed with additional attributes containing data such as cities, types of attacks and more. These attributes make it easy to create customized sub-sensors to meet individual requirements. For example, you can set up specific sensors that activate only when an alarm pertains to a particular city or area.

I tried various methods in Home Assistant, but this script worked best for my needs.

*This code is based on and inspired by https://gist.github.com/shahafc84/5e8b62cdaeb03d2dfaaf906a4fad98b9*

### Sensor Capabilities
![Capture](https://github.com/idodov/RedAlert/assets/19820046/79adf8ff-1369-472b-a463-0c1fe82a9c4d)
![Capture--](https://github.com/idodov/RedAlert/assets/19820046/2cdee4bb-0849-4dc1-bb78-c2e282300fdd)
![000](https://github.com/idodov/RedAlert/assets/19820046/22c3336b-cb39-42f9-8b32-195d9b6447b2)

The icon and label of the sensor, presented on the dashboard via the default entity card, are subject to change dynamically with each new alert occurrence. To illustrate, in the event of a rocket attack, the icon depict a rocket.

Additionally, there exists a distinct emoji associated with each type of alert, which can be displayed alongside the alert message.

### Important Notice
* If you choose to follow this guide before any active alerts are present, you may notice that the sub-sensor you later create status displays as "unavailable". This happens because the sensor doesn't have any stored data to reference until the first alert occurs, at which point it will be resolved.
* This installation method relies on Supervised Add-ons, which are exclusively accessible if you've employed either the Home Assistant Operating System or the Home Assistant Supervised installation method (You can also opt to install the AppDaemon add-on through Docker. For additional details, please consult the following link: https://appdaemon.readthedocs.io/en/latest/DOCKER_TUTORIAL.html).
* Following a HA system reboot, the sensor's historical data will be erased, and your custom sensors will remain inaccessible until the initial alert occurs.
# Installation Instructions
1. Install the **AppDaemon** addon in Home Assistant by going to Settings > Add-ons > Ad-on-store and search for **AppDaemon**.
2. Once AppDaemon is installed, enable the **Auto-Start** and **Watchdog** options.
3. Go to the AppDaemon ***configuration*** page and add ```requests``` ***Python package*** under the Python Packages section.

![Capture1](https://github.com/idodov/RedAlert/assets/19820046/d4e3800a-a59b-4605-b8fe-402942c3525b)

4. **Start** the ad-on
5. In file editor open **/config/appdaemon/appdaemon.yaml** and make this changes under *appdeamon* section for `latitude: 31.9837528` & 
  `longitude: 34.7359077` & `elevation: 2` & `time_zone: Asia/Jerusalem`. 
*You can locate your own coordinates (latitude & longitude) here: https://www.latlong.net/*

*Make sure you have /config/secrets.yaml file. If not, create a file and save it empty, or remove `secrets: /config/secrets.yaml` line from the file appdaemon.yaml.*
```yaml
---
secrets: /config/secrets.yaml
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
5. Create a file named **orefalert.py** in the **/config/appdaemon/apps/** directory.
6. Paste the script code into the **orefalert.py** file and save it.
The script updates the sensors every *3 seconds*, or more frequently if you specify a shorter scan ```interval```. 
```orefalert.py
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
```yaml
orefalert:
  module: orefalert
  class: OrefAlert
```
8. Restart/Start the **AppDaemon** addon.

After restarting the AppDaemon addon, Home Assistant will generate the binary sensor named **binary_sensor.oref_alert**. You can incorporate this sensor into your automations and dashboards. *All sensor attributes will remain empty until an alert occurs, at which point they will be updated.*

## Red Alert Trigger for Cities with Similar Character Patterns, Specific City, and Cities With Multiple Alert Zones
In Israel, city names can exhibit similar patterns, such as "Yavne" and "Gan Yavne," so it's essential to consider this when creating a binary sensor based on the 'data' attribute using the SPIT function rather than the REGEX_SEARCH function. Also 11 cities have been subdivided into multiple alert zones, each receiving a separate alert only when there is a threat to the population residing in that specific area. This implies that there are various approaches to creating a sensor for a city as a whole and a specific area within it. The cities that have been divided into multiple alert zones include Ashkelon, Beersheba, Ashdod, Herzliya, Hadera, Haifa, Jerusalem, Netanya, Rishon Lezion, Ramat Gan, and Tel Aviv-Yafo. For a list of city names and areas, please refer to this link: https://www.oref.org.il//12481-he/Pakar.aspx

## Sample Trigger or Value Template for a Binary Sensor
**Please note that there is a primary method for creating sub-sensors, and it employs a distinct syntax compared to automation triggers. Here are a few examples to illustrate this.**
Which is the preferred option custom sensors or automation triggers? It varies based on your specific requirements. In a nutshell, if your goal is to display data as a distinct entity on a dashboard, then exclusively employ custom sensor code. However, if your primary objective is to facilitate automation triggers, you have the flexibility to utilize both approaches.

### Yavne city and not Gan-Yavne city
To create a sensor that activates only when an attack occurs in a specific city that has similar character patterns in other city names, you should use the following approach. For example, if you want to create a sensor that activates when **only** "יבנה" and **not** "גן יבנה" is attacked, you can use the following code syntax.

**Trigger for Automation**
```
{{ "יבנה" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```

**Custom Binary sensor / Helper**

When you're in the process of crafting a bespoke helper or sensor and encounter an absence of alerts, your custom helper or sensor will become inaccessible. To resolve this issue, opt for this specific code syntax instead.
```
{{ "יבנה" in state_attr('binary_sensor.oref_alert', 'prev_data').split(', ') and is_state('binary_sensor.oref_alert','on') }}
```
### Sample trigger alert for multiple cities or city areas
**Trigger for Automation**
```
{{ "אירוס" in state_attr('binary_sensor.oref_alert', 'data').split(', ')
 or "בית חנן" in state_attr('binary_sensor.oref_alert', 'data').split(', ')
 or "גן שורק" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
**Custom Binary sensor / Helper**
```
{{ ("אירוס" in state_attr('binary_sensor.oref_alert', 'prev_data').split(', ')
 or "בית חנן" in state_attr('binary_sensor.oref_alert', 'prev_data').split(', ')
 or "גן שורק" in state_attr('binary_sensor.oref_alert', 'prev_data').split(', '))
 and is_state('binary_sensor.oref_alert','on') }}
```

### Sample Trigger or Value Template for a Binary Sensor - Cities With Multiple Zones:
In cities with multiple zones, relying solely on the SPLIT function won't be effective if you've only defined the city name. If you need a sensor that triggers for all zones within the 11 cities divided into multiple alert zones, it's advisable to utilize the SEARCH_REGEX function instead of splitting the data.

**Trigger for Automation**
```
{{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב") }} 
```
**Custom Binary sensor / Helper**
```
{{ state_attr('binary_sensor.oref_alert', 'prev_data') | regex_search("תל אביב")
and is_state('binary_sensor.oref_alert','on') }}
```
If you want to trigger a specific area, use the SPLIT function and make sure to type the city name and area **exactly** as they appear in https://www.oref.org.il/12481-he/Pakar.aspx

**Trigger for Automation**
```
{{ "תל אביב - מרכז העיר" in state_attr('binary_sensor.oref_alert', 'data').split(', ')
```
**Custom Binary sensor / Helper**
```
{{ "תל אביב - מרכז העיר" in state_attr('binary_sensor.oref_alert', 'prev_data').split(', ')
and is_state('binary_sensor.oref_alert','on') }}
```
## Red Alert Trigger for Particular Type of Alert:
The **'cat'** attribute defines the alert type, with a range from 1 to 13, where 1 represents a missile attack, 6 indicates unauthorized aircraft penetration and 13 indicates the infiltration of terrorists. You have the option to set up a binary sensor for a particular type of alert with or without any city or area of your choice.
### Sample trigger alert for unauthorized aircraft penetration
**Trigger for Automation**
```
{{ state_attr('binary_sensor.oref_alert', 'cat') == '6' }}
```
**Custom Binary sensor / Helper**
```
{{ state_attr('binary_sensor.oref_alert', 'prev_cat') == '6' and is_state('binary_sensor.oref_alert','on') }}
```
### Sample trigger alert for unauthorized aircraft penetration in Nahal-Oz
**Trigger for Automation**
```yaml
{{ state_attr('binary_sensor.oref_alert', 'cat') == '6'
and "נחל עוז" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
**Custom Binary sensor / Helper**
```yaml
{{ (state_attr('binary_sensor.oref_alert', 'prev_cat') == '6'
and "נחל עוז" in state_attr('binary_sensor.oref_alert', 'prev_data').split(', ')) 
and is_state('binary_sensor.oref_alert','on') }}
```
## How to create a custom sub-sensor
You can generate a new binary sensor to monitor your city within the user interface under **'Settings' > 'Devices and Services' > 'Helpers' > 'Create Helper' > 'Template' > 'Template binary sensor'** 

**Ensure that you employ the accurate syntax!**

![QQQ](https://github.com/idodov/RedAlert/assets/19820046/3d5e93ab-d698-4ce0-b341-6bee0e641e05)

## Usage *binary_sensor.oref_alert* for Home Assistant
### Lovelace Card Example
Displays whether there is an alert, the number of active alerts, and their respective locations.
![TILIM](https://github.com/idodov/RedAlert/assets/19820046/f8ad780b-7e64-4c54-ab74-79e7ff56b780)

```yaml
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
You have the flexibility to generate various automated actions triggered by the binary sensor or its subsidiary sensors. As an example, one potential application is to dispatch alert messages to a LED matrix screen (in  pic: forwarding all alerts to the Ulanzi Smart Clock, which is based on ESPHome32 and features a screen).

![20231013_210149](https://github.com/idodov/RedAlert/assets/19820046/0f88c82c-c87a-4933-aec7-8db425f6515f)

### Send a notification to the phone (Home Assistant app) when there is an alert in Israel (all cities)
*(Change ```#your phone#``` to your entity name)*
```yaml
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
```yaml
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

### Get notification when it's safe
The "desc" attribute provides information on the duration in minutes for staying inside the safe room. This automation will generate a timer based on the data from this attribute.
Before implementing this automation, it's essential to create a TIMER helper.
1. Create a new **TIMER helper**. You can generate a new timer entity within the user interface under **'Settings' > 'Devices and Services' > 'Helpers' > 'Create Helper' > 'Timer'**
2. Name it "**Oref Alert**".
3. Create automation with your desire trigger, 
**for example:** *(change ```#your phone#``` to your entity name)*
```yaml
Alias: Safe to go out
description: "Notify on phone that it's safe to go outside"
mode: single
trigger:
  - platform: template
    value_template: >-
      {{ "תל אביב - מרכז העיר" in state_attr('binary_sensor.oref_alert',
      'data').split(', ') }}
condition: []
action:
  - service: timer.start
    data:
      duration: >-
        {{ (states.binary_sensor.oref_alert.attributes.desc |
        regex_findall_index('\d+') | int) * 60 }}
    target:
      entity_id: timer.oref_alert
  - service: notify.mobile_app_#your phone#
    data:
      title: ההתרעה הוסרה
      message: אפשר לחזור לשגרה
```


## Sensor Data Attributes
```yaml
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
### Example Data When There is Active Alert (state is on)
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
### Example Data When There is No Active Alert (state is off):
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

## Sensor History
Since it's a binary sensor based on attributes, Home Assistant history is only saved when the sensor transitions between on and off states. If you wish to maintain a complete history of all alerts, including the type of alert and the city, follow these steps:

1. Create a new **TEXT helper**. You can generate a new text entity to monitor history, within the user interface under **'Settings' > 'Devices and Services' > 'Helpers' > 'Create Helper' > 'Text'**
2. Name it "**Last Alert in Israel**".
3. Change the **maximum length** from 100 to **255**.
   
![111Capture](https://github.com/idodov/RedAlert/assets/19820046/1008a3ba-65a1-4de5-96cb-6bef5d2f85b0)

4. Develop a new automation that updates the text sensor each time a red alert occurs in Israel with the flexibility to create this automation for all cities or for a specific city or area, depending on your preferences.
You can use the following code (all alerts). 
```yaml
alias: Last Alert
description: "Saving the last alert to INPUT_TEXT (all alerts)"
mode: single
trigger:
  - platform: state
    entity_id:
      - binary_sensor.oref_alert
    to: "on"
condition: []
action:
  - service: input_text.set_value
    data:
      value: >-
        {{ state_attr('binary_sensor.oref_alert', 'title') }} - {{
        state_attr('binary_sensor.oref_alert', 'data') }}
    target:
      entity_id: input_text.last_alert_in_israel
```
*The sensor's logbook will become available following the initial alert.*

![00Capture](https://github.com/idodov/RedAlert/assets/19820046/283b7be8-7888-4930-a9b8-0ce48054e9d6)
