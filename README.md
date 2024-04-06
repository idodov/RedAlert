# Israeli Red Alert Service for Home Assistant (AppDaemon)
***Not Official Pikud Ha-Oref***

This script generates a series of binary sensors that provide alerts for all threats that PIKUD HA-OREF warns against. These threats include red alerts for rocket and missile launches, unauthorized aircraft intrusions, earthquakes, potential tsunamis, terrorist infiltrations, hazardous materials incidents, unconventional warfare, and other threats. When an alert is received, the nature of the threat is displayed at the beginning of the alert (for example, ‘ירי רקטות וטילים’).
____
### This script introduces four new entities in Home Assistant:
> [!NOTE]
> **You have the flexibility to define the sensor name as per your preference. The default sensor name value is `red_alert`.**
* `binary_sensor.red_alert`, which stores PIKUD HA-OREF data. This sensor activates whenever there is an alarm and deactivates otherwise. It can be utilized in automations or to create sub-sensors/binary sensors.
* `binary_sensor.red_alert_city`, which also stores PIKUD-HA-OREF data. However, it only activates if the city you define is included in the alarm cities.
* `input_text.red_alert`, which stores the latest alert information, primarily for historical reference.
* `input_boolean.red_alert`, which activate a false alert - design to test automations.

> [!TIP]
> To ensure the history of sensors is maintained after a restart in Home Assistant, it’s advisable to establish input text and boolean helpers. It’s best to do this prior to installation. Here’s how you can proceed:
> 1. Open `configuration.yaml`.
> 2. Add this lines and restart Home Assistant:
> ```yaml
> #/homeassistant/configuration.yaml
> input_text:
>   red_alert:
>     name: Last Alert in Israel
>     min: 0
>     max: 255
>
> input_boolean:
>   oref_alert_test:
>     name: Test Alert
>     icon: mdi:alert-circle
> ```

# Installation Instructions
1. Install the **AppDaemon** addon in Home Assistant by going to Settings > Add-ons > Ad-on-store and search for **AppDaemon**.
2. Once AppDaemon is installed, enable the **Auto-Start** and **Watchdog** options.
3. Go to the AppDaemon ***configuration*** page and add ```requests``` ***Python package*** under the Python Packages section.

