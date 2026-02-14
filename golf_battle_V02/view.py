import streamlit as st
import logic
import pandas as pd

def show_setup_screen():
    """화면 1: 설정 (Warning 메시지 해결 버전)"""
    st.title("⛳️ 골프 내기 정산 앱")
    
    def auto_distribute_carts():
        p = st.session_state.ui_num_p
        c = st.session_state.ui_num_c
        
        st.session_state.game_info['participants_count'] = p
        st.session_state.game_info['cart_count'] = c
        
        for i in range(p):
            auto_cart_num = int((i * c) / p) + 1
            st.session_state[f"cart_{i}"] = auto_cart_num
            
            if i < len(st.session_state.players):
                st.session_state.players[i]['cart'] = auto_cart_num

    with st.sidebar:
        st.header("파일 관리")
        if hasattr(logic, 'export_game_data'):
            st.download_button(
                label="💾 현재 상태 저장하기",
                data=logic.export_game_data(),
                file_name="golf_game_save.json",
                mime="application/json"
            )

    st.subheader("참가자 설정")

    saved_p = st.session_state.game_info.get('participants_count', 4)
    saved_c = st.session_state.game_info.get('cart_count', 1)
    
    MAX_PLAYERS = 12
    MAX_CARTS = 3
    if saved_p > MAX_PLAYERS: saved_p = MAX_PLAYERS
    if saved_c > MAX_CARTS: saved_c = MAX_CARTS

    col1, col2 = st.columns(2)
    with col1:
        st.number_input(
            "참가 인원수 (최대 12명)", 
            min_value=1, max_value=MAX_PLAYERS, 
            value=saved_p, step=1,
            key="ui_num_p",             
            on_change=auto_distribute_carts 
        )
    with col2:
        st.number_input(
            "카트 개수 (최대 3개)", 
            min_value=1, max_value=MAX_CARTS, 
            value=saved_c, step=1,
            key="ui_num_c",             
            on_change=auto_distribute_carts 
        )
    
    num_p = st.session_state.ui_num_p
    num_c = st.session_state.ui_num_c

    st.markdown("---")
    
    col_header1, col_header2 = st.columns([2, 1])
    col_header1.write("**참가자명**")
    col_header2.write("**카트번호**")

    input_names = []
    input_carts = []

    for i in range(num_p):
        c1, c2 = st.columns([2, 1])
        with c1:
            default_name = st.session_state.players[i]['name'] if i < len(st.session_state.players) else ""
            name = st.text_input(f"참가자 {i+1}", value=default_name, key=f"name_{i}", label_visibility="collapsed")
        with c2:
            if f"cart_{i}" not in st.session_state:
                if i < len(st.session_state.players):
                    st.session_state[f"cart_{i}"] = st.session_state.players[i]['cart']
                else:
                    st.session_state[f"cart_{i}"] = 1
            
            if st.session_state[f"cart_{i}"] > num_c:
                st.session_state[f"cart_{i}"] = num_c

            cart = st.number_input(
                f"카트 {i+1}", 
                min_value=1, max_value=num_c, 
                key=f"cart_{i}", 
                label_visibility="collapsed"
            )
        
        input_names.append(name)
        input_carts.append(cart)

    st.markdown("---")
    
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        with st.expander("📂 파일 불러오기"):
            uploaded_file = st.file_uploader("저장된 JSON 파일 선택", type="json")
            if uploaded_file is not None and hasattr(logic, 'load_game_data'):
                if logic.load_game_data(uploaded_file):
                    st.success("불러오기 성공!")
                    st.rerun()
                else:
                    st.error("파일 형식이 잘못되었습니다.")

    with b_col2:
        if st.button("새 게임 시작 (다음)", use_container_width=True):
            logic.save_setup_data(num_p, num_c, input_names, input_carts)
            st.session_state.step = 2
            st.rerun()

