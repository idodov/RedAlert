> [!IMPORTANT]  
> * In AppDaemon, make sure to specify the apps directory in `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml`.
> * Also, remember to transfer all files from `/addon_configs/a0d7b954_appdaemon/apps/` to `/homeassistant/appdaemon/apps/`.
```yaml
#/addon_configs/a0d7b954_appdaemon/appdaemon.yaml
---
secrets: /homeassistant/secrets.yaml
appdaemon:
  app_dir: /homeassistant/appdaemon/apps/
```
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
