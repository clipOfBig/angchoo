import streamlit as st
import pandas as pd

# ==========================================
# [Model] 데이터 및 게임 로직
# ==========================================
class Player:
    def __init__(self, name):
        self.name = name
        self.money = 0
        self.scores = []       
        self.pnl_history = []  

class GolfGame:
    def __init__(self):
        self.players = []
        self.current_hole = 1
        self.total_holes = 18
        self.current_par = 4

    def add_player(self, name):
        self.players.append(Player(name))

    def calculate_hole(self, scores):
        logs = []
        min_score = min(scores.values())
        winners = [p for p, s in scores.items() if s == min_score]
        
        is_baepan = False
        reasons = []

        if any(s < self.current_par for s in scores.values()):
            is_baepan = True
            reasons.append("언더파 발생")
        if any(s >= self.current_par + 3 for s in scores.values()):
            is_baepan = True
            reasons.append("트리플보기 이상")
        if self.current_par == 3 and any(s >= 5 for s in scores.values()):
            is_baepan = True
            reasons.append("파3 더블보기 이상")

        score_counts = {}
        for s in scores.values():
            score_counts[s] = score_counts.get(s, 0) + 1
        max_tie_count = max(score_counts.values())
        if max_tie_count > (len(self.players) / 2):
            is_baepan = True
            reasons.append(f"동타 인원 과반({max_tie_count}명)")

        round_ledger = {p: 0 for p in self.players}

        if is_baepan:
            logs.append(f"🚨 [배판 성립] {', '.join(reasons)}")
            for p, score in scores.items():
                if p not in winners:
                    diff = score - min_score
                    amount_per_winner = diff * 1000 
                    for w in winners:
                        round_ledger[p] -= amount_per_winner
                        round_ledger[w] += amount_per_winner
        else:
            logs.append("ℹ️ 배판 조건 없음")

        for p, score in scores.items():
            if score < self.current_par:
                bonus_amt = 2000
                for other in self.players:
                    if other != p:
                        round_ledger[other] -= bonus_amt
                        round_ledger[p] += bonus_amt

        transactions = self.simplify_transactions(round_ledger)
        return round_ledger, transactions, logs

    def simplify_transactions(self, ledger):
        receivers = []
        senders = []
        for p, amount in ledger.items():
            if amount > 0: receivers.append({'player': p, 'amount': amount})
            elif amount < 0: senders.append({'player': p, 'amount': -amount})
        receivers.sort(key=lambda x: x['amount'], reverse=True)
        senders.sort(key=lambda x: x['amount'], reverse=True)
        trans_list = []
        r_idx, s_idx = 0, 0
        while r_idx < len(receivers) and s_idx < len(senders):
            receiver, sender = receivers[r_idx], senders[s_idx]
            amount = min(receiver['amount'], sender['amount'])
            if amount > 0: trans_list.append(f"**{sender['player'].name}** ➡️ **{receiver['player'].name}**: `{amount:,}원`")
            receiver['amount'] -= amount
            sender['amount'] -= amount
            if receiver['amount'] == 0: r_idx += 1
            if sender['amount'] == 0: s_idx += 1
        return trans_list

    def commit_round(self, round_ledger, scores):
        for p, amount in round_ledger.items():
            p.money += amount
            p.scores.append(scores[p])
            p.pnl_history.append(amount)
        self.current_hole += 1

    def get_settlement_guide(self, current_ledger=None):
        temp_ledger = {p: p.money for p in self.players}
        if current_ledger:
            for p, amt in current_ledger.items(): temp_ledger[p] += amt
        return self.simplify_transactions(temp_ledger)
    
    def generate_html_report(self):
        html = """<style>table { width: 100%; border-collapse: collapse; font-size: 13px; text-align: center; } 
        th, td { border: 1px solid #ddd; padding: 2px 4px; } th { background-color: #f8f9fa; } 
        .pos { color: blue; font-weight: bold; } .neg { color: red; font-weight: bold; }</style>"""
        html += "<h5>⛳️ 스코어 기록</h5><div style='overflow-x:auto;'><table><thead><tr><th>이름</th>"
        max_holes = len(self.players[0].scores) if self.players else 0
        for i in range(max_holes): html += f"<th>{i+1}H</th>"
        html += "<th>Total</th></tr></thead><tbody>"
        for p in self.players:
            html += f"<tr><td>{p.name}</td>"
            for s in p.scores: html += f"<td>{s}</td>"
            html += f"<td>{sum(p.scores)}</td></tr>"
        html += "</tbody></table></div>"
        return html

