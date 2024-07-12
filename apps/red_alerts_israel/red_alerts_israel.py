"""
Red Alerts Israel - Appdaemon Script for Home Assistant
-------------------------------------------------------
The script will create four Home Assistant sensors, using the name you choose (in sensor_name). As exemplified here, the value is ‘red_alert’:

binary_sensor.red_alert: This sensor will be on when there is an alarm anywhere in Israel.
binary_sensor.red_alert_city: This sensor will be on when there is an alarm in any city that is on the city_names list.
text_input.red_alert: This sensor will store all historical data for viewing in the Home Assistant logbook.
input_boolean.red_alert: This sensor will activate a fake alert design to test automations.

Additionally, the script can save the history of all alerts in dedicated TXT and CSV files, which will be accessible from the WWW folder inside the Home Assistant directory.

The sensor attributes contain several message formats for display or sending notifications. You also have the flexibility to display or use any of the attributes of the sensor to create more sub-sensors from the main binary_sensor.red_alert.

Configuration: 
1. Open appdaemon/apps/apps.yaml
2. Add the code line
3. Save the code after you choose the city names as exemplified. You can add as many cities as you want. 
* City names can be found here: https://github.com/idodov/RedAlert/blob/main/cities_name.md
---
red_alerts_israel:
  module: red_alerts_israel
  class: Red_Alerts_Israel
  interval: 2 
  timer: 120 
  save_2_file: True 
  sensor_name: "red_alert" 
  city_names: 
    - אזור תעשייה אכזיב מילואות
    - שלומי
    - כיסופים
    - שדרות, איבים, ניר עם

"""

import requests
import re
import time
import json
import codecs
import traceback
import random
import os
from datetime import datetime
from appdaemon.plugins.hass.hassapi import Hass

