"""
Campus events, import side: time zones, the iCalendar parser, the public W&M feed list, a hardened fetch and the
import that replaces one calendar's rows. Ported from AndEVENTS (github.com/alexbespik/AndEVENTS) by the same author.

Feed text is untrusted data: it is parsed with fixed caps (bytes, lines, events), titles and descriptions are reduced
to plain text, links must be https, and nothing here ever hands feed text to a model. campus_events.py holds the
tables, the queries and the routes; classify() lives there and is looked up lazily (it imports this module).
"""
import functools
import html
import json
import re
import threading
import time
from datetime import date, datetime, time as dtime, timedelta, timezone as dt_timezone, tzinfo
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

CAMPUS_TZ_NAME = "America/New_York"
ALLOWED_HOSTS = frozenset({"events.wm.edu", "tribelink.wm.edu"})
USER_AGENT = "andedu-campus-events/1.0"
MAX_FEED_BYTES = 5 * 1024 * 1024
MAX_ICAL_LINES = 100_000
MAX_EVENTS_PER_FEED = 5000      # after recurring events are expanded
MAX_EVENTS_TOTAL = 20000        # rows in campus_events
FETCH_TIMEOUT_S = 8.0
SYNC_DEADLINE_S = 60.0
WINDOW_PAST_DAYS, WINDOW_AHEAD_DAYS = 2, 45   # recurring events are expanded over this window around "now"
MAX_YEAR, MIN_YEAR = 2100, 1970

# (slug, name, url): public calendars only, one per feed
FEEDS: Tuple[Tuple[str, str, str], ...] = (
    ("tribelink", "TribeLink Campus Events", "https://tribelink.wm.edu/events.ics"),
    ("wm-main", "William & Mary Master Calendar", "https://events.wm.edu/calendar/upcoming_ical/wm"),
    ("studentengagement", "Student Engagement & Activities", "https://events.wm.edu/calendar/upcoming_ical/studentengagement"),
    ("libraries", "Swem Library Events & Workshops", "https://events.wm.edu/calendar/upcoming_ical/libraries"),
    ("swem", "Swem Library", "https://events.wm.edu/calendar/upcoming_ical/swem"),
    ("athletics", "W&M Tribe Athletics", "https://events.wm.edu/calendar/upcoming_ical/athletics"),
    ("recsports", "Campus Recreation & Fitness", "https://events.wm.edu/calendar/upcoming_ical/recsports"),
    ("career", "Cohen Career Center", "https://events.wm.edu/calendar/upcoming_ical/career"),
    ("wellness", "Health & Wellness", "https://events.wm.edu/calendar/upcoming_ical/wellness"),
    ("arts", "Arts & Entertainment", "https://events.wm.edu/calendar/upcoming_ical/arts"),
    ("theatre-performance", "Theatre & Performance", "https://events.wm.edu/calendar/upcoming_ical/theatre-performance"),
    ("music", "Music Department Events", "https://events.wm.edu/calendar/upcoming_ical/music"),
    ("student-affairs", "Student Affairs & Campus Life", "https://events.wm.edu/calendar/upcoming_ical/student-affairs"),
    ("cce", "Civic & Community Engagement", "https://events.wm.edu/calendar/upcoming_ical/cce"),
    ("computerscience", "Computer Science Colloquia & Events", "https://events.wm.edu/calendar/upcoming_ical/computerscience"),
    ("studenthappenings", "Sadler & Campus Happenings", "https://events.wm.edu/calendar/upcoming_ical/studenthappenings"),
    ("academiccalendarug", "Undergraduate Academic Calendar", "https://events.wm.edu/calendar/upcoming_ical/academiccalendarug"),
)


# ---------------------------------------------------------------- time zones
class _EasternFallback(tzinfo):
    """US Eastern rules (EST/EDT: 2nd Sunday of March to 1st Sunday of November) for machines without tzdata."""

    def _edges(self, year: int) -> Tuple[datetime, datetime]:
        def sunday(month: int, nth: int) -> date:
            first = date(year, month, 1)
            return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (nth - 1))
        return datetime.combine(sunday(3, 2), dtime(2)), datetime.combine(sunday(11, 1), dtime(2))

    def _is_dst(self, dt: datetime) -> bool:
        start, end = self._edges(dt.year)
        wall = dt.replace(tzinfo=None)
        if start <= wall < end - timedelta(hours=1):
            return True
        return end - timedelta(hours=1) <= wall < end and not dt.fold   # the repeated hour: fold=0 is the first pass

    def utcoffset(self, dt):
        return timedelta(hours=-4 if self._is_dst(dt) else -5)

    def dst(self, dt):
        return timedelta(hours=1 if self._is_dst(dt) else 0)

    def tzname(self, dt):
        return "EDT" if self._is_dst(dt) else "EST"

    def fromutc(self, dt):
        utc = dt.replace(tzinfo=None)
        start, end = self._edges(utc.year)
        start_utc, end_utc = start + timedelta(hours=5), end + timedelta(hours=4)
        dst = start_utc <= utc < end_utc
        local = utc + timedelta(hours=-4 if dst else -5)
        fold = 1 if end_utc <= utc < end_utc + timedelta(hours=1) else 0
        return local.replace(tzinfo=self, fold=fold)


