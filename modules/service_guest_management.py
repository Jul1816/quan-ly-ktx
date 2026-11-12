"""Module Quan ly Dich vu va So truc Khach den tham.

Cung cap cac ham truy van va xu ly nghiep vu tang du lieu:
- Quan ly danh muc dich vu (bang dich_vu) va cap nhat don gia niem yet.
- Ghi nhan luot su dung dich vu cua sinh vien (bang su_dung_dich_vu).
- Tra cuu lich su su dung dich vu co bo loc sargable.
- Quan ly thong tin khach den tham va ghi nhan luot den tham bang Transaction nguyen tu.
- Tra cuu so truc khach den tham ket hop thong tin phong luu tru hien tai cua sinh vien.
"""

import datetime
from decimal import Decimal
from typing import Optional

import pandas as pd
import streamlit as st
import db
from modules.ui_helpers import (
    display_table,
    format_vnd,
    render_export_buttons,
    show_feedback,
    styled_header,
)

VALID_SERVICE_TYPES = ["GIAT_LA", "TRONG_XE", "THUE_XE", "AN_UONG", "KHAC"]


def get_students_dropdown() -> list[tuple[str, str]]:
    """Lấy danh sách sinh viên phục vụ selectbox lựa chọn trên giao diện.

    Trả về:
        Danh sách tuple dạng (ma_sv, nhan_hien_thi).
    """
    sql = """
    SELECT ma_sv, CONCAT(ma_sv, ' - ', ho_ten, ' (', COALESCE(lop, 'N/A'), ')') AS label
    FROM sinh_vien
    ORDER BY ma_sv ASC;
    """
    df = db.fetch_df(sql)
    if df.empty:
        return []
    return list(zip(df["ma_sv"].astype(str), df["label"].astype(str)))


def get_services_catalog() -> pd.DataFrame:
    """Truy van toan bo danh muc dich vu tu bang dich_vu.

    Tra ve:
        pd.DataFrame chua cac cot: ma_dv, ten_dv, loai_dv, don_gia.
    """
    sql = "SELECT ma_dv, ten_dv, loai_dv, don_gia FROM dich_vu ORDER BY ma_dv ASC;"
    return db.fetch_df(sql)


def add_service_usage(
    ma_sv: str,
    ma_dv: str,
    thoi_gian_su_dung: datetime.datetime,
    so_luong: int,
    don_gia_ap_dung: Decimal,
) -> tuple[bool, str]:
    """Ghi nhan luot su dung dich vu cua sinh vien vao bang su_dung_dich_vu.

    Tham so:
        ma_sv: Ma sinh vien.
        ma_dv: Ma dich vu.
        thoi_gian_su_dung: Thoi gian su dung dich vu.
        so_luong: So luong su dung (phai > 0).
        don_gia_ap_dung: Don gia ap dung tai thoi diem dung (>= 0).

    Tra ve:
        (True, "Ghi nhan su dung dich vu thanh cong.") hoac (False, thong_bao_loi).
    """
    clean_ma_sv = ma_sv.strip() if ma_sv else ""
    clean_ma_dv = ma_dv.strip() if ma_dv else ""

    if not clean_ma_sv:
        return False, "Mã sinh viên không được để trống."
    if not clean_ma_dv:
        return False, "Mã dịch vụ không được để trống."
    if so_luong <= 0:
        return False, "Số lượng sử dụng phải lớn hơn 0."
    if don_gia_ap_dung < 0:
        return False, "Đơn giá áp dụng không được âm."

    tg = (
        thoi_gian_su_dung.replace(microsecond=0)
        if thoi_gian_su_dung
        else datetime.datetime.now().replace(microsecond=0)
    )

    sql = """
    INSERT INTO su_dung_dich_vu (ma_sv, ma_dv, thoi_gian_su_dung, so_luong, don_gia_ap_dung)
    VALUES (%s, %s, %s, %s, %s);
    """
    success, msg = db.execute_query(
        sql, (clean_ma_sv, clean_ma_dv, tg, so_luong, don_gia_ap_dung)
    )
    if not success:
        return False, f"Lỗi ghi nhận sử dụng dịch vụ: {msg}"
    return True, "Ghi nhận sử dụng dịch vụ thành công."


