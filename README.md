# Assessment Hub

App Frappe Framework v16 quản lý bài đánh giá theo cấu trúc Assessment, Question, Answer.

## Yêu cầu môi trường

| Thành phần | Phiên bản tối thiểu | Đã test trên |
| --- | --- | --- |
| Frappe Framework | version-16 | 16.34.0 |
| Python | 3.14, dưới 3.15 | 3.14.7 |
| Node.js | 24 | 24.21.0 |
| Yarn | 1.22 | 1.22.22 |
| MariaDB | 10.6 (utf8mb4) | 10.11.14 |
| Redis | 6 | 7.0.15 |

Frappe v16 khoá cứng `requires-python = ">=3.14,<3.15"` và `engines.node = ">=24"`.
Python 3.11, 3.12 hoặc Node 20 sẽ không cài được app này.

## Cài đặt

### Bước 1. Chuẩn bị bench

Bỏ qua bước này nếu bạn đã có sẵn một bench chạy Frappe v16.

```bash
# Runtime
uv python install 3.14
nvm install 24 && nvm use 24
npm install -g yarn
uv tool install frappe-bench

# Bench mới
#  mkdir frappe-bench && cd frappe-bench
#  bench init --frappe-branch version-16 --python "$(which python3.14)" --ignore-exist .
cd ~
bench init --frappe-branch version-16 --python "$(uv python find 3.14)" frappe-bench
cd frappe-bench
```

### Bước 2. Tạo site

```bash
bench new-site dev.localhost \
  --db-root-password '<mật khẩu root MariaDB>' \
  --admin-password '<mật khẩu Administrator>' \
  --mariadb-user-host-login-scope='%'

bench use dev.localhost
```

### Bước 3. Lấy app từ repo

```bash
bench get-app https://github.com/TienPhuc02/assessment_hub.git
```

Lấy theo tag hoặc branch cụ thể:

```bash
bench get-app --branch main https://github.com/TienPhuc02/assessment_hub.git
```

### Bước 4. Cài app lên site

```bash
bench --site dev.localhost install-app assessment_hub
bench --site dev.localhost migrate
```

### Bước 5. Build assets

```bash
nvm use 24
bench build --app assessment_hub
```

### Bước 6. Chạy

```bash
bench start
```

Mở http://dev.localhost:8000 và đăng nhập bằng user `Administrator`.

Nếu cổng 8000 đã bị chiếm, bench sẽ tự chọn cổng khác. Kiểm tra bằng:

```bash
grep webserver_port sites/common_site_config.json
```

## Kiểm tra cài đặt

```bash
# App có trong danh sách của site
bench --site dev.localhost list-apps

# Phiên bản frappe đang chạy
bench version
```

Kết quả mong đợi của `list-apps`:

```
frappe          16.34.0 version-16
assessment_hub  0.0.1
```

## Gỡ cài đặt

```bash
# Gỡ khỏi site
bench --site dev.localhost uninstall-app assessment_hub

# Gỡ khỏi bench
bench remove-app assessment_hub
```

## Kiến trúc dữ liệu

```mermaid
erDiagram
    ASSESSMENT ||--o{ QUESTION : "có 0..n"
    QUESTION   ||--|{ ANSWER   : "gồm 1..n"
    ASSESSMENT {
        string name PK "ASM-.#####"
        string title
        string description
        string status "Draft|Published|Archived"
    }
    QUESTION {
        string name PK "QST-.#####"
        string assessment FK
        string content
        int    sort_order
        string status "Active|Inactive"
    }
    ANSWER {
        string name PK
        string parent FK "-> Question"
        string content
        float  score
        int    sort_order
    }
```

### Answer là Child Table của Question

**Lý do.** Answer không có ý nghĩa khi tách khỏi Question. Nhập trên grid ngay trong form
Question nhanh hơn mở từng form riêng. Một lần `doc.insert()` ghi Question và toàn bộ Answer
trong cùng một transaction nên tính atomic là tự nhiên, không phải viết thêm code. Answer kế
thừa quyền của Question, không bao giờ mồ côi, xoá Question là xoá sạch Answer đi kèm.

**Đánh đổi.** Không phân quyền riêng cho từng Answer. DocType khác không Link trực tiếp tới
một Answer được. Sửa một Answer phải save lại cả Question.

**Khi nào nên đổi sang Standalone.** Khi cần ngân hàng đáp án dùng lại giữa nhiều câu hỏi,
hoặc khi có bảng kết quả làm bài cần Link tới từng Answer cụ thể.

### Question là Standalone DocType, không phải Child Table của Assessment

**Lý do.** Question cần `status` và `sort_order` riêng, cần List View và form riêng cho luồng
thêm câu hỏi, cần API list và create độc lập. Quan trọng nhất: Frappe không hỗ trợ child table
lồng trong child table, nên nếu Question là child của Assessment thì Answer không thể là child
của Question nữa.

