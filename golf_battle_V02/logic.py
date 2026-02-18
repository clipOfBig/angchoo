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

# --- 구글 시트 연결 ---
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

# --- 시트 초기화 ---
def init_sheets(wb):
    # Settings 시트 확인
    try: wb.worksheet('Settings')
    except:
        try:
            ws = wb.add_worksheet('Settings', 10, 30)
            ws.append_row(['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)])
        except: pass
    
    # Scores 시트 확인
    try: wb.worksheet('Scores')
    except:
        try:
            ws = wb.add_worksheet('Scores', 50, 20)
            ws.append_row(['hole', 'par'] + [f'p{i}' for i in range(12)])
        except: pass

# --- [핵심 수정] 데이터 동기화 (자동 복구 기능 추가) ---
def sync_data():
    wb = connect_to_sheet()
    if not wb: return

    # 1. Settings 로드
    try:
        ws_settings = wb.worksheet('Settings')
        rows = ws_settings.get_all_values()
        
        # [자동 복구] Settings 헤더 체크
        if rows and str(rows[0][0]).strip() != 'participants_count':
             header_row = ['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)]
             ws_settings.insert_row(header_row, index=1)
             rows = ws_settings.get_all_values() # 다시 읽기
             st.toast("Settings 시트 헤더 자동 복구 완료 🛠️")

        if len(rows) > 1:
            header = rows[0]; data = rows[1]
            # 안전하게 매핑 (데이터 길이가 짧을 경우 대비)
            settings_map = {}
            for i, h in enumerate(header):
                if i < len(data): settings_map[h] = data[i]
            
            if settings_map.get('participants_count'):
                st.session_state.game_info['participants_count'] = int(settings_map['participants_count'])
            if settings_map.get('cart_count'):
                st.session_state.game_info['cart_count'] = int(settings_map['cart_count'])
            
            players = []
            p_count = st.session_state.game_info.get('participants_count', 4)
            for i in range(p_count):
                p_name = settings_map.get(f"player_{i}", f"참가자{i+1}")
                c_val = str(settings_map.get(f"cart_{i}", "1"))
                players.append({'id': i, 'name': p_name, 'cart': int(c_val) if c_val.isdigit() else 1, 'scores': {}})
            st.session_state.players = players
    except Exception as e: pass

    # 2. Scores 로드
    try:
        ws_scores = wb.worksheet('Scores')
        rows = ws_scores.get_all_values()
        
        # [자동 복구] Scores 헤더 체크 (첫 칸이 'hole'이 아니면 복구)
        if rows and len(rows) > 0 and str(rows[0][0]).lower().strip() != 'hole':
             header_row = ['hole', 'par'] + [f'p{i}' for i in range(12)]
             ws_scores.insert_row(header_row, index=1)
             rows = ws_scores.get_all_values() # 다시 읽기
             st.toast("Scores 시트 헤더 자동 복구 완료 🛠️")

        if len(rows) > 1:
            header = rows[0]
            p_indices = {}; hole_idx = -1; par_idx = -1
            for idx, col in enumerate(header):
                if col == 'hole': hole_idx = idx
                if col == 'par': par_idx = idx
                if col.startswith('p') and col[1:].isdigit(): p_indices[int(col[1:])] = idx
            
            if hole_idx != -1:
                # 데이터 읽기
                for row in rows[1:]:
                    if len(row) <= hole_idx or not row[hole_idx]: continue
                    try: h = int(row[hole_idx])
                    except: continue
                    
                    if par_idx != -1 and len(row) > par_idx:
                        try: st.session_state.game_info['pars'][h] = int(row[par_idx])
                        except: pass

                    for p_idx in range(len(st.session_state.players)):
                        if p_idx in p_indices and p_indices[p_idx] < len(row):
                            val = row[p_indices[p_idx]]
                            if val and str(val).strip():
                                try: st.session_state.players[p_idx]['scores'][h] = int(val)
                                except: pass
        
        # [화면 강제 갱신] 캐시 삭제
        keys_to_drop = []
        for key in st.session_state.keys():
            if key.startswith("score_rel_") or key.startswith("par_select_"):
                keys_to_drop.append(key)
        for key in keys_to_drop:
            del st.session_state[key]
            
    except Exception as e: st.error(f"점수 동기화 중 오류: {e}")

# --- 저장 ---
def save_setup_data(num_participants, num_carts, names, carts):
    st.session_state.game_info['participants_count'] = num_participants
    st.session_state.game_info['cart_count'] = num_carts
    new_players = []
    for i in range(num_participants):
        saved = st.session_state.players[i]['scores'] if i < len(st.session_state.players) else {}
        new_players.append({'id': i, 'name': names[i], 'cart': carts[i], 'scores': saved})
    st.session_state.players = new_players

    wb = connect_to_sheet()
    if wb:
        try: ws = wb.worksheet('Settings')
        except: init_sheets(wb); ws = wb.worksheet('Settings')
        
        # 헤더 체크 및 삽입
        rows = ws.get_all_values()
        if not rows or (rows and str(rows[0][0]).strip() != 'participants_count'):
            ws.insert_row(['participants_count', 'cart_count'] + [f'player_{i}' for i in range(12)] + [f'cart_{i}' for i in range(12)], index=1)
            
        data = [num_participants, num_carts] + names + [""]*(12-len(names)) + carts + [""]*(12-len(carts))
        try:
            # 2번째 줄(A2) 업데이트
            cell_list = ws.range('A2:AZ2')
            for i, v in enumerate(data): 
                if i < len(cell_list): cell_list[i].value = v
            ws.update_cells(cell_list)
            st.toast("설정 저장 완료")
        except: pass

def update_scores(hole_num, par, scores_list):
    st.session_state.game_info['current_hole'] = hole_num
    st.session_state.game_info['par'] = par
    st.session_state.game_info['pars'][hole_num] = par
    for i, s in enumerate(scores_list): st.session_state.players[i]['scores'][hole_num] = s

    wb = connect_to_sheet()
    if wb:
        try: ws = wb.worksheet('Scores')
        except: init_sheets(wb); ws = wb.worksheet('Scores')
        
        try:
            all_vals = ws.get_all_values()
            # 헤더가 없으면 삽입
            if not all_vals or (all_vals and str(all_vals[0][0]).lower().strip() != 'hole'):
                ws.insert_row(['hole', 'par'] + [f'p{i}' for i in range(12)], index=1)
                all_vals = ws.get_all_values() # 다시 읽기

            row_idx = -1
            for i, r in enumerate(all_vals):
                if i==0: continue # 헤더 건너뛰기
                if len(r)>0 and str(r[0])==str(hole_num): row_idx=i+1; break
            
            data = [hole_num, par] + scores_list
            if row_idx > 0:
                cells = ws.range(f'A{row_idx}:Z{row_idx}')
                for i, v in enumerate(data): 
                    if i < len(cells): cells[i].value = v
                ws.update_cells(cells)
            else: ws.append_row(data)
            st.toast(f"{hole_num}번 홀 저장 완료")
        except Exception as e: st.error(f"저장 실패: {e}")

# --- 리셋 ---
def reset_all_data():
    wb = connect_to_sheet()
    if wb:
        try: 
            wb.worksheet('Settings').clear()
            wb.worksheet('Scores').clear()
            init_sheets(wb)
        except: pass
    st.session_state.players = []
    st.session_state.game_info = {'current_hole': 1, 'par': 4, 'participants_count': 4, 'cart_count': 1, 'pars': {}}
    st.session_state.history = {}
    st.session_state.step = 1
    st.session_state.show_reset_confirm = False

# --- 계산/초기화 (유지) ---
def init_session_state():
    if 'step' not in st.session_state: st.session_state.step = 1
    if 'players' not in st.session_state: st.session_state.players = []
    if 'game_info' not in st.session_state: st.session_state.game_info = {'current_hole': 1, 'par': 4, 'participants_count': 4, 'cart_count': 1, 'pars': {}}
    if 'history' not in st.session_state: st.session_state.history = {}
    if 'is_synced' not in st.session_state: sync_data(); st.session_state.is_synced = True

def check_baepan(scores, par, num_players):
    reasons = []; is_baepan = False
    if any(s < par for s in scores): reasons.append("언더파"); is_baepan = True
    if any((s - par) >= 3 for s in scores): reasons.append("트리플보기+"); is_baepan = True
    if par == 3 and any((s - par) >= 2 for s in scores): reasons.append("파3 더블+"); is_baepan = True
    cnt = Counter(scores)
    if cnt and max(cnt.values()) > (num_players/2): reasons.append("과반수 동타"); is_baepan = True
    return is_baepan, reasons

def calculate_settlement(hole_num):
    players = st.session_state.players
    par = st.session_state.game_info['pars'].get(hole_num, 4)
    num_players = len(players); scores = [p['scores'].get(hole_num, 0) for p in players]
    names = [p['name'] for p in players]
    
    is_baepan, baepan_reasons = check_baepan(scores, par, num_players)
    stake = BASE_STAKE * BAEPAN_MULTIPLIER if is_baepan else BASE_STAKE
    
    m_str = [0]*num_players; m_bon = [0]*num_players
    for i in range(num_players):
        for j in range(i+1, num_players):
            amt = (scores[j]-scores[i])*stake
            m_str[i]+=amt; m_str[j]-=amt
            
    under = [i for i, s in enumerate(scores) if s < par]
    for w in under:
        for l in range(num_players):
            if w!=l: m_bon[w]+=BONUS_AMOUNT; m_bon[l]-=BONUS_AMOUNT

    res = []
    for i in range(num_players):
        res.append({'이름': names[i], '스코어': scores[i], '타당정산': m_str[i], '보너스': m_bon[i], '합계': m_str[i]+m_bon[i]})
    
    df = pd.DataFrame(res)
    st.session_state.history[hole_num] = df
    return df, is_baepan, baepan_reasons

def get_total_settlement():
    tot = {p['name']: 0 for p in st.session_state.players}
    for h in range(1, 19):
        if not any(p['scores'].get(h) for p in st.session_state.players): continue
        df, _, _ = calculate_settlement(h)
        for _, r in df.iterrows(): tot[r['이름']] += r['합계']
    return pd.DataFrame([{'이름': k, '누적금액': v} for k, v in tot.items()])

def calculate_transfer_details():
    df = get_total_settlement()
    if df.empty: return []
    bal = dict(zip(df['이름'], df['누적금액']))
    snd = sorted([{'name': k, 'amount': abs(v)} for k, v in bal.items() if v < 0], key=lambda x: x['amount'], reverse=True)
    rcv = sorted([{'name': k, 'amount': v} for k, v in bal.items() if v > 0], key=lambda x: x['amount'], reverse=True)
    
    res = []; s=0; r=0
    while s < len(snd) and r < len(rcv):
        amt = min(snd[s]['amount'], rcv[r]['amount'])
        if amt > 0: res.append({'보내는사람': snd[s]['name'], '받는사람': rcv[r]['name'], '금액': amt})
        snd[s]['amount'] -= amt; rcv[r]['amount'] -= amt
        if snd[s]['amount'] == 0: s+=1
        if rcv[r]['amount'] == 0: r+=1
    return res

def export_game_data(): return "{}"
def load_game_data(f): return False