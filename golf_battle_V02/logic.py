import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

# --- 상수 설정 ---
BASE_STAKE = 1000
BAEPAN_MULTIPLIER = 1
BONUS_AMOUNT = 2000

# --- 구글 시트 연결 함수 ---
def connect_to_sheet():
    """구글 시트 연결 및 워크북 객체 반환"""
    try:
        # secrets.toml에서 정보 가져오기
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        # 스트림릿 시크릿에서 JSON 정보를 dict로 가져옴
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet_url = st.secrets["sheets"]["url"]
        return client.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"구글 시트 연결 실패: {e}")
        return None

# --- 데이터 동기화 (Load) ---
def sync_data():
    """구글 시트에서 최신 데이터를 가져와 세션 상태 업데이트"""
    wb = connect_to_sheet()
    if not wb: return

    try:
        # 1. Settings 시트 읽기
        ws_settings = wb.worksheet('Settings')
        settings_data = ws_settings.get_all_records()
        
        if settings_data:
            # 첫 번째 행에 설정 정보가 있다고 가정
            row = settings_data[0]
            st.session_state.game_info['participants_count'] = int(row['participants_count'])
            st.session_state.game_info['cart_count'] = int(row['cart_count'])
            
            # 플레이어 정보 파싱
            players = []
            for i in range(row['participants_count']):
                p_key = f"player_{i}"
                c_key = f"cart_{i}"
                # 시트에 저장된 JSON 형태의 스코어를 복구하거나 별도 시트에서 가져옴
                # 여기서는 간단하게 Scores 시트에서 다시 읽는 구조로 감
                players.append({
                    'id': i,
                    'name': row.get(p_key, f"참가자{i+1}"),
                    'cart': int(row.get(c_key, 1)),
                    'scores': {} # 아래에서 채움
                })
            st.session_state.players = players
            
        # 2. Scores 시트 읽기
        ws_scores = wb.worksheet('Scores')
        score_rows = ws_scores.get_all_records()
        
        # score_rows 예: [{'hole': 1, 'par': 4, 'p0': 5, 'p1': 4...}, ...]
        for row in score_rows:
            h = int(row['hole'])
            for p_idx in range(len(st.session_state.players)):
                p_key = f"p{p_idx}"
                if p_key in row and row[p_key] != "":
                    st.session_state.players[p_idx]['scores'][h] = int(row[p_key])
                    
    except gspread.exceptions.WorksheetNotFound:
        # 시트가 없으면 생성 (초기화)
        init_sheets(wb)
    except Exception as e:
        # 아직 데이터가 없는 경우 등
        pass