def add_new_service(
    ma_dv: str,
    ten_dv: str,
    loai_dv: str,
    don_gia: Decimal,
) -> tuple[bool, str]:
    """Them dich vu moi vao danh muc dich vu (bang dich_vu).

    Tham so:
        ma_dv: Ma dich vu moi (VD: DV06).
        ten_dv: Ten dich vu.
        loai_dv: Loai dich vu, phai thuoc ENUM: GIAT_LA, TRONG_XE, THUE_XE, AN_UONG, KHAC.
        don_gia: Don gia niem yet (>= 0).

    Tra ve:
        (True, "Them dich vu moi thanh cong.") hoac (False, thong_bao_loi).
    """
    clean_ma_dv = ma_dv.strip().upper() if ma_dv else ""
    clean_ten_dv = ten_dv.strip() if ten_dv else ""
    clean_loai_dv = loai_dv.strip().upper() if loai_dv else ""

    if not clean_ma_dv:
        return False, "Mã dịch vụ không được để trống."
    if not clean_ten_dv:
        return False, "Tên dịch vụ không được để trống."
    if clean_loai_dv not in VALID_SERVICE_TYPES:
        return False, "Loại dịch vụ không hợp lệ. Phải thuộc: " + ", ".join(VALID_SERVICE_TYPES)
    if don_gia < 0:
        return False, "Đơn giá dịch vụ không được âm."

    sql = """
    INSERT INTO dich_vu (ma_dv, ten_dv, loai_dv, don_gia)
    VALUES (%s, %s, %s, %s);
    """
    success, msg = db.execute_query(
        sql, (clean_ma_dv, clean_ten_dv, clean_loai_dv, don_gia)
    )
    if not success:
        return False, f"Lỗi thêm dịch vụ: {msg}"
    return True, "Thêm dịch vụ mới thành công."


def update_service_price(ma_dv: str, don_gia: Decimal) -> tuple[bool, str]:
    """Cap nhat don gia niem yet cua dich vu trong bang dich_vu.

    Tham so:
        ma_dv: Ma dich vu can cap nhat.
        don_gia: Don gia moi (>= 0).

    Tra ve:
        (True, "Cap nhat don gia thanh cong.") hoac (False, thong_bao_loi).
    """
    clean_ma_dv = ma_dv.strip().upper() if ma_dv else ""
    if not clean_ma_dv:
        return False, "Mã dịch vụ không được để trống."
    if don_gia < 0:
        return False, "Đơn giá dịch vụ không được âm."

    sql = "UPDATE dich_vu SET don_gia = %s WHERE ma_dv = %s;"
    success, msg = db.execute_query(sql, (don_gia, clean_ma_dv))
    if not success:
        return False, f"Lỗi cập nhật đơn giá dịch vụ: {msg}"
    return True, "Cập nhật đơn giá dịch vụ thành công."


