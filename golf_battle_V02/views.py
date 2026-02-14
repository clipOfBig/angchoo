import streamlit as st
import logic
import pandas as pd

# --- [추가됨] 모바일 최적화 CSS 스타일 함수 ---
def apply_mobile_style():
    st.markdown("""
        <style>
            /* 1. 전체 여백 줄이기 (모바일 화면 넓게 쓰기) */
            .main .block-container {
                padding-top: 1rem !important;
                padding-bottom: 5rem !important;
                padding-left: 0.5rem !important;
                padding-right: 0.5rem !important;
            }
            
            /* 2. 제목 글자 크기 조절 */
            h1 { font-size: 1.5rem !important; margin-bottom: 0.5rem !important; }
            h2 { font-size: 1.3rem !important; }
            h3 { font-size: 1.1rem !important; }
            
            /* 3. 버튼 크기 키우기 (터치하기 편하게) */
            .stButton > button {
                width: 100%;
                height: 3.5rem !important;
                font-size: 1.2rem !important;
                font-weight: bold !important;
                border-radius: 12px !important;
            }
            
            /* 4. 입력창 및 선택창 폰트 크기 (아이폰 확대 방지) */
            div[data-baseweb="input"] { font-size: 16px !important; }
            div[data-baseweb="select"] { font-size: 16px !important; }
            
            /* 5. 데이터프레임(표) 스타일 */
            .stDataFrame { font-size: 14px !important; }
            
            /* 6. 모바일에서 불필요한 상단 헤더 숨김 (선택사항) */
            header { visibility: hidden; }
        </style>
    """, unsafe_allow_html=True)

def show_setup_screen():
    """화면 1: 설정"""
    apply_mobile_style() # 스타일 적용
    
    st.title("⛳️ 골프 내기 정산")
    
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
                label="💾 상태 저장",
                data=logic.export_game_data(),
                file_name="golf_game_save.json",
                mime="application/json"
            )

    st.caption("인원과 카트 수를 설정하세요.")

    saved_p = st.session_state.game_info.get('participants_count', 4)
    saved_c = st.session_state.game_info.get('cart_count', 1)
    
    MAX_PLAYERS = 12
    MAX_CARTS = 3
    if saved_p > MAX_PLAYERS: saved_p = MAX_PLAYERS
    if saved_c > MAX_CARTS: saved_c = MAX_CARTS

    col1, col2 = st.columns(2)
    with col1:
        st.number_input(
            "참가 인원 (최대 12)", 
            min_value=1, max_value=MAX_PLAYERS, 
            value=saved_p, step=1,
            key="ui_num_p",             
            on_change=auto_distribute_carts 
        )
    with col2:
        st.number_input(
            "카트 수 (최대 3)", 
            min_value=1, max_value=MAX_CARTS, 
            value=saved_c, step=1,
            key="ui_num_c",             
            on_change=auto_distribute_carts 
        )
    
    num_p = st.session_state.ui_num_p
    num_c = st.session_state.ui_num_c

    st.markdown("---")
    
    # 모바일에서 보기 편하게 비율 조정 (이름을 더 넓게)
    col_header1, col_header2 = st.columns([2.5, 1.5])
    col_header1.markdown("##### 참가자명")
    col_header2.markdown("##### 카트")

    input_names = []
    input_carts = []

    for i in range(num_p):
        c1, c2 = st.columns([2.5, 1.5])
        with c1:
            default_name = st.session_state.players[i]['name'] if i < len(st.session_state.players) else ""
            name = st.text_input(f"이름{i+1}", value=default_name, key=f"name_{i}", label_visibility="collapsed", placeholder="이름")
        with c2:
            if f"cart_{i}" not in st.session_state:
                if i < len(st.session_state.players):
                    st.session_state[f"cart_{i}"] = st.session_state.players[i]['cart']
                else:
                    st.session_state[f"cart_{i}"] = 1
            
            if st.session_state[f"cart_{i}"] > num_c:
                st.session_state[f"cart_{i}"] = num_c

            cart = st.number_input(
                f"카트{i+1}", 
                min_value=1, max_value=num_c, 
                key=f"cart_{i}", 
                label_visibility="collapsed"
            )
        
        input_names.append(name)
        input_carts.append(cart)

    st.markdown("---")
    
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        with st.expander("📂 불러오기"):
            uploaded_file = st.file_uploader("JSON 파일 선택", type="json")
            if uploaded_file is not None and hasattr(logic, 'load_game_data'):
                if logic.load_game_data(uploaded_file):
                    st.success("완료!")
                    st.rerun()
                else:
                    st.error("오류")

    with b_col2:
        # 모바일에선 버튼이 꽉 차는게 좋음
        if st.button("게임 시작 ▶", use_container_width=True):
            logic.save_setup_data(num_p, num_c, input_names, input_carts)
            st.session_state.step = 2
            st.rerun()

