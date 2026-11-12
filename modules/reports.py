"""Module Báo cáo và Hóa đơn nghiệp vụ Ký túc xá.

Tuân thủ kiến trúc hai tầng tách bạch:
- Tầng Dữ liệu (Data Functions): Thực thi truy vấn SQL CTE trả về DataFrame và dict.
- Tầng Giao diện (UI Layer): Hiển thị giao diện Streamlit không sử dụng icon hay emoji.
"""

import calendar
import datetime
from decimal import Decimal
from typing import Optional, Union
import pandas as pd
import streamlit as st
import db
from modules.ui_helpers import (
    display_table,
    export_csv,
    export_excel,
    format_vnd,
    number_to_vietnamese_words,
    render_export_buttons,
    styled_header,
)


def _to_date_str(val: Union[str, datetime.date, datetime.datetime]) -> str:
    """Chuyển đổi giá trị ngày sang chuỗi YYYY-MM-DD."""
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d")
    return str(val)


def get_date_bounds(thang: int, nam: int) -> tuple[str, str]:
    """Xác định mốc thời gian bắt đầu tháng và bắt đầu tháng tiếp theo."""
    dau_thang = f"{nam:04d}-{thang:02d}-01"
    if thang == 12:
        dau_thang_sau = f"{nam + 1:04d}-01-01"
    else:
        dau_thang_sau = f"{nam:04d}-{thang + 1:02d}-01"
    return dau_thang, dau_thang_sau


def get_monthly_invoices(thang: int, nam: int) -> pd.DataFrame:
    """Truy vấn tổng hợp chi phí hóa đơn tháng của tất cả sinh viên đang lưu trú.

    Nhúng nguyên bản CTE Truy vấn tổng hợp từ 2.sql gồm 4 thành phần:
    tiền phòng, tiền dịch vụ, tiền vé xe tháng và phụ thu lượt xe.
    """
    dau_thang, dau_thang_sau = get_date_bounds(thang, nam)

    query = """
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
      s.ma_sv,
      s.ho_ten,
      s.lop,
      s.que_quan,
      COALESCE(p.tien_phong, 0) AS tien_phong,
      COALESCE(d.tien_dich_vu, 0) AS tien_dich_vu,
      COALESCE(x.tien_ve_thang, 0) AS tien_ve_thang,
      COALESCE(xp.tien_phu_thu_xe, 0) AS tien_phu_thu_xe,
      (COALESCE(p.tien_phong, 0) + COALESCE(d.tien_dich_vu, 0) +
       COALESCE(x.tien_ve_thang, 0) + COALESCE(xp.tien_phu_thu_xe, 0)) AS tong_phai_tra
    FROM sinh_vien s
    JOIN p ON s.ma_sv = p.ma_sv
    LEFT JOIN d ON s.ma_sv = d.ma_sv
    LEFT JOIN x ON s.ma_sv = x.ma_sv
    LEFT JOIN xe_phat_sinh xp ON s.ma_sv = xp.ma_sv
    ORDER BY s.ma_sv;
    """

    params = (
        dau_thang_sau,
        dau_thang,
        dau_thang,
        dau_thang_sau,
        dau_thang_sau,
        dau_thang,
        dau_thang,
        dau_thang_sau,
    )
    return db.fetch_df(query, params)


def get_student_invoice_detail(ma_sv: str, thang: int, nam: int) -> Optional[dict]:
    """Lay chi tiet hoa don kem so phong dang o cho mot sinh vien cu the."""
    dau_thang, dau_thang_sau = get_date_bounds(thang, nam)
    df_inv = get_monthly_invoices(thang, nam)
    match_row = df_inv[df_inv["ma_sv"] == ma_sv]
    if match_row.empty:
        return None

    detail = match_row.iloc[0].to_dict()

    q_phong = """
    SELECT GROUP_CONCAT(DISTINCT so_phong SEPARATOR ', ') AS so_phong
    FROM lich_su_o_phong
    WHERE ma_sv = %s
      AND ngay_vao < %s
      AND (ngay_ra IS NULL OR ngay_ra >= %s);
    """
    df_phong = db.fetch_df(q_phong, (ma_sv, dau_thang_sau, dau_thang))
    so_phong = "Chưa xếp phòng"
    if not df_phong.empty and df_phong["so_phong"].iloc[0]:
        so_phong = str(df_phong["so_phong"].iloc[0])

    detail["so_phong"] = so_phong
    detail["thang"] = thang
    detail["nam"] = nam
    return detail


