"""Module Quản lý Bãi giữ xe và Xe vãng lai.

Cung cấp các hàm truy vấn và xử lý nghiệp vụ tầng dữ liệu:
- Quản lý thẻ xe vé tháng của sinh viên (đăng ký, hủy thẻ, tra cứu danh sách).
- Ghi nhận lượt gửi/lấy xe vé tháng và kiểm soát phụ thu tự động qua Trigger MySQL.
- Tra cứu nhật ký lượt gửi/lấy xe với các bộ lọc sargable.
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
    set_flash_feedback,
    show_feedback,
    styled_header,
)


def get_don_gia_dv(ma_dv: str, fallback: float = 0.0) -> float:
    """Lấy đơn giá dịch vụ từ DB theo mã dịch vụ.

    Dùng để đồng bộ giá xe vãng lai (DV02) với bảng dich_vu,
    tránh hardcode khi admin cập nhật đơn giá.
    """
    df = db.fetch_df(
        "SELECT don_gia FROM dich_vu WHERE ma_dv = %s LIMIT 1;",
        (ma_dv.strip(),),
    )
    if df.empty:
        return fallback
    return float(df.iloc[0]["don_gia"])


def get_monthly_tickets(only_active: bool = False) -> pd.DataFrame:
    """Truy van danh sach ve xe thang ket hop thong tin sinh vien tu bang sinh_vien.

    Tham so:
        only_active: Neu True, chi lay cac ve xe con hieu luc (ngay_huy IS NULL).

    Tra ve:
        pd.DataFrame chua cac cot: bien_so, ma_sv, ho_ten, loai_xe,
        ngay_dang_ky, ngay_huy, trang_thai.
    """
    sql = """
    SELECT 
        x.bien_so,
        x.ma_sv,
        s.ho_ten,
        x.loai_xe,
        x.ngay_dang_ky,
        x.ngay_huy,
        CASE 
            WHEN x.ngay_huy IS NULL THEN 'Còn hiệu lực'
            ELSE 'Đã hủy'
        END AS trang_thai
    FROM xe_ve_thang x
    JOIN sinh_vien s ON x.ma_sv = s.ma_sv
    """
    if only_active:
        sql += " WHERE x.ngay_huy IS NULL"
    sql += " ORDER BY x.ngay_dang_ky DESC, x.bien_so ASC;"
    return db.fetch_df(sql)


def get_active_students_dropdown() -> list[tuple[str, str]]:
    """Lay danh sach sinh vien phuc vu selectbox lua chon tren giao dien.

    Tra ve:
        Danh sach tuple dang (ma_sv, nhan_hien_thi).
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


def register_monthly_ticket(
    bien_so: str, ma_sv: str, loai_xe: str, ngay_dang_ky: datetime.date
) -> tuple[bool, str]:
    """Dang ky ve xe thang cho sinh vien.

    Chuan hoa bien so viet hoa va cat khoang trang. Bat loi trigger trg_xe_insert
    khi vuot qua gioi han 2 xe ve thang cung thoi diem.

    Tra ve:
        (True, "Dang ky ve xe thang thanh cong.") hoac (False, thong_bao_loi).
    """
    clean_bien_so = bien_so.strip().upper() if bien_so else ""
    clean_ma_sv = ma_sv.strip() if ma_sv else ""
    clean_loai = loai_xe.strip() if loai_xe else ""

    if not clean_bien_so:
        return False, "Biển số xe không được để trống."
    if not clean_ma_sv:
        return False, "Mã sinh viên không được để trống."
    if not clean_loai:
        return False, "Loại xe không được để trống."
    if not ngay_dang_ky:
        return False, "Ngày đăng ký không hợp lệ."

    sql = """
    INSERT INTO xe_ve_thang (bien_so, ma_sv, loai_xe, ngay_dang_ky, ngay_huy)
    VALUES (%s, %s, %s, %s, NULL);
    """
    success, msg = db.execute_query(
        sql, (clean_bien_so, clean_ma_sv, clean_loai, ngay_dang_ky)
    )
    if success:
        return True, "Đăng ký vé xe tháng thành công."
    return False, msg


