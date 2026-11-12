"""Hệ thống Quản lý Ký túc xá Sinh viên - Web GUI (Python + Streamlit + MySQL 8.0)

File chạy chính của ứng dụng:
- Cấu hình giao diện Streamlit layout wide.
- Thanh Sidebar: Chọn Kỳ làm việc (Tháng/Năm) và Menu điều hướng 6 phân khu.
- Màn hình khởi đầu: Tổng quan Vận hành.
"""

import streamlit as st
from modules.dashboard import render_dashboard
from modules.reports import render_reports
from modules.trigger_validation import render_trigger_validation
from modules.room_management import render_room_management
from modules.parking_management import render_parking_management
from modules.service_guest_management import render_service_guest_management
import db

st.set_page_config(
    page_title="Quản lý Ký túc xá Sinh viên",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        [data-testid="stMetricValue"] {
            font-size: 1.8rem;
            color: #1E3A8A;
        }
        .stSidebar [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown(
        """
        <div style="text-align: center; padding: 10px 0 15px 0;">
            <h2 style="margin: 0; color: #1E3A8A;">KTX SINH VIÊN</h2>
            <p style="margin: 2px 0 0 0; font-size: 0.85rem; color: #64748B;">Hệ thống Vận hành & Quản lý</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Kỳ làm việc")
    col_thang, col_nam = st.columns(2)

    with col_thang:
        # Mặc định tháng 10/2026 khớp tập dữ liệu mẫu.
        danh_sach_thang = list(range(1, 13))
        thang_chon = st.selectbox(
            "Tháng",
            options=danh_sach_thang,
            index=9,
            format_func=lambda m: f"Tháng {m:02d}",
            help="Chọn tháng để lọc báo cáo và hóa đơn",
        )

    with col_nam:
        danh_sach_nam = [2024, 2025, 2026, 2027, 2028]
        nam_chon = st.selectbox(
            "Năm",
            options=danh_sach_nam,
            index=2,
            help="Chọn năm làm việc",
        )

    st.divider()

    st.markdown("### Menu Điều hướng")
    menu_options = [
        "Tổng quan",
        "Báo cáo & Hóa đơn",
        "Kiểm chứng Ràng buộc",
        "Quản lý Phòng ở",
        "Quản lý Bãi giữ xe",
        "Dịch vụ & Khách thăm",
    ]

    lua_chon_menu = st.radio(
        "Chọn phân khu chức năng:",
        options=menu_options,
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    try:
        df_ping = db.fetch_df("SELECT DATABASE() AS db_name;")
        db_name = df_ping["db_name"].iloc[0] if not df_ping.empty else "N/A"
        st.caption(f"CSDL đã kết nối: `{db_name}`")
    except Exception as ex:
        st.error(f"Mất kết nối CSDL: {ex}")

if lua_chon_menu == "Tổng quan":
    render_dashboard(thang_chon, nam_chon)

elif lua_chon_menu == "Báo cáo & Hóa đơn":
    render_reports(thang_chon, nam_chon)

elif lua_chon_menu == "Kiểm chứng Ràng buộc":
    render_trigger_validation()

elif lua_chon_menu == "Quản lý Phòng ở":
    render_room_management()

elif lua_chon_menu == "Quản lý Bãi giữ xe":
    render_parking_management()

elif lua_chon_menu == "Dịch vụ & Khách thăm":
    render_service_guest_management()