def get_service_usage(
    tu_ngay: Union[str, datetime.date],
    den_ngay: Union[str, datetime.date],
    ma_sv: Optional[str] = None,
    loai_dv: Optional[str] = None,
) -> pd.DataFrame:
    """Truy van chi tiet su dung dich vu trong khoang thoi gian (TRUY VAN 2)."""
    tu_str = _to_date_str(tu_ngay)
    den_str = _to_date_str(den_ngay)

    query = """
    SELECT
      s.ma_sv,
      s.ho_ten,
      d.ma_dv,
      d.ten_dv,
      COUNT(sd.ma_sd) AS so_lan_su_dung,
      SUM(sd.so_luong) AS tong_so_luong,
      SUM(sd.so_luong * sd.don_gia_ap_dung) AS tong_tien
    FROM su_dung_dich_vu sd
    JOIN sinh_vien s ON sd.ma_sv = s.ma_sv
    JOIN dich_vu d ON sd.ma_dv = d.ma_dv
    WHERE sd.thoi_gian_su_dung >= %s
      AND sd.thoi_gian_su_dung < DATE_ADD(%s, INTERVAL 1 DAY)
    """
    params: list[Union[str, int]] = [tu_str, den_str]

    if ma_sv and ma_sv != "Tat ca":
        query += " AND sd.ma_sv = %s"
        params.append(ma_sv)

    if loai_dv and loai_dv != "Tat ca":
        query += " AND d.loai_dv = %s"
        params.append(loai_dv)

    query += """
    GROUP BY s.ma_sv, s.ho_ten, d.ma_dv, d.ten_dv
    ORDER BY s.ma_sv, d.ma_dv;
    """

    return db.fetch_df(query, tuple(params))


def get_visitor_statistics(
    tu_ngay: Union[str, datetime.date],
    den_ngay: Union[str, datetime.date],
    ma_sv: Optional[str] = None,
) -> pd.DataFrame:
    """Truy van thong ke luot khach den tham sinh vien trong khoang thoi gian (TRUY VAN 3)."""
    tu_str = _to_date_str(tu_ngay)
    den_str = _to_date_str(den_ngay)

    query = """
    SELECT
      s.ma_sv,
      s.ho_ten AS ten_sinh_vien,
      k.so_cmt AS cmt_khach,
      k.ten_khach,
      k.ngay_sinh AS ngay_sinh_khach,
      COUNT(*) AS so_lan_den,
      MIN(l.ngay_den) AS lan_dau,
      MAX(l.ngay_den) AS lan_cuoi
    FROM luot_den_choi l
    JOIN sinh_vien s ON l.ma_sv = s.ma_sv
    JOIN khach k ON l.so_cmt_khach = k.so_cmt
    WHERE l.ngay_den >= %s
      AND l.ngay_den < DATE_ADD(%s, INTERVAL 1 DAY)
    """
    params: list[Union[str, int]] = [tu_str, den_str]

    if ma_sv and ma_sv != "Tat ca":
        query += " AND l.ma_sv = %s"
        params.append(ma_sv)

    query += """
    GROUP BY s.ma_sv, s.ho_ten, k.so_cmt, k.ten_khach, k.ngay_sinh
    ORDER BY s.ma_sv, so_lan_den DESC;
    """

    return db.fetch_df(query, tuple(params))


