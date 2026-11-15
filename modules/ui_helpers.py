"""Bộ công cụ tiện ích UI chuẩn hóa cho Streamlit App (UI Helpers).

Cung cấp các hàm tiện ích bám sát Streamlit Best Practices:
- Sử dụng width="stretch" thay vì use_container_width đã deprecated.
- Đồng bộ bảng màu thương hiệu #1E3A8A.
- Hỗ trợ xuất file Excel, CSV và định dạng tiền tệ VNĐ.
- Tuyệt đối không sử dụng icon hay emoji trong toàn bộ thành phần UI.
"""

import io
import re
from decimal import Decimal
from typing import Optional, Union
import streamlit as st
import pandas as pd


def _clean_feedback_message(message: str) -> str:
    """Loại bỏ tiền tố lặp như 'Lỗi: Loi:', 'Lỗi: Lỗi:', 'Loi: Loi:'."""
    if not message:
        return ""
    return re.sub(r'^(?:Lỗi|Loi):\s*(?:Lỗi|Loi):\s*', 'Lỗi: ', str(message).strip(), flags=re.IGNORECASE)


def styled_header(title: str, subtitle: Optional[str] = None) -> None:
    """Hiển thị tiêu đề phân khu với mô tả phụ đồng bộ giao diện."""
    st.markdown(
        f"""
        <div style="padding: 5px 0 15px 0;">
            <h2 style="margin: 0; color: #1E3A8A; font-weight: 700;">{title}</h2>
            {f'<p style="margin: 4px 0 0 0; color: #64748B; font-size: 0.95rem;">{subtitle}</p>' if subtitle else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )


def set_flash_feedback(success: bool, message: str, trigger_toast: bool = True) -> None:
    """Lưu trữ thông báo tạm thời vào session_state để hiển thị sau st.rerun()."""
    st.session_state["_flash_feedback"] = {
        "success": bool(success),
        "message": _clean_feedback_message(message),
        "trigger_toast": bool(trigger_toast),
    }


def render_pending_feedback() -> None:
    """Kiểm tra và hiển thị thông báo flash đang chờ trong session_state."""
    feedback = st.session_state.pop("_flash_feedback", None)
    if feedback:
        msg = feedback.get("message", "")
        is_success = feedback.get("success", True)
        if feedback.get("trigger_toast", True):
            try:
                st.toast(msg, icon=None)
            except Exception:
                pass
        if is_success:
            st.success(msg)
        else:
            st.error(msg)


def show_feedback(success: bool, message: str, use_toast: bool = True) -> None:
    """Hiển thị thông báo kết quả thực thi an toàn kèm toast (dành cho thao tác không rerun)."""
    clean_msg = _clean_feedback_message(message)
    if use_toast:
        try:
            st.toast(clean_msg, icon=None)
        except Exception:
            pass
    if success:
        st.success(clean_msg)
    else:
        st.error(clean_msg)


def display_table(
    df: pd.DataFrame,
    title: Optional[str] = None,
    height: Optional[int] = None,
    hide_index: bool = True,
) -> None:
    """Hiển thị bảng dữ liệu chuẩn hóa với width='stretch'."""
    if title:
        st.markdown(f"**{title}**")
    if df.empty:
        st.info("Không có dữ liệu phù hợp với điều kiện lọc.")
        return

    kwargs = {"width": "stretch", "hide_index": hide_index}
    if height is not None:
        kwargs["height"] = height
    st.dataframe(df, **kwargs)


def format_vnd(amount: Optional[Union[int, float, Decimal]]) -> str:
    """Định dạng số tiền thành chuỗi tiền tệ VNĐ với khoảng trắng không ngắt."""
    if amount is None:
        return "0\u00a0đ"
    try:
        val = int(round(float(amount)))
        return f"{val:,}\u00a0đ".replace(",", ".")
    except (ValueError, TypeError):
        return "0\u00a0đ"


def number_to_vietnamese_words(amount: Optional[Union[int, float, Decimal]]) -> str:
    """Chuyển đổi số tiền nguyên sang chữ tiếng Việt thuần Python."""
    if amount is None:
        return "Không đồng"
    try:
        val = int(round(float(amount)))
    except (ValueError, TypeError):
        return "Không đồng"

    if val == 0:
        return "Không đồng"
    if val < 0:
        return "Âm " + number_to_vietnamese_words(-val).lower()

    units_map = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    scales = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ", "tỷ tỷ"]

    def read_three_digits(n: int, has_higher: bool) -> list[str]:
        h = n // 100
        t = (n % 100) // 10
        u = n % 10
        words: list[str] = []

        show_hundred = (h > 0) or (has_higher and (t > 0 or u > 0))
        if show_hundred:
            words.extend([units_map[h], "trăm"])

        if t > 1:
            words.extend([units_map[t], "mươi"])
            if u == 1:
                words.append("mốt")
            elif u == 4:
                words.append("tư")
            elif u == 5:
                words.append("lăm")
            elif u > 0:
                words.append(units_map[u])
        elif t == 1:
            words.append("mười")
            if u == 5:
                words.append("lăm")
            elif u > 0:
                words.append(units_map[u])
        elif t == 0:
            if show_hundred and u > 0:
                words.extend(["lẻ", units_map[u]])
            elif not show_hundred and u > 0:
                words.append(units_map[u])

        return words

    chunks: list[int] = []
    temp = val
    while temp > 0:
        chunks.append(temp % 1000)
        temp //= 1000

    result_words: list[str] = []
    for i in range(len(chunks) - 1, -1, -1):
        chunk = chunks[i]
        if chunk == 0:
            continue
        has_higher = any(c > 0 for c in chunks[i + 1:])
        chunk_words = read_three_digits(chunk, has_higher)
        if chunk_words:
            result_words.extend(chunk_words)
            scale = scales[i] if i < len(scales) else "tỷ"
            if scale:
                result_words.append(scale)

    text = " ".join(result_words)
    if text:
        return text[0].upper() + text[1:] + " đồng"
    return "Không đồng"


def export_excel(df: pd.DataFrame, sheet_name: str = "BaoCao") -> bytes:
    """Xuất DataFrame sang file Excel (.xlsx) bằng BytesIO và openpyxl."""
    export_df = df.copy()
    for col in export_df.columns:
        if export_df[col].dtype == object:
            if export_df[col].apply(lambda x: isinstance(x, Decimal)).any():
                export_df[col] = export_df[col].apply(
                    lambda x: float(x) if isinstance(x, Decimal) else x
                )
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export_df.to_excel(writer, sheet_name=sheet_name, index=False)
    return output.getvalue()


def export_csv(df: pd.DataFrame) -> bytes:
    """Xuất DataFrame sang CSV mã hóa utf-8-sig cho Excel trên Windows."""
    return df.to_csv(index=False).encode("utf-8-sig")


def render_export_buttons(
    df: pd.DataFrame,
    file_prefix: str,
    key_prefix: str = "export",
) -> None:
    """Tạo 2 cột hiển thị nút xuất file Excel và CSV không dùng icon."""
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Xuất file Excel (.xlsx)",
            data=export_excel(df),
            file_name=f"{file_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{key_prefix}_xlsx",
            width="stretch",
        )
    with col2:
        st.download_button(
            label="Xuất file CSV (.csv)",
            data=export_csv(df),
            file_name=f"{file_prefix}.csv",
            mime="text/csv",
            key=f"{key_prefix}_csv",
            width="stretch",
        )
