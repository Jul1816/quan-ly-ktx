"""Bộ công cụ kiểm thử tự động (Health Check & AppTest) cho Streamlit App.

Sử dụng streamlit.testing.v1.AppTest để mô phỏng tải giao diện không cần mở trình duyệt,
hỗ trợ AI Agent và Lập trình viên kiểm chứng nhanh trạng thái hoạt động của app.
"""

import unittest
from pathlib import Path


class TestStreamlitApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app_path = Path(__file__).parent / "app.py"

    def test_app_file_exists(self):
        """Kiểm tra file app.py tồn tại."""
        self.assertTrue(self.app_path.exists(), f"Không tìm thấy file {self.app_path}")

    def test_streamlit_apptest_run(self):
        """Khởi chạy headless Streamlit AppTest để phát hiện lỗi cú pháp và runtime."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(self.app_path), default_timeout=15)
        at.run()

        # Kiểm tra xem có Exception/Error nào bị ném ra mà không được bắt không
        if at.exception:
            # Ghi nhận chi tiết exception nếu có
            error_msgs = [e.value for e in at.exception]
            self.fail(f"Streamlit AppTest gặp lỗi runtime ngoại lệ: {error_msgs}")

        # Kiểm tra trang đã render ít nhất 1 thành phần
        has_content = len(at.markdown) > 0 or len(at.sidebar.radio) > 0 or len(at.title) > 0
        self.assertTrue(has_content, "App không render bất kỳ nội dung nào lên giao diện.")

    def test_all_six_menu_sections_render_cleanly(self):
        """Kiểm tra duyệt lần lượt toàn bộ 6 phân khu trên menu điều hướng."""
        from streamlit.testing.v1 import AppTest
        from pathlib import Path

        app_path = Path(__file__).parent / "app.py"
        at = AppTest.from_file(str(app_path), default_timeout=20)
        at.run()
        menu_items = [
            "Tổng quan (Dashboard)",
            "Báo cáo & Hóa đơn cốt lõi (CN-01 -> CN-04)",
            "Kiểm chứng Ràng buộc Trigger (CN-05)",
            "Quản lý Phòng & Lưu trú Sinh viên (Bổ trợ 2, 3, 4, 5)",
            "Quản lý Bãi giữ xe & Xe vãng lai (Bổ trợ 6, 7, 8)",
            "Ghi nhận Dịch vụ & Khách thăm (Bổ trợ 9)",
        ]
        for item in menu_items:
            at.sidebar.radio[0].set_value(item)
            at.run()
            self.assertFalse(at.exception, f"Gặp lỗi khi render phân khu '{item}': {[e.value for e in at.exception]}")


    def test_ui_helpers_formatting_and_export(self):
        """Kiem tra cac tien ich format tien te, doc so thanh chu va xuat file Excel, CSV."""
        import io
        from decimal import Decimal
        import pandas as pd
        import openpyxl
        from modules.ui_helpers import (
            format_vnd,
            number_to_vietnamese_words,
            export_excel,
            export_csv,
            render_export_buttons,
        )

        # Kiem tra format_vnd
        self.assertEqual(format_vnd(400000), "400.000\u00a0đ")
        self.assertEqual(format_vnd(Decimal("851000.00")), "851.000\u00a0đ")
        self.assertEqual(format_vnd(0), "0\u00a0đ")
        self.assertEqual(format_vnd(None), "0\u00a0đ")

        # Kiem tra number_to_vietnamese_words
        words_851k = number_to_vietnamese_words(851000)
        self.assertEqual(words_851k, "Tám trăm năm mươi mốt nghìn đồng")
        self.assertEqual(number_to_vietnamese_words(0), "Không đồng")
        self.assertEqual(number_to_vietnamese_words(1000000), "Một triệu đồng")
        self.assertEqual(number_to_vietnamese_words(1000000000), "Một tỷ đồng")

        # Kiem tra export_excel voi cot chua Decimal
        df = pd.DataFrame([
            {"ma_sv": "SV001", "tien_phong": Decimal("400000.00"), "tong_tien": Decimal("851000.00")},
            {"ma_sv": "SV002", "tien_phong": Decimal("500000.00"), "tong_tien": Decimal("528000.00")},
        ])
        excel_bytes = export_excel(df, sheet_name="BaoCaoTest")
        self.assertIsInstance(excel_bytes, bytes)
        self.assertGreater(len(excel_bytes), 0)

        wb = openpyxl.load_workbook(io.BytesIO(excel_bytes))
        self.assertIn("BaoCaoTest", wb.sheetnames)
        ws = wb["BaoCaoTest"]
        self.assertEqual(ws.cell(row=2, column=2).value, 400000.0)

        # Kiem tra export_csv voi utf-8-sig
        csv_bytes = export_csv(df)
        self.assertIsInstance(csv_bytes, bytes)
        self.assertTrue(csv_bytes.startswith(b"\xef\xbb\xbf"))
        csv_text = csv_bytes.decode("utf-8-sig")
        self.assertIn("SV001", csv_text)
        self.assertIn("400000.00", csv_text)

        # Kiem tra render_export_buttons callable
        self.assertTrue(callable(render_export_buttons))

    def test_format_vnd_non_breaking_space(self):
        """Kiem tra format_vnd su dung khoang trang khong ngat \u00a0đ theo Vercel Web Guidelines."""
        from modules.ui_helpers import format_vnd
        self.assertEqual(format_vnd(400000), "400.000\u00a0đ")
        self.assertEqual(format_vnd(0), "0\u00a0đ")
        self.assertEqual(format_vnd(None), "0\u00a0đ")

    def test_reports_data_layer(self):
        """Kiem tra cac ham truy van CTE cua phan khu bao cao va hoa don."""
        from modules.reports import (
            get_date_bounds,
            get_monthly_invoices,
            get_student_invoice_detail,
            get_service_usage,
            get_visitor_statistics,
            get_service_revenue,
        )

        # Kiem tra xac dinh moc thoi gian dau thang va dau thang sau
        dau_thang, dau_thang_sau = get_date_bounds(10, 2026)
        self.assertEqual(dau_thang, "2026-10-01")
        self.assertEqual(dau_thang_sau, "2026-11-01")

        # Kiem tra CN-01: tong hop hoa don thang 10/2026
        df_inv = get_monthly_invoices(10, 2026)
        self.assertEqual(len(df_inv), 5)
        inv_map = df_inv.set_index("ma_sv")["tong_phai_tra"].to_dict()
        self.assertEqual(inv_map["SV001"], 761000)
        self.assertEqual(inv_map["SV002"], 528000)
        self.assertEqual(inv_map["SV003"], 750000)
        self.assertEqual(inv_map["SV004"], 405000)
        self.assertEqual(inv_map["SV005"], 650000)
        self.assertEqual(df_inv["tong_phai_tra"].sum(), 3094000)

        # Kiem tra phieu bao thu ca nhan kem so phong
        detail_sv1 = get_student_invoice_detail("SV001", 10, 2026)
        self.assertIsNotNone(detail_sv1)
        self.assertEqual(detail_sv1["so_phong"], "A101")
        self.assertEqual(detail_sv1["tien_phong"], 400000)
        self.assertEqual(detail_sv1["tien_dich_vu"], 155000)
        self.assertEqual(detail_sv1["tien_ve_thang"], 200000)
        self.assertEqual(detail_sv1["tien_phu_thu_xe"], 6000)
        self.assertEqual(detail_sv1["tong_phai_tra"], 761000)

        # Kiem tra CN-02: bao cao su dung dich vu
        df_usage = get_service_usage("2026-10-01", "2026-10-31")
        self.assertGreater(len(df_usage), 0)
        df_usage_sv1 = get_service_usage("2026-10-01", "2026-10-31", ma_sv="SV001")
        self.assertEqual(len(df_usage_sv1), 2)

        # Kiem tra CN-03: thong ke khach den tham
        df_visitors = get_visitor_statistics("2026-10-01", "2026-10-31")
        self.assertGreater(len(df_visitors), 0)
        df_visitors_sv1 = get_visitor_statistics("2026-10-01", "2026-10-31", ma_sv="SV001")
        self.assertEqual(len(df_visitors_sv1), 2)

        # Kiem tra CN-04: doanh thu dich vu thang
        df_rev, metrics = get_service_revenue(10, 2026)
        self.assertEqual(metrics["tien_ve"], 300000)
        self.assertEqual(metrics["tien_phu_thu"], 9000)
        self.assertEqual(metrics["tong_doanh_thu"], 694000)
        self.assertEqual(len(df_rev), 4)

        # Kiem tra mau phieu thu in an HTML Bo tro 10
        from modules.reports import _generate_receipt_html, render_reports
        html_doc = _generate_receipt_html(detail_sv1)
        self.assertIn("@page", html_doc)
        self.assertIn("A4", html_doc)
        self.assertIn("SV001", html_doc)
        self.assertIn("A101", html_doc)
        self.assertTrue(callable(render_reports))

    def test_reports_streamlit_apptest(self):
        """Kiem tra runtime headless Streamlit AppTest khi render phan khu bao cao."""
        from streamlit.testing.v1 import AppTest

        test_code = """