def get_service_revenue(thang: int, nam: int) -> tuple[pd.DataFrame, dict]:
    """Truy van doanh thu dich vu thang kem tien ve thang va phu thu xe (TRUY VAN 4)."""
    dau_thang, dau_thang_sau = get_date_bounds(thang, nam)

    query_df = """
    WITH
    dt_ve_xe AS (
      SELECT COUNT(*) * 100000 AS tien_ve
      FROM xe_ve_thang
      WHERE ngay_dang_ky < %s
        AND (ngay_huy IS NULL OR ngay_huy >= %s)
    ),
    dt_phu_thu_xe AS (
      SELECT COALESCE(SUM(so_tien_phai_tra), 0) AS tien_phu_thu
      FROM luot_gui_lay_xe
      WHERE thoi_gian_gui >= %s
        AND thoi_gian_gui < %s
    )
    SELECT
      d.ma_dv,
      d.ten_dv,
      d.loai_dv,
      CASE
        WHEN d.loai_dv = 'TRONG_XE' THEN
          COALESCE(SUM(sd.so_luong * sd.don_gia_ap_dung), 0) +
          (SELECT tien_ve FROM dt_ve_xe) +
          (SELECT tien_phu_thu FROM dt_phu_thu_xe)
        ELSE
          COALESCE(SUM(sd.so_luong * sd.don_gia_ap_dung), 0)
      END AS doanh_thu_thang
    FROM dich_vu d
    LEFT JOIN su_dung_dich_vu sd
      ON sd.ma_dv = d.ma_dv
      AND sd.thoi_gian_su_dung >= %s
      AND sd.thoi_gian_su_dung < %s
    GROUP BY d.ma_dv, d.ten_dv, d.loai_dv
    ORDER BY d.ma_dv;
    """
    params_df = (
        dau_thang_sau,
        dau_thang,
        dau_thang,
        dau_thang_sau,
        dau_thang,
        dau_thang_sau,
    )
    df_revenue = db.fetch_df(query_df, params_df)

    query_metrics = """
    SELECT
      (SELECT COUNT(*) * 100000 FROM xe_ve_thang WHERE ngay_dang_ky < %s AND (ngay_huy IS NULL OR ngay_huy >= %s)) AS tien_ve,
      (SELECT COALESCE(SUM(so_tien_phai_tra), 0) FROM luot_gui_lay_xe WHERE thoi_gian_gui >= %s AND thoi_gian_gui < %s) AS tien_phu_thu;
    """
    params_metrics = (dau_thang_sau, dau_thang, dau_thang, dau_thang_sau)
    df_m = db.fetch_df(query_metrics, params_metrics)

    tien_ve = int(df_m["tien_ve"].iloc[0]) if not df_m.empty and df_m["tien_ve"].iloc[0] is not None else 0
    tien_phu_thu = int(df_m["tien_phu_thu"].iloc[0]) if not df_m.empty and df_m["tien_phu_thu"].iloc[0] is not None else 0
    tong_doanh_thu = int(df_revenue["doanh_thu_thang"].sum()) if not df_revenue.empty else 0

    metrics = {
        "tien_ve": tien_ve,
        "tien_phu_thu": tien_phu_thu,
        "tong_doanh_thu": tong_doanh_thu,
    }
    return df_revenue, metrics


