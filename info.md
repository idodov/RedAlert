The script will create 3 Home Assistant sensors, by the name you choose (in sensor_name, as exemplified here, the value is ‘red_alert’):
* `binary_sensor.red_alert` - will be on when there is an alarm anywhere in Israel
* `binary_sensor.red_alert_city` - will be on when there is an alarm in any city that is on the city_names list
* `text_input.red_alert` - will store all the historical data for viewing in the Home Assistant logbook

The sensor attributes contain several message formats to display or send as notifications.
You also have the flexibility to display or use any of the attributes of the sensor to create more sub-sensors from the main binary_sensor.red_alert

# Installation Instructions
1. Install the **AppDaemon** addon in Home Assistant by going to Settings > Add-ons > Ad-on-store and search for **AppDaemon**.
2. Once AppDaemon is installed, enable the **Auto-Start** and **Watchdog** options.
3. Go to the AppDaemon ***configuration*** page and add ```requests``` ***Python package*** under the Python Packages section.

![Capture1](https://github.com/idodov/RedAlert/assets/19820046/d4e3800a-a59b-4605-b8fe-402942c3525b)

4. **Start** the add-on
5. In file editor open **\addon_configs\appdaemon\appdaemon.yaml** and make this changes under *appdeamon* section for `latitude: 31.9837528` & 
  `longitude: 34.7359077` & `time_zone: Asia/Jerusalem`. 
*You can locate your own coordinates (latitude & longitude) here: https://www.latlong.net/*
```yaml
#/addon_configs/a0d7b954_appdaemon/appdaemon.yaml
---
secrets: /homeassistant/secrets.yaml
appdaemon:
  app_dir: /homeassistant/appdaemon/apps/
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

> [!IMPORTANT]  
> * In AppDaemon, make sure to specify the apps directory in `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml`.
> * Also, remember to transfer all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.

In the `/appdaemon/apps/apps.yaml` file, add the following code. Make sure to replace the values as described below and save the file:
| Parameter | Description | Example |
|---|---|---|
| `interval` | The interval in seconds at which the script runs | `2` |
| `timer` | The duration, in seconds, for which the sensor remains on after an alert | `120` |
| `sensor_name` | The name of the primary binary sensor in Home Assistant (`binary_sensor.#sensor_name#`) | `red_alert` |
| `test` | A boolean value indicating whether to check the sensor by sending text data | `False` |
| `city_names` | The names of the cities that activate the second binary sensor that will be named `binary_sensor.#sensor_name#_city`. You can add as many cities you want | `ראשון לציון - מערב, תל אביב - דרום` |

```yaml
# /appdaemon/apps/apps.yaml
---
red_alerts_israel:
  module: red_alerts_israel
  class: Red_Alerts_Israel
  interval: 2
  timer: 120
  sensor_name: "red_alert"
  test: False
  city_names: "שתולה, קרית שמונה, כיסופים, שלומי, ראש הנקרה ,תל אביב - מרכז העיר, שניר" 
```

## Sensor Attributes
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