def get_service_usage_history(
    ma_sv: Optional[str] = None,
    ma_dv: Optional[str] = None,
    loai_dv: Optional[str] = None,
) -> pd.DataFrame:
    """Truy van lich su su dung dich vu ket hop thong tin sinh vien va dich vu.

    Tham so:
        ma_sv: Ma sinh vien can loc (neu co).
        ma_dv: Ma dich vu can loc (neu co).
        loai_dv: Loai dich vu can loc (neu co).

    Tra ve:
        pd.DataFrame chua cac cot: ma_sd, ma_sv, ho_ten, ma_dv, ten_dv,
        loai_dv, thoi_gian_su_dung, so_luong, don_gia_ap_dung, thanh_tien.
    """
    sql = """
    SELECT 
        sd.ma_sd,
        sd.ma_sv,
        s.ho_ten,
        sd.ma_dv,
        d.ten_dv,
        d.loai_dv,
        sd.thoi_gian_su_dung,
        sd.so_luong,
        sd.don_gia_ap_dung,
        (sd.so_luong * sd.don_gia_ap_dung) AS thanh_tien
    FROM su_dung_dich_vu sd
    JOIN sinh_vien s ON sd.ma_sv = s.ma_sv
    JOIN dich_vu d ON sd.ma_dv = d.ma_dv
    """
    conditions = []
    params = []

    if ma_sv:
        conditions.append("sd.ma_sv = %s")
        params.append(ma_sv.strip())
    if ma_dv:
        conditions.append("sd.ma_dv = %s")
        params.append(ma_dv.strip())
    if loai_dv:
        conditions.append("d.loai_dv = %s")
        params.append(loai_dv.strip().upper())

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    sql += " ORDER BY sd.thoi_gian_su_dung DESC, sd.ma_sd DESC;"
    return db.fetch_df(sql, tuple(params))


def get_existing_visitors() -> pd.DataFrame:
    """Lay danh sach thong tin khach da luu trong bang khach.

    Tra ve:
        pd.DataFrame chua cac cot: so_cmt, ten_khach, ngay_sinh.
    """
    sql = "SELECT so_cmt, ten_khach, ngay_sinh FROM khach ORDER BY ten_khach ASC;"
    return db.fetch_df(sql)


def record_guest_visit(
    so_cmt: str,
    ten_khach: str,
    ngay_sinh: Optional[datetime.date],
    ma_sv: str,
    ngay_den: datetime.datetime,
) -> tuple[bool, str]:
    """Ghi nhan luot khach den tham sinh vien bang Transaction nguyen tu.

    Neu khach da ton tai (khoa chinh so_cmt), tu dong cap nhat lai ho ten va ngay sinh
    qua cu phap ON DUPLICATE KEY UPDATE. Sau do them ban ghi vao luot_den_choi.

    Tham so:
        so_cmt: So CMND/CCCD cua khach.
        ten_khach: Ho ten khach den tham.
        ngay_sinh: Ngay sinh cua khach (co the None).
        ma_sv: Ma sinh vien duoc tham.
        ngay_den: Thoi diem khach den tham.

    Tra ve:
        (True, "Ghi nhan khach den tham thanh cong.") hoac (False, thong_bao_loi).
    """
    clean_cmt = so_cmt.strip() if so_cmt else ""
    clean_ten = ten_khach.strip() if ten_khach else ""
    clean_ma_sv = ma_sv.strip() if ma_sv else ""

    if not clean_cmt:
        return False, "Số CMT/CCCD của khách không được để trống."
    if not clean_ten:
        return False, "Tên khách đến thăm không được để trống."
    if not clean_ma_sv:
        return False, "Mã sinh viên được thăm không được để trống."
    if not ngay_den:
        return False, "Thời gian đến thăm không hợp lệ."

    clean_den = ngay_den.replace(microsecond=0)

    sql_khach = """
    INSERT INTO khach (so_cmt, ten_khach, ngay_sinh)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
        ten_khach = VALUES(ten_khach),
        ngay_sinh = COALESCE(VALUES(ngay_sinh), ngay_sinh);
    """
    sql_luot = """
    INSERT INTO luot_den_choi (so_cmt_khach, ma_sv, ngay_den)
    VALUES (%s, %s, %s);
    """
    operations = [
        (sql_khach, (clean_cmt, clean_ten, ngay_sinh)),
        (sql_luot, (clean_cmt, clean_ma_sv, clean_den)),
    ]
    success, msg = db.execute_transaction(operations)
    if not success:
        if "Duplicate entry" in msg or "uq_khach_sv_ngay_den" in msg:
            return False, "Khách này đã được ghi nhận đến thăm sinh viên vào đúng thời điểm trên."
        if "foreign key constraint fails" in msg.lower():
            return False, f"Không tìm thấy sinh viên có mã '{clean_ma_sv}' trong hệ thống."
        return False, f"Lỗi ghi nhận lượt khách thăm: {msg}"
    return True, "Ghi nhận khách đến thăm thành công."