def cancel_monthly_ticket(bien_so: str, ngay_huy: datetime.date) -> tuple[bool, str]:
    """Huy ve xe thang bang cach cap nhat ngay_huy vao CSDL.

    Tra ve:
        (True, "Huy ve xe thang thanh cong.") hoac (False, thong_bao_loi).
    """
    clean_bien_so = bien_so.strip().upper() if bien_so else ""
    if not clean_bien_so:
        return False, "Biển số xe không được để trống."
    if not ngay_huy:
        return False, "Ngày hủy không hợp lệ."

    sql = "UPDATE xe_ve_thang SET ngay_huy = %s WHERE bien_so = %s;"
    success, msg = db.execute_query(sql, (ngay_huy, clean_bien_so))
    if success:
        return True, "Hủy vé xe tháng thành công."
    return False, msg


def record_parking_turn(
    bien_so: str,
    thoi_gian_gui: datetime.datetime,
    thoi_gian_lay: datetime.datetime,
) -> tuple[bool, str, Optional[Decimal], int]:
    """Ghi nhan luot gui va lay xe ve thang vao bang luot_gui_lay_xe.

    Kiem tra validation thoi gian lay xe phai sau thoi gian gui.
    Kiem tra trigger trg_luot_xe_insert (xe co ve thang con hieu luc).
    Tu dong tinh phi theo trigger (2 luot dau trong ngay 0d, tu luot thu 3 phu thu 3.000d).
    Dem tong so luot trong ngay bang truy van sargable.

    Tra ve:
        (success, thong_bao, so_tien_phai_tra, so_luot_trong_ngay).
    """
    if thoi_gian_lay <= thoi_gian_gui:
        return False, "Thời gian lấy xe phải sau thời gian gửi", None, 0

    clean_bien_so = bien_so.strip().upper() if bien_so else ""
    if not clean_bien_so:
        return False, "Biển số xe không được để trống.", None, 0

    tg_gui = thoi_gian_gui.replace(microsecond=0)
    tg_lay = thoi_gian_lay.replace(microsecond=0)

    sql_insert = """
    INSERT INTO luot_gui_lay_xe (bien_so, thoi_gian_gui, thoi_gian_lay)
    VALUES (%s, %s, %s);
    """
    success, err_msg = db.execute_query(sql_insert, (clean_bien_so, tg_gui, tg_lay))
    if not success:
        return False, err_msg, None, 0

    # Truy van so tien phai tra do Trigger trg_luot_xe_insert tu dong tinh va luu
    sql_fee = """
    SELECT so_tien_phai_tra 
    FROM luot_gui_lay_xe 
    WHERE bien_so = %s AND thoi_gian_gui = %s;
    """
    df_fee = db.fetch_df(sql_fee, (clean_bien_so, tg_gui))
    so_tien_phai_tra = (
        Decimal(str(df_fee["so_tien_phai_tra"].iloc[0]))
        if not df_fee.empty
        else Decimal("0.00")
    )

    # Dem sargable so luot gui xe trong cung ngay tinh den thoi diem luot gui hien tai
    start_of_day = datetime.datetime.combine(tg_gui.date(), datetime.time.min)
    sql_count = """
    SELECT COUNT(*) AS c 
    FROM luot_gui_lay_xe 
    WHERE bien_so = %s AND thoi_gian_gui >= %s AND thoi_gian_gui <= %s;
    """
    df_count = db.fetch_df(sql_count, (clean_bien_so, start_of_day, tg_gui))
    turn_count = int(df_count["c"].iloc[0]) if not df_count.empty else 1

    return True, "Ghi nhận lượt gửi/lấy xe thành công.", so_tien_phai_tra, turn_count


