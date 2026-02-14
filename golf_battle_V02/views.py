import streamlit as st
import logic
import pandas as pd

def apply_mobile_style():
    st.markdown("""
        <style>
            .main .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
            h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
            .stButton > button { width: 100%; height: 3.5rem !important; font-size: 1.2rem !important; font-weight: bold !important; border-radius: 12px !important; }
            div[data-baseweb="input"] { font-size: 16px !important; }
            div[data-baseweb="select"] { font-size: 16px !important; }
            .stDataFrame { font-size: 14px !important; }
            header { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

def sidebar_sync_button():
    with st.sidebar:
        st.header("데이터 동기화")
        if st.button("🔄 최신 점수 불러오기", type="primary"):
            logic.sync_data()
            st.toast("구글 시트에서 최신 정보를 가져왔습니다.")
            st.rerun()
        st.caption("다른 카트에서 입력한 점수가 안 보이면 눌러주세요.")

def show_setup_screen():
    """화면 1: 설정"""
    apply_mobile_style()
    sidebar_sync_button()
    
    st.title("⛳️ 골프 내기 정산")
    
    # 설정값 로드
    saved_p = st.session_state.game_info.get('participants_count', 4)
    saved_c = st.session_state.game_info.get('cart_count', 1)
    
    col1, col2 = st.columns(2)
    with col1:
        num_p = st.number_input("참가 인원 (최대 12)", 1, 12, saved_p, 1, key="ui_num_p")
    with col2:
        num_c = st.number_input("카트 수 (최대 3)", 1, 3, saved_c, 1, key="ui_num_c")
    
    st.markdown("---")
    
    col_header1, col_header2 = st.columns([2.5, 1.5])
    col_header1.markdown("##### 참가자명")
    col_header2.markdown("##### 카트")

    input_names = []
    input_carts = []

    for i in range(num_p):
        c1, c2 = st.columns([2.5, 1.5])
        with c1:
            default_name = st.session_state.players[i]['name'] if i < len(st.session_state.players) else ""
            name = st.text_input(f"이름{i+1}", value=default_name, key=f"name_{i}", label_visibility="collapsed")
        with c2:
            default_cart = st.session_state.players[i]['cart'] if i < len(st.session_state.players) else 1
            # 자동 배분 로직 간소화: 새로 설정할 때만 적용되도록
            if f"cart_{i}" not in st.session_state: 
                auto_val = int((i * num_c) / num_p) + 1
                st.session_state[f"cart_{i}"] = auto_val

            cart = st.number_input(f"카트{i+1}", 1, num_c, key=f"cart_{i}", label_visibility="collapsed")
        
        input_names.append(name)
        input_carts.append(cart)

    st.markdown("---")
    
    if st.button("게임 시작 (설정 저장) ▶", use_container_width=True):
        logic.save_setup_data(num_p, num_c, input_names, input_carts)
        st.session_state.step = 2
        st.rerun()

def show_score_screen():
    """화면 2: 점수 입력"""
    apply_mobile_style()
    sidebar_sync_button()

    st.title("📝 점수 입력")
    
    hole_options = list(range(1, 19))
    current_idx = st.session_state.game_info['current_hole'] - 1
    
    c1, c2 = st.columns([1, 1])
    with c1:
        selected_hole = st.selectbox("홀", options=hole_options, index=current_idx)
        if selected_hole != st.session_state.game_info['current_hole']:
            st.session_state.game_info['current_hole'] = selected_hole
            st.rerun()
    with c2:
        par = st.selectbox("Par", options=[3, 4, 5, 6], index=1, key=f"par_select_{selected_hole}")
    
    st.markdown("---")
    
    score_options = list(range(6, -4, -1))
    def format_score(s):
        if s > 0: return f"+{s}"
        elif s == 0: return "0 (Par)"
        else: return f"{s}"

    players = st.session_state.players
    cart_ids = sorted(list(set(p['cart'] for p in players)))
    
    temp_score_map = {} 

    for cid in cart_ids:
        st.info(f"🛒 **카트 {cid}**")
        cart_players = [p for p in players if p['cart'] == cid]
        for p in cart_players:
            c1, c2 = st.columns([2, 1.5])
            with c1: st.write(f"**{p['name']}**")
            with c2:
                saved_abs_score = p['scores'].get(selected_hole, 0)
                default_rel = saved_abs_score - par if saved_abs_score != 0 else 0
                if default_rel not in score_options: default_rel = 0
                
                selected_rel = st.selectbox(
                    f"{p['name']} 점수", options=score_options, format_func=format_score,
                    index=score_options.index(default_rel), key=f"score_rel_{selected_hole}_{p['id']}", label_visibility="collapsed"
                )
                temp_score_map[p['id']] = par + selected_rel
        st.write("") 

    final_scores = [temp_score_map[p['id']] for p in players]
    st.markdown("---")

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("◀ 뒤로", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with b_col2:
        if st.button("정산 하기 (저장) ▶", use_container_width=True):
            logic.update_scores(selected_hole, par, final_scores)
            st.session_state.step = 3
            st.rerun()

def show_result_screen():
    """화면 3: 정산 결과"""
    apply_mobile_style()
    sidebar_sync_button()
    
    current_hole = st.session_state.game_info['current_hole']
    
    st.title(f"⛳️ {current_hole}번홀 정산")
    
    df_hole, is_baepan, reasons = logic.calculate_settlement(current_hole)
    
    if is_baepan:
        mul = logic.BAEPAN_MULTIPLIER
        st.error(f"🚨 **배판! (x{mul})**")
        for r in reasons: st.caption(f"• {r}")
    else:
        st.success("✅ 평범한 판")

    st.markdown("---")
    st.subheader("💰 이번 홀 결과")
    styled_df = df_hole.style.format({"타당정산": "{:,}", "보너스": "{:,}", "합계": "{:,}"}).set_properties(**{'font-size': '16px', 'text-align': 'center'})
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader(f"🏆 누적 ({current_hole}홀 까지)")
    df_total = logic.get_total_settlement()
    if not df_total.empty:
        df_total = df_total.sort_values(by='누적금액', ascending=False)
        styled_total = df_total.style.format({"누적금액": "{:,}"}).set_properties(**{'font-size': '16px', 'text-align': 'center', 'font-weight': 'bold'})
        st.dataframe(styled_total, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.subheader("💸 최종 송금 내역")
    transfers = logic.calculate_transfer_details()
    if transfers:
        df_transfers = pd.DataFrame(transfers)
        df_transfers['내역'] = df_transfers.apply(lambda x: f"{x['보내는사람']} ➡️ {x['받는사람']}", axis=1)
        st.dataframe(df_transfers[['내역', '금액']].style.format({"금액": "{:,}"}).set_properties(**{'font-size': '16px'}), use_container_width=True, hide_index=True)
    else:
        st.caption("정산 내역 없음")
    
    st.markdown("---")
    if st.button("◀ 뒤로 (점수 수정/홀 이동)", use_container_width=True):
        st.session_state.step = 2
        st.rerun()