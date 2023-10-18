# התרעות פיקוד העורף / צבע אדום במערכת Home Assistant (AppDaemon)
***זהו לא תוסף רשמי של פיקוד העורף***. 
קיימת גרסה בשפה האנגלית עם מידע מורחב ועוד דוגמאות/שימושים ברכיב: https://github.com/idodov/RedAlert

**עקב הערות ובקשות לשיניים, עדכנתי את הקוד בתאריך 18/10/2023. מומלץ למי שכבר משתמש בקוד והתקין לפני לעדכן את קובץ orefalert.py. במידה ובחרת שלא, עדיין הכל אמור להמשיך לעבוד כרגיל.**

**סקריפט זה יוצר יישות/חיישן בינארי למעקב אחר מצב התרעות פיקוד העורף בישראל. החיישן יכול להיות שמיש בתרחישים (אוטומציות) ו/או ליצור ממנו חיישני משנה/חיישנים בינאריים.**
ההחיישן מספק התרעה לכל סוגי האיומים שפיקוד העורף מתריע, לרבות ירי רקטות וטילים, חדירת כלי טייס עויינים, חדירת מחבלים, רעידת אדמה, חששות לצונאמי וכל איום אחר.

לאתר התקנת החיישן תייצר ישות חדשה במערכת HA בשם ***binary_sensor.oref_alert***. ישות זו תהיה מופעלת בזמן התרעה וכבוייה כשאין התרעה. היישות כוללת פרטי מידע נוספים, אותם ניתן לחלץ ולהשתמש בהם לצרכי תצוגה או טריגרים להפעלת תרחישים.
האייקון וכותרת החיישן, כפופים לשינוי דינמי עם כל התרעה חדשה. לשם המחשה, במקרה של ירי רקטות וטילים האייקון של החיישן יציג הסמל המתאר רקטה. בנוסף, קיים אימוג'י נפרד המשויך לכל סוג התרעה אותו ניתן להציג לצד הודעת ההתרעה.