def _generate_receipt_html(detail: dict) -> str:
    """Sinh ma HTML phieu thu ca nhan kem CSS dinh dang in an A4."""
    ma_sv = detail.get("ma_sv", "")
    ho_ten = detail.get("ho_ten", "")
    lop = detail.get("lop", "")
    que_quan = detail.get("que_quan", "")
    so_phong = detail.get("so_phong", "Chưa xếp phòng")
    thang = detail.get("thang", 10)
    nam = detail.get("nam", 2026)

    tien_phong_str = format_vnd(detail.get("tien_phong", 0))
    tien_dv_str = format_vnd(detail.get("tien_dich_vu", 0))
    tien_ve_str = format_vnd(detail.get("tien_ve_thang", 0))
    tien_phu_thu_str = format_vnd(detail.get("tien_phu_thu_xe", 0))
    tong_str = format_vnd(detail.get("tong_phai_tra", 0))
    bang_chu = number_to_vietnamese_words(detail.get("tong_phai_tra", 0))

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>Phiếu Báo Thu Tiền KTX - {ma_sv}</title>
<style>
  @page {{
    size: A4 portrait;
    margin: 15mm;
  }}
  * {{
    box-sizing: border-box;
  }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
    color: #0F172A;
    background-color: #FFFFFF;
    margin: 0;
    padding: 24px;
    line-height: 1.5;
  }}
  .header {{
    text-align: center;
    border-bottom: 2px solid #1E3A8A;
    padding-bottom: 12px;
    margin-bottom: 20px;
  }}
  .sub-org {{
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #475569;
    margin: 0 0 4px 0;
  }}
  .doc-title {{
    font-size: 20px;
    font-weight: 700;
    color: #1E3A8A;
    margin: 4px 0;
    text-transform: uppercase;
  }}
  .period {{
    font-size: 14px;
    color: #334155;
    margin: 4px 0 0 0;
  }}
  .info-table {{
    width: 100%;
    margin-bottom: 20px;
    border-collapse: collapse;
  }}
  .info-table td {{
    padding: 6px 8px;
    font-size: 14px;
    vertical-align: top;
  }}
  .info-label {{
    width: 18%;
    color: #64748B;
    font-weight: 500;
  }}
  .info-value {{
    width: 32%;
    color: #0F172A;
    font-weight: 600;
  }}
  .fee-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 16px;
  }}
  .fee-table th, .fee-table td {{
    border: 1px solid #CBD5E1;
    padding: 10px 12px;
    font-size: 14px;
    font-variant-numeric: tabular-nums;
  }}
  .fee-table th {{
    background-color: #F1F5F9;
    color: #1E3A8A;
    font-weight: 600;
    text-align: left;
  }}
  .text-center {{
    text-align: center;
  }}
  .text-right {{
    text-align: right;
  }}
  .total-card {{
    background-color: #F8FAFC;
    border: 1px solid #E2E8F0;
    border-radius: 4px;
    padding: 14px 16px;
    margin-bottom: 24px;
  }}
  .total-row {{
    display: flex;
    justify-content: space-between;
    font-size: 16px;
    font-weight: 700;
    color: #1E3A8A;
    font-variant-numeric: tabular-nums;
  }}
  .words-row {{
    margin-top: 6px;
    font-size: 13px;
    color: #334155;
    font-style: italic;
  }}
  .signatures {{
    display: flex;
    justify-content: space-between;
    margin-top: 36px;
    page-break-inside: avoid;
  }}
  .sign-col {{
    width: 40%;
    text-align: center;
  }}
  .sign-title {{
    font-size: 14px;
    font-weight: 600;
    color: #0F172A;
    margin-bottom: 4px;
  }}
  .sign-sub {{
    font-size: 12px;
    color: #64748B;
    font-style: italic;
    margin-bottom: 70px;
  }}
  .sign-name {{
    font-size: 14px;
    font-weight: 600;
    color: #334155;
  }}
  @media print {{
    body {{
      padding: 0;
    }}
  }}
</style>
</head>
<body>
  <div class="header">
    <p class="sub-org">Ban Quản lý Ký túc xá Sinh viên</p>
    <h1 class="doc-title">Phiếu Báo Thu Tiền Ký Túc Xá</h1>
    <p class="period">Kỳ thu: Tháng {thang:02d} năm {nam}</p>
  </div>

  <table class="info-table">
    <tr>
      <td class="info-label">Mã sinh viên:</td>
      <td class="info-value">{ma_sv}</td>
      <td class="info-label">Họ và tên:</td>
      <td class="info-value">{ho_ten}</td>
    </tr>
    <tr>
      <td class="info-label">Lớp học:</td>
      <td class="info-value">{lop}</td>
      <td class="info-label">Quê quán:</td>
      <td class="info-value">{que_quan}</td>
    </tr>
    <tr>
      <td class="info-label">Phòng đang ở:</td>
      <td class="info-value" colspan="3">{so_phong}</td>
    </tr>
  </table>

  <table class="fee-table">
    <thead>
      <tr>
        <th class="text-center" style="width: 8%;">STT</th>
        <th style="width: 62%;">Khoản mục thanh toán</th>
        <th class="text-right" style="width: 30%;">Số tiền (VNĐ)</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td class="text-center">1</td>
        <td>Tiền phòng ở lưu trú trọn tháng</td>
        <td class="text-right">{tien_phong_str}</td>
      </tr>
      <tr>
        <td class="text-center">2</td>
        <td>Tiền dịch vụ đời sống đã sử dụng trong kỳ</td>
        <td class="text-right">{tien_dv_str}</td>
      </tr>
      <tr>
        <td class="text-center">3</td>
        <td>Tiền vé xe tháng (100.000 đ/xe)</td>
        <td class="text-right">{tien_ve_str}</td>
      </tr>
      <tr>
        <td class="text-center">4</td>
        <td>Phụ thu lượt gửi/lấy xe vượt hạn mức (3.000 đ/lượt)</td>
        <td class="text-right">{tien_phu_thu_str}</td>
      </tr>
    </tbody>
  </table>

  <div class="total-card">
    <div class="total-row">
      <span>Tổng số tiền phải nộp:</span>
      <span>{tong_str}</span>
    </div>
    <div class="words-row">
      Bằng chữ: {bang_chu}
    </div>
  </div>

  <div class="signatures">
    <div class="sign-col">
      <div class="sign-title">Sinh viên xác nhận</div>
      <div class="sign-sub">(Ký và ghi rõ họ tên)</div>
      <div class="sign-name">{ho_ten}</div>
    </div>
    <div class="sign-col">
      <div class="sign-title">Người lập phiếu thu</div>
      <div class="sign-sub">(Ký và đóng dấu)</div>
      <div class="sign-name">Ban Quản lý KTX</div>
    </div>
  </div>
