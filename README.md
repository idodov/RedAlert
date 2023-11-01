# Israeli Red Alert Service for Home Assistant (AppDaemon)
***Not Official Pikud Ha-Oref***.  Short Hebrew version can be found here: https://github.com/idodov/RedAlert/blob/main/hebrew.md
____
**This script sets up two new entities in Home Assistant:**
1. A binary sensor called ***binary_sensor.oref_alert*** to store PIKUD HA-OREF data. The sensor can be used in automations or to create sub-sensors/binary sensors from it.
2. A text input entity named ***input_text.last_alert_in_israel*** for storing the latest alert information, mainly for historical purposes.

The binary sensor provides a warning for all threats that the PIKUD HA-OREF alerts for, including red alerts rocket and missile launches, unauthorized aircraft penetration, earthquakes, tsunami concerns, infiltration of terrorists, hazardous materials incidents, unconventional warfare, and any other threat. When the alert is received, the nature of the threat will appear at the beginning of the alert (e.g., 'ירי רקטות וטילים').

While the binary sensor's state switches to 'on' when there is an active alert in Israel behavior may not suit everyone, the sensor is designed with additional attributes containing data such as cities, types of attacks and more. These attributes make it easy to create customized sub-sensors to meet individual requirements. For example, you can set up specific sensors that activate only when an alarm pertains to a particular city or area.

<details>
<summary>Why did I choose this method and not REST sensor?</summary>
Until we all have an official Home Assistant add-on to handle 'Red Alert' situations, there are several approaches for implementing the data into Home Assistant. One of them is creating a REST sensor and adding the code to the *configuration.yaml* file. However, using a binary sensor (instead of a 'REST sensor') is a better choice because it accurately represents binary states (alerted or not alerted), is more compatible with Home Assistant tools, and simplifies automation and user configuration. It offers a more intuitive and standardized approach to monitoring alert status. I tried various methods in Home Assistant, but this script worked best for my needs.
</details>

Installing this script will create a Home Assistant entity called ***binary_sensor.oref_alert***. This sensor will be **on** if there is a Red Alert in Israel, and **off** otherwise. The sensor also includes attributes that can serve various purposes, including category, ID, title, data, description, the number of active alerts, and emojis.

The second entity, ***input_text.last_alert_in_israel*** is primarily designed for historical alert records on the logbook screen. Please be aware that Home Assistant has an internal character limit of 255 characters for text entities. This limitation means that during significant events, like a large-scale attack involving multiple areas or cities, some data may be truncated or lost. Therefore, it is highly discouraged to use the text input entity as a trigger for automations or to create sub-sensors from it.

*By default, for testing purposes, the entities will contain data related to cities inside the Gaza Strip.*
## Important Notice
This installation method **relies** on Supervised Add-ons, which are exclusively accessible if you've employed either the Home Assistant Operating System or the Home Assistant Supervised installation method (You can also opt to install the AppDaemon add-on through Docker. For additional details, please consult the following link: https://appdaemon.readthedocs.io/en/latest/DOCKER_TUTORIAL.html).
# Installation Instructions
1. Install the **AppDaemon** addon in Home Assistant by going to Settings > Add-ons > Ad-on-store and search for **AppDaemon**.
2. Once AppDaemon is installed, enable the **Auto-Start** and **Watchdog** options.
3. Go to the AppDaemon ***configuration*** page and add ```requests``` ***Python package*** under the Python Packages section.