**Đánh đổi.** Phải kiểm tra Link và phân quyền ở cả hai DocType thay vì một.

## Partner REST API v1

Đang xây dần theo từng endpoint (FR-14 đến FR-17); phần dưới đây là **hợp đồng chung**, đã cố
định và có code thật (`assessment_hub/api/utils.py`), không phụ thuộc endpoint nào.

### Xác thực

Header `Authorization: token <api_key>:<api_secret>`. Không có `allow_guest=True` ở bất kỳ
endpoint nào — thiếu token bị Frappe từ chối như Guest không đủ quyền, sai token bị từ chối ở
tầng xác thực trước khi vào code của app.

```bash
curl -H "Authorization: token <api_key>:<api_secret>" \
  http://dev.localhost:8000/api/v2/method/assessment_hub.api.v1.assessments.list_assessments
```

Sinh API key/secret cho một user:

```bash
bench --site dev.localhost console
```

```python
user = frappe.get_doc("User", "partner@example.com")
api_secret = frappe.generate_hash(length=15)
user.api_key = frappe.generate_hash(length=15)
user.api_secret = api_secret
user.save(ignore_permissions=True)
frappe.db.commit()
print(user.api_key, api_secret)  # api_secret chỉ hiện lúc này, không đọc lại được
```

### Định dạng response

Thành công: HTTP 200, `{"data": ...}`. Thất bại: HTTP 4xx/5xx,
`{"errors": [{"message": "...", "code": "..."}]}`. Mọi endpoint bọc bằng decorator
`@api_response` (`api/utils.py`), tự bắt exception và dựng đúng hai dạng trên.

| HTTP | code | Khi nào |
| --- | --- | --- |
| 400 | MISSING_REQUIRED_FIELD | Thiếu tham số bắt buộc |
| 400 | INVALID_PARAMETER | Sai kiểu, sai enum, vượt giới hạn, sai định dạng ngày |
| 400 | VALIDATION_ERROR | Vi phạm rule dữ liệu trong controller |
| 401 | AUTHENTICATION_FAILED | Token sai/thiếu định dạng |
| 403 | PERMISSION_DENIED | Không đủ quyền (kể cả gọi ẩn danh, xem giới hạn bên dưới) |
| 404 | NOT_FOUND | Bản ghi không tồn tại |
| 405 | METHOD_NOT_ALLOWED | Sai HTTP method |
| 422 | ASSESSMENT_ARCHIVED | Thêm/sửa Question của Assessment đã Archived |
| 500 | INTERNAL_ERROR | Lỗi không lường trước, đã ghi Error Log, không lộ traceback |

### Giới hạn đã biết (R-02)

Lỗi 401 (token sai) và 405 (sai HTTP method) phát sinh ở tầng xác thực/định tuyến của Frappe,
**trước khi** request tới được `@api_response` — body trả về là định dạng lỗi mặc định của
Frappe, không phải `{"errors": [...]}`. Đã kiểm chứng bằng `curl` thật: token sai trả về
`{"exception": "...AuthenticationError", ...}` kèm traceback, không phải hai dòng
`message`/`code` như các lỗi khác.

**Thiếu token hẳn (không có header) trả 403, không phải 401** — request không có
`Authorization` được Frappe xử lý như user `Guest`, và `Guest` không có quyền gọi endpoint
không `allow_guest`, nên rơi vào `PermissionError` (403) chứ không phải `AuthenticationError`
(401). Chỉ token **sai định dạng hoặc sai giá trị** mới ra đúng 401.

### Endpoint: `GET assessments.list_assessments`

| Tham số | Bắt buộc | Mặc định | Quy tắc |
| --- | --- | --- | --- |
| `status` | Không | Không | `Draft`, `Published` hoặc `Archived` |
| `search` | Không | Không | Tìm trong `title`, không phân biệt hoa thường, tối đa 140 ký tự |
| `updated_since` | Không | Không | ISO 8601 hoặc `YYYY-MM-DD`; lọc `modified >=`, đổi sort sang tăng dần |
| `page_length` | Không | 20 (Settings) | 1–100 (trần từ Settings) |
| `start` | Không | 0 | ≥ 0, bỏ qua nếu có `page` |
| `page` | Không | Không | ≥ 1, ưu tiên hơn `start` |

```bash
curl -H "Authorization: token <api_key>:<api_secret>" \
  "http://dev.localhost:8000/api/v2/method/assessment_hub.api.v1.assessments.list_assessments?status=Published&page=1&page_length=10"
```

```json
{
  "data": {
    "items": [
      {
        "id": "ASM-00001",
        "title": "Python Fundamentals",
        "description": null,
        "status": "Published",
        "created_at": "2026-09-15T09:12:03+07:00",
        "updated_at": "2026-09-16T14:30:45+07:00"
      }
    ],
    "pagination": {"start": 0, "page_length": 10, "has_more": false}
  }
}
```