</body>
</html>
"""


def _get_student_options() -> list[tuple[str, str]]:
    """Lấy danh sách mã và tên sinh viên để phục vụ bộ lọc."""
    df_sv = db.fetch_df("SELECT ma_sv, ho_ten, lop FROM sinh_vien ORDER BY ma_sv;")
    options = [("Tat ca", "Tất cả sinh viên")]
    for _, row in df_sv.iterrows():
        options.append((row["ma_sv"], f"{row['ma_sv']} - {row['ho_ten']} ({row['lop']})"))
    return options


def render_tab_hoa_don_thang(thang: int, nam: int) -> None:
    """Giao diện: Tổng hợp hóa đơn tháng và phiếu thu cá nhân."""
    che_do = st.radio(
        "Hình thức xem hóa đơn:",
        options=["Xem toàn bộ danh sách", "Xem Phiếu báo thu cá nhân từng Sinh viên"],
        horizontal=True,
        key="cn01_view_mode",
    )

    df_inv = get_monthly_invoices(thang, nam)

    if che_do == "Xem toàn bộ danh sách":
        if df_inv.empty:
            st.info("Không có dữ liệu hóa đơn cho tháng được chọn.")
            return

        c1, c2 = st.columns(2)
        c1.metric("Số lượng sinh viên", f"{len(df_inv)} sinh viên")
        c2.metric("Tổng phí KTX phải thu", format_vnd(df_inv["tong_phai_tra"].sum()))

        display_df = df_inv.copy()
        for col in ["tien_phong", "tien_dich_vu", "tien_ve_thang", "tien_phu_thu_xe", "tong_phai_tra"]:
            if col in display_df.columns:
                display_df[col] = display_df[col].apply(format_vnd)

        display_df.columns = [
            "Mã SV",
            "Họ tên",
            "Lớp",
            "Quê quán",
            "Tiền phòng",
            "Tiền dịch vụ",
            "Tiền vé tháng",
            "Phụ thu xe",
            "Tổng phải trả",
        ]
        display_table(display_df, title=f"Danh sách hóa đơn tháng {thang:02d}/{nam}")
        render_export_buttons(df_inv, f"hoa_don_thang_{thang:02d}_{nam}", "hd_all")

    else:
        if df_inv.empty:
            st.info("Không có sinh viên lưu trú trong kỳ để xuất phiếu thu.")
            return

        sv_labels = [f"{r['ma_sv']} - {r['ho_ten']} ({r['lop']})" for _, r in df_inv.iterrows()]
        selected_label = st.selectbox(
            "Chọn sinh viên cần xem phiếu báo thu:",
            options=sv_labels,
            index=0,
            key="cn01_sv_select",
        )
        ma_sv = selected_label.split(" - ")[0]
        detail = get_student_invoice_detail(ma_sv, thang, nam)

        if not detail:
            st.warning("Không tìm thấy chi tiết hóa đơn cho sinh viên đã chọn.")
            return

        st.markdown(
            f"""
            <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 20px; margin: 12px 0 20px 0;">
                <div style="text-align: center; border-bottom: 2px solid #1E3A8A; padding-bottom: 10px; margin-bottom: 16px;">
                    <div style="font-size: 12px; color: #64748B; text-transform: uppercase;">Ban Quản lý Ký túc xá Sinh viên</div>
                    <div style="font-size: 18px; font-weight: 700; color: #1E3A8A; margin: 4px 0;">PHIẾU BÁO THU TIỀN KÝ TÚC XÁ</div>
                    <div style="font-size: 13px; color: #334155;">Kỳ thu: Tháng {thang:02d}/{nam}</div>
                </div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 14px; margin-bottom: 16px;">
                    <div><strong>Mã sinh viên:</strong> {detail['ma_sv']}</div>
                    <div><strong>Họ và tên:</strong> {detail['ho_ten']}</div>
                    <div><strong>Lớp học:</strong> {detail['lop']}</div>
                    <div><strong>Quê quán:</strong> {detail['que_quan']}</div>
                    <div><strong>Phòng đang ở:</strong> {detail['so_phong']}</div>
                </div>
                <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
                    <thead>
                        <tr style="background-color: #F1F5F9; color: #1E3A8A;">
                            <th style="border: 1px solid #CBD5E1; padding: 8px; text-align: center; width: 8%;">STT</th>
                            <th style="border: 1px solid #CBD5E1; padding: 8px; text-align: left; width: 62%;">Khoản mục thanh toán</th>
                            <th style="border: 1px solid #CBD5E1; padding: 8px; text-align: right; width: 30%;">Số tiền</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: center;">1</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px;">Tiền phòng ở lưu trú trọn tháng</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: right;">{format_vnd(detail['tien_phong'])}</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: center;">2</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px;">Tiền dịch vụ đời sống đã sử dụng trong kỳ</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: right;">{format_vnd(detail['tien_dich_vu'])}</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: center;">3</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px;">Tiền vé xe tháng (100.000 đ/xe)</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: right;">{format_vnd(detail['tien_ve_thang'])}</td>
                        </tr>
                        <tr>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: center;">4</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px;">Phụ thu lượt gửi/lấy xe vượt hạn mức (3.000 đ/lượt)</td>
                            <td style="border: 1px solid #CBD5E1; padding: 8px; text-align: right;">{format_vnd(detail['tien_phu_thu_xe'])}</td>
                        </tr>
                    </tbody>
                </table>
                <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 12px 16px; border-radius: 4px;">
                    <div style="display: flex; justify-content: space-between; font-weight: 700; color: #1E3A8A; font-size: 15px;">
                        <span>Tổng số tiền phải nộp:</span>
                        <span>{format_vnd(detail['tong_phai_tra'])}</span>
                    </div>
                    <div style="margin-top: 4px; font-size: 13px; font-style: italic; color: #475569;">
                        Bằng chữ: {number_to_vietnamese_words(detail['tong_phai_tra'])}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        receipt_df = pd.DataFrame([
            {"Khoản mục": "Mã sinh viên", "Chi tiết": detail["ma_sv"]},
            {"Khoản mục": "Họ và tên", "Chi tiết": detail["ho_ten"]},
            {"Khoản mục": "Lớp học", "Chi tiết": detail["lop"]},
            {"Khoản mục": "Quê quán", "Chi tiết": detail["que_quan"]},
            {"Khoản mục": "Phòng đang ở", "Chi tiết": detail["so_phong"]},
            {"Khoản mục": "Kỳ thu", "Chi tiết": f"Tháng {thang:02d}/{nam}"},
            {"Khoản mục": "1. Tiền phòng ở", "Chi tiết": float(detail["tien_phong"])},
            {"Khoản mục": "2. Tiền dịch vụ", "Chi tiết": float(detail["tien_dich_vu"])},
            {"Khoản mục": "3. Tiền vé xe tháng", "Chi tiết": float(detail["tien_ve_thang"])},
            {"Khoản mục": "4. Phụ thu lượt xe", "Chi tiết": float(detail["tien_phu_thu_xe"])},
            {"Khoản mục": "Tổng cộng phải trả (VNĐ)", "Chi tiết": float(detail["tong_phai_tra"])},
            {"Khoản mục": "Bằng chữ", "Chi tiết": number_to_vietnamese_words(detail["tong_phai_tra"])},
        ])

        html_data = _generate_receipt_html(detail)

        b1, b2, b3 = st.columns(3)
        with b1:
            st.download_button(
                label="Tải phiếu thu in ấn (HTML)",
                data=html_data,
                file_name=f"phieu_thu_{detail['ma_sv']}_{thang:02d}_{nam}.html",
                mime="text/html",
                key="cn01_dl_html",
                width="stretch",
            )
        with b2:
            st.download_button(
                label="Xuất phiếu thu (.xlsx)",
                data=export_excel(receipt_df, sheet_name=f"PhieuThu_{detail['ma_sv']}"),
                file_name=f"phieu_thu_{detail['ma_sv']}_{thang:02d}_{nam}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="cn01_dl_xlsx",
                width="stretch",
            )
        with b3:
            st.download_button(
                label="Xuất phiếu thu (.csv)",
                data=export_csv(receipt_df),
                file_name=f"phieu_thu_{detail['ma_sv']}_{thang:02d}_{nam}.csv",
                mime="text/csv",
                key="cn01_dl_csv",
                width="stretch",
            )