def get_parking_logs(
    bien_so: Optional[str] = None, ngay_gui: Optional[datetime.date] = None
) -> pd.DataFrame:
    """Truy van nhat ky luot gui/lay xe kem thong tin sinh vien chu so huu.

    Tham so:
        bien_so: Bien so xe can loc (khop chinh xac hoac tim kiem gan dung).
        ngay_gui: Ngay gui can tra cuu (truy van sargable tu 00:00 den het ngay).

    Tra ve:
        pd.DataFrame danh sach luot xe sap xep giam dan theo thoi_gian_gui.
    """
    sql = """
    SELECT 
        l.ma_luot,
        l.bien_so,
        x.ma_sv,
        s.ho_ten,
        x.loai_xe,
        l.thoi_gian_gui,
        l.thoi_gian_lay,
        l.so_tien_phai_tra
    FROM luot_gui_lay_xe l
    JOIN xe_ve_thang x ON l.bien_so = x.bien_so
    JOIN sinh_vien s ON x.ma_sv = s.ma_sv
    WHERE 1=1
    """
    params = []
    if bien_so and bien_so.strip():
        sql += " AND l.bien_so LIKE %s"
        params.append(f"%{bien_so.strip().upper()}%")
    if ngay_gui:
        start_dt = datetime.datetime.combine(ngay_gui, datetime.time.min)
        end_dt = start_dt + datetime.timedelta(days=1)
        sql += " AND l.thoi_gian_gui >= %s AND l.thoi_gian_gui < %s"
        params.extend([start_dt, end_dt])
    sql += " ORDER BY l.thoi_gian_gui DESC;"
    return db.fetch_df(sql, tuple(params))


