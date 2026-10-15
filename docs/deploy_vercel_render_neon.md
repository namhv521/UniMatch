# Hướng dẫn UniMatch: Vercel, Render Free và Neon PostgreSQL

Hướng dẫn thao tác thủ công, đối chiếu source ngày 15/10/2026. Chưa tạo hoặc triển khai dịch vụ cloud. Các URL ví dụ phải thay bằng URL được cấp thực tế.

## 1. Cấu hình nên dùng

- **Frontend:** Vercel, static HTML/CSS/JavaScript trong `frontend/`.
- **Backend:** Render Web Service, Python/FastAPI, một worker.
- **Database:** Neon PostgreSQL, kết nối từ backend bằng `DATABASE_URL`.
- **Ping:** cron-job.org gọi health endpoint của Render mỗi 5 phút.

Trình duyệt gọi `https://<frontend>/api/v1/...`. Vercel rewrite request tới `https://<backend>/api/v1/...`. FE và BE vẫn triển khai độc lập; trình duyệt sử dụng cùng origin cho giao diện và API.

Cách này phù hợp với code hiện tại: FE gọi `/api/v1`, gửi cookie `same-origin`; backend đặt cookie `HttpOnly`, `Secure`, `SameSite=Strict` và kiểm tra Origin của request ghi. Không cần chuyển sang token trong localStorage hoặc sửa giao diện. Cần kiểm chứng login, cookie và Origin sau khi triển khai proxy thực tế.

**Chọn Neon thay MongoDB:** đã có `PostgresStorage` trong `backend/app/storage.py` và schema tại `database/schema.sql`. MongoDB chưa có adapter; không thể chỉ thay connection string.

## 2. Chuẩn bị source và dữ liệu trước khi deploy

Repo sản phẩm nằm tại `C:\Su\KLTNv2\KLTN`. Repo Git hiện bỏ qua `data/` và `outputs/`. Clone/push source thông thường không mang theo dữ liệu và checkpoint. API có thể trả HTTP 200 ở health nhưng `data_loaded=false`.

### Phương án đơn giản cho lần deploy đầu

Tạo **repository GitHub private riêng** cho deployment. Chỉ đưa source, snapshot cần phục vụ và checkpoint cần demo vào repo private này. Giữ repo nguồn công khai và `.gitignore` hiện tại nguyên trạng. Không chuyển repo deployment sang public vì chứa hồ sơ sinh viên/GV và model.

Copy từ **working tree hiện tại**, không clone remote cũ rồi kỳ vọng có các thay đổi local chưa push.

PowerShell, tạo bản sao riêng; lệnh dừng nếu thư mục đích đã tồn tại:

```powershell
$sourceRoot = 'C:\Su\KLTNv2\KLTN'
$deployRoot = 'C:\Su\UniMatch-deploy'
if (Test-Path -LiteralPath $deployRoot) { throw 'Thư mục đích đã tồn tại. Chọn thư mục mới.' }
New-Item -ItemType Directory -Path $deployRoot | Out-Null

foreach ($name in @('src', 'backend', 'scripts', 'database', 'configs', 'assets', 'frontend')) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination $deployRoot -Recurse
}
foreach ($name in @('requirements.txt', 'run_dashboard.py', '.gitignore')) {
    Copy-Item -LiteralPath (Join-Path $sourceRoot $name) -Destination $deployRoot
}

New-Item -ItemType Directory -Path "$deployRoot\data\curated", "$deployRoot\data\features", "$deployRoot\outputs\benchmarks" -Force | Out-Null
foreach ($name in @('theses.json', 'advisors.json', 'split_indices.json', 'serving_contract.json', 'quality_report_v2.json')) {
    Copy-Item -LiteralPath "$sourceRoot\data\curated\$name" -Destination "$deployRoot\data\curated"
}
foreach ($name in @('feature_manifest_v2.json', 'compatibility_matrix_v2.npy')) {
    Copy-Item -LiteralPath "$sourceRoot\data\features\$name" -Destination "$deployRoot\data\features"
}
Copy-Item -LiteralPath "$sourceRoot\outputs\benchmarks\current-validation.json" -Destination "$deployRoot\outputs\benchmarks"

foreach ($name in @('checkpoints', 'research-real', 'research-filtered', 'research-current')) {
    $modelDirectory = Join-Path "$sourceRoot\outputs" $name
    if (Test-Path -LiteralPath $modelDirectory) {
        New-Item -ItemType Directory -Path "$deployRoot\outputs\$name" -Force | Out-Null
        Get-ChildItem -LiteralPath $modelDirectory -File |
            Where-Object { $_.Extension -in @('.json', '.zip') } |
            Copy-Item -Destination "$deployRoot\outputs\$name"
    }
}
Set-Location $deployRoot
```