def render_tab_su_dung_dich_vu(thang: int, nam: int) -> None:
    """Giao diện: Báo cáo sử dụng dịch vụ theo kỳ với bộ lọc."""
    first_day = datetime.date(nam, thang, 1)
    last_day_num = calendar.monthrange(nam, thang)[1]
    last_day = datetime.date(nam, thang, last_day_num)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        tu_ngay = st.date_input("Từ ngày", value=first_day, key="cn02_from")
    with c2:
        den_ngay = st.date_input("Đến ngày", value=last_day, key="cn02_to")
    with c3:
        sv_opts = _get_student_options()
        sv_choice = st.selectbox(
            "Lọc theo sinh viên:",
            options=[opt[0] for opt in sv_opts],
            format_func=lambda code: next((opt[1] for opt in sv_opts if opt[0] == code), code),
            key="cn02_sv",
        )
    with c4:
        loai_dv_map = {
            "Tat ca": "Tất cả loại dịch vụ",
            "GIAT_LA": "Giặt là",
            "TRONG_XE": "Trông xe",
            "THUE_XE": "Thuê xe",
            "AN_UONG": "Ăn uống",
            "KHAC": "Khác",
        }
        loai_dv_opts = list(loai_dv_map.keys())
        loai_dv_choice = st.selectbox(
            "Loại dịch vụ:",
            options=loai_dv_opts,
            format_func=lambda k: loai_dv_map.get(k, k),
            key="cn02_dv",
        )

    df_usage = get_service_usage(tu_ngay, den_ngay, sv_choice, loai_dv_choice)

    if df_usage.empty:
        st.info("Không có dữ liệu sử dụng dịch vụ trong khoảng thời gian được chọn.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Số lượt sử dụng", f"{df_usage['so_lan_su_dung'].sum():,}")
    m2.metric("Tổng số lượng", f"{df_usage['tong_so_luong'].sum():,}")
    m3.metric("Tổng tiền dịch vụ", format_vnd(df_usage["tong_tien"].sum()))

    display_df = df_usage.copy()
    display_df["tong_tien"] = display_df["tong_tien"].apply(format_vnd)
    display_df.columns = [
        "Mã SV",
        "Họ và tên",
        "Mã DV",
        "Tên dịch vụ",
        "Số lần sử dụng",
        "Tổng số lượng",
        "Tổng tiền",
    ]
    display_table(display_df, title="Bảng kê sử dụng dịch vụ chi tiết")
    render_export_buttons(df_usage, f"su_dung_dich_vu_{tu_ngay}_{den_ngay}", "dv_usage")


