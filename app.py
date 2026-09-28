from datetime import datetime, time
from zoneinfo import ZoneInfo
from uuid import uuid4
import html
import hmac
import json
import streamlit as st
from storage import DemoStore, SheetsStore, validate

st.set_page_config(page_title='회의록 작성 프로그램', page_icon='📝', layout='centered')
st.markdown('''<style>
.stApp {background:#F4F7FA;color:#172B43}
.block-container {max-width:920px;padding-top:2.7rem;padding-bottom:3rem}
h1,h2,h3 {color:#172B43;letter-spacing:-.04em}
h1 {font-size:2.2rem!important}
[data-testid="stVerticalBlockBorderWrapper"]>div {background:white;border-radius:18px}
.stButton>button {border-radius:10px;min-height:45px;font-weight:600}
[data-testid="stTextInput"] input,[data-baseweb="select"]>div {border-radius:9px}
.eyebrow {font-size:12px;font-weight:700;letter-spacing:.18em;color:#158477;margin-bottom:9px}
.hero-sub {color:#65788B;margin:0 0 25px;font-size:15px}
.steps {display:flex;gap:8px;margin:22px 0 26px}
.step {flex:1;padding:12px 5px;background:#E8EEF3;border-radius:10px;text-align:center;color:#708090;font-size:13px}
.step.active {background:#137F75;color:white;font-weight:700}
.step.done {background:#DCEFEA;color:#116B62}
@media(max-width:550px){.block-container{padding-top:1.4rem}.step{font-size:11px}.steps{gap:4px}h1{font-size:1.8rem!important}}
</style>''', unsafe_allow_html=True)
try:
    config = st.secrets.to_dict()
except FileNotFoundError:
    config = {}

# Optional shared password, evaluated before any Google data is requested.
password = config.get('app_password')
if password and not st.session_state.get('authenticated'):
    st.title('회의록 작성 프로그램')
    with st.form('login'):
        entered = st.text_input('접속 비밀번호', type='password')
        if st.form_submit_button('입장하기', type='primary'):
            if hmac.compare_digest(entered.encode(), str(password).encode()):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error('비밀번호를 확인해 주세요.')
    st.stop()

s = st.session_state
# Keep keyed widget values when their wizard step is temporarily hidden.
for widget_key in list(s):
    if widget_key.startswith('input_'):
        s[widget_key] = s[widget_key]

def reset():
    for key in list(s):
        if key.startswith('input_'):
            del s[key]
    today = datetime.now(ZoneInfo('Asia/Seoul')).date()
    s.draft = dict(id=str(uuid4()), title='', date=today, start=time(9), end=time(10), people=[], place=None, agenda='', notes='', decisions='', actions='', author='')
    s.step = 0
    s.saved = False

if 'draft' not in s:
    reset()
if 'demo_rows' not in s:
    s.demo_rows = []
connected = bool(config.get('gcp_service_account') and config.get('google_sheets', {}).get('spreadsheet_id'))

@st.cache_resource(show_spinner=False)
def google_store():
    return SheetsStore(st.secrets['google_sheets'], st.secrets['gcp_service_account'])

st.markdown('<div class="eyebrow">MEETING NOTES / WORKSPACE</div>', unsafe_allow_html=True)
st.title('회의록 작성 프로그램')
st.markdown('<p class="hero-sub">회의의 흐름을 따라, 중요한 내용을 한곳에.</p>', unsafe_allow_html=True)
try:
    store = google_store() if connected else DemoStore(s.demo_rows)
    # Fresh per session, explicitly refreshed after saves or on request.
    if 'records' not in s:
        with st.spinner('회의록을 불러오는 중입니다…'):
            s.records = store.list()
except Exception:
    st.error('Google Sheets에 연결하지 못했습니다. 시트 ID, 서비스 계정 편집 권한, Secrets 설정과 시트 열 구성을 확인해 주세요. 연결 오류 시 데모 저장으로 전환하지 않습니다.')
    if st.button('연결 다시 시도'):
        google_store.clear()
        st.rerun()
    st.stop()

if connected:
    st.caption('● Google Sheets 연결됨 · 한국 시간 기준')
else:
    st.info('체험 모드 · Google Sheets는 아직 연결되지 않았습니다. 체험 기록은 현재 세션에만 남습니다.')

page = st.radio('메뉴', ['새 회의록', '저장된 회의록'], horizontal=True, label_visibility='collapsed')

def show_record(d):
    st.subheader(d['title'])
    st.write(f"{d['date']} · {d['start']}–{d['end']} · {d['place']}")
    st.write('참석자: ' + ', '.join(d['people']))
    st.write('작성자: ' + d['author'])
    for key, title in [('agenda', '안건'), ('notes', '논의 내용'), ('decisions', '결정 사항'), ('actions', '후속 업무')]:
        st.markdown('**' + title + '**')
        st.text(d.get(key) or '—')

if page == '저장된 회의록':
    a, b = st.columns([4, 1])
    with a:
        query = st.text_input('검색', placeholder='회의 제목, 참석자 또는 장소 검색')
    with b:
        st.write('')
        if st.button('새로고침', use_container_width=True):
            try:
                s.records = store.list()
                st.rerun()
            except Exception:
                st.error('불러오기에 실패했습니다. 잠시 후 다시 시도해 주세요.')
    records = [r for r in reversed(s.records) if query.casefold() in ' '.join([r['title'], r['place'], *r['people']]).casefold()]
    st.caption(f'총 {len(records)}건')
    if not records:
        st.info('아직 표시할 회의록이 없습니다.')
    for r in records:
        with st.expander(f"{r['date']} · {r['title']}"):
            show_record(r)
    st.stop()

