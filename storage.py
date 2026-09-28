"""Google Sheets persistence; meeting rows also supply reusable dropdown options."""
import json
import threading

HEADERS = ['회의ID', '저장시각', '회의제목', '회의일자', '시작시간', '종료시간', '참석자', '장소', '안건', '논의내용', '결정사항', '후속업무', '작성자']
FIELDS = ['id', 'saved_at', 'title', 'date', 'start', 'end', 'people', 'place', 'agenda', 'notes', 'decisions', 'actions', 'author']
LOCK = threading.Lock()


def validate(d):
    missing = [label for key, label in [('title', '회의 제목'), ('people', '참석자'), ('place', '장소'), ('notes', '논의 내용'), ('author', '작성자')] if not d.get(key)]
    if missing:
        raise ValueError(', '.join(missing) + '을(를) 입력해 주세요.')
    if d['end'] <= d['start']:
        raise ValueError('종료 시간은 시작 시간 이후로 선택해 주세요. 자정을 넘는 회의는 날짜별로 나눠 주세요.')
    if any(len(str(v)) > 45000 for v in d.values()):
        raise ValueError('한 항목은 45,000자 이하로 작성해 주세요.')


def encode(d):
    return [json.dumps(d[k], ensure_ascii=False) if k == 'people' else str(d.get(k, '')) for k in FIELDS]


def decode(row):
    d = dict(zip(FIELDS, row + [''] * max(0, len(FIELDS) - len(row))))
    d['people'] = json.loads(d['people'] or '[]')
    return d


class SheetsStore:
    def __init__(self, config, account):
        import gspread
        self.client = gspread.service_account_from_dict(dict(account), scopes=['https://www.googleapis.com/auth/spreadsheets'])
        self.client.set_timeout(20)
        self.book = self.client.open_by_key(config['spreadsheet_id'])
        name = config.get('worksheet', '회의록')
        try:
            self.ws = self.book.worksheet(name)
        except gspread.WorksheetNotFound:
            try:
                self.ws = self.book.add_worksheet(title=name, rows=1000, cols=len(HEADERS))
            except gspread.exceptions.APIError:
                self.ws = self.book.worksheet(name)
        with LOCK:
            header = self.ws.row_values(1)
            if not header:
                self.ws.update(values=[HEADERS], range_name='A1:M1', value_input_option='RAW')
                self.ws.freeze(rows=1)
            elif header != HEADERS:
                raise ValueError('시트의 열 구성이 다릅니다. 전용 빈 탭을 지정해 주세요.')

    def list(self):
        return [decode(r) for r in self.ws.get_all_values()[1:] if r and r[0]]

    def save(self, d):
        validate(d)
        # Prevent repeated clicks/retries within a process. UUID also helps reconcile
        # a timeout after the server has accepted the first append.
        with LOCK:
            if d['id'] in self.ws.col_values(1)[1:]:
                return
            self.ws.append_row(encode(d), value_input_option='RAW', insert_data_option='INSERT_ROWS', table_range='A:M')


class DemoStore:
    def __init__(self, rows):
        self.rows = rows

    def list(self):
        return list(self.rows)

    def save(self, d):
        validate(d)
        if not any(r['id'] == d['id'] for r in self.rows):
            self.rows.append(dict(d))

# Append-only phrase revisions avoid deleting or shifting spreadsheet rows.
PHRASE_HEADERS = ['상용구ID', '이름', '분류', '내용', '수정시각', '삭제여부', '버전ID']
PHRASE_FIELDS = ['id', 'name', 'category', 'content', 'updated_at', 'deleted', 'revision']
CATEGORIES = {'agenda': '안건', 'notes': '논의 내용', 'decisions': '결정 사항', 'actions': '후속 업무'}


def latest_phrases(rows):
    latest = {}
    for row in rows:
        if len(row) >= 7 and row[0]:
            latest[row[0]] = dict(zip(PHRASE_FIELDS, row[:7]))
    return latest


def check_phrase(item):
    if not item['name'].strip() or not item['content'].strip():
        raise ValueError('상용구 이름과 내용을 입력해 주세요.')
    if item['category'] not in CATEGORIES:
        raise ValueError('상용구 분류를 선택해 주세요.')
    if len(item['name']) > 200 or len(item['content']) > 45000:
        raise ValueError('이름은 200자, 내용은 45,000자 이하로 입력해 주세요.')


class PhraseStore:
    def __init__(self, book=None, rows=None):
        self.rows = rows if rows is not None else []
        self.ws = None
        if book is not None:
            import gspread
            try:
                self.ws = book.worksheet('상용구')
            except gspread.WorksheetNotFound:
                try:
                    self.ws = book.add_worksheet(title='상용구', rows=1000, cols=7)
                except gspread.exceptions.APIError:
                    self.ws = book.worksheet('상용구')
            with LOCK:
                header = self.ws.row_values(1)
                if not header:
                    self.ws.update(values=[PHRASE_HEADERS], range_name='A1:G1', value_input_option='RAW')
                    self.ws.freeze(rows=1)
                elif header != PHRASE_HEADERS:
                    raise ValueError('상용구 탭의 열 구성이 다릅니다. 기존 탭의 이름을 변경한 후 다시 시도해 주세요.')

    def _rows(self):
        return self.ws.get_all_values()[1:] if self.ws is not None else self.rows

    def list(self):
        return [p for p in latest_phrases(self._rows()).values() if p['deleted'] != '1']

    def save(self, item, expected_revision=None):
        check_phrase(item)
        with LOCK:
            rows = self._rows()
            # A retry keeps the same revision UUID, including after response loss.
            if any(len(r) >= 7 and r[6] == item['revision'] for r in rows):
                return
            current = latest_phrases(rows).get(item['id'])
            if (current['revision'] if current else None) != expected_revision:
                raise ValueError('다른 사용자가 이 상용구를 변경했습니다. 목록을 새로고침하고 다시 편집해 주세요.')
            active = latest_phrases(rows).values()
            if item['deleted'] != '1' and any(p['id'] != item['id'] and p['deleted'] != '1' and p['category'] == item['category'] and p['name'].strip().casefold() == item['name'].strip().casefold() for p in active):
                raise ValueError('같은 분류에 동일한 이름이 있습니다. 다른 이름을 사용해 주세요.')
            row = [str(item[k]) for k in PHRASE_FIELDS]
            if self.ws is not None:
                self.ws.append_row(row, value_input_option='RAW', insert_data_option='INSERT_ROWS', table_range='A:G')
            else:
                self.rows.append(row)