def _load_campus_tz() -> tzinfo:
    try:
        return ZoneInfo(CAMPUS_TZ_NAME)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        return _EasternFallback()


CAMPUS_TZ = _load_campus_tz()
_TZID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+\-]*(?:/[A-Za-z0-9_+\-]+){0,2}")

WINDOWS_TZ_MAP = {
    "eastern standard time": CAMPUS_TZ_NAME,
    "eastern daylight time": CAMPUS_TZ_NAME,
    "us/eastern": CAMPUS_TZ_NAME,
    "est": CAMPUS_TZ_NAME,
    "edt": CAMPUS_TZ_NAME,
    "utc": "UTC",
    "gmt": "UTC",
}


class ICalendarError(ValueError):
    """A feed cannot be safely parsed."""


class FetchError(RuntimeError):
    """A feed could not be fetched within the rules (host, redirect, size, status)."""


def resolve_tzid(tz_name: Any) -> str:
    """Windows, legacy and case-insensitive zone names to IANA names; anything else is returned as given."""
    if not isinstance(tz_name, str):
        return CAMPUS_TZ_NAME
    cleaned = tz_name.strip().strip("\"'").strip()
    return WINDOWS_TZ_MAP.get(cleaned.lower(), cleaned) if cleaned else CAMPUS_TZ_NAME


@functools.lru_cache(maxsize=64)
def _zone(name: str) -> tzinfo:
    if name == "UTC":
        return dt_timezone.utc
    if name == CAMPUS_TZ_NAME:
        return CAMPUS_TZ
    if not _TZID_RE.fullmatch(name) or len(name) > 64:
        raise ICalendarError("Unknown time zone")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:   # hostile names raise ValueError or OSError
        raise ICalendarError("Unknown time zone") from exc


def campus_now(now: Optional[datetime] = None) -> datetime:
    """An aware campus-time datetime (naive input is read as campus time)."""
    if now is None:
        return datetime.now(CAMPUS_TZ)
    return now.replace(tzinfo=CAMPUS_TZ) if now.tzinfo is None else now.astimezone(CAMPUS_TZ)


def local_midnight_ts(d: date) -> float:
    return datetime.combine(d, dtime.min, tzinfo=CAMPUS_TZ).timestamp()


# ---------------------------------------------------------------- feed URLs and text cleaning
def is_allowed_feed_url(url: Any) -> bool:
    """An allowed W&M calendar host over https on port 443, without credentials."""
    if not isinstance(url, str) or not url.strip():
        return False
    if re.search(r"[\x00-\x1f\x7f\\]", url) or " " in url.strip():   # URL parsers disagree about these
        return False
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme != "https" or parsed.port not in (None, 443):
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        return (parsed.hostname or "").lower() in ALLOWED_HOSTS
    except (ValueError, TypeError):
        return False


_TAG_RE = re.compile(r"<[^<>]{0,2000}>")   # bounded and no nested "<": a run of "<" cannot make this quadratic
_CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def clean_text(value: Any, limit: int, multiline: bool = False) -> str:
    """Plain text: entities decoded, tags removed, control characters dropped, whitespace tidied, length capped."""
    text = html.unescape(str(value or "")[:max(limit, 1) * 8 + 4000])   # cut before the regex work, not after
    text = _TAG_RE.sub(" ", text)
    text = _CTRL_RE.sub("", text)
    if multiline:
        text = "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in text.replace("\r", "\n").split("\n"))
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
    else:
        text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def clean_url(value: Any) -> str:
    """An https link with a host and no credentials, else ''."""
    url = str(value or "").strip()
    if not url or len(url) > 500 or re.search(r"[\x00-\x20\x7f<>\"]", url):
        return ""
    try:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None:
            return ""
        parsed.port  # noqa: B018  (a bad port raises ValueError)
    except ValueError:
        return ""
    return url


