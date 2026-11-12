"""Module Quan ly Phong va Luu tru Sinh vien.

Cung cap cac ham xu ly du lieu va logic nghiep vu:
- Tab 1: Tra cuu phong, kiem tra cho trong va quan ly danh muc phong.
- Tab 2: Quan ly ho so sinh vien va tra cuu lich su 360 do.
- Tab 3: Tiep nhan va xep phong sinh vien.
- Tab 4: Tra phong va chuyen phong qua Transaction.
"""

import datetime
from typing import Optional, Union
import pandas as pd
import streamlit as st
import db
from modules.ui_helpers import (
    display_table,
    format_vnd,
    show_feedback,
    styled_header,
)


def get_room_occupancy_list(only_available: bool = False) -> pd.DataFrame:
    """Truy van danh sach phong ket hop dem so sinh vien dang o thuc te."""
    sql = """
    SELECT 
        p.so_phong,
        p.loai_phong,
        p.don_gia_thang,
        p.so_nguoi_toi_da,
        COUNT(l.ma_o) AS so_nguoi_dang_o,
        (p.so_nguoi_toi_da - COUNT(l.ma_o)) AS so_cho_trong,
        CONCAT(COUNT(l.ma_o), '/', p.so_nguoi_toi_da, ' chỗ (', 
               CASE 
                   WHEN p.so_nguoi_toi_da - COUNT(l.ma_o) = 0 THEN 'Đã đầy'
                   ELSE CONCAT('Còn ', p.so_nguoi_toi_da - COUNT(l.ma_o), ' chỗ')
               END, ')') AS ty_le_lap_day,
        CASE 
            WHEN p.so_nguoi_toi_da - COUNT(l.ma_o) = 0 THEN 'Đã đầy'
            ELSE 'Còn chỗ'
        END AS trang_thai_cho
    FROM phong p
    LEFT JOIN lich_su_o_phong l 
        ON p.so_phong = l.so_phong AND l.ngay_ra IS NULL
    GROUP BY p.so_phong, p.loai_phong, p.don_gia_thang, p.so_nguoi_toi_da
    """
    if only_available:
        sql += " HAVING so_cho_trong > 0"
    sql += " ORDER BY p.so_phong ASC;"
    return db.fetch_df(sql)


def get_students_in_room(so_phong: str) -> pd.DataFrame:
    """Truy van danh sach chi tiet cac sinh vien dang o trong phong."""
    sql = """
    SELECT 
        s.ma_sv,
        s.ho_ten,
        s.lop,
        s.que_quan,
        s.so_cmt,
        l.ngay_vao,
        l.don_gia_ap_dung
    FROM lich_su_o_phong l
    JOIN sinh_vien s ON l.ma_sv = s.ma_sv
    WHERE l.so_phong = %s AND l.ngay_ra IS NULL
    ORDER BY l.ngay_vao ASC;
    """
    return db.fetch_df(sql, (so_phong.strip(),))


def add_new_room(
    so_phong: str, loai_phong: str, don_gia_thang: float, so_nguoi_toi_da: int
) -> tuple[bool, str]:
    """Them phong moi vao bang phong."""
    sql = "INSERT INTO phong (so_phong, loai_phong, don_gia_thang, so_nguoi_toi_da) VALUES (%s, %s, %s, %s);"
    return db.execute_query(
        sql,
        (
            so_phong.strip(),
            loai_phong.strip(),
            float(don_gia_thang),
            int(so_nguoi_toi_da),
        ),
    )


def update_room(
    so_phong: str, loai_phong: str, don_gia_thang: float, so_nguoi_toi_da: int
) -> tuple[bool, str]:
    """Cap nhat thong tin phong, chan neu suc chua nho hon so nguoi dang o thuc te."""
    df_current = get_students_in_room(so_phong)
    so_dang_o = len(df_current)
    if int(so_nguoi_toi_da) < so_dang_o:
        return False, f"Không thể cập nhật: Sức chứa mới ({so_nguoi_toi_da}) nhỏ hơn số sinh viên đang ở ({so_dang_o})."

    sql = """
    UPDATE phong 
    SET loai_phong = %s, don_gia_thang = %s, so_nguoi_toi_da = %s 
    WHERE so_phong = %s;
    """
    return db.execute_query(
        sql,
        (
            loai_phong.strip(),
            float(don_gia_thang),
            int(so_nguoi_toi_da),
            so_phong.strip(),
        ),
    )


def search_students(keyword: str = "") -> pd.DataFrame:
    """Tìm kiếm nhanh sinh viên theo ma_sv, ho_ten, so_cmt, lop, hoặc que_quan."""
    sql = """
    SELECT ma_sv, so_cmt, ho_ten, ngay_sinh, lop, que_quan
    FROM sinh_vien
    """
    if keyword and keyword.strip():
        kw = f"%{keyword.strip()}%"
        sql += """
        WHERE ma_sv LIKE %s 
           OR ho_ten LIKE %s 
           OR so_cmt LIKE %s 
           OR lop LIKE %s 
           OR que_quan LIKE %s
        """
        sql += " ORDER BY ma_sv ASC;"
        return db.fetch_df(sql, (kw, kw, kw, kw, kw))
    sql += " ORDER BY ma_sv ASC;"
    return db.fetch_df(sql)