def render_tab_khach_den_tham(thang: int, nam: int) -> None:
    """Giao diện: Thống kê khách đến thăm sinh viên trong kỳ."""
    first_day = datetime.date(nam, thang, 1)
    last_day_num = calendar.monthrange(nam, thang)[1]
    last_day = datetime.date(nam, thang, last_day_num)

    che_do = st.radio(
        "Chế độ lọc thời gian:",
        options=["Theo tháng hiện tại", "7 ngày gần nhất", "Khoảng ngày tùy chọn"],
        horizontal=True,
        key="khach_mode",
    )

    if che_do == "Theo tháng hiện tại":
        tu_ngay = first_day
        den_ngay = last_day
    elif che_do == "7 ngày gần nhất":
        den_ngay = last_day
        tu_ngay = last_day - datetime.timedelta(days=7)
    else:
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            tu_ngay = st.date_input("Từ ngày", value=first_day, key="khach_from")
        with col_d2:
            den_ngay = st.date_input("Đến ngày", value=last_day, key="khach_to")

    sv_opts = _get_student_options()
    sv_choice = st.selectbox(
        "Lọc theo sinh viên có khách đến thăm:",
        options=[opt[0] for opt in sv_opts],
        format_func=lambda code: next((opt[1] for opt in sv_opts if opt[0] == code), code),
        key="khach_sv",
    )

    df_vis = get_visitor_statistics(tu_ngay, den_ngay, sv_choice)

    if df_vis.empty:
        st.info("Không có lượt khách đến thăm nào trong khoảng thời gian được chọn.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Tổng lượt đến thăm", f"{df_vis['so_lan_den'].sum():,} lượt")
    m2.metric("Số sinh viên có khách", f"{df_vis['ma_sv'].nunique()} sinh viên")
    m3.metric("Số lượng khách duy nhất", f"{df_vis['cmt_khach'].nunique()} người")

    display_df = df_vis.copy()
    display_df.columns = [
        "Mã SV",
        "Tên sinh viên",
        "Số CMT / CCCD",
        "Tên khách",
        "Ngày sinh khách",
        "Số lần đến",
        "Lần đầu",
        "Lần cuối",
    ]
    display_table(display_df, title="Bảng thống kê khách đến thăm chi tiết")
    render_export_buttons(df_vis, f"khach_den_tham_{tu_ngay}_{den_ngay}", "khach")