url = "https://www.oref.org.il/warningMessages/alert/alerts.json"
headers = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3', 'Referer': 'https://www.oref.org.il/', 'X-Requested-With': 'XMLHttpRequest', 'Content-Type': 'application/json',}
lamas_data = {"areas":{"רצועת עזה":{"עזה":{}},"גליל עליון":{"אבו סנאן":{},"אור הגנוז":{},"אזור תעשייה בר-לב":{},"אזור תעשייה חצור הגלילית":{},"אזור תעשייה כרמיאל":{},"אזור תעשייה צ.ח.ר":{},"אזור תעשייה שער נעמן":{},"אחיהוד":{},"איילת השחר":{},"אליפלט":{},"אמירים":{},"אמנון":{},"אפק":{},"אשרת":{},"בוסתן הגליל":{},"ביריה":{},"בית ג'אן":{},"בית העמק":{},"בענה":{},"בר יוחאי":{},"ג'דידה מכר":{},"ג'וליס":{},"גדות":{},"גיתה":{},"דיר אל-אסד":{},"הר-חלוץ":{},"חולתה":{},"חצור הגלילית":{},"חרשים":{},"טובא זנגריה":{},"טל-אל":{},"ינוח-ג'ת":{},"יסוד המעלה":{},"יסעור":{},"ירכא":{},"כורזים ורד הגליל":{},"כחל":{},"כיסרא סמיע":{},"כישור":{},"כליל":{},"כמון":{},"כפר הנשיא":{},"כפר יסיף":{},"כפר מסריק":{},"כפר שמאי":{},"כרכום":{},"כרמיאל":{},"לבון":{},"לוחמי הגטאות":{},"לפידות":{},"מג'דל כרום":{},"מרכז אזורי מרום גליל":{},"מזרעה":{},"מחניים":{},"מירון":{},"מכמנים":{},"מנחת מחניים":{},"משמר הירדן":{},"נחף":{},"נס עמים":{},"נתיב השיירה":{},"סאג'ור":{},"ספסופה - כפר חושן":{},"עין אל אסד":{},"עין המפרץ":{},"עין כמונים":{},"עכו":{},"עכו - אזור תעשייה":{},"עמוקה":{},"עמיעד":{},"עמקה":{},"פלך":{},"פרוד":{},"צורית גילון":{},"צפת":{},"קדיתא":{},"קדרים":{},"ראמה":{},"ראש פינה":{},"רגבה":{},"שבי ציון":{},"שדה אליעזר":{},"שומרת":{},"שזור":{},"שייח' דנון":{},"שפר":{},"תובל":{}},"דרום הנגב":{"אבו קרינאת":{},"אבו תלול":{},"אורון תעשייה ומסחר":{},"אזור תעשייה דימונה":{},"אזור תעשייה רותם":{},"אל פורעה":{},"אשלים":{},"באר מילכה":{},"'ביר הדאג":{},"בית סוהר נפחא":{},"דימונה":{},"הר הנגב":{},"ואדי אל נעם דרום":{},"חירן":{},"טללים":{},"ירוחם":{},"כמהין":{},"כסייפה":{},"מדרשת בן גוריון":{},"ממשית":{},"מצפה רמון":{},"מרחב עם":{},"מרעית":{},"משאבי שדה":{},"ניצנה":{},"סעייה-מולדה":{},"עבדת":{},"עזוז":{},"ערד":{},"ערערה בנגב":{},"קדש ברנע":{},"קצר-א-סיר":{},"רביבים":{},"רתמים":{},"שאנטי במדבר":{},"שדה בוקר":{},"תל ערד":{}},"שפלת יהודה":{"אבו-גוש":{},"אביעזר":{},"אדרת":{},"אזור תעשייה ברוש":{},"אזור תעשייה הר טוב - צרעה":{},"אשתאול":{},"בית גוברין":{},"בית מאיר":{},"בית ניר":{},"בית נקופה":{},"בית שמש":{},"בקוע":{},"בר גיורא":{},"גבעות עדן":{},"גבעת יערים":{},"גבעת ישעיהו":{},"גיזו":{},"גלאון":{},"גפן":{},"הר אדר":{},"הראל":{},"זכריה":{},"זנוח":{},"טל שחר":{},"יד השמונה":{},"ישעי":{},"כסלון":{},"כפר אוריה":{},"כפר זוהרים":{},"כפר מנחם":{},"לוזית":{},"לטרון":{},"מבוא ביתר":{},"מחסיה":{},"מטע":{},"מסילת ציון":{},"מעלה החמישה":{},"נווה אילן":{},"נווה מיכאל - רוגלית":{},"נווה שלום":{},"נחושה":{},"נחם":{},"נחשון":{},"נטף":{},"נס הרים":{},"נתיב הל''ה":{},"עגור":{},"עין נקובא":{},"עין ראפה":{},"צובה":{},"צור הדסה":{},"צלפון":{},"צפרירים":{},"צרעה":{},"קריית יערים":{},"קריית ענבים":{},"רטורנו - גבעת שמש":{},"רמת רזיאל":{},"שדות מיכה":{},"שואבה":{},"שורש":{},"שריגים - ליאון":{},"תירוש":{},"תעוז":{},"תרום":{}},"מרכז הגליל":{"אבטליון":{},"אזור תעשייה תרדיון":{},"אעבלין":{},"אשבל":{},"אשחר":{},"בועיינה-נוג'ידאת":{},"ביר אלמכסור":{},"בית סוהר צלמון":{},"בית רימון":{},"דיר חנא":{},"דמיידה":{},"הררית יחד":{},"חוסנייה":{},"חזון":{},"חנתון":{},"טורעאן":{},"טמרה":{},"טפחות":{},"יובלים":{},"יודפת":{},"יעד":{},"כאבול":{},"כאוכב אבו אלהיג'א":{},"כלנית":{},"כפר חנניה":{},"כפר מנדא":{},"לוטם וחמדון":{},"מורן":{},"מורשת":{},"מנוף":{},"מסד":{},"מע'אר":{},"מעלה צביה":{},"מצפה אבי''ב":{},"מצפה נטופה":{},"מרכז אזורי משגב":{},"סכנין":{},"סלמה":{},"עוזייר":{},"עילבון":{},"עינבר":{},"עצמון - שגב":{},"עראבה":{},"ערב אל-נעים":{},"קורנית":{},"ראס אל-עין":{},"רומאנה":{},"רומת אל הייב":{},"רקפת":{},"שורשים":{},"שכניה":{},"שעב":{},"שפרעם":{}},"מנשה":{"אביאל":{},"אור עקיבא":{},"אזור תעשייה קיסריה":{},"אזור תעשייה רגבים":{},"אלוני יצחק":{},"בית חנניה":{},"בית ספר אורט בנימינה":{},"בנימינה":{},"ברקאי":{},"ג'סר א-זרקא":{},"גבעת חביבה":{},"גבעת עדה":{},"גן השומרון":{},"גן שמואל":{},"זכרון יעקב":{},"חדרה - מזרח":{},"חדרה - מערב":{},"חדרה - מרכז":{},"חדרה - נווה חיים":{},"כפר גליקסון":{},"כפר פינס":{},"להבות חביבה":{},"מאור":{},"מעגן מיכאל":{},"מעיין צבי":{},"מענית":{},"מרכז ימי קיסריה":{},"משמרות":{},"עין עירון":{},"עין שמר":{},"עמיקם":{},"פרדס חנה-כרכור":{},"קיסריה":{},"רמת הנדיב":{},"שדה יצחק":{},"שדות ים":{},"שער מנשה":{},"תלמי אלעזר":{}},"קו העימות":{"אביבים":{},"אבירים":{},"אבן מנחם":{},"אדמית":{},"אזור תעשייה אכזיב מילואות":{},"אזור תעשייה רמת דלתון":{},"אילון":{},"אלקוש":{},"בית הלל":{},"בית ספר שדה מירון":{},"בן עמי":{},"בצת":{},"ברעם":{},"ג'ש - גוש חלב":{},"גונן":{},"גורן":{},"גורנות הגליל":{},"געתון":{},"גשר הזיו":{},"דוב''ב":{},"דישון":{},"דלתון":{},"קיבוץ דן":{},"דפנה":{},"הגושרים":{},"הילה":{},"זרעית":{},"חוסן":{},"חורפיש":{},"חניתה":{},"יחיעם":{},"יערה":{},"יפתח":{},"יראון":{},"כברי":{},"כפר בלום":{},"כפר גלעדי":{},"כפר ורדים":{},"כפר יובל":{},"כפר סאלד":{},"כרם בן זמרה":{},"להבות הבשן":{},"לימן":{},"מרכז אזורי מבואות חרמון":{},"מטולה":{},"מלכיה":{},"מנות":{},"מנרה":{},"מעונה":{},"מעיין ברוך":{},"מעיליא":{},"מעלות תרשיחא":{},"מצובה":{},"מרגליות":{},"משגב עם":{},"מתת":{},"נאות מרדכי":{},"נהריה":{},"נווה זיו":{},"נטועה":{},"סאסא":{},"סער":{},"עבדון":{},"עברון":{},"ע'ג'ר":{},"עין יעקב":{},"עלמה":{},"עמיר":{},"ערב אל עראמשה":{},"פסוטה":{},"פקיעין":{},"צבעון":{},"צוריאל":{},"קריית שמונה":{},"ראש הנקרה":{},"ריחאנייה":{},"רמות נפתלי":{},"שאר ישוב":{},"שדה נחמיה":{},"שומרה":{},"שלומי":{},"שמיר":{},"שניר":{},"שתולה":{},"תל חי":{}},"לכיש":{"אביגדור":{},"אבן שמואל":{},"אורות":{},"אזור תעשייה באר טוביה":{},"אזור תעשייה כנות":{},"אזור תעשייה עד הלום":{},"אזור תעשייה קריית גת":{},"אזור תעשייה תימורים":{},"אחווה":{},"אחוזם":{},"איתן":{},"אל עזי":{},"אלומה":{},"אמונים":{},"אשדוד - א,ב,ד,ה":{},"אשדוד - איזור תעשייה צפוני":{},"אשדוד - ג,ו,ז":{},"אשדוד - ח,ט,י,יג,יד,טז":{},"אשדוד -יא,יב,טו,יז,מרינה,סיט":{},"באר טוביה":{},"ביצרון":{},"בית אלעזרי":{},"בית גמליאל":{},"בית חלקיה":{},"בית עזרא":{},"בן זכאי":{},"בני דרום":{},"בני עי''ש":{},"בני ראם":{},"בניה":{},"גבעת ברנר":{},"גבעת וושינגטון":{},"גבעתי":{},"גדרה":{},"גן הדרום":{},"גן יבנה":{},"גני טל":{},"גת":{},"ורדון":{},"זבדיאל":{},"זוהר":{},"זרחיה":{},"חפץ חיים":{},"חצב":{},"חצור":{},"יבנה":{},"יד בנימין":{},"יד נתן":{},"ינון":{},"כנות":{},"כפר אביב":{},"כפר אחים":{},"כפר הנגיד":{},"כפר הרי''ף וצומת ראם":{},"כפר ורבורג":{},"כפר מרדכי":{},"כרם ביבנה":{},"לכיש":{},"מישר":{},"מנוחה":{},"מעון צופיה":{},"מרכז שפירא":{},"משגב דב":{},"משואות יצחק":{},"מתחם בני דרום":{},"נגבה":{},"נהורה":{},"נוגה":{},"נווה מבטח":{},"נועם":{},"נחלה":{},"ניר בנים":{},"ניר גלים":{},"ניר ח''ן":{},"סגולה":{},"עוזה":{},"עוצם":{},"עזר":{},"עזריקם":{},"עין צורים":{},"ערוגות":{},"עשרת":{},"פארק תעשייה ראם":{},"פלמחים":{},"קבוצת יבנה":{},"קדמה":{},"קדרון":{},"קוממיות":{},"קריית גת, כרמי גת":{},"קריית מלאכי":{},"רבדים":{},"רווחה":{},"שדה דוד":{},"שדה יואב":{},"שדה משה":{},"שדה עוזיהו":{},"שדמה":{},"שחר":{},"שלווה":{},"שפיר":{},"שתולים":{},"תימורים":{},"תלמי יחיאל":{},"תלמים":{}},"שרון":{"אביחיל":{},"אבן יהודה":{},"אודים":{},"אורנית":{},"אזור תעשייה טירה":{},"אזור תעשייה עמק חפר":{},"אחיטוב":{},"אייל":{},"אליכין":{},"אלישיב":{},"אלישמע":{},"אלפי מנשה":{},"אלקנה":{},"אמץ":{},"ארסוף":{},"בארותיים":{},"בורגתה":{},"בחן":{},"בית ברל":{},"בית הלוי":{},"בית חזון":{},"בית חרות":{},"בית יהושע":{},"בית ינאי":{},"בית יצחק - שער חפר":{},"בית סוהר השרון":{},"ביתן אהרן":{},"בני דרור":{},"בני ציון":{},"בצרה":{},"בת חן":{},"בת חפר":{},"ג'לג'וליה":{},"גאולי תימן":{},"גאולים":{},"גבעת חיים איחוד":{},"גבעת חיים מאוחד":{},"גבעת חן":{},"גבעת שפירא":{},"גן חיים":{},"גן יאשיה":{},"גנות הדר":{},"גני עם":{},"געש":{},"הדר עם":{},"הוד השרון":{},"המעפיל":{},"המרכז האקדמי רופין":{},"העוגן":{},"זמר":{},"חבצלת השרון וצוקי ים":{},"חגור":{},"חגלה":{},"חופית":{},"חורשים":{},"חיבת ציון":{},"חניאל":{},"חרב לאת":{},"חרוצים":{},"חרות":{},"טייבה":{},"טירה":{},"יד חנה":{},"ינוב":{},"יעף":{},"יקום":{},"ירחיב":{},"ירקונה":{},"כוכב יאיר - צור יגאל":{},"כפר ברא":{},"כפר הס":{},"כפר הרא''ה":{},"כפר ויתקין":{},"כפר חיים":{},"כפר ידידיה":{},"כפר יונה":{},"כפר יעבץ":{},"כפר מונש":{},"כפר מל''ל":{},"כפר נטר":{},"כפר סבא":{},"כפר עבודה":{},"כפר קאסם":{},"מרכז אזורי דרום השרון":{},"מכון וינגייט":{},"מכמורת":{},"מעברות":{},"משמר השרון":{},"משמרת":{},"מתן":{},"נווה ימין":{},"נווה ירק":{},"נורדיה":{},"ניצני עוז":{},"ניר אליהו":{},"נירית":{},"נעורים":{},"נתניה - מזרח":{},"נתניה - מערב":{},"סלעית":{},"עדנים":{},"עולש":{},"עזריאל":{},"עין החורש":{},"עין ורד":{},"עין שריד":{},"עץ אפרים":{},"פורת":{},"פרדסיה":{},"צופים":{},"צופית":{},"צור יצחק":{},"צור משה":{},"צור נתן":{},"קדימה-צורן":{},"קלנסווה":{},"רמות השבים":{},"רמת הכובש":{},"רעננה":{},"רשפון":{},"שדה ורבורג":{},"שדי חמד":{},"שושנת העמקים":{},"שער אפרים":{},"שערי תקווה":{},"שפיים":{},"תחנת רכבת ראש העין":{},"תל יצחק":{},"תל מונד":{},"תנובות":{}},"ירושלים":{"אבן ספיר":{},"אורה":{},"בית זית":{},"גבעת זאב":{},"ירושלים - אזור תעשייה עטרות":{},"ירושלים - דרום":{},"ירושלים - כפר עקב":{},"ירושלים - מזרח":{},"ירושלים - מערב":{},"ירושלים - מרכז":{},"ירושלים - צפון":{},"מבשרת ציון":{},"מוצא עילית":{},"נבי סמואל":{},"עמינדב":{},"פנימיית עין כרם":{}},"דרום הגולן":{"אבני איתן":{},"אזור תעשייה בני יהודה":{},"אלוני הבשן":{},"אלי עד":{},"אלמגור":{},"אניעם":{},"אפיק":{},"אשדות יעקב איחוד":{},"אשדות יעקב מאוחד":{},"בני יהודה וגבעת יואב":{},"גשור":{},"האון":{},"חד נס":{},"חמת גדר":{},"חספין":{},"יונתן":{},"כנף":{},"כפר חרוב":{},"מבוא חמה":{},"מיצר":{},"מסדה":{},"מעגן":{},"מעלה גמלא":{},"נאות גולן":{},"נוב":{},"נטור":{},"עין גב":{},"קדמת צבי":{},"קצרין":{},"קצרין - אזור תעשייה":{},"קשת":{},"רמות":{},"רמת מגשימים":{},"שער הגולן":{},"תל קציר":{}},"שומרון":{"אבני חפץ":{},"אזור תעשייה בראון":{},"אזור תעשייה שער בנימין":{},"אחיה":{},"איתמר":{},"אלון מורה":{},"אריאל":{},"בית אל":{},"בית אריה":{},"בית חורון":{},"ברוכין":{},"ברקן":{},"גבע בנימין":{},"גבעת אסף":{},"גבעת הראל וגבעת הרואה":{},"דולב":{},"הר ברכה":{},"חוות גלעד":{},"חוות יאיר":{},"חיננית":{},"חלמיש":{},"חרמש":{},"חרשה":{},"טל מנשה":{},"טלמון":{},"יצהר":{},"יקיר":{},"כוכב השחר":{},"כוכב יעקב":{},"כפר תפוח":{},"מבוא דותן":{},"מגדלים":{},"מגרון":{},"מעלה לבונה":{},"מעלה מכמש":{},"מעלה שומרון":{},"נופי נחמיה":{},"נופים":{},"נחליאל":{},"ניל''י":{},"נעלה":{},"נריה":{},"עדי עד":{},"עופרים":{},"עטרת":{},"עלי":{},"עלי זהב":{},"עמיחי":{},"עמנואל":{},"ענב":{},"עפרה":{},"פדואל":{},"פסגות":{},"קדומים":{},"קידה":{},"קריית נטפים":{},"קרני שומרון":{},"רבבה":{},"רחלים":{},"ריחן":{},"רימונים":{},"שבות רחל":{},"שבי שומרון":{},"שילה":{},"שקד":{},"תל ציון":{}},"ים המלח":{"אבנת":{},"אלמוג":{},"בית הערבה":{},"בתי מלון ים המלח":{},"ורד יריחו":{},"מלונות ים המלח מרכז":{},"מצדה":{},"מצוקי דרגות":{},"מצפה שלם":{},"מרחצאות עין גדי":{},"מרכז אזורי מגילות":{},"נאות הכיכר":{},"נווה זוהר":{},"עין בוקק":{},"עין גדי":{},"עין תמר":{},"קליה":{}},"עוטף עזה":{"אבשלום":{},"אור הנר":{},"ארז":{},"בארי":{},"בני נצרים":{},"גבים, מכללת ספיר":{},"גברעם":{},"דקל":{},"זיקים":{},"זמרת, שובה":{},"חולית":{},"יבול":{},"יד מרדכי":{},"יכיני":{},"יתד":{},"כיסופים":{},"כפר מימון ותושיה":{},"כפר עזה":{},"כרם שלום":{},"כרמיה":{},"מבטחים, עמיעוז, ישע":{},"מגן":{},"מטווח ניר עם":{},"מפלסים":{},"נווה":{},"נחל עוז":{},"ניר יצחק":{},"ניר עוז":{},"נירים":{},"נתיב העשרה":{},"סופה":{},"סעד":{},"עין הבשור":{},"עין השלושה":{},"עלומים":{},"פרי גן":{},"צוחר, אוהד":{},"רעים":{},"שדה אברהם":{},"שדה ניצן":{},"שדרות, איבים, ניר עם":{},"שוקדה":{},"שלומית":{},"תלמי אליהו":{},"תלמי יוסף":{},"תקומה":{},"תקומה וחוות יזרעם":{}},"יהודה":{"אדורה":{},"אדוריים":{},"אזור תעשייה מישור אדומים":{},"אזור תעשייה מיתרים":{},"אלון":{},"אלון שבות":{},"אליאב":{},"אלעזר":{},"אמציה":{},"אפרת":{},"בית חגי":{},"בית יתיר":{},"ביתר עילית":{},"בני דקלים":{},"בת עין":{},"גבעות":{},"הר גילה":{},"הר עמשא":{},"חברון":{},"חוות שדה בר":{},"טנא עומרים":{},"כפר אדומים":{},"כפר אלדד":{},"כפר עציון":{},"כרמי צור":{},"כרמי קטיף":{},"כרמל":{},"מגדל עוז":{},"מיצד":{},"מעון":{},"מעלה אדומים":{},"מעלה חבר":{},"מעלה עמוס":{},"מעלה רחבעם":{},"מצפה יריחו":{},"נגוהות":{},"נווה דניאל":{},"נופי פרת":{},"נוקדים":{},"נטע":{},"סוסיא":{},"עלמון":{},"עשאהל":{},"עתניאל":{},"פני קדם":{},"קדר":{},"קרית ארבע":{},"ראש צורים":{},"שומריה":{},"שמעה":{},"שני ליבנה":{},"שקף":{},"תלם":{},"תקוע":{}},"צפון הגולן":{"אודם":{},"אורטל":{},"אל רום":{},"בוקעתא":{},"מג'דל שמס":{},"מסעדה":{},"מרום גולן":{},"נווה אטי''ב":{},"נמרוד":{},"עין זיוון":{},"עין קנייא":{},"קלע":{},"שעל":{}},"גליל תחתון":{"בית ירח":{},"אזור תעשייה צמח":{},"אזור תעשייה קדמת גליל":{},"אלומות":{},"אפיקים":{},"ארבל":{},"אתר ההנצחה גולני":{},"בית זרע":{},"גבעת אבני":{},"גינוסר":{},"דגניה א":{},"דגניה ב":{},"הודיות":{},"הזורעים":{},"המכללה האקדמית כנרת":{},"ואדי אל חמאם":{},"חוקוק":{},"טבריה":{},"יבנאל":{},"כינרת מושבה":{},"כינרת קבוצה":{},"כפר זיתים":{},"כפר חיטים":{},"כפר כמא":{},"כפר נהר הירדן":{},"לביא":{},"לבנים":{},"מגדל":{},"מצפה":{},"פוריה כפר עבודה":{},"פוריה נווה עובד":{},"פוריה עילית":{},"רביד":{},"שדה אילן":{},"שרונה":{}},"ואדי ערה":{"אום אל פחם":{},"אום אל קוטוף":{},"אזור תעשייה יקנעם עילית":{},"אזור תעשייה מבוא כרמל":{},"אל עריאן":{},"אליקים":{},"באקה אל גרבייה":{},"בית סוהר מגידו":{},"ברטעה":{},"ג'ת":{},"גבעת ניל''י":{},"גבעת עוז":{},"גלעד":{},"דליה":{},"חריש":{},"יקנעם המושבה והזורע":{},"יקנעם עילית":{},"כפר קרע":{},"קיבוץ מגידו":{},"מגל":{},"מדרך עוז":{},"מועאוויה":{},"מי עמי":{},"מייסר":{},"מעלה עירון":{},"מצפה אילן":{},"מצר":{},"משמר העמק":{},"עין אל-סהלה":{},"עין העמק":{},"עין השופט":{},"ערערה":{},"קציר":{},"רגבים":{},"רמות מנשה":{},"רמת השופט":{}},"העמקים":{"אום אל-גנם":{},"אורנים":{},"אזור תעשייה אלון התבור":{},"אזור תעשייה מבואות הגלבוע":{},"אזור תעשייה ציפורית":{},"אחוזת ברק":{},"אילניה":{},"אכסאל":{},"אל-ח'וואלד מערב":{},"אלון הגליל":{},"אלוני אבא":{},"אלונים":{},"בית לחם הגלילית":{},"בית סוהר שיטה וגלבוע":{},"בית קשת":{},"בית שערים":{},"בלפוריה":{},"בסמת טבעון":{},"קבוצת גבע":{},"גבעת אלה":{},"גבת":{},"גדעונה":{},"גזית":{},"גן נר":{},"גניגר":{},"דבוריה":{},"דברת":{},"דחי":{},"הושעיה":{},"היוגב":{},"הסוללים":{},"הרדוף":{},"זרזיר":{},"ח'וואלד":{},"חג'אג'רה":{},"טמרה בגלבוע":{},"יזרעאל":{},"יפיע":{},"יפעת":{},"ישובי אומן":{},"מרכז חבר":{},"ישובי יעל":{},"כדורי":{},"כעביה":{},"כעביה טבאש":{},"כפר ברוך":{},"כפר גדעון":{},"כפר החורש":{},"כפר טבאש":{},"כפר יהושע":{},"כפר יחזקאל":{},"כפר כנא":{},"כפר מצר":{},"כפר קיש":{},"כפר תבור":{},"כפר תקווה":{},"מגדל העמק":{},"מגן שאול":{},"מוקיבלה":{},"מזרע":{},"מנשית זבדה":{},"מרחביה מושב":{},"מרחביה קיבוץ":{},"משהד":{},"נעורה":{},"נהלל":{},"נופית":{},"נורית":{},"נין":{},"נצרת":{},"נוף הגליל":{},"סואעד חמירה":{},"סולם":{},"סנדלה":{},"עדי":{},"עילוט":{},"עין דור":{},"עין חרוד":{},"עין מאהל":{},"עפולה":{},"ציפורי":{},"קריית טבעון-בית זייד":{},"ראס עלי":{},"ריינה":{},"רם און":{},"רמת דוד":{},"רמת ישי":{},"רמת צבי":{},"שבלי":{},"שדה יעקב":{},"שדמות דבורה":{},"שמשית":{},"שער העמקים":{},"שריד":{},"תחנת רכבת כפר יהושוע":{},"תל יוסף":{},"תל עדשים":{},"תמרת":{}},"מרכז הנגב":{"אום בטין":{},"אזור תעשייה עידן הנגב":{},"אל סייד":{},"אשכולות":{},"אתר דודאים":{},"באר שבע - דרום":{},"באר שבע - מזרח":{},"באר שבע - מערב":{},"באר שבע - צפון":{},"בית קמה":{},"גבעות בר":{},"גבעות גורל":{},"דביר":{},"חורה":{},"חצרים":{},"כרמים":{},"כרמית":{},"להב":{},"להבים":{},"לקיה":{},"מיתר":{},"משמר הנגב":{},"מתחם צומת שוקת":{},"נבטים":{},"סנסנה":{},"עומר":{},"רהט":{},"שגב שלום":{},"שובל":{},"תל שבע":{},"תארבין":{}},"מערב הנגב":{"אופקים":{},"אורים":{},"אזור תעשייה נ.ע.מ":{},"אשבול":{},"אשל הנשיא":{},"בטחה":{},"בית הגדי":{},"ברור חיל":{},"ברוש":{},"גבולות":{},"גילת":{},"דורות":{},"דניאל":{},"זרועה":{},"חוות שיקמים":{},"יושיביה":{},"מבועים":{},"מסלול":{},"מעגלים, גבעולים, מלילות":{},"ניר משה":{},"ניר עקיבא":{},"נתיבות":{},"פדויים":{},"פטיש":{},"פעמי תש''ז":{},"צאלים":{},"קלחים":{},"קריית חינוך מרחבים":{},"רוחמה":{},"רנן":{},"שבי דרום":{},"שדה צבי":{},"שיבולים":{},"שרשרת":{},"תאשור":{},"תדהר":{},"תלמי ביל''ו":{},"תפרח":{}},"גוש דן":{"אור יהודה":{},"אזור":{},"בני ברק":{},"בת-ים":{},"גבעת השלושה":{},"גבעת שמואל":{},"גבעתיים":{},"גני תקווה":{},"גת רימון":{},"הרצליה - מערב":{},"הרצליה - מרכז וגליל ים":{},"חולון":{},"יהוד-מונוסון":{},"כפר סירקין":{},"כפר שמריהו":{},"מגשימים":{},"מעש":{},"מקווה ישראל":{},"מתחם פי גלילות":{},"סביון":{},"סינמה סיטי גלילות":{},"פתח תקווה":{},"קריית אונו":{},"רמת גן - מזרח":{},"רמת גן - מערב":{},"רמת השרון":{},"תל אביב - דרום העיר ויפו":{},"תל אביב - מזרח":{},"תל אביב - מרכז העיר":{},"תל אביב - עבר הירקון":{}},"המפרץ":{"אושה":{},"איבטין":{},"בית עלמין תל רגב":{},"החותרים":{},"חיפה - כרמל ועיר תחתית":{},"חיפה - מערב":{},"חיפה - נווה שאנן ורמות כרמל":{},"חיפה - קריית חיים ושמואל":{},"חיפה-מפרץ":{},"טירת כרמל":{},"יגור":{},"כפר ביאליק":{},"כפר גלים":{},"כפר המכבי":{},"כפר חסידים":{},"נשר":{},"קריית ביאליק":{},"קריית ים":{},"קריית מוצקין":{},"קריית אתא":{},"רכסים":{},"רמת יוחנן":{}},"ירקון":{"אזור תעשייה אפק ולב הארץ":{},"אזור תעשייה חבל מודיעין":{},"אלעד":{},"בארות יצחק":{},"בית נחמיה":{},"בית עריף":{},"בני עטרות":{},"ברקת":{},"גבעת כ''ח":{},"גמזו":{},"חדיד":{},"חשמונאים":{},"טירת יהודה":{},"כפר דניאל":{},"כפר האורנים":{},"כפר טרומן":{},"כפר רות":{},"לפיד":{},"מבוא חורון":{},"מבוא מודיעים":{},"מודיעין":{},"מודיעין - ישפרו סנטר":{},"מודיעין - ליגד סנטר":{},"מודיעין עילית":{},"מזור":{},"מתתיהו":{},"נוף איילון":{},"נופך":{},"נחלים":{},"נחשונים":{},"עינת":{},"ראש העין":{},"רינתיה":{},"שהם":{},"שילת":{},"שעלבים":{},"תעשיון חצב":{}},"מערב לכיש":{"אזור תעשייה הדרומי אשקלון":{},"אזור תעשייה צפוני אשקלון":{},"אשקלון - דרום":{},"אשקלון - צפון":{},"באר גנים":{},"בית שקמה":{},"ברכיה":{},"בת הדר":{},"גיאה":{},"הודיה":{},"חלץ":{},"כוכב מיכאל":{},"כפר סילבר":{},"מבקיעים":{},"משען":{},"ניצן":{},"ניצנים":{},"ניר ישראל":{},"תלמי יפה":{}},"הכרמל":{"אזור תעשייה ניר עציון":{},"בית אורן":{},"בית סוהר קישון":{},"בית צבי":{},"בת שלמה":{},"גבע כרמל":{},"גבעת וולפסון":{},"דור":{},"דלית אל כרמל":{},"הבונים":{},"יערות הכרמל":{},"כלא דמון":{},"כפר הנוער ימין אורד":{},"כרם מהר''ל":{},"מאיר שפיה":{},"מגדים":{},"מרכז מיר''ב":{},"נווה ים":{},"נחשולים":{},"ניר עציון":{},"עופר":{},"עין איילה":{},"עין הוד":{},"עין חוד":{},"עין כרמל":{},"עספיא":{},"עתלית":{},"פוריידיס":{},"צרופה":{}},"השפלה":{"אזור תעשייה נשר - רמלה":{},"אחיסמך":{},"אחיעזר":{},"אירוס":{},"באר יעקב":{},"בית דגן":{},"בית חנן":{},"בית חשמונאי":{},"בית עובד":{},"בית עוזיאל":{},"בן שמן":{},"גאליה":{},"גזר":{},"גיבתון":{},"גינתון":{},"גן שורק":{},"גן שלמה":{},"גנות":{},"גני הדר":{},"גני יוחנן":{},"זיתן":{},"חולדה":{},"חמד":{},"יגל":{},"יד רמב''ם":{},"יסודות":{},"יציץ":{},"ישרש":{},"כפר ביל''ו":{},"כפר בן נון":{},"כפר חב''ד":{},"כפר נוער בן שמן":{},"כפר שמואל":{},"כרמי יוסף":{},"לוד":{},"מזכרת בתיה":{},"מצליח":{},"משמר איילון":{},"משמר דוד":{},"משמר השבעה":{},"נטעים":{},"ניר צבי":{},"נס ציונה":{},"נען":{},"נצר חזני":{},"נצר סרני":{},"סתריה":{},"עזריה":{},"עיינות":{},"פארק תעשיות פלמחים":{},"פדיה":{},"פתחיה":{},"צפריה":{},"קריית עקרון":{},"ראשון לציון - מזרח":{},"ראשון לציון - מערב":{},"רחובות":{},"רמות מאיר":{},"רמלה":{},"תעשיון צריפין":{}},"בקעת בית שאן":{"אזור תעשייה צבאים":{},"בית אלפא וחפציבה":{},"בית השיטה":{},"בית יוסף":{},"בית שאן":{},"גשר":{},"חוות עדן":{},"חמדיה":{},"טייבה בגלבוע":{},"טירת צבי":{},"ירדנה":{},"כפר גמילה מלכישוע":{},"כפר רופין":{},"מולדת":{},"מירב":{},"מנחמיה":{},"מסילות":{},"מעוז חיים":{},"מעלה גלבוע":{},"נווה אור":{},"נוה איתן":{},"ניר דוד":{},"עין הנצי''ב":{},"רוויה":{},"רחוב":{},"רשפים":{},"שדה אליהו":{},"שדה נחום":{},"שדי תרומות":{},"שלוחות":{},"שלפים":{},"תל תאומים":{}},"אילת":{"אזור תעשייה שחורת":{},"אילות":{},"אילת":{}},"ערבה":{"אל עמארני, אל מסק":{},"אליפז ומכרות תמנע":{},"באר אורה":{},"גרופית":{},"חוות ערנדל":{},"חי-בר יטבתה":{},"חצבה":{},"יהל":{},"יטבתה":{},"כושי רמון":{},"לוטן":{},"נאות סמדר":{},"נווה חריף":{},"סמר":{},"ספיר":{},"עידן":{},"עין חצבה":{},"עין יהב":{},"עיר אובות":{},"פארן":{},"צופר":{},"צוקים":{},"קטורה":{},"שחרות":{},"שיטים":{}},"בקעה":{"ארגמן":{},"בקעות":{},"גיתית":{},"גלגל":{},"חמדת":{},"חמרה":{},"ייט''ב":{},"יפית":{},"מבואות יריחו":{},"מחולה":{},"מכורה":{},"מעלה אפרים":{},"משואה":{},"משכיות":{},"נעמה":{},"נערן":{},"נתיב הגדוד":{},"פצאל":{},"רועי":{},"רותם":{},"שדמות מחולה":{},"תומר":{}}}}
icons_and_emojis = {0: ("mdi:alert", "❗"), 1: ("mdi:rocket-launch", "🚀"),2: ("mdi:home-alert", "⚠️"),3: ("mdi:earth-box", "🌍"), 4: ("mdi:chemical-weapon", "☢️"),5: ("mdi:waves", "🌊"),6: ("mdi:airplane", "🛩️"), 7: ("mdi:skull", "💀"),8: ("mdi:alert", "❗"),9: ("mdi:alert", "❗"),10: ("mdi:alert", "❗"),11: ("mdi:alert", "❗"),12: ("mdi:alert", "❗"), 13: ("mdi:run-fast", "👹"),}
def_attributes = {"id": 0,"cat": 0,"title": "אין התרעות","desc": "", "data": "", "areas": "", "data_count": 0,"duration": 0,"icon": "mdi:alert", "emoji": "⚠️"}
day_names = {'Sunday': 'יום ראשון', 'Monday': 'יום שני', 'Tuesday': 'יום שלישי', 'Wednesday': 'יום רביעי', 'Thursday': 'יום חמישי', 'Friday': 'יום שישי', 'Saturday': 'יום שבת' }
false_data_json = {"id": 0, "cat": "1", "title": "ירי רקטות וטילים", "data": ["עזה"], "time": f"{datetime.now().isoformat()}"}        