def add_student(
    ma_sv: str, so_cmt: str, ho_ten: str, ngay_sinh: str, lop: str, que_quan: str
) -> tuple[bool, str]:
    """Thêm hồ sơ sinh viên mới vào bảng sinh_vien."""
    sql = """
    INSERT INTO sinh_vien (ma_sv, so_cmt, ho_ten, ngay_sinh, lop, que_quan)
    VALUES (%s, %s, %s, %s, %s, %s);
    """
    return db.execute_query(
        sql,
        (
            ma_sv.strip(),
            so_cmt.strip(),
            ho_ten.strip(),
            str(ngay_sinh).strip(),
            lop.strip(),
            que_quan.strip(),
        ),
    )


def update_student(
    ma_sv: str, so_cmt: str, ho_ten: str, ngay_sinh: str, lop: str, que_quan: str
) -> tuple[bool, str]:
    """Cập nhật thông tin sinh viên theo ma_sv."""
    sql = """
    UPDATE sinh_vien 
    SET so_cmt = %s, ho_ten = %s, ngay_sinh = %s, lop = %s, que_quan = %s
    WHERE ma_sv = %s;
    """
    return db.execute_query(
        sql,
        (
            so_cmt.strip(),
            ho_ten.strip(),
            str(ngay_sinh).strip(),
            lop.strip(),
            que_quan.strip(),
            ma_sv.strip(),
        ),
    )


def delete_student(ma_sv: str) -> tuple[bool, str]:
    """Xóa sinh viên, bắt lỗi khóa ngoại thân thiện."""
    sql = "DELETE FROM sinh_vien WHERE ma_sv = %s;"
    success, msg = db.execute_query(sql, (ma_sv.strip(),))
    if not success and ("foreign key" in msg.lower() or "1451" in msg):
        return (
            False,
            f"Không thể xóa sinh viên {ma_sv}: Sinh viên đã có dữ liệu ràng buộc lưu trú, dịch vụ, gửi xe hoặc khách thăm trong CSDL.",
        )
    return success, msg


def get_student_profile_360(ma_sv: str) -> dict[str, pd.DataFrame]:
    """Truy vấn toàn bộ 4 nhóm lịch sử 360 độ của 1 sinh viên."""
    sv_id = ma_sv.strip()
    sql_o = """
    SELECT l.ma_o, l.so_phong, p.loai_phong, l.ngay_vao, l.ngay_ra, l.don_gia_ap_dung,
           CASE WHEN l.ngay_ra IS NULL THEN 'Đang ở' ELSE 'Đã trả phòng' END AS trang_thai
    FROM lich_su_o_phong l
    JOIN phong p ON l.so_phong = p.so_phong
    WHERE l.ma_sv = %s
    ORDER BY l.ngay_vao DESC;
    """
    sql_dv = """
    SELECT s.ma_sd, s.thoi_gian_su_dung, d.ma_dv, d.ten_dv, d.loai_dv, s.so_luong, s.don_gia_ap_dung,
           (s.so_luong * s.don_gia_ap_dung) AS thanh_tien
    FROM su_dung_dich_vu s
    JOIN dich_vu d ON s.ma_dv = d.ma_dv
    WHERE s.ma_sv = %s
    ORDER BY s.thoi_gian_su_dung DESC;
    """
    sql_xe = """
    SELECT x.bien_so, x.loai_xe, x.ngay_dang_ky, x.ngay_huy,
           CASE WHEN x.ngay_huy IS NULL THEN 'Còn hiệu lực' ELSE 'Đã hủy vé' END AS trang_thai
    FROM xe_ve_thang x
    WHERE x.ma_sv = %s
    ORDER BY x.ngay_dang_ky DESC;
    """
    sql_khach = """
    SELECT l.ma_luot, l.ngay_den, k.so_cmt AS so_cmt_khach, k.ten_khach, k.ngay_sinh
    FROM luot_den_choi l
    JOIN khach k ON l.so_cmt_khach = k.so_cmt
    WHERE l.ma_sv = %s
    ORDER BY l.ngay_den DESC;
    """
    return {
        "lich_su_o": db.fetch_df(sql_o, (sv_id,)),
        "dich_vu": db.fetch_df(sql_dv, (sv_id,)),
        "xe_ve_thang": db.fetch_df(sql_xe, (sv_id,)),
        "khach_tham": db.fetch_df(sql_khach, (sv_id,)),
    }