Đây là bản sao phục vụ inference; không cần copy raw data, training logs hoặc SQLite runtime. Những file build/cache được copy trong các thư mục source vẫn được `.gitignore` loại khỏi Git. Bản copy không mang theo `.git`, `.env` hoặc GitHub Actions cũ.

Kiểm tra tối thiểu trên bản sao, dùng môi trường Python đã cài dependency:

```powershell
python -c "from src.serving import MatchingService; s=MatchingService(); print('advisors:',len(s.advisors)); print('quality_ready:',s.catalog()['quality']['ready'])"
npm --prefix frontend run check
npm --prefix frontend run test
npm --prefix frontend run build
```

Với snapshot hiện tại, mong đợi 38 GV và quality report còn khớp hash. Không sửa hash để vượt kiểm tra. Checkpoint không đồng nghĩa RL đã được promote.

Tạo GitHub repository **private** tên `unimatch-deploy`, không khởi tạo README. Sau đó, PowerShell tại bản sao:

```powershell
git init
git branch -M main
git add src backend scripts database configs assets frontend requirements.txt run_dashboard.py .gitignore
git add -f data/curated/theses.json data/curated/advisors.json data/curated/split_indices.json data/curated/serving_contract.json data/curated/quality_report_v2.json
git add -f data/features/feature_manifest_v2.json data/features/compatibility_matrix_v2.npy outputs/benchmarks/current-validation.json
foreach ($name in @('checkpoints', 'research-real', 'research-filtered', 'research-current')) {
    if (Test-Path -LiteralPath "outputs\$name") { git add -f -- "outputs/$name" }
}
git diff --cached --stat
git status --short
```

Kiểm tra danh sách không chứa credential, `.env`, SQLite, file không cần thiết; xác nhận repository đích là private. Thay `<GITHUB_USER>` bằng tài khoản của bạn:

```powershell
git commit -m "Prepare private UniMatch deployment"
git remote add origin https://github.com/<GITHUB_USER>/unimatch-deploy.git
git push -u origin main
```

Về lâu dài có thể đưa bundle riêng lên object storage có xác thực. Không cần xây thêm cơ chế đó cho lần deploy đầu. Neon lưu dữ liệu ứng dụng; source hiện vẫn cần các file snapshot/model bên trên để inference.

## 3. Tạo database Neon trước

