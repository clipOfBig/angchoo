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
    try:
        ws_set = wb.worksheet('Settings')
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws_set = wb.add_worksheet(title="Settings", rows=10, cols=30)
            headers = ['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)]
            ws_set.append_row(headers)
        except Exception as e: st.error(f"Settings 생성 오류: {e}")

    try:
        ws_sco = wb.worksheet('Scores')
    except gspread.exceptions.WorksheetNotFound:
        try:
            ws_sco = wb.add_worksheet(title="Scores", rows=50, cols=20)
            headers_sco = ['hole', 'par'] + [f'p{i}' for i in range(12)]
            ws_sco.append_row(headers_sco)
        except Exception as e: st.error(f"Scores 생성 오류: {e}")

# --- 데이터 동기화 (Load) ---
def sync_data():
    wb = connect_to_sheet()
    if not wb: return

    # 1. Settings 로드
    try:
        ws_settings = wb.worksheet('Settings')
        rows = ws_settings.get_all_values()
        if len(rows) > 1:
            header = rows[0]
            data = rows[1]
            settings_map = {k: v for k, v in zip(header, data)}
            
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
                    'id': i, 'name': p_name, 
                    'cart': int(c_val) if c_val.isdigit() else 1, 
                    'scores': {}
                })
            st.session_state.players = players
    except: pass

    # 2. Scores 로드 (Par 정보 포함)
    try:
        ws_scores = wb.worksheet('Scores')
        rows = ws_scores.get_all_values()
        if len(rows) > 1:
            header = rows[0]
            p_indices = {}
            hole_idx = -1; par_idx = -1
            
            for idx, col_name in enumerate(header):
                if col_name == 'hole': hole_idx = idx
                if col_name == 'par': par_idx = idx # Par 컬럼 찾기
                if col_name.startswith('p') and col_name[1:].isdigit():
                    p_indices[int(col_name[1:])] = idx
            
            if hole_idx != -1:
                for row in rows[1:]:
                    if not row[hole_idx]: continue
                    try: h = int(row[hole_idx])
                    except: continue

                    # [핵심] Par 정보 불러와서 저장
                    if par_idx != -1 and len(row) > par_idx:
                        try:
                            par_val = int(row[par_idx])
                            st.session_state.game_info['pars'][h] = par_val
                        except: pass

                    for p_idx in range(len(st.session_state.players)):
                        if p_idx in p_indices and p_indices[p_idx] < len(row):
                            score_val = row[p_indices[p_idx]]
                            if score_val and str(score_val).strip() != "":
                                try: st.session_state.players[p_idx]['scores'][h] = int(score_val)
                                except: pass
    except Exception as e: st.error(f"점수 로드 실패: {e}")