def get_student_options_for_checkin() -> list[dict]:
    """Lấy danh sách sinh viên kèm thông tin phòng hiện tại (nếu đang ở)."""
    sql = """
    SELECT 
        s.ma_sv,
        s.ho_ten,
        s.lop,
        l.so_phong AS phong_hien_tai
    FROM sinh_vien s
    LEFT JOIN lich_su_o_phong l 
        ON s.ma_sv = l.ma_sv AND l.ngay_ra IS NULL
    ORDER BY s.ma_sv ASC;
    """
    df = db.fetch_df(sql)
    records = df.to_dict(orient="records")
    return [{k: (None if pd.isna(v) else v) for k, v in row.items()} for row in records]


def get_room_options_for_checkin() -> list[dict]:
    """Lấy danh sách phòng kèm đơn giá và trạng thái chỗ để chọn khi xếp phòng."""
    df = get_room_occupancy_list(only_available=False)
    return df.to_dict(orient="records")


def checkin_student(
    ma_sv: str, so_phong: str, ngay_vao: str, don_gia_ap_dung: float
) -> tuple[bool, str]:
    """Tiếp nhận xếp phòng sinh viên, bắt lỗi từ Trigger trg_phong_insert."""
    sql = """
    INSERT INTO lich_su_o_phong (ma_sv, so_phong, ngay_vao, ngay_ra, don_gia_ap_dung)
    VALUES (%s, %s, %s, NULL, %s);
    """
    return db.execute_query(
        sql,
        (
            ma_sv.strip(),
            so_phong.strip(),
            str(ngay_vao).strip(),
            float(don_gia_ap_dung),
        ),
    )


def get_active_stays() -> list[dict]:
    """Lấy danh sách các lưu trú đang ở (ngay_ra IS NULL) để phục vụ Trả/Chuyển phòng."""
    sql = """
    SELECT 
        l.ma_o,
        l.ma_sv,
        s.ho_ten,
        s.lop,
        l.so_phong,
        p.loai_phong,
        l.ngay_vao,
        l.don_gia_ap_dung
    FROM lich_su_o_phong l
    JOIN sinh_vien s ON l.ma_sv = s.ma_sv
    JOIN phong p ON l.so_phong = p.so_phong
    WHERE l.ngay_ra IS NULL
    ORDER BY l.so_phong ASC, l.ma_sv ASC;
    """
    df = db.fetch_df(sql)
    return df.to_dict(orient="records")


def checkout_student(ma_o: int, ngay_ra: str, ngay_vao: str) -> tuple[bool, str]:
    """Thực hiện trả phòng (checkout) cho sinh viên."""
    if str(ngay_ra) < str(ngay_vao):
        return False, f"Ngày trả phòng ({ngay_ra}) phải lớn hơn hoặc bằng ngày vào ({ngay_vao})."
    sql = "UPDATE lich_su_o_phong SET ngay_ra = %s WHERE ma_o = %s;"
    return db.execute_query(sql, (str(ngay_ra).strip(), int(ma_o)))


def transfer_student_room(
    ma_o_cu: int,
    ma_sv: str,
    so_phong_moi: str,
    ngay_chuyen: str,
    ngay_vao_cu: str,
    don_gia_moi: float,
) -> tuple[bool, str]:
    """Chuyển phòng cho sinh viên trong 1 Transaction duy nhất."""
    if str(ngay_chuyen) <= str(ngay_vao_cu):
        return (
            False,
            f"Ngày chuyển phòng ({ngay_chuyen}) phải sau ngày vào phòng cũ ({ngay_vao_cu}) ít nhất 1 ngày.",
        )

    sql_step1 = "UPDATE lich_su_o_phong SET ngay_ra = DATE_SUB(%s, INTERVAL 1 DAY) WHERE ma_o = %s;"
    sql_step2 = """
    INSERT INTO lich_su_o_phong (ma_sv, so_phong, ngay_vao, ngay_ra, don_gia_ap_dung)
    VALUES (%s, %s, %s, NULL, %s);
    """
    operations = [
        (sql_step1, (str(ngay_chuyen).strip(), int(ma_o_cu))),
        (
            sql_step2,
            (
                str(ma_sv).strip(),
                str(so_phong_moi).strip(),
                str(ngay_chuyen).strip(),
                float(don_gia_moi),
            ),
        ),
    ]
    return db.execute_transaction(operations)


