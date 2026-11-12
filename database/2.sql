-- Hệ thống Quản lý Ký túc xá Sinh viên (MySQL 8.0+)
-- Quy ước nghiệp vụ:
-- 1. Đơn giá phòng (don_gia_thang) là số tiền mỗi sinh viên phải trả theo tháng.
-- 2. Tiền phòng tính tròn tháng (ở bất kỳ ngày nào trong tháng đều tính đủ 1 tháng).
-- 3. Phí giữ xe vé tháng: 100.000 VNĐ / xe / tháng (mỗi sinh viên tối đa 2 xe cùng thời điểm).
-- 4. Mỗi ngày mỗi xe vé tháng được miễn phí 2 lượt gửi/lấy đầu tiên; từ lượt thứ 3 tính phụ thu 3.000 VNĐ / lượt.
-- 5. Xe vãng lai thu tiền trực tiếp, không lưu vào CSDL.

DROP DATABASE IF EXISTS ql_ky_tuc_xa;
CREATE DATABASE ql_ky_tuc_xa CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ql_ky_tuc_xa;

-- 1. Tạo các bảng cơ sở (DDL)

CREATE TABLE phong (
  so_phong VARCHAR(10) PRIMARY KEY,
  loai_phong VARCHAR(30) NOT NULL,
  don_gia_thang DECIMAL(12,2) NOT NULL CHECK (don_gia_thang >= 0),
  so_nguoi_toi_da INT NOT NULL CHECK (so_nguoi_toi_da > 0)
);

CREATE TABLE sinh_vien (
  ma_sv VARCHAR(15) PRIMARY KEY,
  so_cmt VARCHAR(20) NOT NULL UNIQUE,
  ho_ten VARCHAR(100) NOT NULL,
  ngay_sinh DATE NOT NULL,
  lop VARCHAR(30),
  que_quan VARCHAR(120)
);

CREATE TABLE lich_su_o_phong (
  ma_o BIGINT AUTO_INCREMENT PRIMARY KEY,
  ma_sv VARCHAR(15) NOT NULL,
  so_phong VARCHAR(10) NOT NULL,
  ngay_vao DATE NOT NULL,
  ngay_ra DATE NULL,
  don_gia_ap_dung DECIMAL(12,2) NOT NULL,
  CHECK (ngay_ra IS NULL OR ngay_ra >= ngay_vao),
  CHECK (don_gia_ap_dung >= 0),
  FOREIGN KEY (ma_sv) REFERENCES sinh_vien(ma_sv),
  FOREIGN KEY (so_phong) REFERENCES phong(so_phong),
  INDEX idx_lich_su_phong (so_phong, ngay_vao, ngay_ra),
  INDEX idx_lich_su_sv (ma_sv, ngay_vao, ngay_ra)
);

CREATE TABLE khach (
  so_cmt VARCHAR(20) PRIMARY KEY,
  ten_khach VARCHAR(100) NOT NULL,
  ngay_sinh DATE
);

CREATE TABLE luot_den_choi (
  ma_luot BIGINT AUTO_INCREMENT PRIMARY KEY,
  so_cmt_khach VARCHAR(20) NOT NULL,
  ma_sv VARCHAR(15) NOT NULL,
  ngay_den DATETIME NOT NULL,
  FOREIGN KEY (so_cmt_khach) REFERENCES khach(so_cmt),
  FOREIGN KEY (ma_sv) REFERENCES sinh_vien(ma_sv),
  UNIQUE KEY uq_khach_sv_ngay_den (so_cmt_khach, ma_sv, ngay_den),
  INDEX idx_luot_den (ngay_den)
);

-- Giá trị 'KHAC' đồng bộ với cụ thể hóa một phần trên mô hình EER.
CREATE TABLE dich_vu (
  ma_dv VARCHAR(10) PRIMARY KEY,
  ten_dv VARCHAR(80) NOT NULL,
  loai_dv ENUM('GIAT_LA','TRONG_XE','THUE_XE','AN_UONG','KHAC') NOT NULL,
  don_gia DECIMAL(12,2) NOT NULL CHECK (don_gia >= 0)
);

