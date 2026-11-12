"""Module Kiểm chứng Ràng buộc Trigger.

Cung cấp các hàm nghiệp vụ và giao diện kiểm thử:
- Tầng Dữ liệu & Xử lý Logic: Truy vấn thông tin trigger, audit phí lượt xe, chạy kịch bản test lỗi.
- Tầng Giao diện: Hiển thị danh sách trigger, thẻ tương tác kiểm thử vi phạm và bảng audit phí lượt xe.
Tuyệt đối không sử dụng bất kỳ icon hoặc emoji nào.
"""

import pandas as pd
import streamlit as st
import db
from modules.ui_helpers import (
    display_table,
    format_vnd,
    render_export_buttons,
    styled_header,
)

# Định nghĩa 4 kịch bản kiểm thử vi phạm ràng buộc trigger từ mục 5 của 2.sql
TRIGGER_TEST_SCENARIOS = {
    1: {
        "title": "Kịch bản 1: Xếp sinh viên vào phòng đã đầy",
        "description": "Kiểm chứng trigger trg_phong_insert chặn xếp thêm sinh viên SV006 vào phòng A102 đã đạt tối đa 2/2 người.",
        "sql": "INSERT INTO lich_su_o_phong (ma_sv, so_phong, ngay_vao, ngay_ra, don_gia_ap_dung) VALUES ('SV006', 'A102', '2026-10-25', NULL, 650000);",
        "cleanup": "DELETE FROM lich_su_o_phong WHERE ma_sv = 'SV006' AND so_phong = 'A102' AND ngay_vao = '2026-10-25';",
        "button_label": "Chạy kiểm thử kịch bản 1",
    },
    2: {
        "title": "Kịch bản 2: Xếp sinh viên trùng khoảng thời gian ở",
        "description": "Kiểm chứng trigger trg_phong_insert chặn xếp sinh viên SV002 vào phòng B201 vì đang có lịch ở phòng A101.",
        "sql": "INSERT INTO lich_su_o_phong (ma_sv, so_phong, ngay_vao, ngay_ra, don_gia_ap_dung) VALUES ('SV002', 'B201', '2026-10-20', NULL, 300000);",
        "cleanup": "DELETE FROM lich_su_o_phong WHERE ma_sv = 'SV002' AND so_phong = 'B201' AND ngay_vao = '2026-10-20';",
        "button_label": "Chạy kiểm thử kịch bản 2",
    },
    3: {
        "title": "Kịch bản 3: Đăng ký xe vé tháng thứ 3",
        "description": "Kiểm chứng trigger trg_xe_insert chặn sinh viên SV001 đăng ký xe thứ 3 vượt quá giới hạn 2 xe cùng thời điểm.",
        "sql": "INSERT INTO xe_ve_thang (bien_so, ma_sv, loai_xe, ngay_dang_ky, ngay_huy) VALUES ('29A-33333', 'SV001', 'Xe may AirBlade', '2026-10-15', NULL);",
        "cleanup": "DELETE FROM xe_ve_thang WHERE bien_so = '29A-33333';",
        "button_label": "Chạy kiểm thử kịch bản 3",
    },
    4: {
        "title": "Kịch bản 4: Gửi xe trước ngày đăng ký vé tháng",
        "description": "Kiểm chứng trigger trg_luot_xe_insert chặn lượt gửi xe khi vé tháng chưa có hiệu lực tại thời điểm gửi.",
        "sql": "INSERT INTO luot_gui_lay_xe (bien_so, thoi_gian_gui, thoi_gian_lay) VALUES ('15B-55555', '2026-10-01 08:00:00', '2026-10-01 10:00:00');",
        "cleanup": "DELETE FROM luot_gui_lay_xe WHERE bien_so = '15B-55555' AND thoi_gian_gui = '2026-10-01 08:00:00';",
        "button_label": "Chạy kiểm thử kịch bản 4",
    },
}


def get_triggers_status() -> pd.DataFrame:
    """Truy van thong tin cac trigger he thong tu information_schema."""
    query = """
    SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, ACTION_TIMING
    FROM information_schema.TRIGGERS
    WHERE TRIGGER_SCHEMA = DATABASE()
    ORDER BY TRIGGER_NAME;
    """
    return db.fetch_df(query)


def get_parking_fee_audit() -> pd.DataFrame:
    """Truy van lich su luot gui xe de kiem chung tinh phi tu dong."""
    query = """
    SELECT ma_luot, bien_so, thoi_gian_gui, thoi_gian_lay, so_tien_phai_tra
    FROM luot_gui_lay_xe
    ORDER BY ma_luot;
    """
    return db.fetch_df(query)