def get_guest_visit_logs(ma_sv: Optional[str] = None) -> pd.DataFrame:
    """Truy van so truc khach den tham ket hop thong tin sinh vien va phong dang o.

    Tham so:
        ma_sv: Loc theo ma sinh vien (neu co).

    Tra ve:
        pd.DataFrame chua cac cot: ma_luot, ngay_den, so_cmt, ten_khach,
        ngay_sinh, ma_sv, ten_sinh_vien, lop, phong_hien_tai.
    """
    sql = """
    SELECT 
        l.ma_luot,
        l.ngay_den,
        k.so_cmt,
        k.ten_khach,
        k.ngay_sinh,
        s.ma_sv,
        s.ho_ten AS ten_sinh_vien,
        s.lop,
        COALESCE(ls.so_phong, 'Chưa xếp phòng') AS phong_hien_tai
    FROM luot_den_choi l
    JOIN khach k ON l.so_cmt_khach = k.so_cmt
    JOIN sinh_vien s ON l.ma_sv = s.ma_sv
    LEFT JOIN lich_su_o_phong ls ON s.ma_sv = ls.ma_sv AND ls.ngay_ra IS NULL
    """
    params = []
    if ma_sv:
        sql += " WHERE l.ma_sv = %s"
        params.append(ma_sv.strip())

    sql += " ORDER BY l.ngay_den DESC, l.ma_luot DESC;"
    return db.fetch_df(sql, tuple(params))


