# Red Alerts Israel
***Not Official Pikud Ha-Oref***

> Simple rocket-alert monitoring for Home Assistant via AppDaemon

Red Alerts Israel is an AppDaemon application for Home Assistant that connects to the official Israeli Home Front Command (Pikud HaOref) API. It fetches real-time "Tzeva Adom" rocket alerts and other hazards, making this information available via easy-to-use Home Assistant sensors.

This script monitors various hazards signaled by PIKUD HA-OREF, including missile/rocket fire, unauthorized aircraft, seismic activity, tsunami, terrorist incursions, chemical emergencies, and more. Upon receiving an alert, the specific threat type is indicated, for example, `ירי רקטות וטילים` for rocket and missile fire.

The application is designed for reliability and persistence, offering features like archiving alert details, state persistence via JSON backup, triggering Home Assistant native events, publishing messages via MQTT, and providing detailed sensor attributes for creating derived sensors and advanced automations.

---

## Key Features

*   **Polls** the official Israeli Home Front Command API every few seconds for live alerts.
*   **Creates** dedicated Home Assistant entities: main binary sensors, a text helper, a test boolean, and three detailed history sensors.
*   **Offers** flexible alert notification publishing via **MQTT** and native **Home Assistant events** triggered by new alert payloads.
*   **Saves** alert history (TXT, CSV) and the last active state (JSON) for persistence across restarts (optional).
*   **Generates** GeoJSON files for visualizing active and historical alert locations on the Home Assistant map (optional).
*   **Provides** specific binary sensors to indicate if an alert affects *your configured cities* or if it's a special "Pre-Alert" type.
*   **Tracks** the history of distinct alert events within a configurable time window.
*   **Generates** pre-formatted messages suitable for platforms like WhatsApp and Telegram based on cumulative window data.

---

## Entities Created

The script creates several Home Assistant entities, using your configured `sensor_name` as the base name (default: `red_alert`):

*   `binary_sensor.YOUR_SENSOR_NAME`: Indicates if *any* alert is currently active *nationwide*. This sensor stays `on` for the duration of the configured `timer` after the *last detected alert activity* in a sequence.
*   `binary_sensor.YOUR_SENSOR_NAME_city`: Indicates if `binary_sensor.YOUR_SENSOR_NAME` is `on` *and* the alert window includes one of the specific cities/areas you configured in `city_names`.
*   `binary_sensor.YOUR_SENSOR_NAME_pre_alert`: Indicates if a **pre alert** is currently active *nationwide*. This sensor turns `on`.
*   `binary_sensor.YOUR_SENSOR_NAME_city_pre_alert`: Indicates if a **pre alert** alert is currently active *and* affects one of your configured `city_names`. This sensor turns `on` only when an pre alert is received and processed AND the alert window includes one of your configured `city_names`.
*   `binary_sensor.YOUR_SENSOR_NAME_active_alert`: Indicates if an alert with a **category other than pre alert** is currently active *nationwide*. This sensor turns `on`.
*   `binary_sensor.YOUR_SENSOR_NAME_city_active_alert`: Indicates if an alert with a **category other pre alert** is currently active *and* affects one of your configured `city_names`. This sensor turns `on` when a pre alert is received and processed AND the alert window includes one of your configured `city_names`.
*   `input_text.YOUR_SENSOR_NAME`: Displays a summary of the *latest alert payload* received during an active alert window.
*   `input_boolean.YOUR_SENSOR_NAME_test`: Allows manual triggering of a fictitious test alert sequence.

Three additional history sensors track distinct alert *events* that occurred within the configured `hours_to_show` timeframe (after applying timer-based deduplication):

*   `sensor.YOUR_SENSOR_NAME_history_cities`: State is the count, attributes list unique cities alerted in the history window.
*   `sensor.YOUR_SENSOR_NAME_history_list`: State is the count, attributes list each distinct alert event entry in the history window.
*   `sensor.YOUR_SENSOR_NAME_history_group`: State is the count, attributes group distinct alert events by title, area, and city in the history window.

<details>
<summary>Detailed Binary Sensor Logic and Attributes</summary>

### Binary Sensor States (`binary_sensor.YOUR_SENSOR_NAME`, `_city`, `_pre_alert`, `_city_pre_alert`, `_active_alert`, `_city_active_alert`)

All six binary sensors are controlled by the script's polling and reset logic.

*   **When a new alert payload is received from the API:**
    *   `binary_sensor.YOUR_SENSOR_NAME` turns `on` (if not already) and its internal `timer` is reset.
    *   `binary_sensor.YOUR_SENSOR_NAME_city` turns `on` if any of the *accumulated* cities in the current alert window match your configured `city_names`, otherwise it stays `off`.
    *   If the `cat` value in the *latest incoming alert payload* is `13`:
        *   `binary_sensor.YOUR_SENSOR_NAME_pre_alert` turns `on`.
        *   `binary_sensor.YOUR_SENSOR_NAME_city_pre_alert` turns `on` if the `binary_sensor.YOUR_SENSOR_NAME_city` sensor is `on` (i.e., if configured cities are affected), otherwise it turns `off`.
        *   `binary_sensor.YOUR_SENSOR_NAME_active_alert` turns `off`.
        *   `binary_sensor.YOUR_SENSOR_NAME_city_active_alert` turns `off`.
    *   If the `cat` value in the *latest incoming alert payload* is *not* `13` (e.g., `cat=1` for rockets, which is the case for test alerts):
        *   `binary_sensor.YOUR_SENSOR_NAME_pre_alert` turns `off`.
        *   `binary_sensor.YOUR_SENSOR_NAME_city_pre_alert` turns `off`.
        *   `binary_sensor.YOUR_SENSOR_NAME_active_alert` turns `on`.
        *   `binary_sensor.YOUR_SENSOR_NAME_city_active_alert` turns `on` if the `binary_sensor.YOUR_SENSOR_NAME_city` sensor is `on`, otherwise it turns `off`.

*   **When the alert timer expires and confirms no active alerts are pending:**
    *   All six binary sensors (`_main`, `_city`, `_pre_alert`, `_city_pre_alert`, `_active_alert`, `_city_active_alert`) are explicitly set to `off`.

*   **On Script Initialization/Restart:**
    *   All six binary sensors are initialized to `off`.

