"""Role-specific diagnostic questions and self-reported tool options."""

from hashlib import sha256

# Correct answer first in source. Display order is stable across sessions and varies by question.
BANK = """
frontend_development|Frontend Developer|React,Vue,TypeScript,Tailwind CSS|frontend development
Nút gửi biểu mẫu nên dùng phần tử nào?|button|span|div
Để label liên kết với input qua ID dùng thuộc tính nào?|for|role|name
Khi danh sách đổi thứ tự, React nên nhận key gì?|ID ổn định của phần tử|Chỉ số hiện tại|Số ngẫu nhiên mỗi lần render
Cách phát hiện thao tác bị kẹt với người dùng bàn phím?|Kiểm thử Tab và Enter trên luồng chính|Đo tốc độ mạng|Đổi font chữ
Khi gọi API lấy dữ liệu, giao diện nên phân biệt trạng thái nào?|Đang tải, lỗi, trống và có dữ liệu|Chỉ thành công và đang tải|Chỉ có dữ liệu và mất mạng

backend_development|Backend Developer|FastAPI,Spring Boot,Node.js,PostgreSQL,Redis|backend development
Mã HTTP nào biểu thị tài nguyên đã được tạo?|201|204|304
Cách ngăn hai yêu cầu đồng thời tạo trùng email?|Đặt ràng buộc UNIQUE ở cơ sở dữ liệu|Kiểm tra ô nhập ở frontend|Dùng bộ nhớ đệm phía trình duyệt
Với truy vấn SQL có dữ liệu người dùng, cách truyền dữ liệu an toàn hơn là gì?|Tham số truy vấn|Nối chuỗi sau khi trim|Mã hóa URL rồi nối chuỗi
Thiết kế thanh toán có thể gửi lại sau timeout cần thuộc tính nào?|Idempotency bằng mã yêu cầu|Ẩn nút sau mỗi click|Luôn tạo giao dịch mới khi thử lại
Hai cập nhật số dư phải cùng thành công cần cơ chế nào?|Giao dịch cơ sở dữ liệu|Bộ nhớ đệm CDN|Chỉ mục toàn văn

full_stack_development|Full-stack / Web & App|React,Next.js,Node.js,FastAPI,GraphQL,Docker|full stack development,web development
Khi frontend và backend thay đổi độc lập, nên thống nhất gì trước?|Hợp đồng API và dữ liệu lỗi|Cùng một IDE|Cùng hệ điều hành
Vì sao vẫn cần kiểm tra quyền trên server sau khi ẩn nút ở client?|Client có thể gọi API trực tiếp|Ẩn nút làm chậm DOM|Server cần chọn màu nút
Để cập nhật trạng thái đơn hàng ngay khi server thay đổi, giao thức nào phù hợp?|WebSocket|CSS media query|DNS
Khi một luồng hỏng ở production, dữ liệu nào giúp nối các log?|Mã tương quan của yêu cầu|Màu giao diện|Tên máy cá nhân
Để chắc chắn form lưu dữ liệu và hiển thị đúng, nên bổ sung bài kiểm thử nào?|Kiểm thử end-to-end qua luồng thật|Chỉ kiểm tra format mã nguồn|Chỉ so sánh ảnh màn hình tĩnh

mobile_app_development|Mobile / Desktop Developer|Flutter,React Native,Kotlin,Swift,SQLite,Electron|mobile application development,desktop application
Ứng dụng offline nên lưu dữ liệu cấu trúc vào đâu?|SQLite thiết bị|URL deep link|Bộ nhớ của màn hình
Khi mạng trở lại, cách chọn bản ghi cần đồng bộ?|Theo trạng thái chưa đồng bộ và ID ổn định|Gửi lại tất cả sau mỗi thao tác|Dựa vào tên màn hình
Deep link dùng để làm gì?|Mở đúng màn hình hoặc nội dung trong ứng dụng|Phân phối bản cập nhật hệ điều hành|Mã hóa cơ sở dữ liệu cục bộ
Khi cần quyền vị trí, lúc nào nên hỏi?|Khi người dùng mở tính năng cần vị trí|Ngay khi cài xong dù chưa dùng|Mỗi lần chuyển tab
Tình huống nào cần thử để kiểm tra khả năng khôi phục giao diện?|Hệ điều hành hủy tiến trình rồi mở lại|Đổi tên gói ứng dụng|Đổi nền IDE

game_programming|Game Developer / VR / AR|Unity,Unreal Engine,Godot,Blender,Three.js|game programming,virtual reality
Tham số nào giúp tốc độ di chuyển phụ thuộc thời gian thực thay vì FPS?|Delta time|Số thứ tự frame|Số đối tượng trong scene
Kỹ thuật nào giảm tạo và hủy liên tục các viên đạn?|Object pooling|Texture baking|Tăng độ phân giải
Chạy mô phỏng vật lý thường nên dùng bước thời gian nào?|Bước thời gian cố định|Bước phụ thuộc số vật thể thấy được|Chỉ mô phỏng khi người chơi bấm nút
Thuật toán tìm đường phổ biến trên lưới có heuristic là gì?|A*|QuickSort|Binary search
Để giảm khó chịu trong VR nên ưu tiên điều gì?|Khung hình ổn định và hạn chế gia tốc camera đột ngột|Quay camera nhanh khi người dùng đứng yên|Thay đổi FOV liên tục

machine_learning|AI / Machine Learning Engineer|PyTorch,TensorFlow,Scikit-learn,Pandas|artificial intelligence,machine learning
Để đánh giá cuối sau khi chốt mô hình, dùng dữ liệu nào?|Tập kiểm thử độc lập|Tập huấn luyện|Tập chọn siêu tham số
Fit bộ chuẩn hóa trên toàn bộ dữ liệu trước khi chia tạo rủi ro gì?|Rò rỉ dữ liệu|Mất nhãn phân loại|Giảm số đặc trưng
Dữ liệu có rất ít ca dương tính, chỉ số nào hữu ích để đọc đánh đổi precision và recall?|PR-AUC|Accuracy đơn lẻ|Thời gian train
Khi train tốt nhưng validation giảm, nghi ngờ gì trước?|Overfitting|Underflow của hệ điều hành|Thiếu số lớp ở tập nhãn
Để kiểm tra mô hình sau khi triển khai khi dữ liệu đổi, nên làm gì?|Theo dõi drift và hiệu năng trên mẫu có nhãn|Chỉ xem loss huấn luyện cũ|Chỉ xem dung lượng checkpoint

computer_vision|Computer Vision Engineer|OpenCV,YOLO,PyTorch,MediaPipe|computer vision,object detection
Bounding box đánh dấu gì?|Vị trí hình chữ nhật bao quanh đối tượng|Nhãn từng pixel|Tọa độ camera GPS
IoU của hai hộp đo gì?|Diện tích giao chia diện tích hợp|Khoảng cách giữa hai tâm|Sai số phân lớp trung bình
Khi lật ảnh huấn luyện detection, phải làm thêm gì?|Biến đổi tọa độ hộp tương ứng|Giữ tọa độ cũ|Tăng số lớp nhãn
Semantic segmentation đầu ra thường là gì?|Nhãn lớp theo pixel|Một nhãn cho cả ảnh|Một hộp duy nhất
Để tránh rò rỉ ở dữ liệu khung hình video, nên chia dữ liệu theo gì?|Video hoặc phiên ghi gốc|Khung hình ngẫu nhiên|Kích thước file

nlp|NLP Engineer|Hugging Face,spaCy,PyTorch,Scikit-learn|natural language processing,text classification
TF-IDF ưu tiên từ loại nào?|Từ hay gặp trong văn bản đó nhưng hiếm trên toàn tập|Từ xuất hiện ở mọi văn bản|Từ dài nhất
Tokenizer làm gì?|Tách văn bản thành các đơn vị token|Kiểm chứng dữ kiện|Dịch mọi văn bản sang tiếng Anh
Khi nhãn cảm xúc mất cân bằng, nên xem thêm chỉ số nào?|Macro F1|Chỉ accuracy|Số lượng token trung bình
Named Entity Recognition tìm gì?|Thực thể như tên người, địa danh, tổ chức|Ngôn ngữ của cả tài liệu|Câu dài nhất
Khi thử tokenizer mới, điều gì phải khớp để dùng checkpoint cũ?|Từ vựng và ánh xạ token ID|Font giao diện|Chiều dài tên file

llm|GenAI / AI Agent Engineer|LangChain,LlamaIndex,Transformers,Vector DB|large language model,AI agent,RAG
RAG đưa dữ liệu mới vào câu trả lời theo cách nào?|Truy xuất đoạn liên quan rồi đưa vào ngữ cảnh|Huấn luyện lại mô hình cho từng câu|Đổi nhiệt độ sampling
Khi agent có công cụ thay đổi dữ liệu, kiểm tra nào giảm thao tác ngoài quyền?|Kiểm tra quyền và tham số ở ranh giới công cụ|Tăng context window|Đổi tên công cụ
Đo chất lượng bộ truy xuất có thể dùng chỉ số nào?|Recall@k trên tập có nguồn chuẩn|Số chữ trong prompt|Nhiệt độ sinh văn bản
Nếu tài liệu tìm thấy chứa chỉ dẫn giả cho agent, nên xử lý ra sao?|Xem nội dung tài liệu là dữ liệu không đáng tin|Cho tài liệu quyền cao hơn luật hệ thống|Cho phép thi hành mọi tool call trong tài liệu
Khi yêu cầu chỉ hỏi về nguồn hiện có mà thiếu bằng chứng, phản hồi phù hợp là gì?|Nêu thiếu nguồn và phạm vi biết được|Bịa trích dẫn gần chủ đề|Chấp nhận câu trả lời vì viết trôi chảy

data_analyst|Data Analyst / BI|SQL,Excel,Power BI,Tableau,Pandas|data analysis,business intelligence
Khi JOIN làm tổng doanh thu tăng bất thường, cần kiểm tra gì?|Số bản ghi khớp mỗi khóa|Cỡ chữ bảng|Kiểu sắp xếp cột
Muốn hiển thị xu hướng doanh thu theo tháng, dạng biểu đồ nào hữu ích?|Biểu đồ đường|Biểu đồ tròn từng bản ghi|Word cloud
Chỉ số tỷ lệ chuyển đổi cần mô tả gì?|Tử số, mẫu số và khoảng thời gian|Chỉ tổng lượt truy cập|Chỉ doanh thu
Trước khi xử lý giá trị thiếu, nên làm gì?|Kiểm tra mẫu thiếu và tác động|Thay toàn bộ bằng 0|Xóa mọi dòng ngay
Để so sánh hai kỳ có số ngày khác nhau, có thể dùng gì?|Chỉ số chuẩn hóa theo ngày hoặc cửa sổ tương đương|Cộng hai tổng vào nhau|Đổi màu biểu đồ

data_science|Data Scientist / FinTech|Python,Pandas,Scikit-learn,R,Statsmodels|data science,financial technology
Với dữ liệu chuỗi thời gian, cách chia nào tránh nhìn trước tương lai?|Train trên quá khứ, test trên tương lai|Trộn ngẫu nhiên toàn bộ thời điểm|Chọn test bằng lỗi train nhỏ nhất
Trong A/B test, ngẫu nhiên hóa giúp gì?|Giảm sai lệch do khác biệt nền giữa nhóm|Bảo đảm kết quả có ý nghĩa|Loại bỏ luôn dữ liệu lỗi
Khoảng tin cậy rộng thường phản ánh gì?|Ước lượng thiếu chính xác|Kết quả chắc chắn không có hiệu ứng|Mô hình luôn sai
Để giảm tác động của ngoại lệ khi tóm tắt trung tâm, chọn gì?|Trung vị|Trung bình cộng bắt buộc|Giá trị cực đại
Khi đánh giá mô hình phát hiện gian lận, chi phí nào quan trọng?|Chi phí bỏ sót và chặn nhầm giao dịch|Chỉ số dòng SQL|Chỉ số chiều rộng mô hình

data_engineer|Data Engineer / Big Data|Airflow,dbt,Spark,Kafka,BigQuery|data engineering,big data
Pipeline nhận lại cùng một sự kiện nên làm gì?|Ghi idempotent hoặc khử trùng theo ID|Nhân đôi bản ghi|Xóa toàn bộ partition
Partition theo ngày thường giúp gì?|Chỉ đọc các vùng dữ liệu liên quan|Mã hóa nội dung|Bảo đảm không có giá trị null
Schema evolution nên xử lý ra sao?|Kiểm tra tương thích với consumer trước khi đổi|Đổi mọi kiểu cột cùng lúc|Chỉ sửa tên dashboard
Data lineage mô tả gì?|Nguồn, biến đổi và đích của dữ liệu|Quyền đăng nhập Chrome|Tần suất commit dự án
Hệ thống realtime cần phân biệt thời gian nào?|Thời điểm sự kiện và thời điểm xử lý|Thời gian build và chiều dài query|Phiên bản DB và giờ địa phương

business_analyst|Business Analyst (BA)|BPMN,Jira,SQL,Figma|business analysis,information systems
Khi hai nhóm mô tả quy trình khác nhau, BA nên bắt đầu bằng gì?|Đối chiếu luồng hiện tại và xác nhận với các bên|Chọn ngay ý kiến mới nhất|Thiết kế giao diện trước
Acceptance criteria tốt cần đặc điểm nào?|Quan sát và kiểm thử được|Chỉ nêu mục tiêu mơ hồ|Chỉ liệt kê tên stakeholder
BPMN gateway biểu diễn gì?|Điểm rẽ hoặc hợp luồng|Tên cơ sở dữ liệu|Giao diện API
Khi nghiệp vụ thay đổi, công cụ nào giúp biết yêu cầu và test bị ảnh hưởng?|Ma trận truy vết yêu cầu|Bảng màu thương hiệu|Danh sách email lịch sử
Phỏng vấn để tìm nguyên nhân nên tránh cách hỏi nào?|Câu hỏi dẫn dắt người trả lời tới đáp án|Yêu cầu ví dụ thực tế|Hỏi bước nào tạo trở ngại

project_manager|Project Manager (PM)|Jira,Trello,Excel,MS Project|project management,software engineering
Đường găng trong lịch dự án biểu diễn gì?|Chuỗi phụ thuộc quyết định thời lượng tối thiểu|Tất cả việc có cùng người làm|Danh sách việc đã xong
Risk register nên có gì?|Rủi ro, mức ảnh hưởng, người phụ trách và cách ứng phó|Chỉ tên dự án|Chỉ các lỗi đã sửa
Khi phạm vi tăng, nên làm gì trước khi cam kết ngày mới?|Đánh giá tác động và thống nhất thay đổi|Thêm việc vào sprint không báo|Bỏ các bước kiểm thử mặc định
Nếu dự án phụ thuộc API nhà cung cấp, cần theo dõi gì?|Mốc, người phụ trách và phương án dự phòng|Chỉ màu dashboard|Chỉ số lượng cuộc họp
Đo tiến độ nên dùng dấu hiệu nào?|Đầu ra đã được nghiệm thu theo mốc|Số giờ họp|Số tin nhắn nhóm

product_owner|Product Owner (PO)|Jira,Product analytics,Figma,Miro|product ownership,product management
Product backlog nên ưu tiên theo gì?|Giá trị, rủi ro, bằng chứng và mục tiêu sản phẩm|Thứ tự người gửi gần nhất|Tên tính năng theo alphabet
Khi chưa rõ nhu cầu của người dùng, bước hợp lý là gì?|Kiểm chứng giả thuyết với mẫu người dùng phù hợp|Cam kết phát hành ngay|Tăng số lượng tính năng
Chỉ số nào phù hợp hơn để đo giảm khó khăn khi đăng ký?|Tỷ lệ hoàn thành đăng ký|Số màu giao diện|Số dòng CSS
MVP giúp làm gì?|Kiểm chứng giả thuyết trọng yếu với phạm vi nhỏ|Triển khai đủ mọi yêu cầu|Bỏ mọi cách đo kết quả
Hai yêu cầu cùng ưu tiên cao, nên ra quyết định dựa vào gì?|Đánh đổi gắn với mục tiêu và giá trị kỳ vọng|Chọn cái có tên ngắn hơn|Đưa cả hai vào sprint bất kể nguồn lực

ui_ux_design|UI/UX Designer|Figma,FigJam,Prototype,Usability Testing|user experience design,human computer interaction
Usability test nên giao nhiệm vụ thế nào?|Mô tả mục tiêu để người dùng tự tìm cách|Chỉ chính xác từng nút phải bấm|Đọc lại tên các trang
Để người mù màu hiểu lỗi, nên dùng gì?|Văn bản rõ cùng trạng thái trực quan|Chỉ đỏ và xanh|Chỉ hiệu ứng rung
Prototype độ trung thực thấp phù hợp để thử gì sớm?|Cấu trúc và luồng thao tác|Màu cuối cùng theo chuẩn in|Hiệu năng truy vấn SQL
Khi biểu mẫu lỗi, thông báo nên đặt ở đâu?|Gần trường lỗi và có hướng dẫn sửa|Chỉ trong console|Trong trang điều khoản
Để biết vì sao người dùng bỏ giữa chừng, nên kết hợp gì?|Dữ liệu funnel và quan sát định tính|Chỉ ảnh chụp giao diện|Chỉ số máy tính trong nhóm

software_testing|QA / Test Engineer|Playwright,Postman,Pytest,JMeter|software testing,software engineering
Với đầu vào hợp lệ 1–100, tập giá trị nào hữu ích cho kiểm thử biên?|0, 1, 100, 101|20, 25, 30, 35|2, 3, 4, 5
Kiểm thử hồi quy nhằm phát hiện gì?|Chức năng đã chạy bị hỏng sau thay đổi|Dự án có đủ thành viên|Màu không đúng sở thích
Để test API trả mã quyền sai, cần kiểm tra bằng phiên nào?|Phiên thiếu đúng quyền cần thiết|Chỉ phiên quản trị|Chỉ tài khoản của lập trình viên
Một bug report dễ tái hiện cần gì?|Bước làm, dữ liệu, kết quả kỳ vọng và thực tế|Chỉ ảnh báo lỗi|Chỉ tên module
Flaky test có đặc điểm gì?|Kết quả thay đổi dù code kiểm thử không đổi|Luôn thất bại với dữ liệu hợp lệ|Chỉ kiểm tra bằng tay

cloud_devops|Cloud / DevOps Engineer|Docker,Kubernetes,Terraform,GitHub Actions,AWS|cloud computing,devops
Secret môi trường nên lưu ở đâu?|Kho secret với quyền phù hợp|Repo Git công khai|Log build
Readiness probe phục vụ mục đích gì?|Xác định instance có thể nhận traffic|Đo chất lượng code|Đổi phiên bản database
Canary rollout là gì?|Cấp bản mới cho một phần traffic trước|Dừng toàn bộ bản cũ ngay|Mỗi người dùng chạy một commit tự chọn
Hạ tầng khai báo giúp giảm vấn đề gì?|Sai khác cấu hình và thao tác thủ công|Kích cỡ request|Số lỗi chính tả
Khi 5xx tăng ngay sau deploy, tín hiệu nào hữu ích nhất?|So sánh tỷ lệ lỗi giữa phiên bản và log tương ứng|Đếm commit trong năm|Đổi DNS ngay

cybersecurity|Cybersecurity Engineer|Wireshark,Burp Suite,OWASP ZAP,SIEM|cybersecurity,network security
Quyền tối thiểu có nghĩa là gì?|Chỉ cấp quyền cần cho công việc|Mọi người có quyền quản trị|Mỗi người chỉ được một mật khẩu
Cơ chế nào giảm nguy cơ injection khi đưa đầu vào tới SQL?|Truy vấn tham số hóa|Ẩn ô nhập|Mã hóa base64 đầu vào
Để lưu mật khẩu đăng nhập, nên dùng gì?|Hàm băm mật khẩu có salt và chi phí tính toán|Mã hóa base64|SHA-256 trực tiếp không salt
Khi phát hiện token bị lộ, ưu tiên gì?|Thu hồi hoặc xoay token và kiểm tra truy cập|Chỉ xóa tin nhắn chứa token|Đổi màu trang cài đặt
Xác thực đa yếu tố mạnh hơn khi dùng gì?|Hai yếu tố độc lập|Hai mật khẩu lưu cùng chỗ|Hai lần nhập cùng PIN

internet_of_things|IoT / Embedded Engineer|ESP32,Arduino,Raspberry Pi,STM32,MQTT|internet of things,embedded systems
MQTT trao đổi bản tin thường theo mô hình nào?|Publish/subscribe qua broker|Client truy cập bảng SQL trực tiếp|FTP point-to-point
Deep sleep trên vi điều khiển nhằm mục đích gì?|Giảm điện năng khi không xử lý|Tăng tốc lấy mẫu|Lưu firmware lên cloud
Khi cảm biến nhiễu ngẫu nhiên, có thể áp dụng gì?|Bộ lọc trung bình trượt|Tăng độ dài chuỗi ID|Đổi cổng mạng
Khi mất Wi-Fi, thiết bị cần làm gì để giữ số đo?|Lưu đệm và gửi lại có kiểm soát|Xóa số đo tại chỗ|Khởi động lại liên tục
Điều gì giúp kiểm tra firmware đúng trước cập nhật OTA?|Xác minh chữ ký firmware|Đặt tên tập tin ngắn|Dựa vào dung lượng gần giống

research_methods|Nghiên cứu / Thuật toán|Python,R,LaTeX,MATLAB|research methods,algorithm optimization
Baseline dùng để làm gì trong nghiên cứu?|Tạo mốc đối chiếu trên cùng điều kiện|Thay cho mô tả dữ liệu|Chọn kết quả đẹp nhất
Ablation study giúp kiểm tra gì?|Đóng góp của từng thành phần khi bỏ hoặc thay riêng|Lỗi chính tả trong bài báo|Số màn hình của ứng dụng
So sánh thuật toán công bằng cần gì?|Cùng đầu vào, chỉ số và ràng buộc phù hợp|Chọn dữ liệu khác mà không ghi|Chỉ báo thời gian trên một máy
Để người khác tái lập, nên công bố hoặc ghi lại gì?|Dữ liệu, cấu hình, mã và seed trong phạm vi được phép|Chỉ tiêu đề bài báo|Chỉ ảnh chart
Với tìm kiếm nhị phân trên mảng đã sắp xếp, thời gian điển hình là gì?|O(log n)|O(n²)|O(n log n)

blockchain|Blockchain Developer|Solidity,Ethereum,Hardhat,Foundry|blockchain,smart contracts
Smart contract thường lưu trạng thái ở đâu sau giao dịch xác nhận?|Trên blockchain theo đồng thuận|Chỉ trong RAM trình duyệt|Trong cache CSS
Gas phản ánh gì?|Chi phí tài nguyên thực thi|Số tài khoản đăng nhập|Kích cỡ ảnh
Checks-effects-interactions giúp giảm nguy cơ nào?|Reentrancy|Overfitting|SQL deadlock
Testnet dùng để làm gì?|Thử giao dịch và hợp đồng trong mạng thử|Cất private key bí mật|Thay thế audit bảo mật
Khi quản trị contract có tác vụ quan trọng, lựa chọn nào giảm rủi ro một khóa bị lộ?|Ví đa chữ ký và quyền hạn rõ|Dùng một khóa chia sẻ công khai|Đặt khóa trong mã frontend
"""


def parse_bank():
    tracks = {}
    for block in BANK.strip().split('\n\n'):
        header, *questions = block.splitlines()
        key, label, tools, keywords = header.split('|')
        rows = []
        for question in questions:
            prompt, correct, *wrong = question.split('|')
            position = sha256(prompt.encode()).digest()[0] % 3
            wrong.insert(position, correct)
            rows.append((prompt, wrong, position))
        tracks[key] = {'label': label, 'tools': tools.split(','), 'keywords': keywords.split(','), 'questions': rows}
    return tracks


TRACKS = parse_bank()