def render_tab1_services() -> None:
    """Tab 1: Sử dụng Dịch vụ & Quản lý danh mục (Bổ trợ 9)."""
    df_services = get_services_catalog()
    df_history_all = get_service_usage_history()

    # 1. 3 Metric chỉ số nhanh
    so_dv_niem_yet = len(df_services)
    so_luot_dung = len(df_history_all)
    tong_tien = (
        Decimal(str(df_history_all["thanh_tien"].sum()))
        if not df_history_all.empty and "thanh_tien" in df_history_all.columns
        else Decimal("0")
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Số dịch vụ niêm yết", so_dv_niem_yet)
    m2.metric("Số lượt dùng đã ghi nhận", so_luot_dung)
    m3.metric("Tổng tiền phát sinh", format_vnd(tong_tien))

    st.markdown("---")

    # 2. Form ghi nhận nhanh lượt dùng dịch vụ
    st.markdown("**Ghi nhận lượt sử dụng dịch vụ nội khu**")
    st.caption("Chọn sinh viên và dịch vụ từ danh mục. Đơn giá áp dụng được khóa cứng tự động theo giá niêm yết.")

    students = get_students_dropdown()
    if not students:
        st.warning("Chưa có dữ liệu sinh viên trong hệ thống.")
        return

    student_dict = dict(students)
    student_keys = [s[0] for s in students]

    col_sv, col_dv = st.columns(2)
    with col_sv:
        sel_ma_sv = st.selectbox(
            "Chọn sinh viên:",
            options=student_keys,
            format_func=lambda x: student_dict.get(x, x),
            key="tab1_sel_sv",
        )

    with col_dv:
        if df_services.empty:
            st.error("Chưa có dịch vụ nào trong danh mục. Vui lòng thêm dịch vụ mới bên dưới.")
            return

        service_dict = {
            r["ma_dv"]: f"{r['ma_dv']} - {r['ten_dv']} ({r['loai_dv']}) - {format_vnd(r['don_gia'])}"
            for _, r in df_services.iterrows()
        }
        service_keys = list(service_dict.keys())
        sel_ma_dv = st.selectbox(
            "Chọn dịch vụ:",
            options=service_keys,
            format_func=lambda x: service_dict.get(x, x),
            key="tab1_sel_dv",
        )

    # Lấy thông tin dịch vụ đã chọn
    selected_service_row = df_services[df_services["ma_dv"] == sel_ma_dv].iloc[0]
    don_gia_niem_yet = selected_service_row["don_gia"]

    col_gia, col_sl, col_ngay, col_gio = st.columns([1.5, 1, 1.25, 1.25])
    with col_gia:
        st.text_input(
            "Đơn giá áp dụng (VNĐ):",
            value=format_vnd(don_gia_niem_yet),
            disabled=True,
            key="tab1_txt_don_gia",
            help="Đơn giá niêm yết được cố định theo danh mục dịch vụ (Read-only).",
        )
    with col_sl:
        so_luong = st.number_input(
            "Số lượng:",
            min_value=1,
            value=1,
            step=1,
            key="tab1_num_so_luong",
        )
    with col_ngay:
        d_sd = st.date_input(
            "Ngày sử dụng:",
            value=datetime.date.today(),
            key="tab1_date_sd",
        )
    with col_gio:
        now_time = datetime.datetime.now().time().replace(microsecond=0)
        t_sd = st.time_input(
            "Giờ sử dụng:",
            value=now_time,
            key="tab1_time_sd",
        )

    # Hiển thị nổi bật thành tiền tạm tính
    thanh_tien_tam = Decimal(str(so_luong)) * Decimal(str(don_gia_niem_yet))
    st.markdown(
        f"""
        <div style="background-color: #F1F5F9; border-left: 4px solid #1E3A8A; padding: 10px 14px; border-radius: 4px; margin-bottom: 12px;">
            <span style="font-weight: 600; color: #1E3A8A; font-size: 1.05rem;">Thành tiền tạm tính: </span>
            <span style="font-weight: 700; color: #1E3A8A; font-size: 1.25rem;">{format_vnd(thanh_tien_tam)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    btn_save_service = st.button("Lưu lượt dùng dịch vụ", width="stretch", key="tab1_btn_save_sd")
    if btn_save_service:
        tg_su_dung = datetime.datetime.combine(d_sd, t_sd)
        suc, msg = add_service_usage(
            ma_sv=sel_ma_sv,
            ma_dv=sel_ma_dv,
            thoi_gian_su_dung=tg_su_dung,
            so_luong=int(so_luong),
            don_gia_ap_dung=Decimal(str(don_gia_niem_yet)),
        )
        show_feedback(suc, msg)
        if suc:
            st.rerun()

    st.markdown("---")

    # 3. Expander Quản lý danh mục Dịch vụ
    with st.expander("Quản lý danh mục Dịch vụ", expanded=False):
        col_add_dv, col_upd_dv = st.columns(2)

        with col_add_dv:
            st.markdown("**Thêm dịch vụ mới**")
            new_ma_dv = st.text_input("Mã dịch vụ mới (VD: DV06):", key="tab1_add_ma_dv")
            new_ten_dv = st.text_input("Tên dịch vụ mới:", key="tab1_add_ten_dv")
            new_loai_dv = st.selectbox(
                "Loại dịch vụ:",
                options=VALID_SERVICE_TYPES,
                key="tab1_add_loai_dv",
            )
            new_don_gia = st.number_input(
                "Đơn giá niêm yết (VNĐ):",
                min_value=0,
                value=10000,
                step=1000,
                key="tab1_add_don_gia",
            )
            btn_add_dv = st.button("Thêm dịch vụ mới", width="stretch", key="tab1_btn_add_dv")
            if btn_add_dv:
                suc, msg = add_new_service(
                    ma_dv=new_ma_dv,
                    ten_dv=new_ten_dv,
                    loai_dv=new_loai_dv,
                    don_gia=Decimal(str(new_don_gia)),
                )
                show_feedback(suc, msg)
                if suc:
                    st.rerun()

        with col_upd_dv:
            st.markdown("**Cập nhật đơn giá niêm yết**")
            if not df_services.empty:
                sel_upd_dv = st.selectbox(
                    "Chọn dịch vụ cần cập nhật giá:",
                    options=service_keys,
                    format_func=lambda x: service_dict.get(x, x),
                    key="tab1_upd_sel_dv",
                )
                curr_price_upd = df_services[df_services["ma_dv"] == sel_upd_dv].iloc[0]["don_gia"]
                upd_don_gia = st.number_input(
                    "Đơn giá mới (VNĐ):",
                    min_value=0,
                    value=int(round(float(curr_price_upd))),
                    step=1000,
                    key="tab1_upd_don_gia",
                )
                btn_upd_price = st.button("Cập nhật đơn giá", width="stretch", key="tab1_btn_upd_price")
                if btn_upd_price:
                    suc, msg = update_service_price(sel_upd_dv, Decimal(str(upd_don_gia)))
                    show_feedback(suc, msg)
                    if suc:
                        st.rerun()
            else:
                st.info("Chưa có dịch vụ nào để cập nhật.")

    st.markdown("---")

    # 4. Bảng nhật ký sử dụng dịch vụ gần đây kèm bộ lọc
    st.markdown("**Nhật ký sử dụng dịch vụ gần đây**")
    col_filter_sv, col_filter_dv, col_filter_loai = st.columns(3)

    with col_filter_sv:
        filter_sv_opts = [("TAT_CA", "Tất cả sinh viên")] + students
        filter_sv_dict = dict(filter_sv_opts)
        sel_filter_sv = st.selectbox(
            "Lọc theo sinh viên:",
            options=[x[0] for x in filter_sv_opts],
            format_func=lambda x: filter_sv_dict.get(x, x),
            key="tab1_filter_sv",
        )

    with col_filter_dv:
        filter_dv_opts = [("TAT_CA", "Tất cả dịch vụ")] + [
            (r["ma_dv"], f"{r['ma_dv']} - {r['ten_dv']}")
            for _, r in df_services.iterrows()
        ]
        filter_dv_dict = dict(filter_dv_opts)
        sel_filter_dv = st.selectbox(
            "Lọc theo dịch vụ:",
            options=[x[0] for x in filter_dv_opts],
            format_func=lambda x: filter_dv_dict.get(x, x),
            key="tab1_filter_dv",
        )

    with col_filter_loai:
        filter_loai_opts = ["Tất cả loại dịch vụ"] + VALID_SERVICE_TYPES
        sel_filter_loai = st.selectbox(
            "Lọc theo loại dịch vụ:",
            options=filter_loai_opts,
            key="tab1_filter_loai",
        )

    param_sv = None if sel_filter_sv == "TAT_CA" else sel_filter_sv
    param_dv = None if sel_filter_dv == "TAT_CA" else sel_filter_dv
    param_loai = None if sel_filter_loai == "Tất cả loại dịch vụ" else sel_filter_loai
    df_history = get_service_usage_history(ma_sv=param_sv, ma_dv=param_dv, loai_dv=param_loai)

    if df_history.empty:
        st.info("Không có dữ liệu lượt sử dụng dịch vụ phù hợp với bộ lọc.")
    else:
        df_display = df_history.copy()
        if "don_gia_ap_dung" in df_display.columns:
            df_display["don_gia_ap_dung"] = df_display["don_gia_ap_dung"].apply(format_vnd)
        if "thanh_tien" in df_display.columns:
            df_display["thanh_tien"] = df_display["thanh_tien"].apply(format_vnd)

        df_display = df_display.rename(
            columns={
                "ma_sd": "Mã SD",
                "ma_sv": "Mã SV",
                "ho_ten": "Họ tên sinh viên",
                "ma_dv": "Mã DV",
                "ten_dv": "Tên dịch vụ",
                "loai_dv": "Loại dịch vụ",
                "thoi_gian_su_dung": "Thời gian sử dụng",
                "so_luong": "Số lượng",
                "don_gia_ap_dung": "Đơn giá áp dụng",
                "thanh_tien": "Thành tiền",
            }
        )
        display_table(df_display, height=350)
        render_export_buttons(
            df_history, "nhat_ky_su_dung_dich_vu", key_prefix="tab1_export_history"
        )


def render_tab2_guest_book() -> None:
    """Tab 2: Sổ trực Khách thăm (Bổ trợ 9)."""
    st.markdown("**Ghi nhận khách đến thăm ký túc xá**")
    st.caption("Quản lý thông tin khách vào thăm sinh viên nội trú. Hệ thống liên kết tự động với phòng lưu trú hiện tại của sinh viên.")

    students = get_students_dropdown()
    if not students:
        st.warning("Chưa có dữ liệu sinh viên trong hệ thống.")
        return

    student_dict = dict(students)
    student_keys = [s[0] for s in students]

    # Form ghi nhận khách vào KTX
    mode_khach = st.radio(
        "Chọn đối tượng khách:",
        options=["Khách đã có trong sổ trực", "Khách mới lần đầu đến KTX"],
        horizontal=True,
        key="tab2_mode_khach",
    )

    df_existing_visitors = get_existing_visitors()
    so_cmt_val = ""
    ten_khach_val = ""
    ngay_sinh_val = None

    if mode_khach == "Khách đã có trong sổ trực":
        if df_existing_visitors.empty:
            st.info("Chưa có thông tin khách cũ trong hệ thống. Vui lòng chuyển sang 'Khách mới lần đầu đến KTX'.")
        else:
            visitor_dict = {
                r["so_cmt"]: f"{r['so_cmt']} - {r['ten_khach']}"
                for _, r in df_existing_visitors.iterrows()
            }
            visitor_keys = list(visitor_dict.keys())
            sel_cmt = st.selectbox(
                "Chọn khách từ danh sách đã lưu:",
                options=visitor_keys,
                format_func=lambda x: visitor_dict.get(x, x),
                key="tab2_sel_existing_visitor",
            )
            matched_visitor = df_existing_visitors[df_existing_visitors["so_cmt"] == sel_cmt].iloc[0]
            so_cmt_val = matched_visitor["so_cmt"]
            ten_khach_val = matched_visitor["ten_khach"]
            ngay_sinh_val = matched_visitor["ngay_sinh"]
            ns_display = str(ngay_sinh_val) if ngay_sinh_val else "Chưa có thông tin"
            st.caption(f"Họ tên khách: **{ten_khach_val}** | Số CMT/CCCD: **{so_cmt_val}** | Ngày sinh: **{ns_display}**")
    else:
        col_cmt, col_ten, col_ns = st.columns([1.5, 2, 1.5])
        with col_cmt:
            so_cmt_val = st.text_input(
                "Số CMT / CCCD:",
                key="tab2_new_cmt",
                placeholder="Nhập số CMT hoặc CCCD…",
            )
        with col_ten:
            ten_khach_val = st.text_input(
                "Họ tên khách:",
                key="tab2_new_ten",
                placeholder="Nhập đầy đủ họ tên khách…",
            )
        with col_ns:
            chk_dob = st.checkbox("Có ngày sinh", value=True, key="tab2_chk_dob")
            if chk_dob:
                ngay_sinh_val = st.date_input(
                    "Ngày sinh:",
                    value=datetime.date(2000, 1, 1),
                    min_value=datetime.date(1940, 1, 1),
                    max_value=datetime.date.today(),
                    key="tab2_new_ns",
                )
            else:
                ngay_sinh_val = None

    col_sv, col_den_d, col_den_t = st.columns([2, 1.25, 1.25])
    with col_sv:
        sel_ma_sv_visit = st.selectbox(
            "Sinh viên được thăm:",
            options=student_keys,
            format_func=lambda x: student_dict.get(x, x),
            key="tab2_sel_sv_visit",
        )
    with col_den_d:
        d_den = st.date_input(
            "Ngày đến:",
            value=datetime.date.today(),
            key="tab2_d_den",
        )
    with col_den_t:
        now_time = datetime.datetime.now().time().replace(microsecond=0)
        t_den = st.time_input(
            "Giờ đến:",
            value=now_time,
            key="tab2_t_den",
        )

    btn_record_visit = st.button("Ghi nhận khách vào KTX", width="stretch", key="tab2_btn_record_visit")
    if btn_record_visit:
        clean_cmt = so_cmt_val.strip() if so_cmt_val else ""
        clean_ten = ten_khach_val.strip() if ten_khach_val else ""
        if not clean_cmt:
            st.error("Lỗi: Số CMT / CCCD của khách không được để trống.")
        elif not clean_ten:
            st.error("Lỗi: Họ tên khách đến thăm không được để trống.")
        else:
            tg_den = datetime.datetime.combine(d_den, t_den)
            suc, msg = record_guest_visit(
                so_cmt=clean_cmt,
                ten_khach=clean_ten,
                ngay_sinh=ngay_sinh_val,
                ma_sv=sel_ma_sv_visit,
                ngay_den=tg_den,
            )
            if not suc and ("đúng thời điểm" in msg or "uq_khach_sv_ngay_den" in msg or "Duplicate entry" in msg):
                st.error("Khách này đã được ghi nhận đến thăm cùng sinh viên vào thời điểm này.")
            else:
                show_feedback(suc, msg)
                if suc:
                    st.rerun()

    st.markdown("---")

    # Bảng nhật ký khách đến thăm gần đây
    st.markdown("**Sổ trực nhật ký khách đến thăm gần đây**")
    filter_sv_opts = [("TAT_CA", "Tất cả sinh viên")] + students
    filter_sv_dict = dict(filter_sv_opts)
    sel_guest_filter_sv = st.selectbox(
        "Lọc sổ trực theo sinh viên:",
        options=[x[0] for x in filter_sv_opts],
        format_func=lambda x: filter_sv_dict.get(x, x),
        key="tab2_filter_sv_guest",
    )

    param_guest_sv = None if sel_guest_filter_sv == "TAT_CA" else sel_guest_filter_sv
    df_guest_logs = get_guest_visit_logs(ma_sv=param_guest_sv)

    if df_guest_logs.empty:
        st.info("Chưa có lượt khách nào trong sổ trực phù hợp với điều kiện lọc.")
    else:
        df_guest_display = df_guest_logs.rename(
            columns={
                "ma_luot": "Mã lượt",
                "ngay_den": "Thời gian đến",
                "so_cmt": "Số CMT / CCCD",
                "ten_khach": "Họ tên khách",
                "ngay_sinh": "Ngày sinh",
                "ma_sv": "Mã SV",
                "ten_sinh_vien": "Sinh viên được thăm",
                "lop": "Lớp",
                "phong_hien_tai": "Phòng lưu trú hiện tại",
            }
        )
        display_table(df_guest_display, height=350)
        render_export_buttons(
            df_guest_logs, "so_truc_khach_den_tham", key_prefix="tab2_export_guest"
        )


def render_service_guest_management() -> None:
    """Điều phối toàn bộ phân khu Ghi nhận Dịch vụ & Khách thăm (Bổ trợ 9)."""
    styled_header(
        "GHI NHẬN DỊCH VỤ & KHÁCH THĂM",
        "Ghi nhận sinh viên sử dụng dịch vụ nội khu và sổ trực khách ghé thăm ký túc xá.",
    )

    tab1, tab2 = st.tabs([
        "Sử dụng Dịch vụ (Bổ trợ 9)",
        "Sổ trực Khách thăm (Bổ trợ 9)",
    ])

    with tab1:
        render_tab1_services()
    with tab2:
        render_tab2_guest_book()

