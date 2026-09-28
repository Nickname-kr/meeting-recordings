"""Reusable meeting drafts and phrase text transformations."""
from copy import deepcopy
from datetime import datetime, time
from zoneinfo import ZoneInfo
from uuid import uuid4

COPY_FIELDS = {'title': '회의 제목', 'people': '참석자', 'place': '장소', 'agenda': '안건', 'notes': '논의 내용', 'decisions': '결정 사항', 'actions': '후속 업무'}


def new_draft(source=None, fields=()):
    draft = dict(id=str(uuid4()), title='', date=datetime.now(ZoneInfo('Asia/Seoul')).date(), start=time(9), end=time(10), people=[], place=None, agenda='', notes='', decisions='', actions='', author='')
    if source:
        for key in fields:
            if key in COPY_FIELDS:
                draft[key] = deepcopy(source.get(key, draft[key]))
    return draft


def insert_phrase(current, content, mode):
    result = '\n\n'.join(v for v in [current.rstrip(), content.strip()] if v) if mode == '현재 내용 뒤에 추가' else content.strip()
    if len(result) > 45000:
        raise ValueError('삽입 후 내용이 45,000자를 초과합니다. 내용을 줄인 후 다시 시도해 주세요.')
    return result