def render_tab_doanh_thu_dich_vu(thang: int, nam: int) -> None:
    """Giao diện: Doanh thu theo từng danh mục dịch vụ trong tháng."""
    df_rev, metrics = get_service_revenue(thang, nam)

    c1, c2, c3 = st.columns(3)
    c1.metric("Doanh thu vé xe tháng", format_vnd(metrics["tien_ve"]))
    c2.metric("Phụ thu lượt gửi/lấy xe", format_vnd(metrics["tien_phu_thu"]))
    c3.metric("Tổng doanh thu toàn bộ", format_vnd(metrics["tong_doanh_thu"]))

    if df_rev.empty:
        st.info("Không có dữ liệu doanh thu dịch vụ cho kỳ được chọn.")
        return

    display_df = df_rev.copy()
    display_df["doanh_thu_thang"] = display_df["doanh_thu_thang"].apply(format_vnd)
    display_df.columns = [
        "Mã DV",
        "Tên dịch vụ",
        "Loại dịch vụ",
        "Doanh thu tháng",
    ]
    display_table(display_df, title=f"Doanh thu theo danh mục dịch vụ tháng {thang:02d}/{nam}")
    render_export_buttons(df_rev, f"doanh_thu_dich_vu_{thang:02d}_{nam}", "doanh_thu")


def render_reports(thang_sidebar: int, nam_sidebar: int) -> None:
    """Điều phối 4 Tab chức năng báo cáo và hóa đơn nghiệp vụ KTX."""
    styled_header(
        "Báo cáo & Hóa đơn",
        f"Các báo cáo nghiệp vụ tổng hợp tháng {thang_sidebar:02d}/{nam_sidebar}",
    )

    tab1, tab2, tab3, tab4 = st.tabs([
        "Tổng hợp hóa đơn",
        "Báo cáo sử dụng dịch vụ",
        "Thống kê khách đến thăm",
        "Doanh thu dịch vụ",
    ])

    with tab1:
        render_tab_hoa_don_thang(thang_sidebar, nam_sidebar)
    with tab2:
        render_tab_su_dung_dich_vu(thang_sidebar, nam_sidebar)
    with tab3:
        render_tab_khach_den_tham(thang_sidebar, nam_sidebar)
    with tab4:
        render_tab_doanh_thu_dich_vu(thang_sidebar, nam_sidebar)
