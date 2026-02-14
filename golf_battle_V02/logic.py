import streamlit as st
import pandas as pd
import json
from collections import Counter

# --- 상수 설정 ---
BASE_STAKE = 1000       # 타당 기본 금액
BAEPAN_MULTIPLIER = 1   # 배판 시 배율 (1배 유지)
BONUS_AMOUNT = 2000     # 언더파 보너스 금액

def init_session_state():
    if 'step' not in st.session_state:
        st.session_state.step = 1
    
    if 'players' not in st.session_state:
        st.session_state.players = []
        
    if 'game_info' not in st.session_state:
        st.session_state.game_info = {
            'current_hole': 1,
            'par': 4,
            'participants_count': 4,
            'cart_count': 1
        }
    if 'history' not in st.session_state:
        st.session_state.history = {} 

def save_setup_data(num_participants, num_carts, names, carts):
    old_players = st.session_state.players
    new_players = []
    st.session_state.game_info['participants_count'] = num_participants
    st.session_state.game_info['cart_count'] = num_carts
    
    for i in range(num_participants):
        saved_scores = {}
        if i < len(old_players):
            saved_scores = old_players[i].get('scores', {})
            
        new_players.append({
            'id': i,
            'name': names[i],
            'cart': carts[i],
            'scores': saved_scores
        })
        
    st.session_state.players = new_players

def update_scores(hole_num, par, scores_list):
    st.session_state.game_info['current_hole'] = hole_num
    st.session_state.game_info['par'] = par
    for i, score in enumerate(scores_list):
        st.session_state.players[i]['scores'][hole_num] = score

def check_baepan(scores, par, num_players):
    reasons = []
    is_baepan = False
    
    if any(s < par for s in scores):
        reasons.append("언더파 발생 (버디+)")
        is_baepan = True
        
    if any((s - par) >= 3 for s in scores):
        reasons.append("트리플보기 이상 발생")
        is_baepan = True
        
    if par == 3 and any((s - par) >= 2 for s in scores):
        reasons.append("파3 더블보기 이상 발생")
        is_baepan = True
        
    score_counts = Counter(scores)
    max_tie_count = max(score_counts.values())
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
    
    # 타당 정산
    for i in range(num_players):
        for j in range(i + 1, num_players):
            score_i = scores[i]
            score_j = scores[j]
            diff = score_j - score_i 
            amount = diff * current_stake
            money_stroke[i] += amount
            money_stroke[j] -= amount

    # 보너스 정산
    under_par_indices = [i for i, s in enumerate(scores) if s < par]
    for winner_idx in under_par_indices:
        for loser_idx in range(num_players):
            if winner_idx == loser_idx: continue
            money_bonus[winner_idx] += BONUS_AMOUNT
            money_bonus[loser_idx] -= BONUS_AMOUNT

    results = []
    for i in range(num_players):
        total_money = money_stroke[i] + money_bonus[i]
        results.append({
            '이름': names[i],
            '스코어': scores[i],
            '타당정산': money_stroke[i],
            '보너스': money_bonus[i],
            '합계': total_money
        })
    
    df = pd.DataFrame(results)
    st.session_state.history[hole_num] = df
    
    return df, is_baepan, baepan_reasons

def get_total_settlement():
    if not st.session_state.history:
        return pd.DataFrame()
    
    names = [p['name'] for p in st.session_state.players]
    total_map = {name: 0 for name in names}
    
    for hole, df in st.session_state.history.items():
        for index, row in df.iterrows():
            name = row['이름']
            money = row['합계']
            if name in total_map:
                total_map[name] += money
    
    result_list = [{'이름': k, '누적금액': v} for k, v in total_map.items()]
    return pd.DataFrame(result_list)

# --- [핵심] 최종 송금 내역 계산 함수 ---
def calculate_transfer_details():
    """누적 금액을 바탕으로 누가 누구에게 얼마를 줘야 하는지 계산"""
    df = get_total_settlement()
    if df.empty:
        return []
    
    # 데이터프레임을 딕셔너리로 변환 {이름: 금액}
    balances = dict(zip(df['이름'], df['누적금액']))
    
    # 줄 사람(Senders: 마이너스)과 받을 사람(Receivers: 플러스) 분리
    senders = []   
    receivers = [] 
    
    for name, amount in balances.items():
        if amount < 0:
            senders.append({'name': name, 'amount': abs(amount)})
        elif amount > 0:
            receivers.append({'name': name, 'amount': amount})
            
    # 큰 금액부터 처리하여 트랜잭션 최소화 시도
    senders.sort(key=lambda x: x['amount'], reverse=True)
    receivers.sort(key=lambda x: x['amount'], reverse=True)
    
    transfers = []
    s_idx = 0
    r_idx = 0
    
    # 매칭 알고리즘 (Zero-sum Game)
    while s_idx < len(senders) and r_idx < len(receivers):
        sender = senders[s_idx]
        receiver = receivers[r_idx]
        
        # 보낼 금액은 둘 중 작은 금액
        amount = min(sender['amount'], receiver['amount'])
        
        if amount > 0:
            transfers.append({
                '보내는사람': sender['name'],
                '받는사람': receiver['name'],
                '금액': amount
            })
            
        # 잔액 차감
        sender['amount'] -= amount
        receiver['amount'] -= amount
        
        # 0원이 된 쪽은 다음 사람으로 넘어감
        if sender['amount'] == 0:
            s_idx += 1
        if receiver['amount'] == 0:
            r_idx += 1
            
    return transfers

def export_game_data():
    history_serializable = {}
    if 'history' in st.session_state:
        for hole, df in st.session_state.history.items():
            history_serializable[hole] = df.to_dict('records')

    data = {
        'players': st.session_state.players,
        'game_info': st.session_state.game_info,
        'history': history_serializable,
        'step': st.session_state.step
    }
    return json.dumps(data, ensure_ascii=False, indent=4)

def load_game_data(uploaded_file):
    try:
        data = json.load(uploaded_file)
        
        st.session_state.players = data['players']
        st.session_state.game_info = data['game_info']
        st.session_state.step = data['step']
        
        st.session_state.history = {}
        if 'history' in data:
            for hole, records in data['history'].items():
                hole_num = int(hole)
                st.session_state.history[hole_num] = pd.DataFrame(records)
        return True
    except Exception as e:
        print(f"Error loading file: {e}")
        return False