def render_tab1_monthly_tickets() -> None:
    """Tab 1: Quản lý vé xe tháng của sinh viên."""
    df_tickets = get_monthly_tickets()

    # 1. Hiển thị 3 chỉ số nhanh
    tong_so_the = len(df_tickets)
    the_hieu_luc = (
        len(df_tickets[df_tickets["trang_thai"] == "Còn hiệu lực"])
        if not df_tickets.empty
        else 0
    )
    the_da_huy = (
        len(df_tickets[df_tickets["trang_thai"] == "Đã hủy"])
        if not df_tickets.empty
        else 0
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Tổng số thẻ xe", tong_so_the)
    m2.metric("Số thẻ còn hiệu lực", the_hieu_luc)
    m3.metric("Số thẻ đã hủy", the_da_huy)

    st.markdown("---")

    # 2. Bảng danh sách thẻ xe có ô tìm kiếm
    st.markdown("**Danh sách Thẻ xe vé tháng**")
    search_kw = st.text_input(
        "Tìm kiếm thẻ xe (Biển số hoặc Họ tên sinh viên):",
        key="tab1_search_kw",
        placeholder="Nhập biển số xe hoặc tên sinh viên…",
    )

    df_filtered = df_tickets.copy()
    if search_kw.strip() and not df_filtered.empty:
        kw = search_kw.strip().upper()
        df_filtered = df_filtered[
            df_filtered["bien_so"].str.upper().str.contains(kw, na=False)
            | df_filtered["ho_ten"].str.upper().str.contains(kw, na=False)
        ]

    if not df_filtered.empty:
        df_display = df_filtered.rename(
            columns={
                "bien_so": "Biển số",
                "ma_sv": "Mã SV",
                "ho_ten": "Họ và tên",
                "loai_xe": "Loại xe",
                "ngay_dang_ky": "Ngày đăng ký",
                "ngay_huy": "Ngày hủy",
                "trang_thai": "Trạng thái",
            }
        )
        display_table(df_display, height=280)
    else:
        st.info("Không tìm thấy thẻ xe phù hợp với điều kiện tìm kiếm.")

    st.markdown("---")

    # 3. Hai cột bên dưới: Đăng ký mới và Hủy vé xe
    col_reg, col_cancel = st.columns(2)

    with col_reg:
        st.markdown("**Đăng ký vé xe tháng mới**")
        st.caption(
            "Đơn giá cố định: 100.000 VNĐ/tháng (thu qua hóa đơn phòng). "
            "Mỗi sinh viên được đăng ký tối đa 2 xe cùng thời điểm."
        )
        students = get_active_students_dropdown()
        if not students:
            st.warning("Chưa có dữ liệu sinh viên trong hệ thống.")
        else:
            with st.form("form_register_monthly_ticket"):
                student_options = [s[0] for s in students]
                student_labels = {s[0]: s[1] for s in students}
                sel_ma_sv = st.selectbox(
                    "Chọn sinh viên:",
                    options=student_options,
                    format_func=lambda x: student_labels.get(x, x),
                    key="tab1_reg_student",
                )
                reg_bien_so = st.text_input(
                    "Biển số xe (ví dụ: 29A-12345):",
                    key="tab1_reg_bien_so",
                )
                reg_loai_xe = st.text_input(
                    "Loại xe (ví dụ: Xe máy Honda Wave Alpha):",
                    key="tab1_reg_loai_xe",
                )
                reg_ngay_dk = st.date_input(
                    "Ngày đăng ký:",
                    value=datetime.date.today(),
                    key="tab1_reg_ngay_dk",
                )
                btn_reg = st.form_submit_button("Đăng ký vé tháng", width="stretch")
                if btn_reg:
                    ok, msg = register_monthly_ticket(
                        bien_so=reg_bien_so,
                        ma_sv=sel_ma_sv,
                        loai_xe=reg_loai_xe,
                        ngay_dang_ky=reg_ngay_dk,
                    )
                    if ok:
                        clean_bs = reg_bien_so.strip().upper()
                        set_flash_feedback(
                            True,
                            f"Đã đăng ký vé tháng cho xe {clean_bs} thành công!",
                        )
                        st.rerun()
                    else:
                        show_feedback(False, msg)

    with col_cancel:
        st.markdown("**Hủy vé xe tháng**")
        st.caption(
            "Cập nhật ngày hủy cho thẻ xe. Sau khi hủy, thẻ xe sẽ không còn được hưởng "
            "chính sách vé tháng khi gửi xe."
        )
        df_active = (
            df_tickets[df_tickets["trang_thai"] == "Còn hiệu lực"]
            if not df_tickets.empty
            else pd.DataFrame()
        )
        if df_active.empty:
            st.info("Hiện không có thẻ xe nào đang còn hiệu lực để hủy.")
        else:
            active_options = [
                f"{r['bien_so']} - {r['ho_ten']} ({r['loai_xe']})"
                for _, r in df_active.iterrows()
            ]
            with st.form("form_cancel_monthly_ticket"):
                sel_cancel_label = st.selectbox(
                    "Chọn thẻ xe cần hủy:",
                    options=active_options,
                    key="tab1_cancel_select",
                )
                sel_bien_so = sel_cancel_label.split(" - ")[0]
                matched_row = df_active[df_active["bien_so"] == sel_bien_so].iloc[0]
                dk_date = matched_row["ngay_dang_ky"]
                if isinstance(dk_date, str):
                    try:
                        dk_date = datetime.date.fromisoformat(dk_date)
                    except Exception:
                        dk_date = datetime.date.today()
                elif isinstance(dk_date, datetime.datetime):
                    dk_date = dk_date.date()

                cancel_date = st.date_input(
                    "Ngày hủy:",
                    value=max(datetime.date.today(), dk_date),
                    min_value=dk_date,
                    key="tab1_cancel_ngay_huy",
                )
                chk_confirm_cancel = st.checkbox(
                    "Tôi xác nhận muốn hủy vé xe này (không thể hoàn tác)",
                    value=False,
                    key="tab1_chk_confirm_cancel",
                )
                btn_cancel = st.form_submit_button("Hủy vé xe", width="stretch")
                if btn_cancel:
                    if not chk_confirm_cancel:
                        st.warning("Vui lòng tích chọn xác nhận trước khi thực hiện hủy vé xe.")
                    else:
                        ok, msg = cancel_monthly_ticket(
                            bien_so=sel_bien_so,
                            ngay_huy=cancel_date,
                        )
                        if ok:
                            set_flash_feedback(
                                True,
                                f"Đã hủy vé tháng cho xe {sel_bien_so} thành công!",
                            )
                            st.rerun()
                        else:
                            show_feedback(False, msg)


def render_tab2_parking_turns() -> None:
    """Tab 2: Quẹt thẻ lượt xe vé tháng."""
    st.markdown("**Ghi nhận lượt xe ra / vào bãi**")
    st.caption(
        "Chính sách bãi xe: Miễn phí 2 lượt gửi/lấy đầu tiên trong ngày. "
        "Từ lượt thứ 3 trong cùng ngày, hệ thống tự động áp phụ thu 3.000 VNĐ/lượt (Trigger trg_luot_xe_insert)."
    )

    chk_manual = st.checkbox(
        "Nhập biển số thủ công (kiểm thử)",
        value=False,
        key="tab2_chk_manual",
        help="Đánh dấu để nhập biển số bất kỳ phục vụ kiểm thử lỗi xe chưa đăng ký hoặc hết hạn.",
    )

    if chk_manual:
        bien_so_val = st.text_input(
            "Nhập biển số kiểm thử (ví dụ: 99Z-99999):",
            key="tab2_txt_bien_so",
            placeholder="Nhập biển số xe kiểm thử…",
        )
    else:
        df_active = get_monthly_tickets(only_active=True)
        if df_active.empty:
            st.warning(
                "Chưa có xe vé tháng nào còn hiệu lực. Hãy đăng ký vé tháng tại Tab 1 hoặc chọn Nhập biển số thủ công."
            )
            bien_so_val = ""
        else:
            options = [
                f"{r['bien_so']} - {r['ho_ten']} ({r['loai_xe']})"
                for _, r in df_active.iterrows()
            ]
            sel_opt = st.selectbox(
                "Chọn xe vé tháng còn hiệu lực:",
                options=options,
                key="tab2_sel_active_v",
            )
            bien_so_val = sel_opt.split(" - ")[0] if sel_opt else ""

    col_gui, col_lay = st.columns(2)
    with col_gui:
        st.markdown("**Thời gian gửi xe**")
        d_gui = st.date_input("Ngày gửi:", value=datetime.date.today(), key="tab2_d_gui")
        t_gui = st.time_input("Giờ gửi:", value=datetime.time(8, 0), key="tab2_t_gui")

    with col_lay:
        st.markdown("**Thời gian lấy xe**")
        d_lay = st.date_input("Ngày lấy:", value=datetime.date.today(), key="tab2_d_lay")
        t_lay = st.time_input("Giờ lấy:", value=datetime.time(11, 30), key="tab2_t_lay")

    btn_record = st.button("Ghi nhận lượt gửi/lấy xe", width="stretch", key="tab2_btn_record")
    if btn_record:
        clean_bs = bien_so_val.strip().upper() if bien_so_val else ""
        if not clean_bs:
            st.error("Vui lòng chọn hoặc nhập biển số xe.")
        else:
            tg_gui = datetime.datetime.combine(d_gui, t_gui)
            tg_lay = datetime.datetime.combine(d_lay, t_lay)

            if tg_lay <= tg_gui:
                st.error("Thời gian lấy xe phải sau thời gian gửi.")
            else:
                ok, msg, fee, turn = record_parking_turn(clean_bs, tg_gui, tg_lay)
                if ok:
                    try:
                        st.toast(
                            f"Đã ghi nhận lượt gửi/lấy xe {clean_bs} thành công!",
                            icon=None,
                        )
                    except Exception:
                        pass
                    if fee == 0 or fee == Decimal("0.00"):
                        st.success(
                            f"Đã ghi nhận lượt gửi/lấy xe {clean_bs} thành công! Đây là lượt thứ {turn} trong ngày -> Miễn phí (0 VNĐ)."
                        )
                    elif fee == 3000 or fee == Decimal("3000.00"):
                        st.warning(
                            f"Đã ghi nhận lượt gửi/lấy xe {clean_bs} thành công! Đây là lượt thứ {turn} trong ngày (vượt quá 2 lượt miễn phí/ngày) "
                            "-> Trigger đã tự động áp mức phụ thu: 3.000 VNĐ."
                        )
                    else:
                        st.info(
                            f"Đã ghi nhận lượt gửi/lấy xe {clean_bs} thành công! Đây là lượt thứ {turn} trong ngày. Số tiền phải trả: {format_vnd(fee)}"
                        )
                else:
                    show_feedback(False, msg)

    st.markdown("---")

    # Bảng nhật ký lượt xe
    st.markdown("**Nhật ký lượt gửi/lấy xe**")
    c_f1, c_f2 = st.columns(2)
    filter_bs = c_f1.text_input(
        "Lọc theo biển số:",
        key="tab2_filter_bs",
        placeholder="Nhập biển số xe cần lọc…",
    )
    use_date_filter = c_f2.checkbox("Lọc theo ngày gửi", value=False, key="tab2_chk_use_date")
    filter_date = None
    if use_date_filter:
        filter_date = c_f2.date_input(
            "Chọn ngày gửi:",
            value=datetime.date.today(),
            key="tab2_filter_date",
        )

    df_logs = get_parking_logs(
        bien_so=filter_bs.strip() if filter_bs else None,
        ngay_gui=filter_date,
    )

    if not df_logs.empty:
        df_logs_disp = df_logs.copy()
        df_logs_disp["so_tien_phai_tra"] = df_logs_disp["so_tien_phai_tra"].apply(format_vnd)
        df_logs_disp = df_logs_disp.rename(
            columns={
                "ma_luot": "Mã lượt",
                "bien_so": "Biển số",
                "ma_sv": "Mã SV",
                "ho_ten": "Họ và tên",
                "loai_xe": "Loại xe",
                "thoi_gian_gui": "Thời gian gửi",
                "thoi_gian_lay": "Thời gian lấy",
                "so_tien_phai_tra": "Số tiền (VNĐ)",
            }
        )
        display_table(df_logs_disp, height=300)
    else:
        st.info("Chưa có nhật ký lượt xe nào phù hợp điều kiện lọc.")


def render_tab3_visitor_vehicles() -> None:
    """Tab 3: Tiện ích tính tiền xe vãng lai tại cổng."""
    st.info(
        "Theo quy định nghiệp vụ KTX, các xe không đăng ký vé tháng (xe vãng lai của khách "
        "hoặc sinh viên) được thu tiền mặt trực tiếp theo từng lượt tại bốt bảo vệ và KHÔNG lưu vào CSDL."
    )

    don_gia_vang_lai = int(get_don_gia_dv("DV02", fallback=3000.0))

    c_left, c_right = st.columns([1, 1])

    with c_left:
        st.markdown("**Thông tin lượt gửi xe vãng lai**")
        loai_pt = st.radio(
            "Loại phương tiện",
            ["Xe đạp / Xe đạp điện", "Xe máy"],
            key="tab3_loai_pt",
        )
        ca_gui = st.radio(
            "Ca gửi",
            ["Ban ngày (06:00 - 18:00)", "Buổi tối (18:00 - 22:00)", "Qua đêm (Sau 22:00)"],
            key="tab3_ca_gui",
        )
        st.text_input(
            "Đơn giá lượt (đồng bộ mã DV02):",
            value=f"{format_vnd(don_gia_vang_lai)} / lượt",
            disabled=True,
        )

        so_luong = st.number_input(
            "Số lượng xe / Số lượt gửi",
            min_value=1,
            value=1,
            step=1,
            key="tab3_so_luong",
        )
        tien_khach = st.number_input(
            "Số tiền khách đưa (VNĐ)",
            min_value=0,
            step=1000,
            value=don_gia_vang_lai,
            key="tab3_tien_khach",
        )

    tong_tien = so_luong * don_gia_vang_lai
    tien_thoi = tien_khach - tong_tien

    with c_right:
        st.markdown("**Biên nhận tính tiền tại bốt bảo vệ**")
        if tien_khach < tong_tien:
            st.warning(
                f"Khách đưa chưa đủ tiền! Còn thiếu: {format_vnd(tong_tien - tien_khach)}"
            )

        now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        color_thua = "#16A34A" if tien_thoi >= 0 else "#DC2626"
        st.markdown(
            f"""
            <div style="background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 18px; margin-top: 5px;">
                <div style="text-align: center; border-bottom: 2px solid #1E3A8A; padding-bottom: 8px; margin-bottom: 12px;">
                    <h3 style="color: #1E3A8A; margin: 0; font-size: 1.15rem; font-weight: 700;">PHIẾU THU TIỀN XE VÃNG LAI</h3>
                    <p style="color: #64748B; margin: 3px 0 0 0; font-size: 0.85rem;">Bốt Bảo vệ Ký túc xá Sinh viên - Thu tiền mặt trực tiếp</p>
                </div>
                <div style="font-size: 0.9rem; line-height: 1.8; color: #1E293B;">
                    <div><strong>Thời gian lập:</strong> {now_str}</div>
                    <div><strong>Bảo vệ trực ban:</strong> Tổ bảo vệ KTX</div>
                    <div><strong>Loại phương tiện:</strong> {loai_pt}</div>
                    <div><strong>Ca gửi:</strong> {ca_gui}</div>
                    <div><strong>Số lượng lượt:</strong> {so_luong} lượt</div>
                    <div><strong>Đơn giá:</strong> {format_vnd(don_gia_vang_lai)} / lượt</div>
                    <div style="margin-top: 8px; padding-top: 8px; border-top: 1px dashed #CBD5E1; font-size: 1rem;">
                        <strong>TỔNG TIỀN PHẢI THU:</strong> <span style="color: #1E3A8A; font-weight: 700; font-size: 1.15rem;">{format_vnd(tong_tien)}</span>
                    </div>
                    <div><strong>Tiền khách đưa:</strong> {format_vnd(tien_khach)}</div>
                    <div><strong>Tiền thừa trả khách:</strong> <span style="color: {color_thua}; font-weight: 700;">{format_vnd(max(0, tien_thoi))}</span></div>
                </div>
                <div style="margin-top: 14px; text-align: center; font-size: 0.8rem; color: #64748B; font-style: italic;">
                    (Phiếu thu tiền mặt thanh toán tại chỗ - Dữ liệu không ghi vào CSDL)
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_parking_management() -> None:
    """Điều phối toàn bộ phân khu Quản lý Bãi giữ xe & Xe vãng lai."""
    styled_header(
        "Quản lý Bãi giữ xe",
        "Đăng ký vé tháng, quẹt thẻ lượt gửi/lấy và tiện ích tính tiền xe vãng lai tại cổng.",
    )

    tab1, tab2, tab3 = st.tabs([
        "Vé xe tháng",
        "Lượt gửi & Lấy xe",
        "Thu phí xe vãng lai",
    ])

    with tab1:
        render_tab1_monthly_tickets()
    with tab2:
        render_tab2_parking_turns()
    with tab3:
        render_tab3_visitor_vehicles()

