# Van Ban Tool — hướng dẫn đóng gói .exe qua GitHub (miễn phí, không cần thẻ)

Vì môi trường làm việc của Claude là máy Linux, không thể tự tay tạo file `.exe`
của Windows. Cách thay thế: đẩy mã nguồn lên GitHub, để **GitHub Actions** (máy
ảo Windows miễn phí của GitHub) tự động build `.exe` mỗi khi bạn phát hành bản
mới. Toàn bộ các bước dưới đây làm trên trình duyệt + Git, không cần máy Windows
riêng (trừ **bước 6 — gói HanLP**, bắt buộc phải có 1 máy Windows thật để chạy
1 lần).

## Cần 2 repo GitHub (đều free, đều public)

| Repo | Chứa gì | Bạn sửa nó khi nào |
|---|---|---|
| `vanban-tool` | Mã nguồn + máy build ra `.exe` | Khi sửa code |
| `vanban-tool-data` | 4 file danh sách loại trừ/họ/ký tự cắt | **Thường xuyên** — đây chính là chỗ bạn cập nhật danh sách loại trừ mà không cần build lại app |

Tách 2 repo để bạn sửa danh sách loại trừ (việc làm hàng ngày) mà không phải
đụng tới code hay chờ build `.exe` lại.

---

## Bước 1 — Tạo tài khoản & 2 repo trên GitHub

