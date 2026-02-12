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
            if amount > 0:
                receivers.append({'player': p, 'amount': amount})
            elif amount < 0:
                senders.append({'player': p, 'amount': -amount})

        receivers.sort(key=lambda x: x['amount'], reverse=True)
        senders.sort(key=lambda x: x['amount'], reverse=True)

        trans_list = []
        r_idx = 0
        s_idx = 0

        while r_idx < len(receivers) and s_idx < len(senders):
            receiver = receivers[r_idx]
            sender = senders[s_idx]

            amount = min(receiver['amount'], sender['amount'])

            if amount > 0:
                trans_list.append(f"**{sender['player'].name}** ➡️ **{receiver['player'].name}**: `{amount:,}원`")

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
            for p, amt in current_ledger.items():
                temp_ledger[p] += amt
        return self.simplify_transactions(temp_ledger)
    
    def generate_html_report(self):
        html = """
        <style>
            table { width: 100%; border-collapse: collapse; font-size: 12px; text-align: center; white-space: nowrap; }
            th, td { border: 1px solid #ddd; padding: 4px 6px; }
            th { background-color: #f8f9fa; position: sticky; left: 0; }
            .pos { color: blue; font-weight: bold; }
            .neg { color: red; font-weight: bold; }
        </style>
        """
        html += "<h5>⛳️ 스코어 (Score)</h5>"
        html += """<div style='overflow-x:auto;'><table><thead><tr><th>이름</th>"""
        
        max_holes = len(self.players[0].scores) if self.players else 0
        for i in range(max_holes):
            html += f"<th>{i+1}H</th>"
        html += "<th>Total</th></tr></thead><tbody>"
        
        for p in self.players:
            html += f"<tr><td>{p.name}</td>"
            for s in p.scores:
                html += f"<td>{s}</td>"
            html += f"<td>{sum(p.scores)}</td></tr>"
        html += "</tbody></table></div>"
        
        html += "<h5>💰 홀별 손익 (단위: 천원)</h5>"
        html += """<div style='overflow-x:auto;'><table><thead><tr><th>이름</th>"""
        for i in range(max_holes):
            html += f"<th>{i+1}H</th>"
        html += "<th>계</th></tr></thead><tbody>"
        
        for p in self.players:
            html += f"<tr><td>{p.name}</td>"
            for amt in p.pnl_history:
                val_k = int(amt / 1000)
                color_class = "pos" if val_k > 0 else "neg" if val_k < 0 else ""
                html += f"<td class='{color_class}'>{val_k:,}</td>"
            
            total_k = int(p.money / 1000)
            color_class = "pos" if total_k > 0 else "neg" if total_k < 0 else ""
            html += f"<td class='{color_class}'>{total_k:,}</td></tr>"
        html += "</tbody></table></div>"
        return html

# ==========================================
# [Streamlit View] UI 구성 (토글/버튼형 최적화)
# ==========================================

st.set_page_config(page_title="골프 정산", layout="centered", initial_sidebar_state="collapsed")

# [CSS] 스타일 최적화
st.markdown("""
    <style>
        /* 1. 기본 폰트 크기 */
        html, body, [class*="css"] {
            font-size: 16px !important;
        }
        .block-container { 
            padding-top: 3rem !important; 
            padding-bottom: 3rem !important; 
            padding-left: 0.5rem !important; 
            padding-right: 0.5rem !important; 
        }
        
        /* 2. 제목 크기 */
        h1 { font-size: 1.8rem !important; padding-bottom: 0.5rem !important; }
        h3 { font-size: 1.3rem !important; padding-top: 0.5rem !important; }
        p, div, label { font-size: 16px !important; }

        /* 3. 숫자 입력창(Number Input) 스타일 - 토글 버튼처럼 보이게 */
        .stNumberInput input {
            text-align: center !important; /* 숫자 가운데 정렬 */
            font-weight: bold !important;
            font-size: 18px !important;
            height: 3.0rem !important;
        }
        /* +/- 버튼 크기 키우기 */
        button[kind="secondary"] {
            height: 3.0rem !important;
            width: 3.0rem !important;
        }

        /* 4. 입력창 및 버튼 크기 통일 */
        .stTextInput input, .stSelectbox div[data-baseweb="select"] div {
            height: 3.0rem !important; 
            min-height: 3.0rem !important;
            font-size: 16px !important;
        }
        
        /* 5. 메인 버튼 확대 */
        .stButton button { 
            width: 100%; 
            border-radius: 10px; 
            height: 3.2rem !important; 
            min-height: 3.2rem !important;
            font-size: 17px !important;
            margin-top: 10px !important;
            font-weight: bold !important;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 3.0rem !important;
            font-size: 16px !important;
        }
    </style>
""", unsafe_allow_html=True)

if 'game' not in st.session_state:
    st.session_state.game = None
if 'step' not in st.session_state:
    st.session_state.step = 'setup' 
if 'temp_ledger' not in st.session_state:
    st.session_state.temp_ledger = None
if 'temp_scores' not in st.session_state:
    st.session_state.temp_scores = None

