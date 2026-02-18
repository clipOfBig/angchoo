import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
from collections import Counter

# --- 상수 설정 ---
BASE_STAKE = 1000
BAEPAN_MULTIPLIER = 1
BONUS_AMOUNT = 2000

# --- 구글 시트 연결 함수 ---
def connect_to_sheet():
    """구글 시트 연결 및 워크북 객체 반환"""
    try:
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet_url = st.secrets["sheets"]["url"]
        return client.open_by_url(sheet_url)
    except Exception as e:
        st.error(f"❌ 구글 시트 연결 실패: {e}")
        return None

# --- 시트 초기화 함수 ---
def init_sheets(wb):
    """시트가 없을 때 초기 구조 생성"""
    # 1. Settings 시트
    try:
        ws_set = wb.worksheet('Settings')
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws_set = wb.add_worksheet(title="Settings", rows=10, cols=30)
            headers = ['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)]
            ws_set.append_row(headers)
        except Exception as e:
            st.error(f"Settings 시트 생성 오류: {e}")

    # 2. Scores 시트
    try:
        ws_sco = wb.worksheet('Scores')
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws_sco = wb.add_worksheet(title="Scores", rows=50, cols=20)
            headers_sco = ['hole', 'par'] + [f'p{i}' for i in range(12)]
            ws_sco.append_row(headers_sco)
        except Exception as e:
            st.error(f"Scores 시트 생성 오류: {e}")

# --- [핵심 수정] 데이터 동기화 (Load) ---
def sync_data():
    """구글 시트에서 최신 데이터를 가져와 세션 상태 업데이트 (get_all_values 사용)"""
    wb = connect_to_sheet()
    if not wb: return

    # 1. Settings 시트 읽기
    try:
        ws_settings = wb.worksheet('Settings')
        # get_all_records 대신 get_all_values 사용 (더 안전함)
        rows = ws_settings.get_all_values()
        
        if len(rows) > 1: # 헤더 제외 데이터가 있을 때
            header = rows[0]
            data = rows[1] # 첫 번째 데이터 행만 사용
            
            # 딕셔너리로 변환
            settings_map = {k: v for k, v in zip(header, data)}
            
            # 데이터 적용
            if settings_map.get('participants_count'):
                st.session_state.game_info['participants_count'] = int(settings_map['participants_count'])
            if settings_map.get('cart_count'):
                st.session_state.game_info['cart_count'] = int(settings_map['cart_count'])
            
            players = []
            p_count = st.session_state.game_info['participants_count']
            
            for i in range(p_count):
                p_name = settings_map.get(f"player_{i}", f"참가자{i+1}")
                c_val = settings_map.get(f"cart_{i}", "1")
                
                players.append({
                    'id': i,
                    'name': p_name,
                    'cart': int(c_val) if c_val.isdigit() else 1,
                    'scores': {} # 점수는 아래에서 채움
                })
            st.session_state.players = players
            
    except gspread.exceptions.WorksheetNotFound:
        init_sheets(wb)
    except Exception as e:
        st.error(f"⚠️ 설정 불러오기 실패: {e}")

    # 2. Scores 시트 읽기
    try:
        ws_scores = wb.worksheet('Scores')
        rows = ws_scores.get_all_values()
        
        if len(rows) > 1:
            header = rows[0]
            # 헤더에서 p0, p1... 인덱스 찾기
            p_indices = {}
            hole_idx = -1
            
            for idx, col_name in enumerate(header):
                if col_name == 'hole': hole_idx = idx
                if col_name.startswith('p') and col_name[1:].isdigit():
                    p_id = int(col_name[1:])
                    p_indices[p_id] = idx
            
            if hole_idx != -1:
                for row in rows[1:]: # 데이터 줄 반복
                    if not row[hole_idx]: continue # 홀 번호 없으면 패스
                    
                    try:
                        h = int(row[hole_idx])
                    except:
                        continue # 홀 번호가 숫자가 아니면 패스

                    for p_idx in range(len(st.session_state.players)):
                        # 해당 플레이어의 컬럼 인덱스가 시트에 있다면
                        if p_idx in p_indices and p_indices[p_idx] < len(row):
                            score_val = row[p_indices[p_idx]]
                            if score_val and str(score_val).strip() != "":
                                try:
                                    st.session_state.players[p_idx]['scores'][h] = int(score_val)
                                except: pass
                                
    except Exception as e:
        st.error(f"⚠️ 점수 불러오기 실패: {e}")

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
        try:
            ws = wb.worksheet('Settings')
        except:
            init_sheets(wb)
            ws = wb.worksheet('Settings')
            
        row_data = [num_participants, num_carts]
        for n in names: row_data.append(n)
        for _ in range(12 - len(names)): row_data.append("")
        for c in carts: row_data.append(c)
        for _ in range(12 - len(carts)): row_data.append("")
        
        # 안전하게 값 업데이트
        try:
            if not ws.get_all_values():
                headers = ['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)]
                ws.append_row(headers)
                ws.append_row(row_data)
            else:
                # 범위 업데이트 (A2 시작)
                end_col_char = chr(65 + len(row_data) - 1) # 대략적인 컬럼 계산
                if len(row_data) > 26: end_col_char = 'AZ' 
                
                # 안전하게 한 셀씩 업데이트 하거나 범위 지정
                # range 사용이 가장 확실함
                cell_list = ws.range(f'A2:AZ2') 
                for i, val in enumerate(row_data):
                    if i < len(cell_list):
                        cell_list[i].value = val
                ws.update_cells(cell_list)
                
            st.toast("설정 저장 완료!")
        except Exception as e:
            st.error(f"설정 저장 중 오류: {e}")

def update_scores(hole_num, par, scores_list):
    # 세션 업데이트
    st.session_state.game_info['current_hole'] = hole_num
    st.session_state.game_info['par'] = par
    for i, score in enumerate(scores_list):
        st.session_state.players[i]['scores'][hole_num] = score

    # 구글 시트 저장
    wb = connect_to_sheet()
    if wb:
        try:
            ws = wb.worksheet('Scores')
        except:
            init_sheets(wb)
            ws = wb.worksheet('Scores')

        try:
            all_vals = ws.get_all_values()
            
            # 헤더가 없으면 생성
            if not all_vals:
                headers_sco = ['hole', 'par'] + [f'p{i}' for i in range(12)]
                ws.append_row(headers_sco)
                all_vals = [headers_sco]

            row_idx = -1
            # 홀 번호 찾기 (첫번째 컬럼)
            for idx, row in enumerate(all_vals):
                if idx == 0: continue
                # 문자열로 비교하여 안전성 확보
                if len(row) > 0 and str(row[0]).strip() == str(hole_num):
                    row_idx = idx + 1 # 1-based index for gspread
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

# --- 정산 로직 (기존 유지) ---
def init_session_state():
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'players' not in st.session_state: st.session_state.players = []
    if 'game_info' not in st.session_state:
        st.session_state.game_info = {'current_hole': 1, 'par': 4, 'participants_count': 4, 'cart_count': 1}
    if 'history' not in st.session_state: st.session_state.history = {}
    
    # 앱 시작 시 자동 동기화
    if 'is_synced' not in st.session_state:
        sync_data()
        st.session_state.is_synced = True

def check_baepan(scores, par, num_players):
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
    for p in st.session_state.players: total_map[p['name']] = 0
    for h in range(1, 19):
        # 데이터 있는지 체크
        has_data = False
        for p in st.session_state.players:
            if p['scores'].get(h): has_data = True; break
        if not has_data: continue
        
        df, _, _ = calculate_settlement(h)
        for _, row in df.iterrows(): total_map[row['이름']] += row['합계']
    result_list = [{'이름': k, '누적금액': v} for k, v in total_map.items()]
    return pd.DataFrame(result_list)

def calculate_transfer_details():
    df = get_total_settlement()
    if df.empty: return []
    balances = dict(zip(df['이름'], df['누적금액']))
    senders = []; receivers = []
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