# --- 데이터 저장 (Save) ---
def save_setup_data(num_participants, num_carts, names, carts):
    st.session_state.game_info['participants_count'] = num_participants
    st.session_state.game_info['cart_count'] = num_carts
    
    # 세션 업데이트
    new_players = []
    for i in range(num_participants):
        saved_scores = st.session_state.players[i]['scores'] if i < len(st.session_state.players) else {}
        new_players.append({'id': i, 'name': names[i], 'cart': carts[i], 'scores': saved_scores})
    st.session_state.players = new_players

    # 구글 시트 저장
    wb = connect_to_sheet()
    if wb:
        try:
            ws = wb.worksheet('Settings')
        except:
            init_sheets(wb); ws = wb.worksheet('Settings')
            
        row_data = [num_participants, num_carts] + names + [""]*(12-len(names)) + carts + [""]*(12-len(carts))
        try:
            if not ws.get_all_values():
                ws.append_row(['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)])
                ws.append_row(row_data)
            else:
                cell_list = ws.range('A2:AZ2')
                for i, val in enumerate(row_data):
                    if i < len(cell_list): cell_list[i].value = val
                ws.update_cells(cell_list)
            st.toast("설정 저장 완료!")
        except Exception as e: st.error(f"저장 오류: {e}")

def update_scores(hole_num, par, scores_list):
    # 1. 세션 업데이트 (Par 정보 저장 추가)
    st.session_state.game_info['current_hole'] = hole_num
    st.session_state.game_info['par'] = par
    st.session_state.game_info['pars'][hole_num] = par # [핵심] 홀별 Par 저장
    
    for i, score in enumerate(scores_list):
        st.session_state.players[i]['scores'][hole_num] = score

    # 2. 구글 시트 저장
    wb = connect_to_sheet()
    if wb:
        try: ws = wb.worksheet('Scores')
        except: init_sheets(wb); ws = wb.worksheet('Scores')

        try:
            all_vals = ws.get_all_values()
            if not all_vals:
                ws.append_row(['hole', 'par'] + [f'p{i}' for i in range(12)])
                all_vals = [['hole']] # 더미

            row_idx = -1
            for idx, row in enumerate(all_vals):
                if idx == 0: continue
                if len(row) > 0 and str(row[0]).strip() == str(hole_num):
                    row_idx = idx + 1; break
            
            row_data = [hole_num, par] + scores_list
            
            if row_idx > 0:
                cell_list = ws.range(f'A{row_idx}:Z{row_idx}')
                for i, val in enumerate(row_data):
                    if i < len(cell_list): cell_list[i].value = val
                ws.update_cells(cell_list)
            else:
                ws.append_row(row_data)
            st.toast(f"{hole_num}번 홀 (Par {par}) 저장 완료! ✅")
        except Exception as e: st.error(f"저장 실패: {e}")

# --- 초기화 및 정산 ---
def init_session_state():
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'players' not in st.session_state: st.session_state.players = []
    if 'game_info' not in st.session_state:
        # pars 딕셔너리 추가
        st.session_state.game_info = {
            'current_hole': 1, 'par': 4, 
            'participants_count': 4, 'cart_count': 1,
            'pars': {} # 홀별 파 정보를 담을 그릇
        }
    if 'history' not in st.session_state: st.session_state.history = {}
    if 'is_synced' not in st.session_state:
        sync_data(); st.session_state.is_synced = True

def check_baepan(scores, par, num_players):
    reasons = []; is_baepan = False
    if any(s < par for s in scores): reasons.append("언더파"); is_baepan = True
    if any((s - par) >= 3 for s in scores): reasons.append("트리플보기+"); is_baepan = True
    if par == 3 and any((s - par) >= 2 for s in scores): reasons.append("파3 더블+"); is_baepan = True
    score_counts = Counter(scores)
    if score_counts and max(score_counts.values()) > (num_players/2):
        reasons.append("과반수 동타"); is_baepan = True
    return is_baepan, reasons

def calculate_settlement(hole_num):
    players = st.session_state.players
    # 저장된 Par 정보가 있으면 쓰고, 없으면 기본값 4
    par = st.session_state.game_info['pars'].get(hole_num, 4)
    
    num_players = len(players)
    scores = [p['scores'].get(hole_num, 0) for p in players]
    names = [p['name'] for p in players]
    
    is_baepan, baepan_reasons = check_baepan(scores, par, num_players)
    current_stake = BASE_STAKE * BAEPAN_MULTIPLIER if is_baepan else BASE_STAKE
    
    money_stroke = [0] * num_players; money_bonus = [0] * num_players
    for i in range(num_players):
        for j in range(i + 1, num_players):
            diff = scores[j] - scores[i]
            amount = diff * current_stake
            money_stroke[i] += amount; money_stroke[j] -= amount
    
    under_par = [i for i, s in enumerate(scores) if s < par]
    for w in under_par:
        for l in range(num_players):
            if w == l: continue
            money_bonus[w] += BONUS_AMOUNT; money_bonus[l] -= BONUS_AMOUNT

    results = []
    for i in range(num_players):
        results.append({'이름': names[i], '스코어': scores[i], '타당정산': money_stroke[i], '보너스': money_bonus[i], '합계': money_stroke[i]+money_bonus[i]})
    
    df = pd.DataFrame(results)
    st.session_state.history[hole_num] = df
    return df, is_baepan, baepan_reasons

def get_total_settlement():
    total_map = {p['name']: 0 for p in st.session_state.players}
    for h in range(1, 19):
        has_data = False
        for p in st.session_state.players:
            if p['scores'].get(h): has_data = True; break
        if not has_data: continue
        
        df, _, _ = calculate_settlement(h)
        for _, row in df.iterrows(): total_map[row['이름']] += row['합계']
    return pd.DataFrame([{'이름': k, '누적금액': v} for k, v in total_map.items()])

def calculate_transfer_details():
    df = get_total_settlement()
    if df.empty: return []
    balances = dict(zip(df['이름'], df['누적금액']))
    senders = sorted([{'name': k, 'amount': abs(v)} for k, v in balances.items() if v < 0], key=lambda x: x['amount'], reverse=True)
    receivers = sorted([{'name': k, 'amount': v} for k, v in balances.items() if v > 0], key=lambda x: x['amount'], reverse=True)
    
    transfers = []
    s, r = 0, 0
    while s < len(senders) and r < len(receivers):
        amt = min(senders[s]['amount'], receivers[r]['amount'])
        if amt > 0: transfers.append({'보내는사람': senders[s]['name'], '받는사람': receivers[r]['name'], '금액': amt})
        senders[s]['amount'] -= amt; receivers[r]['amount'] -= amt
        if senders[s]['amount'] == 0: s += 1
        if receivers[r]['amount'] == 0: r += 1
    return transfers

def export_game_data(): return "{}"
def load_game_data(f): return False

# ... (위의 기존 코드들은 그대로 두세요) ...

# --- [추가됨] 게임 전체 초기화 (리셋) ---
def reset_all_data():
    """구글 시트와 세션 데이터를 모두 초기화"""
    # 1. 구글 시트 초기화 (내용 지우기)
    wb = connect_to_sheet()
    if wb:
        try:
            # Settings 시트 클리어
            try:
                ws_set = wb.worksheet('Settings')
                ws_set.clear() # 모든 내용 삭제
            except: pass
            
            # Scores 시트 클리어
            try:
                ws_sco = wb.worksheet('Scores')
                ws_sco.clear() # 모든 내용 삭제
            except: pass
            
            # 헤더 다시 생성 (초기 상태로 복구)
            init_sheets(wb)
            st.toast("구글 시트가 초기화되었습니다.")
        except Exception as e:
            st.error(f"시트 초기화 실패: {e}")

    # 2. 세션 상태 초기화
    st.session_state.players = []
    st.session_state.game_info = {
        'current_hole': 1, 'par': 4, 
        'participants_count': 4, 'cart_count': 1,
        'pars': {}
    }
    st.session_state.history = {}
    st.session_state.step = 1
    
    # 리셋 확인창 상태 해제
    st.session_state.show_reset_confirm = False