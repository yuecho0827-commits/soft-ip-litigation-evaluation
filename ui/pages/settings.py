"""系统配置 — 运行模式与外部服务参数管理"""
import streamlit as st
from config import get_runtime_settings, get_runtime_configuration_status, save_runtime_settings
from styles import page_header, form_section_title, metric_card, empty_state_notice, accent_notice, COLORS

def render():
    page_header('系统配置', '运行模式与外部服务参数管理')
    current_settings = get_runtime_settings()
    current_status = get_runtime_configuration_status()
    saved_mode_label = 'Mock 模拟模式' if current_settings['use_mock'] else '真实 Demo 模式'
    mode_options = ['Mock 模拟模式', '真实 Demo 模式']
    if st.session_state.get('system_config_mode_saved') != saved_mode_label:
        st.session_state['system_config_mode_preview'] = saved_mode_label
        st.session_state['system_config_mode_saved'] = saved_mode_label
    preview_mode_label = st.session_state.get('system_config_mode_preview', saved_mode_label)
    is_mock_mode = preview_mode_label == 'Mock 模拟模式'
    st.markdown(f"""\n    <div class="card" style="border-left:4px solid {COLORS['accent']};">\n        <div style="font-size:1.05rem;font-weight:700;color:{COLORS['primary']};">本地配置中心</div>\n        <div style="font-size:0.88rem;color:{COLORS['text_body']};margin-top:10px;line-height:1.8;">\n            系统配置页用于维护当前机器上的运行参数。配置会写入本地 <code>.env</code> 文件，不会提交到仓库，也不会在页面中回显凭证明文。\n        </div>\n    </div>\n    """, unsafe_allow_html=True)
    col_form, col_status = st.columns([1.2, 0.8], gap='large')
    with col_form:
        form_section_title('运行配置')
        st.radio('运行模式', mode_options, key='system_config_mode_preview', horizontal=True)
        preview_mode_label = st.session_state.get('system_config_mode_preview', saved_mode_label)
        is_mock_mode = preview_mode_label == 'Mock 模拟模式'
        with st.form('system_config_form'):
            st.markdown('**模型提供方**')
            st.caption('DeepSeek（固定，不可更换）')
            base_url = st.text_input('DeepSeek Base URL', value=current_settings['deepseek_base_url'], placeholder='https://api.deepseek.com', disabled=is_mock_mode)
            if is_mock_mode:
                st.caption('当前为 Mock 模式，真实服务配置已锁定。')
            else:
                st.caption('DeepSeek API Key：已配置。留空保存会保留现有 Key。' if current_status['api_key_configured'] else 'DeepSeek API Key：未配置。')
            api_key_input = st.text_input('DeepSeek API Key', value='', type='password', placeholder='留空则保留现有 API Key' if not is_mock_mode else 'Mock 模式下无需填写', disabled=is_mock_mode)
            clear_api_key = st.checkbox('保存时清空当前 DeepSeek API Key', disabled=is_mock_mode)
            st.markdown('**外部检索服务**')
            st.caption('企查查 Token：已配置。留空保存会保留现有 Token。' if current_status['qcc_api_token_configured'] else '企查查 Token：未配置。')
            qcc_api_token_input = st.text_input('企查查 Token', value='', type='password', placeholder='留空则保留现有企查查 Token' if not is_mock_mode else 'Mock 模式下无需填写', disabled=is_mock_mode)
            clear_qcc_api_token = st.checkbox('保存时清空当前企查查 Token', disabled=is_mock_mode)
            st.caption('北大法宝 Token：已配置。留空保存会保留现有 Token。' if current_status['pkulaw_api_token_configured'] else '北大法宝 Token：未配置。')
            pkulaw_api_token_input = st.text_input('北大法宝 Token', value='', type='password', placeholder='留空则保留现有北大法宝 Token' if not is_mock_mode else 'Mock 模式下无需填写', disabled=is_mock_mode)
            clear_pkulaw_api_token = st.checkbox('保存时清空当前北大法宝 Token', disabled=is_mock_mode)
            submitted = st.form_submit_button('保存配置', type='primary', use_container_width=True)
        if submitted:
            validation_errors = []
            if clear_api_key and api_key_input.strip():
                validation_errors.append('已勾选清空 DeepSeek API Key 时，请不要同时输入新的 Key。')
            if clear_qcc_api_token and qcc_api_token_input.strip():
                validation_errors.append('已勾选清空企查查 Token 时，请不要同时输入新的 Token。')
            if clear_pkulaw_api_token and pkulaw_api_token_input.strip():
                validation_errors.append('已勾选清空北大法宝 Token 时，请不要同时输入新的 Token。')
            if validation_errors:
                for message in validation_errors:
                    st.error(message)
            else:
                final_api_key = '' if clear_api_key else api_key_input.strip() or current_settings['deepseek_api_key']
                final_qcc_api_token = '' if clear_qcc_api_token else qcc_api_token_input.strip() or current_settings['qcc_api_token']
                final_pkulaw_api_token = '' if clear_pkulaw_api_token else pkulaw_api_token_input.strip() or current_settings['pkulaw_api_token']
                save_runtime_settings(use_mock=preview_mode_label == 'Mock 模拟模式', llm_provider='deepseek', deepseek_api_key=final_api_key, deepseek_base_url=base_url.strip() or 'https://api.deepseek.com', qcc_api_token=final_qcc_api_token, pkulaw_api_token=final_pkulaw_api_token)
                accent_notice('系统配置已保存。当前页面会立即按新配置重新加载。')
                st.rerun()
    with col_status:
        form_section_title('当前状态')
        metric_cols = st.columns(2)
        with metric_cols[0]:
            metric_card('运行模式', current_status['mode_label'], '')
        with metric_cols[1]:
            metric_card('配置状态', '就绪' if current_status['ready'] else '待补充', '')
        service_cols_top = st.columns(2)
        with service_cols_top[0]:
            metric_card('DeepSeek', '已配置' if current_status['api_key_configured'] else '未配置', '')
        with service_cols_top[1]:
            metric_card('企查查', '已配置' if current_status['qcc_api_token_configured'] else '未配置', '')
        service_cols_bottom = st.columns(2)
        with service_cols_bottom[0]:
            metric_card('北大法宝', '已配置' if current_status['pkulaw_api_token_configured'] else '未配置', '')
        if not current_status['ready']:
            empty_state_notice('真实 Demo 模式下需要先配置 DeepSeek API Key，保存后即可发起真实评估。')
        if current_status.get('storage_notice'):
            accent_notice(current_status['storage_notice'])
        for warning in current_status['optional_warnings']:
            accent_notice(warning)
        st.caption(f"用户数据目录：{current_status['preferred_user_data_dir']}")
        st.caption(f"安装目录：{current_status['install_dir']}")
        st.caption(f"当前实际生效目录：{current_status['user_data_dir']}")
        st.caption('配置文件、数据库、缓存都会写入当前实际生效目录。')
        test_disabled = current_settings['use_mock'] or not current_status['api_key_configured']
        if current_settings['use_mock']:
            test_help = 'Mock 模式下不调用真实 DeepSeek，无法测试连接。'
        elif not current_status['api_key_configured']:
            test_help = '请先保存 DeepSeek API Key，再测试连接。'
        else:
            test_help = '测试当前已保存的 DeepSeek 配置是否可用。'
        with st.container(key='system_config_status_actions'):
            if st.button('测试 DeepSeek 连接', use_container_width=True, disabled=test_disabled, help=test_help):
                with st.spinner('正在测试 DeepSeek API 连接...'):
                    import llm_client
                    if llm_client.check_api_connection():
                        accent_notice('连接成功，真实 Demo 模式已可用。')
                    else:
                        st.error('连接失败。请检查 API Key、Base URL 或网络环境。')