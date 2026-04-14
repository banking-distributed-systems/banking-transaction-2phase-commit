# Giải thích các test case trong menu test_toxiproxy.py

## 1. Health Check

Kiểm tra API backend có đang chạy bình thường không (trả về status "ok").

## 2. Get Accounts

Gọi API lấy danh sách tài khoản, kiểm tra backend trả về dữ liệu tài khoản đúng.

## 3. Login

Test chức năng đăng nhập với tài khoản/mật khẩu mẫu, kiểm tra xác thực hoạt động.

## 4. Transfer (bình thường)

Test chuyển tiền giữa 2 tài khoản khi không có lỗi mạng, kiểm tra giao dịch thành công.

## 5. Transfer với Toxics hiện tại

Test chuyển tiền khi đang bật các “toxic” (giả lập lỗi mạng như delay, timeout...), kiểm tra hệ thống xử lý lỗi mạng.

---

## A. Tạo Proxy

Tạo mới một proxy trên Toxiproxy để chuyển hướng traffic qua proxy này.

## B. Xóa Proxy

Xóa proxy đã tạo.

## C. Thêm Latency (nhập ms)

Thêm độ trễ (delay) vào proxy để mô phỏng mạng chậm.

## D. Thêm Timeout (nhập ms)

Thêm timeout vào proxy để mô phỏng backend phản hồi chậm hoặc không phản hồi.

## L. Thêm Limit Data (Packet Loss)

Giới hạn dung lượng dữ liệu truyền, mô phỏng mất gói tin.

## K. Thêm Close Stream (Server chết)

Mô phỏng server backend bị chết, đóng kết nối đột ngột.

## M. Thêm Bandwidth (Slow network)

Giới hạn băng thông, mô phỏng mạng chậm.

## P. Thêm Slicer (Random packet loss)

Mô phỏng mất gói tin ngẫu nhiên.

## F. Thêm CẢ Latency + Timeout

Thêm đồng thời cả delay và timeout để test tình huống phức tạp.

## S. Xem thông tin Proxy & Toxics

Xem trạng thái hiện tại của proxy và các toxic đang bật.

## E. Xóa tất cả Toxics

Xóa toàn bộ các toxic đang áp dụng lên proxy.

---

## R. Test Retry Logic (timeout → retry)

Test logic tự động retry khi gặp timeout, kiểm tra hệ thống có thử lại khi lỗi mạng không.

## W. Test Fallback Data (API fail → dùng dự phòng)

Test khi API backend bị lỗi thì hệ thống có dùng dữ liệu dự phòng (fallback) không.

---

## 1. Scenario: Timeout → Retry → Success

Mô phỏng tình huống request bị timeout, hệ thống tự động retry và cuối cùng thành công.

## 2. Scenario: Partial Commit (Bank B chết)

Mô phỏng tình huống một bank chết giữa chừng, kiểm tra hệ thống xử lý commit một phần (partial commit) như thế nào.

---

## T. DEBUG CHUYÊN SÂU Timeout (theo dõi từng bước)

Chạy test chuyên sâu để debug chi tiết quá trình timeout.

## G. Cấu hình giá trị mặc định

Cấu hình lại các giá trị mặc định cho các toxic.

## 7. KIỂM TRA SERVICES

Kiểm tra trạng thái các service (backend, proxy, toxiproxy...).

## 0. Thoát

Thoát chương trình test.

# Gợi ý debug khi test mạng chậm (Bandwidth Toxic)

# Khi bạn thêm Bandwidth (giới hạn băng thông), để dễ nhận biết hiệu ứng mạng chậm:

# 1. Quan sát thời gian thực thi (elapsed time) của từng request, sẽ tăng rõ rệt.

# 2. Có thể thêm log chi tiết tốc độ truyền thực tế vào các test case.

# 3. Sử dụng debug_print để in thêm thông tin về bandwidth nếu có.

# Ví dụ: Thêm log tốc độ truyền vào các test case

# (Chèn đoạn này sau khi in Time và trước khi in kết quả)

# Giả sử bạn biết bandwidth đang set (rate), có thể in ra:

# debug_print(f"Bandwidth toxic đang bật: {rate} bytes/s ({rate/1024:.2f} KB/s)")

# debug_print(f"Thời gian thực thi: {elapsed:.2f}s, dữ liệu truyền: {data_size} bytes, tốc độ TB: {data_size/elapsed/1024:.2f} KB/s")

# Nếu muốn tự động phát hiện có bandwidth toxic, có thể sửa hàm format_toxic_info hoặc khi gọi API xem thông tin toxics, in ra nếu có type = 'bandwidth'.

# Khi test, nếu thấy thời gian trả về tăng lên bất thường, hoặc tốc độ truyền thấp hơn bình thường, đó là dấu hiệu mạng chậm đã được mô phỏng thành công.