WM_BUILDING_PATTERNS: List[Tuple["re.Pattern[str]", str]] = [
    (re.compile(r"\b(?:Integrated Science Center(?:\s+(?:1|2|3|Phase\s+[123]))?|Integrated Science Ctr|ISC(?:\s+[123])?)\b", re.I), "ISC"),
    (re.compile(r"\b(?:Sadler Center|Sadler Ctr|Sadler)\b", re.I), "Sadler"),
    (re.compile(r"\b(?:Blow Memorial Hall|Blow Hall|Blow)\b", re.I), "Blow"),
    (re.compile(r"\b(?:Jones Hall|Jones)\b", re.I), "Jones"),
    (re.compile(r"\b(?:Blair Hall|Blair)\b", re.I), "Blair"),
    (re.compile(r"\b(?:Chancellors Hall|Chancellors|Tyler Hall)\b", re.I), "Chancellors"),
    (re.compile(r"\b(?:McGlothlin-Street Hall|McGlothlin-Street|McGlothlin Street Hall|McGlothlin Street|MSH)\b", re.I), "McGlothlin-Street"),
    (re.compile(r"\b(?:Boswell Hall|Boswell|Morton Hall)\b", re.I), "Boswell"),
    (re.compile(r"\b(?:Tucker Hall|Tucker)\b", re.I), "Tucker"),
    (re.compile(r"\b(?:Earl Gregg Swem Library|Swem Library|Swem)\b", re.I), "Swem"),
    (re.compile(r"\b(?:Wren Building|Wren)\b", re.I), "Wren"),
    (re.compile(r"\b(?:Miller Hall|Miller)\b", re.I), "Miller"),
    (re.compile(r"\b(?:Small Hall|Small)\b", re.I), "Small"),
    (re.compile(r"\b(?:Washington Hall|Washington)\b", re.I), "Washington"),
    (re.compile(r"\b(?:Student Recreation Center|Student Rec Center|Rec Center)\b", re.I), "Rec Center"),
]


def normalize_wm_location(raw_loc: Any) -> str:
    """Campus building names and room numbers in one short form ("Integrated Science Center 1127" -> "ISC 1127")."""
    loc = str(raw_loc or "").strip()
    if not loc:
        return ""
    for pattern, canonical in WM_BUILDING_PATTERNS:
        m = pattern.search(loc)
        if m:
            prefix = loc[:m.start()].strip(" ,-–;:|")
            suffix = loc[m.end():].strip(" ,-–;:|")
            suffix = re.sub(r"^(?:room|rm\.?|suite|ste\.?)\s*", "", suffix, flags=re.I).strip(" ,-–;:|")
            return " ".join(p for p in (prefix, canonical, suffix) if p)
    return loc


# ---------------------------------------------------------------- iCalendar parsing
def _unfold_lines(text: str) -> List[str]:
    physical = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    parts: List[List[str]] = []   # joined once at the end: appending to a growing string is quadratic
    for line in physical:
        if line.startswith((" ", "\t")):
            if not parts:
                raise ICalendarError("Feed starts with an orphan folded line")
            parts[-1].append(line[1:])
        elif line:
            parts.append([line])
    return ["".join(p) for p in parts]


def _split_unquoted(value: str, delimiter: str) -> List[str]:
    """Splits on a delimiter outside quoted parameter values."""
    parts: List[str] = []
    quoted = escaped = False
    start = 0
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == delimiter and not quoted:
            parts.append(value[start:index])
            start = index + 1
    if quoted:
        raise ICalendarError("Unterminated quoted parameter value")
    parts.append(value[start:])
    return parts


def _split_content_line(line: str) -> Tuple[str, Dict[str, str], str]:
    """NAME;PARAM=value:value, respecting quoted parameter values."""
    quoted = escaped = False
    separator = -1
    for index, char in enumerate(line):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif char == ":" and not quoted:
            separator = index
            break
    if separator < 1:
        raise ICalendarError(f"Malformed content line: {line[:80]!r}")
    left, value = line[:separator], line[separator + 1:]
    parts = _split_unquoted(left, ";")
    name = parts[0].split(".")[-1].upper()
    params: Dict[str, str] = {}
    for part in parts[1:]:
        key, equals, raw = part.partition("=")
        if equals:
            raw = raw.strip()
            if len(raw) >= 2 and raw[0] == raw[-1] == '"':
                raw = raw[1:-1]
            params[key.strip().upper()] = raw
    return name, params, value