### Shared Binary Sensor Attributes
When any of the six binary sensors are updated, they receive the *same* set of attributes. These attributes reflect the state and accumulated information for the *current alert window* since `binary_sensor.YOUR_SENSOR_NAME` last turned `on`. When `binary_sensor.YOUR_SENSOR_NAME` is `off`, they show default/empty values or the `prev_*` values from the window that just ended, providing context about the *last* alert incident.

| Attribute name      | Description                                                                                                                                                                                               | Example                                    |
| :------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------- |
| `active_now`        | `true` when `binary_sensor.YOUR_SENSOR_NAME` is `on`, `false` when `off`. Mirrors the main sensor state.                                                                                                     | `false`                                    |
| `script_status`     | The operational status of the AppDaemon script (`initializing`, `running`, `error`, `terminated`). Useful for monitoring the script itself.                                                                | `running`                                  |
| `id`                | Unique ID of the *latest* alert payload received during the current window.                                                                                                                               | `1721993400123456`                         |
| `cat`               | Category number (0-14) of the *latest* alert payload. Corresponds to alert type (e.g., 1 for rockets, 13 for special update).                                                                            | `1`                                        |
| `title`             | Title/Type of the *latest* alert payload (e.g., "ירי רקטות וטילים").                                                                                                                                      | `ירי רקטות וטילים`                        |
| `desc`              | Recommended action description from the *latest* alert payload (e.g., "היכנסו למרחב המוגן ושהו בו 10 דקות").                                                                                                | `היכנסו למרחב המוגן ושהו בו 10 דקות`      |
| `special_update`    | `true` if the `cat` of the *latest* alert payload is 13, `false` otherwise. This attribute mirrors the state logic of the `*_pre_alert` sensors.                                                         | `false`                                    |
| `areas`             | Comma-separated string of *all areas* affected by *any payload* within the current active window.                                                                                                         | `גוש דן, קו העימות`                        |
| `cities`            | A sorted list of all unique original city names affected by *any payload* within the current active window.                                                                                             | `['אור יהודה', 'תל אביב - מרכז העיר']`    |
| `data`              | Comma-separated string of all unique original city names affected during the current active window. May be truncated if very long.                                                                      | `אור יהודה, תל אביב - מרכז העיר, חולון...` |
| `data_count`        | Count of unique original city names affected during the current active window.                                                                                                                            | `5`                                        |
| `duration`          | Recommended duration (in seconds) to stay in a safe room, extracted from the `desc` of the *latest* alert payload.                                                                                       | `600`                                      |
| `icon`              | MDI icon string based on the `cat` of the *latest* alert payload.                                                                                                                                         | `mdi:rocket-launch`                        |
| `emoji`             | Emoji character based on the `cat` of the *latest* alert payload.                                                                                                                                         | `🚀`                                       |
| `alerts_count`      | The number of individual alert *payloads* received and processed by the script during the current active alert window (since the main sensor last went `on`).                                                | `3`                                        |
| `last_changed`      | ISO timestamp string (`YYYY-MM-DDTHH:MM:SS.ffffff`) when *this sensor's state or any of its attributes were last updated*.                                                                                | `"2024-07-25T10:30:00.123456"`             |
| `my_cities`         | A sorted list of the city names exactly as configured in your `apps.yaml` `city_names` list.                                                                                                              | `['חיפה - מפרץ', 'תל אביב - מרכז העיר']`   |
| `alert`             | One-line summary string: `[Title] - [Areas]: [Cities]`. Uses cumulative window data.                                                                                                                      | `ירי רקטות וטילים - גוש דן, קו העימות: ...` |
| `alert_alt`         | Multi-line summary string: `[Title]\n* [Area]: [Cities]\n* [Area]: [Cities]...`. Uses cumulative window data.                                                                                             | ` ירי רקטות וטילים\n* גוש דן: תל אביב...\n* קו העימות: כיסופים` |
| `alert_txt`         | One-line string listing Areas and Cities affected in the current window: `[Area]: [Cities], [Area]: [Cities]...`.                                                                                           | `גוש דן: תל אביב - מרכז העיר, אור יהודה...` |
| `alert_wa`          | Multi-line formatted message optimized for WhatsApp, summarizing alerts by type and area based on cumulative window data.                                                                                   |  ![whatsapp](https://github.com/idodov/RedAlert/assets/19820046/817c72f4-70b1-4499-b831-e5daf55b6220)  |
| `alert_tg`          | Multi-line formatted message optimized for Telegram, summarizing alerts by type and area based on cumulative window data.                                                                                   |                                            |
| `prev_cat`          | Category number of the alert from the *previous* alert window (before the main sensor last went `off` and then `on` again).                                                                            | `1`                                        |
| `prev_title`        | Title of the alert from the *previous* alert window.                                                                                                                                                        | `ירי רקטות וטילים`                        |
| `prev_desc`         | Description from the *previous* alert window.                                                                                                                                                             | `היכנסו למרחב המוגן ושהו בו 10 דקות`      |
| `prev_areas`        | Areas from the *previous* alert window.                                                                                                                                                                   | `קו העימות`                                |
| `prev_cities`       | List of cities from the *previous* alert window.                                                                                                                                                          | `['שלומי']`                                |
| `prev_data`         | Comma-separated cities string from the *previous* alert window.                                                                                                                                           | `שלומי`                                    |
| `prev_data_count`   | City count from the *previous* alert window.                                                                                                                                                              | `1`                                        |
| `prev_duration`     | Duration from the *previous* alert window.                                                                                                                                                                | `600`                                      |
| `prev_last_changed` | ISO timestamp when the *previous* alert window became active (when the main sensor state last went `on` for that window).                                                                                        | `"2024-07-25T10:15:05.987654"`             |
| `prev_alerts_count` | Sequence count from the *previous* alert window.                                                                                                                                                          | `2`                                        |
| `prev_special_update` | Special update flag status (`cat==13`) from the *previous* alert window.                                                                                                                                | `false`                                    |
</details>

### `input_text.YOUR_SENSOR_NAME`
*   **State**: Holds a brief summary (up to 255 characters) derived from the *latest alert payload's* title, area, and cities (`input_text_state` attribute in the script).
*   **Use**: Primarily intended for simple dashboard displays or logbook entries.
*   **Important**: This sensor only updates its state when the primary binary sensor (`binary_sensor.YOUR_SENSOR_NAME`) transitions from `off` to `on`, or while it remains `on` AND the script receives a new alert payload. It goes blank or shows "אין התרעות" when the primary sensor turns `off`. Due to its character limit and update behavior, it is **not** recommended for critical automation triggers or storing the full alert details. Use the binary sensor attributes for that.

### Dedicated History Sensors (`sensor.YOUR_SENSOR_NAME_history_*`)
These sensors provide structured access to a list of distinct alert *events* that occurred within the past `hours_to_show` timeframe. An "event" here is a single alert payload that is deemed unique based on its title, city, and area, and not within the `timer` duration of a previously recorded event of the same type/location.

*   **`sensor.YOUR_SENSOR_NAME_history_cities`**:
    *   **State**: The count of unique city names that appeared in *any* distinct history event within the window.
    *   **Attribute**: `cities_past_N_h` – A sorted list of the unique original city names. Includes `script_status`.
*   **`sensor.YOUR_SENSOR_NAME_history_list`**:
    *   **State**: The total count of distinct alert events within the history window.
    *   **Attribute**: `last_N_h_alerts` – A list of dictionaries, where each dictionary represents one distinct event with keys `{ title, city, area, time }`. Includes `script_status`. Note: `time` is a string formatted as 'YYYY-MM-DD HH:MM:SS'.
*   **`sensor.YOUR_SENSOR_NAME_history_group`**:
    *   **State**: Same count as `sensor.YOUR_SENSOR_NAME_history_list`.
    *   **Attribute**: `last_N_h_alerts_group` – A nested dictionary structure `{ title: { area: [ { city, time }, ... ], ... }, ... }` grouping the distinct events. Includes `script_status`. Note: `time` in this attribute is a string formatted as 'HH:MM:SS'.

</details>

---

# Installation Instructions

To ensure the states of your `input_text` and `input_boolean` helpers persist across Home Assistant restarts, create them manually beforehand:
1.  Open your Home Assistant `configuration.yaml` file using the File Editor add-on or similar method.
<details>
<summary>2. Add Helpers and File Access to configuration.yaml</summary>

Add the configuration below under `homeassistant:`, `input_text:`, and `input_boolean:`. Adjust the `sensor_name` if you plan to use a different base name than `red_alert`.

```yaml
#/config/configuration.yaml

homeassistant:
  # ... other homeassistant settings ...

  # Required for GeoJSON integration to access files from /config/www
  # Add the URL(s) Home Assistant uses to access itself locally
  allowlist_external_urls:
    - http://<YOUR_HOME_ASSISTANT_IP_OR_HOSTNAME>:8123  # Replace with your actual HA access URL(s)
    - http://homeassistant.local:8123 # Example using the default mDNS name

  # Optional: Allow File Editor or other addons to access www if needed
  # This entry *might* be needed if your add-on config paths are non-standard
  # or you have issues accessing /config/www from other add-ons.
  # allowlist_external_dirs:
  #  - "/config/www"

input_text:
  # Matches default sensor_name. Change 'red_alert' if you use a different sensor_name
  red_alert:
    name: Last Alert Summary
    min: 0 # Minimum length
    max: 255 # Maximum length for input_text state

input_boolean:
  # Matches default sensor_name. Change 'red_alert' if you use a different sensor_name
  red_alert_test:
    name: Trigger Test Alert
    icon: mdi:alert-circle
```
</details>

3.  Install the **AppDaemon** addon in Home Assistant: Navigate to `Settings` > `Add-ons` > `Add-on store` > Search for "AppDaemon" and install it.
4.  Once installed, configure AppDaemon: Enable **Show in sidebar**, **Auto-start**, and **Watchdog**. Apply the configuration changes.
5.  **Start** the AppDaemon add-on.
6.  Using a file editor (like the File Editor add-on), edit the AppDaemon configuration file. This is typically located at `/addon_configs/a0d7b954_appdaemon/appdaemon.yaml`.

> [!TIP]
>
> If using the File Editor add-on and unable to access `/addon_configs`, you might need to disable `Enforce Basepath` in its configuration: Go to `Settings` > `Add-ons` > `File Editor` > `Configuration` and toggle the option off. Remember to re-enable it later if you prefer the security.

> [!IMPORTANT]
>
> *   The `latitude`, `longitude`, `elevation`, and `time_zone` settings here are for AppDaemon itself and affect how AppDaemon handles time-based functions. They are **not** used by the Red Alerts Israel script to determine your location for filtering cities.
> *   If you installed via **HACS**, ensure `app_dir: /homeassistant/appdaemon/apps/` is correctly set in your `appdaemon.yaml`. This tells AppDaemon where to find the script files downloaded by HACS. If you installed manually into `/config/appdaemon/apps`, this path might be `/config/appdaemon/apps`. Check your AppDaemon add-on documentation for the correct default if unsure.

<details>
<summary>Configure appdaemon.yaml</summary>

```yaml
#/addon_configs/a0d7b954_appdaemon/appdaemon.yaml
---
# secrets: /homeassistant/secrets.yaml # Uncomment this line if you use secrets
appdaemon:
  # Set app_dir to where AppDaemon finds your app files.
  # For HACS installs, this is typically:
  app_dir: /homeassistant/appdaemon/apps/

  # IMPORTANT - Add your geolocation from https://www.latlong.net/
  latitude: 31.9837528
  longitude: 34.7359077
  elevation: 2
  time_zone: Asia/Jerusalem

  plugins:
    HASS:
      type: hass

http:
  timeout: 30 # Recommended timeout
admin:
api:
hadashboard:
```
</details>

You can download the script file manually or via HACS. Using HACS is recommended as it simplifies future updates.

### Manual Download
1.  Download the `red_alerts_israel.py` script file directly from the GitHub repository: [Download Script](https://raw.githubusercontent.com/idodov/RedAlert/main/apps/red_alerts_israel/red_alerts_israel.py).
2.  Using the File Editor add-on or similar, create a new folder inside your AppDaemon apps directory (usually `/config/appdaemon/apps/` or `/homeassistant/appdaemon/apps/`). Name the folder `red_alerts_israel`.
3.  Place the downloaded `red_alerts_israel.py` file inside the `/red_alerts_israel/` folder you just created.
4.  Proceed to the final step.

### HACS Download
1.  In Home Assistant: Navigate to `Settings` > `Integrations` > `HACS` > `Configure` and enable `AppDaemon apps discovery & tracking`. After enabling, return to the main HACS screen.
2.  Click the `...` menu in the top right and select `Custom repositories`.
3.  Add `https://github.com/idodov/RedAlert/` as the repository URL. Select `AppDaemon` as the Category. Click `Add`.
4.  Go back to the main HACS page, search for `Red Alerts Israel`, and click on it.
5.  Click the `Download` button on the integration page.
6.  Proceed to the final step.

### Final Step: Configure `apps.yaml`
In your AppDaemon applications configuration file, typically located at `/config/appdaemon/apps/apps.yaml`, add the following configuration block.

> [!IMPORTANT]
> **`city_names` List**: The names in the `city_names` list **must exactly match** the names defined by PIKUD HA-OREF, including spelling and special characters like hyphens or quotation marks. Consult the official list here: [PIKUD HA-OREF City Names List](https://github.com/idodov/RedAlert/blob/main/cities_name.md). Using incorrect names means the `binary_sensor.YOUR_SENSOR_NAME_city` sensor will **not** turn on for those locations.

<details>
<summary>Configure apps.yaml</summary>

```yaml
#/config/appdaemon/apps/apps.yaml

# Make sure this entry matches your app directory name (e.g., red_alerts_israel folder name)
red_alerts_israel: # This is the AppDaemon app name (used in logs)
  module: red_alerts_israel      # Name of the Python file without the .py extension
  class: Red_Alerts_Israel       # Name of the main class within the Python file

  # --- Core Settings ---
  interval: 5                   # (Seconds) How often the script checks the Oref API. Default: 5. Shorter intervals provide faster updates.
  timer: 120                    # (Seconds) How long binary_sensor.#sensor_name# and binary_sensor.#sensor_name#_city stay 'on' *after the last alert activity is detected* in an incident window. Default: 120.
  sensor_name: "red_alert"      # Base name for all created Home Assistant entities (e.g., binary_sensor.red_alert). Match this in configuration.yaml if using default helpers. Default: "red_alert".

  # --- History & Saving ---
  save_2_file: True             # Set to True to enable saving history (.txt, .csv), GeoJSON files (latest & 24h), and JSON state backup to the '/config/www' folder. Default: True. Requires www folder to be writeable.
  hours_to_show: 12             # (Hours) The duration for the dedicated history sensors (sensor.#sensor_name#_history_*). Alerts older than this are excluded from history attributes. Default: 4.

  # --- Optional Features ---
  mqtt: False                   # (Boolean or String) Set True to publish JSON alert payload via MQTT to 'home/[sensor_name]/event' topic when a new alert payload is received. Set to a custom topic string (e.g., "notifications/alerts") for a different topic. Default: False.
  event: True                   # (Boolean) Set True to fire a native Home Assistant event '[sensor_name]_event' with the full alert payload when a new alert payload is received. Default: True.

  # --- Location Specific ---
  city_names:                   # List of exact city/area names you want to monitor for binary_sensor.#sensor_name#_city. Case-sensitive.
     - "אזור תעשייה צפוני אשקלון"  # Example: Ashkelon Industrial Zone North
     - "חיפה - מפרץ"                # Example: Haifa Bay
     - "תל אביב - מרכז העיר"        # Example: Tel Aviv - City Center
     # Add more city names here exactly as they appear in cities_name.md
     - "אשדוד - א,ב,ד,ה"
     - "כיסופים"

```

| Parameter       | Description                                                                                                                                                                                                                                                                                          | Example                         | Default Value |
| :-------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------ | :------------ |
| `interval`      | The interval in seconds at which the script polls the API. Shorter intervals mean faster updates but more frequent API calls. Must be > 1.                                                                                                                                                         | `3`                             | `5`           |
| `timer`         | The duration, in seconds, for which the main binary sensors (`binary_sensor.YOUR_SENSOR_NAME`, `binary_sensor.YOUR_SENSOR_NAME_city`) remain `on` after the *last alert activity is detected* in a single alert window. After this time *and* confirmation of no active alerts, sensors turn `off`. | `180`                           | `120`         |
| `sensor_name`   | The base name for all created Home Assistant entities (e.g., `binary_sensor.YOUR_NAME`). Choose a unique name. Ensure it matches the name used for the `input_text` and `input_boolean` helpers in `configuration.yaml`.                                                                     | `"tseva_adom"`                  | `"red_alert"` |
| `save_2_file`   | Set to `True` to enable saving history files (.txt, .csv), GeoJSON files (`latest` and `history`), and a JSON state backup file to the `/config/www` directory. Requires write permissions for the AppDaemon user/container.                                                                       | `True`                          | `True`        |
| `hours_to_show` | The duration, in hours, that the dedicated history sensors (`sensor.YOUR_SENSOR_NAME_history_*`) should track and display distinct past alert events. Alerts older than this window are pruned from history attributes.                                                                                 | `24`                            | `4`           |
| `mqtt`          | Set to `True` to publish the full JSON alert payload via MQTT when a *new alert payload* is received from the API. The default topic is `home/YOUR_SENSOR_NAME/event`. Can be set to a string (e.g., `"your/custom/topic"`) for a different topic.                                                  | `True` or `"alerts/rocket"`     | `False`       |
| `event`         | Set to `True` to fire a native Home Assistant event (`YOUR_SENSOR_NAME_event`) with the full alert payload when a *new alert payload* is received from the API.                                                                                                                                  | `True`                          | `True`           |
| `city_names`    | A list of the exact city or area names you want to monitor for the city-specific sensor (`binary_sensor.YOUR_SENSOR_NAME_city`). Names must match the official PIKUD HA-OREF list precisely ([cities_name.md](https://github.com/idodov/RedAlert/blob/main/cities_name.md)). Can be an empty list `[]`. | `תל אביב - מרכז העיר` | `[]`          |

</details>

7.  Restart the AppDaemon add-on after saving `apps.yaml`. Check the AppDaemon logs (`Settings` > `Add-ons` > `AppDaemon` > `Log`) for errors during initialization.


## Home Assistant Entities Summary

After successful installation and configuration, Home Assistant will expose several new entities based on your `sensor_name` (default: `red_alert`):

*   `binary_sensor.red_alert`: State is `on` during *any* alert nationwide, `off` otherwise (controlled by `timer`). Attributes contain latest and cumulative data for the current window.
*   `binary_sensor.red_alert_city`: State is `on` only if an alert includes one of your `city_names`. Attributes contain same data as the main sensor for the current window.
*   `input_text.red_alert`: State shows a brief summary of the *latest alert payload* when a sensor is `on`.
*   `input_boolean.red_alert_test`: Toggle this to `on` to manually trigger a test alert sequence. It will turn `off` automatically when the test completes.
*   `sensor.red_alert_history_cities`: State is the count of unique cities in the history window (`hours_to_show`). Attribute `cities_past_N_h` lists them.
*   `sensor.red_alert_history_list`: State is the count of distinct alert *events* in the history window. Attribute `last_N_h_alerts` lists the events.
*   `sensor.red_alert_history_group`: State is the count of distinct alert *events* in the history window. Attribute `last_N_h_alerts_group` provides a grouped structure.


</details>

## Attribute Reference
The primary binary sensors (`binary_sensor.YOUR_SENSOR_NAME` and `binary_sensor.YOUR_SENSOR_NAME_city`) expose detailed attributes about the current alert window. You can access any attribute in automations, templates, or Lovelace cards using `state_attr('ENTITY_ID', 'attribute_name')`. For example: ```{{ state_attr('binary_sensor.red_alert', 'title') }}```

<details>
<summary>Full List of Sensor Attributes for `binary_sensor.YOUR_SENSOR_NAME` and `binary_sensor.YOUR_SENSOR_NAME_city`</summary>

These attributes reflect the *current state of the alert window* since the sensor last turned `on`. When the sensor is `off`, they show default/empty values or the `prev_*` values from the window that just ended.

| Attribute name      | Description                                                                                                                                                                                               | Example                                    |
| :------------------ | :-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------------- |
| `active_now`        | `true` when the sensor state is `on`, `false` when `off`. Mirrors the sensor state.                                                                                                                       | `false`                                    |
| `script_status`     | The operational status of the AppDaemon script (`initializing`, `running`, `error`, `terminated`). Useful for monitoring the script itself.                                                                | `running`                                  |
| `id`                | Unique ID of the *latest* alert payload received during the current window.                                                                                                                               | `1721993400123456`                         |
| `cat`               | Category number (1-13) of the *latest* alert payload. Corresponds to alert type (e.g., 1 for rockets).                                                                                                    | `1`                                        |
| `title`             | Title/Type of the *latest* alert payload (e.g., "ירי רקטות וטילים").                                                                                                                                      | `ירי רקטות וטילים`                        |
| `desc`              | Recommended action description from the *latest* alert payload (e.g., "היכנסו למרחב המוגן ושהו בו 10 דקות").                                                                                                | `היכנסו למרחב המוגן ושהו בו 10 דקות`      |
| `special_update`    | `true` if the *latest* alert payload is a "special update" from Pikud HaOref, `false` otherwise.                                                                                                          | `false`                                    |
| `areas`             | Comma-separated string of *all areas* affected by *any payload* within the current active window.                                                                                                         | `גוש דן, קו העימות`                        |
| `cities`            | A sorted list of all unique original city names affected by *any payload* within the current active window.                                                                                             | `['אור יהודה', 'תל אביב - מרכז העיר']`    |
| `data`              | Comma-separated string of all unique original city names affected during the current active window. May be truncated if very long.                                                                      | `אור יהודה, תל אביב - מרכז העיר, חולון...` |
| `data_count`        | Count of unique original city names affected during the current active window.                                                                                                                            | `5`                                        |
| `duration`          | Recommended duration (in seconds) to stay in a safe room, extracted from the `desc` of the *latest* alert payload.                                                                                       | `600`                                      |
| `icon`              | MDI icon string based on the `cat` of the *latest* alert payload.                                                                                                                                         | `mdi:rocket-launch`                        |
| `emoji`             | Emoji character based on the `cat` of the *latest* alert payload.                                                                                                                                         | `🚀`                                       |
| `alerts_count`      | The number of individual alert *payloads* received and processed by the script during the current active alert window (since the sensor last went `on`).                                                | `3`                                        |
| `last_changed`      | ISO timestamp string (`YYYY-MM-DDTHH:MM:SS.ffffff`) when *this sensor's state or any of its attributes were last updated*.                                                                                | `"2024-07-25T10:30:00.123456"`             |
| `my_cities`         | A sorted list of the city names exactly as configured in your `apps.yaml` `city_names` list.                                                                                                              | `['חיפה - מפרץ', 'תל אביב - מרכז העיר']`   |
| `alert`             | One-line summary string: `[Title] - [Areas]: [Cities]`. Uses cumulative window data.                                                                                                                      | `ירי רקטות וטילים - גוש דן, קו העימות: ...` |
| `alert_alt`         | Multi-line summary string: `[Title]\n* [Area]: [Cities]\n* [Area]: [Cities]...`. Uses cumulative window data.                                                                                             | ` ירי רקטות וטילים\n* גוש דן: תל אביב...\n* קו העימות: כיסופים` |
| `alert_txt`         | One-line string listing Areas and Cities affected in the current window: `[Area]: [Cities], [Area]: [Cities]...`.                                                                                           | `גוש דן: תל אביב - מרכז העיר, אור יהודה...` |
| `alert_wa`          | Multi-line formatted message optimized for WhatsApp, summarizing alerts by type and area based on cumulative window data.                                                                                   |  ![whatsapp](https://github.com/idodov/RedAlert/assets/19820046/817c72f4-70b1-4499-b831-e5daf55b6220)  |
| `alert_tg`          | Multi-line formatted message optimized for Telegram, summarizing alerts by type and area based on cumulative window data.                                                                                   |                                            |
| `prev_cat`          | Category number of the alert from the *previous* alert window (before the sensor last went `off` and then `on` again).                                                                                      | `1`                                        |
| `prev_title`        | Title of the alert from the *previous* alert window.                                                                                                                                                        | `ירי רקטות וטילים`                        |
| `prev_desc`         | Description from the *previous* alert window.                                                                                                                                                             | `היכנסו למרחב המוגן ושהו בו 10 דקות`      |
| `prev_areas`        | Areas from the *previous* alert window.                                                                                                                                                                   | `קו העימות`                                |
| `prev_cities`       | List of cities from the *previous* alert window.                                                                                                                                                          | `['שלומי']`                                |
| `prev_data`         | Comma-separated cities string from the *previous* alert window.                                                                                                                                           | `שלומי`                                    |
| `prev_data_count`   | City count from the *previous* alert window.                                                                                                                                                              | `1`                                        |
| `prev_duration`     | Duration from the *previous* alert window.                                                                                                                                                                | `600`                                      |
| `prev_last_changed` | ISO timestamp when the *previous* alert window became active (when the sensor state last went `on` for that window).                                                                                        | `"2024-07-25T10:15:05.987654"`             |
| `prev_alerts_count` | Sequence count from the *previous* alert window.                                                                                                                                                          | `2`                                        |
| `prev_special_update` | Special update flag status from the *previous* alert window.                                                                                                                                            | `false`                                    |
</details>

---

# Usage Examples

## Creating Derived Sensors for Specific Updates

The primary binary sensors (`binary_sensor.YOUR_SENSOR_NAME` and `binary_sensor.YOUR_SENSOR_NAME_city`) remain `on` for the `timer` duration *after the last alert activity* in a window. If multiple alert *payloads* arrive in quick succession during this window, the sensor's attributes update, but the state stays `on`.

To trigger automations on *each new alert payload* (not just the `off` to `on` state change) or specific types of updates, you can create template binary sensors that monitor attribute changes of the primary sensors.

A particularly useful attribute is `special_update`. PIKUD HA-OREF sometimes sends specific informational updates (like "Alert will trigger soon") which the script flags by setting this attribute to `true`. You can create binary sensors that turn `on` specifically when the `special_update` attribute becomes `true` on the main or city sensor:

### Lovelace Card Example

You can add the entities to your dashboard using various cards. Here's a simple example using a Vertical Stack card:

![red-alerts-sensors](https://github.com/idodov/RedAlert/assets/19820046/e0e779fc-ed92-4f4e-8e36-4116324cd089)
<details>
<summary>Lovelace Card YAML</summary>

```yaml
type: vertical-stack
cards:
  - type: tile
    entity: input_text.red_alert # Displays the main alert summary text
    vertical: true
    state_content: state # Or set to 'last-changed', 'last-updated', etc.

  - type: entities
    entities:
      - entity: binary_sensor.red_alert # Main sensor (any alert)
        state_color: true # Optional: Color icon based on state
      - entity: binary_sensor.red_alert_city # City-specific sensor
        state_color: true # Optional: Color icon based on state
      - entity: sensor.red_alert_history_cities # Example history sensor
      - entity: input_boolean.red_alert_test # Test trigger
    state_color: true # Applies state_color to entities unless overridden above
```
</details>

### Map Visualization (GeoJSON)

![GeoJSON Map Example](https://github.com/user-attachments/assets/6834a827-0186-4b60-921c-f5918dc3bd1b)
> [!NOTE]
> If the GeoJSON integration fails to load, double-check your `allowlist_external_urls` and the exact URL you are using in the integration setup. Also verify that the files actually exist in the `/config/www` folder after an alert occurs (or after script initialization for the empty/default files).

<details>
<summary>GeoJSON Setup Details</summary>

If the `save_2_file` parameter is set to `True`, the script automatically generates two GeoJSON files in the Home Assistant `/config/www` directory. This directory is typically accessible via the Home Assistant frontend at the URL `/local/`.

*   **`YOUR_SENSOR_NAME_latest.geojson`**: Contains coordinate data for the unique cities included in the *currently active* alert window. This file is updated whenever a new payload arrives within an active window.
*   **`YOUR_SENSOR_NAME_24h.geojson`**: Contains coordinate data for *distinct alert events* that occurred within the last `hours_to_show` timeframe, based on the history sensor data. This file is updated every time the primary sensor state changes (on -> off, or off -> on) or when a new payload arrives during an active window.

**To display these on the Home Assistant map:**
1.  Ensure the `www` folder exists in your `/config` directory.
2.  Ensure your `configuration.yaml` includes `allowlist_external_urls` correctly configured with the URL(s) you use to access your Home Assistant instance (as shown in the Installation steps). This allows the GeoJSON integration to fetch the files.
3.  Install the GeoJSON integration in Home Assistant: Go to `Settings` > `Devices & Services` > `Add Integration`, search for "GeoJSON", and follow the prompts.
4.  When prompted for the GeoJSON file URL, enter `http://YOUR_HOME_ASSISTANT_IP_OR_HOSTNAME:8123/local/YOUR_SENSOR_NAME_24h.geojson`. Replace `YOUR_HOME_ASSISTANT_IP_OR_HOSTNAME:8123` with your actual Home Assistant access address and port, and `YOUR_SENSOR_NAME` with your configured sensor base name.
5.  Optionally, add a second GeoJSON integration entity pointing to `http://YOUR_HOME_ASSISTANT_IP_OR_HOSTNAME:8123/local/YOUR_SENSOR_NAME_latest.geojson` to visualize only the currently active alert locations separately.
6.  After adding the integration entity/entities, you can click on the created GeoJSON entity (e.g., `geo_location.your_sensor_name_24h`). In the entity's settings, you can adjust the `Default maximum radius` (e.g., set it to 2000-3000 km to ensure all points in Israel are visible) and `Home Zone Behavior`.

![{28E29F42-3F7F-4625-859B-587381F81941}](https://github.com/user-attachments/assets/23f2f200-28a9-49c1-82c7-79a00343f23c)

</details>

### Home Assistant Events

If the `event` parameter is set to `True` (default), the script fires a native Home Assistant event *each time a new alert payload is received* from the API. This is often the most responsive way to trigger automations, as it doesn't rely on polling sensor states.

The event name is `YOUR_SENSOR_NAME_event`. You can see these events in Home Assistant's Developer Tools > Events section by subscribing to `YOUR_SENSOR_NAME_event`.

<details>
<summary>Home Assistant Event Data Structure & Example Automation</summary>

The data payload associated with the `YOUR_SENSOR_NAME_event` is a dictionary containing detailed information about the *specific alert payload* that triggered the event:

| Key            | Type     | Description                                                                                                                                   | Example Value                         |
| :------------- | :------- | :-------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------ |
| `id`           | integer  | Unique ID of the alert payload from the API.                                                                                                  | `1234567890123456`                    |
| `category`     | integer  | Category number of the alert (corresponds to type, 1-13).                                                                                     | `1`                                   |
| `title`        | string   | Title of the alert (e.g., "ירי רקטות וטילים").                                                                                                | `"ירי רקטות וטילים"`                 |
| `cities`       | list     | A list of the original city names affected by *this specific payload*.                                                                        | `["אבירים", "פסוטה"]`                |
| `areas`        | string   | A comma-separated string of areas affected by *this specific payload*.                                                                        | `"קו העימות"`                         |
| `description`  | string   | The recommended action description (e.g., "היכנסו למרחב המוגן ושהו בו 10 דקות").                                                             | `"היכנסו למרחב המוגן ושהו בו 10 דקות"` |
| `timestamp`    | string   | ISO formatted timestamp when the event was processed by the script.                                                                           | `"2024-07-25T10:30:00.123456"`        |
| `alerts_count` | integer  | The sequence number of this alert *payload* within the current active alert window. This count resets when the main binary sensor goes `off`. | `1` (for the first in a window) or `3` |
| `is_test`      | boolean  | `True` if this event was triggered by the test input_boolean, `False` for real alerts from the API.                                           | `False`                               |

**Example Automation Triggering on the Event:**

You can set up an automation in Home Assistant that triggers whenever this event is fired:

**Example event payload**
```json
{
   "id": 1234567890123456,
   "category": 1,
   "title": "ירי רקטות וטילים",
   "cities": ["אבירים", "פסוטה"],
   "areas": "עוטף עזה",
   "description": "היכנסו למרחב המוגן ושהו בו 10 דקות",
   "timestamp": "2024-07-25T10:30:00",
   "alerts_count": 2,
   "is_test": false
}
```

**Example automation added to automations.yaml or configured via the UI**
```yaml
automation:
  - alias: Respond to Red Alert Event
    # Trigger when the custom event is fired
    trigger:
      platform: event
      event_type: red_alert_event # Use your configured sensor_name_event name
    action:
      # Example Action: Send a notification with details from the event data
      - service: notify.your_notification_service # Replace with your actual notification service entity ID
        data:
          title: "🔴 Red Alert!"
          message: >
            {% set data = trigger.event.data %}
            {{ data.title }} in {{ data.cities | join(', ') }}
            [{{ as_timestamp(data.timestamp) | timestamp_custom('%H:%M:%S', true) }}]
            {{ data.description }}

      # Example Action: Play a TTS message
      # - service: tts.speak
      #   data:
      #     media_player_entity_id: media_player.your_speaker # Replace with your speaker
      #     language: he-IL # Set language if needed
      #     message: >
      #       {% set data = trigger.event.data %}
      #       התרעת {{ data.title }} ב{{ data.areas }}. {{ data.description }}

      # Add other actions like turning on lights, etc.
```
</details>

### MQTT Events

If the `mqtt` parameter is set to `True` (or a custom topic string), the script publishes a JSON message to an MQTT topic *each time a new alert payload is received* from the API. This is useful for integrating with other systems or dashboards that consume MQTT messages.

The default MQTT topic is `home/YOUR_SENSOR_NAME/event`. If you set `mqtt` to a string (e.g., `"my/alerts/topic"`), that string will be used as the topic.

<details>
<summary>MQTT Payload Structure & Example Automation</summary>

The payload published to the MQTT topic is a JSON string containing details about the *specific alert payload* that was received.

**Example Payload (JSON string) - Note: This structure matches the specific example provided in the request:**

```json
{
  "id": 1234567890123456,
  "category": 1,
  "title": "ירי רקטות וטילים",
  "data": ["אבירים", "פסוטה"],
  "desc": "היכנסו למרחב המוגן ושהו בו 10 דקות",
  "alertDate": "2024-07-25 10:30:00",
}
```

#### Using the MQTT Event in Home Assistant Automations

To trigger Home Assistant automations based on these MQTT messages, configure an MQTT trigger subscribing to the topic the script publishes to (`home/YOUR_SENSOR_NAME/event` by default, or your custom topic).

Ensure the MQTT integration is configured in Home Assistant.

```yaml
# Example automation added to automations.yaml or configured via the UI
automation:
  - alias: Respond to MQTT Alert
    # Trigger when a message arrives on the specified MQTT topic
    trigger:
      platform: mqtt
      topic: "home/red_alert/event" # Match the script's publish topic (replace red_alert if needed)
    action:
      # Example Action: Send a notification using data from the JSON payload
      - service: notify.your_notification_service # Replace with your actual notification service entity ID
        data:
          title: "🚨 MQTT Alert!"
          # Access payload data using trigger.payload_json.<key>
          # Note: Access keys match the JSON payload structure above (data, desc, alertDate)
          message: >
            {% set data = trigger.payload_json %}
            {{ data.title }} in {{ data.data | join(', ') }}
            [{{ as_timestamp(data.alertDate) | timestamp_custom('%H:%M:%S', true) }}]
            {{ data.desc }}

      # Add other actions like playing TTS, etc.
```
This setup allows you to leverage the detailed JSON payload sent over MQTT directly within your Home Assistant automations, providing flexibility for advanced logic or integrating with other systems.

</details>

### History & Backup Files

<details>
<summary>History and Backup File Details</summary>

If `save_2_file` is enabled, the script manages several files in the Home Assistant `/config/www` directory. This allows you to access historical alert data and maintain the last known alert state across AppDaemon restarts. The `/config/www` directory is typically mapped to `http://YOUR_HA_IP:8123/local/` in Home Assistant.

1.  **`YOUR_SENSOR_NAME_history.txt`**: This file is appended with a summary of each *completed* alert window (when the main sensor state transitions back to `off`). The summary includes the date, time, alert type, areas, and cities.
2.  **`YOUR_SENSOR_NAME_history.csv`**: This file is appended with structured data for each *completed* alert window. It includes columns for ID, Day, Date, Time, Title, City Count, Areas, Cities (string), Description, and Number of Payloads in the window. This format is suitable for importing into spreadsheet software for analysis. The CSV header is automatically created if the file doesn't exist or is empty on startup.
3.  **`YOUR_SENSOR_NAME_history.json`**: This file is a simple backup of the *last received alert payload's core data*. It is saved to help the script restore the `prev_*` attributes of the sensors after AppDaemon restarts, providing some state persistence. It does **not** store the full history list.
4.  **`YOUR_SENSOR_NAME_latest.geojson`**: (See Map section) Stores GeoJSON point data for the cities in the *currently active* alert window.
5.  **`YOUR_SENSOR_NAME_24h.geojson`**: (See Map section) Stores GeoJSON point data for distinct alert *events* within the history window (`hours_to_show`).

The TXT and CSV history files summarize incidents *after* the main sensor resets to `off` (i.e., after the `timer` duration has passed and no new alerts were detected). The JSON backup is primarily for restoring the `prev_*` attributes on startup.

You can access these files directly via your browser using URLs like `http://YOUR_HOME_ASSISTANT_IP:8123/local/YOUR_SENSOR_NAME_history.txt`.
</details>

---

## Script Status
![image](https://github.com/user-attachments/assets/7ec3d3ee-7bdf-4846-84a3-e5f49b83de6e)

<details>
<summary>Markdown Card YAML</summary>

```yaml
# Replace 'red_alert' with your configured sensor_name if different.
type: markdown
content: |
   {% set status = state_attr('binary_sensor.red_alert', 'script_status') %} {# Adjust if needd #} 
   {% if status == 'running' or status == 'idle' %}
   <ha-alert alert-type="success">Script status: {{ status }}</ha-alert>
   {% elif status == 'initializing' %}
   <ha-alert alert-type="info">Script status: {{ status }}</ha-alert>
   {% else %}
   <ha-alert alert-type="error">Script status: {{ status }} (Check appdaemon log)</ha-alert>
   {% endif %}
```
</details>

## History Markdown Example

This example provides YAML code for a Home Assistant Markdown card that displays recent alert history grouped by alert type and area, leveraging the data available in the `sensor.YOUR_SENSOR_NAME_history_group` sensor's attributes.

![History Markdown Card Example](https://github.com/user-attachments/assets/60e6b1d5-bfca-421c-8f5e-840ca95bc917)

<details>
<summary>Markdown Card YAML</summary>

```yaml
# Replace 'red_alert' with your configured sensor_name if different.
type: markdown
content: |
  {% set show_history = True %}
  {% set show_info = True %}
  {% set alerts = state_attr('sensor.red_alert_history_group', 'last_24h_alerts_group') %}
  {% set oref = states('binary_sensor.red_alert') %}
  <table width=100%>
  <tr><td align=center>
  {% if oref == 'on' %}
  # <font color="red">{{ state_attr('binary_sensor.red_alert', 'title') }}</font> {{ state_attr('binary_sensor.red_alert', 'emoji') }}
  </td></tr>
  <tr><td align=center>
  <big><big><b>{{ state_attr('binary_sensor.red_alert', 'alert_txt') }}</b></big></big>
  {% else %}
  ## <font color="green">אין התרעות</font> ✅
  {% endif %}
  </td></tr>
  </table>
  {% set current_date = now().date() %}
  {# Check if prev_last_changed attribute exists and is in expected ISO format before parsing #}
  {% if state_attr('binary_sensor.red_alert', 'prev_last_changed') is string and state_attr('binary_sensor.red_alert', 'prev_last_changed') | regex_match("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(\\.\\d+)?([+-]\\d{2}:\\d{2}|Z)?$") %}
    {% set last_changed_str = state_attr('binary_sensor.red_alert', 'prev_last_changed') %}
    {# Attempt parsing with fromisoformat, fallback to as_timestamp if needed or problematic #}
    {% set last_changed_dt = last_changed_str | as_datetime(with_tz=True) | default(last_changed_str | as_datetime) | default(None) %}

    {% if last_changed_dt %}
      {# Ensure datetime is naive for date comparison if needed, or use UTC #}
      {% set last_changed_dt_naive = last_changed_dt | as_local %} # Convert to local time for display/comparison

      <center>התרעה אחרונה נשלחה
      {% set time_difference = (now() - last_changed_dt_naive).total_seconds() %}

      {% if time_difference < 60 %}
      לפני פחות מדקה
      {% elif time_difference < 3600 %}
      לפני {{ (time_difference / 60) | int }} דקות
      {% elif time_difference < 86400 and last_changed_dt_naive.date() == now().date() %}
      היום בשעה {{ last_changed_dt_naive | timestamp_custom('%H:%M', true) }}
      {% else %}
      בתאריך {{ last_changed_dt_naive | timestamp_custom('%d/%m/%Y', true) }}, בשעה {{ last_changed_dt_naive | timestamp_custom('%H:%M', true) }}
      {% endif %}
      </center>
    {# else %} {# Optional: Log if parsing failed #}
      {# <center> שגיאה בעיבוד זמן התרעה אחרונה </center> #}
    {% endif %}
  {% endif %}

  <hr>
  {% if alerts and show_history %}
  {% if show_info %}
  <table width=100%>
  <tr><td align=center>
  {{ state_attr('sensor.red_alert_history_cities', 'cities_past_24h') | length }} :ערים</td>
  <td align=center>
  {{ state_attr('sensor.red_alert_history_list', 'last_24h_alerts') | length }} :התרעות</td></tr>
  <tr><td colspan=2><hr></td></tr>
  </table>
  {% endif %}
  <table width=100% align=center>
  {% for alert_type, areas in alerts.items() %}
  <tr><td colspan=3 align=center><h2><font color="blue">{{ alert_type }}</font></h2><hr></td></tr> {# Adjusted colspan for 3 columns #}
  {% for area, cities in areas.items() %}
  <tr><td colspan=3 align=center><big><b>{{ area }}</b></big></td></tr> {# Adjusted colspan #}
  {% set unique_cities = [] %}
  {% for city_pair in cities|batch(2) %} {# Iterating in batches of 2 for side-by-side display #}
  <tr>
    <td align=right valign=top width=30%>{% if city_pair[0].time[:10] == (now() - timedelta(days=1)).strftime('%Y-%m-%d') %}
      <font color="red">{{ city_pair[0].city }}</font> {# Use city_pair[0].city #}
    {% else %}
      {{ city_pair[0].city }} {# Use city_pair[0].city #}
    {% endif %}
    </td>
    <td valign=top width=10%> - </td>
    <td valign=top width=60%>{{ city_pair[0].time[:5] }}</td> {# Use city_pair[0].time #}
  </tr>
  {# Removed logic for second city in batch as layout is now single column per row for cities/times #}
  {% endfor %}
  {% endfor %}
  {% endfor %}
  </table>
  {% endif %}
```

</details>
