import csv
import hashlib
import io
import re


OWN_DOUYIN_FIELD_ALIASES = {
    "title": ["作品名称", "标题", "title", "作品标题"],
    "video_url": ["作品链接", "视频链接", "video_url", "url", "链接"],
    "published_at": ["发布时间", "published_at", "发布时间 "],
    "content_format": ["体裁", "内容体裁", "content_format"],
    "visibility_status": ["审核状态", "状态", "visibility_status"],
    "play_count": ["播放量", "播放次数", "play_count"],
    "completion_rate": ["完播率", "completion_rate"],
    "five_sec_completion_rate": ["5s完播率", "5秒完播率", "five_sec_completion_rate"],
    "cover_click_rate": ["封面点击率", "cover_click_rate"],
    "two_sec_bounce_rate": ["2s跳出率", "2秒跳出率", "two_sec_bounce_rate"],
    "avg_play_duration": ["平均播放时长", "avg_play_duration"],
    "like_count": ["点赞量", "点赞数", "like_count"],
    "share_count": ["分享量", "分享数", "share_count"],
    "comment_count": ["评论量", "评论数", "comment_count"],
    "collect_count": ["收藏量", "收藏数", "collect_count"],
    "profile_visit_count": ["主页访问量", "profile_visit_count"],
    "follower_delta": ["粉丝增量", "涨粉数", "follower_delta"],
    "transcript": ["作品文案", "文案", "口播文案", "transcript"],
    "notes": ["备注", "notes"],
}

OWN_DOUYIN_INTEGER_FIELDS = {
    "play_count", "like_count", "share_count", "comment_count", "collect_count",
    "profile_visit_count", "follower_delta",
}
OWN_DOUYIN_FLOAT_FIELDS = {
    "completion_rate", "five_sec_completion_rate", "cover_click_rate",
    "two_sec_bounce_rate", "avg_play_duration",
}


def normalize_import_header(value):
    return re.sub(r"\s+", "", str(value or "")).strip().lower()


def build_own_douyin_field_map(headers):
    normalized_headers = {normalize_import_header(header): header for header in headers}
    mapping = {}
    for target, aliases in OWN_DOUYIN_FIELD_ALIASES.items():
        for alias in aliases:
            header = normalized_headers.get(normalize_import_header(alias))
            if header is not None:
                mapping[target] = header
                break
    return mapping


def clean_import_value(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {"-", "—", "nan", "NaN", "None"}:
        return None
    return text


def parse_import_int(value):
    text = clean_import_value(value)
    if text is None:
        return None
    text = text.replace(",", "")
    try:
        return int(float(text))
    except Exception:
        return None


def parse_import_float(value):
    text = clean_import_value(value)
    if text is None:
        return None
    text = text.replace(",", "")
    try:
        if text.endswith("%"):
            return float(text[:-1]) / 100
        return float(text)
    except Exception:
        return None


def normalize_import_row(raw_row, field_map):
    item = {}
    for field, header in field_map.items():
        value = raw_row.get(header)
        if field in OWN_DOUYIN_INTEGER_FIELDS:
            item[field] = parse_import_int(value)
        elif field in OWN_DOUYIN_FLOAT_FIELDS:
            item[field] = parse_import_float(value)
        else:
            item[field] = clean_import_value(value)
    item["title"] = item.get("title") or ""
    return item


def own_douyin_source_key(item):
    url = clean_import_value(item.get("video_url"))
    if url:
        return f"url:{url}"
    title = clean_import_value(item.get("title")) or ""
    published_at = clean_import_value(item.get("published_at")) or ""
    digest = hashlib.sha1(f"{title}|{published_at}".encode("utf-8")).hexdigest()
    return f"title_time:{digest}"


def read_own_douyin_import_file(file_storage):
    filename = (file_storage.filename or "").lower()
    payload = file_storage.read()
    rows = []
    if filename.endswith(".xlsx"):
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise RuntimeError("缺少 openpyxl 依赖，请先安装 requirements.txt") from exc
        workbook = load_workbook(io.BytesIO(payload), read_only=True, data_only=True)
        sheet = workbook.active
        values = list(sheet.iter_rows(values_only=True))
        if not values:
            return [], []
        headers = [str(cell).strip() if cell is not None else "" for cell in values[0]]
        for row in values[1:]:
            raw = {headers[index]: value for index, value in enumerate(row) if index < len(headers) and headers[index]}
            if any(clean_import_value(value) for value in raw.values()):
                rows.append(raw)
        return headers, rows
    if filename.endswith(".csv"):
        text = None
        for encoding in ("utf-8-sig", "gb18030"):
            try:
                text = payload.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if text is None:
            raise ValueError("CSV 编码无法识别，请使用 UTF-8 或 GB18030")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []
        rows = [row for row in reader if any(clean_import_value(value) for value in row.values())]
        return headers, rows
    raise ValueError("仅支持 .xlsx 或 .csv 文件")


def parse_own_douyin_import(file_storage):
    headers, raw_rows = read_own_douyin_import_file(file_storage)
    field_map = build_own_douyin_field_map(headers)
    if "title" not in field_map:
        raise ValueError("导入文件缺少作品名称/标题字段")
    normalized_rows = [normalize_import_row(row, field_map) for row in raw_rows]
    valid_rows = [row for row in normalized_rows if row.get("title")]
    return {
        "headers": headers,
        "field_map": field_map,
        "rows": valid_rows,
        "raw_count": len(raw_rows),
        "valid_count": len(valid_rows),
    }