def show_score_screen():
    """화면 2: 점수 입력"""
    apply_mobile_style() # 스타일 적용
    
    with st.sidebar:
        st.header("파일 관리")
        if hasattr(logic, 'export_game_data'):
            st.download_button(
                label="💾 상태 저장",
                data=logic.export_game_data(),
                file_name="golf_game_save.json",
                mime="application/json"
            )

    st.title("📝 점수 입력")
    
    hole_options = list(range(1, 19))
    current_idx = st.session_state.game_info['current_hole'] - 1
    
    # 홀 정보 선택창 (꽉 차게)
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
        st.info(f"🛒 **카트 {cid}**") # 모바일 가독성을 위해 subheader 대신 info 박스 사용
        cart_players = [p for p in players if p['cart'] == cid]
        
        for p in cart_players:
            c1, c2 = st.columns([2, 1.5]) # 이름 공간 확보
            with c1:
                st.write(f"**{p['name']}**")
            with c2:
                saved_abs_score = p['scores'].get(selected_hole, 0)
                if saved_abs_score == 0: default_rel = 0
                else: default_rel = saved_abs_score - par
                
                if default_rel not in score_options: default_rel = 0

                selected_rel = st.selectbox(
                    f"{p['name']} 점수", 
                    options=score_options, 
                    format_func=format_score,
                    index=score_options.index(default_rel),
                    key=f"score_rel_{selected_hole}_{p['id']}", 
                    label_visibility="collapsed"
                )
                temp_score_map[p['id']] = par + selected_rel
        st.write("") # 간격 추가

    final_scores = [temp_score_map[p['id']] for p in players]
    
    st.markdown("---")

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("◀ 뒤로", use_container_width=True):
            st.session_state.step = 1
            st.rerun()
    with b_col2:
        if st.button("정산 하기 ▶", use_container_width=True):
            logic.update_scores(selected_hole, par, final_scores)
            st.session_state.step = 3
            st.rerun()

def show_result_screen():
    """화면 3: 정산 결과"""
    apply_mobile_style() # 스타일 적용
    
    current_hole = st.session_state.game_info['current_hole']
    par = st.session_state.game_info['par']
    
    with st.sidebar:
        st.header("파일 관리")
        if hasattr(logic, 'export_game_data'):
            st.download_button(
                label="💾 상태 저장",
                data=logic.export_game_data(),
                file_name="golf_game_save.json",
                mime="application/json"
            )

    st.title(f"⛳️ {current_hole}번홀 정산")
    
    df_hole, is_baepan, reasons = logic.calculate_settlement(current_hole)
    
    if is_baepan:
        mul = logic.BAEPAN_MULTIPLIER if hasattr(logic, 'BAEPAN_MULTIPLIER') else 1
        st.error(f"🚨 **배판! (x{mul})**")
        for r in reasons:
            st.caption(f"• {r}")
    else:
        st.success("✅ 평범한 판")

    st.markdown("---")

    st.subheader("💰 이번 홀 결과")
    # 모바일에서 표가 잘 보이도록 폰트 크기 강제 지정
    styled_df = df_hole.style.format({
        "타당정산": "{:,}",
        "보너스": "{:,}",
        "합계": "{:,}"
    }).set_properties(**{'font-size': '16px', 'text-align': 'center'})
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    st.subheader(f"🏆 누적 ({current_hole}홀 까지)")
    df_total = logic.get_total_settlement()
    
    if not df_total.empty:
        df_total = df_total.sort_values(by='누적금액', ascending=False)
        styled_total = df_total.style.format({"누적금액": "{:,}"})\
            .set_properties(**{'font-size': '16px', 'text-align': 'center', 'font-weight': 'bold'})
        st.dataframe(styled_total, use_container_width=True, hide_index=True)
    
    # 송금 내역 섹션
    st.markdown("---")
    st.subheader("💸 최종 송금 내역")
    
    transfers = logic.calculate_transfer_details()
    if transfers:
        st.info("누적 금액 기준 송금 내역입니다.")
        
        df_transfers = pd.DataFrame(transfers)
        df_transfers['내역'] = df_transfers.apply(
            lambda x: f"{x['보내는사람']} ➡️ {x['받는사람']}", axis=1
        )
        df_display = df_transfers[['내역', '금액']]
        
        # 글자를 키워서 잘 보이게
        st.dataframe(
            df_display.style.format({"금액": "{:,}"}).set_properties(**{'font-size': '16px'}), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.caption("정산 내역 없음")
    
    st.markdown("---")
    
    # 버튼 하나를 꽉 차게
    if st.button("◀ 뒤로 (점수 수정/홀 이동)", use_container_width=True):
        st.session_state.step = 2
        st.rerun()

    if current_hole == 18:
        st.balloons()
        st.success("🎉 경기 종료! 수고하셨습니다.")