![Capture--](https://github.com/idodov/RedAlert/assets/19820046/2cdee4bb-0849-4dc1-bb78-c2e282300fdd)
![000](https://github.com/idodov/RedAlert/assets/19820046/22c3336b-cb39-42f9-8b32-195d9b6447b2)
### חשוב לדעת
* שיטת התקנה זו מתבססת על מערכת ההפעלה של Home Assistant
* לאחר אתחול מלא של מערכת ההפעלה יאבדו נתוני החיישן ההיסטורים. אולם, יש פתרון עוקף באמצעות הקמת עזר TEXT במסך העזרים ולשרשר אליו באמצעות תרחיש את נתוני ההתרעות.
## הוראות התקנה
1. תחילה היכנס אל מסך **ההגדרות**, בחר **הרחבות** ומשם את **חנות ההרחבות**
2. בחנות ההרחבות יש לחפש הרחבה בשם **"AppDaemon"**
3. לאחר התקנתה יש להפעיל מצב **כלב שמירה** ומצב **עדכון אוטומטי** (עדיין לא להריץ את ההרחבה)
4. יש לגשת ללשונית **תצורה** ולהוסיף תחת ההגדרה "Python packages" את ההגדרה "**requests**"

![Capture1](https://github.com/idodov/RedAlert/assets/19820046/d4e3800a-a59b-4605-b8fe-402942c3525b)

5. **כעת יש להריץ את ההרחבה**
6. נדרש לפתוח FILE EDITOR (ניתן להתקין דרך חנות ההרחבות) ולפתוח את הקובץ `config/appdaemon/appdaemon.yaml/`
7. יש לעדכן את הנתונים הבאים: 
את איזור הזמן (`time_zone`) יש לעדכן ל-"Asia/Jerusalem", את הגדרת קו הרוחב (`latitude`) יש לעדכן ל-"31.9837528", את הגדרת קו האורך (`longitude`) יש לעדכן ל-"34.7359077".
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
8. בעזרת FILE EDITOR נווט לתיקייה `config/appdaemon/apps/` והקם קובץ בשם **orefalert.py** אל תוכו להעתיק את הקוד הבא:
*לתשומת ליבך, בקוד מוגדר שהסנסור יבדוק מידע מול פיקוד העורף **כל 3 שניות**. ניתן לשנות את הנתון `interval = 3` למספר אחר. לדוגמא 1 = שנייה, 0.5 = חצי שנייה.* 
```orefalert.py
import requests
import re
import time
import json
import codecs
from datetime import datetime
from appdaemon.plugins.hass.hassapi import Hass

interval = 3

class OrefAlert(Hass):
    def initialize(self):
        self.check_create_binary_sensor()
        self.run_every(self.poll_alerts, datetime.now(), interval)

    def check_create_binary_sensor(self):
        # Check if the binary_sensor exists
        if not self.entity_exists("binary_sensor.oref_alert"):
            self.set_state("binary_sensor.oref_alert", state="off", 
            attributes={ "id":"", "cat": "", "title": "", "desc": "", "data": "", "data_count": 0, "duration": 0, "last_changed": "", "prev_cat": 0, "prev_title": "", "prev_desc": "", "prev_data": "", "prev_data_count": 0,"prev_duration": 0, "prev_last_changed": ""},)

    def poll_alerts(self, kwargs):
        url = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': 'https://www.oref.org.il/',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        }
        icons = {1: "mdi:rocket-launch",2: "mdi:home-alert",3: "mdi:earth-box",4: "mdi:chemical-weapon",5: "mdi:waves",6: "mdi:airplane",7: "mdi:skull",8: "mdi:alert",9: "mdi:alert",10: "mdi:alert",11: "mdi:alert",12: "mdi:alert",13: "mdi:run-fast",}
        icon_alert = "mdi:alert"
        emojis = {1: "🚀",2: "⚠️",3: "🌍",4: "☢️",5: "🌊",6: "🛩️",7: "💀",8: "❗",9: "❗",10: "❗",11: "❗",12: "❗",13: "👣👹",}
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
                            duration_match = re.findall(r'\d+', data.get('desc', '0'))
                            if duration_match:
                                duration = int(duration_match[0]) * 60
                            else:
                                duration = 0
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
                                    "data_count": data_count,
                                    "duration": duration,
                                    "last_changed": datetime.now().isoformat(),
                                    "prev_cat": data.get('cat', None),
                                    "prev_title": alert_title,
                                    "prev_desc": data.get('desc', None),
                                    "prev_data": alerts_data,
                                    "prev_data_count": data_count,
                                    "prev_duration": duration,
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
                                    "id": "",
                                    "cat": 0,
                                    "title": "אין התרעות",
                                    "desc": "",
                                    "data": "",
                                    "data_count": 0,
                                    "duration": 0,
                                    "emoji":  icon_emoji,
                                    "icon": icon_alert,
                                    "friendly_name": "Oref Alert",
                                },
                            )
                    except json.JSONDecodeError:
                        self.log("Error: Invalid JSON format in the response.")
                        icon_alert = "mdi:alert"
                else:
                    # Clear the input_text and set binary_sensor state to off if there is no data in the response
                    self.set_state(
                        "binary_sensor.oref_alert",
                        state="off", 
                        attributes={
                            "id": "",
                            "cat": 0,
                            "title": "אין התרעות",
                            "desc": "",
                            "data": "",
                            "data_count": 0,
                            "duration": 0,
                            "icon": icon_alert,
                            "emoji":  icon_emoji,
                            "friendly_name": "Oref Alert",
                        },
                    )
            else:
                self.log(f"Failed to retrieve data. Status code: {response.status_code}")
        except Exception as e:
            self.log(f"Error: {e}")
```
9. יש לפתוח את הקובץ **apps.yaml** אשר נמצא בנתיב `config/appdaemon/apps/` ולהוסיף את השורות הבאות ולשמור:
```yaml
orefalert:
  module: orefalert
  class: OrefAlert
```
10. **הפעל מחדש** את התוסף **appdaemon**.

לאחר ההפעלה החיישן יהיה זמין לשימוש. תחילה החיישן יהיה במצב כבוי ללא נתונים, עד אשר תתקבל התרעה מפיקוד העורף.
## דוגמאות
יש מספר דרכים להגדיר חיישנים נוספים או טריגרים לתרחישים. מאוד חשוב לשמור על כללי כתיבת הקוד, אחרת החיישן לא יעבוד תקין.
### עיר / אזור בעיר
```
{{ "יבנה" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
### מספר ערים / איזורים
```
{{ "אירוס" in state_attr('binary_sensor.oref_alert', 'data').split(', ')
 or "בית חנן" in state_attr('binary_sensor.oref_alert', 'data').split(', ')
 or "גן שורק" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
### ערים המחולקות לאזורים
במידה ורוצים לקבל התרעה בכל האזורים בעיר (בישראל 11 ערים המחולקות לאזורים)

```
{{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב") }} 
```
## שמירת נתונים היסוטריים
מכיוון שמדובר בחיישן בינארי, היסטוריית שלו נשמרת רק כאשר החיישן עובר בין מצבי מופעל וכיבוי. אם ברצונך לשמור על היסטוריה מלאה של כל ההתראות, כולל סוג ההתראה והעיר, בצע את השלבים הבאים:
1. נדרש לייצר **מסייע טקסט** חדש בתוך ממשק המשתמש תחת **'הגדרות' > 'מכשירים ושירותים' > 'עוזרים' > 'צור עוזר' > 'טקסט'**
2. יש להגדיר את שם עוזר ל-"**Last Alert in Israel**". אם מוגדר שם אחר, יש לעדכן את האוטומציה המובאת לדוגמא.
3. בשדה **האורך המרבי** לעדכן את הנתון מ-100 ל-**255** ולייצר את העוזר.

![111Capture](https://github.com/idodov/RedAlert/assets/19820046/1008a3ba-65a1-4de5-96cb-6bef5d2f85b0)

**מצ"ב אוטומציה המעדכנת את חיישן הטקסט בכל פעם שמתרחשת התרעת צבע אדום (עם הגמישות ליצור אוטומציה זו לכל הערים או לעיר או אזור ספציפי, בהתאם להעדפות שלכם).**
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


## שימושים
### כרטיסייה
לדוגמא לקוד המציג מידע על מספר התרעות פעילות, סוג ההתרעה, ערים והסבר התגוננות.
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
## תרחיש לדוגמא
אפשר באמצעות החיישן לייצר מגוון רחב של תרחישים, לדוגמא - לשלוח התרעה למסך LED MATRIX כמו בדוגמא בתמונה.
![20231013_210149](https://github.com/idodov/RedAlert/assets/19820046/0f88c82c-c87a-4933-aec7-8db425f6515f)

### שליחת התרעה לטלפון בכל אירוע צבע אדום
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
### שינוי צבע האורות בבית במידה ויש אזעקה בעיר המחולקת לאזורים
![20231013_221552](https://github.com/idodov/RedAlert/assets/19820046/6e60d5ca-12a9-4fd2-9b10-bcb19bf38a6d)
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
