from datetime import datetime, time
from zoneinfo import ZoneInfo
from uuid import uuid4
import html
import hmac
import json
import streamlit as st
from storage import DemoStore, SheetsStore, PhraseStore, CATEGORIES, validate
from reuse import COPY_FIELDS, new_draft, insert_phrase
from exports import make_docx, make_pdf, filename

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
    if widget_key.startswith(('input_', 'phrase_name_', 'phrase_mode_', 'replace_ok_')):
        s[widget_key] = s[widget_key]

def reset():
    for key in list(s):
        if key.startswith('input_'):
            del s[key]
    s.draft = new_draft()
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
except Exception as exc:
    st.caption(f'연결 오류 유형: {type(exc).__name__}')
    st.error('Google Sheets에 연결하지 못했습니다. 시트 ID, 서비스 계정 편집 권한, Secrets 설정과 시트 열 구성을 확인해 주세요. 연결 오류 시 데모 저장으로 전환하지 않습니다.')
    if st.button('연결 다시 시도'):
        google_store.clear()
        st.rerun()
    st.stop()

if connected:
    st.caption('● Google Sheets 연결됨 · 한국 시간 기준')
else:
    st.info('체험 모드 · Google Sheets는 아직 연결되지 않았습니다. 체험 기록은 현재 세션에만 남습니다.')

page = st.radio('메뉴', ['새 회의록', '저장된 회의록', '상용구 관리'], horizontal=True, label_visibility='collapsed')

