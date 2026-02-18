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
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet_url = st.secrets["sheets"]["url"]
        return client.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"구글 시트 연결 실패: {e}")
        return None

# --- [수정됨] 시트 초기화 함수 (에러 방지 강화) ---
def init_sheets(wb):
    """시트가 없을 때 초기 구조 생성 (권한 에러 확인용)"""
    
    # 1. Settings 시트 확인 및 생성
    try:
        ws_set = wb.worksheet('Settings')
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws_set = wb.add_worksheet(title="Settings", rows=10, cols=30)
            # 헤더 초기화
            headers = ['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)]
            ws_set.append_row(headers)
        except Exception as e:
            st.error(f"🚨 'Settings' 시트 생성 실패! 구글 시트 공유 설정이 '편집자(Editor)'인지 확인하세요.\n에러 내용: {e}")
            return None

    # 2. Scores 시트 확인 및 생성
    try:
        ws_sco = wb.worksheet('Scores')
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws_sco = wb.add_worksheet(title="Scores", rows=50, cols=20)
            # 헤더 초기화
            headers_sco = ['hole', 'par'] + [f'p{i}' for i in range(12)]
            ws_sco.append_row(headers_sco)
        except Exception as e:
            st.error(f"🚨 'Scores' 시트 생성 실패! 권한을 확인하세요.\n에러 내용: {e}")
            return None

# --- 데이터 동기화 (Load) ---
def sync_data():
    """구글 시트에서 최신 데이터를 가져와 세션 상태 업데이트"""
    wb = connect_to_sheet()
    if not wb: return

    try:
        # 시트 존재 여부 확인 및 초기화
        try:
            ws_settings = wb.worksheet('Settings')
        except gspread.exceptions.WorksheetNotFound:
            init_sheets(wb)
            # 초기화 후 다시 시도
            try:
                ws_settings = wb.worksheet('Settings')
            except:
                return # 여전히 없으면 중단 (권한 문제 등)

        settings_data = ws_settings.get_all_records()
        
        if settings_data:
            row = settings_data[0]
            st.session_state.game_info['participants_count'] = int(row['participants_count'])
            st.session_state.game_info['cart_count'] = int(row['cart_count'])
            
            players = []
            for i in range(row['participants_count']):
                p_key = f"player_{i}"
                c_key = f"cart_{i}"
                players.append({
                    'id': i,
                    'name': row.get(p_key, f"참가자{i+1}"),
                    'cart': int(row.get(c_key, 1)),
                    'scores': {}
                })
            st.session_state.players = players
            
        # Scores 읽기
        try:
            ws_scores = wb.worksheet('Scores')
            score_rows = ws_scores.get_all_records()
            
            for row in score_rows:
                h = int(row['hole'])
                for p_idx in range(len(st.session_state.players)):
                    p_key = f"p{p_idx}"
                    # 빈 문자열이나 키가 없는 경우 제외
                    if p_key in row and row[p_key] != "":
                        st.session_state.players[p_idx]['scores'][h] = int(row[p_key])
        except gspread.exceptions.WorksheetNotFound:
            pass # Scores 시트가 아직 없으면 패스
            
    except Exception as e:
        # st.error(f"동기화 중 오류: {e}") # 디버깅용
        pass

# --- 데이터 저장 (Save) ---
def save_setup_data(num_participants, num_carts, names, carts):
    # 세션 업데이트
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

    # 구글 시트 저장
    wb = connect_to_sheet()
    if wb:
        # 시트가 없으면 생성 시도
        init_sheets(wb)
        try:
            ws = wb.worksheet('Settings')
            
            row_data = [num_participants, num_carts]
            for n in names: row_data.append(n)
            for _ in range(12 - len(names)): row_data.append("")
            for c in carts: row_data.append(c)
            for _ in range(12 - len(carts)): row_data.append("")
            
            # 헤더가 없으면 추가, 있으면 2번째 줄 업데이트
            if not ws.get_all_values():
                headers = ['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)]
                ws.append_row(headers)
                ws.append_row(row_data)
            else:
                # 2번째 줄 업데이트 (A2부터 시작)
                # gspread 버전에 따라 update 문법이 다를 수 있음. range 사용이 안전.
                cell_list = ws.range(f'A2:AZ2') # 넉넉하게 잡음
                for i, val in enumerate(row_data):
                    if i < len(cell_list):
                        cell_list[i].value = val
                ws.update_cells(cell_list)
                
            st.toast("설정 저장 완료!")
        except Exception as e:
            st.error(f"저장 실패: {e}")

def update_scores(hole_num, par, scores_list):
    # 세션 업데이트
    st.session_state.game_info['current_hole'] = hole_num
    st.session_state.game_info['par'] = par
    for i, score in enumerate(scores_list):
        st.session_state.players[i]['scores'][hole_num] = score

    # 구글 시트 저장
    wb = connect_to_sheet()
    if wb:
        init_sheets(wb)
        try:
            ws = wb.worksheet('Scores')
            if not ws.get_all_values():
                headers_sco = ['hole', 'par'] + [f'p{i}' for i in range(12)]
                ws.append_row(headers_sco)
            
            # 해당 홀 데이터 찾기 (홀 번호는 유니크하다고 가정)
            # 전체 데이터를 가져와서 해당 홀이 있는지 확인
            all_vals = ws.get_all_values()
            row_idx = -1
            
            # 1번째 줄은 헤더이므로 2번째 줄부터 확인
            for idx, row in enumerate(all_vals):
                if idx == 0: continue
                if row and str(row[0]) == str(hole_num):
                    row_idx = idx + 1 # 1-based index
                    break
            
            row_data = [hole_num, par] + scores_list
            
            if row_idx > 0:
                # 기존 행 업데이트
                cell_list = ws.range(f'A{row_idx}:Z{row_idx}')
                for i, val in enumerate(row_data):
                    if i < len(cell_list):
                        cell_list[i].value = val
                ws.update_cells(cell_list)
            else:
                # 새 행 추가
                ws.append_row(row_data)
                
            st.toast(f"{hole_num}번 홀 저장 완료!")
        except Exception as e:
            st.error(f"점수 저장 실패: {e}")

# --- 기존 로직 (유지) ---
def init_session_state():
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'players' not in st.session_state: st.session_state.players = []
    if 'game_info' not in st.session_state:
        st.session_state.game_info = {'current_hole': 1, 'par': 4, 'participants_count': 4, 'cart_count': 1}
    if 'history' not in st.session_state: st.session_state.history = {}

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
    total_map = {}
    if not st.session_state.players: return pd.DataFrame()
    
    for p in st.session_state.players:
        total_map[p['name']] = 0
        
    max_hole = st.session_state.game_info['current_hole']
    for h in range(1, 19):
        # 데이터 존재 여부 확인
        has_data = False
        for p in st.session_state.players:
             if h in p['scores']:
                 has_data = True
                 break
        if not has_data: continue
        
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

def export_game_data(): return "{}" 
def load_game_data(f): return False