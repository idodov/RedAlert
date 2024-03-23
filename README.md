# Israeli Red Alert Service for Home Assistant (AppDaemon)
***Not Official Pikud Ha-Oref***
____
### This script introduces three new entities in Home Assistant:
> **You have the flexibility to define the sensor name as per your preference. The default sensor name value is `red_alert`.**
1. A binary sensor named `binary_sensor.red_alert`, which stores PIKUD HA-OREF data. This sensor activates whenever there is an alarm and deactivates otherwise. It can be utilized in automations or to create sub-sensors/binary sensors.
2. A binary sensor named `*binary_sensor.red_alert_city`, which also stores PIKUD-HA-OREF data. However, it only activates if the city you define is included in the alarm cities.
3. A text input entity named `input_text.red_alert`, which stores the latest alert information, primarily for historical reference.

The binary sensor provides a warning for all threats that the PIKUD HA-OREF alerts for, including red alerts rocket and missile launches, unauthorized aircraft penetration, earthquakes, tsunami concerns, infiltration of terrorists, hazardous materials incidents, unconventional warfare, and any other threat. When the alert is received, the nature of the threat will appear at the beginning of the alert (e.g., 'ירי רקטות וטילים').

# Installation Instructions
1. Install the **AppDaemon** addon in Home Assistant by going to Settings > Add-ons > Ad-on-store and search for **AppDaemon**.
2. Once AppDaemon is installed, enable the **Auto-Start** and **Watchdog** options.
3. Go to the AppDaemon ***configuration*** page and add ```requests``` ***Python package*** under the Python Packages section.

![Capture1](https://github.com/idodov/RedAlert/assets/19820046/d4e3800a-a59b-4605-b8fe-402942c3525b)

4. **Start** the add-on
5. In file editor open **\addon_configs\appdaemon\appdaemon.yaml** and make the changes under *appdeamon* section as described:
> [!IMPORTANT]
> In file editor open **\addon_configs\appdaemon\appdaemon.yaml** and make this changes under *appdeamon* section for. You can locate your own coordinates (latitude & longitude) here: https://www.latlong.net/
> *  `latitude: 31.9837528`
> *  `longitude: 34.7359077`
> *  `time_zone: Asia/Jerusalem`.
> *   If you install this script via HACS - **Specify the apps directory in `app_dir: /homeassistant/appdaemon/apps/`.**
>     * Also, remember to **transfer** all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
>     ```yaml
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
>     ```

### Manual Download
1. Download the Python file from [This Link](https://github.com/idodov/RedAlert/blob/main/apps/red_alerts_israel/red_alerts_israel.py).
2. Place the downloaded file inside the `appdaemon/apps` directory and proceed to the final step
### HACS Download
1. In Home Assistant: Navigate to `HACS > Automation`
   * If this option is not available, go to `Settings > Integrations > HACS > Configure` and enable `AppDaemon apps discovery & tracking`. After enabling, return to the main HACS screen and select `Automation`
2. Navigate to the `Custom Repositories` page and add the following repository as `Appdaemon`: `https://github.com/idodov/RedAlert/`
3. Return to the `HACS Automation` screen, search for `Red Alerts Israel`, click on `Download` and proceed to the final step
### Final Step
> [!TIP]
> Since Home Assistant won't preserve the history of the sensors after a restart, it's recommended to create an input text helper. Here are the steps to do this:
> 1. Open `configuration.yaml`.
> 2. Add this lines and restart Home Assistant:
> ```yaml
>   input_text:
>     red_alert:
>       name: Last Alert in Israel
>       min: 0
>       max: 255
> ```
In the `/appdaemon/apps/apps.yaml` file, add the following code. Make sure to replace the values as described below and save the file:
```yaml
red_alerts_israel:
  module: red_alerts_israel
  class: Red_Alerts_Israel
  interval: 2
  sensor_name: "red_alert"
  city_names: "שתולה, קרית שמונה, כיסופים, שלומי, ראש הנקרה ,תל אביב - מרכז העיר, שניר"
```
| Parameter | Description | Example |
|---|---|---|
| `interval` | The interval in seconds at which the script runs | `2` |
| `sensor_name` | The name of the primary binary sensor in Home Assistant (`binary_sensor.#sensor_name#`) | `red_alert` |
| `city_names` | The names of the cities that activate the second binary sensor that will be named `binary_sensor.#sensor_name#_city` | `תל אביב - מרכז העיר, שניר, מטולה` |
_______
## YOU ARE ALL SET!
After restarting the AppDaemon addon, Home Assistant will generate 3 entities. 
* The first entity called `binary_sensor.red_alert`, is the main sensor. This sensor will be **on** if there is a Red Alert in Israel, and **off** otherwise. The sensor also includes attributes that can serve various purposes, including category, ID, title, data, description, the number of active alerts, and emojis.
* The second entity is a binary sensor named `binary_sensor.red_alert_city`, which also stores PIKUD-HA-OREF data. However, it only activates if the city you define is included in the alarm cities.
* The third entity `input_text.red_alert` is primarily designed for historical alert records on the logbook screen. Please be aware that Home Assistant has an internal character limit of 255 characters for text entities. This limitation means that during significant events, like a large-scale attack involving multiple areas or cities, some data may be truncated or lost. Therefore, it is highly discouraged to use the text input entity as a trigger for automations or to create sub-sensors from it.

## binary_sensor.red_alert Attribues
You can use any attribue from the sensor. For example, to show the title on lovelace card, use this code syntax:

```{{ state_attr('binary_sensor.red_alert', 'title') }}```
| Attribute name | Means | Example |
| ----- | ----- | ----- |
| count | Counts the number of times the script has run since the last restart of Home Assistant. By monitoring this data, you can determine if and when the script is not running. | `12345` |
| cat | Category number. can be from 1 to 13 | `1` |
| title | Attack type in text | `ירי רקטות וטילים` |
| data | List of cities | `תל אביב - מרכז העיר` |
| areas | List of areas | `גוש דן` |
| desc | Explain what to do |  `היכנסו למרחב המוגן ושהו בו 10 דקות` |
| duration | How many seconds to be in the safe room | `600` |
| id | Id of the alert | 133413399870000000 |
| data_count | Number of cities that are attacked | `1` |
| emoji | Icon for type of attack | `🚀` |
| prev_* | Last data from each attribue | *stores the most recent information when the sensor was active. These attributes will become available after the first alert.* |

## Usage *binary_sensor.red_alert* for Home Assistant
### Lovelace Card Example
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
### Get notification 
## When script not running
Use this trigger in automation `{{ (as_timestamp(now()) - as_timestamp(states.binary_sensor.red_alert.last_updated)) > 30 }}` to know when the script fails to run
## When it's safe
The "desc" attribute provides information on the duration in minutes for staying inside the safe room. This automation will generate a timer based on the data from this attribute.
Before implementing this automation, it's essential to create a TIMER helper.
1. Create a new **TIMER helper**. You can generate a new timer entity within the user interface under **'Settings' > 'Devices and Services' > 'Helpers' > 'Create Helper' > 'Timer'**
2. Name it "*Red Alert**".
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