def download_record(record, key_prefix):
    # Limit export generation to this session and one selected record at a time.
    signature = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
    if st.button('인쇄·문서 다운로드 준비', key=key_prefix + '_prepare'):
        with st.spinner('인쇄용 파일을 준비하는 중입니다…'):
            outputs, errors = {}, []
            for extension, builder in [('pdf', make_pdf), ('docx', make_docx)]:
                try:
                    outputs[extension] = builder(record)
                except Exception as exc:
                    errors.append(f'{extension.upper()} 생성 실패 ({type(exc).__name__})')
            s.export_bundle = dict(signature=signature, outputs=outputs, errors=errors)
    bundle = s.get('export_bundle', {})
    if bundle.get('signature') == signature:
        for error in bundle['errors']:
            st.error(error + ' · requirements.txt와 assets/fonts 폴더가 업로드되었는지 확인해 주세요.')
        a, b = st.columns(2)
        with a:
            if 'pdf' in bundle['outputs']:
                st.download_button('PDF 다운로드 · 인쇄용', bundle['outputs']['pdf'], file_name=filename(record) + '.pdf', mime='application/pdf', key=key_prefix + '_pdf', use_container_width=True)
        with b:
            if 'docx' in bundle['outputs']:
                st.download_button('Word 다운로드 · 편집용', bundle['outputs']['docx'], file_name=filename(record) + '.docx', mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document', key=key_prefix + '_docx', use_container_width=True)
        st.caption('PDF를 열어 A4로 인쇄하세요. Word 파일은 편집 후 인쇄할 수 있습니다.')


def show_record(d):
    st.subheader(d['title'])
    st.write(f"{d['date']} · {d['start']}–{d['end']} · {d['place']}")
    st.write('참석자: ' + ', '.join(d['people']))
    st.write('작성자: ' + d['author'])
    for key, title in [('agenda', '안건'), ('notes', '논의 내용'), ('decisions', '결정 사항'), ('actions', '후속 업무')]:
        st.markdown('**' + title + '**')
        st.text(d.get(key) or '—')

def phrase_store():
    if 'demo_phrases' not in s:
        s.demo_phrases = []
    return PhraseStore(book=store.book) if connected else PhraseStore(rows=s.demo_phrases)


def load_phrases(force=False):
    try:
        if force or 'phrases' not in s:
            s.phrases = phrase_store().list()
        return s.phrases
    except Exception as exc:
        st.error(f'상용구를 불러오지 못했습니다 ({type(exc).__name__}). 시트 권한과 상용구 탭 구성을 확인해 주세요.')
        return None


def save_phrase(name, category, content, original=None, deleted=False, operation='new'):
    # Keep one operation UUID across ambiguous network failures.
    signature = (name.strip(), category, content.strip(), original['id'] if original else None, original['revision'] if original else None, deleted)
    pending_key = 'phrase_pending_' + operation
    pending = s.get(pending_key)
    if not pending or pending['signature'] != signature:
        pending = dict(signature=signature, item=dict(id=original['id'] if original else str(uuid4()), name=name.strip(), category=category, content=content.strip(), updated_at=datetime.now(ZoneInfo('Asia/Seoul')).isoformat(timespec='microseconds'), deleted='1' if deleted else '0', revision=str(uuid4())))
        s[pending_key] = pending
    try:
        phrase_store().save(pending['item'], original['revision'] if original else None)
    except ValueError as exc:
        st.error(str(exc))
        return False
    except Exception as exc:
        st.error(f'저장 결과를 확인하지 못했습니다 ({type(exc).__name__}). 입력을 유지한 채 같은 버튼으로 다시 시도해 주세요.')
        return False
    s.pop(pending_key, None)
    s.pop('phrases', None)
    return True


def apply_phrase(field, content, mode):
    try:
        value = insert_phrase(s.get('input_' + field, s.draft[field]), content, mode)
        s['input_' + field] = value
        s.draft[field] = value
        s.phrase_notice = '상용구를 삽입했습니다. 내용을 확인해 주세요.'
    except ValueError as exc:
        s.phrase_notice = str(exc)


if page == '상용구 관리':
    st.subheader('자주 쓰는 문구를 한곳에')
    st.caption('분류별로 저장해 두고, 회의록을 작성할 때 꺼내 쓰세요.')
    if st.button('상용구 새로고침'):
        s.pop('phrases', None)
    phrases = load_phrases()
    if phrases is None:
        st.stop()
    with st.expander('＋ 새 상용구 등록', expanded=not phrases):
        with st.form('phrase_create', clear_on_submit=False):
            name = st.text_input('상용구 이름', max_chars=200)
            category = st.selectbox('분류', list(CATEGORIES), format_func=CATEGORIES.get)
            content = st.text_area('상용구 내용', height=160, max_chars=45000)
            if st.form_submit_button('상용구 등록', type='primary'):
                if save_phrase(name, category, content, operation='manager_create'):
                    s.phrase_flash = '상용구를 등록했습니다.'
                    st.rerun()
    if s.get('phrase_flash'):
        st.success(s.pop('phrase_flash'))
    search = st.text_input('상용구 검색', placeholder='이름이나 내용으로 검색')
    category_filter = st.selectbox('분류 필터', ['all', *CATEGORIES], format_func=lambda x: '전체' if x == 'all' else CATEGORIES[x])
    matches = [p for p in phrases if (category_filter == 'all' or p['category'] == category_filter) and search.casefold() in (p['name'] + ' ' + p['content']).casefold()]
    st.caption(f'{len(matches)}개 상용구')
    for phrase in matches:
        rid = phrase['revision']
        with st.expander(f"{CATEGORIES.get(phrase['category'], phrase['category'])} · {phrase['name']}"):
            with st.form('edit_' + rid):
                name = st.text_input('이름 수정', value=phrase['name'], max_chars=200)
                category = st.selectbox('분류 수정', list(CATEGORIES), index=list(CATEGORIES).index(phrase['category']))
                content = st.text_area('내용 수정', value=phrase['content'], height=160, max_chars=45000)
                if st.form_submit_button('수정 저장'):
                    if save_phrase(name, category, content, phrase, operation='edit_' + phrase['id']):
                        s.phrase_flash = '상용구를 수정했습니다.'
                        st.rerun()
            confirm = st.checkbox('이 상용구를 삭제합니다', key='delete_check_' + rid)
            if st.button('상용구 삭제', key='delete_' + rid, disabled=not confirm):
                if save_phrase(phrase['name'], phrase['category'], phrase['content'], phrase, deleted=True, operation='delete_' + phrase['id']):
                    s.phrase_flash = '상용구를 삭제했습니다.'
                    st.rerun()
    st.stop()


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
            download_record(r, 'history_' + r['id'])
    st.stop()

if s.saved:
    st.success('Google Sheets에 저장했습니다.' if connected else '체험 기록을 저장했습니다. Google Sheets에는 저장되지 않았습니다.')
    with st.container(border=True):
        show_record(s.draft)
    download_record(s.draft, 'saved_' + s.draft['id'])
    if st.button('새 회의록 작성', type='primary'):
        reset()
        st.rerun()
    st.stop()

if s.step == 0:
    with st.expander('이전 회의록에서 시작'):
        st.caption('필요한 항목을 골라 새 회의의 초안으로 불러오세요. 날짜는 오늘, 시간은 09:00–10:00으로 시작합니다.')
        if st.button('이전 회의록 새로고침'):
            try:
                s.records = store.list()
            except Exception:
                st.error('목록을 불러오지 못했습니다. 다시 시도해 주세요.')
        if not s.records:
            st.info('저장된 회의록이 생기면 여기에서 불러올 수 있습니다.')
        else:
            lookup = {r['id']: r for r in reversed(s.records)}
            selected = st.selectbox('불러올 회의록', list(lookup), index=None, placeholder='날짜 또는 회의 제목으로 검색', format_func=lambda k: f"{lookup[k]['date']} · {lookup[k]['title']} · {k[:8]}")
            if selected:
                fields = st.multiselect('불러올 항목', list(COPY_FIELDS), default=['title', 'people', 'place', 'agenda', 'notes'], format_func=COPY_FIELDS.get)
                with st.expander('선택한 회의록 미리보기'):
                    show_record(lookup[selected])
                has_draft = any(s.draft[k] for k in ['title', 'people', 'place', 'agenda', 'notes', 'decisions', 'actions', 'author'])
                approved = st.checkbox('현재 작성 중인 초안을 새 초안으로 바꿉니다') if has_draft else True
                if st.button('초안으로 불러오기', type='primary', disabled=not fields or not approved):
                    source = lookup[selected]
                    reset()
                    s.draft = new_draft(source, fields)
                    s.import_notice = '이전 회의록을 새 초안으로 불러왔습니다. 날짜·시간과 내용을 확인해 주세요.'
                    st.rerun()
    if s.get('import_notice'):
        st.success(s.pop('import_notice'))

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
        if s.get('phrase_notice'):
            st.info(s.pop('phrase_notice'))
        if st.button('상용구 목록 새로고침'):
            s.pop('phrases', None)
        phrases = load_phrases()
        capture('author', st.text_input('작성자 *', value=d['author'], max_chars=100, key='input_author').strip())
        for key, label, placeholder, height in [('agenda','안건','오늘 논의할 주요 안건',90), ('notes','논의 내용 *','안건별 주요 의견과 논의 내용을 적어 주세요.',170), ('decisions','결정 사항','합의된 결론과 결정 사항',100), ('actions','후속 업무','예: 자료 정리 / 담당자 / 10월 2일까지',100)]:
            with st.expander(CATEGORIES[key] + ' · 상용구 불러오기'):
                available = {p['id']: p for p in (phrases or []) if p['category'] == key}
                if available:
                    selected = st.selectbox('자주 쓰는 문구', list(available), index=None, format_func=lambda pid, options=available: options[pid]['name'], key='phrase_select_' + key, placeholder='상용구 선택')
                    if selected:
                        st.text(available[selected]['content'])
                        mode = st.radio('삽입 방식', ['현재 내용 뒤에 추가', '내용 교체'], key='phrase_mode_' + key, horizontal=True)
                        approved = st.checkbox('현재 내용을 선택한 상용구로 교체합니다', key='replace_ok_' + key) if mode == '내용 교체' else True
                        st.button('삽입', key='insert_' + key, disabled=not approved, on_click=apply_phrase, args=(key, available[selected]['content'], mode))
                else:
                    st.caption('이 분류에 저장된 상용구가 없습니다. 아래 내용을 작성하고 상용구로 저장해 보세요.')
            capture(key, st.text_area(label, value=d[key], placeholder=placeholder, height=height, max_chars=45000, key='input_' + key).strip())
            with st.expander(CATEGORIES[key] + ' · 상용구로 저장'):
                phrase_name = st.text_input('저장할 상용구 이름', key='phrase_name_' + key, max_chars=200, placeholder='예: 월례회의 기본 문구')
                if st.button('상용구로 저장', key='save_phrase_' + key, disabled=not d[key]):
                    if save_phrase(phrase_name, key, d[key], operation='inline_' + key):
                        s.phrase_notice = '상용구를 저장했습니다. 회의록은 마지막 단계에서 별도로 저장해 주세요.'
                        st.rerun()

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