if s.saved:
    st.success('Google Sheets에 저장했습니다.' if connected else '체험 기록을 저장했습니다. Google Sheets에는 저장되지 않았습니다.')
    with st.container(border=True):
        show_record(s.draft)
    st.download_button('회의록 JSON 다운로드', json.dumps(s.draft, ensure_ascii=False, indent=2, default=str), file_name=f"meeting-{s.draft['id']}.json", mime='application/json')
    if st.button('새 회의록 작성', type='primary'):
        reset()
        st.rerun()
    st.stop()

labels = ['일시', '참석자', '장소', '회의 내용', '확인 및 저장']
st.markdown('<div class="steps">' + ''.join(f'<div class="step {"active" if i == s.step else "done" if i < s.step else ""}">{i+1} · {html.escape(v)}</div>' for i, v in enumerate(labels)) + '</div>', unsafe_allow_html=True)
d = s.draft
people = sorted(set(config.get('defaults', {}).get('people', [])) | {p for r in s.records for p in r['people']} | set(d['people']))
places = sorted(set(config.get('defaults', {}).get('places', [])) | {r['place'] for r in s.records} | ({d['place']} if d['place'] else set()))

def capture(field, value):
    d[field] = value
    return value

with st.container(border=True):
    st.caption(f'STEP {s.step + 1:02d} / 05')
    if s.step == 0:
        st.subheader('언제 열리는 회의인가요?')
        capture('title', st.text_input('회의 제목 *', value=d['title'], placeholder='예: 9월 진료 운영 회의', max_chars=200, key='input_title')).strip()
        d['title'] = d['title'].strip()
        capture('date', st.date_input('회의 날짜 *', value=d['date'], format='YYYY/MM/DD', key='input_date'))
        c1, c2 = st.columns(2)
        with c1:
            capture('start', st.time_input('시작 시간 *', value=d['start'], step=900, key='input_start'))
        with c2:
            capture('end', st.time_input('종료 시간 *', value=d['end'], step=900, key='input_end'))
    elif s.step == 1:
        st.subheader('누가 참석하나요?')
        st.caption('명단에서 여러 명을 선택하세요. 없는 이름은 입력 후 Enter로 추가할 수 있습니다.')
        capture('people', [p.strip() for p in st.multiselect('참석자 *', people, default=d['people'], accept_new_options=True, placeholder='이름 검색 또는 새 이름 입력', key='input_people') if p.strip()])
        st.caption(f"{len(d['people'])}명 선택됨 · 새 이름은 회의록 저장 후 다음 회의에도 표시됩니다.")
    elif s.step == 2:
        st.subheader('어디에서 진행하나요?')
        capture('place', st.selectbox('회의 장소 *', places, index=places.index(d['place']) if d['place'] in places else None, accept_new_options=True, placeholder='장소 선택 또는 새 장소 입력', key='input_place'))
        if d['place']:
            d['place'] = d['place'].strip()
        st.caption('온라인 회의라면 Zoom, Google Meet 등을 입력해 주세요.')
    elif s.step == 3:
        st.subheader('어떤 이야기를 나누었나요?')
        capture('author', st.text_input('작성자 *', value=d['author'], max_chars=100, key='input_author').strip())
        for key, label, placeholder, height in [('agenda','안건','오늘 논의할 주요 안건',90), ('notes','논의 내용 *','안건별 주요 의견과 논의 내용을 적어 주세요.',170), ('decisions','결정 사항','합의된 결론과 결정 사항',100), ('actions','후속 업무','예: 자료 정리 / 담당자 / 10월 2일까지',100)]:
            capture(key, st.text_area(label, value=d[key], placeholder=placeholder, height=height, max_chars=45000, key='input_' + key).strip())
    else:
        st.subheader('저장 전, 한 번만 확인해 주세요.')
        show_record(d)
        st.caption('아래 버튼을 누르면 회의록 한 건이 Google Sheets에 저장됩니다.' if connected else '체험 모드에서는 현재 세션에만 저장됩니다.')

left, right = st.columns([1, 2])
with left:
    if st.button('← 이전', disabled=s.step == 0, use_container_width=True):
        s.step -= 1
        st.rerun()
with right:
    if s.step < 4:
        if st.button('다음 →', type='primary', use_container_width=True):
            error = None
            if s.step == 0:
                if not d['title']:
                    error = '회의 제목을 입력해 주세요.'
                elif d['end'] <= d['start']:
                    error = '종료 시간은 시작 시간 이후여야 합니다.'
            elif s.step == 1 and not d['people']:
                error = '참석자를 한 명 이상 선택해 주세요.'
            elif s.step == 2 and not d['place']:
                error = '장소를 선택하거나 입력해 주세요.'
            elif s.step == 3 and (not d['notes'] or not d['author']):
                error = '논의 내용과 작성자를 입력해 주세요.'
            if error:
                st.error(error)
            else:
                s.step += 1
                st.rerun()
    elif st.button('Google Sheets에 저장' if connected else '체험 기록 저장', type='primary', use_container_width=True):
        try:
            validate(d)
            payload = dict(d, date=str(d['date']), start=d['start'].strftime('%H:%M'), end=d['end'].strftime('%H:%M'), saved_at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='seconds'))
            with st.spinner('저장 중입니다…'):
                store.save(payload)
            s.draft = payload
            s.saved = True
            if not any(r['id'] == payload['id'] for r in s.records):
                s.records.append(payload)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
        except Exception:
            st.error('저장 결과를 확인하지 못했습니다. 입력 내용은 유지됩니다. 같은 화면에서 다시 저장하면 회의 ID로 기존 저장 여부를 확인합니다.')
st.caption('필수 항목 * · 입력 내용은 단계 이동 시 유지됩니다. 브라우저 새로고침·종료 시 미저장 내용은 사라질 수 있습니다.')