# ==========================================
# [Streamlit View] UI 구성 (압축 및 소형화 모드)
# ==========================================
st.set_page_config(page_title="골프 정산", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
        /* 1. 전체 글자 크기 10% 축소 (18px -> 16.2px) */
        html, body, [class*="css"] { font-size: 16.2px !important; }
        
        .block-container { 
            padding-top: 1rem !important; 
            padding-bottom: 1rem !important; 
            padding-left: 0.5rem !important; 
            padding-right: 0.5rem !important;
            max-width: 480px !important; margin: auto;
        }
        
        /* 2. 줄 간격 및 요소 간격 15% 이상 압축 */
        div[data-testid="stVerticalBlock"] { gap: 0.35rem !important; }
        div[data-testid="stHorizontalBlock"] { gap: 0.18rem !important; }
        
        h1 { font-size: 1.6rem !important; margin-bottom: 0.4rem !important; }
        p, div, label, caption { line-height: 1.05 !important; margin-bottom: 0px !important; }

        /* 입력 위젯 크기 조절 */
        .stNumberInput input { height: 2.1rem !important; font-size: 16px !important; }
        button[kind="secondary"] { height: 2.1rem !important; width: 2.1rem !important; }
        
        .stTextInput input, .stSelectbox div[data-baseweb="select"] div {
            height: 2.1rem !important; min-height: 2.1rem !important; font-size: 16px !important;
        }
        
        .stButton button { 
            height: 2.6rem !important; font-size: 16.2px !important; font-weight: bold !important;
            border-radius: 6px; margin-top: 2px !important;
        }

        /* 테이블 및 기타 요소 압축 */
        [data-testid="stTable"] td, [data-testid="stDataFrame"] td { padding: 1.5px !important; line-height: 1.0 !important; }
        div[data-testid="stNotification"] { padding: 0.25rem 0.5rem !important; min-height: auto !important; }
        div[data-testid="stExpander"] { margin-bottom: 0px !important; }
    </style>
""", unsafe_allow_html=True)

if 'game' not in st.session_state:
    st.session_state.game = None
    st.session_state.step = 'setup' 
if 'temp_ledger' not in st.session_state: st.session_state.temp_ledger = None

def main():
    if st.session_state.step == 'setup':
        st.title("⛳️ 골프 정산")
        num_players = st.selectbox("인원", list(range(2, 13)), index=2)
        with st.form("setup_form"):
            input_names = []
            cols = st.columns(2)
            default_names = ["홍길동", "김프로", "박싱글", "최버디", "이장타", "정퍼터", "강아이언", "윤우드", "송어프로", "임샌드", "한이글", "오홀인원"]
            for i in range(num_players):
                val = default_names[i] if i < len(default_names) else f"선수{i+1}"
                with cols[i % 2]: input_names.append(st.text_input(f"p{i}", value=val, key=f"p_input_{i}", label_visibility="collapsed"))
            total_h = st.number_input("홀수", 1, 36, 18)
            if st.form_submit_button("시작", type="primary"):
                names = [n.strip() for n in input_names if n.strip()]
                if len(names) < 2: st.error("2명 이상 필요")
                else:
                    st.session_state.game = GolfGame()
                    st.session_state.game.total_holes = total_h
                    for n in names: st.session_state.game.add_player(n)
                    st.session_state.step = 'playing'
                    st.rerun()

    elif st.session_state.step == 'playing':
        game = st.session_state.game
        st.info(f"🚩 **Hole {game.current_hole}** / {game.total_holes}")
        tab1, tab2 = st.tabs(["📝 입력", "📊 현황"])
        with tab1:
            col_par, _ = st.columns([1, 2])
            with col_par: game.current_par = st.selectbox("Par", [3, 4, 5, 6], index=1)
            with st.form("score_form"):
                input_scores = {}
                for p in game.players:
                    c_n, c_i = st.columns([0.4, 0.6])
                    c_n.markdown(f"<div style='margin-top: 7px; font-weight: bold; font-size: 16px;'>{p.name}</div>", unsafe_allow_html=True)
                    input_scores[p] = game.current_par + c_i.number_input(f"s_{p.name}", -10, 10, 0, step=1, label_visibility="collapsed")
                if st.form_submit_button("💰 계산", type="primary"):
                    st.session_state.temp_ledger, st.session_state.transactions, st.session_state.logs = game.calculate_hole(input_scores)
                    st.session_state.temp_scores = input_scores
            if st.session_state.get('temp_ledger'):
                for log in st.session_state.logs: st.caption(log)
                if st.session_state.transactions:
                    with st.expander("💸 송금 합산", expanded=True):
                        for trans in st.session_state.transactions: st.markdown(f"<div style='font-size: 15px;'>{trans}</div>", unsafe_allow_html=True)
                cols_res = st.columns(len(game.players))
                for idx, (p, amt) in enumerate(st.session_state.temp_ledger.items()):
                    color = "blue" if amt > 0 else "red" if amt < 0 else "black"
                    cols_res[idx].markdown(f"<div style='text-align:center; font-size:14px;'>{p.name}<br><span style='color:{color}; font-weight:bold;'>{amt//1000}k</span></div>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                if c1.button("✅ 확정"):
                    game.commit_round(st.session_state.temp_ledger, st.session_state.temp_scores)
                    st.session_state.temp_ledger = None
                    if game.current_hole > game.total_holes: st.session_state.step = 'final'
                    st.rerun()
                if c2.button("🔄 재입력"):
                    st.session_state.temp_ledger = None
                    st.rerun()

        with tab2:
            guide = game.get_settlement_guide()
            if not guide or guide[0] == "정산할 내용이 없습니다.":
                st.info("정산할 금액이 없습니다.")
            else:
                for line in guide: st.success(line)
            st.divider()
            score_summary_df = pd.DataFrame({p.name: [sum(p.scores)] for p in game.players}).T.rename(columns={0: "Total"})
            st.dataframe(score_summary_df, use_container_width=True)

    elif st.session_state.step == 'final':
        st.title("🏆 결과")
        st.components.v1.html(game.generate_html_report(), height=400, scrolling=True)
        final_guide = game.get_settlement_guide()
        for line in final_guide: st.success(line)
        if st.button("새 게임", type="primary"):
            st.session_state.clear()
            st.rerun()

if __name__ == '__main__': main()