def render_tab1_rooms() -> None:
    """Giao diện Tab 1: Tra cứu danh mục phòng, tỷ lệ lấp đầy và quản lý phòng."""
    st.markdown("**Danh mục phòng và tình trạng lưu trú hiện tại**")

    df_all = get_room_occupancy_list(only_available=False)
    if not df_all.empty:
        tong_phong = len(df_all)
        tong_suc_chua = int(df_all["so_nguoi_toi_da"].sum())
        tong_dang_o = int(df_all["so_nguoi_dang_o"].sum())
        tong_cho_trong = int(df_all["so_cho_trong"].sum())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tổng số phòng", f"{tong_phong} phòng")
        c2.metric("Tổng sức chứa", f"{tong_suc_chua} chỗ")
        c3.metric("Số người đang ở", f"{tong_dang_o} sinh viên")
        c4.metric("Chỗ trống hiện tại", f"{tong_cho_trong} chỗ")

    only_avail = st.checkbox("Chỉ hiển thị các phòng còn chỗ trống", value=False, key="chk_only_available_rooms")
    df_rooms = get_room_occupancy_list(only_available=only_avail)

    if df_rooms.empty:
        st.info("Không có phòng nào thỏa mãn điều kiện lọc.")
    else:
        df_show = df_rooms.copy()
        df_show["don_gia_thang"] = df_show["don_gia_thang"].apply(format_vnd)
        df_show = df_show[[
            "so_phong",
            "loai_phong",
            "don_gia_thang",
            "so_nguoi_toi_da",
            "so_nguoi_dang_o",
            "so_cho_trong",
            "ty_le_lap_day",
            "trang_thai_cho",
        ]]
        df_show.columns = [
            "Số phòng",
            "Loại phòng",
            "Đơn giá tháng",
            "Sức chứa",
            "Đang ở",
            "Còn trống",
            "Tỷ lệ lấp đầy",
            "Trạng thái",
        ]
        display_table(df_show, title="Bảng thống kê tỷ lệ lấp đầy từng phòng")

    with st.expander("Chi tiết sinh viên đang lưu trú trong phòng"):
        if df_all.empty:
            st.info("Chưa có dữ liệu phòng.")
        else:
            phong_list = df_all["so_phong"].tolist()
            phong_chon = st.selectbox("Chọn số phòng cần xem:", options=phong_list, key="sel_room_occupants")
            df_sv_room = get_students_in_room(phong_chon)
            if df_sv_room.empty:
                st.info(f"Phòng {phong_chon} hiện đang trống (0 sinh viên).")
            else:
                df_sv_show = df_sv_room.copy()
                df_sv_show["don_gia_ap_dung"] = df_sv_show["don_gia_ap_dung"].apply(format_vnd)
                df_sv_show.columns = [
                    "Mã SV",
                    "Họ và tên",
                    "Lớp",
                    "Quê quán",
                    "Số CMT",
                    "Ngày vào",
                    "Đơn giá áp dụng",
                ]
                display_table(df_sv_show, title=f"Danh sách sinh viên đang ở phòng {phong_chon} ({len(df_sv_show)} người)")

    with st.expander("Thêm phòng mới vào danh mục"):
        with st.form("form_add_room"):
            c1, c2 = st.columns(2)
            new_so = c1.text_input("Số phòng mới (VD: B202):", max_chars=10)
            new_loai = c2.selectbox(
                "Loại phòng:",
                options=["Phòng 2 người", "Phòng 4 người", "Phòng 6 người", "Phòng 8 người"],
            )
            c3, c4 = st.columns(2)
            new_gia = c3.number_input("Đơn giá tháng (VNĐ):", min_value=0.0, value=400000.0, step=50000.0)
            new_chua = c4.number_input("Sức chứa tối đa (người):", min_value=1, max_value=20, value=4, step=1)
            btn_add = st.form_submit_button("Lưu phòng mới", width="stretch")
            if btn_add:
                if not new_so.strip():
                    st.warning("Vui lòng nhập số phòng.")
                else:
                    ok, msg = add_new_room(new_so, new_loai, new_gia, new_chua)
                    show_feedback(ok, f"Đã thêm phòng {new_so} thành công!" if ok else msg)
                    if ok:
                        st.rerun()

    with st.expander("Cập nhật thông tin phòng"):
        if not df_all.empty:
            phong_upd = st.selectbox("Chọn phòng cần cập nhật:", options=df_all["so_phong"].tolist(), key="sel_room_to_update")
            curr_room = df_all[df_all["so_phong"] == phong_upd].iloc[0]
            with st.form("form_update_room"):
                c1, c2 = st.columns(2)
                upd_loai = c1.text_input("Loại phòng:", value=str(curr_room["loai_phong"]))
                upd_gia = c2.number_input("Đơn giá tháng (VNĐ):", min_value=0.0, value=float(curr_room["don_gia_thang"]), step=50000.0)
                upd_chua = st.number_input(
                    "Sức chứa tối đa mới:",
                    min_value=1,
                    max_value=20,
                    value=int(curr_room["so_nguoi_toi_da"]),
                    step=1,
                )
                st.caption(f"Lưu ý: Phòng hiện có {curr_room['so_nguoi_dang_o']} sinh viên đang ở. Sức chứa mới không được nhỏ hơn số này.")
                btn_upd = st.form_submit_button("Lưu cập nhật phòng", width="stretch")
                if btn_upd:
                    ok, msg = update_room(phong_upd, upd_loai, upd_gia, upd_chua)
                    show_feedback(ok, f"Đã cập nhật phòng {phong_upd} thành công!" if ok else msg)
                    if ok:
                        st.rerun()