1. Mở [Neon Console](https://console.neon.tech/), tạo project `unimatch`, gói Free.
2. Chọn region gần backend. Có thể chọn Singapore cho cả hai nếu tài khoản hiện hỗ trợ.
3. Dùng database `neondb` được tạo sẵn, hoặc tạo database tên `unimatch`.
4. Chọn **Connect**, lấy PostgreSQL connection string. Bật pooling nếu dùng hostname `-pooler`.
5. Giữ `sslmode=require`; giữ các tùy chọn bảo mật khác mà Neon cung cấp.

Ví dụ minh họa, không phải credential thật:

```dotenv
DATABASE_URL=postgresql://<USER>:<PASSWORD>@<HOST>-pooler.<REGION>.aws.neon.tech/neondb?sslmode=require
```

Copy nguyên URI do Neon cung cấp. Backend dùng psycopg trực tiếp, không dùng prefix `postgresql+psycopg://`. Chỉ đặt URI ở Environment của Render; không đặt trong frontend, `vercel.json` hoặc Git.

Không cần import schema bằng tay khi tạo database trống. Khi FastAPI startup, `PostgresStorage.initialize()` chạy `database/schema.sql`, tạo bảng và import snapshot nếu bundle đã có. Role database phải có quyền tạo bảng trong schema được chọn.

Các bảng chính: `snapshots`, `students`, `advisors`, `split_memberships`, `simulation_runs`, `feedback`. Lịch sử SQLite cũ không tự chuyển sang Neon; hướng dẫn này tạo deployment với lịch sử mới.

## 4. Deploy backend lên Render Free

Tạo **New → Web Service**, kết nối repository private `unimatch-deploy`. Chọn native runtime **Python 3**, không chọn Docker tự nhận diện từ repo nguồn.

| Trường | Giá trị |
|---|---|
| Name | `unimatch-api` hoặc tên còn trống |
| Branch | `main` |
| Root Directory | Để trống, vì bản sao đã có `backend/` ở root |
| Runtime / Language | Python 3 |
| Region | Gần region Neon |
| Instance | Free |
| Health Check Path | `/api/v1/health` |

**Build Command:** cài CPU PyTorch trước để tránh tải CUDA package không cần thiết:

```bash
pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu && pip install -r requirements.txt
```

**Start Command:**

```bash
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT --workers 1
```

Đây là lệnh Linux của Render; không thay `$PORT` bằng cú pháp PowerShell. Một worker vì session hiện lưu trong RAM. Không chạy training trên Render Free.

Thêm Environment Variables:

| Key | Value |
|---|---|
| `PYTHON_VERSION` | `3.12.12` |
| `DATABASE_URL` | URI Neon vừa copy |
| `KLTN_DATABASE_SCHEMA` | `public` |
| `KLTN_LOGIN_EMAIL` | Email bạn chọn để đăng nhập ứng dụng |
| `KLTN_LOGIN_PASSWORD` | Mật khẩu dài, riêng cho ứng dụng |
| `KLTN_COOKIE_SECURE` | `true` |
| `KLTN_ALLOWED_ORIGIN` | Sau bước 5, đặt URL Vercel chính xác, ví dụ `https://unimatch-demo.vercel.app` |
| `OMP_NUM_THREADS` | `1` |
| `OPENBLAS_NUM_THREADS` | `1` |
| `MKL_NUM_THREADS` | `1` |

Nếu chưa có URL FE, có thể để trống `KLTN_ALLOWED_ORIGIN` trong lần deploy BE đầu; phải bổ sung trước khi đăng nhập qua FE. Không dùng `*`. Không cần các biến Docker `POSTGRES_PASSWORD`, `KLTN_DOMAIN` hoặc `KLTN_WEB_PORT` cho native Render.

Deploy, chờ service **Live**, ghi lại URL thật. Ví dụ dưới đây dùng `https://unimatch-api-EXAMPLE.onrender.com`; tên thật có thể có hậu tố khác.

PowerShell:

```powershell
Invoke-RestMethod 'https://<RENDER_HOST>/api/v1/health'
```

Phải có `data_loaded=true`, `total_advisors=38`. Chỉ có HTTP 200 chưa đủ vì endpoint hiện vẫn trả 200 khi thiếu serving data. `quality_ready` phản ánh kiểm tra dữ liệu/chất lượng trong code, không chứng minh RL đã được promote.

Render Free có 512 MB RAM; cần theo dõi Metrics/Logs khi chạy RL. Cấu hình CPU và một worker giảm tải nhưng chưa chứng minh model chạy vừa RAM. Nếu OOM, dùng semantic/Hungarian để demo trước hoặc chọn máy đủ RAM; không thể sửa giới hạn RAM bằng ping.

## 5. Deploy frontend lên Vercel

Trong **bản sao deployment**, tạo `frontend/vercel.json`. Thay hostname ví dụ bằng hostname Render thật trước khi commit:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": null,
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://unimatch-api-EXAMPLE.onrender.com/api/:path*"
    }
  ],
  "headers": [
    {
      "source": "/api/:path*",
      "headers": [
        { "key": "Cache-Control", "value": "private, no-store" }
      ]
    }
  ]
}
```

Giữ `/api` ở destination, vì backend có route `/api/v1/...`. Không cấu hình redirect 301/302 sang Render. Không cache các route API chứa dữ liệu theo phiên.

```powershell
Set-Location C:\Su\UniMatch-deploy
git add frontend/vercel.json
git commit -m "Route frontend API requests to Render"
git push
```

Vercel → Add New Project → import repo private:

| Trường | Giá trị |
|---|---|
| Framework Preset | **Other**, không chọn FastAPI |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `dist` |

FE hiện không phải Next.js/Vite, không cần `NEXT_PUBLIC_API_URL` hoặc `VITE_API_URL`. `frontend/build.mjs` copy năm file static sang `dist`.

Deploy FE. Lấy URL production được cấp; quay lại Render, đặt:

```dotenv
KLTN_ALLOWED_ORIGIN=https://<VERCEL_PRODUCTION_HOST>
```

Save/redeploy BE, rồi mới đăng nhập trên Vercel. Nếu thêm domain riêng, thêm chính xác origin mới vào biến trên; nhiều origin ngăn cách bằng dấu phẩy. Tránh wildcard cho mọi preview. Request frontend vẫn dùng URL `/api/v1`, cookie được trình duyệt xử lý trên domain Vercel qua proxy.

Backend hiện vẫn có khả năng phục vụ bản frontend đi kèm trên URL Render. Trong deployment này, URL dành cho người dùng là Vercel; không cần dùng trang Render để đăng nhập.

## 6. Ping Render mỗi 5 phút

### Cách dùng ít code nhất: cron-job.org

1. Tạo tài khoản tại [cron-job.org](https://cron-job.org/en/).
2. Tạo cron job `UniMatch API health`.
3. URL: `https://<RENDER_HOST>/api/v1/health`.
4. Method: `GET`.
5. Schedule: every **5 minutes**, hoặc biểu thức `*/5 * * * *`.
6. Chạy thử và xem execution history có HTTP 200. Không cần gửi mật khẩu hoặc URI database.

Gọi trực tiếp Render để tránh phụ thuộc vào Vercel/protection của preview. Health hiện không query PostgreSQL, nên ping này không giữ Neon compute thức liên tục; Neon có thể có cold start riêng.

