<p align="center">
  <img src="miku.jpg" alt="MikuMaintaining" width="500">
</p>
<p align="center"><span style="color:#8a8f98;">"39!"</span></p>

<h1 align="center">MikuMaid_reborn</h1> 

**MikuMaid_reborn** phiên bản tối giản, tập trung hoàn toàn vào hiệu năng với sự hỗ trợ của NVIDIA NIM. Dự án đã được tinh chỉnh để loại bỏ các thành phần dư thừa.

## Tính năng

- **NVIDIA NIM Integration:** Sử dụng model `google/gemma-3n-e4b-it` (hoặc các model khác hỗ trợ bởi NVIDIA NIM) cho tốc độ phản hồi cực nhanh.
- **User-Based Memory Isolation:** Mỗi người dùng có một "bộ não" riêng. Lịch sử trò chuyện được cô lập theo `user_id`, không còn tình trạng nhầm lẫn ngữ cảnh giữa những người dùng khác nhau.
- **KomiFilter 2.0:** Bộ lọc bảo mật nâng cao chống Prompt Injection, Jailbreak và rò rỉ thông tin hệ thống (Prompt Leak).
- **Visual Env Sync:** Hệ thống đồng bộ hóa file cấu hình trực quan, tự động cập nhật và liệt kê các biến còn thiếu khi khởi động.
- **Tối giản tối đa:** Đã loại bỏ tất cả các Hooks phức tạp và các Provider khác để tối ưu hóa tài nguyên.

## Cài đặt nhanh

```bash
# Tạo môi trường ảo
python -m venv .venv
# Kích hoạt môi trường (Windows)
.venv\Scripts\activate
# Cài đặt thư viện
pip install -r requirements.txt
```

## Cấu hình (.env)

Hệ thống sẽ tự động tạo file `.env` từ `.env.example` khi bạn chạy bot lần đầu. Bạn chỉ cần điền các thông tin quan trọng:

- `NVIDIA_API_KEY`: API Key lấy từ NVIDIA API Catalog.
- `NVIDIA_MODEL`: Model sử dụng (mặc định: `google/gemma-3n-e4b-it`).
- `DISCORD_TOKEN`: Token của bot Discord.
- `OWNER_USER_ID`: ID của bạn để sử dụng các lệnh Admin.

## Lệnh điều khiển

### Chat & AI
- **@Bot + Nội dung:** Chat trực tiếp với Miku.
- **!chat <nội dung>:** Chat bằng lệnh (hỗ trợ đính kèm hình ảnh).
- **!ask <nội dung>:** Bí danh của lệnh chat.

### Quản lý (Admin Only)
- **!clearmemo:** Xóa sạch toàn bộ bộ nhớ ngắn hạn của **tất cả người dùng**.
- **!ban @user [lý do]:** Cấm người dùng sử dụng bot.
- **!removeban @user:** Gỡ lệnh cấm.
- **!replaymiku ls:** Xem danh sách nhật ký chat gần đây.
- **!replaymiku <id>:** Xem chi tiết nội dung chat theo ID.

### Khác
- **!provider:** Xem thông tin về model và cấu hình hệ thống hiện tại.
- **!terminated on|off:** Bật/tắt chế độ tạm dừng hoạt động của bot.

## Bảo mật (KomiFilter)

`KomiFilter` bảo vệ bot qua 3 lớp:
1. **Chặn User Injection:** Ngăn chặn các câu lệnh như "ignore previous instructions".
2. **Chặn Prompt Leak:** Ngăn người dùng yêu cầu xem mã nguồn hoặc luật hệ thống.
3. **Chặn Response Leak:** Tự động ẩn các phản hồi từ AI nếu chứa thông tin nhạy cảm của hệ thống.

## Lưu trữ

Hệ thống sử dụng SQLite để lưu trữ dữ liệu một cách độc lập:
- `chat_memory.db`: Lưu lịch sử chat cô lập theo User ID.
- `ban_control.db`: Lưu danh sách người dùng bị cấm.
- `callnames.db`: Lưu biệt danh cá nhân hóa.

---
**License:** MIT  
**Art by:** [gomya0_0](https://x.com/gomya0_0)
