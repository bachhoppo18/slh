# SLH Tool

Công cụ làm truyện chữ: lọc tên nhân vật tiếng Trung, dịch tên (Hán Việt),
dịch Trung → Việt, và đóng gói thành file EPUB hoàn chỉnh — không cần dùng
Word hay các công cụ trung gian khác.

## Tải về

Vào **[Releases](https://github.com/bachhoppo18/slh/releases/latest)**, tải 1 trong 2 file:

- **`SLHTool_Setup.exe`** *(khuyên dùng)* — bộ cài, có Start Menu, gỡ cài đặt được; có thể tự cài bản mới khi xác nhận cập nhật trong app.
- **`slhtool_portable.zip`** — giải nén ra là chạy luôn `slhtool.exe`, không cần cài, hợp máy không cho cài phần mềm.

Không cần tài khoản Windows quyền Admin — cài vào thư mục riêng của người
dùng, không đụng tới Program Files.

> **Lần đầu mở app, Windows có thể hiện cảnh báo màu xanh "Windows protected
> your PC"** — đây là cảnh báo bình thường với app chưa mua chứng chỉ ký số
> (không phải virus). Bấm **"More info" → "Run anyway"** để mở.

## Cài đặt

1. Mở `SLHTool_Setup.exe` → **Next** → **Install**.
2. Xong, mở app từ Start Menu hoặc icon ngoài Desktop (nếu có tick chọn lúc cài).

## Giao diện gồm 3 tab chính

### 1. 👤 Lọc tên nhân vật

1. Dán văn bản tiếng Trung vào ô bên trái (nút **📋 Dán văn bản** hoặc **📂 Mở file .txt**).
2. Bấm **🎯 Lọc bằng HanLP** — app quét toàn bộ văn bản, liệt kê tên nhân vật
   tìm được kèm số lần xuất hiện và phân loại (nhân vật chính/phụ).
   - *Máy chưa từng dùng HanLP*: một hộp thoại hiện ra, bấm **⬇ Tải gói HanLP**
     (tải 1 lần, không cần tự cài Python). Xong thì bấm lại **🎯 Lọc bằng HanLP**.
3. Có kết quả rồi, bấm **🌐 Dịch name** — mở cửa sổ **tự động dịch** toàn bộ tên
   vừa lọc sang Hán Việt (viết hoa sẵn 3-4 chữ đầu tuỳ độ dài tên).
   - Muốn dịch riêng vài tên: chọn (bôi đen) các dòng đó trong bảng kết quả
     trước khi bấm **🌐 Dịch name**.
4. Trong cửa sổ Dịch name: xem lại, sửa tên nếu cần (bấm đúp vào dòng), chọn
   **bộ tên đích** (hoặc bấm **＋ Bộ mới…** để tạo bộ mới), rồi bấm
   **✔ Thêm N name vào bộ tên**. Tên đã có trong bộ được đánh dấu rõ (trùng /
   khác nghĩa) để bạn quyết định giữ nghĩa cũ hay ghi đè.
5. **🗂 Quản lý danh sách**: quản lý 4 danh sách dùng khi lọc — *Loại trừ*,
   *Họ*, *Ký tự cắt đầu*, *Ký tự cắt cuối*. Bấm **🔄 Đồng bộ từ máy chủ** để
   nhận bản danh sách mới nhất (không mất phần bạn tự thêm).

  Danh sách riêng trên máy được lưu trong `%APPDATA%\SLHTool`; danh sách máy chủ
  được tải từ thư mục `slh-data/` trong repository. Mỗi mục máy chủ nằm trên một
  dòng trong file tương ứng; tăng `version` trong `slh-data/version.json` sau khi
  cập nhật để app tải bản mới. Danh sách máy chủ được thay thế theo version, còn
  danh sách riêng trên máy không bị ghi đè.

### 2. 📚 Tạo & Gộp EPUB

- **📄 Tạo EPUB (.docx / .txt)**: thêm file `.docx` hoặc `.txt` đã dịch xong,
  điền tên truyện/tác giả/văn án/ảnh bìa, bấm **Xuất EPUB**.
  - Với file `.txt`: app tự nhận diện chương ("Chương 1", "Hồi 2"...), mở cửa
    sổ **xem trước & sửa chương** trước khi xuất — sửa tên chương, tách/gộp
    chương sai, rồi bấm **✔ Xác nhận và Tạo EPUB**.
- **🔗 Gộp EPUB**: ghép nhiều file EPUB (nhiều phần của cùng 1 truyện) thành 1
  file duy nhất, giữ đúng thứ tự chương.

### 3. 🌐 Dịch Trung → Việt

- **Dịch QT**: dán văn bản tiếng Trung, dịch Việt (offline, dùng từ điển có
  sẵn) hoặc qua máy chủ, có thể dịch riêng phần tên theo bộ tên đang chọn.
- **Quản lý Name**: xem/sửa/xoá từng name trong bộ tên đang dùng, chuyển đổi
  giữa các bộ tên (mỗi truyện có thể dùng 1 bộ riêng).
- **Nâng cao**: đổi nguồn tải từ điển Hán Việt/tên riêng nếu cần.

## Cập nhật app

App tự kiểm tra bản mới mỗi khi mở. Với bản cài `SLHTool_Setup.exe`, app có thể
tải bộ cài mới, xác minh file, cài đè im lặng và mở lại app sau khi bạn xác nhận.
Cấu hình và bộ tên trong `%APPDATA%\SLHTool` được giữ nguyên. Bản portable vẫn
cập nhật bằng cách tải gói mới từ trang Releases.

## Tài khoản

Ứng dụng không cần Admin API, URL máy chủ hay tài khoản trực tuyến. Đăng nhập
cục bộ lần đầu bằng tài khoản `admin`, mật khẩu `123456`; chọn **Đổi mật khẩu**
ngay trên cửa sổ đăng nhập để đặt mật khẩu riêng (tối thiểu 8 ký tự).

Thông tin đăng nhập được lưu tại `%APPDATA%\SLHTool\admin_config.json`; ứng dụng
chỉ lưu mã băm mật khẩu, không lưu mật khẩu dạng văn bản. Đây là khóa truy cập
cục bộ tiện dụng, không phải cơ chế bảo mật máy chủ: mật khẩu mặc định có trong
bản ứng dụng, vì vậy hãy đổi mật khẩu trước khi chia sẻ hoặc dùng chung máy.

Các danh sách nền vẫn được đồng bộ trực tiếp từ repository dữ liệu; danh sách
riêng được lưu trên máy và không bị ghi đè.

## Dữ liệu của bạn được lưu ở đâu

`%APPDATA%\SLHTool` (gõ thẳng `%APPDATA%\SLHTool` vào ô địa chỉ File Explorer
để mở nhanh) — gồm cấu hình, bộ tên, danh sách loại trừ, gói HanLP đã tải.
Gỡ cài đặt hoặc cài đè bản mới **không xoá** thư mục này.

## Câu hỏi thường gặp

**Dùng HanLP có cần cài Python không?**
Không. Bấm **⬇ Tải gói HanLP** ngay trong app (mục 3 ở trên) là dùng được,
không cần biết gì về Python.

**Không có mạng thì dùng được gì?**
Lọc tên bằng HanLP, dịch offline, tạo/gộp EPUB đều dùng được khi không có
mạng (sau khi đã tải gói HanLP + từ điển lần đầu). Cần mạng cho: lần đầu tải
gói HanLP/từ điển, dịch qua máy chủ, đồng bộ danh sách loại trừ, kiểm tra
cập nhật.

**Diệt virus báo nhầm file cài đặt là virus?**
Đây là báo nhầm (false positive) thường gặp với app chưa mua chứng chỉ ký số,
không phải app này có vấn đề. Thêm ngoại lệ (Allow/Exception) cho file trong
phần mềm diệt virus, hoặc kiểm tra chéo trên [VirusTotal](https://www.virustotal.com).