from modules.reports import render_reports
render_reports(10, 2026)
"""
        at = AppTest.from_string(test_code, default_timeout=30)
        at.run()

        if at.exception:
            error_msgs = [e.value for e in at.exception]
            self.fail(f"render_reports gap ngoai le Streamlit runtime: {error_msgs}")

        self.assertGreater(len(at.tabs), 0)
        self.assertGreater(len(at.dataframe), 0)
        self.assertGreater(len(at.metric), 0)

    def test_full_app_navigation_and_rendering(self):
        """Kiem tra dieu huong menu sidebar toan dien qua Streamlit AppTest."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(self.app_path), default_timeout=30)
        at.run()

        # 1. Kiem tra trang Dashboard mac dinh
        self.assertEqual(len(at.exception), 0)
        self.assertGreater(len(at.metric), 0)

        # 2. Chuyen sang phan khu Bao cao & Hoa don cot loi
        at.sidebar.radio[0].set_value("Báo cáo & Hóa đơn cốt lõi (CN-01 -> CN-04)").run()
        self.assertEqual(len(at.exception), 0)
        self.assertGreater(len(at.tabs), 0, "Phan khu bao cao chua duoc tich hop tabs vao app.py")

        # 3. Chuyen sang phan khu Kiem chung Rang buoc Trigger
        at.sidebar.radio[0].set_value("Kiểm chứng Ràng buộc Trigger (CN-05)").run()
        self.assertEqual(len(at.exception), 0)
        self.assertGreater(len(at.button), 0, "Phan khu kiem chung trigger chua duoc tich hop buttons vao app.py")


    def test_trigger_validation_logic(self):
        """Kiem tra logic lay trang thai trigger, 4 kich ban vi pham va phi gui xe."""
        from modules.trigger_validation import (
            get_triggers_status,
            get_parking_fee_audit,
            run_trigger_test,
        )

        # 1. Kiem tra danh sach trigger
        df_trg = get_triggers_status()
        self.assertGreaterEqual(len(df_trg), 5)
        for col in ["TRIGGER_NAME", "EVENT_MANIPULATION", "EVENT_OBJECT_TABLE", "ACTION_TIMING"]:
            self.assertIn(col, df_trg.columns)

        trg_names = df_trg["TRIGGER_NAME"].tolist()
        self.assertIn("trg_phong_insert", trg_names)
        self.assertIn("trg_phong_update", trg_names)
        self.assertIn("trg_xe_insert", trg_names)
        self.assertIn("trg_xe_update", trg_names)
        self.assertIn("trg_luot_xe_insert", trg_names)

        # 2. Kiem tra 4 kich ban vi pham trigger
        expected_keywords = {
            1: "Phong da du so nguoi toi da",
            2: "Sinh vien da co lich su o phong trung khoang thoi gian nay",
            3: "Moi sinh vien chi duoc dang ky toi da 2 xe ve thang cung thoi diem",
            4: "Xe chua dang ky hoac ve thang khong con hieu luc tai ngay gui",
        }

        for tid, keyword in expected_keywords.items():
            ok, sql, msg = run_trigger_test(tid)
            self.assertFalse(ok, f"Kich ban {tid} khong bi trigger chan.")
            self.assertGreater(len(sql), 0)
            self.assertIn(keyword, msg, f"Thong diep loi kich ban {tid} khong chua '{keyword}'.")

        # 3. Kiem tra bang audit phi gui xe
        df_audit = get_parking_fee_audit()
        self.assertEqual(len(df_audit), 8)
        for col in ["ma_luot", "bien_so", "thoi_gian_gui", "thoi_gian_lay", "so_tien_phai_tra"]:
            self.assertIn(col, df_audit.columns)

        fees = [int(float(f)) for f in df_audit["so_tien_phai_tra"].tolist()]
        self.assertEqual(fees, [0, 0, 3000, 3000, 0, 0, 0, 3000])

    def test_trigger_validation_streamlit_apptest(self):
        """Kiem tra runtime headless Streamlit AppTest cho render_trigger_validation."""
        from streamlit.testing.v1 import AppTest

        test_code = """
from modules.trigger_validation import render_trigger_validation
render_trigger_validation()
"""
        at = AppTest.from_string(test_code, default_timeout=30)
        at.run()

        if at.exception:
            error_msgs = [e.value for e in at.exception]
            self.fail(f"render_trigger_validation gap ngoai le Streamlit runtime: {error_msgs}")

        self.assertGreater(len(at.button), 0)
        self.assertGreater(len(at.dataframe), 0)

    def test_db_execute_transaction_success_and_rollback(self):
        """Kiem tra ham execute_transaction thanh cong va tu dong rollback khi gap loi."""
        import db

        # Kiem tra transaction thanh cong
        success, msg = db.execute_transaction([
            ("SELECT 1;", ()),
            ("SELECT 2;", ()),
        ])
        self.assertTrue(success)
        self.assertEqual(msg, "Thành công")

        # Kiem tra transaction rollback khi gap loi
        success_err, msg_err = db.execute_transaction([
            ("SELECT 1;", ()),
            ("INSERT INTO bang_khong_ton_tai VALUES (1);", ()),
        ])
        self.assertFalse(success_err)
        self.assertIn("bang_khong_ton_tai", msg_err)

    def test_tab1_room_occupancy_and_details(self):
        """Kiem tra cac ham truy van phong, ty le lap day va chi tiet nguoi o cua Tab 1."""
        from modules.room_management import (
            get_room_occupancy_list,
            get_students_in_room,
            add_new_room,
            update_room,
        )
        df_rooms = get_room_occupancy_list(only_available=False)
        self.assertFalse(df_rooms.empty)
        self.assertIn("so_phong", df_rooms.columns)
        self.assertIn("so_nguoi_dang_o", df_rooms.columns)
        self.assertIn("ty_le_lap_day", df_rooms.columns)
        self.assertIn("trang_thai_cho", df_rooms.columns)

        # Phong A101 co 2 nguoi dang o (SV001, SV002)
        df_a101 = get_students_in_room("A101")
        self.assertEqual(len(df_a101), 2)
        self.assertIn("SV001", df_a101["ma_sv"].values)
        self.assertIn("SV002", df_a101["ma_sv"].values)

        # Kiem tra phong A102 da day (2/2 cho)
        df_avail = get_room_occupancy_list(only_available=True)
        self.assertNotIn("A102", df_avail["so_phong"].values)

        # Kiem tra update_room can so_nguoi_toi_da >= so_nguoi_dang_o
        ok, msg = update_room("A101", "Phong 4 nguoi", 400000, 1)
        self.assertFalse(ok)
        self.assertIn("nhỏ hơn số sinh viên đang ở", msg)

    def test_tab2_student_crud_and_360_profile(self):
        """Kiem tra tim kiem, CRUD sinh vien va tra cuu ho so 360 do cua Tab 2."""
        from modules.room_management import (
            search_students,
            get_student_profile_360,
            add_student,
            update_student,
            delete_student,
        )
        # Tim kiem theo ten
        df_search = search_students("Nguyen Van An")
        self.assertFalse(df_search.empty)
        self.assertEqual(df_search.iloc[0]["ma_sv"], "SV001")

        # Ho so 360 do cua SV001 co day du 4 nhom lich su va khong rong
        p360 = get_student_profile_360("SV001")
        self.assertIn("lich_su_o", p360)
        self.assertIn("dich_vu", p360)
        self.assertIn("xe_ve_thang", p360)
        self.assertIn("khach_tham", p360)
        self.assertFalse(p360["lich_su_o"].empty)
        self.assertFalse(p360["dich_vu"].empty)
        self.assertFalse(p360["xe_ve_thang"].empty)
        self.assertFalse(p360["khach_tham"].empty)

        # Kiem tra xoa SV001 bi chan boi rang buoc khoa ngoai
        success, msg = delete_student("SV001")
        self.assertFalse(success)
        self.assertIn("ràng buộc", msg.lower())

        # Kiem tra them, cap nhat va xoa sinh vien moi hop le
        delete_student("SV999")  # Dam bao khong bi sot tu test cu
        ok_add, msg_add = add_student(
            ma_sv="SV999",
            so_cmt="999999999",
            ho_ten="Sinh Vien Test",
            ngay_sinh="2004-01-01",
            lop="CNTT1",
            que_quan="Ha Noi",
        )
        self.assertTrue(ok_add, f"add_student that bai: {msg_add}")

        df_added = search_students("SV999")
        self.assertEqual(len(df_added), 1)
        self.assertEqual(df_added.iloc[0]["ho_ten"], "Sinh Vien Test")

        ok_upd, msg_upd = update_student(
            ma_sv="SV999",
            so_cmt="999999999",
            ho_ten="Sinh Vien Test Update",
            ngay_sinh="2004-01-01",
            lop="CNTT2",
            que_quan="Hai Phong",
        )
        self.assertTrue(ok_upd, f"update_student that bai: {msg_upd}")

        df_upd = search_students("SV999")
        self.assertEqual(df_upd.iloc[0]["ho_ten"], "Sinh Vien Test Update")
        self.assertEqual(df_upd.iloc[0]["lop"], "CNTT2")

        ok_del, msg_del = delete_student("SV999")
        self.assertTrue(ok_del, f"delete_student SV999 that bai: {msg_del}")

        df_empty = search_students("SV999")
        self.assertTrue(df_empty.empty)

    def test_tab3_checkin_and_trigger_validation(self):
        """Kiem tra chuc nang xep phong va bat loi Trigger trg_phong_insert cua Tab 3."""
        from modules.room_management import (
            get_student_options_for_checkin,
            get_room_options_for_checkin,
            checkin_student,
        )
        sv_options = get_student_options_for_checkin()
        self.assertGreater(len(sv_options), 0)
        sv006 = next(item for item in sv_options if item["ma_sv"] == "SV006")
        self.assertIsNone(sv006["phong_hien_tai"])

        # Kiem tra lay danh sach phong options
        room_options = get_room_options_for_checkin()
        self.assertGreater(len(room_options), 0)

        # Xep SV006 vao phong A102 da day (2/2 cho) -> Bi trigger chan
        success, msg = checkin_student("SV006", "A102", "2026-10-25", 650000.0)
        self.assertFalse(success)
        self.assertIn("Phong da du so nguoi toi da", msg)

        # Xep SV002 trung thoi gian dang o A101 -> Bi trigger chan trung lich
        success2, msg2 = checkin_student("SV002", "B201", "2026-10-20", 300000.0)
        self.assertFalse(success2)
        self.assertIn("trung khoang thoi gian nay", msg2)

    def test_tab4_checkout_and_transfer_transaction(self):
        """Kiem tra chuc nang tra phong va chuyen phong an toan bang Transaction cua Tab 4."""
        from modules.room_management import (
            get_active_stays,
            checkout_student,
            transfer_student_room,
        )

        stays = get_active_stays()
        self.assertGreater(len(stays), 0)

        # Kiem tra validation ngay_ra < ngay_vao khi checkout
        success_val, msg_val = checkout_student(
            ma_o=stays[0]["ma_o"],
            ngay_ra="2020-01-01",
            ngay_vao=str(stays[0]["ngay_vao"]),
        )
        self.assertFalse(success_val)
        self.assertIn("phải lớn hơn hoặc bằng", msg_val)

        # Kiem tra chuyen phong sang phong A102 da day -> Transaction rollback, phong cu khong bi chot
        sv001_stay = next(s for s in stays if s["ma_sv"] == "SV001")
        success_tr, msg_tr = transfer_student_room(
            ma_o_cu=sv001_stay["ma_o"],
            ma_sv="SV001",
            so_phong_moi="A102",
            ngay_chuyen="2026-11-01",
            ngay_vao_cu=str(sv001_stay["ngay_vao"]),
            don_gia_moi=650000.0,
        )
        self.assertFalse(success_tr)
        self.assertIn("Phong da du so nguoi toi da", msg_tr)

        # Xac minh lai SV001 van dang o phong A101 (ngay_ra IS NULL)
        stays_after = get_active_stays()
        sv001_after = next(s for s in stays_after if s["ma_sv"] == "SV001")
        self.assertEqual(sv001_after["so_phong"], "A101")

    def test_render_room_management_callable(self):
        """Kiểm tra hàm render_room_management tồn tại và có thể gọi được."""
        from modules.room_management import render_room_management

        self.assertTrue(callable(render_room_management))

    def test_streamlit_apptest_room_management_menu(self):
        """Kiểm tra AppTest khi người dùng chọn menu Quản lý Phòng & Lưu trú Sinh viên."""
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_file(str(self.app_path), default_timeout=15)
        at.run()
        # Chọn menu phân khu phòng
        at.sidebar.radio[0].set_value("Quản lý Phòng & Lưu trú Sinh viên (Bổ trợ 2, 3, 4, 5)").run()
        if at.exception:
            error_msgs = [e.value for e in at.exception]
            self.fail(f"Menu Quản lý Phòng & Lưu trú gặp lỗi runtime: {error_msgs}")
        self.assertFalse(at.exception)

    def test_parking_management_data_layer(self):
        """Kiểm tra toàn diện các hàm nghiệp vụ vé xe tháng và lượt gửi/lấy xe."""
        import datetime
        from decimal import Decimal
        from modules.parking_management import (
            get_monthly_tickets,
            register_monthly_ticket,
            cancel_monthly_ticket,
            record_parking_turn,
            get_parking_logs,
        )
        import db

        bien_so_test = "29X-88888"
        try:
            # 1. Truy vấn danh sách vé tháng hiện tại
            df_tickets = get_monthly_tickets()
            self.assertFalse(df_tickets.empty)
            self.assertIn("bien_so", df_tickets.columns)
            self.assertIn("trang_thai", df_tickets.columns)

            # 2. Kiểm tra Trigger trg_xe_insert chặn xe thứ 3 của SV001
            success_err, msg_err = register_monthly_ticket(
                bien_so="29A-99999",
                ma_sv="SV001",
                loai_xe="Xe may Wave",
                ngay_dang_ky=datetime.date(2026, 10, 25),
            )
            self.assertFalse(success_err)
            self.assertIn("Moi sinh vien chi duoc dang ky toi da 2 xe ve thang", msg_err)

            # 3. Đăng ký xe hợp lệ cho SV003 (chưa có xe nào)
            success_ok, msg_ok = register_monthly_ticket(
                bien_so=bien_so_test,
                ma_sv="SV003",
                loai_xe="Xe dap dien VinFast",
                ngay_dang_ky=datetime.date(2026, 10, 1),
            )
            self.assertTrue(success_ok)

            # 4. Kiểm tra logic chặn thời gian lấy <= thời gian gửi
            dt_invalid_gui = datetime.datetime(2026, 10, 5, 10, 0, 0)
            dt_invalid_lay = datetime.datetime(2026, 10, 5, 9, 0, 0)
            suc_time, msg_time, _, _ = record_parking_turn(bien_so_test, dt_invalid_gui, dt_invalid_lay)
            self.assertFalse(suc_time)
            self.assertIn("Thời gian lấy xe phải sau thời gian gửi", msg_time)

            # 5. Ghi nhận lượt xe cho 29X-88888: Lượt 1 trong ngày 2026-10-05 (kỳ vọng 0đ)
            dt_gui1 = datetime.datetime(2026, 10, 5, 8, 0, 0)
            dt_lay1 = datetime.datetime(2026, 10, 5, 10, 0, 0)
            suc1, msg1, fee1, turn1 = record_parking_turn(bien_so_test, dt_gui1, dt_lay1)
            self.assertTrue(suc1)
            self.assertEqual(fee1, Decimal("0.00"))
            self.assertEqual(turn1, 1)

            # Lượt 2 trong ngày 2026-10-05 (kỳ vọng 0đ)
            dt_gui2 = datetime.datetime(2026, 10, 5, 11, 0, 0)
            dt_lay2 = datetime.datetime(2026, 10, 5, 12, 0, 0)
            suc2, msg2, fee2, turn2 = record_parking_turn(bien_so_test, dt_gui2, dt_lay2)
            self.assertTrue(suc2)
            self.assertEqual(fee2, Decimal("0.00"))
            self.assertEqual(turn2, 2)

            # Lượt 3 trong ngày 2026-10-05 (kỳ vọng phụ thu 3.000đ)
            dt_gui3 = datetime.datetime(2026, 10, 5, 14, 0, 0)
            dt_lay3 = datetime.datetime(2026, 10, 5, 15, 0, 0)
            suc3, msg3, fee3, turn3 = record_parking_turn(bien_so_test, dt_gui3, dt_lay3)
            self.assertTrue(suc3)
            self.assertEqual(fee3, Decimal("3000.00"))
            self.assertEqual(turn3, 3)

            # 6. Kiểm tra Trigger trg_luot_xe_insert chặn xe chưa đăng ký
            suc_fail, msg_fail, _, _ = record_parking_turn(
                "99Z-00000",
                datetime.datetime(2026, 10, 5, 8, 0, 0),
                datetime.datetime(2026, 10, 5, 9, 0, 0),
            )
            self.assertFalse(suc_fail)
            self.assertIn("Xe chua dang ky hoac ve thang khong con hieu luc", msg_fail)

            # 7. Kiểm tra hàm get_parking_logs có dữ liệu của bien_so_test
            df_logs = get_parking_logs(bien_so=bien_so_test)
            self.assertEqual(len(df_logs), 3)

            # 8. Kiểm tra hủy vé xe tháng (cancel_monthly_ticket)
            suc_cancel, msg_cancel = cancel_monthly_ticket(bien_so_test, datetime.date(2026, 10, 30))
            self.assertTrue(suc_cancel)
            df_cancelled = get_monthly_tickets(only_active=True)
            self.assertFalse(any(df_cancelled["bien_so"] == bien_so_test))
        finally:
            # Dọn dẹp dữ liệu an toàn trong mọi tình huống
            db.execute_query("DELETE FROM luot_gui_lay_xe WHERE bien_so = %s;", (bien_so_test,))
            db.execute_query("DELETE FROM xe_ve_thang WHERE bien_so = %s;", (bien_so_test,))

    def test_render_parking_management_callable(self):
        """Kiểm tra hàm render_parking_management tồn tại và có thể gọi được."""
        from modules.parking_management import render_parking_management

        self.assertTrue(callable(render_parking_management))

    def test_render_parking_management_ui(self):
        """Kiểm tra render giao diện Phân khu 5 không ném ngoại lệ."""
        from streamlit.testing.v1 import AppTest
        from pathlib import Path

        app_path = Path(__file__).parent / "app.py"
        at = AppTest.from_file(str(app_path), default_timeout=15)
        at.run()
        # Chọn phân khu Quản lý Bãi giữ xe & Xe vãng lai
        radio_menu = at.sidebar.radio[0]
        radio_menu.set_value("Quản lý Bãi giữ xe & Xe vãng lai (Bổ trợ 6, 7, 8)")
        at.run()
        self.assertFalse(at.exception, f"Lỗi render Phân khu 5: {[e.value for e in at.exception]}")
        # Kiểm tra tồn tại 3 tabs
        self.assertTrue(len(at.tabs) >= 3, "Phân khu 5 không hiển thị đủ 3 tabs nghiệp vụ.")

    def test_service_guest_management_data_layer(self):
        """Kiểm tra toàn diện các hàm nghiệp vụ dịch vụ và sổ trực khách đến thăm."""
        import datetime
        from decimal import Decimal
        from modules.service_guest_management import (
            get_services_catalog,
            add_service_usage,
            add_new_service,
            update_service_price,
            get_service_usage_history,
            record_guest_visit,
            get_guest_visit_logs,
        )
        import db

        now_dt = datetime.datetime(2026, 10, 25, 9, 30, 0)
        cmt_test = "099999888888"
        ma_dv_test = "DV99"

        try:
            # 1. Kiểm tra danh mục dịch vụ
            df_services = get_services_catalog()
            self.assertFalse(df_services.empty)
            self.assertIn("ma_dv", df_services.columns)
            self.assertIn("don_gia", df_services.columns)

            # 2. Thêm dịch vụ mới hợp lệ và kiểm tra từ chối ENUM không hợp lệ
            suc_dv_bad, msg_dv_bad = add_new_service("DVXX", "Test DV", "SAI_ENUM", Decimal("10000"))
            self.assertFalse(suc_dv_bad)
            self.assertIn("Loại dịch vụ không hợp lệ", msg_dv_bad)

            suc_dv_ok, msg_dv_ok = add_new_service(ma_dv_test, "Dich vu Test", "KHAC", Decimal("15000"))
            self.assertTrue(suc_dv_ok)

            # Cập nhật đơn giá dịch vụ
            suc_price, msg_price = update_service_price(ma_dv_test, Decimal("20000"))
            self.assertTrue(suc_price)

            # 3. Thêm lượt dùng dịch vụ cho SV002
            suc_sd, msg_sd = add_service_usage(
                ma_sv="SV002",
                ma_dv="DV01",
                thoi_gian_su_dung=now_dt,
                so_luong=2,
                don_gia_ap_dung=Decimal("25000.00"),
            )
            self.assertTrue(suc_sd)

            # Kiểm tra lịch sử đã có bản ghi vừa tạo
            df_history = get_service_usage_history(ma_sv="SV002")
            self.assertFalse(df_history.empty)

            # 4. Thêm khách mới và ghi nhận lượt thăm
            dt_visit = datetime.datetime(2026, 10, 25, 10, 0, 0)
            suc_visit, msg_visit = record_guest_visit(
                so_cmt=cmt_test,
                ten_khach="Nguyen Van Khach Test",
                ngay_sinh=datetime.date(2000, 1, 1),
                ma_sv="SV002",
                ngay_den=dt_visit,
            )
            self.assertTrue(suc_visit)

            # Kiểm tra gọi lại cùng lượt thăm sẽ bị chặn do trùng Unique uq_khach_sv_ngay_den
            suc_dup, msg_dup = record_guest_visit(
                so_cmt=cmt_test,
                ten_khach="Nguyen Van Khach Test",
                ngay_sinh=datetime.date(2000, 1, 1),
                ma_sv="SV002",
                ngay_den=dt_visit,
            )
            self.assertFalse(suc_dup)

            # Kiểm tra sổ trực có bản ghi vừa tạo
            df_guest_logs = get_guest_visit_logs(ma_sv="SV002")
            self.assertTrue(any(df_guest_logs["so_cmt"] == cmt_test))
        finally:
            # Dọn dẹp dữ liệu an toàn
            db.execute_query("DELETE FROM luot_den_choi WHERE so_cmt_khach = %s;", (cmt_test,))
            db.execute_query("DELETE FROM khach WHERE so_cmt = %s;", (cmt_test,))
            db.execute_query("DELETE FROM su_dung_dich_vu WHERE ma_sv = 'SV002' AND thoi_gian_su_dung = %s;", (now_dt,))
            db.execute_query("DELETE FROM dich_vu WHERE ma_dv = %s;", (ma_dv_test,))

    def test_render_service_guest_management_callable(self):
        """Kiểm tra hàm render_service_guest_management tồn tại và có thể gọi được."""
        from modules.service_guest_management import render_service_guest_management

        self.assertTrue(callable(render_service_guest_management))

    def test_render_service_guest_management_ui(self):
        """Kiểm tra render giao diện Phân khu 6 không ném ngoại lệ."""
        from streamlit.testing.v1 import AppTest
        from pathlib import Path

        app_path = Path(__file__).parent / "app.py"
        at = AppTest.from_file(str(app_path), default_timeout=15)
        at.run()
        # Chọn phân khu Ghi nhận Dịch vụ & Khách thăm
        radio_menu = at.sidebar.radio[0]
        radio_menu.set_value("Ghi nhận Dịch vụ & Khách thăm (Bổ trợ 9)")
        at.run()
        self.assertFalse(at.exception, f"Lỗi render Phân khu 6: {[e.value for e in at.exception]}")
        # Kiểm tra tồn tại 2 tabs
        self.assertTrue(len(at.tabs) >= 2, "Phân khu 6 không hiển thị đủ 2 tabs nghiệp vụ.")


if __name__ == "__main__":
    unittest.main()