1. Vào [github.com](https://github.com) tạo tài khoản (free, không cần thẻ).
2. Bấm **New repository**, đặt tên ví dụ `vanban-tool` → chọn **Public** → **Create repository**. *(Phải Public thì người dùng mới tải file được mà không cần đăng nhập.)*
3. Tạo thêm repo thứ 2, tên `vanban-tool-data` → cũng **Public**.

Ghi lại đúng dạng `tên-tài-khoản/tên-repo`, ví dụ `nguyenvana/vanban-tool` và
`nguyenvana/vanban-tool-data` — sẽ cần điền vào file ở Bước 2.

## Bước 2 — Sửa 2 dòng cấu hình trong `van_ban_tool.py`

Mở file `van_ban_tool.py`, tìm đoạn gần đầu file:

```python
APP_VERSION = "1.0.0"
GITHUB_REPO = "TEN-BAN/vanban-tool"          # repo chứa mã nguồn + bản .exe (GitHub Releases)
DATA_REPO   = "TEN-BAN/vanban-tool-data"     # repo riêng, CHỈ chứa danh sách loại trừ
```

Sửa `GITHUB_REPO` và `DATA_REPO` thành đúng tên 2 repo bạn vừa tạo ở Bước 1.
**Bắt buộc phải sửa trước khi upload**, nếu không app sẽ tự đồng bộ/tự kiểm
tra cập nhật nhắm vào repo mẫu không tồn tại.

## Bước 3 — Upload file lên repo `vanban-tool` (đúng thứ tự)

Cách dễ nhất nếu chưa quen Git: vào repo trên GitHub → **Add file → Upload
files** → kéo-thả. Thứ tự dưới đây không bắt buộc về mặt kỹ thuật (Git không
quan tâm thứ tự), nhưng làm theo cho dễ kiểm tra từng bước:

1. `van_ban_tool.py` *(đã sửa 2 dòng ở Bước 2)*
2. `requirements.txt`
3. `van_ban_tool.spec`
4. `version_info.txt`
5. `app.ico`
6. `installer.iss`
7. `.gitignore`
8. Thư mục `.github/workflows/build.yml` — **giữ nguyên đường dẫn** `.github/workflows/` khi upload, đây là nơi GitHub tìm để chạy Actions.
9. `build_hanlp_pack.bat` *(không upload cũng được, chỉ để bạn tự chạy trên máy — xem Bước 6)*

*Không upload* `vanban-tool-data-example/` vào repo này — thư mục đó dành cho
repo thứ 2 (Bước 5).

Mỗi lần Upload files, viết một dòng "Commit message" ngắn rồi bấm **Commit
changes**.

## Bước 4 — Phát hành bản đầu tiên (để GitHub tự build .exe)

GitHub Actions chỉ chạy build khi bạn tạo một **tag** dạng `v1.0.0`. Cách tạo
tag ngay trên web, không cần cài Git:

1. Vào repo → cột phải → **Releases** → **Create a new release**.
2. Ở "Choose a tag": gõ `v1.0.0` → **Create new tag: v1.0.0 on publish**.
3. Đặt tiêu đề tuỳ ý, ví dụ "Bản 1.0.0".
4. Bấm **Publish release**.

Việc publish release cũng chính là hành động "đẩy tag" mà workflow đang chờ.
Vào tab **Actions** ở đầu repo, sẽ thấy job **Build Windows EXE** đang chạy
(khoảng 3-6 phút). Chạy xong, quay lại **Releases**, bản `v1.0.0` sẽ tự có
thêm 2 file đính kèm:

- **`VanBanTool_Setup.exe`** — bộ cài, đưa link này cho người dùng (khuyên dùng).
- **`van_ban_tool_portable.zip`** — giải nén ra là chạy luôn, không cần cài.

Nếu tab Actions báo lỗi (dấu ✗ đỏ), bấm vào để xem chi tiết dòng nào lỗi —
thường là do 1 trong các file ở Bước 3 thiếu hoặc đặt sai thư mục.

## Bước 5 — Tạo repo dữ liệu `vanban-tool-data`

Upload 5 file trong thư mục `vanban-tool-data-example/` (đã kèm theo) lên
**thẳng gốc** (root) của repo `vanban-tool-data`, giữ nguyên tên file:

```
version.json
blacklist.txt
surname.txt
trim_lead.txt
trim_trail.txt
```

4 file `.txt` mẫu chỉ có vài dòng ví dụ — bạn tự viết đè nội dung thật của
mình vào. Format: mỗi dòng 1 từ, dòng bắt đầu bằng `#` là ghi chú (bị bỏ qua).

### Cách cập nhật danh sách sau này (việc bạn sẽ làm THƯỜNG XUYÊN)

1. Vào repo `vanban-tool-data` trên GitHub, bấm vào file cần sửa (vd.
   `blacklist.txt`) → biểu tượng cây bút (Edit) → sửa → **Commit changes**.
2. Mở `version.json`, tăng số `"version"` lên 1 đơn vị (vd. 1 → 2) → **Commit changes**.
   *(Bắt buộc — app chỉ tải lại khi số version tăng, để khỏi tải lại vô ích mỗi lần mở app.)*

App của mọi người dùng sẽ tự nhận danh sách mới trong lần mở app kế tiếp
(chạy ngầm lúc khởi động), hoặc người dùng có thể bấm nút **"🔄 Đồng bộ từ máy
chủ"** ngay trong cửa sổ **Quản lý danh sách** để nhận ngay không cần khởi
động lại. Danh sách người dùng tự thêm riêng trong app **không bị mất** khi
đồng bộ — 2 phần được gộp lại với nhau.

## Bước 6 — Gói HanLP (để người dùng khỏi cài Python)

Việc này chỉ làm **một lần**, và **bắt buộc cần một máy Windows thật có mạng**
(không làm được trên máy Linux của Claude, cũng không làm được qua GitHub
Actions vì file kết quả quá nặng, mất quá nhiều phút để build mỗi lần).

1. Copy file `build_hanlp_pack.bat` sang máy Windows đó.
2. Chuột phải → **Run as administrator** không bắt buộc, chạy thường cũng
   được. Đợi khoảng 10-20 phút (tải torch + hanlp + model, khá nặng, khoảng
   1-2 GB).
3. Xong sẽ có file `hanlp_pack.zip` cạnh file `.bat`.
4. Vào repo `vanban-tool` (repo code, KHÔNG PHẢI repo data) trên GitHub →
   **Releases** → **Create a new release**.
5. Tag: gõ đúng `hanlp-pack-v1` (đúng chữ này, vì code đang trỏ cứng tới tag
   này) → **Create new tag**.
6. Kéo-thả `hanlp_pack.zip` vào ô "Attach binaries" → **Publish release**.

Từ giờ, ai mở app mà máy chưa có HanLP sẽ thấy nút **"⬇ Tải gói HanLP"** ngay
trong app, bấm vào là tải đúng file này về, không cần biết gì về Python.

Muốn thay bằng bản HanLP mới hơn: chạy lại `.bat`, vào release `hanlp-pack-v1`
cũ, xoá file `hanlp_pack.zip` cũ, đính file mới vào — **giữ nguyên tag**
`hanlp-pack-v1` để đường link không đổi.

## Bước 7 — Phát hành bản cập nhật sau này (sửa code)

Mỗi khi sửa `van_ban_tool.py` (hoặc bất kỳ file build nào):

1. Upload file đã sửa đè lên file cũ trong repo `vanban-tool` (kéo-thả file
   mới, GitHub tự hỏi có ghi đè không).
2. Vào **Releases → Create a new release**, đặt tag mới **tăng số**, ví dụ
   `v1.0.1`.
3. Publish → đợi Actions build xong → có bản `.exe` mới.

Bạn **không cần tự sửa** dòng `APP_VERSION` trong code hay số phiên bản trong
`installer.iss` mỗi lần — workflow tự lấy đúng số từ cái tag bạn gõ (`v1.0.1`
→ tự thành `1.0.1` ở mọi chỗ) và ghi đè vào lúc build.

Người dùng đang mở app cũ sẽ thấy hộp thoại "Có bản cập nhật" (app tự kiểm
tra khi mở), bấm vào sẽ mở đúng trang Releases để tải bản mới.

---

## Dữ liệu người dùng được lưu ở đâu

`%APPDATA%\VanBanTool` (gõ `%APPDATA%` vào ô địa chỉ File Explorer để mở
nhanh) — gồm cấu hình, từ điển, danh sách loại trừ, gói HanLP đã tải. Thư mục
này **không bị xoá** khi gỡ cài đặt hay cài đè bản mới, để không mất dữ liệu.

## Vì sao chọn cách cài này (không cần quyền Admin)

Bộ cài `installer.iss` cài vào `%LocalAppData%\Programs\VanBanTool` (giống
cách VS Code cài) thay vì `C:\Program Files`, nên **không hiện hộp thoại UAC**,
dùng được trên máy công ty / máy dùng chung không có quyền Admin.

## Xử lý khi Windows/diệt-virus báo nhầm là virus

File `.exe` build bằng PyInstaller (không ký chứng chỉ số, vì chứng chỉ mất
phí) hay bị Windows SmartScreen hoặc một số phần mềm diệt virus báo nhầm lúc
mở lần đầu — đây là lỗi nhận diện sai (false positive) rất phổ biến với mọi
app PyInstaller/Python, không riêng app này. Cách xử lý:

- Windows SmartScreen: bấm **"More info" → "Run anyway"**.
- Diệt virus báo nhầm: thêm ngoại lệ (Exception/Allow) cho file, hoặc gửi file
  lên [VirusTotal](https://www.virustotal.com) rồi báo "false positive" cho
  hãng diệt virus đó.
- Cách giảm hẳn tình trạng này: mua chứng chỉ ký code (Code Signing
  Certificate, có phí, khoảng vài triệu/năm) — không bắt buộc để dùng thử.

## Sự khác biệt so với kế hoạch "web (blitz.cloud)" đã bàn trước đó

Bản `.exe` này chạy HanLP **ngay trên máy người dùng** (qua gói đã đóng gói),
không cần server của bạn gánh việc nặng đó — đây là lý do chọn hướng `.exe`
thay vì web như đã trao đổi ở phần trước.