def main():
    if st.session_state.step == 'setup':
        st.title("⛳️ 골프 정산")
        
        num_players = st.selectbox("참가 인원", list(range(2, 13)), index=2)
        
        with st.form("setup_form"):
            st.write(f"플레이어 {num_players}명 이름:")
            input_names = []
            
            cols = st.columns(2) 
            
            default_names = [
                "홍길동", "김프로", "박싱글", "최버디", 
                "이장타", "정퍼터", "강아이언", "윤우드",
                "송어프로", "임샌드", "한이글", "오홀인원"
            ]
            
            for i in range(num_players):
                val = default_names[i] if i < len(default_names) else f"선수{i+1}"
                with cols[i % 2]:
                    name = st.text_input(f"p{i}", value=val, key=f"p_input_{i}", label_visibility="collapsed")
                    input_names.append(name)
            
            st.divider()
            total_h = st.number_input("총 홀수", 1, 36, 18)
            submit = st.form_submit_button("게임 시작", type="primary")

            if submit:
                names = [n.strip() for n in input_names if n.strip()]
                if len(names) < 2:
                    st.error("2명 이상 필요")
                else:
                    st.session_state.game = GolfGame()
                    st.session_state.game.total_holes = total_h
                    for n in names: st.session_state.game.add_player(n)
                    st.session_state.step = 'playing'
                    st.rerun()

    elif st.session_state.step == 'playing':
        game = st.session_state.game
        
        st.info(f"🚩 **Hole {game.current_hole}** / {game.total_holes} (Par {game.current_par})")
        
        tab1, tab2 = st.tabs(["📝 입력", "📊 현황"])
        
        with tab1:
            col_par, col_empty = st.columns([1, 2])
            with col_par:
                game.current_par = st.selectbox("Par", [3, 4, 5, 6], index=1)
            
            with st.form("score_form"):
                st.caption("스코어 ( +/- 버튼으로 조절 )")
                input_scores = {}
                
                # 2열 그리드
                grid_cols = st.columns(2)
                
                for idx, p in enumerate(game.players):
                    with grid_cols[idx % 2]:
                        # [레이아웃] 이름(40%) - 숫자입력(60%)
                        c_name, c_input = st.columns([0.4, 0.6])
                        
                        with c_name:
                            # 이름 수직 중앙 정렬
                            st.markdown(f"<div style='margin-top: 15px; font-weight: bold; text-align: left; font-size: 16px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{p.name}</div>", unsafe_allow_html=True)
                        
                        with c_input:
                            # [핵심] number_input 사용 (토글/스테퍼 역할)
                            # step=1 로 설정하여 + / - 버튼으로 조절
                            # 모바일에서 숫자 부분을 터치하지 않고 +/- 만 누르면 키보드 안 뜸
                            score_val = st.number_input(
                                f"{p.name}_num",
                                min_value=-10, 
                                max_value=10, 
                                value=0, # 기본값 0 (Par)
                                step=1,
                                format="%d", # 정수만 표시 (e.g., 0, -1, +1)
                                key=f"s_{p.name}",
                                label_visibility="collapsed"
                            )
                            # 입력값은 Par 기준 차이 (0 = Par)
                            input_scores[p] = game.current_par + score_val
                
                st.write("")
                if st.form_submit_button("💰 계산 (미리보기)", type="primary"):
                    ledger, transactions, logs = game.calculate_hole(input_scores)
                    st.session_state.temp_ledger = ledger
                    st.session_state.temp_scores = input_scores
                    st.session_state.logs = logs
                    st.session_state.transactions = transactions
            
            if st.session_state.get('temp_ledger'):
                st.divider()
                
                for log in st.session_state.logs:
                    if "배판" in log: st.error(log)
                    else: st.caption(log)
                
                if st.session_state.transactions:
                    with st.expander("💸 송금 (합산)", expanded=True):
                        for trans in st.session_state.transactions:
                            st.write(trans)
                else:
                    st.info("거래 없음")

                st.caption("이번 홀 손익")
                cols_res = st.columns(len(game.players))
                for idx, (p, amt) in enumerate(st.session_state.temp_ledger.items()):
                    with cols_res[idx]:
                        color = "blue" if amt > 0 else "red" if amt < 0 else "black"
                        val_str = f"{amt//1000}k" if abs(amt) >= 1000 else f"{amt}"
                        st.markdown(f"<div style='text-align:center; font-size:14px;'>{p.name}<br><span style='color:{color}; font-weight:bold;'>{val_str}</span></div>", unsafe_allow_html=True)

                st.write("")
                col_conf1, col_conf2 = st.columns(2)
                with col_conf1:
                    if st.button("✅ 확정"):
                        game.commit_round(st.session_state.temp_ledger, st.session_state.temp_scores)
                        st.session_state.temp_ledger = None
                        st.session_state.temp_scores = None
                        if game.current_hole > game.total_holes:
                            st.session_state.step = 'final'
                        st.rerun()
                with col_conf2:
                    if st.button("🔄 재입력"):
                        st.session_state.temp_ledger = None
                        st.rerun()

        with tab2:
            st.subheader("누적 정산")
            guide = game.get_settlement_guide()
            if guide and guide[0] != "정산할 내용이 없습니다 (0원).":
                for line in guide:
                    st.success(line)
            else:
                st.info("정산할 금액이 없습니다.")
            
            st.divider()
            score_summary = {p.name: sum(p.scores) for p in game.players}
            st.dataframe(pd.DataFrame(list(score_summary.items()), columns=["이름", "Total"]), hide_index=True, use_container_width=True)

    elif st.session_state.step == 'final':
        game = st.session_state.game
        st.balloons()
        st.title("🏆 최종 결과")
        
        html_report = game.generate_html_report()
        st.components.v1.html(html_report, height=500, scrolling=True)
        
        st.divider()
        st.subheader("💸 최종 송금")
        final_guide = game.get_settlement_guide()
        for line in final_guide: st.success(line)
            
        if st.button("새 게임 시작", type="primary"):
            st.session_state.clear()
            st.rerun()

if __name__ == '__main__':
    main()