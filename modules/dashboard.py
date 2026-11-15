"""Module Giao diện: Bảng thông tin chỉ số tổng quan (Tổng quan Vận hành)

Hiển thị 4 thẻ chỉ số KPI vận hành theo Tháng/Năm được chọn:
1. Tổng số sinh viên đang lưu trú
2. Số chỗ trống còn lại trong toàn KTX
3. Số xe vé tháng đang gửi có hiệu lực
4. Tổng doanh thu tháng (tính theo đúng công thức CTE của TRUY VẤN 1)

Kèm theo 2 bảng dữ liệu:
- Danh sách trạng thái của các phòng (có highlight cảnh báo khi phòng đã đầy)
- Danh sách sinh viên đang lưu trú hiện tại
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import db


def get_date_bounds(thang: int, nam: int) -> tuple[str, str]:
    """Tính ngày đầu tháng và ngày đầu tháng kế tiếp để phục vụ truy vấn mốc thời gian."""
    dau_thang = f"{nam:04d}-{thang:02d}-01"
    if thang == 12:
        dau_thang_sau = f"{nam + 1:04d}-01-01"
    else:
        dau_thang_sau = f"{nam:04d}-{thang + 1:02d}-01"
    return dau_thang, dau_thang_sau


def render_dashboard(thang: int, nam: int):
    """Vẽ toàn bộ nội dung của màn hình Tổng quan Dashboard."""
    dau_thang, dau_thang_sau = get_date_bounds(thang, nam)

    st.markdown(
        f"""
        <div style="padding: 10px 0 20px 0;">
            <h2 style="margin: 0; color: #1E3A8A;">Tổng quan Vận hành Ký túc xá</h2>
            <p style="margin: 4px 0 0 0; color: #64748B;">
                Báo cáo chỉ số và trạng thái lưu trú trong <b>Tháng {thang:02d}/{nam}</b>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    q_sv = """
        SELECT COUNT(DISTINCT ma_sv) AS so_sv
        FROM lich_su_o_phong
        WHERE ngay_vao < %s
          AND (ngay_ra IS NULL OR ngay_ra >= %s);
    """
    df_sv = db.fetch_df(q_sv, (dau_thang_sau, dau_thang))
    so_sv_dang_o = int(df_sv["so_sv"].iloc[0]) if not df_sv.empty else 0

    q_capacity = """
        SELECT 
            COALESCE(SUM(so_nguoi_toi_da), 0) AS tong_suc_chua
        FROM phong;
    """
    df_cap = db.fetch_df(q_capacity)
    tong_suc_chua = int(df_cap["tong_suc_chua"].iloc[0]) if not df_cap.empty else 0

    q_curr_residents = """
        SELECT COUNT(*) AS dang_o_hien_tai
        FROM lich_su_o_phong
        WHERE ngay_ra IS NULL;
    """
    df_curr = db.fetch_df(q_curr_residents)
    dang_o_hien_tai = int(df_curr["dang_o_hien_tai"].iloc[0]) if not df_curr.empty else 0
    so_cho_trong = max(0, tong_suc_chua - dang_o_hien_tai)

    q_xe = """
        SELECT COUNT(*) AS so_xe
        FROM xe_ve_thang
        WHERE ngay_dang_ky < %s
          AND (ngay_huy IS NULL OR ngay_huy >= %s);
    """
    df_xe = db.fetch_df(q_xe, (dau_thang_sau, dau_thang))
    so_xe_ve_thang = int(df_xe["so_xe"].iloc[0]) if not df_xe.empty else 0

    # Doanh thu tính theo CTE của truy vấn báo cáo 1 (phòng, dịch vụ, vé tháng và phụ thu xe).
    q_revenue = """
        WITH
        p AS (
          SELECT ma_sv, SUM(don_gia_ap_dung) AS tien_phong
          FROM lich_su_o_phong
          WHERE ngay_vao < %s
            AND (ngay_ra IS NULL OR ngay_ra >= %s)
          GROUP BY ma_sv
        ),
        d AS (
          SELECT ma_sv, SUM(so_luong * don_gia_ap_dung) AS tien_dich_vu
          FROM su_dung_dich_vu
          WHERE thoi_gian_su_dung >= %s
            AND thoi_gian_su_dung < %s
          GROUP BY ma_sv
        ),
        x AS (
          SELECT ma_sv, COUNT(*) * 100000 AS tien_ve_thang
          FROM xe_ve_thang
          WHERE ngay_dang_ky < %s
            AND (ngay_huy IS NULL OR ngay_huy >= %s)
          GROUP BY ma_sv
        ),
        xe_phat_sinh AS (
          SELECT x.ma_sv, SUM(l.so_tien_phai_tra) AS tien_phu_thu_xe
          FROM luot_gui_lay_xe l
          JOIN xe_ve_thang x ON l.bien_so = x.bien_so
          WHERE l.thoi_gian_gui >= %s
            AND l.thoi_gian_gui < %s
          GROUP BY x.ma_sv
        )
        SELECT
          COALESCE(SUM(p.tien_phong), 0) AS tien_phong,
          COALESCE(SUM(d.tien_dich_vu), 0) AS tien_dich_vu,
          COALESCE(SUM(x.tien_ve_thang), 0) AS tien_ve_thang,
          COALESCE(SUM(xp.tien_phu_thu_xe), 0) AS tien_phu_thu_xe,
          (COALESCE(SUM(p.tien_phong), 0) +
           COALESCE(SUM(d.tien_dich_vu), 0) +
           COALESCE(SUM(x.tien_ve_thang), 0) +
           COALESCE(SUM(xp.tien_phu_thu_xe), 0)) AS tong_doanh_thu
        FROM sinh_vien s
        JOIN p ON s.ma_sv = p.ma_sv
        LEFT JOIN d ON s.ma_sv = d.ma_sv
        LEFT JOIN x ON s.ma_sv = x.ma_sv
        LEFT JOIN xe_phat_sinh xp ON s.ma_sv = xp.ma_sv;
    """
    df_rev = db.fetch_df(
        q_revenue,
        (
            dau_thang_sau,
            dau_thang,
            dau_thang,
            dau_thang_sau,
            dau_thang_sau,
            dau_thang,
            dau_thang,
            dau_thang_sau,
        ),
    )
    tong_doanh_thu = float(df_rev["tong_doanh_thu"].iloc[0]) if not df_rev.empty else 0.0

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Sinh viên lưu trú",
            value=f"{so_sv_dang_o} sinh viên",
            help=f"Số lượng sinh viên đang ở trong KTX trong tháng {thang:02d}/{nam}",
        )

    with col2:
        st.metric(
            label="Số chỗ trống còn lại",
            value=f"{so_cho_trong} / {tong_suc_chua} chỗ",
            help="Tổng sức chứa trừ đi số người đang ở thực tế (ngay_ra IS NULL)",
        )

    with col3:
        st.metric(
            label="Xe vé tháng hiệu lực",
            value=f"{so_xe_ve_thang} xe",
            help=f"Số xe có vé tháng hoạt động trong tháng {thang:02d}/{nam}",
        )

    with col4:
        st.metric(
            label="Tổng doanh thu kỳ",
            value=f"{tong_doanh_thu:,.0f}\u00a0đ".replace(",", "."),
            help="Tổng tiền phòng + tiền dịch vụ + tiền vé tháng (100k/xe) + tiền phụ thu gửi xe",
        )

    st.divider()

    tab1, tab2 = st.tabs([
        "Trạng thái các phòng",
        "Danh sách sinh viên đang lưu trú",
    ])

    with tab1:
        st.subheader("Trạng thái từng phòng ở")

        q_rooms = """
            SELECT 
                p.so_phong,
                p.loai_phong,
                p.don_gia_thang,
                p.so_nguoi_toi_da,
                COUNT(l.ma_o) AS dang_o,
                (p.so_nguoi_toi_da - COUNT(l.ma_o)) AS con_trong,
                ROUND((COUNT(l.ma_o) / p.so_nguoi_toi_da) * 100, 1) AS ty_le_lap_day
            FROM phong p
            LEFT JOIN lich_su_o_phong l 
                ON p.so_phong = l.so_phong 
                AND l.ngay_vao < %s
                AND (l.ngay_ra IS NULL OR l.ngay_ra >= %s)
            GROUP BY p.so_phong, p.loai_phong, p.don_gia_thang, p.so_nguoi_toi_da
            ORDER BY p.so_phong;
        """
        df_rooms = db.fetch_df(q_rooms, (dau_thang_sau, dau_thang))

        if not df_rooms.empty:
            def danh_gia_trang_thai(row):
                if row["con_trong"] == 0:
                    return "ĐÃ ĐẦY"
                return f"Còn {int(row['con_trong'])} chỗ"

            df_rooms["trang_thai"] = df_rooms.apply(danh_gia_trang_thai, axis=1)

            df_display_rooms = df_rooms[[
                "so_phong",
                "loai_phong",
                "don_gia_thang",
                "dang_o",
                "so_nguoi_toi_da",
                "con_trong",
                "trang_thai",
            ]].copy()

            df_display_rooms.columns = [
                "Số phòng",
                "Loại phòng",
                "Đơn giá tháng (VNĐ)",
                "Đang ở",
                "Sức chứa",
                "Chỗ trống",
                "Tình trạng",
            ]

            def highlight_full_room(row):
                if "ĐÃ ĐẦY" in str(row["Tình trạng"]):
                    return ["background-color: #fee2e2; color: #991b1b; font-weight: bold;"] * len(row)
                return [""] * len(row)

            styled_rooms = df_display_rooms.style.apply(highlight_full_room, axis=1).format({
                "Đơn giá tháng (VNĐ)": "{:,.0f}".format,
            })

            st.dataframe(styled_rooms, width="stretch", hide_index=True)
        else:
            st.info("Chưa có dữ liệu phòng ở trong CSDL.")

    with tab2:
        st.subheader("Danh sách sinh viên đang lưu trú tại KTX")
        st.caption(f"Ghi nhận các sinh viên có hợp đồng lưu trú trong Tháng {thang:02d}/{nam}.")

        q_residents = """
            SELECT 
                s.ma_sv,
                s.ho_ten,
                s.lop,
                s.que_quan,
                l.so_phong,
                p.loai_phong,
                l.ngay_vao,
                l.don_gia_ap_dung
            FROM lich_su_o_phong l
            JOIN sinh_vien s ON l.ma_sv = s.ma_sv
            JOIN phong p ON l.so_phong = p.so_phong
            WHERE l.ngay_vao < %s
              AND (l.ngay_ra IS NULL OR l.ngay_ra >= %s)
            ORDER BY l.so_phong, s.ma_sv;
        """
        df_residents = db.fetch_df(q_residents, (dau_thang_sau, dau_thang))

        if not df_residents.empty:
            tu_khoa = st.text_input(
                "Tìm kiếm nhanh sinh viên:",
                placeholder="Nhập Mã SV, Họ tên, Số phòng hoặc Quê quán…",
            )

            df_display_res = df_residents.copy()

            if tu_khoa.strip():
                kw = tu_khoa.strip().lower()
                match = (
                    df_display_res["ma_sv"].astype(str).str.lower().str.contains(kw)
                    | df_display_res["ho_ten"].astype(str).str.lower().str.contains(kw)
                    | df_display_res["so_phong"].astype(str).str.lower().str.contains(kw)
                    | df_display_res["que_quan"].astype(str).str.lower().str.contains(kw)
                )
                df_display_res = df_display_res[match]

            df_display_res.columns = [
                "Mã SV",
                "Họ và tên",
                "Lớp",
                "Quê quán",
                "Phòng ở",
                "Loại phòng",
                "Ngày vào ở",
                "Đơn giá áp dụng (VNĐ)",
            ]

            df_display_res["Ngày vào ở"] = pd.to_datetime(df_display_res["Ngày vào ở"]).dt.strftime("%d/%m/%Y")
            styled_res = df_display_res.style.format({
                "Đơn giá áp dụng (VNĐ)": "{:,.0f}".format,
            })

            st.dataframe(styled_res, width="stretch", hide_index=True)
            st.caption(f"Tổng số bản ghi: **{len(df_display_res)}** sinh viên.")
        else:
            st.info(f"Không có sinh viên nào lưu trú trong Tháng {thang:02d}/{nam}.")
