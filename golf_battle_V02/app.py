# app.py
import streamlit as st
import logic
import views

# 1. 페이지 설정
st.set_page_config(page_title="골프 내기 정산", page_icon="⛳️")

# 2. 데이터 초기화
logic.init_session_state()

# 3. 단계별 화면 보여주기 (라우팅)
if st.session_state.step == 1:
    views.show_setup_screen()
    
elif st.session_state.step == 2:
    views.show_score_screen()
    
elif st.session_state.step == 3:
    views.show_result_screen()