Không có `total` trong `pagination` — đó là FR-19 (Could, mở rộng), cố tình chưa làm để giữ
đúng kỹ thuật "lấy `page_length + 1` bản ghi suy ra `has_more`" (không cần query COUNT riêng).

### Endpoint: `GET assessments.get_assessment`

| Tham số | Bắt buộc | Mặc định | Quy tắc |
| --- | --- | --- | --- |
| `id` | Có | Không | Phải tồn tại và có quyền đọc, không thì 404/403 |
| `include_questions` | Không | `0` | `0`/`1`/`true`/`false`; giá trị khác → 400 |

```bash
curl -H "Authorization: token <api_key>:<api_secret>" \
  "http://dev.localhost:8000/api/v2/method/assessment_hub.api.v1.assessments.get_assessment?id=ASM-00001&include_questions=1"
```

```json
{
  "data": {
    "id": "ASM-00001",
    "title": "Python Fundamentals",
    "description": null,
    "status": "Published",
    "created_at": "2026-09-15T09:12:03+07:00",
    "updated_at": "2026-09-16T14:30:45+07:00",
    "questions": [
      {
        "id": "QST-00001",
        "assessment_id": "ASM-00001",
        "content": "len([1, 2, 3])?",
        "sort_order": 1,
        "status": "Active",
        "answers": [
          {"id": "a1b2c3d4e5", "content": "3", "score": 1.0, "sort_order": 1},
          {"id": "f6g7h8i9j0", "content": "2", "score": 0.0, "sort_order": 2}
        ]
      }
    ]
  }
}
```

`questions` chỉ xuất hiện khi `include_questions=1`. Answers của toàn bộ câu hỏi lấy bằng
**một** truy vấn `frappe.qb` (`parent IN (...)`), không lặp truy vấn theo từng câu hỏi.

### Endpoint: `POST questions.create_question`

| Field | Bắt buộc | Mặc định | Quy tắc |
| --- | --- | --- | --- |
| `assessment_id` | Có | Không | Phải tồn tại (404) và không Archived (422) |
| `content` | Có | Không | Không rỗng sau trim, tối đa 10.000 ký tự |
| `sort_order` | Không | max hiện có + 1 | ≥ 0 |
| `status` | Không | Lấy từ Assessment Hub Settings | `Active` hoặc `Inactive` |
| `answers` | Có | Không | Mảng 1–50 phần tử |
| `answers[].content` | Có | Không | Không rỗng sau trim |
| `answers[].score` | Có | Không | Số hữu hạn, không nhận boolean |
| `answers[].sort_order` | Không | Vị trí trong mảng + 1 | ≥ 0 |

Chỉ Assessment Manager mới tạo được (403 nếu không đủ quyền). Question và toàn bộ Answer ghi
trong đúng 1 `doc.insert()` — không có Question thiếu Answer nửa chừng nếu có lỗi giữa chừng.

```bash
curl -X POST -H "Authorization: token <api_key>:<api_secret>" -H "Content-Type: application/json" \
  -d '{"assessment_id":"ASM-00001","content":"2 + 2 = ?","answers":[{"content":"4","score":1},{"content":"5","score":0}]}' \
  "http://dev.localhost:8000/api/v2/method/assessment_hub.api.v1.questions.create_question"
```

Lỗi mẫu khi một answer rỗng (`answers[1].content`):

```json
{
  "errors": [
    {"message": "Answer content is required", "code": "MISSING_REQUIRED_FIELD", "field": "answers[1].content"}
  ]
}
```

`field` trong response lỗi là 0-based (`answers[1]` = phần tử thứ 2), khác với chỉ số hiển thị
trên Desk grid (1-based, "Row #2") — hai bối cảnh khác nhau, cùng một dòng dữ liệu.

### Endpoint: `GET questions.list_questions`

| Tham số | Bắt buộc | Mặc định | Quy tắc |
| --- | --- | --- | --- |
| `assessment_id` | Có | Không | Phải tồn tại và có quyền đọc, không thì 404/403 |
| `status` | Không | Không | `Active` hoặc `Inactive` |
| `page_length`, `start`, `page` | Không | Như `list_assessments` | Như `list_assessments` |

```bash
curl -H "Authorization: token <api_key>:<api_secret>" \
  "http://dev.localhost:8000/api/v2/method/assessment_hub.api.v1.questions.list_questions?assessment_id=ASM-00001"
```

```json
{
  "data": {
    "items": [
      {
        "id": "QST-00001",
        "assessment_id": "ASM-00001",
        "content": "len([1, 2, 3])?",
        "sort_order": 1,
        "status": "Active"
      }
    ],
    "pagination": {"start": 0, "page_length": 20, "has_more": false}
  }
}
```

Sort mặc định `sort_order ASC`, cùng `sort_order` thì `creation ASC`. `items` **không có**
key `answers` (khác `get_assessment`/`create_question`) — muốn xem đáp án của một câu hỏi cụ
thể, dùng `get_assessment?include_questions=1`.

## License

MIT, xem [license.txt](license.txt).
