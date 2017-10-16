from flask import (Flask, render_template, abort, send_from_directory,
                   url_for, g, request, jsonify, redirect, make_response)

import requests
import re
import datetime
from icalendar import Calendar, Event, vText
import qrcode
import qrcode.image.svg
from io import BytesIO

app = Flask(__name__)
app.config["APPLICATION_ROOT"] = "/ttics/"
app.config['SERVER_NAME'] = 'math-info.hse.ru'
app.debug=True

class MyError(Exception):
    pass

@app.route('/', methods=['GET', 'POST'])
def hello_world():
    if request.method == 'GET':
        return render_template("form.html",
                               rootdir=app.config["APPLICATION_ROOT"])
    page_url = request.form.get('url')
    try:
        idxes = page_to_idxes(page_url)
    except MyError as err:
        return render_template("form.html", url=page_url,
                               error=str(err))

    url = url_for("ics", idx="_".join(idxes), _external=True)
    return render_template("form.html", url=page_url,
                           dest=url,
                           qr=qr(url))

@app.route('/<string:idxes>/cal.ics')
def ics(idxes):
    tts = get_current_timetable(idxes)
    cal = tt_to_ical(tts)
    response = make_response(cal.to_ical().decode('utf-8'))
    response.headers["Content-Disposition"] = ("attachment; "
                                               "filename=calendar.ics")
    response.headers["Content-Type"] = "text/calendar; charset=utf-8"

    return response

def page_to_idxes(url):
    m = re.match(
        r"http(s?)://(www\.)?hse.ru/(org/persons/\d+|staff/\w+)",
        url)
    if not m:
        raise MyError(
            "{url} doesn't look like HSE professor personal page".format(
                url=url
            ))

    url_tt = m.group(0) + "/timetable"
    page = requests.get(url_tt)
    out = [m.group(1)
            for m in re.finditer(r"idx.push\('(\d+)'\);", page.text)]
    if not out:
        raise MyError("idx not found on page {url_tt}".format(
            url_tt=url_tt
        ))
    return out

def qr(data):
    factory = qrcode.image.svg.SvgImage
    img = qrcode.make(data, image_factory=factory)
    io = BytesIO()
    img.save(io)
    return io.getvalue().decode("utf-8")


def get_timetable(idxes, fromdate, todate):
    entrypoint = "https://www.hse.ru/api/timetable/lessons"
    out = []
    for idx in idxes.split("_"):
        out.append(requests.get(entrypoint, params=dict(fromdate=fromdate,
                                               todate=todate,
                                               lectureroid=idx,
                                               receiverType='1')).json())
    return out

def dt_to_Ymd(dt):
    return dt.strftime("%Y.%m.%d")

def get_current_timetable(idxes, weeks=10):
    now = datetime.datetime.now()
    delta = datetime.timedelta(weeks=weeks)
    fromdate = dt_to_Ymd(now - delta)
    todate = dt_to_Ymd(now + delta)
    return get_timetable(idxes, fromdate, todate)

def lesson_to_event(lesson):
    ev = Event()
    date = lesson['date']
    begin = lesson['beginLesson']
    end = lesson['endLesson']
    fmt = "%Y.%m.%d %H:%M"
    begin_dt = datetime.datetime.strptime(date + " " + begin, fmt)
    end_dt = datetime.datetime.strptime(date + " " + end, fmt)
    ev.add("dtstart", begin_dt)
    ev.add("dtend", end_dt)
    ev.add("summary", lesson['discipline'])
    ev.add("location", vText(", ".join([lesson['building'],
                             lesson.get('auditorium', '')])))
    return ev

def tt_to_ical(tts):
    cal = Calendar()
    for tt in tts:
        for lesson in tt['Lessons']:
            cal.add_component(lesson_to_event(lesson))
    return cal

if __name__ == '__main__':
    app.run()