def show_score_screen():
    """화면 2: 점수 입력"""
    
    with st.sidebar:
        st.header("파일 관리")
        if hasattr(logic, 'export_game_data'):
            st.download_button(
                label="💾 현재 상태 저장하기",
                data=logic.export_game_data(),
                file_name="golf_game_save.json",
                mime="application/json"
            )

    st.header("점수 입력")
    
    hole_options = list(range(1, 19))
    current_idx = st.session_state.game_info['current_hole'] - 1
    
    info_cols = st.columns([1, 2, 3])
    with info_cols[0]:
        selected_hole = st.selectbox("홀 번호", options=hole_options, index=current_idx)
        if selected_hole != st.session_state.game_info['current_hole']:
            st.session_state.game_info['current_hole'] = selected_hole
            st.rerun()

    with info_cols[1]:
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
        st.subheader(f"🛒 카트 {cid}")
        cart_players = [p for p in players if p['cart'] == cid]
        
        for p in cart_players:
            c1, c2 = st.columns([2, 1])
            with c1:
                st.write(f"**{p['name']}**")
            with c2:
                saved_abs_score = p['scores'].get(selected_hole, 0)
                if saved_abs_score == 0: default_rel = 0
                else: default_rel = saved_abs_score - par
                
                if default_rel not in score_options: default_rel = 0

                selected_rel = st.selectbox(
                    "스코어", 
                    options=score_options, 
                    format_func=format_score,
                    index=score_options.index(default_rel),
                    key=f"score_rel_{selected_hole}_{p['id']}", 
                    label_visibility="collapsed"
                )
                temp_score_map[p['id']] = par + selected_rel
        st.divider()

    final_scores = [temp_score_map[p['id']] for p in players]

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("뒤로", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with b_col2:
        if st.button("다음 (정산)", use_container_width=True):
            logic.update_scores(selected_hole, par, final_scores)
            st.session_state.step = 3
            st.rerun()

def show_result_screen():
    """화면 3: 정산 결과 (송금 내역 추가)"""
    current_hole = st.session_state.game_info['current_hole']
    par = st.session_state.game_info['par']
    
    with st.sidebar:
        st.header("파일 관리")
        if hasattr(logic, 'export_game_data'):
            st.download_button(
                label="💾 현재 상태 저장하기",
                data=logic.export_game_data(),
                file_name="golf_game_save.json",
                mime="application/json"
            )

    st.header(f"{current_hole}번홀 (Par {par}) 정산")
    
    df_hole, is_baepan, reasons = logic.calculate_settlement(current_hole)
    
    if is_baepan:
        mul = logic.BAEPAN_MULTIPLIER if hasattr(logic, 'BAEPAN_MULTIPLIER') else 1
        st.error(f"🚨 **배판 조건 발생! (현재 배율: {mul}배)**")
        for r in reasons:
            st.caption(f"- {r}")
    else:
        st.success("평범한 판입니다")

    st.markdown("---")

    st.subheader(f"💰 {current_hole}번 홀 정산 결과")
    styled_df = df_hole.style.format({
        "타당정산": "{:,}원",
        "보너스": "{:,}원",
        "합계": "{:,}원"
    })
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    st.subheader(f"🏆 전체 누적 (1 ~ {current_hole}홀)")
    df_total = logic.get_total_settlement()
    
    if not df_total.empty:
        df_total = df_total.sort_values(by='누적금액', ascending=False)
        styled_total = df_total.style.format({"누적금액": "{:,}원"})
        st.dataframe(styled_total, use_container_width=True, hide_index=True)
    
    # --- [여기가 핵심입니다] 최종 송금 내역 섹션 ---
    st.markdown("---")
    st.subheader("💸 최종 송금 내역 (Total)")
    
    transfers = logic.calculate_transfer_details()
    if transfers:
        st.info("현재까지의 누적 금액을 기준으로 계산된 송금 내역입니다.")
        
        # 보기 좋은 표 형태로 변환
        df_transfers = pd.DataFrame(transfers)
        
        # 화살표 모양 컬럼 추가해서 보기 좋게 만듦
        df_transfers['내역'] = df_transfers.apply(
            lambda x: f"{x['보내는사람']} ➡️ {x['받는사람']}", axis=1
        )
        
        # 보여줄 컬럼만 선택
        df_display = df_transfers[['내역', '금액']]
        
        st.dataframe(
            df_display.style.format({"금액": "{:,}원"}), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.caption("정산할 내역이 없습니다.")
    
    st.markdown("---")
    
    if st.button("뒤로 (다른 홀 선택 / 점수 수정)", use_container_width=True):
        st.session_state.step = 2
        st.rerun()

    if current_hole == 18:
        st.balloons()
        st.success("🎉 모든 경기가 종료되었습니다! 수고하셨습니다.")