![Capture1](https://github.com/idodov/RedAlert/assets/19820046/d4e3800a-a59b-4605-b8fe-402942c3525b)

4. **Start** the add-on
5. In file editor open **\addon_configs\appdaemon\appdaemon.yaml** and make the changes under *appdeamon* section as described:
> [!IMPORTANT]
> You can locate your own coordinates (latitude & longitude) here: https://www.latlong.net/
> *  `latitude: 31.9837528`
> *  `longitude: 34.7359077`
> *  `time_zone: Asia/Jerusalem`.
> *   If you install this script via HACS - **Specify the apps directory in `app_dir: /homeassistant/appdaemon/apps/`.**
>     * Also, remember to **transfer** all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
>   ```yaml
>     #/addon_configs/a0d7b954_appdaemon/appdaemon.yaml
>     ---
>     secrets: /homeassistant/secrets.yaml
>     appdaemon:
>         app_dir: /homeassistant/appdaemon/apps/ # If you install this script via HACS
>         latitude: 31.9837528
>         longitude: 34.7359077
>         elevation: 2
>         time_zone: Asia/Jerusalem
>         plugins:
>           HASS:
>             type: hass
>     http:
>         url: http://127.0.0.1:5050
>     admin:
>     api:
>     hadashboard:

### Manual Download
1. Download the Python file from [This Link](https://github.com/idodov/RedAlert/blob/main/apps/red_alerts_israel/red_alerts_israel.py).
2. Place the downloaded file inside the `appdaemon/apps` directory and proceed to the final step
### HACS Download
1. In Home Assistant: Navigate to `HACS > Automation`
   * If this option is not available, go to `Settings > Integrations > HACS > Configure` and enable `AppDaemon apps discovery & tracking`. After enabling, return to the main HACS screen and select `Automation`
2. Navigate to the `Custom Repositories` page and add the following repository as `Appdaemon`: `https://github.com/idodov/RedAlert/`
3. Return to the `HACS Automation` screen, search for `Red Alerts Israel`, click on `Download` and proceed to the final step
### Final Step
In the `/appdaemon/apps/apps.yaml` file, add the following code. **Make sure to replace the city_names values as described below and save the file:**

```yaml
#/appdaemon/apps/apps.yaml
red_alerts_israel:
  module: red_alerts_israel
  class: Red_Alerts_Israel
  interval: 2
  timer: 120
  sensor_name: "red_alert"
  save_2_file: True
  city_names:
    - תל אביב - מרכז העיר
    - כיסופים
```

| Parameter | Description | Example |
|---|---|---|
| `interval` | The interval in seconds at which the script runs | `2` |
| `timer` | The duration, in seconds, for which the sensor remains on after an alert | `120` |
| `sensor_name` | The name of the primary binary sensor in Home Assistant (`binary_sensor.#sensor_name#`) | `red_alert` |
| `save_2_file` | An option to save the alerts information in a text file | `True` |
| `city_names` | The names of the cities that activate the second binary sensor that will be named `binary_sensor.#sensor_name#_city`. You can add as many cities you want | `תל אביב - מרכז העיר` |
_______
## YOU ARE ALL SET!  
Upon restarting the AppDaemon add-on, Home Assistant will create four entities:
* The primary entity, `binary_sensor.red_alert`, activates when there’s a Red Alert in Israel and deactivates otherwise. This sensor also includes various attributes such as category, ID, title, data, description, the count of active alerts, and emojis.
* The second entity, `binary_sensor.red_alert_city`, stores PIKUD-HA-OREF data and only activates if the defined city is included in the alert cities.
* The third entity, `input_text.red_alert`, is mainly for recording historical alert data on the logbook screen. Please note that Home Assistant has a character limit of 255 for text entities. This means that during significant events, like large-scale attacks involving multiple areas or cities, some data might be truncated or lost. Hence, it’s not recommended to use this text input entity as a trigger for automations or to create sub-sensors from it.
* The final entity, `input_boolean.red_alert`, when toggled on, sends false data to the sensor, which activates it for the period you defined in the `timer` value.

![red-alerts-sensors](https://github.com/idodov/RedAlert/assets/19820046/e0e779fc-ed92-4f4e-8e36-4116324cd089)
> [!TIP]
> Use this trigger in automation `{{ (as_timestamp(now()) - as_timestamp(states.binary_sensor.red_alert.last_updated)) > 30 }}` to know when the script fails to run
## binary_sensor.red_alert Attribues
You can use any attribue from the sensor. For example, to show the title on lovelace card, use this code syntax: 
```{{ state_attr('binary_sensor.red_alert', 'title') }}```
| Attribute name | Means | Example |
| ----- | ----- | ----- |
| `count` | Counts the number of times the script has run since the last restart of Home Assistant. By monitoring this data, you can determine if and when the script is not running. | `12345` |
| `cat` | Category number. can be from 1 to 13 | `1` |
| `title` | Attack type in text | `ירי רקטות וטילים` |
| `data` | List of cities | `תל אביב - מרכז העיר` |
| `areas` | List of areas | `גוש דן` |
| `desc` | Explain what to do |  `היכנסו למרחב המוגן ושהו בו 10 דקות` |
| `duration` | How many seconds to be in the safe room | `600` |
| `id` | Id of the alert | `133413399870000000` |
| `data_count` | Number of cities that are attacked | `1` |
| `emoji` | Icon for type of attack | `🚀` |
| `prev_*` | Last data from each attribue | Stores the most recent information when the sensor was active |
| `alert` | One line full text  | `ירי רקטות וטילים ב־קו העימות - בצת, שלומי` |
| `alert_alt` | Breaking line full text | ` ירי רקטות וטילים/n* קו העימות: בצת, שלומי` |
| `alert_txt` | One line text | `קו העימות: בצת, שלומי` |
| `alert_wa` | Optimize text message to send via whatsapp | ![whatsapp](https://github.com/idodov/RedAlert/assets/19820046/817c72f4-70b1-4499-b831-e5daf55b6220) |
| `alert_tg` | Optimize text message to send via telegram |  |

**Example:**
```yaml
count: 237
id: 1234567890000000
cat: 1
title: ירי רקטות וטילים
desc: היכנסו למרחב המוגן ושהו בו 10 דקות
data: אבירים, פסוטה
areas: קו העימות
data_count: 2
duration: 600
last_changed: "2024-03-29T20:18:36.354614"
emoji: ⚠️
icon_alert: mdi:alert
prev_last_changed: "2024-03-29T20:18:36.354636"
prev_cat: 1
prev_title: ירי רקטות וטילים
prev_desc: היכנסו למרחב המוגן ושהו בו 10 דקות
prev_data: שלומי
prev_data_count: 1
prev_duration: 600
prev_areas: קו העימות
alert: "ירי רקטות וטילים ב־קו העימות: שלומי"
alert_alt: |-
  ירי רקטות וטילים
   * קו העימות: שלומי
alert_txt: "קו העימות: שלומי"
alert_wa: |-
  🚀 *ירי רקטות וטילים*
  > קו העימות
  שלומי

  _היכנסו למרחב המוגן ושהו בו 10 דקות_
friendly_name: All Red Alerts
icon: mdi:alert
alert_tg: |-
  🚀 **ירי רקטות וטילים**
  **__קו העימות__** — שלומי

  __היכנסו למרחב המוגן ושהו בו 10 דקות__
```
# Usage *Red Alert* for Home Assistant
## History File
The script stores the sensor data in a text file named `red_alert_history.txt`, located in the `\\homeassistant\config\www` directory. Each time an alert (including test alerts) is triggered, the file gets updated. You can directly access this file from your browser using the provided URL: [ http://homeassistant.local:8123/loca/red_alert_history.txt](http://homeassistant.local:8123/local/red_alert_history.txt)

![red-alert-txt](https://github.com/idodov/RedAlert/assets/19820046/70e28cd2-2aee-4519-a0d6-6ac415c703e7)
## Lovelace Card Example
Displays whether there is an alert, the number of active alerts, and their respective locations.

![TILIM](https://github.com/idodov/RedAlert/assets/19820046/f8ad780b-7e64-4c54-ab74-79e7ff56b780)
```yaml
type: markdown
content: >-
  <center><h3>{% if state_attr('binary_sensor.red_alert', 'data_count') > 0 %}
  כרגע יש {% if state_attr('binary_sensor.red_alert', 'data_count') > 1 %}{{
  state_attr('binary_sensor.red_alert', 'data_count') }} התרעות פעילות{% elif
  state_attr('binary_sensor.red_alert', 'data_count') == 1 %} התרעה פעילה אחת{%
  endif %}{% else %} אין התרעות פעילות{% endif %}</h3>

  {% if state_attr('binary_sensor.red_alert', 'data_count') > 0 %}<h2>{{
  state_attr('binary_sensor.red_alert', 'emoji') }} {{
  state_attr('binary_sensor.red_alert', 'title') }}</h2>
  <h3>{{ state_attr('binary_sensor.red_alert', 'data') }}</h3>
  **{{ state_attr('binary_sensor.red_alert', 'desc') }}** {% endif %} </center>
title: Red Alert
```
Using this script, you have the flexibility to include additional information, such as the **precise time the alert was triggered**.

![TILIMA](https://github.com/idodov/RedAlert/assets/19820046/4ba18dde-ae0c-4415-a55d-80ed0c010cbc)
![LAST](https://github.com/idodov/RedAlert/assets/19820046/ae52bc94-46ba-4cdb-b92b-36220500ee48)
```
type: markdown
content: >-
  <center><h3>{% if state_attr('binary_sensor.red_alert', 'data_count') > 0 %}
  כרגע יש {% if state_attr('binary_sensor.red_alert', 'data_count') > 1 %}{{
  state_attr('binary_sensor.red_alert', 'data_count') }} התרעות פעילות{% elif
  state_attr('binary_sensor.red_alert', 'data_count') == 1 %} התרעה פעילה אחת{%
  endif %}{% else %} אין התרעות פעילות{% endif %}</h3>

  {% if state_attr('binary_sensor.red_alert', 'data_count') > 0 %}<h2>{{
  state_attr('binary_sensor.red_alert', 'emoji') }} {{
  state_attr('binary_sensor.red_alert', 'title') }}</h2> <h3>{{
  state_attr('binary_sensor.red_alert', 'data') }}</h3> **{{
  state_attr('binary_sensor.red_alert', 'desc') }}** {% endif %}

  {% if state_attr('binary_sensor.red_alert', 'last_changed') |
  regex_match("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\d{2}:\d{2}.\d+$") %}

  {% set last_changed_timestamp = state_attr('binary_sensor.red_alert',
  'last_changed') | as_timestamp %}

  {% set current_date = now().date() %}

  {% if current_date == (last_changed_timestamp | timestamp_custom('%Y-%m-%d',
  true)
   | as_datetime).date() %}
   ההתרעה האחרונה נשלחה היום בשעה {{ last_changed_timestamp | timestamp_custom('%H:%M', true) }}
  {% else %}התרעה אחרונה נשלחה בתאריך {{ last_changed_timestamp |
  timestamp_custom('%d/%m/%Y', true) }}, בשעה {{ last_changed_timestamp |
  timestamp_custom('%H:%M', true) }}

  {% endif %}
  {% endif %}
  </center>
```
**Another nicer way:**

![3333](https://github.com/idodov/RedAlert/assets/19820046/438c0870-56e8-461b-a1e5-aa24122a71bc)
![000000](https://github.com/idodov/RedAlert/assets/19820046/2d6da8d4-2f84-46d4-9f52-baffdbd4b54b)
```
type: markdown
content: >-
  <ha-icon icon="{{ state_attr('binary_sensor.red_alert', 'icon')
  }}"></ha-icon> {% if state_attr('binary_sensor.red_alert', 'data_count') > 0
  %}כרגע יש {% if state_attr('binary_sensor.red_alert', 'data_count') > 1 %}{{
  state_attr('binary_sensor.red_alert', 'data_count') }} התרעות פעילות{% elif
  state_attr('binary_sensor.red_alert', 'data_count') == 1 %} התרעה פעילה אחת{%
  endif %}{% else %}אין התרעות פעילות{% endif %}{% if
  state_attr('binary_sensor.red_alert', 'data_count') > 0 %}

  <ha-alert alert-type="error" title="{{ state_attr('binary_sensor.red_alert',
  'title') }}">{{ state_attr('binary_sensor.red_alert', 'data') }}</ha-alert>

  <ha-alert alert-type="warning">{{ state_attr('binary_sensor.red_alert',
  'desc') }}</ha-alert>

  {% endif %}

  {% if state_attr('binary_sensor.red_alert', 'last_changed') |
  regex_match("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\d{2}:\d{2}.\d+$") %}

  {% set last_changed_timestamp = state_attr('binary_sensor.red_alert',
  'last_changed') | as_timestamp %}

  {% set current_date = now().date() %}{% if current_date ==
  (last_changed_timestamp | timestamp_custom('%Y-%m-%d', true)
   | as_datetime).date() %}<ha-alert alert-type="info">ההתרעה האחרונה נשלחה היום בשעה {{ last_changed_timestamp | timestamp_custom('%H:%M', true) }}
  {% else %}התרעה אחרונה נשלחה בתאריך {{ last_changed_timestamp |
  timestamp_custom('%d/%m/%Y', true) }}, בשעה {{ last_changed_timestamp |
  timestamp_custom('%H:%M', true) }}{% endif %}{% endif %}</ha-alert>
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
      - binary_sensor.red_alert
    from: "off"
    to: "on"
condition: []
action:
  - service: notify.mobile_app_#your phone#
    data:
      message: "{{ state_attr('binary_sensor.red_alert', 'data') }}"
      title: "{{ state_attr('binary_sensor.red_alert', 'title') }} {{ state_attr('binary_sensor.red_alert', 'areas') }}"
mode: single
```
### Change the light color when there is an active alert in your city
As another illustration, you can configure your RGB lights to change colors repeatedly while the alert is active.

![20231013_221552](https://github.com/idodov/RedAlert/assets/19820046/6e60d5ca-12a9-4fd2-9b10-bcb19bf38a6d)

*(Change ```light.#light-1#``` to your entity name)*
```yaml
alias: Alert in city
description: "When an alert occurs in your define city, the lights will cyclically change to red and blue for a duration of 30 seconds, after which they will revert to their previous states"
trigger:
- platform: state
  entity_id:
    - binary_sensor.red_alert_city
  from: "off"
  to: "on"
condition: []
action:
  - service: scene.create
    data:
      scene_id: before_red_alert
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
      entity_id: scene.before_red_alert
mode: single
```
### Get notification When it's safe
The "desc" attribute provides information on the duration in minutes for staying inside the safe room. This automation will generate a timer based on the data from this attribute.
Before implementing this automation, it's essential to create a TIMER helper.
1. Create a new **TIMER helper**. You can generate a new timer entity within the user interface under **'Settings' > 'Devices and Services' > 'Helpers' > 'Create Helper' > 'Timer'**
2. Name it "**Red Alert**".
3. Create automation with your desire trigger, 
**for example:** *(change ```#your phone#``` to your entity name)*
```yaml
Alias: Safe to go out
description: "Notify on phone that it's safe to go outside"
mode: single
trigger:
  - platform: template
    value_template: >-
      {{ "תל אביב - מרכז העיר" in state_attr('binary_sensor.red_alert',
      'data').split(', ') }}
condition: []
action:
  - service: timer.start
    data:
      duration: >-
        {{ state_attr('binary_sensor.red_alert_city', 'duration') }}
    target:
      entity_id: timer.red_alert
  - service: notify.mobile_app_#your phone#
    data:
      title: ההתרעה הוסרה
      message: אפשר לחזור לשגרה
```
### Creating Sub Sensors
While you need to specify the cities in which the secondary binary sensor will be activated, you also have the flexibility to define additional sub-sensors based on the main sensor. Here are a few examples of how you can do this.
> [!NOTE]
> To create a sensor that activates only when an attack occurs in a specific city that has similar character patterns in other city names, you should use the following approach. For example, if you want to create a sensor that activates when **only** "יבנה" and **not** "גן יבנה" is attacked, you can use the following code syntax.
> If you want to trigger a specific area, use the SPLIT function and make sure to type the city name and area **exactly** as they appear in https://www.oref.org.il/12481-he/Pakar.aspx
> ```
> {{ "תל אביב - מרכז העיר" in state_attr('binary_sensor.red_alert', 'data').split(', ') }}
> ```
#### Yavne city and not Gan-Yavne city
```
{{ "יבנה" in state_attr('binary_sensor.red_alert', 'data').split(', ') }}
```
#### Multiple cities or city areas
```
{{ "אירוס" in state_attr('binary_sensor.red_alert', 'data').split(', ')
 or "בית חנן" in state_attr('binary_sensor.red_alert', 'data').split(', ')
 or "גן שורק" in state_attr('binary_sensor.red_alert', 'data').split(', ') }}
```
### Cities With Multiple Zones:
In cities with multiple zones, relying solely on the SPLIT function won't be effective if you've only defined the city name. If you need a sensor that triggers for all zones within the 11 cities divided into multiple alert zones, it's advisable to utilize the SEARCH_REGEX function instead of splitting the data.
```
{{ state_attr('binary_sensor.red_alert', 'data') | regex_search("תל אביב") }} 
```
### Metropolitan Areas
Israel is segmented into 30 metropolitan areas, allowing you to determine the general status of nearby towns without the need to specify each one individually. To achieve this, you can utilize the "areas" attribute. Here's the list of the 30 metropolitan areas in Israel, presented in alphabetical order:

אילת, בקעה, בקעת בית שאן, גוש דן, גליל עליון, גליל תחתון, דרום הגולן, דרום הנגב, הכרמל, המפרץ, העמקים, השפלה, ואדי ערה, יהודה, ים המלח, ירושלים, ירקון, לכיש,  מנשה, מערב הנגב, מערב לכיש, מרכז הגליל, מרכז הנגב, עוטף עזה, 
ערבה, צפון הגולן, קו העימות, שומרון, שפלת יהודה ושרון
```
{{ "גוש דן" in state_attr('binary_sensor.red_alert', 'areas').split(', ') }}
```
### Red Alert Trigger for Particular Type of Alert:
The **'cat'** attribute defines the alert type, with a range from 1 to 13. You have the option to set up a binary sensor for a particular type of alert with or without any city or area of your choice.
| Cat (number) | Type of Alert |
| ---- | --- |
| 1 | Missle Attack |
| 6 | Unauthorized Aircraft Penetration |
| 13 | Infiltration of Terrorists |

**Trigger for Automation**
```
{{ state_attr('binary_sensor.red_alert', 'cat') == '6' }}
```
***Sample trigger alert for unauthorized aircraft penetration in Nahal-Oz***
```yaml
{{ state_attr('binary_sensor.red_alert', 'cat') == '6'
and "נחל עוז" in state_attr('binary_sensor.red_alert', 'data').split(', ') }}
```
