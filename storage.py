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