**Giới hạn cần biết:**

- Render Free spin down sau 15 phút không có inbound traffic. Ping ngoài là request định kỳ hỗ trợ giảm tình huống này, không bảo đảm luôn thức hoặc tránh restart.
- Render cấp 750 free instance hours cho **cả workspace** mỗi tháng. Nhiều web service Free cùng chạy liên tục có thể hết quota. Kiểm tra Usage trước khi giữ thêm service thức cả ngày.
- Vercel Hobby cron chỉ hỗ trợ lịch hằng ngày, không phù hợp ping mỗi 5 phút.
- `setInterval` trong FE ngừng hoạt động khi đóng tab và có thể bị throttle khi chạy nền. Timer bên trong BE cũng dừng khi instance ngủ. Không dùng hai cách này làm scheduler liên tục.
- Health HTTP 200 không thay thế kiểm tra `data_loaded`, DB hoặc một lượt phân bổ thực tế.

### Nếu muốn tự chạy code ping trên máy luôn bật

PowerShell, thay URL thật:

```powershell
$healthUrl = 'https://<RENDER_HOST>/api/v1/health'
while ($true) {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 90
        Write-Host (Get-Date -Format s) 'data_loaded=' $health.data_loaded
    } catch {
        Write-Warning ('Ping thất bại: ' + $_.Exception.Message)
    }
    Start-Sleep -Seconds 300
}
```

Máy và terminal phải luôn chạy; `Ctrl+C` dừng vòng lặp. Không cần chạy đồng thời với cron-job.org.

## 7. Kiểm chứng sau deploy

1. Mở health trực tiếp Render, xác nhận bundle được nạp.
2. Mở `https://<VERCEL_HOST>/api/v1/health`, so sánh kết quả để xác nhận rewrite.
3. Đăng nhập trên Vercel. DevTools → Network: login 200; `/auth/session` trả `authenticated=true`; catalog 200.
4. Cookie `kltn_session` thuộc domain frontend, có `HttpOnly`, `Secure`, `SameSite=Strict`.
5. Chạy phân bổ semantic/Hungarian và thử Excel mẫu; request phải thành công.
6. Trong Neon SQL Editor, kiểm tra:

```sql
SELECT count(*) FROM snapshots;
SELECT count(*) FROM students;
SELECT count(*) FROM advisors;
SELECT count(*) FROM simulation_runs;
SELECT count(*) FROM feedback;
```

Với một snapshot hiện tại, mong đợi 215 students và 38 advisors. Sau nhiều snapshot, tổng có thể lớn hơn. Một lượt phân bổ thành công phải tăng `simulation_runs`; feedback chỉ tăng khi gửi feedback.

7. Restart BE một lần rồi đăng nhập lại: lịch sử ở Neon vẫn còn. Session RAM mất khi restart/sleep/redeploy là giới hạn hiện tại; chưa có persistent session store.
8. Xem RAM khi chạy từng model RL, execution history của ping, quota Render và Neon. Chưa có các kiểm tra này thì chưa kết luận cloud hoạt động đầy đủ.

## 8. Lỗi thường gặp

| Hiện tượng | Kiểm tra |
|---|---|
| Vercel tự chọn FastAPI | Đổi Other, Root Directory = `frontend` |
| API qua Vercel 404 | Kiểm tra `frontend/vercel.json`, hostname Render và `/api` trong destination |
| Login trả `origin_rejected` | `KLTN_ALLOWED_ORIGIN` phải khớp URL đang mở trên trình duyệt |
| Login 200, catalog 401 | Kiểm tra rewrite là proxy, cookie trên domain FE, HTTPS và chỉ một worker |
| `data_loaded=false` | Thiếu private snapshot hoặc sai đường dẫn root; xem log `serving_initialization_failed` |
| Startup không hoàn tất | Kiểm tra URI Neon, SSL, role/schema và dependency |
| Backend bị kill/restart khi RL | Xem RAM; Render Free chỉ 512 MB |
| Lần truy cập đầu chậm | Có thể Render hoặc Neon cold start; kiểm tra từng dịch vụ |
| Sau restart bị đăng xuất | Session hiện lưu RAM; dữ liệu Neon vẫn cần kiểm tra độc lập |

## Nguồn chính thức

- [Vercel external rewrites](https://vercel.com/docs/routing/rewrites)
- [Vercel cron scheduling limits](https://vercel.com/docs/cron-jobs/usage-and-pricing)
- [Render Free: sleep và quota](https://render.com/docs/free)
- [Render Python version](https://render.com/docs/python-version)
- [Render instance resources](https://render.com/pricing)
- [Neon connection strings](https://neon.com/docs/connect/connect-from-any-app)
- [cron-job.org](https://cron-job.org/en/)