CREATE TABLE su_dung_dich_vu (
  ma_sd BIGINT AUTO_INCREMENT PRIMARY KEY,
  ma_sv VARCHAR(15) NOT NULL,
  ma_dv VARCHAR(10) NOT NULL,
  thoi_gian_su_dung DATETIME NOT NULL,
  so_luong INT NOT NULL DEFAULT 1 CHECK (so_luong > 0),
  don_gia_ap_dung DECIMAL(12,2) NOT NULL CHECK (don_gia_ap_dung >= 0),
  FOREIGN KEY (ma_sv) REFERENCES sinh_vien(ma_sv),
  FOREIGN KEY (ma_dv) REFERENCES dich_vu(ma_dv),
  INDEX idx_sd_time (thoi_gian_su_dung)
);

CREATE TABLE xe_ve_thang (
  bien_so VARCHAR(20) PRIMARY KEY,
  ma_sv VARCHAR(15) NOT NULL,
  loai_xe VARCHAR(30) NOT NULL,
  ngay_dang_ky DATE NOT NULL,
  ngay_huy DATE NULL,
  CHECK (ngay_huy IS NULL OR ngay_huy >= ngay_dang_ky),
  FOREIGN KEY (ma_sv) REFERENCES sinh_vien(ma_sv),
  INDEX idx_xe_sv (ma_sv, ngay_dang_ky, ngay_huy)
);

-- Khóa thực thể yếu luot_gui_lay_xe phụ thuộc xe_ve_thang.
CREATE TABLE luot_gui_lay_xe (
  ma_luot BIGINT AUTO_INCREMENT PRIMARY KEY,
  bien_so VARCHAR(20) NOT NULL,
  thoi_gian_gui DATETIME NOT NULL,
  thoi_gian_lay DATETIME NOT NULL,
  so_tien_phai_tra DECIMAL(12,2) NOT NULL DEFAULT 0 CHECK (so_tien_phai_tra >= 0),
  CHECK (thoi_gian_lay > thoi_gian_gui),
  FOREIGN KEY (bien_so) REFERENCES xe_ve_thang(bien_so),
  UNIQUE KEY uq_bien_so_tg_gui (bien_so, thoi_gian_gui),
  INDEX idx_luot_xe (bien_so, thoi_gian_gui)
);

-- 2. Trigger kiểm tra ràng buộc toàn vẹn (INSERT và UPDATE)
DELIMITER $$