![Capture1](https://github.com/idodov/RedAlert/assets/19820046/d4e3800a-a59b-4605-b8fe-402942c3525b)

4. **Start** the add-on
5. In file editor open **/config/appdaemon/appdaemon.yaml** and make this changes under *appdeamon* section for `latitude: 31.9837528` & 
  `longitude: 34.7359077` & `time_zone: Asia/Jerusalem`. 
*You can locate your own coordinates (latitude & longitude) here: https://www.latlong.net/*
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
The script updates the sensors every *2 seconds*, or more frequently if you specify a shorter scan ```interval```. 
```
# UPDATE 31/10/2023 - Add Text Input entity
import requests
import re
import time
import json
import codecs
from datetime import datetime
from appdaemon.plugins.hass.hassapi import Hass

interval = 2

class OrefAlert(Hass):
    def initialize(self):
        self.check_create_binary_sensor()
        self.run_every(self.poll_alerts, datetime.now(), interval, timeout=30)

    def check_create_binary_sensor(self):
        if not self.entity_exists("binary_sensor.oref_alert"):
            self.set_state("binary_sensor.oref_alert", state="off", attributes={ "id":"", "cat": "", "title": "", "desc": "", "data": "", "data_count": 0, "duration": 0, "last_changed": "", "prev_cat": 0,  "prev_title": "מפוצצים את עזה", "prev_desc": "תישארו בחוץ", "prev_data" :"בית חאנון, בית לאהיא, בני סוהילה, ג'באליה, דיר אל-בלח, ח'אן יונס, עבסאן אל-כבירה, עזה, רפיח", "prev_data_count": 9,"prev_duration": 10, "prev_last_changed": datetime.now().isoformat()},)
        if not self.entity_exists("input_text.last_alert_in_israel"):
            self.set_state("input_text.last_alert_in_israel", state="ירי רקטות וטילים = בית חאנון, בית לאהיא, בני סוהילה, ג'באליה, דיר אל-בלח, ח'אן יונס, עבסאן אל-כבירה, עזה, רפיח", attributes={"editable": true, "min": 0, "max": 255, "mode": "text", "friendly_name": "Last Alert in Israel"},)

    def poll_alerts(self, kwargs):
        #url = "https://www.oref.org.il/WarningMessages/History/AlertsHistory.json"
        url = "https://www.oref.org.il/WarningMessages/alert/alerts.json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            'Referer': 'https://www.oref.org.il/',
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
        }
        lamas = {"areas":{"גליל עליון":{"אבו סנאן":{},"אור הגנוז":{},"אזור תעשייה בר-לב":{},"אזור תעשייה חצור הגלילית":{},"אזור תעשייה כרמיאל":{},"אזור תעשייה צ.ח.ר":{},"אזור תעשייה שער נעמן":{},"אחיהוד":{},"איילת השחר":{},"אליפלט":{},"אמירים":{},"אמנון":{},"אפק":{},"אשרת":{},"בוסתן הגליל":{},"ביריה":{},"בית ג'אן":{},"בית העמק":{},"בענה":{},"בר יוחאי":{},"ג'דידה מכר":{},"ג'וליס":{},"גדות":{},"גיתה":{},"דיר אל-אסד":{},"הר-חלוץ":{},"חולתה":{},"חצור הגלילית":{},"חרשים":{},"טובא זנגריה":{},"טל-אל":{},"ינוח-ג'ת":{},"יסוד המעלה":{},"יסעור":{},"ירכא":{},"כורזים ורד הגליל":{},"כחל":{},"כיסרא סמיע":{},"כישור":{},"כליל":{},"כמון":{},"כפר הנשיא":{},"כפר יסיף":{},"כפר מסריק":{},"כפר שמאי":{},"כרכום":{},"כרמיאל":{},"לבון":{},"לוחמי הגטאות":{},"לפידות":{},"מג'דל כרום":{},"מרכז אזורי מרום גליל":{},"מזרעה":{},"מחניים":{},"מירון":{},"מכמנים":{},"מנחת מחניים":{},"משמר הירדן":{},"נחף":{},"נס עמים":{},"נתיב השיירה":{},"סאג'ור":{},"ספסופה - כפר חושן":{},"עין אל אסד":{},"עין המפרץ":{},"עין כמונים":{},"עכו":{},"עכו - אזור תעשייה":{},"עמוקה":{},"עמיעד":{},"עמקה":{},"פלך":{},"פרוד":{},"צורית גילון":{},"צפת":{},"קדיתא":{},"קדרים":{},"ראמה":{},"ראש פינה":{},"רגבה":{},"שבי ציון":{},"שדה אליעזר":{},"שומרת":{},"שזור":{},"שייח' דנון":{},"שפר":{},"תובל":{}},"דרום הנגב":{"אבו קרינאת":{},"אבו תלול":{},"אורון תעשייה ומסחר":{},"אזור תעשייה דימונה":{},"אזור תעשייה רותם":{},"אל פורעה":{},"אשלים":{},"באר מילכה":{},"'ביר הדאג":{},"בית סוהר נפחא":{},"דימונה":{},"הר הנגב":{},"ואדי אל נעם דרום":{},"חירן":{},"טללים":{},"ירוחם":{},"כמהין":{},"כסייפה":{},"מדרשת בן גוריון":{},"ממשית":{},"מצפה רמון":{},"מרחב עם":{},"מרעית":{},"משאבי שדה":{},"ניצנה":{},"סעייה-מולדה":{},"עבדת":{},"עזוז":{},"ערד":{},"ערערה בנגב":{},"קדש ברנע":{},"קצר-א-סיר":{},"רביבים":{},"רתמים":{},"שאנטי במדבר":{},"שדה בוקר":{},"תל ערד":{}},"שפלת יהודה":{"אבו-גוש":{},"אביעזר":{},"אדרת":{},"אזור תעשייה ברוש":{},"אזור תעשייה הר טוב - צרעה":{},"אשתאול":{},"בית גוברין":{},"בית מאיר":{},"בית ניר":{},"בית נקופה":{},"בית שמש":{},"בקוע":{},"בר גיורא":{},"גבעות עדן":{},"גבעת יערים":{},"גבעת ישעיהו":{},"גיזו":{},"גלאון":{},"גפן":{},"הר אדר":{},"הראל":{},"זכריה":{},"זנוח":{},"טל שחר":{},"יד השמונה":{},"ישעי":{},"כסלון":{},"כפר אוריה":{},"כפר זוהרים":{},"כפר מנחם":{},"לוזית":{},"לטרון":{},"מבוא ביתר":{},"מחסיה":{},"מטע":{},"מסילת ציון":{},"מעלה החמישה":{},"נווה אילן":{},"נווה מיכאל - רוגלית":{},"נווה שלום":{},"נחושה":{},"נחם":{},"נחשון":{},"נטף":{},"נס הרים":{},"נתיב הל''ה":{},"עגור":{},"עין נקובא":{},"עין ראפה":{},"צובה":{},"צור הדסה":{},"צלפון":{},"צפרירים":{},"צרעה":{},"קריית יערים":{},"קריית ענבים":{},"רטורנו - גבעת שמש":{},"רמת רזיאל":{},"שדות מיכה":{},"שואבה":{},"שורש":{},"שריגים - ליאון":{},"תירוש":{},"תעוז":{},"תרום":{}},"מרכז הגליל":{"אבטליון":{},"אזור תעשייה תרדיון":{},"אעבלין":{},"אשבל":{},"אשחר":{},"בועיינה-נוג'ידאת":{},"ביר אלמכסור":{},"בית סוהר צלמון":{},"בית רימון":{},"דיר חנא":{},"דמיידה":{},"הררית יחד":{},"חוסנייה":{},"חזון":{},"חנתון":{},"טורעאן":{},"טמרה":{},"טפחות":{},"יובלים":{},"יודפת":{},"יעד":{},"כאבול":{},"כאוכב אבו אלהיג'א":{},"כלנית":{},"כפר חנניה":{},"כפר מנדא":{},"לוטם וחמדון":{},"מורן":{},"מורשת":{},"מנוף":{},"מסד":{},"מע'אר":{},"מעלה צביה":{},"מצפה אבי''ב":{},"מצפה נטופה":{},"מרכז אזורי משגב":{},"סכנין":{},"סלמה":{},"עוזייר":{},"עילבון":{},"עינבר":{},"עצמון - שגב":{},"עראבה":{},"ערב אל-נעים":{},"קורנית":{},"ראס אל-עין":{},"רומאנה":{},"רומת אל הייב":{},"רקפת":{},"שורשים":{},"שכניה":{},"שעב":{},"שפרעם":{}},"מנשה":{"אביאל":{},"אור עקיבא":{},"אזור תעשייה קיסריה":{},"אזור תעשייה רגבים":{},"אלוני יצחק":{},"בית חנניה":{},"בית ספר אורט בנימינה":{},"בנימינה":{},"ברקאי":{},"ג'סר א-זרקא":{},"גבעת חביבה":{},"גבעת עדה":{},"גן השומרון":{},"גן שמואל":{},"זכרון יעקב":{},"חדרה - מזרח":{},"חדרה - מערב":{},"חדרה - מרכז":{},"חדרה - נווה חיים":{},"כפר גליקסון":{},"כפר פינס":{},"להבות חביבה":{},"מאור":{},"מעגן מיכאל":{},"מעיין צבי":{},"מענית":{},"מרכז ימי קיסריה":{},"משמרות":{},"עין עירון":{},"עין שמר":{},"עמיקם":{},"פרדס חנה-כרכור":{},"קיסריה":{},"רמת הנדיב":{},"שדה יצחק":{},"שדות ים":{},"שער מנשה":{},"תלמי אלעזר":{}},"קו העימות":{"אביבים":{},"אבירים":{},"אבן מנחם":{},"אדמית":{},"אזור תעשייה אכזיב מילואות":{},"אזור תעשייה רמת דלתון":{},"אילון":{},"אלקוש":{},"בית הלל":{},"בית ספר שדה מירון":{},"בן עמי":{},"בצת":{},"ברעם":{},"ג'ש - גוש חלב":{},"גונן":{},"גורן":{},"גורנות הגליל":{},"געתון":{},"גשר הזיו":{},"דוב''ב":{},"דישון":{},"דלתון":{},"קיבוץ דן":{},"דפנה":{},"הגושרים":{},"הילה":{},"זרעית":{},"חוסן":{},"חורפיש":{},"חניתה":{},"יחיעם":{},"יערה":{},"יפתח":{},"יראון":{},"כברי":{},"כפר בלום":{},"כפר גלעדי":{},"כפר ורדים":{},"כפר יובל":{},"כפר סאלד":{},"כרם בן זמרה":{},"להבות הבשן":{},"לימן":{},"מרכז אזורי מבואות חרמון":{},"מטולה":{},"מלכיה":{},"מנות":{},"מנרה":{},"מעונה":{},"מעיין ברוך":{},"מעיליא":{},"מעלות תרשיחא":{},"מצובה":{},"מרגליות":{},"משגב עם":{},"מתת":{},"נאות מרדכי":{},"נהריה":{},"נווה זיו":{},"נטועה":{},"סאסא":{},"סער":{},"עבדון":{},"עברון":{},"ע'ג'ר":{},"עין יעקב":{},"עלמה":{},"עמיר":{},"ערב אל עראמשה":{},"פסוטה":{},"פקיעין":{},"צבעון":{},"צוריאל":{},"קריית שמונה":{},"ראש הנקרה":{},"ריחאנייה":{},"רמות נפתלי":{},"שאר ישוב":{},"שדה נחמיה":{},"שומרה":{},"שלומי":{},"שמיר":{},"שניר":{},"שתולה":{},"תל חי":{}},"לכיש":{"אביגדור":{},"אבן שמואל":{},"אורות":{},"אזור תעשייה באר טוביה":{},"אזור תעשייה כנות":{},"אזור תעשייה עד הלום":{},"אזור תעשייה קריית גת":{},"אזור תעשייה תימורים":{},"אחווה":{},"אחוזם":{},"איתן":{},"אל עזי":{},"אלומה":{},"אמונים":{},"אשדוד - א,ב,ד,ה":{},"אשדוד - איזור תעשייה צפוני":{},"אשדוד - ג,ו,ז":{},"אשדוד - ח,ט,י,יג,יד,טז":{},"אשדוד -יא,יב,טו,יז,מרינה,סיט":{},"באר טוביה":{},"ביצרון":{},"בית אלעזרי":{},"בית גמליאל":{},"בית חלקיה":{},"בית עזרא":{},"בן זכאי":{},"בני דרום":{},"בני עי''ש":{},"בני ראם":{},"בניה":{},"גבעת ברנר":{},"גבעת וושינגטון":{},"גבעתי":{},"גדרה":{},"גן הדרום":{},"גן יבנה":{},"גני טל":{},"גת":{},"ורדון":{},"זבדיאל":{},"זוהר":{},"זרחיה":{},"חפץ חיים":{},"חצב":{},"חצור":{},"יבנה":{},"יד בנימין":{},"יד נתן":{},"ינון":{},"כנות":{},"כפר אביב":{},"כפר אחים":{},"כפר הנגיד":{},"כפר הרי''ף וצומת ראם":{},"כפר ורבורג":{},"כפר מרדכי":{},"כרם ביבנה":{},"לכיש":{},"מישר":{},"מנוחה":{},"מעון צופיה":{},"מרכז שפירא":{},"משגב דב":{},"משואות יצחק":{},"מתחם בני דרום":{},"נגבה":{},"נהורה":{},"נוגה":{},"נווה מבטח":{},"נועם":{},"נחלה":{},"ניר בנים":{},"ניר גלים":{},"ניר ח''ן":{},"סגולה":{},"עוזה":{},"עוצם":{},"עזר":{},"עזריקם":{},"עין צורים":{},"ערוגות":{},"עשרת":{},"פארק תעשייה ראם":{},"פלמחים":{},"קבוצת יבנה":{},"קדמה":{},"קדרון":{},"קוממיות":{},"קריית גת, כרמי גת":{},"קריית מלאכי":{},"רבדים":{},"רווחה":{},"שדה דוד":{},"שדה יואב":{},"שדה משה":{},"שדה עוזיהו":{},"שדמה":{},"שחר":{},"שלווה":{},"שפיר":{},"שתולים":{},"תימורים":{},"תלמי יחיאל":{},"תלמים":{}},"שרון":{"אביחיל":{},"אבן יהודה":{},"אודים":{},"אורנית":{},"אזור תעשייה טירה":{},"אזור תעשייה עמק חפר":{},"אחיטוב":{},"אייל":{},"אליכין":{},"אלישיב":{},"אלישמע":{},"אלפי מנשה":{},"אלקנה":{},"אמץ":{},"ארסוף":{},"בארותיים":{},"בורגתה":{},"בחן":{},"בית ברל":{},"בית הלוי":{},"בית חזון":{},"בית חרות":{},"בית יהושע":{},"בית ינאי":{},"בית יצחק - שער חפר":{},"בית סוהר השרון":{},"ביתן אהרן":{},"בני דרור":{},"בני ציון":{},"בצרה":{},"בת חן":{},"בת חפר":{},"ג'לג'וליה":{},"גאולי תימן":{},"גאולים":{},"גבעת חיים איחוד":{},"גבעת חיים מאוחד":{},"גבעת חן":{},"גבעת שפירא":{},"גן חיים":{},"גן יאשיה":{},"גנות הדר":{},"גני עם":{},"געש":{},"הדר עם":{},"הוד השרון":{},"המעפיל":{},"המרכז האקדמי רופין":{},"העוגן":{},"זמר":{},"חבצלת השרון וצוקי ים":{},"חגור":{},"חגלה":{},"חופית":{},"חורשים":{},"חיבת ציון":{},"חניאל":{},"חרב לאת":{},"חרוצים":{},"חרות":{},"טייבה":{},"טירה":{},"יד חנה":{},"ינוב":{},"יעף":{},"יקום":{},"ירחיב":{},"ירקונה":{},"כוכב יאיר - צור יגאל":{},"כפר ברא":{},"כפר הס":{},"כפר הרא''ה":{},"כפר ויתקין":{},"כפר חיים":{},"כפר ידידיה":{},"כפר יונה":{},"כפר יעבץ":{},"כפר מונש":{},"כפר מל''ל":{},"כפר נטר":{},"כפר סבא":{},"כפר עבודה":{},"כפר קאסם":{},"מרכז אזורי דרום השרון":{},"מכון וינגייט":{},"מכמורת":{},"מעברות":{},"משמר השרון":{},"משמרת":{},"מתן":{},"נווה ימין":{},"נווה ירק":{},"נורדיה":{},"ניצני עוז":{},"ניר אליהו":{},"נירית":{},"נעורים":{},"נתניה - מזרח":{},"נתניה - מערב":{},"סלעית":{},"עדנים":{},"עולש":{},"עזריאל":{},"עין החורש":{},"עין ורד":{},"עין שריד":{},"עץ אפרים":{},"פורת":{},"פרדסיה":{},"צופים":{},"צופית":{},"צור יצחק":{},"צור משה":{},"צור נתן":{},"קדימה-צורן":{},"קלנסווה":{},"רמות השבים":{},"רמת הכובש":{},"רעננה":{},"רשפון":{},"שדה ורבורג":{},"שדי חמד":{},"שושנת העמקים":{},"שער אפרים":{},"שערי תקווה":{},"שפיים":{},"תחנת רכבת ראש העין":{},"תל יצחק":{},"תל מונד":{},"תנובות":{}},"ירושלים":{"אבן ספיר":{},"אורה":{},"בית זית":{},"גבעת זאב":{},"ירושלים - אזור תעשייה עטרות":{},"ירושלים - דרום":{},"ירושלים - כפר עקב":{},"ירושלים - מזרח":{},"ירושלים - מערב":{},"ירושלים - מרכז":{},"ירושלים - צפון":{},"מבשרת ציון":{},"מוצא עילית":{},"נבי סמואל":{},"עמינדב":{},"פנימיית עין כרם":{}},"דרום הגולן":{"אבני איתן":{},"אזור תעשייה בני יהודה":{},"אלוני הבשן":{},"אלי עד":{},"אלמגור":{},"אניעם":{},"אפיק":{},"אשדות יעקב איחוד":{},"אשדות יעקב מאוחד":{},"בני יהודה וגבעת יואב":{},"גשור":{},"האון":{},"חד נס":{},"חמת גדר":{},"חספין":{},"יונתן":{},"כנף":{},"כפר חרוב":{},"מבוא חמה":{},"מיצר":{},"מסדה":{},"מעגן":{},"מעלה גמלא":{},"נאות גולן":{},"נוב":{},"נטור":{},"עין גב":{},"קדמת צבי":{},"קצרין":{},"קצרין - אזור תעשייה":{},"קשת":{},"רמות":{},"רמת מגשימים":{},"שער הגולן":{},"תל קציר":{}},"שומרון":{"אבני חפץ":{},"אזור תעשייה בראון":{},"אזור תעשייה שער בנימין":{},"אחיה":{},"איתמר":{},"אלון מורה":{},"אריאל":{},"בית אל":{},"בית אריה":{},"בית חורון":{},"ברוכין":{},"ברקן":{},"גבע בנימין":{},"גבעת אסף":{},"גבעת הראל וגבעת הרואה":{},"דולב":{},"הר ברכה":{},"חוות גלעד":{},"חוות יאיר":{},"חיננית":{},"חלמיש":{},"חרמש":{},"חרשה":{},"טל מנשה":{},"טלמון":{},"יצהר":{},"יקיר":{},"כוכב השחר":{},"כוכב יעקב":{},"כפר תפוח":{},"מבוא דותן":{},"מגדלים":{},"מגרון":{},"מעלה לבונה":{},"מעלה מכמש":{},"מעלה שומרון":{},"נופי נחמיה":{},"נופים":{},"נחליאל":{},"ניל''י":{},"נעלה":{},"נריה":{},"עדי עד":{},"עופרים":{},"עטרת":{},"עלי":{},"עלי זהב":{},"עמיחי":{},"עמנואל":{},"ענב":{},"עפרה":{},"פדואל":{},"פסגות":{},"קדומים":{},"קידה":{},"קריית נטפים":{},"קרני שומרון":{},"רבבה":{},"רחלים":{},"ריחן":{},"רימונים":{},"שבות רחל":{},"שבי שומרון":{},"שילה":{},"שקד":{},"תל ציון":{}},"ים המלח":{"אבנת":{},"אלמוג":{},"בית הערבה":{},"בתי מלון ים המלח":{},"ורד יריחו":{},"מלונות ים המלח מרכז":{},"מצדה":{},"מצוקי דרגות":{},"מצפה שלם":{},"מרחצאות עין גדי":{},"מרכז אזורי מגילות":{},"נאות הכיכר":{},"נווה זוהר":{},"עין בוקק":{},"עין גדי":{},"עין תמר":{},"קליה":{}},"עוטף עזה":{"אבשלום":{},"אור הנר":{},"ארז":{},"בארי":{},"בני נצרים":{},"גבים, מכללת ספיר":{},"גברעם":{},"דקל":{},"זיקים":{},"זמרת, שובה":{},"חולית":{},"יבול":{},"יד מרדכי":{},"יכיני":{},"יתד":{},"כיסופים":{},"כפר מימון ותושיה":{},"כפר עזה":{},"כרם שלום":{},"כרמיה":{},"מבטחים, עמיעוז, ישע":{},"מגן":{},"מטווח ניר עם":{},"מפלסים":{},"נווה":{},"נחל עוז":{},"ניר יצחק":{},"ניר עוז":{},"נירים":{},"נתיב העשרה":{},"סופה":{},"סעד":{},"עין הבשור":{},"עין השלושה":{},"עלומים":{},"פרי גן":{},"צוחר, אוהד":{},"רעים":{},"שדה אברהם":{},"שדה ניצן":{},"שדרות, איבים, ניר עם":{},"שוקדה":{},"שלומית":{},"תלמי אליהו":{},"תלמי יוסף":{},"תקומה":{},"תקומה וחוות יזרעם":{}},"יהודה":{"אדורה":{},"אדוריים":{},"אזור תעשייה מישור אדומים":{},"אזור תעשייה מיתרים":{},"אלון":{},"אלון שבות":{},"אליאב":{},"אלעזר":{},"אמציה":{},"אפרת":{},"בית חגי":{},"בית יתיר":{},"ביתר עילית":{},"בני דקלים":{},"בת עין":{},"גבעות":{},"הר גילה":{},"הר עמשא":{},"חברון":{},"חוות שדה בר":{},"טנא עומרים":{},"כפר אדומים":{},"כפר אלדד":{},"כפר עציון":{},"כרמי צור":{},"כרמי קטיף":{},"כרמל":{},"מגדל עוז":{},"מיצד":{},"מעון":{},"מעלה אדומים":{},"מעלה חבר":{},"מעלה עמוס":{},"מעלה רחבעם":{},"מצפה יריחו":{},"נגוהות":{},"נווה דניאל":{},"נופי פרת":{},"נוקדים":{},"נטע":{},"סוסיא":{},"עלמון":{},"עשאהל":{},"עתניאל":{},"פני קדם":{},"קדר":{},"קרית ארבע":{},"ראש צורים":{},"שומריה":{},"שמעה":{},"שני ליבנה":{},"שקף":{},"תלם":{},"תקוע":{}},"צפון הגולן":{"אודם":{},"אורטל":{},"אל רום":{},"בוקעתא":{},"מג'דל שמס":{},"מסעדה":{},"מרום גולן":{},"נווה אטי''ב":{},"נמרוד":{},"עין זיוון":{},"עין קנייא":{},"קלע":{},"שעל":{}},"גליל תחתון":{"בית ירח":{},"אזור תעשייה צמח":{},"אזור תעשייה קדמת גליל":{},"אלומות":{},"אפיקים":{},"ארבל":{},"אתר ההנצחה גולני":{},"בית זרע":{},"גבעת אבני":{},"גינוסר":{},"דגניה א":{},"דגניה ב":{},"הודיות":{},"הזורעים":{},"המכללה האקדמית כנרת":{},"ואדי אל חמאם":{},"חוקוק":{},"טבריה":{},"יבנאל":{},"כינרת מושבה":{},"כינרת קבוצה":{},"כפר זיתים":{},"כפר חיטים":{},"כפר כמא":{},"כפר נהר הירדן":{},"לביא":{},"לבנים":{},"מגדל":{},"מצפה":{},"פוריה כפר עבודה":{},"פוריה נווה עובד":{},"פוריה עילית":{},"רביד":{},"שדה אילן":{},"שרונה":{}},"ואדי ערה":{"אום אל פחם":{},"אום אל קוטוף":{},"אזור תעשייה יקנעם עילית":{},"אזור תעשייה מבוא כרמל":{},"אל עריאן":{},"אליקים":{},"באקה אל גרבייה":{},"בית סוהר מגידו":{},"ברטעה":{},"ג'ת":{},"גבעת ניל''י":{},"גבעת עוז":{},"גלעד":{},"דליה":{},"חריש":{},"יקנעם המושבה והזורע":{},"יקנעם עילית":{},"כפר קרע":{},"קיבוץ מגידו":{},"מגל":{},"מדרך עוז":{},"מועאוויה":{},"מי עמי":{},"מייסר":{},"מעלה עירון":{},"מצפה אילן":{},"מצר":{},"משמר העמק":{},"עין אל-סהלה":{},"עין העמק":{},"עין השופט":{},"ערערה":{},"קציר":{},"רגבים":{},"רמות מנשה":{},"רמת השופט":{}},"העמקים":{"אום אל-גנם":{},"אורנים":{},"אזור תעשייה אלון התבור":{},"אזור תעשייה מבואות הגלבוע":{},"אזור תעשייה ציפורית":{},"אחוזת ברק":{},"אילניה":{},"אכסאל":{},"אל-ח'וואלד מערב":{},"אלון הגליל":{},"אלוני אבא":{},"אלונים":{},"בית לחם הגלילית":{},"בית סוהר שיטה וגלבוע":{},"בית קשת":{},"בית שערים":{},"בלפוריה":{},"בסמת טבעון":{},"קבוצת גבע":{},"גבעת אלה":{},"גבת":{},"גדעונה":{},"גזית":{},"גן נר":{},"גניגר":{},"דבוריה":{},"דברת":{},"דחי":{},"הושעיה":{},"היוגב":{},"הסוללים":{},"הרדוף":{},"זרזיר":{},"ח'וואלד":{},"חג'אג'רה":{},"טמרה בגלבוע":{},"יזרעאל":{},"יפיע":{},"יפעת":{},"ישובי אומן":{},"מרכז חבר":{},"ישובי יעל":{},"כדורי":{},"כעביה":{},"כעביה טבאש":{},"כפר ברוך":{},"כפר גדעון":{},"כפר החורש":{},"כפר טבאש":{},"כפר יהושע":{},"כפר יחזקאל":{},"כפר כנא":{},"כפר מצר":{},"כפר קיש":{},"כפר תבור":{},"כפר תקווה":{},"מגדל העמק":{},"מגן שאול":{},"מוקיבלה":{},"מזרע":{},"מנשית זבדה":{},"מרחביה מושב":{},"מרחביה קיבוץ":{},"משהד":{},"נעורה":{},"נהלל":{},"נופית":{},"נורית":{},"נין":{},"נצרת":{},"נוף הגליל":{},"סואעד חמירה":{},"סולם":{},"סנדלה":{},"עדי":{},"עילוט":{},"עין דור":{},"עין חרוד":{},"עין מאהל":{},"עפולה":{},"ציפורי":{},"קריית טבעון-בית זייד":{},"ראס עלי":{},"ריינה":{},"רם און":{},"רמת דוד":{},"רמת ישי":{},"רמת צבי":{},"שבלי":{},"שדה יעקב":{},"שדמות דבורה":{},"שמשית":{},"שער העמקים":{},"שריד":{},"תחנת רכבת כפר יהושוע":{},"תל יוסף":{},"תל עדשים":{},"תמרת":{}},"מרכז הנגב":{"אום בטין":{},"אזור תעשייה עידן הנגב":{},"אל סייד":{},"אשכולות":{},"אתר דודאים":{},"באר שבע - דרום":{},"באר שבע - מזרח":{},"באר שבע - מערב":{},"באר שבע - צפון":{},"בית קמה":{},"גבעות בר":{},"גבעות גורל":{},"דביר":{},"חורה":{},"חצרים":{},"כרמים":{},"כרמית":{},"להב":{},"להבים":{},"לקיה":{},"מיתר":{},"משמר הנגב":{},"מתחם צומת שוקת":{},"נבטים":{},"סנסנה":{},"עומר":{},"רהט":{},"שגב שלום":{},"שובל":{},"תל שבע":{},"תארבין":{}},"מערב הנגב":{"אופקים":{},"אורים":{},"אזור תעשייה נ.ע.מ":{},"אשבול":{},"אשל הנשיא":{},"בטחה":{},"בית הגדי":{},"ברור חיל":{},"ברוש":{},"גבולות":{},"גילת":{},"דורות":{},"דניאל":{},"זרועה":{},"חוות שיקמים":{},"יושיביה":{},"מבועים":{},"מסלול":{},"מעגלים, גבעולים, מלילות":{},"ניר משה":{},"ניר עקיבא":{},"נתיבות":{},"פדויים":{},"פטיש":{},"פעמי תש''ז":{},"צאלים":{},"קלחים":{},"קריית חינוך מרחבים":{},"רוחמה":{},"רנן":{},"שבי דרום":{},"שדה צבי":{},"שיבולים":{},"שרשרת":{},"תאשור":{},"תדהר":{},"תלמי ביל''ו":{},"תפרח":{}},"גוש דן":{"אור יהודה":{},"אזור":{},"בני ברק":{},"בת-ים":{},"גבעת השלושה":{},"גבעת שמואל":{},"גבעתיים":{},"גני תקווה":{},"גת רימון":{},"הרצליה - מערב":{},"הרצליה - מרכז וגליל ים":{},"חולון":{},"יהוד-מונוסון":{},"כפר סירקין":{},"כפר שמריהו":{},"מגשימים":{},"מעש":{},"מקווה ישראל":{},"מתחם פי גלילות":{},"סביון":{},"סינמה סיטי גלילות":{},"פתח תקווה":{},"קריית אונו":{},"רמת גן - מזרח":{},"רמת גן - מערב":{},"רמת השרון":{},"תל אביב - דרום העיר ויפו":{},"תל אביב - מזרח":{},"תל אביב - מרכז העיר":{},"תל אביב - עבר הירקון":{}},"המפרץ":{"אושה":{},"איבטין":{},"בית עלמין תל רגב":{},"החותרים":{},"חיפה - כרמל ועיר תחתית":{},"חיפה - מערב":{},"חיפה - נווה שאנן ורמות כרמל":{},"חיפה - קריית חיים ושמואל":{},"חיפה-מפרץ":{},"טירת כרמל":{},"יגור":{},"כפר ביאליק":{},"כפר גלים":{},"כפר המכבי":{},"כפר חסידים":{},"נשר":{},"קריית ביאליק":{},"קריית ים":{},"קריית מוצקין":{},"קריית אתא":{},"רכסים":{},"רמת יוחנן":{}},"ירקון":{"אזור תעשייה אפק ולב הארץ":{},"אזור תעשייה חבל מודיעין":{},"אלעד":{},"בארות יצחק":{},"בית נחמיה":{},"בית עריף":{},"בני עטרות":{},"ברקת":{},"גבעת כ''ח":{},"גמזו":{},"חדיד":{},"חשמונאים":{},"טירת יהודה":{},"כפר דניאל":{},"כפר האורנים":{},"כפר טרומן":{},"כפר רות":{},"לפיד":{},"מבוא חורון":{},"מבוא מודיעים":{},"מודיעין":{},"מודיעין - ישפרו סנטר":{},"מודיעין - ליגד סנטר":{},"מודיעין עילית":{},"מזור":{},"מתתיהו":{},"נוף איילון":{},"נופך":{},"נחלים":{},"נחשונים":{},"עינת":{},"ראש העין":{},"רינתיה":{},"שהם":{},"שילת":{},"שעלבים":{},"תעשיון חצב":{}},"מערב לכיש":{"אזור תעשייה הדרומי אשקלון":{},"אזור תעשייה צפוני אשקלון":{},"אשקלון - דרום":{},"אשקלון - צפון":{},"באר גנים":{},"בית שקמה":{},"ברכיה":{},"בת הדר":{},"גיאה":{},"הודיה":{},"חלץ":{},"כוכב מיכאל":{},"כפר סילבר":{},"מבקיעים":{},"משען":{},"ניצן":{},"ניצנים":{},"ניר ישראל":{},"תלמי יפה":{}},"הכרמל":{"אזור תעשייה ניר עציון":{},"בית אורן":{},"בית סוהר קישון":{},"בית צבי":{},"בת שלמה":{},"גבע כרמל":{},"גבעת וולפסון":{},"דור":{},"דלית אל כרמל":{},"הבונים":{},"יערות הכרמל":{},"כלא דמון":{},"כפר הנוער ימין אורד":{},"כרם מהר''ל":{},"מאיר שפיה":{},"מגדים":{},"מרכז מיר''ב":{},"נווה ים":{},"נחשולים":{},"ניר עציון":{},"עופר":{},"עין איילה":{},"עין הוד":{},"עין חוד":{},"עין כרמל":{},"עספיא":{},"עתלית":{},"פוריידיס":{},"צרופה":{}},"השפלה":{"אזור תעשייה נשר - רמלה":{},"אחיסמך":{},"אחיעזר":{},"אירוס":{},"באר יעקב":{},"בית דגן":{},"בית חנן":{},"בית חשמונאי":{},"בית עובד":{},"בית עוזיאל":{},"בן שמן":{},"גאליה":{},"גזר":{},"גיבתון":{},"גינתון":{},"גן שורק":{},"גן שלמה":{},"גנות":{},"גני הדר":{},"גני יוחנן":{},"זיתן":{},"חולדה":{},"חמד":{},"יגל":{},"יד רמב''ם":{},"יסודות":{},"יציץ":{},"ישרש":{},"כפר ביל''ו":{},"כפר בן נון":{},"כפר חב''ד":{},"כפר נוער בן שמן":{},"כפר שמואל":{},"כרמי יוסף":{},"לוד":{},"מזכרת בתיה":{},"מצליח":{},"משמר איילון":{},"משמר דוד":{},"משמר השבעה":{},"נטעים":{},"ניר צבי":{},"נס ציונה":{},"נען":{},"נצר חזני":{},"נצר סרני":{},"סתריה":{},"עזריה":{},"עיינות":{},"פארק תעשיות פלמחים":{},"פדיה":{},"פתחיה":{},"צפריה":{},"קריית עקרון":{},"ראשון לציון - מזרח":{},"ראשון לציון - מערב":{},"רחובות":{},"רמות מאיר":{},"רמלה":{},"תעשיון צריפין":{}},"בקעת בית שאן":{"אזור תעשייה צבאים":{},"בית אלפא וחפציבה":{},"בית השיטה":{},"בית יוסף":{},"בית שאן":{},"גשר":{},"חוות עדן":{},"חמדיה":{},"טייבה בגלבוע":{},"טירת צבי":{},"ירדנה":{},"כפר גמילה מלכישוע":{},"כפר רופין":{},"מולדת":{},"מירב":{},"מנחמיה":{},"מסילות":{},"מעוז חיים":{},"מעלה גלבוע":{},"נווה אור":{},"נוה איתן":{},"ניר דוד":{},"עין הנצי''ב":{},"רוויה":{},"רחוב":{},"רשפים":{},"שדה אליהו":{},"שדה נחום":{},"שדי תרומות":{},"שלוחות":{},"שלפים":{},"תל תאומים":{}},"אילת":{"אזור תעשייה שחורת":{},"אילות":{},"אילת":{}},"ערבה":{"אל עמארני, אל מסק":{},"אליפז ומכרות תמנע":{},"באר אורה":{},"גרופית":{},"חוות ערנדל":{},"חי-בר יטבתה":{},"חצבה":{},"יהל":{},"יטבתה":{},"כושי רמון":{},"לוטן":{},"נאות סמדר":{},"נווה חריף":{},"סמר":{},"ספיר":{},"עידן":{},"עין חצבה":{},"עין יהב":{},"עיר אובות":{},"פארן":{},"צופר":{},"צוקים":{},"קטורה":{},"שחרות":{},"שיטים":{}},"בקעה":{"ארגמן":{},"בקעות":{},"גיתית":{},"גלגל":{},"חמדת":{},"חמרה":{},"ייט''ב":{},"יפית":{},"מבואות יריחו":{},"מחולה":{},"מכורה":{},"מעלה אפרים":{},"משואה":{},"משכיות":{},"נעמה":{},"נערן":{},"נתיב הגדוד":{},"פצאל":{},"רועי":{},"רותם":{},"שדמות מחולה":{},"תומר":{}}}}
        icons = {1: "mdi:rocket-launch",2: "mdi:home-alert",3: "mdi:earth-box",4: "mdi:chemical-weapon",5: "mdi:waves",6: "mdi:airplane",7: "mdi:skull",8: "mdi:alert",9: "mdi:alert",10: "mdi:alert",11: "mdi:alert",12: "mdi:alert",13: "mdi:run-fast",}
        icon_alert = "mdi:alert"
        emojis = {1: "🚀",2: "⚠️",3: "🌍",4: "☢️",5: "🌊",6: "🛩️",7: "💀",8: "❗",9: "❗",10: "❗",11: "❗",12: "❗",13: "👣👹",}
        icon_emoji = "🚨"
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                response_data = codecs.decode(response.content, 'utf-8-sig')
                current_value = self.get_state("binary_sensor.oref_alert", attribute="prev_data")
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
                                
                            # Standardize lamas cities once globally
                            for area, cities in lamas['areas'].items():
                                if isinstance(cities, str):
                                    cities = cities.split(',')
                                standardized_cities = [re.sub(r'[\-\,\(\)\s]+', '', city).strip() for city in cities]
                                lamas['areas'][area] = standardized_cities

                            city_names = alerts_data.split(',')
                            standardized_names = [re.sub(r'[\-\,\(\)\s]+', '', name).strip() for name in city_names]

                            areas = []

                            for area, cities in lamas['areas'].items():
                                if any(city in cities for city in standardized_names):
                                    areas.append(area)

                            areas.sort()

                            if len(areas) > 1:
                                all_but_last = ", ".join(areas[:-1])
                                areas_text = f"{all_but_last} ו{areas[-1]}"
                            else:
                                areas_text = areas[0]

                            areas_text = areas_text.replace('השפלה', 'שפלה')
                            areas_alert = areas_text
                            
                            
                            if not current_value or current_value != alerts_data:
                                self.set_state("binary_sensor.oref_alert", state="on", attributes={
                                    "id": data.get('id', None),
                                    "cat": data.get('cat', None),
                                    "title": alert_title,
                                    "desc": data.get('desc', None),
                                    "areas": areas_alert,
                                    "data": alerts_data,
                                    "data_count": data_count,
                                    "duration": duration,
                                    "last_changed": datetime.now().isoformat(),
                                    "prev_cat": data.get('cat', None),
                                    "prev_title": alert_title,
                                    "prev_desc": data.get('desc', None),
                                    "prev_areas": areas_alert,
                                    "prev_data": alerts_data,
                                    "prev_data_count": data_count,
                                    "prev_duration": duration,
                                    "prev_last_changed": datetime.now().isoformat(),
                                    "icon": icon_alert,
                                    "emoji":  icon_emoji,
                                    "friendly_name": alert_title,
                                },
                            )
                                text_status = f"{alert_title} ב{areas_alert} - {alerts_data}"
                                if len(text_status) > 255:
                                    text_status = text_status[:252] + "..."
                                self.set_state("input_text.last_alert_in_israel", state=f"{text_status}", attributes={"icon": f"{icon_alert}"},)
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
                                    "areas": "",
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
                            "areas": "",
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
7. With a file editor, open the **/config/appdaemon/apps/apps.yaml** file and add/enter the following lines
```yaml
orefalert:
  module: orefalert
  class: OrefAlert
```
8. **Restart** the **AppDaemon** addon.

After restarting the AppDaemon addon, Home Assistant will generate two entities. Input text named *last alert in Israel* and a binary sensor named *oref alert* that you can incorporate into your automations and dashboards. *All sensor attributes will remain empty until an alert occurs, at which point they will be updated.*
## Verifying Sensor Functionality and Troubleshooting in AppDaemon
To ensure that the sensor is functioning correctly, it is recommended to follow these steps after installing the script:
1. Access the AppDaemon web interface, which can be found on the main page of the add-on in Home Assistant, located to the right of the "start" button. If you are accessing this page from your local network, you can use the following link: http://homeassistant.local:5050/aui/index.html#/state?tab=apps (If the link is broken, replace "homeassistant.local" with your Home Assistant's IP address).
2. Within the state page, you can monitor the sensor to check if it is working as expected.
![Untitled-1](https://github.com/idodov/RedAlert/assets/19820046/664ece42-52bb-498b-8b3c-12edf41aaedb)

In case the sensor isn't functioning properly, make sure to review the logs. You can access the logs from the main AppDaemon page on the screen. This will help you identify and resolve any issues or problems that may arise.
## Red Alert Trigger for Cities with Similar Character Patterns, Specific City, and Cities With Multiple Alert Zones
Choosing the right method for binary sensors based on city names and alert zones is crucial. To distinguish similar city names, like "Yavne" and "Gan Yavne", it's better to use the SPLIT function instead of REGEX_SEARCH.

For residents in cities with multiple alert zones: Ashkelon, Beersheba, Ashdod, Herzliya, Hadera, Haifa, Jerusalem, Netanya, Rishon Lezion, Ramat Gan, and Tel Aviv-Yafo - to set up triggers or sensors covering the entire city, it's recommended to use the REGEX_SEARCH function. This ensures they receive alerts for the whole city, even if it has multiple alert zones. This approach provides comprehensive coverage for these cities.
## Sample Trigger or Value Template for a Binary Sensor
To create a sensor that activates only when an attack occurs in a specific city that has similar character patterns in other city names, you should use the following approach. For example, if you want to create a sensor that activates when **only** "יבנה" and **not** "גן יבנה" is attacked, you can use the following code syntax.
### Yavne city and not Gan-Yavne city
```
{{ "יבנה" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
### Multiple cities or city areas
```
{{ "אירוס" in state_attr('binary_sensor.oref_alert', 'data').split(', ')
 or "בית חנן" in state_attr('binary_sensor.oref_alert', 'data').split(', ')
 or "גן שורק" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
### Cities With Multiple Zones:
In cities with multiple zones, relying solely on the SPLIT function won't be effective if you've only defined the city name. If you need a sensor that triggers for all zones within the 11 cities divided into multiple alert zones, it's advisable to utilize the SEARCH_REGEX function instead of splitting the data.
```
{{ state_attr('binary_sensor.oref_alert', 'data') | regex_search("תל אביב") }} 
```
If you want to trigger a specific area, use the SPLIT function and make sure to type the city name and area **exactly** as they appear in https://www.oref.org.il/12481-he/Pakar.aspx
```
{{ "תל אביב - מרכז העיר" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
```
### Metropolitan Areas
Israel is segmented into 30 metropolitan areas, allowing you to determine the general status of nearby towns without the need to specify each one individually. To achieve this, you can utilize the "areas" attribute. Here's the list of the 30 metropolitan areas in Israel, presented in alphabetical order:

אילת, בקעה, בקעת בית שאן, גוש דן, גליל עליון, גליל תחתון, דרום הגולן, דרום הנגב, הכרמל, המפרץ, העמקים, השפלה, ואדי ערה, יהודה, ים המלח, ירושלים, ירקון, לכיש,  מנשה, מערב הנגב, מערב לכיש, מרכז הגליל, מרכז הנגב, עוטף עזה, 
ערבה, צפון הגולן, קו העימות, שומרון, שפלת יהודה ושרון
```
{{ "גוש דן" in state_attr('binary_sensor.oref_alert', 'areas').split(', ') }}
```
## Red Alert Trigger for Particular Type of Alert:
The **'cat'** attribute defines the alert type, with a range from 1 to 13. You have the option to set up a binary sensor for a particular type of alert with or without any city or area of your choice.
| Cat (number) | Type of Alert |
| ---- | --- |
| 1 | Missle Attack |
| 6 | Unauthorized Aircraft Penetration |
| 13 | Infiltration of Terrorists |

**Trigger for Automation**
```
{{ state_attr('binary_sensor.oref_alert', 'cat') == '6' }}
```
### Sample trigger alert for unauthorized aircraft penetration in Nahal-Oz
**Trigger for Automation**
```yaml
{{ state_attr('binary_sensor.oref_alert', 'cat') == '6'
and "נחל עוז" in state_attr('binary_sensor.oref_alert', 'data').split(', ') }}
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
Using this script, you have the flexibility to include additional information, such as the **precise time the alert was triggered**.

![TILIMA](https://github.com/idodov/RedAlert/assets/19820046/4ba18dde-ae0c-4415-a55d-80ed0c010cbc)
![LAST](https://github.com/idodov/RedAlert/assets/19820046/ae52bc94-46ba-4cdb-b92b-36220500ee48)
```
type: markdown
content: >-
  <center><h3>{% if state_attr('binary_sensor.oref_alert', 'data_count') > 0 %}
  כרגע יש {% if state_attr('binary_sensor.oref_alert', 'data_count') > 1 %}{{
  state_attr('binary_sensor.oref_alert', 'data_count') }} התרעות פעילות{% elif
  state_attr('binary_sensor.oref_alert', 'data_count') == 1 %} התרעה פעילה אחת{%
  endif %}{% else %} אין התרעות פעילות{% endif %}</h3>

  {% if state_attr('binary_sensor.oref_alert', 'data_count') > 0 %}<h2>{{
  state_attr('binary_sensor.oref_alert', 'emoji') }} {{
  state_attr('binary_sensor.oref_alert', 'title') }}</h2> <h3>{{
  state_attr('binary_sensor.oref_alert', 'data') }}</h3> **{{
  state_attr('binary_sensor.oref_alert', 'desc') }}** {% endif %}

  {% if state_attr('binary_sensor.oref_alert', 'last_changed') |
  regex_match("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\d{2}:\d{2}.\d+$") %}

  {% set last_changed_timestamp = state_attr('binary_sensor.oref_alert',
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
  <ha-icon icon="{{ state_attr('binary_sensor.oref_alert', 'icon')
  }}"></ha-icon> {% if state_attr('binary_sensor.oref_alert', 'data_count') > 0
  %}כרגע יש {% if state_attr('binary_sensor.oref_alert', 'data_count') > 1 %}{{
  state_attr('binary_sensor.oref_alert', 'data_count') }} התרעות פעילות{% elif
  state_attr('binary_sensor.oref_alert', 'data_count') == 1 %} התרעה פעילה אחת{%
  endif %}{% else %}אין התרעות פעילות{% endif %}{% if
  state_attr('binary_sensor.oref_alert', 'data_count') > 0 %}

  <ha-alert alert-type="error" title="{{ state_attr('binary_sensor.oref_alert',
  'title') }}">{{ state_attr('binary_sensor.oref_alert', 'data') }}</ha-alert>

  <ha-alert alert-type="warning">{{ state_attr('binary_sensor.oref_alert',
  'desc') }}</ha-alert>

  {% endif %}

  {% if state_attr('binary_sensor.oref_alert', 'last_changed') |
  regex_match("^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\d{2}:\d{2}.\d+$") %}

  {% set last_changed_timestamp = state_attr('binary_sensor.oref_alert',
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
      - binary_sensor.oref_alert
    from: "off"
    to: "on"
condition: []
action:
  - service: notify.mobile_app_#your phone#
    data:
      message: "{{ state_attr('binary_sensor.oref_alert', 'data') }}"
      title: "{{ state_attr('binary_sensor.oref_alert', 'title') }} ב{{ state_attr('binary_sensor.oref_alert', 'areas') }}"
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
        {{ state_attr('binary_sensor.oref_alert', 'duration') }}
    target:
      entity_id: timer.oref_alert
  - service: notify.mobile_app_#your phone#
    data:
      title: ההתרעה הוסרה
      message: אפשר לחזור לשגרה
```
## Usage *input_text.last_alert_in_israel* for Home Assistant
This entity stores the alert history for viewing on the logbook screen.   
![logobok](https://github.com/idodov/RedAlert/assets/19820046/725e93bc-3c0d-4a1c-8310-a5db08568c26)

You can use this entity as an automation trigger for demonstration purposes. However, it's important to note that it's strongly advised not to rely on this entity for creating sub-sensors or triggers in production scenarios.

To trigger a check for any city, area name or title, you can use the following line of code:
```
{{ 'אור יהודה' in states('input_text.last_alert_in_israel') }}
```
Here's an example automation for demonstration purposes:
```
mode: single
trigger:
  - platform: template
    value_template: |
      {{ 'אור יהודה' in states('input_text.last_alert_in_israel') }}
condition: []
action:
  - service: light.turn_on
    data:
      flash: long
      rgb_color:
        - 255
        - 0
        - 0
    target:
      entity_id: light.#RGB_LIGHT#
```
To test it, navigate to the Developer Tools State screen and select the "input_text.last_alert_in_israel" entity. Here, you'll find the last historical data. If no alerts have occurred yet, you'll see a demo list of cities.

![eeeeee](https://github.com/idodov/RedAlert/assets/19820046/4b072463-19ff-4659-bf0e-9181f8e68e3d)

To trigger your automation, clear the existing data and enter the city, area name or any word from the title you want to use as a trigger. Click **SET STATE** and the entity data will be updated, subsequently triggering your automation.

It's important to note that while this approach may work for live data when alerts occur and function most of the time, **it's not recommended as the primary automation for alerts**, as it may not work reliably under all circumstances.
## Sensor Data Attributes
```yaml
{{ state_attr('binary_sensor.oref_alert', 'title') }} #כותרת 
{{ state_attr('binary_sensor.oref_alert', 'data') }} #רשימת ישובים
{{ state_attr('binary_sensor.oref_alert', 'areas') }} #רשימת אזורים
{{ state_attr('binary_sensor.oref_alert', 'desc') }} #הסבר התגוננות
{{ state_attr('binary_sensor.oref_alert', 'cat') }} #קטגוריה
{{ state_attr('binary_sensor.oref_alert', 'duration') }} #זמן שהייה במרחב מוגן בשניות לצורך כיוון טיימר
{{ state_attr('binary_sensor.oref_alert', 'id') }} #מספר ייחודי
{{ state_attr('binary_sensor.oref_alert', 'data_count') }} #מספר התרעות פעילות
{{ state_attr('binary_sensor.oref_alert', 'emoji') }} #אימוג'י עבור סוג התרעה

{{ state_attr('binary_sensor.oref_alert', 'prev_title') }} #כותרת אחרונה שהיתה פעילה
{{ state_attr('binary_sensor.oref_alert', 'prev_data') }} #רשימת ישובים אחרונים
{{ state_attr('binary_sensor.oref_alert', 'prev_areas') }} #רשימת אזורים אחרונים
{{ state_attr('binary_sensor.oref_alert', 'prev_desc') }} #הסבר התגוננות אחרון
{{ state_attr('binary_sensor.oref_alert', 'prev_cat') }} #קטגוריה אחרונה
{{ state_attr('binary_sensor.oref_alert', 'prev_duration') }} #זמן שהייה האחרון שהיה במרחב מוגן בשניות לצורך כיוון טיימר
{{ state_attr('binary_sensor.oref_alert', 'prev_data_count') }} #מספר התרעות בו זמנית קודמות
```
### Example Data When There is Active Alert (state is on)
```
id: '133413399870000000'
cat: '1'
title: ירי רקטות וטילים
friendly_name:  ירי רקטות וטילים
data: נחל עוז
desc: היכנסו למרחב המוגן ושהו בו 10 דקות
data_count: 1
areas: עוטף עזה
emoji: 🚀
```
### Example Data When There is No Active Alert (state is off):
```
id: ''
cat: 0
title: אין התרעות
desc: ''
data: ''
data_count: 0
duration: 0
last_changed: ''
prev_cat: 0
prev_title: ירי רקטות וטילים
prev_desc: היכנסו למרחב המוגן ושהו בו 10 דקות
prev_data: אזור תעשייה הדרומי אשקלון
prev_areas: מערכ לכיש
prev_data_count: 1
emoji: 🚨
```
"prev_*" stores the most recent information when the sensor was active. These attributes will become available after the first alert.
_______
*This code is based on and inspired by https://gist.github.com/shahafc84/5e8b62cdaeb03d2dfaaf906a4fad98b9*