def render_tab2_students() -> None:
    """Giao diện Tab 2: Quản lý hồ sơ sinh viên và tra cứu lịch sử 360 độ."""
    all_sv = search_students("")
    sub_crud, sub_360 = st.tabs(["Quản lý hồ sơ sinh viên", "Tra cứu hồ sơ 360 độ cá nhân"])

    with sub_crud:
        keyword = st.text_input(
            "Tìm kiếm sinh viên theo Mã SV, Họ tên, CMT, Lớp, Quê quán:",
            value="",
            key="tab2_search_kw",
        )
        df_students = search_students(keyword) if keyword.strip() else all_sv
        display_table(df_students, title=f"Danh sách hồ sơ sinh viên ({len(df_students)} kết quả)")

        with st.expander("Thêm hồ sơ sinh viên mới"):
            with st.form("form_add_student"):
                c1, c2, c3 = st.columns(3)
                ma_sv = c1.text_input("Mã sinh viên (VD: SV007):", max_chars=10)
                so_cmt = c2.text_input("Số CMT/CCCD:", max_chars=20)
                ho_ten = c3.text_input("Họ và tên:", max_chars=50)

                c4, c5, c6 = st.columns(3)
                ngay_sinh = c4.date_input("Ngày sinh:", value=datetime.date(2004, 1, 1), key="add_sv_dob")
                lop = c5.text_input("Lớp:", max_chars=20)
                que_quan = c6.text_input("Quê quán:", max_chars=50)

                btn_add_sv = st.form_submit_button("Thêm sinh viên", width="stretch")
                if btn_add_sv:
                    if not ma_sv.strip() or not ho_ten.strip() or not so_cmt.strip():
                        st.warning("Vui lòng điền đầy đủ Mã SV, Số CMT và Họ tên.")
                    else:
                        ok, msg = add_student(ma_sv, so_cmt, ho_ten, str(ngay_sinh), lop, que_quan)
                        show_feedback(ok, f"Đã thêm sinh viên {ma_sv} thành công!" if ok else msg)
                        if ok:
                            st.rerun()

        with st.expander("Cập nhật thông tin sinh viên"):
            if all_sv.empty:
                st.info("Chưa có dữ liệu sinh viên.")
            else:
                sv_options = [f"{r['ma_sv']} - {r['ho_ten']}" for _, r in all_sv.iterrows()]
                sel_sv_str = st.selectbox("Chọn sinh viên cần cập nhật:", options=sv_options, key="tab2_sel_upd_sv")
                sel_ma = sel_sv_str.split(" - ")[0]
                curr_sv = all_sv[all_sv["ma_sv"] == sel_ma].iloc[0]

                with st.form("form_update_student"):
                    c1, c2 = st.columns(2)
                    upd_cmt = c1.text_input("Số CMT/CCCD:", value=str(curr_sv["so_cmt"]))
                    upd_ten = c2.text_input("Họ và tên:", value=str(curr_sv["ho_ten"]))

                    c3, c4, c5 = st.columns(3)
                    dob_raw = curr_sv["ngay_sinh"]
                    try:
                        parsed_dob = datetime.date.fromisoformat(str(dob_raw))
                    except Exception:
                        parsed_dob = datetime.date(2004, 1, 1)
                    upd_dob = c3.date_input(
                        "Ngày sinh:",
                        value=parsed_dob,
                        min_value=datetime.date(1980, 1, 1),
                        max_value=datetime.date.today(),
                        key="tab2_upd_dob_picker",
                    )
                    upd_lop = c4.text_input("Lớp:", value=str(curr_sv["lop"]))
                    upd_que = c5.text_input("Quê quán:", value=str(curr_sv["que_quan"]))

                    btn_upd_sv = st.form_submit_button("Lưu thay đổi", width="stretch")
                    if btn_upd_sv:
                        ok, msg = update_student(sel_ma, upd_cmt, upd_ten, str(upd_dob), upd_lop, upd_que)
                        show_feedback(ok, f"Đã cập nhật sinh viên {sel_ma} thành công!" if ok else msg)
                        if ok:
                            st.rerun()

        with st.expander("Xóa hồ sơ sinh viên"):
            if all_sv.empty:
                st.info("Chưa có dữ liệu sinh viên.")
            else:
                sv_del_options = [f"{r['ma_sv']} - {r['ho_ten']}" for _, r in all_sv.iterrows()]
                sel_del_str = st.selectbox("Chọn sinh viên cần xóa:", options=sv_del_options, key="tab2_sel_del_sv")
                sel_del_ma = sel_del_str.split(" - ")[0]

                with st.form("form_delete_student"):
                    st.warning(
                        f"Lưu ý: Xóa sinh viên {sel_del_ma}. Hệ thống sẽ chặn xóa nếu sinh viên đã có dữ liệu ràng buộc lưu trú, dịch vụ, gửi xe hoặc khách thăm."
                    )
                    chk_confirm = st.checkbox("Tôi xác nhận muốn xóa sinh viên này khỏi hệ thống", key="tab2_chk_del_confirm")
                    btn_del_sv = st.form_submit_button("Xác nhận xóa sinh viên", width="stretch")
                    if btn_del_sv:
                        if not chk_confirm:
                            st.error("Vui lòng đánh dấu xác nhận trước khi thực hiện xóa.")
                        else:
                            ok, msg = delete_student(sel_del_ma)
                            show_feedback(ok, f"Đã xóa thành công sinh viên {sel_del_ma}!" if ok else msg)
                            if ok:
                                st.rerun()

    with sub_360:
        if all_sv.empty:
            st.info("Chưa có dữ liệu sinh viên để tra cứu hồ sơ 360 độ.")
            return

        sv_360_opts = [f"{r['ma_sv']} - {r['ho_ten']} ({r['lop']})" for _, r in all_sv.iterrows()]
        sel_360_str = st.selectbox("Chọn sinh viên tra cứu hồ sơ 360 độ:", options=sv_360_opts, key="tab2_sel_360")
        target_ma_sv = sel_360_str.split(" - ")[0]
        student_info = all_sv[all_sv["ma_sv"] == target_ma_sv].iloc[0]

        st.markdown(
            f"""
            <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 16px; margin: 10px 0 16px 0;">
                <div style="font-weight: 700; color: #1E3A8A; font-size: 16px; margin-bottom: 8px;">
                    Thông tin cơ bản sinh viên: {student_info['ho_ten']} ({student_info['ma_sv']})
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; font-size: 14px; color: #334155;">
                    <div><strong>Số CMT/CCCD:</strong> {student_info['so_cmt']}</div>
                    <div><strong>Lớp:</strong> {student_info['lop']}</div>
                    <div><strong>Quê quán:</strong> {student_info['que_quan']}</div>
                    <div><strong>Ngày sinh:</strong> {student_info['ngay_sinh']}</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        p360 = get_student_profile_360(target_ma_sv)

        st.markdown("**1. Lịch sử ở phòng & Trạng thái lưu trú**")
        df_o = p360["lich_su_o"].copy()
        if df_o.empty:
            st.info("Sinh viên chưa có lịch sử lưu trú phòng nào.")
        else:
            df_o["don_gia_ap_dung"] = df_o["don_gia_ap_dung"].apply(format_vnd)
            df_o.columns = ["Mã ở", "Số phòng", "Loại phòng", "Ngày vào", "Ngày ra", "Đơn giá áp dụng", "Trạng thái"]
            display_table(df_o)

        st.markdown("**2. Lịch sử sử dụng dịch vụ đời sống**")
        df_dv = p360["dich_vu"].copy()
        if df_dv.empty:
            st.info("Sinh viên chưa phát sinh sử dụng dịch vụ nào.")
        else:
            df_dv["don_gia_ap_dung"] = df_dv["don_gia_ap_dung"].apply(format_vnd)
            df_dv["thanh_tien"] = df_dv["thanh_tien"].apply(format_vnd)
            df_dv.columns = [
                "Mã SD",
                "Thời gian sử dụng",
                "Mã DV",
                "Tên dịch vụ",
                "Loại DV",
                "Số lượng",
                "Đơn giá",
                "Thành tiền",
            ]
            display_table(df_dv)

        st.markdown("**3. Phương tiện gửi vé tháng**")
        df_xe = p360["xe_ve_thang"].copy()
        if df_xe.empty:
            st.info("Sinh viên chưa đăng ký xe vé tháng.")
        else:
            df_xe.columns = ["Biển số", "Loại xe", "Ngày đăng ký", "Ngày hủy", "Trạng thái"]
            display_table(df_xe)

        st.markdown("**4. Lịch sử đón tiếp khách đến thăm**")
        df_khach = p360["khach_tham"].copy()
        if df_khach.empty:
            st.info("Chưa có lượt khách nào đến thăm sinh viên.")
        else:
            df_khach.columns = ["Mã lượt", "Ngày đến", "Số CMT khách", "Tên khách", "Ngày sinh khách"]
            display_table(df_khach)


def render_tab3_checkin() -> None:
    """Giao diện Tab 3: Tiếp nhận và xếp phòng sinh viên."""
    st.markdown("**Tiếp nhận sinh viên vào ở phòng ký túc xá**")
    st.caption(
        "Quy định nghiệp vụ: Sinh viên chỉ được ở 1 phòng trong cùng một khoảng thời gian. "
        "Trigger trg_phong_insert sẽ tự động kiểm tra và chặn nếu phòng đã đủ số người tối đa hoặc sinh viên bị trùng lịch ở."
    )

    sv_options = get_student_options_for_checkin()
    room_options = get_room_options_for_checkin()

    if not sv_options:
        st.warning("Chưa có dữ liệu sinh viên trong hệ thống.")
        return
    if not room_options:
        st.warning("Chưa có danh mục phòng trong hệ thống.")
        return

    c1, c2 = st.columns(2)
    sv_labels = [
        f"{s['ma_sv']} - {s['ho_ten']} ({s['lop']}) "
        + (f"[Đang ở {s['phong_hien_tai']}]" if s.get("phong_hien_tai") else "[Chưa có phòng]")
        for s in sv_options
    ]
    sel_sv_str = c1.selectbox("Chọn sinh viên tiếp nhận:", options=sv_labels, key="tab3_sel_sv")
    chosen_sv = sv_options[sv_labels.index(sel_sv_str)]
    chosen_ma_sv = chosen_sv["ma_sv"]

    room_labels = [
        f"Phòng {r['so_phong']} ({r['loai_phong']}) - Còn {r['so_cho_trong']} chỗ [{r['trang_thai_cho']}]"
        for r in room_options
    ]
    sel_room_str = c2.selectbox("Chọn phòng xếp vào:", options=room_labels, key="tab3_sel_room")
    chosen_room = room_options[room_labels.index(sel_room_str)]
    chosen_so_phong = chosen_room["so_phong"]

    c3, c4 = st.columns(2)
    ngay_vao = c3.date_input("Ngày bắt đầu vào ở:", value=datetime.date.today(), key="tab3_ngay_vao")
    don_gia_def = float(chosen_room["don_gia_thang"])
    don_gia_ap_dung = c4.number_input(
        "Đơn giá áp dụng (VNĐ/tháng):",
        min_value=0.0,
        value=don_gia_def,
        step=50000.0,
        key=f"tab3_price_{chosen_so_phong}",
    )

    btn_checkin = st.button("Xác nhận Tiếp nhận & Xếp phòng", width="stretch", key="tab3_btn_checkin")
    if btn_checkin:
        ok, msg = checkin_student(chosen_ma_sv, chosen_so_phong, str(ngay_vao), don_gia_ap_dung)
        show_feedback(ok, f"Đã tiếp nhận thành công sinh viên {chosen_ma_sv} vào phòng {chosen_so_phong}!" if ok else msg)
        if ok:
            st.rerun()

    st.markdown("<hr style='margin: 25px 0 15px 0;'>", unsafe_allow_html=True)
    active_stays = get_active_stays()
    if active_stays:
        df_active = pd.DataFrame(active_stays)
        df_active_show = df_active[[
            "so_phong",
            "loai_phong",
            "ma_sv",
            "ho_ten",
            "lop",
            "ngay_vao",
            "don_gia_ap_dung",
        ]].copy()
        df_active_show["don_gia_ap_dung"] = df_active_show["don_gia_ap_dung"].apply(format_vnd)
        df_active_show.columns = ["Phòng", "Loại phòng", "Mã SV", "Họ và tên", "Lớp", "Ngày vào", "Đơn giá tháng"]
        display_table(
            df_active_show,
            title=f"Danh sách toàn bộ sinh viên đang lưu trú hiện tại ({len(df_active_show)} sinh viên)",
        )
    else:
        st.info("Hiện không có sinh viên nào đang lưu trú.")


def render_tab4_checkout_transfer() -> None:
    """Giao diện Tab 4: Trả phòng và Chuyển phòng qua Transaction an toàn."""
    active_stays = get_active_stays()
    if not active_stays:
        st.info("Hiện không có sinh viên nào đang lưu trú trong ký túc xá.")
        return

    tab_out, tab_tr = st.tabs(["Nghiệp vụ Trả phòng (Checkout)", "Nghiệp vụ Chuyển phòng (Transaction)"])

    stay_labels = [
        f"{s['so_phong']} - {s['ma_sv']} ({s['ho_ten']}) - Ngày vào: {s['ngay_vao']}"
        for s in active_stays
    ]

    with tab_out:
        st.markdown("**Xác nhận trả phòng cho sinh viên**")
        st.caption("Ghi nhận ngày ra thực tế và kết thúc đợt lưu trú của sinh viên tại phòng hiện tại.")

        sel_stay_str = st.selectbox("Chọn sinh viên trả phòng:", options=stay_labels, key="tab4_sel_checkout_stay")
        idx_stay = stay_labels.index(sel_stay_str)
        target_stay = active_stays[idx_stay]

        c1, c2 = st.columns(2)
        c1.text_input("Ngày vào phòng hiện tại:", value=str(target_stay["ngay_vao"]), disabled=True)
        ngay_ra = c2.date_input("Ngày trả phòng:", value=datetime.date.today(), key="tab4_ngay_ra")

        with st.popover("Xác nhận Trả phòng", width="stretch"):
            st.markdown(f"**Cảnh báo:** Hành động này sẽ kết thúc hợp đồng lưu trú phòng **{target_stay['so_phong']}** của sinh viên **{target_stay['ma_sv']}**.")
            st.caption("Ngày trả phòng sẽ được cập nhật vĩnh viễn vào hệ thống.")
            btn_checkout = st.button("Tôi chắc chắn muốn Trả phòng", type="primary", width="stretch", key="tab4_btn_checkout")
            if btn_checkout:
                ok, msg = checkout_student(target_stay["ma_o"], str(ngay_ra), str(target_stay["ngay_vao"]))
                show_feedback(
                    ok,
                    f"Đã hoàn tất trả phòng {target_stay['so_phong']} cho sinh viên {target_stay['ma_sv']}."
                    if ok
                    else msg,
                )
                if ok:
                    st.rerun()

    with tab_tr:
        st.markdown("**Chuyển phòng lưu trú bằng Transaction nguyên tử**")
        st.caption(
            "Cơ chế Transaction bảo toàn dữ liệu: Thực thi đồng thời Bước 1 (Chốt ngày ra phòng cũ = ngày liền trước ngày chuyển) "
            "và Bước 2 (Tạo bản ghi vào phòng mới). Nếu phòng mới đã đầy hoặc có lỗi xảy ra, toàn bộ giao dịch sẽ tự động Rollback, "
            "giữ nguyên vẹn trạng thái phòng cũ của sinh viên."
        )

        sel_tr_stay_str = st.selectbox("Chọn sinh viên chuyển phòng:", options=stay_labels, key="tab4_sel_transfer_stay")
        chosen_tr_stay = active_stays[stay_labels.index(sel_tr_stay_str)]

        c1, c2 = st.columns(2)
        c1.text_input(
            "Phòng đang ở hiện tại:",
            value=f"{chosen_tr_stay['so_phong']} ({chosen_tr_stay['loai_phong']})",
            disabled=True,
        )
        c2.text_input("Ngày bắt đầu ở phòng hiện tại:", value=str(chosen_tr_stay["ngay_vao"]), disabled=True)

        room_options = get_room_options_for_checkin()
        other_rooms = [r for r in room_options if r["so_phong"] != chosen_tr_stay["so_phong"]]

        if not other_rooms:
            st.warning("Không có phòng khác để chuyển đến.")
            return

        other_room_labels = [
            f"Phòng {r['so_phong']} ({r['loai_phong']}) - Còn {r['so_cho_trong']} chỗ [{r['trang_thai_cho']}]"
            for r in other_rooms
        ]
        sel_new_room = st.selectbox("Chọn phòng chuyển tới:", options=other_room_labels, key="tab4_sel_new_room")
        new_room_obj = other_rooms[other_room_labels.index(sel_new_room)]
        new_so_phong = new_room_obj["so_phong"]

        c3, c4 = st.columns(2)
        ngay_chuyen = c3.date_input("Ngày chuyển sang phòng mới:", value=datetime.date.today(), key="tab4_ngay_chuyen")
        don_gia_new = c4.number_input(
            "Đơn giá phòng mới (VNĐ/tháng):",
            min_value=0.0,
            value=float(new_room_obj["don_gia_thang"]),
            step=50000.0,
            key=f"tab4_price_{new_so_phong}",
        )

        with st.popover("Xác nhận Chuyển phòng (Transaction)", width="stretch"):
            st.markdown(f"**Cảnh báo:** Hành động này sẽ chuyển sinh viên **{chosen_tr_stay['ma_sv']}** từ phòng **{chosen_tr_stay['so_phong']}** sang phòng **{new_so_phong}**.")
            st.caption("Giao dịch nguyên tử (Transaction) sẽ tự động rollback an toàn nếu phòng mới không đủ chỗ.")
            btn_transfer = st.button("Tôi chắc chắn muốn Chuyển phòng", type="primary", width="stretch", key="tab4_btn_transfer")
            if btn_transfer:
                ok, msg = transfer_student_room(
                    chosen_tr_stay["ma_o"],
                    chosen_tr_stay["ma_sv"],
                    new_so_phong,
                    str(ngay_chuyen),
                    str(chosen_tr_stay["ngay_vao"]),
                    don_gia_new,
                )
                show_feedback(
                    ok,
                    f"Chuyển phòng thành công! Sinh viên {chosen_tr_stay['ma_sv']} đã được chuyển sang phòng {new_so_phong}."
                    if ok
                    else msg,
                )
                if ok:
                    st.rerun()


def render_room_management() -> None:
    """Điều phối toàn bộ phân khu Quản lý Phòng & Lưu trú Sinh viên."""
    styled_header(
        "Quản lý Phòng & Lưu trú Sinh viên",
        "Phân khu nghiệp vụ: Tra cứu chỗ trống, Hồ sơ sinh viên 360 độ, Tiếp nhận xếp phòng và Trả/Chuyển phòng an toàn",
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "Tra cứu phòng & Chỗ trống (Bổ trợ 2)",
        "Quản lý hồ sơ SV & 360 độ (Bổ trợ 3)",
        "Tiếp nhận & Xếp phòng (Bổ trợ 4)",
        "Trả & Chuyển phòng qua Transaction (Bổ trợ 5)",
    ])

    with tab1:
        render_tab1_rooms()
    with tab2:
        render_tab2_students()
    with tab3:
        render_tab3_checkin()
    with tab4:
        render_tab4_checkout_transfer()