def run_trigger_test(test_id: int) -> tuple[bool, str, str]:
    """Thuc thi mot trong 4 kich ban kiem thu trigger vi pham va tra ve ket qua bat loi.

    Tra ve:
        (thanh_cong, cau_lenh_sql, thong_diep_loi).
        Khi trigger chan loi dung ky vong, thanh_cong se la False va thong_diep_loi chua thong bao tu MySQL.
    """
    if test_id not in TRIGGER_TEST_SCENARIOS:
        return False, "", f"Kich ban test khong ton tai: {test_id}"

    scenario = TRIGGER_TEST_SCENARIOS[test_id]
    sql_insert = scenario["sql"]
    sql_cleanup = scenario["cleanup"]

    ok = False
    msg = ""
    try:
        ok, msg = db.execute_query(sql_insert)
        return ok, sql_insert, msg
    finally:
        # Neu lenh INSERT khong bi chan (khong xay ra), tu dong xoa ban ghi de bao ve CSDL
        if ok:
            db.execute_query(sql_cleanup)


def render_trigger_validation() -> None:
    """Hiển thị toàn bộ màn hình kiểm chứng ràng buộc trigger và tính phí lượt xe."""
    styled_header(
        "Kiểm chứng Ràng buộc",
        "Thử nghiệm trực quan cơ chế chặn lỗi toàn vẹn và tính phí tự động của Trigger MySQL 8.0",
    )

    st.markdown("### 1. Danh sách Trigger hệ thống đang hoạt động")
    df_trg = get_triggers_status()
    df_trg_display = df_trg.rename(
        columns={
            "TRIGGER_NAME": "Tên Trigger",
            "EVENT_MANIPULATION": "Sự kiện",
            "EVENT_OBJECT_TABLE": "Bảng tác động",
            "ACTION_TIMING": "Thời điểm",
        }
    )
    display_table(df_trg_display)

    st.markdown("### 2. Thử nghiệm vi phạm ràng buộc toàn vẹn")
    st.markdown(
        "Nhấn từng nút để thử nghiệm các hành vi vi phạm dữ liệu mẫu. "
        "Hệ thống sẽ gọi trực tiếp câu lệnh INSERT vào MySQL để kiểm chứng cơ chế bắt lỗi SIGNAL SQLSTATE '45000' và rollback tự động."
    )

    col1, col2 = st.columns(2)
    cards = [
        (col1, 1),
        (col2, 2),
        (col1, 3),
        (col2, 4),
    ]

    for col, tid in cards:
        scenario = TRIGGER_TEST_SCENARIOS[tid]
        with col:
            with st.container(border=True):
                st.markdown(f"**{scenario['title']}**")
                st.caption(f"Mục tiêu: {scenario['description']}")
                st.code(scenario["sql"], language="sql")
                if st.button(scenario["button_label"], key=f"btn_trg_test_{tid}", width="stretch"):
                    ok, _, msg = run_trigger_test(tid)
                    if not ok:
                        st.error(f"Lỗi bắt được từ Trigger: {msg}")
                        st.info("Trạng thái: Trigger chặn vi phạm thành công, giao dịch đã được rollback an toàn.")
                    else:
                        st.warning("Cảnh báo: Lệnh INSERT đã thực thi mà không bị chặn. Bản ghi đã được dọn dẹp tự động.")

    st.markdown("### 3. Kiểm chứng tính phí lượt xe tự động")
    st.markdown(
        "Quy tắc áp phí của trigger trg_luot_xe_insert: "
        "Mỗi sinh viên được miễn phí 2 lượt gửi/lấy xe đầu tiên trong ngày. "
        "Từ lượt thứ 3 trở đi trong cùng ngày, hệ thống tự động áp dụng mức phụ thu 3.000\u00a0đ/lượt."
    )

    df_audit = get_parking_fee_audit()
    df_audit_display = df_audit.copy()
    df_audit_display["so_tien_phai_tra"] = df_audit_display["so_tien_phai_tra"].apply(format_vnd)
    df_audit_display = df_audit_display.rename(
        columns={
            "ma_luot": "Mã lượt",
            "bien_so": "Biển số xe",
            "thoi_gian_gui": "Thời gian gửi",
            "thoi_gian_lay": "Thời gian lấy",
            "so_tien_phai_tra": "Số tiền phải trả",
        }
    )
    display_table(df_audit_display)
    render_export_buttons(df_audit, file_prefix="kiem_chung_phi_luot_xe", key_prefix="audit_parking")