-- 2.1. Kiểm soát xếp phòng: chống trùng lịch ở và không vượt sức chứa tối đa
CREATE TRIGGER trg_phong_insert BEFORE INSERT ON lich_su_o_phong
FOR EACH ROW
BEGIN
  DECLARE v_suc_chua INT;
  DECLARE v_dang_o INT;

  -- Kiểm tra trùng lịch ở phòng khác trong khoảng thời gian
  IF EXISTS (
    SELECT 1 FROM lich_su_o_phong l
    WHERE l.ma_sv = NEW.ma_sv
      AND l.ngay_vao <= COALESCE(NEW.ngay_ra, '9999-12-31')
      AND NEW.ngay_vao <= COALESCE(l.ngay_ra, '9999-12-31')
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Loi: Sinh vien da co lich su o phong trung khoang thoi gian nay';
  END IF;

  -- Kiểm tra sức chứa tối đa của phòng trong khoảng thời gian giao nhau
  SELECT so_nguoi_toi_da INTO v_suc_chua FROM phong WHERE so_phong = NEW.so_phong;

  SELECT COUNT(*) INTO v_dang_o
  FROM lich_su_o_phong l
  WHERE l.so_phong = NEW.so_phong
    AND l.ngay_vao <= COALESCE(NEW.ngay_ra, '9999-12-31')
    AND NEW.ngay_vao <= COALESCE(l.ngay_ra, '9999-12-31');

  IF v_dang_o >= v_suc_chua THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Loi: Phong da du so nguoi toi da, khong the xep them sinh vien';
  END IF;
END$$

CREATE TRIGGER trg_phong_update BEFORE UPDATE ON lich_su_o_phong
FOR EACH ROW
BEGIN
  DECLARE v_suc_chua INT;
  DECLARE v_dang_o INT;

  IF EXISTS (
    SELECT 1 FROM lich_su_o_phong l
    WHERE l.ma_sv = NEW.ma_sv
      AND l.ma_o <> NEW.ma_o
      AND l.ngay_vao <= COALESCE(NEW.ngay_ra, '9999-12-31')
      AND NEW.ngay_vao <= COALESCE(l.ngay_ra, '9999-12-31')
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Loi cap nhat: Sinh vien bi trung thoi gian o phong';
  END IF;

  SELECT so_nguoi_toi_da INTO v_suc_chua FROM phong WHERE so_phong = NEW.so_phong;

  SELECT COUNT(*) INTO v_dang_o
  FROM lich_su_o_phong l
  WHERE l.so_phong = NEW.so_phong
    AND l.ma_o <> NEW.ma_o
    AND l.ngay_vao <= COALESCE(NEW.ngay_ra, '9999-12-31')
    AND NEW.ngay_vao <= COALESCE(l.ngay_ra, '9999-12-31');

  IF v_dang_o >= v_suc_chua THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Loi cap nhat: Phong da du so nguoi toi da';
  END IF;
END$$

-- 2.2. Giới hạn tối đa 2 xe vé tháng hoạt động cùng thời điểm cho mỗi sinh viên
CREATE TRIGGER trg_xe_insert BEFORE INSERT ON xe_ve_thang
FOR EACH ROW
BEGIN
  DECLARE v_so_xe INT;

  SELECT COUNT(*) INTO v_so_xe
  FROM xe_ve_thang x
  WHERE x.ma_sv = NEW.ma_sv
    AND x.ngay_dang_ky <= COALESCE(NEW.ngay_huy, '9999-12-31')
    AND NEW.ngay_dang_ky <= COALESCE(x.ngay_huy, '9999-12-31');

  IF v_so_xe >= 2 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Loi: Moi sinh vien chi duoc dang ky toi da 2 xe ve thang cung thoi diem';
  END IF;
END$$

CREATE TRIGGER trg_xe_update BEFORE UPDATE ON xe_ve_thang
FOR EACH ROW
BEGIN
  DECLARE v_so_xe INT;

  SELECT COUNT(*) INTO v_so_xe
  FROM xe_ve_thang x
  WHERE x.ma_sv = NEW.ma_sv
    AND x.bien_so <> OLD.bien_so
    AND x.ngay_dang_ky <= COALESCE(NEW.ngay_huy, '9999-12-31')
    AND NEW.ngay_dang_ky <= COALESCE(x.ngay_huy, '9999-12-31');

  IF v_so_xe >= 2 THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Loi cap nhat: Sinh vien vuot qua gioi han 2 xe ve thang cung thoi diem';
  END IF;
END$$

-- 2.3. Kiểm tra hiệu lực vé tháng và tự động tính phí gửi/lấy xe
-- Miễn phí 2 lượt đầu trong ngày; từ lượt thứ 3 tính phụ thu 3.000 VNĐ/lượt.
CREATE TRIGGER trg_luot_xe_insert BEFORE INSERT ON luot_gui_lay_xe
FOR EACH ROW
BEGIN
  DECLARE v_so_luot_truoc INT;
  DECLARE v_bat_dau_ngay DATETIME;
  DECLARE v_ket_thuc_ngay DATETIME;

  -- Kiểm tra xe có vé tháng còn hiệu lực tại ngày gửi
  IF NOT EXISTS (
    SELECT 1 FROM xe_ve_thang x
    WHERE x.bien_so = NEW.bien_so
      AND DATE(NEW.thoi_gian_gui) >= x.ngay_dang_ky
      AND (x.ngay_huy IS NULL OR DATE(NEW.thoi_gian_gui) <= x.ngay_huy)
  ) THEN
    SIGNAL SQLSTATE '45000'
      SET MESSAGE_TEXT = 'Loi: Xe chua dang ky hoac ve thang khong con hieu luc tai ngay gui';
  END IF;

  -- Truy vấn DATETIME trong ngày để tận dụng index
  SET v_bat_dau_ngay = TIMESTAMP(DATE(NEW.thoi_gian_gui));
  SET v_ket_thuc_ngay = DATE_ADD(v_bat_dau_ngay, INTERVAL 1 DAY);

  SELECT COUNT(*) INTO v_so_luot_truoc
  FROM luot_gui_lay_xe
  WHERE bien_so = NEW.bien_so
    AND thoi_gian_gui >= v_bat_dau_ngay
    AND thoi_gian_gui < v_ket_thuc_ngay;

  SET NEW.so_tien_phai_tra = IF(v_so_luot_truoc < 2, 0, 3000);
END$$

DELIMITER ;

-- 3. Dữ liệu mẫu kiểm thử toàn diện (Tháng 09 và 10/2026)

-- 3.1. Danh mục phòng (A102 sức chứa 2 người sẽ được lấp đầy để kiểm thử trigger)
INSERT INTO phong (so_phong, loai_phong, don_gia_thang, so_nguoi_toi_da) VALUES
('A101', 'Phong 4 nguoi tieu chuan', 400000, 4),
('A102', 'Phong 2 nguoi dich vu',    650000, 2),
('B201', 'Phong 6 nguoi pho thong',  300000, 6);

-- 3.2. Danh sách sinh viên (SV001 -> SV005 đang ở KTX, SV006 chờ xếp phòng để thử lỗi phòng đầy)
INSERT INTO sinh_vien (ma_sv, so_cmt, ho_ten, ngay_sinh, lop, que_quan) VALUES
('SV001', '001205000001', 'Nguyen Van An',  '2005-02-12', 'CNTT1', 'Ha Noi'),
('SV002', '001205000002', 'Tran Thi Binh',  '2005-08-03', 'CNTT2', 'Hai Phong'),
('SV003', '001204000003', 'Le Minh Cuong',  '2004-11-20', 'KTPM1', 'Nam Dinh'),
('SV004', '001205000004', 'Pham Thu Dung',  '2005-06-09', 'QTKD1', 'Thanh Hoa'),
('SV005', '001205000005', 'Hoang Van Em',   '2005-12-01', 'ATBM1', 'Nghe An'),
('SV006', '001205000006', 'Vu Thi Phuong',  '2005-03-15', 'CNTT1', 'Ha Nam');

-- 3.3. Lịch sử ở phòng (A101: 2/4 người; A102: 2/2 người đã đầy; B201: 1/6 người)
INSERT INTO lich_su_o_phong (ma_sv, so_phong, ngay_vao, ngay_ra, don_gia_ap_dung) VALUES
('SV001', 'A101', '2026-09-10', NULL, 400000),
('SV002', 'A101', '2026-10-19', NULL, 400000),
('SV003', 'A102', '2026-10-01', NULL, 650000),
('SV004', 'B201', '2026-09-01', NULL, 300000),
('SV005', 'A102', '2026-10-05', NULL, 650000);

-- 3.4. Thông tin khách và lượt đến thăm
INSERT INTO khach (so_cmt, ten_khach, ngay_sinh) VALUES
('012345600001', 'Hoang Lan',   '2005-04-10'),
('012345600002', 'Do Viet',     '2003-01-13'),
('012345600003', 'Nguyen Tuan', '2004-07-22');

INSERT INTO luot_den_choi (so_cmt_khach, ma_sv, ngay_den) VALUES
('012345600001', 'SV001', '2026-10-03 09:00:00'),
('012345600001', 'SV001', '2026-10-10 10:30:00'),
('012345600002', 'SV001', '2026-10-11 14:00:00'),
('012345600001', 'SV002', '2026-10-15 08:00:00'),
('012345600003', 'SV003', '2026-10-22 16:15:00');

-- 3.5. Danh mục dịch vụ và lịch sử sử dụng
INSERT INTO dich_vu (ma_dv, ten_dv, loai_dv, don_gia) VALUES
('DV01', 'Giat la say kho',            'GIAT_LA',  25000),
('DV02', 'Trong giữ xe',               'TRONG_XE',  3000),
('DV03', 'Cho thue xe dap/xe dien',    'THUE_XE',  50000),
('DV04', 'Suat an cang tin KTX',       'AN_UONG',  35000);

INSERT INTO su_dung_dich_vu (ma_sv, ma_dv, thoi_gian_su_dung, so_luong, don_gia_ap_dung) VALUES
('SV001', 'DV01', '2026-09-15 10:00:00', 1, 25000), -- Du lieu thang 9 (kiem tra bo loc thang)
('SV001', 'DV01', '2026-10-02 10:00:00', 2, 25000),
('SV001', 'DV04', '2026-10-03 12:00:00', 1, 35000),
('SV001', 'DV04', '2026-10-18 12:00:00', 2, 35000),
('SV002', 'DV01', '2026-10-20 17:00:00', 1, 25000),
('SV003', 'DV03', '2026-10-15 08:00:00', 2, 50000),
('SV004', 'DV04', '2026-10-12 18:00:00', 3, 35000);

-- 3.6. Đăng ký xe vé tháng (SV001 đủ 2 xe, SV002 có 1 xe)
INSERT INTO xe_ve_thang (bien_so, ma_sv, loai_xe, ngay_dang_ky, ngay_huy) VALUES
('29A-12345', 'SV001', 'Xe may Honda Wave', '2026-09-01', NULL),
('29A-23456', 'SV001', 'Xe dap dien',       '2026-10-01', NULL),
('15B-55555', 'SV002', 'Xe may Vision',     '2026-10-19', NULL);

-- 3.7. Lượt gửi/lấy xe (tự động tính tiền qua trigger)
-- Ngày 12/10/2026: xe 29A-12345 gửi 4 lượt (lượt 1-2: 0đ; lượt 3-4: 3.000đ/lượt, tổng 6.000đ)
-- Ngày 13/10/2026: xe 29A-12345 gửi 1 lượt (reset về lượt 1 trong ngày: 0đ)
-- Ngày 20/10/2026: xe 15B-55555 gửi 3 lượt (lượt 1-2: 0đ; lượt 3: 3.000đ)
INSERT INTO luot_gui_lay_xe (bien_so, thoi_gian_gui, thoi_gian_lay) VALUES
('29A-12345', '2026-10-12 08:00:00', '2026-10-12 10:00:00'),
('29A-12345', '2026-10-12 11:00:00', '2026-10-12 12:00:00'),
('29A-12345', '2026-10-12 15:00:00', '2026-10-12 16:00:00'),
('29A-12345', '2026-10-12 18:00:00', '2026-10-12 19:00:00'),
('29A-12345', '2026-10-13 07:00:00', '2026-10-13 08:00:00'),
('15B-55555', '2026-10-20 07:30:00', '2026-10-20 11:30:00'),
('15B-55555', '2026-10-20 13:30:00', '2026-10-20 17:00:00'),
('15B-55555', '2026-10-20 19:00:00', '2026-10-20 21:00:00');

-- 4. Bốn truy vấn báo cáo nghiệp vụ bắt buộc theo đề bài

-- Thiết lập tham số kỳ báo cáo: Tháng 10/2026
SET @nam = 2026;
SET @thang = 10;
SET @dau_thang = STR_TO_DATE(CONCAT(@nam, '-', LPAD(@thang, 2, '0'), '-01'), '%Y-%m-%d');
SET @dau_thang_sau = DATE_ADD(@dau_thang, INTERVAL 1 MONTH);

-- Truy vấn 1: Liệt kê sinh viên và tổng chi phí phải trả trong tháng.
-- Dùng CTE gom nhóm độc lập từng khoản thu (phòng, dịch vụ, vé tháng, phụ thu xe), tránh nhân đôi bản ghi.
WITH
p AS (
  SELECT ma_sv, SUM(don_gia_ap_dung) AS tien_phong
  FROM lich_su_o_phong
  WHERE ngay_vao < @dau_thang_sau
    AND (ngay_ra IS NULL OR ngay_ra >= @dau_thang)
  GROUP BY ma_sv
),
d AS (
  SELECT ma_sv, SUM(so_luong * don_gia_ap_dung) AS tien_dich_vu
  FROM su_dung_dich_vu
  WHERE thoi_gian_su_dung >= @dau_thang
    AND thoi_gian_su_dung < @dau_thang_sau
  GROUP BY ma_sv
),
x AS (
  SELECT ma_sv, COUNT(*) * 100000 AS tien_ve_thang
  FROM xe_ve_thang
  WHERE ngay_dang_ky < @dau_thang_sau
    AND (ngay_huy IS NULL OR ngay_huy >= @dau_thang)
  GROUP BY ma_sv
),
xe_phat_sinh AS (
  SELECT x.ma_sv, SUM(l.so_tien_phai_tra) AS tien_phu_thu_xe
  FROM luot_gui_lay_xe l
  JOIN xe_ve_thang x ON l.bien_so = x.bien_so
  WHERE l.thoi_gian_gui >= @dau_thang
    AND l.thoi_gian_gui < @dau_thang_sau
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
JOIN p ON s.ma_sv = p.ma_sv -- Chi liet ke sinh vien dang luu tru trong KTX vao thang do
LEFT JOIN d ON s.ma_sv = d.ma_sv
LEFT JOIN x ON s.ma_sv = x.ma_sv
LEFT JOIN xe_phat_sinh xp ON s.ma_sv = xp.ma_sv
ORDER BY s.ma_sv;

-- Truy vấn 2: Thống kê chi tiết dịch vụ mỗi sinh viên sử dụng trong khoảng thời gian.
SET @tu_ngay = '2026-10-01';
SET @den_ngay = '2026-10-31';

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
WHERE sd.thoi_gian_su_dung >= @tu_ngay
  AND sd.thoi_gian_su_dung < DATE_ADD(@den_ngay, INTERVAL 1 DAY)
GROUP BY s.ma_sv, s.ho_ten, d.ma_dv, d.ten_dv
ORDER BY s.ma_sv, d.ma_dv;

-- Truy vấn 3: Thống kê khách đến thăm từng sinh viên và số lần đến thăm trong kỳ.
SET @tu_tham = '2026-10-01';
SET @den_tham = '2026-10-31';

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
WHERE l.ngay_den >= @tu_tham
  AND l.ngay_den < DATE_ADD(@den_tham, INTERVAL 1 DAY)
GROUP BY s.ma_sv, s.ho_ten, k.so_cmt, k.ten_khach, k.ngay_sinh
ORDER BY s.ma_sv, so_lan_den DESC;

-- Truy vấn 4: Doanh thu theo từng danh mục dịch vụ trong tháng (gồm vé tháng và phụ thu lượt xe).
WITH
dt_ve_xe AS (
  SELECT COUNT(*) * 100000 AS tien_ve
  FROM xe_ve_thang
  WHERE ngay_dang_ky < @dau_thang_sau
    AND (ngay_huy IS NULL OR ngay_huy >= @dau_thang)
),
dt_phu_thu_xe AS (
  SELECT COALESCE(SUM(so_tien_phai_tra), 0) AS tien_phu_thu
  FROM luot_gui_lay_xe
  WHERE thoi_gian_gui >= @dau_thang
    AND thoi_gian_gui < @dau_thang_sau
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
  AND sd.thoi_gian_su_dung >= @dau_thang
  AND sd.thoi_gian_su_dung < @dau_thang_sau
GROUP BY d.ma_dv, d.ten_dv, d.loai_dv
ORDER BY d.ma_dv;

-- 5. Kịch bản kiểm thử trigger và các trường hợp chặn lỗi

-- 5.1. Kiểm tra kết quả tự động tính phí gửi/lấy xe (kỳ vọng: 0, 0, 3000, 3000, 0, 0, 0, 3000)
SELECT ma_luot, bien_so, thoi_gian_gui, thoi_gian_lay, so_tien_phai_tra
FROM luot_gui_lay_xe
ORDER BY ma_luot;

-- 5.2. Kịch bản kiểm thử trigger chặn vi phạm (bỏ comment từng câu lệnh để chạy kiểm thử):

-- [Test 1]: Xếp SV006 vào phòng A102 đã đầy (2/2 người)
-- Kỳ vọng: Lỗi phòng đã đủ số người tối đa
-- INSERT INTO lich_su_o_phong (ma_sv, so_phong, ngay_vao, ngay_ra, don_gia_ap_dung)
-- VALUES ('SV006', 'A102', '2026-10-25', NULL, 650000);

-- [Test 2]: Xếp SV002 sang phòng B201 trùng khoảng thời gian đang ở A101
-- Kỳ vọng: Lỗi sinh viên đã có lịch sử ở phòng trùng khoảng thời gian
-- INSERT INTO lich_su_o_phong (ma_sv, so_phong, ngay_vao, ngay_ra, don_gia_ap_dung)
-- VALUES ('SV002', 'B201', '2026-10-20', NULL, 300000);

-- [Test 3]: SV001 đăng ký xe vé tháng thứ 3 (đã có 2 xe)
-- Kỳ vọng: Lỗi vượt quá giới hạn 2 xe vé tháng cùng thời điểm
-- INSERT INTO xe_ve_thang (bien_so, ma_sv, loai_xe, ngay_dang_ky, ngay_huy)
-- VALUES ('29A-33333', 'SV001', 'Xe may AirBlade', '2026-10-15', NULL);

-- [Test 4]: Ghi nhận gửi xe trước ngày đăng ký vé tháng
-- Kỳ vọng: Lỗi xe chưa đăng ký hoặc vé tháng không còn hiệu lực
-- INSERT INTO luot_gui_lay_xe (bien_so, thoi_gian_gui, thoi_gian_lay)
-- VALUES ('15B-55555', '2026-10-01 08:00:00', '2026-10-01 10:00:00');