def _unescape_text(value: str) -> str:
    # one pass: a backslash that is itself escaped must not start a line break with the "n" after it
    return re.sub(r"\\([\\,;:nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), value)


def _split_escaped_commas(value: str) -> List[str]:
    parts: List[str] = []
    escaped = False
    start = 0
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ",":
            parts.append(value[start:index])
            start = index + 1
    parts.append(value[start:])
    return parts


def _parse_duration(value: str, is_all_day: bool) -> Tuple[timedelta, timedelta]:
    """A positive RFC 5545 duration as (nominal days/weeks, exact hours/minutes/seconds), so wall time survives DST."""
    match = re.fullmatch(r"(?P<sign>[+-])?P(?:(?P<weeks>\d+)W|(?:(?P<days>\d+)D)?"
                         r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?)", value)
    if not match:
        raise ICalendarError(f"Invalid iCalendar duration: {value[:40]!r}")
    try:
        values = {key: int(match.group(key) or 0) for key in ("weeks", "days", "hours", "minutes", "seconds")}
    except (OverflowError, ValueError) as exc:
        raise ICalendarError("iCalendar duration is out of range") from exc
    if "T" in value and not any(values[k] for k in ("hours", "minutes", "seconds")):
        raise ICalendarError("Invalid iCalendar duration")
    if not any(values.values()) or match.group("sign") == "-":
        raise ICalendarError("VEVENT duration must be positive")
    if is_all_day and any(values[k] for k in ("hours", "minutes", "seconds")):
        raise ICalendarError("All-day VEVENT duration must use whole days or weeks")
    try:
        return (timedelta(weeks=values["weeks"], days=values["days"]),
                timedelta(hours=values["hours"], minutes=values["minutes"], seconds=values["seconds"]))
    except (OverflowError, ValueError) as exc:
        raise ICalendarError("iCalendar duration is out of range") from exc


def _parse_datetime(value: str, params: Dict[str, str]) -> Tuple[str, str, bool]:
    """(ISO value, time zone name, is_all_day) of a DTSTART/DTEND/EXDATE/UNTIL value. A zone name that cannot be
    loaded (unknown, or hostile: ValueError/OSError) falls back to the campus zone."""
    tz_name = resolve_tzid(params.get("TZID", CAMPUS_TZ_NAME))
    if params.get("VALUE", "").upper() == "DATE" or re.fullmatch(r"\d{8}", value):
        try:
            parsed_date = datetime.strptime(value, "%Y%m%d").date()
        except ValueError as exc:
            raise ICalendarError(f"Invalid iCalendar date: {value[:20]!r}") from exc
        if not MIN_YEAR <= parsed_date.year <= MAX_YEAR:
            raise ICalendarError("Date out of range")
        return parsed_date.isoformat(), tz_name if _zone_ok(tz_name) else CAMPUS_TZ_NAME, True
    if not re.fullmatch(r"\d{8}T\d{4}(?:\d{2})?Z?", value):
        raise ICalendarError(f"Unsupported iCalendar date-time: {value[:30]!r}")
    is_utc = value.endswith("Z")
    raw = value[:-1] if is_utc else value
    try:
        parsed = datetime.strptime(raw, "%Y%m%dT%H%M%S" if len(raw) == 15 else "%Y%m%dT%H%M")
    except ValueError as exc:
        raise ICalendarError(f"Invalid iCalendar date-time: {value[:30]!r}") from exc
    if not MIN_YEAR <= parsed.year <= MAX_YEAR:
        raise ICalendarError("Date out of range")
    name = "UTC" if is_utc else (tz_name if _zone_ok(tz_name) else CAMPUS_TZ_NAME)
    return parsed.replace(tzinfo=_zone(name)).isoformat(), name, False


def _zone_ok(name: str) -> bool:
    try:
        _zone(name)
        return True
    except ICalendarError:
        return False


def _event_from_properties(properties: Dict[str, List[Tuple[Dict[str, str], str]]], strict: bool = True) -> Optional[Dict[str, Any]]:
    for name in ("UID", "SUMMARY", "DTSTART", "DTEND", "DURATION", "STATUS"):
        if len(properties.get(name, [])) > 1:
            raise ICalendarError(f"VEVENT contains multiple {name} properties")

    def first(name: str):
        values = properties.get(name)
        return values[0] if values else None

    status = first("STATUS")
    if status and status[1].strip().upper() == "CANCELLED":
        return None
    uid_item, title_item, start_item = first("UID"), first("SUMMARY"), first("DTSTART")
    uid = _CTRL_RE.sub("", _unescape_text(uid_item[1]).replace("\n", "")).strip()[:200] if uid_item else ""
    if not uid:
        raise ICalendarError("VEVENT is missing UID")
    title = clean_text(_unescape_text(title_item[1]), 300) if title_item else ""
    if not title:
        raise ICalendarError("VEVENT is missing SUMMARY")
    if not start_item:
        raise ICalendarError("VEVENT is missing DTSTART")

    start_at, timezone_name, is_all_day = _parse_datetime(start_item[1], start_item[0])
    end_item, duration_item = first("DTEND"), first("DURATION")
    if end_item and duration_item:
        raise ICalendarError("VEVENT cannot contain both DTEND and DURATION")

    end_at: Optional[str] = None
    if end_item:
        end_at, _, end_is_all_day = _parse_datetime(end_item[1], end_item[0])
        if end_is_all_day != is_all_day:
            if strict:
                raise ICalendarError("VEVENT DTSTART and DTEND value types do not match")
            if not is_all_day:   # a date end on a timed start: the end of that day
                end_at = datetime.combine(date.fromisoformat(end_at), dtime(23, 59, 59), tzinfo=_zone(timezone_name)).isoformat()
            else:
                end_at = end_at[:10]
        if is_all_day:
            if date.fromisoformat(end_at) <= date.fromisoformat(start_at):
                end_at = (date.fromisoformat(start_at) + timedelta(days=1)).isoformat()
        elif datetime.fromisoformat(end_at) <= datetime.fromisoformat(start_at):
            raise ICalendarError("VEVENT DTEND must be after DTSTART")
    elif duration_item:
        nominal, exact = _parse_duration(duration_item[1], is_all_day)
        try:
            if is_all_day:
                end_at = (date.fromisoformat(start_at) + nominal).isoformat()
            else:
                zone = _zone(timezone_name)
                wall_end = datetime.fromisoformat(start_at).replace(tzinfo=None) + nominal
                end_at = (wall_end.replace(tzinfo=zone).astimezone(dt_timezone.utc) + exact).astimezone(zone).isoformat()
        except (OverflowError, ValueError) as exc:
            raise ICalendarError("VEVENT DURATION is out of range") from exc
    elif is_all_day:
        end_at = (date.fromisoformat(start_at) + timedelta(days=1)).isoformat()   # a DATE event lasts one day
    # a timed event with neither DTEND nor DURATION has no known end: end_at stays None

    categories: List[str] = []
    for _, raw_categories in properties.get("CATEGORIES", []):
        categories.extend(c for c in (clean_text(_unescape_text(raw), 60) for raw in _split_escaped_commas(raw_categories)) if c)

    def text_value(name: str, limit: int, multiline: bool = False) -> str:
        item = first(name)
        return clean_text(_unescape_text(item[1]), limit, multiline) if item else ""

    return {
        "uid": uid,
        "title": title,
        "description": text_value("DESCRIPTION", 2000, multiline=True),
        "start_at": start_at,
        "end_at": end_at,
        "timezone": timezone_name,
        "is_all_day": is_all_day,
        "location": normalize_wm_location(text_value("LOCATION", 200)),
        "source_url": clean_url(_unescape_text(first("URL")[1]).strip()) if first("URL") else "",
        "categories": categories[:20],
    }


DAY_CODES = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
MAX_RRULE_STEPS = 2000


def _rrule_parts(rrule: str) -> Dict[str, str]:
    parts: Dict[str, str] = {}
    for item in rrule.split(";"):
        k, sep, v = item.partition("=")
        if sep:
            parts[k.strip().upper()] = v.strip()
    return parts


def _fast_forward(freq: str, start_d: date, interval: int, bydays: List[int], from_d: date) -> Tuple[int, Any]:
    """(occurrences skipped, iterator of the later candidate dates). Skipped ones still count toward COUNT, so an old
    series is reached by arithmetic instead of stepping from its first date."""
    if freq == "DAILY":
        first = max(0, -(-(from_d - start_d).days // interval))

        def daily():
            i = first
            while True:
                yield start_d + timedelta(days=i * interval)
                i += 1
        return first, daily()
    start_monday = start_d - timedelta(days=start_d.weekday())
    per_week = len(bydays)
    in_first_week = len([d for d in bydays if d >= start_d.weekday()])
    skip_weeks = max(0, ((from_d - timedelta(days=7)) - start_monday).days // (7 * interval))
    skipped = 0 if skip_weeks == 0 else in_first_week + (skip_weeks - 1) * per_week

    def weekly():
        w = skip_weeks
        while True:
            monday = start_monday + timedelta(weeks=w * interval)
            for d in bydays:
                cand = monday + timedelta(days=d)
                if cand >= start_d:
                    yield cand
            w += 1
    return skipped, weekly()


def _expand_rrule(event: Dict[str, Any], rrule: str, exdate_items: List[Tuple[Dict[str, str], str]],
                  now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Instances of a FREQ=DAILY|WEEKLY series (INTERVAL, COUNT, UNTIL, BYDAY, EXDATE) inside the window
    [now - 2 days, now + 45 days] in campus time. Other frequencies keep the first instance only."""
    now = campus_now(now)
    win_start, win_end = now - timedelta(days=WINDOW_PAST_DAYS), now + timedelta(days=WINDOW_AHEAD_DAYS)
    parts = _rrule_parts(rrule)
    freq = parts.get("FREQ", "").upper()
    if freq not in ("DAILY", "WEEKLY"):
        return [event]
    try:
        interval = min(1000, max(1, int(parts.get("INTERVAL", 1))))
    except ValueError:
        interval = 1
    count = int(parts["COUNT"]) if re.fullmatch(r"[0-9]{1,6}", parts.get("COUNT", "")) else None
    is_all_day = bool(event["is_all_day"])

    exdate_days: set = set()
    exdate_instants: set = set()
    for params, raw in exdate_items:
        for token in raw.split(","):
            try:
                iso, _, ex_all_day = _parse_datetime(token.strip(), params)
            except ICalendarError:
                continue
            if is_all_day or ex_all_day:
                exdate_days.add(date.fromisoformat(iso[:10]))
            else:
                exdate_instants.add(datetime.fromisoformat(iso).astimezone(dt_timezone.utc))

    until_day: Optional[date] = None
    until_instant: Optional[datetime] = None
    if parts.get("UNTIL"):
        try:
            iso, _, until_all_day = _parse_datetime(parts["UNTIL"], {"VALUE": "DATE"} if re.fullmatch(r"\d{8}", parts["UNTIL"]) else {})
            if until_all_day:
                until_day = date.fromisoformat(iso[:10])
            else:
                until_instant = datetime.fromisoformat(iso).astimezone(dt_timezone.utc)
        except ICalendarError:
            pass

    zone = CAMPUS_TZ if is_all_day else _zone(event["timezone"])
    if is_all_day:
        start_d = date.fromisoformat(event["start_at"])
        wall_time = dtime.min
        duration = date.fromisoformat(event["end_at"]) - start_d
    else:
        start_wall = datetime.fromisoformat(event["start_at"]).replace(tzinfo=None)
        start_d, wall_time = start_wall.date(), start_wall.time()
        # the end in the start's zone (a feed may give DTEND in UTC), so the wall-clock length is right
        duration = (datetime.fromisoformat(event["end_at"]).astimezone(zone).replace(tzinfo=None) - start_wall) if event.get("end_at") else timedelta(0)

    if freq == "DAILY" and interval == 1 and parts.get("BYDAY"):
        freq = "WEEKLY"   # "every day, but only on these weekdays" is the same series as weekly on those days
    if freq == "WEEKLY":
        bydays = sorted({DAY_CODES[d[-2:].upper()] for d in parts.get("BYDAY", "").split(",") if d[-2:].upper() in DAY_CODES})
        bydays = bydays or [start_d.weekday()]
    else:
        bydays = []
    margin = timedelta(days=WINDOW_PAST_DAYS + 1)
    skipped, candidates = _fast_forward(freq, start_d, interval, bydays, win_start.date() - margin)

    instances: List[Dict[str, Any]] = []
    total, steps = skipped, 0
    try:
        for cand in candidates:
            steps += 1
            if steps > MAX_RRULE_STEPS or (count is not None and total >= count):
                break
            total += 1
            occ_start = datetime.combine(cand, wall_time, tzinfo=zone)
            if (until_day is not None and cand > until_day) or (until_instant is not None and occ_start.astimezone(dt_timezone.utc) > until_instant):
                break
            if cand > win_end.date() + margin:
                break
            if cand in exdate_days or occ_start.astimezone(dt_timezone.utc) in exdate_instants:
                continue
            if not (win_start <= occ_start <= win_end if not is_all_day else win_start.date() <= cand <= win_end.date()):
                continue
            inst = dict(event)
            inst["uid"] = f"{event['uid']}::{cand.strftime('%Y%m%d')}T{wall_time.strftime('%H%M')}"
            if is_all_day:
                inst["start_at"], inst["end_at"] = cand.isoformat(), (cand + duration).isoformat()
            else:
                inst["start_at"] = occ_start.isoformat()
                inst["end_at"] = (datetime.combine(cand, wall_time) + duration).replace(tzinfo=zone).isoformat() if event.get("end_at") else None
            instances.append(inst)
    except OverflowError:   # a series that runs past the last supported date
        pass
    return instances


def parse_ical(text: str, now: Optional[datetime] = None, strict: bool = True,
               max_events: Optional[int] = None) -> List[Dict[str, Any]]:
    """VEVENT records of a UTF-8 iCalendar feed: folded lines, quoted parameters, escaped text, all-day dates, UTC and
    TZID values, DTEND or DURATION, cancelled events skipped, FREQ=DAILY|WEEKLY series expanded over the window
    around `now`. Date-times with no zone are campus time. strict=False skips bad events and keeps the rest."""
    if not isinstance(text, str):
        raise ICalendarError("Feed must be text")
    if len(text) > MAX_FEED_BYTES or len(text.encode("utf-8", "replace")) > MAX_FEED_BYTES:
        raise ICalendarError(f"Feed exceeds {MAX_FEED_BYTES} bytes")
    if text.count("\n") + text.count("\r") - text.count("\r\n") > MAX_ICAL_LINES:
        raise ICalendarError(f"Feed exceeds {MAX_ICAL_LINES} lines")
    limit = max_events or MAX_EVENTS_PER_FEED
    lines = _unfold_lines(text)
    if not any(line.upper() == "BEGIN:VCALENDAR" for line in lines) or not any(line.upper() == "END:VCALENDAR" for line in lines):
        raise ICalendarError("Input is not a complete VCALENDAR feed")

    events: List[Dict[str, Any]] = []
    current: Optional[Dict[str, List[Tuple[Dict[str, str], str]]]] = None
    nested = 0   # depth inside a component of the event (VALARM): its lines are not the event's
    for line in lines:
        upper = line.upper()
        if current is not None and upper != "BEGIN:VEVENT" and upper != "END:VEVENT":
            if upper.startswith("BEGIN:"):
                nested += 1
                continue
            if nested:
                nested -= 1 if upper.startswith("END:") else 0
                continue
        if upper == "BEGIN:VEVENT":
            if current is not None:
                raise ICalendarError("Nested VEVENT block")
            current = {}
            continue
        if upper == "END:VEVENT":
            if current is None:
                raise ICalendarError("END:VEVENT without BEGIN:VEVENT")
            try:
                event = _event_from_properties(current, strict=strict)
                if event is not None:
                    rrule = current.get("RRULE", [])
                    events.extend(_expand_rrule(event, rrule[0][1], current.get("EXDATE", []), now=now) if rrule else [event])
            except ICalendarError:
                if strict:
                    raise
            current = None
            nested = 0
            if len(events) >= limit:
                break
            continue
        if current is None:
            continue
        try:
            name, params, value = _split_content_line(line)
            current.setdefault(name, []).append((params, value))
        except ICalendarError:
            if strict:
                raise
    else:
        if current is not None:
            raise ICalendarError("Unclosed VEVENT block")

    seen: set = set()
    unique: List[Dict[str, Any]] = []
    for ev in events[:limit]:
        if ev["uid"] in seen:
            if strict:
                raise ICalendarError("Feed contains duplicate event UIDs")
            continue
        seen.add(ev["uid"])
        unique.append(ev)
    return unique


# ---------------------------------------------------------------- stored form
def iso_ts(iso: str, is_all_day: bool) -> float:
    """Epoch seconds of a stored start_at/end_at (all-day dates start at campus midnight)."""
    if is_all_day:
        return local_midnight_ts(date.fromisoformat(str(iso)[:10]))
    dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return (dt.replace(tzinfo=CAMPUS_TZ) if dt.tzinfo is None else dt).timestamp()


def event_ts(event: Dict[str, Any]) -> Tuple[float, float]:
    """(start_ts, end_ts); an end that is not given is one hour after a timed start, one day after an all-day start."""
    all_day = bool(event["is_all_day"])
    start = iso_ts(event["start_at"], all_day)
    if event.get("end_at"):
        end = iso_ts(event["end_at"], all_day)
    else:
        end = iso_ts((date.fromisoformat(event["start_at"][:10]) + timedelta(days=1)).isoformat(), True) if all_day else start + 3600
    return start, max(end, start)


def make_dedupe_key(title: str, start_ts: float, is_all_day: bool) -> str:
    """The same event listed by several feeds: normalized title | campus-local start."""
    local = datetime.fromtimestamp(start_ts, CAMPUS_TZ)
    when = local.strftime("%Y-%m-%d") if is_all_day else local.strftime("%Y-%m-%d %H:%M")
    return f"{re.sub(r'[^a-z0-9]+', '', title.lower())}|{when}"


def _default_classify(event: Dict[str, Any]) -> str:
    import campus_events  # here, not at the top: campus_events imports this module
    return campus_events.classify(event)


def store_events(conn, slug: str, name: str, events: List[Dict[str, Any]],
                 classify: Optional[Callable[[Dict[str, Any]], str]] = None) -> Dict[str, int]:
    """Replaces one calendar's events in one transaction: rows are inserted or updated, memberships this feed no longer
    lists are removed and events left in no calendar are deleted. A failure leaves everything as it was."""
    if not str(slug).strip():
        raise ValueError("calendar slug must not be blank")
    classify = classify or _default_classify
    now = time.time()
    counts = {"seen": len(events), "inserted": 0, "updated": 0, "memberships_added": 0, "memberships_removed": 0, "skipped": 0}
    conn.commit()   # nothing pending: BEGIN IMMEDIATE cannot nest
    conn.execute("BEGIN IMMEDIATE")
    try:
        total = conn.execute("SELECT COUNT(*) FROM campus_events").fetchone()[0]
        active: set = set()
        for ev in events:
            uid = ev["uid"]
            existing = conn.execute("SELECT 1 FROM campus_events WHERE uid = ?", (uid,)).fetchone()
            if not existing and total >= MAX_EVENTS_TOTAL:
                counts["skipped"] += 1
                continue
            start_ts, end_ts = event_ts(ev)
            ev_for_class = {**ev, "categories": ev["categories"]}
            conn.execute(
                "INSERT INTO campus_events (uid, title, description, start_at, end_at, start_ts, end_ts, timezone, location, source_url, "
                "categories, category, is_all_day, dedupe_key, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(uid) DO UPDATE SET title=excluded.title, description=excluded.description, start_at=excluded.start_at, "
                "end_at=excluded.end_at, start_ts=excluded.start_ts, end_ts=excluded.end_ts, timezone=excluded.timezone, "
                "location=excluded.location, source_url=excluded.source_url, categories=excluded.categories, "
                "category=excluded.category, is_all_day=excluded.is_all_day, dedupe_key=excluded.dedupe_key, updated_at=excluded.updated_at",
                (uid, ev["title"], ev["description"], ev["start_at"], ev["end_at"], start_ts, end_ts, ev["timezone"], ev["location"],
                 ev["source_url"], json.dumps(ev["categories"], ensure_ascii=False), classify(ev_for_class), int(ev["is_all_day"]),
                 make_dedupe_key(ev["title"], start_ts, bool(ev["is_all_day"])), now))
            counts["updated" if existing else "inserted"] += 1
            total += 0 if existing else 1
            active.add(uid)
            member = conn.execute("SELECT 1 FROM campus_event_calendars WHERE uid = ? AND calendar_slug = ?", (uid, slug)).fetchone()
            conn.execute("INSERT INTO campus_event_calendars (uid, calendar_slug, calendar_name) VALUES (?, ?, ?) "
                         "ON CONFLICT(uid, calendar_slug) DO UPDATE SET calendar_name = excluded.calendar_name",
                         (uid, slug, name.strip() or slug))
            counts["memberships_added"] += 0 if member else 1
        stale = [r[0] for r in conn.execute("SELECT uid FROM campus_event_calendars WHERE calendar_slug = ?", (slug,)) if r[0] not in active]
        if stale:
            conn.executemany("DELETE FROM campus_event_calendars WHERE uid = ? AND calendar_slug = ?", [(u, slug) for u in stale])
            counts["memberships_removed"] = len(stale)
        conn.execute("DELETE FROM campus_events WHERE NOT EXISTS "
                     "(SELECT 1 FROM campus_event_calendars m WHERE m.uid = campus_events.uid)")
        conn.commit()
        return counts
    except Exception:
        conn.rollback()
        raise


def import_calendar(conn, slug: str, name: str, text: str, strict: bool = False, now: Optional[datetime] = None,
                    classify: Optional[Callable[[Dict[str, Any]], str]] = None) -> Dict[str, int]:
    """Parses a feed and replaces that calendar's events. A feed that fails to parse changes nothing."""
    return store_events(conn, slug, name, parse_ical(text, now=now, strict=strict), classify=classify)


# ---------------------------------------------------------------- fetching
_REDIRECTS = (301, 302, 303, 307, 308)


def fetch_feed(url: str, *, transport: Any = None, timeout: float = FETCH_TIMEOUT_S, max_bytes: int = MAX_FEED_BYTES) -> str:
    """The text of one allowed feed. At most one redirect, to the same host (still an allowed https URL); the body is
    streamed and refused past max_bytes."""
    if not is_allowed_feed_url(url):
        raise FetchError("not an allowed feed address")
    host = (urlparse(url).hostname or "").lower()
    headers = {"User-Agent": USER_AGENT, "Accept": "text/calendar, text/plain;q=0.5, */*;q=0.1"}
    started = time.monotonic()
    with httpx.Client(transport=transport, timeout=timeout, follow_redirects=False, headers=headers) as client:
        current = url
        for hop in range(2):
            with client.stream("GET", current) as resp:
                if resp.status_code in _REDIRECTS:
                    target = urljoin(current, resp.headers.get("location", ""))
                    if hop or not is_allowed_feed_url(target) or (urlparse(target).hostname or "").lower() != host:
                        raise FetchError("refused a redirect")
                    current = target
                    continue
                if resp.status_code != 200:
                    raise FetchError(f"HTTP {resp.status_code}")
                declared = resp.headers.get("content-length", "")
                if declared.isdigit() and int(declared) > max_bytes:
                    raise FetchError("feed is too large")
                chunks: List[bytes] = []
                size = 0
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > max_bytes:
                        raise FetchError("feed is too large")
                    if time.monotonic() - started > timeout:   # httpx times each read, not the whole download
                        raise FetchError("feed took too long")
                    chunks.append(chunk)
                return b"".join(chunks).decode("utf-8-sig", errors="replace")
    raise FetchError("refused a redirect")


def sync(fetch: Optional[Callable[[str], str]] = None, now: Optional[datetime] = None, deadline_s: float = SYNC_DEADLINE_S,
         feeds: Optional[Tuple[Tuple[str, str, str], ...]] = None) -> Dict[str, int]:
    """Fetches every feed first, then writes: no write transaction is open while waiting on the network. A feed that
    fails to fetch or parse keeps its old rows. Call it from a worker thread (db.conn() is per thread).
    fetch(url) -> text is injectable; the default is fetch_feed."""
    import db
    fetch = fetch or fetch_feed
    started = time.monotonic()
    ok = failed = 0
    parsed: List[Tuple[str, str, List[Dict[str, Any]]]] = []
    for slug, name, url in feeds or FEEDS:
        if STOP.is_set() or time.monotonic() - started > deadline_s:
            failed += 1
            continue
        try:
            parsed.append((slug, name, parse_ical(fetch(url), now=now, strict=False)))
        except Exception as exc:
            failed += 1
            print(f"[campus] feed {slug} skipped: {type(exc).__name__}")
    conn = db.conn()
    for slug, name, events in parsed:
        try:
            if STOP.is_set():   # the server is shutting down: its connections are about to close
                raise RuntimeError("stopped")
            store_events(conn, slug, name, events)
            ok += 1
        except Exception as exc:
            failed += 1
            print(f"[campus] feed {slug} not stored: {type(exc).__name__}")
    return {"feeds_ok": ok, "feeds_failed": failed, "total_events": conn.execute("SELECT COUNT(*) FROM campus_events").fetchone()[0]}


STOP = threading.Event()        # set while the server shuts down: a running sync skips what is left and ends
SYNC_LOCK = threading.Lock()   # one sync at a time; the route takes it before the worker thread starts