class Red_Alerts_Israel(Hass):
    def initialize(self):
        self.data_import()
        self.run_every(self.poll_alerts, datetime.now(), self.interval, timeout=30)

    def data_import(self):
        self.lamas = lamas_data
        # Convert Lamas json data to python set
        for area, cities in self.lamas['areas'].items():
            standardized_cities = [re.sub(r'[\-\,\(\)\s\'\’\"]+', '', city).strip() for city in cities]
            self.lamas['areas'][area] = set(standardized_cities)
        
        # Getting args from apps.yaml
        self.pkr_def_city = self.args.get("city_names", "תל אביב - מרכז העיר")
        if isinstance(self.pkr_def_city, str):
            self.pkr_def_city = self.pkr_def_city.split(', ')
        self.city_names_self = set([re.sub(r'[\-\,\(\)\s\'\’\"]+', '', name).strip() for name in self.pkr_def_city])
        self.main_sensor_arg = self.args.get("sensor_name", "red_alert")
        self.interval = self.args.get("interval", 2)
        self.save_2_file = self.args.get("save_2_file", True)
        self.timer = self.args.get("timer", 120)
        self.on_time1 = self.on_time2 = time.time() + self.timer

        # Creating Home Assistant sensorns if they are not exist
        self.main_sensor = f"binary_sensor.{self.main_sensor_arg}"
        self.city_sensor = f"binary_sensor.{self.main_sensor_arg}_city"
        self.main_text = f"input_text.{self.main_sensor_arg}"
        self.activate_alert = f"input_boolean.{self.main_sensor_arg}_test"
        self.history_file = f"/homeassistant/www/{self.main_sensor_arg}_history.txt"
        self.history_file_csv = f"/homeassistant/www/{self.main_sensor_arg}_history.csv"
        self.history_file_json_error = f"/homeassistant/www/{self.main_sensor_arg}_errors.txt"
        self.ERROR_NAME = False
        for city in self.city_names_self:
            # Find the original name corresponding to the standardized city
            original_name = [n for n in self.pkr_def_city if re.sub(r'[\-\,\(\)\s\'\’\"]+', '', n).strip() == city][0]
            if not any(city in cities for cities in self.lamas['areas'].values()):
                print(f"-------\nATTENTION! '{original_name}' is invalid name.\nThe secondary binary sensor is unable to operate because “{original_name}” is not recognized in any region.\nTo resolve this issue, please correct the “city_names” entry in the apps.yaml file.\nCity names can be found here: https://github.com/idodov/RedAlert/blob/main/cities_name.md")
                with open(self.history_file_json_error, 'a', encoding='utf-8-sig') as f6:
                    print(f"-------\n{datetime.now().isoformat()} - - ATTENTION! '{original_name}' is invalid name.\nThe secondary binary sensor is unable to operate because “{original_name}” is not recognized in any region.\nTo resolve this issue, please correct the “city_names” entry in the apps.yaml file.\nCity names can be found here: https://github.com/idodov/RedAlert/blob/main/cities_name.md\n-------\n", file=f6)
                self.ERROR_NAME = original_name

        first_alert_data = self.get_first_alert_data()
        if first_alert_data:
            last_data = self.check_backup_data(first_alert_data)
        else:
            print("Failed to retrieve data.")
            last_data = self.check_backup_data(false_data_json)
        
        if not self.entity_exists(self.main_sensor):
            self.set_state(self.main_sensor, state="off", attributes=last_data)
        
        self.set_state(self.main_sensor, state="off")
        self.c_value = 1
        try:
            self.c_value = self.get_state(self.main_sensor, attribute="count")
        except Exception as e:
            self.c_value = 1

        if not self.entity_exists(self.city_sensor):
            self.set_state(self.city_sensor, state="off", attributes={"id":0, "cat": 0, "title": "", "desc": "", "data": "", "areas": "", "data_count": 0, "duration": 0, "last_changed": "", "emoji":  "🚨", "icon_alert": "mdi:alert",  "prev_last_changed": datetime.now().isoformat(), "prev_cat": 0,  "prev_title": "אין התרעות", "prev_desc": "מצב רגיל", "prev_data" :"", "prev_data_count": 0,"prev_duration": 0, "prev_areas": "", "prev_last_changed": datetime.now().isoformat(), "friendly_name": "City Red Alerts"})
        self.set_state(self.city_sensor, state="off")
        
        if self.ERROR_NAME:
            self.set_state(self.city_sensor, state="off", attributes={"friendly_name": f"ERROR: {self.ERROR_NAME}"})
        else:
            self.set_state(self.city_sensor, state="off", attributes={"friendly_name": "City Red Alerts"})

        if not self.entity_exists(self.main_text):
            self.set_state(self.main_text, state="אין התרעות", attributes={"min": 0, "max": 255, "mode": "text", "friendly_name": "Last Red Alert in Israel"})

        try:
            self.test_alert_now = self.get_state(self.activate_alert)
            self.set_state(self.activate_alert, state="off", attributes={"friendly_name": "Test Red Alert"})
        
        except Exception as e:
            self.log(f"Error getting state for {self.activate_alert}: {e}. Please create it in HA configuration.yaml or as a TOGGLE Helper")
            self.set_state(self.activate_alert, state="off", attributes={"friendly_name": "Test Red Alert"})
        
        self.alert_id = 12345
        self.t_value = 0
        self.test_time = time.time()
        self.my_list = [f"{city}" if "'" in city else f"{city}" for city in self.pkr_def_city]

        if not os.path.exists(self.history_file_csv):
            no_json = True
        else:
            no_json = False

        if self.save_2_file:
            with open(self.history_file_csv, 'a', encoding='utf-8-sig') as f3:
                if no_json:
                    print("ID, DAY, DATE, TIME, TITLE, COUNT, AREAS, CITIES, DESC", file=f3)
        return

    def get_first_alert_data(self):
        history_url = "https://www.oref.org.il/warningMessages/alert/History/AlertsHistory.json"
        try:
            response = requests.get(history_url)
            if response.status_code == 200:
                data = response.json()
                if data and isinstance(data, list):
                    first_alert = data[0]
                    return first_alert
                else:
                    return false_data_json
            else:
                return false_data_json
        except Exception as e:
            print(f"Error fetching data: {e}")
            return false_data_json

    def poll_alerts(self, kwargs):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                response_data = codecs.decode(response.content, 'utf-8-sig')

                # Test Red Alert
                self.test_alert_now = self.get_state(self.activate_alert)
                if self.test_alert_now == "on":
                    self.t_value += 1
                    
                    if self.t_value == 1:
                        self.test_time = time.time()
                        data = {'id': random.randint(123450000000000000, 123456789123456789), 'cat': '1', 'title': 'ירי רקטות וטילים (התרעה לצורך בדיקה)', 'data': self.my_list, 'desc': 'היכנסו למרחב המוגן ושהו בו 10 דקות'}
                        self.check_data(data)
                        self.set_state(self.activate_alert, state="off", attributes=def_attributes)
                    
                    if time.time() - self.test_time >= self.timer:
                        self.t_value = 0

                elif response_data.strip():  
                    try:
                        data = json.loads(response_data)
                        if data.get('data'):
                            self.check_data(data)

                    except (json.JSONDecodeError, TypeError):
                        self.log("Error: Invalid JSON format in the response.")

                else:
                    if time.time() - self.on_time1 >= self.timer:
                        self.set_state(self.main_sensor, state="off", attributes=def_attributes)
                    
                    if time.time() - self.on_time2 >= self.timer:
                        self.set_state(self.city_sensor, state="off", attributes=def_attributes)
                
                # Update the monitor counter attribue (to know if the script is running)
                self.c_value += 1
                self.set_state(self.main_sensor, attributes={"count": self.c_value})

            else:
                self.log(f"Failed to retrieve data. Status code: {response.status_code}")
                
        except requests.exceptions.Timeout:
            self.log("The request from https://www.oref.org.il is timed out.")
            return

        except Exception as e:
            self.log(f"Error: {e}\n{traceback.format_exc()}")
        return

    def check_backup_data(self, data):
        # Get all the data from the json value
        areas, full_message, full_message_wa, full_message_tg = [], [], [], []
        category = int(data.get('cat', 0))
        alert_title = data.get('title', 'לא היו התרעות ביממה האחרונה')
        city_names = data.get('data', [])
        last_time = data.get('alertDate')
        areas_c = 1 if city_names else 0
        icon_alert, icon_emoji = icons_and_emojis[category]

        if last_time:
            parsed_time = datetime.strptime(last_time, "%Y-%m-%d %H:%M:%S")
            last_time = parsed_time.strftime("%Y-%m-%dT%H:%M:%S.%f")
        else:
            last_time =datetime.now().isoformat()
        
        # Update sensor attribues
        sensor_attributes={
            "count":0,
            "id": 0,
            "cat": 0,
            "title": "אין התרעות",
            "desc": "שגרה",
            "areas": "",
            "data": "",
            "alert": "",
            "alert_alt": "",
            "alert_txt": "",
            "alert_wa": "",
            "alert_tg": "",
            "data_count": 0,
            "duration": 0,
            "icon": "mdi:alert",
            "emoji":  "⚠️",
            "last_changed": datetime.now().isoformat(),
            "prev_cat": category,
            "prev_title": alert_title,
            "prev_desc": "היכנסו למרחב המוגן",
            "prev_areas": "ישראל",
            "prev_data": city_names,
            "prev_data_count": areas_c,
            "prev_duration": 0,
            "prev_last_changed": last_time,}
        return sensor_attributes

    def check_data(self, data):
        # Get all the data from the json value
        areas, full_message, full_message_wa, full_message_tg = [], [], [], []
        category = int(data.get('cat', 1))
        alert_c_id = int(data.get('id', 0))
        descr = data.get('desc', '')
        alert_title = data.get('title', '')
        city_names = data.get('data', [])
        icon_alert, icon_emoji = icons_and_emojis[category]
        alerts_data = ', '.join(sorted(city_names))
        original_names = set(city_names)
        standardized_names = set([re.sub(r'[\-\,\(\)\s\'\’\"]+', '', name).strip() for name in city_names])
        
        # Generating attribues for the text messages
        data_count = len(standardized_names) if standardized_names else 0
        duration = int(re.findall(r'\d+', descr)[0]) * 60 if re.findall(r'\d+', descr) else 0
        for area, cities in self.lamas['areas'].items():
            intersecting_cities = cities.intersection(standardized_names)
            if intersecting_cities:
                areas.append(area)
                original_cities = [name for name in original_names if re.sub(r'[\-\,\(\)\s\'\’\"]+', '', name).strip() in intersecting_cities]
                original_cities_str = ', '.join(sorted(original_cities))
                full_message.append(f"{area}: {original_cities_str}")
                full_message_wa.append(f"> {area}\n{original_cities_str}\n")
                full_message_tg.append(f"**__{area}__** — {original_cities_str}\n")
        if len(areas) > 1:
            areas.sort()
            all_but_last = ", ".join(areas[:-1])
            areas_alert = f"{all_but_last} ו{areas[-1]}"
        else:
            areas_alert = ", ".join(areas)

        ### Generating messages ###
        full_message_txt = ' * '.join(full_message)
        full_message_str = alert_title + '\n * ' + '\n * '.join(full_message)
        text_wa = icon_emoji + " *"+alert_title + '*\n' + '\n'.join(full_message_wa) + '\n_' + descr + '_'
        text_tg = icon_emoji + " **"+alert_title + '**\n' + '\n'.join(full_message_tg) + '\n__' + descr + '__'
        text_status = f"{alert_title} - {areas_alert}: {alerts_data}"

        # Update sensor attribues
        sensor_attributes={
            "id": alert_c_id,
            "cat": category,
            "alert": text_status,
            "alert_alt": full_message_str,
            "alert_txt": full_message_txt,
            "alert_wa": text_wa,
            "alert_tg": text_tg,
            "title": alert_title,
            "desc": descr,
            "areas": areas_alert,
            "data": alerts_data,
            "data_count": data_count,
            "duration": duration,
            "icon": icon_alert,
            "emoji":  icon_emoji,
            "last_changed": datetime.now().isoformat(),
            "prev_cat": category,
            "prev_title": alert_title,
            "prev_desc": descr,
            "prev_areas": areas_alert,
            "prev_data": alerts_data,
            "prev_data_count": data_count,
            "prev_duration": duration,
            "prev_last_changed": datetime.now().isoformat(),}

        # Making sure that the input_text state won't be > 255 chars
        while len(text_status) > 255:
            if alert_title in text_status:
                text_status = f"{areas_alert} - {alerts_data}"
            elif areas_alert in text_status:
                text_status = f"{alerts_data}"
            else:
                text_status = f"{text_status[:252]}..."

        # Update the sensors if there are Alarms
        if alert_c_id != self.alert_id:
            self.alert_id = alert_c_id
            self.on_time1 = time.time()
            self.set_state(self.main_sensor, state="on", attributes=sensor_attributes)
            self.set_state(self.main_text, state=f"{text_status}", attributes={"icon": f"{icon_alert}"},)

            if self.save_2_file:
                now = datetime.now()
                day_name_hebrew = day_names[now.strftime('%A')]
                date_time_str = f"\nהתרעה נשלחה ב{day_name_hebrew} ה-{now.strftime('%d/%m/%Y')} בשעה {now.strftime('%H:%M')}"
                csv_cities = alerts_data
                csv_areas = ", ".join(areas)
                if "," in csv_areas:
                    csv_areas = f'"{csv_areas}"'
                if "," in csv_cities:
                    csv_cities = f'"{csv_cities}"'
                if "," in descr:
                    descr = f'"{descr}"'

                csv = f"{int(alert_c_id /10000000)},{day_name_hebrew},{now.strftime('%d/%m/%Y')},{now.strftime('%H:%M:%S')},{alert_title},{data_count},{csv_areas},{csv_cities},{descr}"
                with open(self.history_file, 'a', encoding='utf-8-sig') as f:
                    print(date_time_str, file=f)
                    print(full_message_str, file=f)

                with open(self.history_file_csv, 'a', encoding='utf-8-sig') as f3:
                    print(csv, file=f3)

            if standardized_names.intersection(self.city_names_self):
                self.on_time2 = time.time()
                self.set_state(self.city_sensor, state="on", attributes=sensor_attributes)
        return
