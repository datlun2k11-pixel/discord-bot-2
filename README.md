# Discord Bot - AI Enhanced

Một Discord bot thông minh được tích hợp AI để xử lý hội thoại, quản lý sự kiện và lưu trữ dữ liệu người dùng.

## Tính năng chính

- 🤖 **AI Chat**: Tích hợp mô hình ngôn ngữ lớn để trò chuyện tự nhiên
- 💾 **Lưu trữ dữ liệu**: Tự động lưu lịch sử chat và cấu hình người dùng
- 📎 **Xử lý file**: Hỗ trợ đính kèm hình ảnh và tài liệu
- ⚡ **Real-time events**: Phản hồi nhanh với các sự kiện Discord
- 🔧 **Cấu hình linh hoạt**: Dễ dàng tùy chỉnh qua biến môi trường

## Cài đặt

1. Clone repository:
```bash
git clone <repo-url>
cd <project-folder>
```

2. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

3. Cấu hình biến môi trường (`.env`):
```env
DISCORD_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
GEMINI_API_KEY=your_gemini_key_here
```

4. Chạy bot:
```bash
python main.py
```

## Cấu trúc dự án

```
├── main.py          # Entry point, setup bot và routes
├── event.py         # Xử lý sự kiện Discord và AI logic
├── config.py        # Quản lý cấu hình và lưu trữ dữ liệu
├── requirements.txt # Dependencies
└── README.md        # Tài liệu này
```

## Lưu ý

- Bot cần quyền `Message Content Intent` để đọc nội dung tin nhắn
- Dữ liệu được lưu tự động mỗi 5 phút và khi bot tắt
- Hỗ trợ rate limiting để tránh spam API

---

*written by Qwen Coder*  
*this project was an AI slopped*
