"""新建案件 — 表单填写与证据上传"""
import streamlit as st
from database import SessionLocal, Case
from evidence_parser import parse_pdf, ocr_image, is_pdf_file, is_image_file
from styles import page_header, form_section_title, accent_notice

def render():
    page_header('新建商标侵权案件', '左侧填写案件信息，右侧上传证据材料')
    col_form, col_evidence = st.columns([1, 1], gap='medium')
    with col_form:
        form_section_title('案件信息')
        default_desc = st.session_state.get('last_case_desc', '')
        with st.form('new_case_form'):
            case_name = st.text_input('案件名称 *', placeholder='例如：某品牌诉某电商商标侵权案')
            cause_type = st.selectbox('案由', ['商标侵权', '著作权侵权', '不正当竞争'], disabled=True)
            evidence_extra = st.session_state.get('evidence_text_extra', '')
            prefill = (evidence_extra + '\n\n' + default_desc).strip()
            case_description = st.text_area('案情描述 *', height=110, value=prefill, placeholder='请详细描述案情，包括：\n- 原告商标信息（注册号、类别、有效期）\n- 被告侵权行为（何时发现、如何侵权）\n- 侵权商品销售情况\n- 已收集的证据')
            client_org = st.text_input('我司主体名称', placeholder='例如：我司主体名称')
            goal_type = st.radio('业务目标', ['要钱', '要名'], horizontal=True)
            submitted = st.form_submit_button('创建案件并进入评估', type='primary', use_container_width=True)
            if submitted:
                full_desc = case_description.strip()
                if not case_name or not full_desc:
                    st.error('请填写必填项（案件名称、案情描述）')
                else:
                    db = SessionLocal()
                    try:
                        new_case = Case(name=case_name, cause_type='商标侵权', goal_type=goal_type, client_org=client_org or '', case_description=full_desc, status='pending')
                        db.add(new_case)
                        db.commit()
                        db.refresh(new_case)
                        st.session_state['current_case_id'] = new_case.id
                        st.session_state['current_case_name'] = new_case.name
                        st.session_state['last_case_desc'] = full_desc
                        st.session_state['evidence_text_extra'] = ''
                        st.session_state['nav_target'] = '评估分析'
                        st.rerun()
                    except Exception as e:
                        st.error(f'创建失败: {e}')
                        db.rollback()
                    finally:
                        db.close()
    with col_evidence:
        form_section_title('证据文件上传')
        uploaded_files = st.file_uploader('支持 PDF（自动提取文本）和图片（OCR 识别文字）', type=['pdf', 'png', 'jpg', 'jpeg'], accept_multiple_files=True, key='evidence_uploader', help='上传商标注册证、侵权截图、公证文书等证据文件', label_visibility='collapsed')
        parsed_evidences = []
        if uploaded_files:
            for f in uploaded_files:
                cache_key = f'parsed_{f.name}_{f.size}'
                if cache_key not in st.session_state:
                    with st.spinner(f'正在解析 {f.name} ...'):
                        file_bytes = f.getvalue()
                        if is_pdf_file(f.name):
                            result = parse_pdf(file_bytes, f.name)
                        elif is_image_file(f.name):
                            result = ocr_image(file_bytes, f.name)
                        else:
                            result = {'success': False, 'text': '', 'error': '不支持的文件格式'}
                        if result['success'] and len(result['text']) > 3000:
                            result['text'] = result['text'][:3000] + '\n\n... (文本过长，已截取)'
                        st.session_state[cache_key] = result
                parsed = st.session_state[cache_key]
                parsed_evidences.append((f.name, f.size, parsed))
        for fname, fsize, result in parsed_evidences:
            if result['success']:
                text_len = len(result['text'])
                with st.expander(f'{fname}（{text_len} 字）'):
                    st.text_area(f'内容 - {fname}', value=result['text'], height=120, key=f'preview_{fname}', label_visibility='collapsed')
                    if st.button('追加到案情描述', key=f'append_{hash(fname)}'):
                        current_extra = st.session_state.get('evidence_text_extra', '')
                        st.session_state['evidence_text_extra'] = current_extra + f"\n\n【证据文件: {fname}】\n{result['text']}"
                        st.rerun()
            else:
                accent_notice(f"{fname}: {result['error']}")
        evidence_extra_show = st.session_state.get('evidence_text_extra', '')
        if evidence_extra_show:
            accent_notice(f'已追加 {len(evidence_extra_show)} 字证据文本到案情描述')
            if st.button('清除已追加的证据文本', type='secondary'):
                st.session_state['evidence_text_extra'] = ''
                st.rerun()