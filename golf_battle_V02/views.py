import streamlit as st
import logic
import pandas as pd

def apply_mobile_style():
    st.markdown("""
        <style>
            .main .block-container { padding-top: 1rem !important; padding-bottom: 2rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
            h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
            .stButton > button { width: 100%; height: 3.5rem !important; font-size: 1.2rem !important; font-weight: bold !important; border-radius: 12px !important; }
            div[data-baseweb="input"] { font-size: 16px !important; }
            div[data-baseweb="select"] { font-size: 16px !important; }
            .stDataFrame { font-size: 14px !important; }
            header { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

def show_sync_button():
    if st.button("🔄 최신 점수 불러오기 (동기화)", type="primary", use_container_width=True):
        logic.sync_data()
        st.toast("구글 시트 동기화 완료!", icon="✅")
        st.rerun()

# --- [수정됨] 사이드바 공통 메뉴 (저장 + 리셋) ---
def sidebar_menu():
    with st.sidebar:
        st.header("📂 파일 관리")
        if hasattr(logic, 'export_game_data'):
            st.download_button("💾 상태 저장", logic.export_game_data(), "golf.json", "application/json")
        
        st.markdown("---")
        st.header("⚙️ 관리 기능")
        
        # 리셋 버튼 로직 (사이드바 내에서 동작)
        if not st.session_state.get('show_reset_confirm', False):
            if st.button("🚫 라운드 리셋", type="secondary"):
                st.session_state.show_reset_confirm = True
                st.rerun()
        else:
            st.warning("모든 데이터가 삭제됩니다.\n정말 초기화 할까요?")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("예", type="primary"):
                    logic.reset_all_data()
                    st.rerun()
            with c2:
                if st.button("아니오"):
                    st.session_state.show_reset_confirm = False
                    st.rerun()

def show_setup_screen():
    apply_mobile_style()
    sidebar_menu() # 사이드바 메뉴 표시
    
    st.title("⛳️ 골프 내기 정산")
    show_sync_button()
    
    saved_p = st.session_state.game_info.get('participants_count', 4)
    saved_c = st.session_state.game_info.get('cart_count', 1)
    
    col1, col2 = st.columns(2)
    with col1: num_p = st.number_input("참가 인원 (최대 12)", 1, 12, saved_p, 1, key="ui_num_p")
    with col2: num_c = st.number_input("카트 수 (최대 3)", 1, 3, saved_c, 1, key="ui_num_c")
    
    st.markdown("---")
    col_header1, col_header2 = st.columns([2.5, 1.5])
    col_header1.markdown("##### 참가자명")
    col_header2.markdown("##### 카트")

    input_names = []; input_carts = []
    for i in range(num_p):
        c1, c2 = st.columns([2.5, 1.5])
        with c1:
            def_name = st.session_state.players[i]['name'] if i < len(st.session_state.players) else ""
            name = st.text_input(f"이름{i+1}", value=def_name, key=f"name_{i}", label_visibility="collapsed")
        with c2:
            if f"cart_{i}" not in st.session_state: 
                auto_val = int((i * num_c) / num_p) + 1
                st.session_state[f"cart_{i}"] = auto_val
            cart = st.number_input(f"카트{i+1}", 1, num_c, key=f"cart_{i}", label_visibility="collapsed")
        input_names.append(name); input_carts.append(cart)

    st.markdown("---")
    
    if st.button("게임 시작 (설정 저장) ▶", use_container_width=True):
        logic.save_setup_data(num_p, num_c, input_names, input_carts)
        st.session_state.step = 2
        st.rerun()

def show_score_screen():
    apply_mobile_style()
    sidebar_menu() # 사이드바 메뉴 표시
    
    st.title("📝 점수 입력")
    show_sync_button()
    
    hole_options = list(range(1, 19))
    current_idx = st.session_state.game_info['current_hole'] - 1
    
    c1, c2 = st.columns([1, 1])
    with c1:
        selected_hole = st.selectbox("홀", options=hole_options, index=current_idx)
        if selected_hole != st.session_state.game_info['current_hole']:
            st.session_state.game_info['current_hole'] = selected_hole
            st.rerun()
    with c2:
        par_options = [3, 4, 5, 6]
        saved_par = st.session_state.game_info['pars'].get(selected_hole, 4)
        try: default_idx = par_options.index(saved_par)
        except ValueError: default_idx = 1
        par = st.selectbox("Par", options=par_options, index=default_idx, key=f"par_select_{selected_hole}")
    
    if st.button("🔄 이 홀 점수 리셋 (0)", use_container_width=True):
        for p in st.session_state.players:
            p['scores'][selected_hole] = par
            widget_key = f"score_rel_{selected_hole}_{p['id']}"
            st.session_state[widget_key] = 0
        st.toast("초기화 완료!", icon="↩️")
        st.rerun()

    st.markdown("---")
    with st.container(height=500, border=False):
        score_options = list(range(6, -4, -1))
        def format_score(s): return f"+{s}" if s > 0 else ("0 (Par)" if s == 0 else f"{s}")

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
                    
                    widget_key = f"score_rel_{selected_hole}_{p['id']}"
                    if widget_key not in st.session_state:
                        st.session_state[widget_key] = default_rel
                    
                    selected_rel = st.selectbox(
                        f"{p['name']} 점수", options=score_options, format_func=format_score,
                        key=widget_key, label_visibility="collapsed"
                    )
                    temp_score_map[p['id']] = par + selected_rel
            st.write("") 

    final_scores = [temp_score_map[p['id']] for p in players]
    
    st.markdown("---")
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("◀ 뒤로", use_container_width=True):
            st.session_state.step = 1; st.rerun()
    with b_col2:
        if st.button("정산 하기 (저장) ▶", use_container_width=True):
            logic.update_scores(selected_hole, par, final_scores)
            st.session_state.step = 3; st.rerun()

def show_result_screen():
    apply_mobile_style()
    sidebar_menu() # 사이드바 메뉴 표시
    
    current_hole = st.session_state.game_info['current_hole']
    st.title(f"⛳️ {current_hole}번홀 정산")
    show_sync_button()
    
    df_hole, is_baepan, reasons = logic.calculate_settlement(current_hole)
    if is_baepan: st.error(f"🚨 **배판! (x{logic.BAEPAN_MULTIPLIER})**"); [st.caption(f"• {r}") for r in reasons]
    else: st.success("✅ 평범한 판")

    st.markdown("---")
    with st.container(height=500, border=False):
        st.subheader("💰 이번 홀 결과")
        st.dataframe(df_hole.style.format({"타당정산": "{:,}", "보너스": "{:,}", "합계": "{:,}"}).set_properties(**{'font-size': '16px', 'text-align': 'center'}), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader(f"🏆 누적 ({current_hole}홀 까지)")
        df_total = logic.get_total_settlement()
        if not df_total.empty:
            st.dataframe(df_total.sort_values(by='누적금액', ascending=False).style.format({"누적금액": "{:,}"}).set_properties(**{'font-size': '16px', 'text-align': 'center', 'font-weight': 'bold'}), use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("💸 최종 송금 내역")
        transfers = logic.calculate_transfer_details()
        if transfers:
            df_tr = pd.DataFrame(transfers)
            df_tr['내역'] = df_tr.apply(lambda x: f"{x['보내는사람']} ➡️ {x['받는사람']}", axis=1)
            st.dataframe(df_tr[['내역', '금액']].style.format({"금액": "{:,}"}).set_properties(**{'font-size': '16px'}), use_container_width=True, hide_index=True)
        else: st.caption("정산 내역 없음")
    
    st.markdown("---")
    if st.button("◀ 뒤로 (점수 수정/홀 이동)", use_container_width=True):
        st.session_state.step = 2; st.rerun()
    if current_hole == 18: st.balloons(); st.success("🎉 경기 종료!")