def init_sheets(wb):
    """시트가 없을 때 초기 구조 생성"""
    try:
        wb.add_worksheet(title="Settings", rows=10, cols=20)
    except: pass
    try:
        wb.add_worksheet(title="Scores", rows=20, cols=20)
    except: pass
    
    ws_set = wb.worksheet('Settings')
    # 헤더 생성
    headers = ['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)]
    ws_set.update([headers])

    ws_sco = wb.worksheet('Scores')
    headers_sco = ['hole', 'par'] + [f'p{i}' for i in range(12)]
    ws_sco.update([headers_sco])


# --- 데이터 저장 (Save) ---
def save_setup_data(num_participants, num_carts, names, carts):
    # 1. 세션 업데이트
    old_players = st.session_state.players
    new_players = []
    st.session_state.game_info['participants_count'] = num_participants
    st.session_state.game_info['cart_count'] = num_carts
    
    for i in range(num_participants):
        saved_scores = {}
        if i < len(old_players):
            saved_scores = old_players[i].get('scores', {})
        new_players.append({
            'id': i, 'name': names[i], 'cart': carts[i], 'scores': saved_scores
        })
    st.session_state.players = new_players

    # 2. 구글 시트 저장
    wb = connect_to_sheet()
    if wb:
        try:
            ws = wb.worksheet('Settings')
        except:
            init_sheets(wb)
            ws = wb.worksheet('Settings')
            
        # 데이터 구성
        row_data = [num_participants, num_carts]
        for n in names: row_data.append(n)
        # 빈칸 채우기 (최대 12명)
        for _ in range(12 - len(names)): row_data.append("")
            
        for c in carts: row_data.append(c)
        for _ in range(12 - len(carts)): row_data.append("")
        
        # 2번째 줄(데이터) 업데이트
        ws.update('A2', [row_data])
        st.toast("설정이 구글 시트에 저장되었습니다!")

def update_scores(hole_num, par, scores_list):
    # 1. 세션 업데이트
    st.session_state.game_info['current_hole'] = hole_num
    st.session_state.game_info['par'] = par
    for i, score in enumerate(scores_list):
        st.session_state.players[i]['scores'][hole_num] = score

    # 2. 구글 시트 저장 (해당 홀 행 업데이트)
    wb = connect_to_sheet()
    if wb:
        try:
            ws = wb.worksheet('Scores')
        except:
            init_sheets(wb)
            ws = wb.worksheet('Scores')
        
        # 해당 홀의 데이터 찾기 또는 추가
        # cell_list = ws.find(str(hole_num), in_column=1) ... 비효율적일 수 있으므로
        # 단순히 1번홀=2행, 2번홀=3행 ... 규칙 사용
        
        row_idx = hole_num + 1
        # 데이터: [hole, par, p0_score, p1_score ...]
        row_data = [hole_num, par] + scores_list
        
        # 범위 업데이트 (A열 ~ 끝)
        ws.update(f"A{row_idx}", [row_data])
        st.toast(f"{hole_num}번 홀 점수 저장 완료! (동기화됨)")


# --- 기존 계산 로직 (유지) ---
def init_session_state():
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'players' not in st.session_state: st.session_state.players = []
    if 'game_info' not in st.session_state:
        st.session_state.game_info = {'current_hole': 1, 'par': 4, 'participants_count': 4, 'cart_count': 1}
    if 'history' not in st.session_state: st.session_state.history = {}

    # 앱 시작 시 자동 동기화 시도
    if 'is_synced' not in st.session_state:
        sync_data()
        st.session_state.is_synced = True

def check_baepan(scores, par, num_players):
    from collections import Counter
    reasons = []
    is_baepan = False
    if any(s < par for s in scores):
        reasons.append("언더파 발생")
        is_baepan = True
    if any((s - par) >= 3 for s in scores):
        reasons.append("트리플보기 이상")
        is_baepan = True
    if par == 3 and any((s - par) >= 2 for s in scores):
        reasons.append("파3 더블보기 이상")
        is_baepan = True
    score_counts = Counter(scores)
    max_tie_count = max(score_counts.values()) if score_counts else 0
    if max_tie_count > (num_players / 2):
        reasons.append(f"동타 발생 ({max_tie_count}명)")
        is_baepan = True
    return is_baepan, reasons

def calculate_settlement(hole_num):
    players = st.session_state.players
    par = st.session_state.game_info['par']
    num_players = len(players)
    scores = [p['scores'].get(hole_num, 0) for p in players]
    names = [p['name'] for p in players]
    
    is_baepan, baepan_reasons = check_baepan(scores, par, num_players)
    current_stake = BASE_STAKE * BAEPAN_MULTIPLIER if is_baepan else BASE_STAKE
    
    money_stroke = [0] * num_players
    money_bonus = [0] * num_players
    
    for i in range(num_players):
        for j in range(i + 1, num_players):
            diff = scores[j] - scores[i]
            amount = diff * current_stake
            money_stroke[i] += amount
            money_stroke[j] -= amount

    under_par_indices = [i for i, s in enumerate(scores) if s < par]
    for winner_idx in under_par_indices:
        for loser_idx in range(num_players):
            if winner_idx == loser_idx: continue
            money_bonus[winner_idx] += BONUS_AMOUNT
            money_bonus[loser_idx] -= BONUS_AMOUNT

    results = []
    for i in range(num_players):
        results.append({
            '이름': names[i],
            '스코어': scores[i],
            '타당정산': money_stroke[i],
            '보너스': money_bonus[i],
            '합계': money_stroke[i] + money_bonus[i]
        })
    
    df = pd.DataFrame(results)
    st.session_state.history[hole_num] = df
    return df, is_baepan, baepan_reasons

def get_total_settlement():
    # 전체 기록 재계산을 위해 history 다시 빌드 (동기화된 데이터 기반)
    # 현재 history는 세션에만 있으므로, players의 scores를 기반으로 다시 계산하는게 안전함
    total_map = {}
    for p in st.session_state.players:
        total_map[p['name']] = 0
        
    # 1홀부터 현재 홀까지 순회하며 재계산
    max_hole = st.session_state.game_info['current_hole']
    for h in range(1, 19):
        # 데이터가 있는 홀만 계산
        if not st.session_state.players[0]['scores'].get(h): continue
        
        # 임시 계산
        df, _, _ = calculate_settlement(h)
        for _, row in df.iterrows():
            total_map[row['이름']] += row['합계']
            
    result_list = [{'이름': k, '누적금액': v} for k, v in total_map.items()]
    return pd.DataFrame(result_list)

def calculate_transfer_details():
    df = get_total_settlement()
    if df.empty: return []
    balances = dict(zip(df['이름'], df['누적금액']))
    senders = []   
    receivers = [] 
    for name, amount in balances.items():
        if amount < 0: senders.append({'name': name, 'amount': abs(amount)})
        elif amount > 0: receivers.append({'name': name, 'amount': amount})
    senders.sort(key=lambda x: x['amount'], reverse=True)
    receivers.sort(key=lambda x: x['amount'], reverse=True)
    transfers = []
    s_idx = 0; r_idx = 0
    while s_idx < len(senders) and r_idx < len(receivers):
        sender = senders[s_idx]; receiver = receivers[r_idx]
        amount = min(sender['amount'], receiver['amount'])
        if amount > 0:
            transfers.append({'보내는사람': sender['name'], '받는사람': receiver['name'], '금액': amount})
        sender['amount'] -= amount; receiver['amount'] -= amount
        if sender['amount'] == 0: s_idx += 1
        if receiver['amount'] == 0: r_idx += 1
    return transfers

# 파일 저장/불러오기 기능은 구글 시트로 대체되었으므로 삭제하거나 유지해도 됨
# 여기서는 유지하되 더미로 남김
def export_game_data(): return "{}" 
def load_game_data(f): return False