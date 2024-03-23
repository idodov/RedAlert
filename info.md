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
| `sensor_name` | The name of the primary binary sensor in Home Assistant (`binary_sensor.#sensor_name#`) | `red_alert` |
| `city_names` | The names of the cities that activate the second binary sensor that will be named `binary_sensor.#sensor_name#_city` | `ראשון לציון - מערב, תל אביב - דרום` |

```yaml
# /appdaemon/apps/apps.yaml
red_alerts_israel:
  module: red_alerts_israel
  class: Red_Alerts_Israel
  interval: 2
  sensor_name: "red_alert"
  city_names: "שתולה, קרית שמונה, כיסופים, שלומי, ראש הנקרה ,תל אביב - מרכז העיר, שניר" 
```