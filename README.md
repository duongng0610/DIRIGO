# TÁI HIỆN THỰC NGHIỆM DIRIGO VÀ ĐỀ XUẤT TỰ ĐỘNG HÓA PIPELINE DIRIGO-INVENTORY

> Trạng thái tài liệu: bản mô tả dự án và khung báo cáo thực nghiệm có thể tiếp tục cập nhật khi hoàn thành benchmark thời gian.

## 1. Tóm tắt dự án

Dự án gồm hai phần liên tiếp:

1. **Tái hiện thực nghiệm của Dirigo** trên dữ liệu mô phỏng quy trình lấy hàng tại cảng, bao gồm kiểm tra dữ liệu nguồn, tái tạo ACEL/DOCEL từ schema Dirigo, tạo lại cơ sở dữ liệu SQLite và đánh giá các schema theo các tiêu chí chất lượng QC1-QC4.
2. **Mở rộng Dirigo thành pipeline trích xuất có cấu hình**, trong đó hệ thống lập hồ sơ SQLite, dùng LLM đề xuất mapping, kiểm tra và publish YAML, tạo Intermediate Representation (IR), xuất các bảng Dirigo CSV rồi chạy OUT-QC và QC2a-QC4b.

Phần mở rộng không thay đổi phương pháp phân tích nghiệp vụ năm bước của Dirigo. Mục tiêu là bổ sung lớp công cụ để biến kết quả phân tích nghiệp vụ thành một pipeline có thể cấu hình, chạy lại và kiểm thử.

---

## 2. Cơ sở nghiên cứu: phương pháp Dirigo

Dirigo là phương pháp trích xuất event log cho quy trình hướng đối tượng. Phương pháp được thiết kế theo ba nguyên tắc:

- **Conceptualisation principle**: mô hình hóa ở mức khái niệm, độc lập với hệ quản trị dữ liệu và công cụ cụ thể.
- **100% principle**: thu thập đầy đủ thông tin cần thiết để sinh OCEL.
- **Generic principle**: có khả năng áp dụng cho nhiều miền nghiệp vụ.

Dirigo thực hiện phân tích theo năm bước:

| Bước | Nội dung | Sản phẩm đầu ra |
|---|---|---|
| 1 | Xác định mục tiêu nghiệp vụ | Phạm vi và câu hỏi phân tích |
| 2 | Xác định các hoạt động | Danh sách event type/activity |
| 3 | Xác định object và thuộc tính | Object type, thuộc tính tĩnh và động |
| 4 | Xác định quan hệ Event-to-Object | E2O và qualifier |
| 5 | Xác định quan hệ Object-to-Object | O2O tĩnh/động và qualifier |

### 2.1. Các tiêu chí chất lượng

| Mã | Tiêu chí |
|---|---|
| QC1 | Các bảng quan hệ tuân thủ tối thiểu chuẩn 3NF |
| QC2.a | Không mất thuộc tính tĩnh của object |
| QC2.b | Không mất thuộc tính động của object |
| QC2.c | Không mất thuộc tính event |
| QC3.a | Không mất quan hệ O2O tĩnh |
| QC3.b | Không mất quan hệ O2O động |
| QC3.c | Không mất quan hệ E2O |
| QC4.a | Không mất qualifier của O2O |
| QC4.b | Không mất qualifier của E2O |

### 2.2. Giới hạn của nghiên cứu làm cơ sở cho phần mở rộng

Bài báo đã cung cấp **way of working** và **way of modelling**, nhưng để lại các khoảng trống sau:

1. Chưa cung cấp cách tự động tạo object-centric log ở instance level từ dữ liệu nguồn.
2. Phần **way of supporting**, tức công cụ hỗ trợ thực thi phương pháp, nằm ngoài phạm vi nghiên cứu.
3. Việc lựa chọn bảng, join, khóa định danh, event, object, E2O, O2O và qualifier vẫn cần thực hiện thủ công.
4. Mã thực nghiệm phụ thuộc vào đường dẫn, notebook và cấu trúc dữ liệu cụ thể của use case.
5. Chưa có lớp cấu hình trung gian để tái sử dụng phương pháp cho một dataset mới.
6. Future work của bài báo tập trung vào object-centric process analytics, nhưng trước khi phân tích cần có một pipeline trích xuất đáng tin cậy, có thể kiểm tra và chạy lại.

Từ đó, phần mở rộng của dự án đặt câu hỏi:

> Có thể chuyển kết quả phân tích năm bước của Dirigo thành cấu hình máy đọc được, từ đó tự động sinh log Dirigo CSV cho một cơ sở dữ liệu SQLite mới hay không?

OCEL 2.0 exporter là hướng mở rộng tiếp theo; source hiện tại chưa xuất trực tiếp OCEL 2.0 JSON/XML.

---

## 3. Phần I - Tái hiện thực nghiệm Dirigo

### 3.1. Mục tiêu

- Thiết lập lại môi trường của repository `Dirigo_OCEL`.
- Kiểm tra dữ liệu đầu vào.
- Chạy lại phép chuyển đổi Dirigo sang DOCEL và ACEL.
- Tạo lại ba cơ sở dữ liệu SQLite.
- Kiểm tra QC2.a-QC4.b trên Dirigo, ACEL và DOCEL.
- Chạy benchmark thời gian trong `Database_Queries` và báo cáo trung bình, độ lệch chuẩn.

### 3.2. Quy trình tái hiện

```mermaid
flowchart TD
    A[Thiết lập môi trường] --> B[Kiểm tra dữ liệu đầu vào]
    B --> C[Tái tạo DOCEL và ACEL]
    C --> D[Tạo lại ba SQLite]
    D --> E[Chạy truy vấn QC]
    E --> F[Chạy benchmark thời gian]
    F --> G[Tổng hợp và đối chiếu kết quả]
```

### 3.3. Môi trường chạy

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Các notebook trong `Database_Processing` cần dùng một biến `ROOT` thống nhất thay vì đường dẫn tuyệt đối:

```python
from pathlib import Path

ROOT = Path.cwd().resolve()
```

Ví dụ đọc file:

```python
events = pd.read_csv(ROOT / "Dirigo" / "OCEL_Events.csv")
```

### 3.4. Kiểm tra dữ liệu đầu vào

| Bảng/file | Số bản ghi quan sát được |
|---|---:|
| `OCEL_Events` | 1.500 |
| `OCEL_E2O` | 1.600 |
| `OCEL_O2O` | 500 |
| `OCEL_Truck` | 1.450 |
| `OCEL_Cargo` | 120 |
| `OCEL_PickupPlan` | 100 |

Các số lượng này được dùng làm mốc kiểm tra cho các notebook chuyển đổi và truy vấn QC.

### 3.5. Kết quả tái tạo schema

| Thực nghiệm | Kết quả | Kết luận |
|---|---|---|
| Dirigo -> DOCEL | Các file tái tạo khớp baseline về danh sách file, cột, số dòng và nội dung; 12/12 file PASS | Tái tạo thành công |
| Dirigo -> ACEL | Các file tái tạo khớp baseline; 3/3 file PASS | Tái tạo thành công |
| CSV -> SQLite | Tạo được ba database tương ứng Dirigo, ACEL và DOCEL | Thành công về mặt sinh file; cần bổ sung kiểm tra toàn vẹn |

Phép so sánh baseline sử dụng `dtype=str` và `keep_default_na=False` để tránh khác biệt giả do suy luận kiểu dữ liệu hoặc cách biểu diễn giá trị rỗng.

### 3.6. Kết quả QC quan sát được

| Tiêu chí | Dirigo | ACEL | DOCEL | Ghi chú |
|---|:---:|:---:|:---:|---|
| QC1 | Chưa đo bằng test | Chưa đo bằng test | Chưa đo bằng test | Báo cáo mới nêu đánh giá cấu trúc; cần kiểm tra 3NF có hệ thống |
| QC2.a | PASS | PASS | PASS | Thuộc tính tĩnh Truck/Cargo đầy đủ |
| QC2.b | PASS | FAIL | FAIL | ACEL và DOCEL thiếu lịch sử của một số thuộc tính động |
| QC2.c | PASS | PASS | PASS | Đủ `event_id`, `activity`, `timestamp` cho 1.500 event |
| QC3.a | PASS | PASS | PASS | Quan sát được 100 liên kết O2O tĩnh |
| QC3.b | PASS | PASS | **FAIL** | Dirigo/ACEL có 400 bản ghi lịch sử; DOCEL chỉ có 200 và thiếu thao tác `Drop` |
| QC3.c | PASS | PASS | PASS | Quan sát được 1.600 cặp Event-Object |
| QC4.a | PASS | PASS | FAIL | DOCEL không lưu qualifier O2O |
| QC4.b | PASS | PASS | FAIL trong bản tái hiện | DOCEL không có qualifier E2O trong dữ liệu tái tạo |

### 3.7. Phát hiện quan trọng khi tái hiện

#### QC3.b của DOCEL

Bảng tổng kết cuối báo cáo đánh dấu DOCEL đạt QC3.b, nhưng phần phân tích chi tiết cho thấy:

- Kỳ vọng: 400 bản ghi lịch sử của quan hệ động.
- Quan sát: 200 bản ghi.
- Tất cả bản ghi là `Assign For Truck`.
- Không có thao tác `Drop`.

Vì vậy kết luận nhất quán với bằng chứng phải là **DOCEL FAIL QC3.b**.

#### QC4.b của DOCEL

Kết quả tái hiện cho thấy DOCEL không chứa qualifier E2O và được tính là 0%, trong khi bảng đánh giá của bài báo gốc đánh dấu DOCEL đạt QC4.b. Đây là sai khác cần được trình bày như một phát hiện tái hiện, không nên tự động sửa kết quả để khớp bài báo.

### 3.8. Những phần thực nghiệm chưa hoàn tất

1. **Benchmark thời gian chưa có kết quả số**: chưa báo cáo `mean`, `standard deviation`, số vòng lặp và cấu hình máy.
2. **QC1 chưa có test tái lập**: chưa có kiểm tra functional dependency, khóa và vi phạm chuẩn hóa.
3. **Chưa kiểm tra toàn vẹn sau CSV -> SQLite**: cần kiểm tra số dòng, khóa chính, khóa ngoại, duplicate và null bắt buộc.
4. **Chưa đo kích thước lưu trữ**: cần so sánh dung lượng ACEL, DOCEL và Dirigo.
5. **Chưa có round-trip test**: CSV -> SQLite -> DataFrame phải bảo toàn dữ liệu.
6. **Chưa ghi rõ phiên bản thư viện và cấu hình phần cứng**.

### 3.9. Các điểm cần sửa trong phương pháp kiểm tra

- Không loại giá trị `0` khi kiểm tra thuộc tính động; `0` có thể là giá trị nghiệp vụ hợp lệ.
- Không nên kết luận quan hệ tĩnh chỉ vì cặp object xuất hiện tại một timestamp. Cần xét semantic của qualifier và toàn bộ lifecycle.
- QC2.c không chỉ là ba trường bắt buộc. Cần kiểm tra cả các event attribute được xác định ở bước phân tích miền.
- Cần phân biệt **số relation duy nhất** và **số bản ghi lịch sử của relation**.
- Mọi tiêu chí phải chỉ rõ công thức, tập kỳ vọng, tập quan sát và điều kiện PASS/FAIL.

### 3.10. Kế hoạch chạy benchmark cuối

Các notebook processing-time cần chạy đủ 20 tập kết quả:

| Tiêu chí | Số schema được đo | Số kết quả `mean/std` |
|---|---:|---:|
| QC2.a | Dirigo, ACEL, DOCEL | 3 |
| QC2.b | Dirigo | 1 |
| QC2.c | Dirigo, ACEL, DOCEL | 3 |
| QC3.a | Dirigo, ACEL, DOCEL | 3 |
| QC3.b | Dirigo, ACEL, DOCEL | 3 |
| QC3.c | Dirigo, ACEL, DOCEL | 3 |
| QC4.a | Dirigo, ACEL | 2 |
| QC4.b | Dirigo, ACEL | 2 |
| **Tổng** |  | **20** |

Mỗi truy vấn cần ghi:

```text
schema, criterion, repetitions, mean_ms, std_ms,
min_ms, median_ms, max_ms, machine, Python version
```

---

## 4. Cấu trúc source và cách chạy thực nghiệm

```text
Dirigo/
├── README.md
├── dirigo_reproduction/       # Notebook và dữ liệu tái hiện bài báo
└── dirigo_pipeline/           # Pipeline mở rộng cho SQLite mới
```

Hai phần dùng môi trường Python và dependency riêng. Không chạy notebook tái hiện từ `dirigo_pipeline` và không dùng virtual environment của phần này thay cho phần kia.

### 4.1. Chạy phần tái hiện

#### Thiết lập môi trường

```powershell
cd <DIRIGO_PROJECT_ROOT>\dirigo_reproduction
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m jupyter lab
```

Phải mở Jupyter từ `dirigo_reproduction/` để các đường dẫn tương đối tới `Dirigo/`, `ACEL/`, `DOCEL/` và `Databases_Queries/` được tính đúng.

#### Thứ tự thực thi bắt buộc

1. Kiểm tra sáu bảng nguồn trong `dirigo_reproduction/Dirigo/`.
2. Restart kernel và Run All `Database_Processing/Dirigo_DOCEL.ipynb`.
3. Restart kernel và Run All `Database_Processing/Dirigo_ACEL.ipynb`.
4. Run All `Database_Processing/CSVs_to_SQLites.ipynb`.
5. Chạy `EvaluationCriteria/QC2a.ipynb` đến `QC4b.ipynb` theo thứ tự.
6. Chạy các file `Databases_Queries/QC*.sql` để xác nhận kết quả.
7. Chỉ khi query đúng mới chạy `Databases_Queries/QC*_ProcessingTime.ipynb`.

SQLite bắt buộc sau bước 4:

```text
dirigo_reproduction/Databases_Queries/Dirigo.sqlite
dirigo_reproduction/Databases_Queries/ACEL.sqlite
dirigo_reproduction/Databases_Queries/DOCEL.sqlite
```

#### Baseline truy vấn

| QC | Kết quả tham chiếu |
|---|---|
| QC2a | `RICE` |
| QC2b | `120122.9` |
| QC2c | `2024-05-01 08:51:25` |
| QC3a | `2024-04-29 11:17:06` |
| QC3b | `Pcp16` |
| QC3c | `14439.9` |
| QC4a | Quan hệ assign/drop giữa truck `926VFT` và `Pcp18` |
| QC4b | `Truck being evaluated for exit` |

Không kết luận notebook thành công chỉ vì còn output cũ. Mỗi notebook phải được chạy lại từ kernel sạch và không còn traceback.

## 5. Chạy phần mở rộng `dirigo_pipeline`

Pipeline hiện nhận một file SQLite và thực hiện:

![Quy trình mở rộng Dirigo pipeline](docs/images/dirigo_pipeline_workflow.png)

### 5.1. Kiến trúc khớp với code hiện tại

1. `Source profiler` đọc schema, kiểu cột, candidate key, foreign key và sample rows.
2. Gemini đề xuất `mapping_proposal.json`.
3. MAP-QC kiểm tra proposal; LLM repair có số lần thử hữu hạn.
4. Chỉ proposal PASS mới được compile thành `mapping.yaml`.
5. Object, Event/E2O và O2O builders tạo các IR record.
6. Extractor xuất Dirigo CSV.
7. OUT-QC kiểm tra tính toàn vẹn của output.
8. Paper QC so sánh expected/actual projections cho QC2a-QC4b.

Giới hạn hiện tại:

- input chỉ hỗ trợ SQLite (`.sqlite`, `.sqlite3`, `.db`);
- chưa có CSV reader hoặc connector tới hệ quản trị CSDL khác;
- output hiện là Dirigo CSV, chưa phải OCEL 2.0 JSON/XML;
- builders tạo IR, do đó IR không phải một bước đứng trước builders;
- OUT-QC đọc CSV đã sinh nên export diễn ra trước OUT-QC.

### 5.2. Cài đặt pipeline

```powershell
cd <DIRIGO_PROJECT_ROOT>\dirigo_pipeline
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Điền hai biến trong `.env`:

```dotenv
GOOGLE_API_KEY=<your-google-api-key>
GOOGLE_LLM_MODEL=gemini-2.5-pro
```

Không commit `.env` hoặc API key. Nếu đồng thời có `GOOGLE_API_KEY` và `GEMINI_API_KEY`, SDK ưu tiên `GOOGLE_API_KEY`; nên chỉ giữ một biến để tránh nhầm cấu hình.

### 5.3. Chuẩn bị datasource

Đặt SQLite trực tiếp trong `dirigo_pipeline/data/raw/`, ví dụ:

```text
dirigo_pipeline/data/raw/inventory_management.db
```

Script chỉ nhận **tên file**, không nhận đường dẫn tuyệt đối:

```text
inventory_management.db
```

Tên file không có phần mở rộng (`inventory_management`) trở thành tên dataset dùng cho mapping, output và report.

### 5.4. Chạy toàn bộ pipeline

```powershell
python scripts/07_run_all_steps.py inventory_management.db `
  --domain-hint "Inventory management"
```

Script 07 dùng đúng `sys.executable`; vì vậy cần kích hoạt `.venv` trước. Pipeline dừng ngay khi một script con trả exit code khác 0.

### 5.5. Chạy từng bước

```powershell
# 1. Tạo source profile
python scripts/01_profile_source.py inventory_management.db

# 2. Gọi Gemini đề xuất mapping
python scripts/02_propose_mapping.py inventory_management.db `
  --domain-hint "Inventory management"

# 3. MAP-QC, repair tối đa hai lần và publish YAML khi PASS
python scripts/03_validate_publish_mapping.py inventory_management.db `
  --max-repairs 2

# 4. Build IR và xuất Dirigo CSV
python scripts/04_build_dirigo.py inventory_management.db

# 5. Kiểm tra toàn vẹn output
python scripts/05_validate_output.py inventory_management.db

# 6. Chạy Paper QC2a-QC4b
python scripts/06_run_paper_qc.py inventory_management.db
```

Bước 01 đã hoàn thành thì không cần chạy lại chỉ vì Gemini trả HTTP 503 ở bước 02. Có thể đợi và chạy lại riêng bước 02, sau đó tiếp tục từ bước 03.

### 5.6. Mapping, output và report

Với input `inventory_management.db`, kết quả được tách theo tên dataset:

```text
dirigo_pipeline/
├── configs/mappings/inventory_management/
│   └── mapping.yaml
├── outputs/inventory_management/
│   ├── OCEL_Events.csv
│   ├── OCEL_E2O.csv
│   ├── OCEL_O2O.csv
│   └── OCEL_<object_type>.csv
└── reports/steps/inventory_management/
    ├── source_profile.json
    ├── mapping_proposal.json
    ├── mapping_proposal_attempt_*.json
    ├── mapping_proposal_approved.json
    ├── map_qc_attempt_*.json
    ├── map_qc_report.json
    ├── output_qc_report.json
    └── paper_qc_report.json
```

Ý nghĩa trạng thái Paper QC:

- `PASS`: expected và actual khớp theo tiêu chí;
- `FAIL`: có phần tử thiếu hoặc thừa;
- `NOT_APPLICABLE`: mapping không chứa loại dữ liệu mà QC đánh giá, ví dụ không có O2O tĩnh cho QC3a.

## 6. Phạm vi kiểm chứng của các lớp QC

### MAP-QC

Kiểm tra cấu trúc mapping, bảng/cột, ID, resolver và các ràng buộc mà runtime hỗ trợ. Proposal chỉ được publish thành YAML khi MAP-QC PASS.

### OUT-QC

Kiểm tra output CSV: duplicate ID, timestamp không hợp lệ, E2O/O2O tham chiếu object hoặc event không tồn tại và các lỗi toàn vẹn khác.

### Paper QC

Paper QC tạo expected projection từ **source + mapping** và so với actual projection từ output. Nó chứng minh builder thực thi đúng mapping đã duyệt, nhưng không tự chứng minh mapping đã mô tả đầy đủ nghiệp vụ nguồn.

Nếu LLM bỏ hẳn một event hoặc relationship, expected và actual có thể cùng thiếu nên QC vẫn PASS. Vì vậy cần review thủ công:

1. object, event, E2O, O2O và qualifier;
2. các cặp lifecycle start/end hoặc assign/unassign;
3. source profile so với mapping đã publish;
4. warning và unresolved question của MAP-QC.

## 7. Xử lý lỗi thường gặp

### `ModuleNotFoundError: No module named 'src'`

Chạy entry point qua `python scripts/<script>.py ...`. Các script import `pipeline_paths` trước để thêm project root vào `sys.path`.

### `ModuleNotFoundError: No module named 'dotenv'`

Lệnh đang dùng sai interpreter hoặc dependency chưa được cài. Xác nhận:

```powershell
.\.venv\Scripts\Activate.ps1
python -c "import sys; print(sys.executable)"
python -m pip install -r requirements.txt
```

`sys.executable` phải trỏ tới `dirigo_pipeline\.venv\Scripts\python.exe`.

### Gemini trả `503 UNAVAILABLE`

Đây là lỗi tạm thời do model quá tải, không phải lỗi SQLite hoặc mapping. Đợi rồi chạy lại bước 02. `CalledProcessError` ở script 07 chỉ là lỗi bọc cho biết script con đã thất bại.

### MAP-QC không PASS

Đọc `reports/steps/<dataset>/map_qc_report.json` và `map_qc_attempt_*.json`. Script 03 không publish YAML nếu hết lượt repair mà report vẫn FAIL.

### Paper QC PASS nhưng thiếu nghiệp vụ

Đây có thể là lỗi semantic của mapping. Đối chiếu source profile, timestamp lifecycle và các quan hệ nghiệp vụ thay vì chỉ dựa vào expected/actual được sinh từ chính mapping đó.

---

## 8. Tài liệu tham khảo và nguồn dữ liệu

1. Wei, J. và cộng sự. *Dirigo: A Method to Extract Event Logs for Object-Centric Processes*. arXiv:2411.07490. <https://arxiv.org/abs/2411.07490>
2. Dirigo OCEL repository. <https://github.com/jennyVVei/Dirigo_OCEL>
3. OCEL 2.0 Specification. <https://www.ocel-standard.org/>
4. Inventory Management Database and OCELs. <https://www.ocel-standard.org/event-logs/simulations/invent_manag/>
5. Zenodo dataset DOI: <https://doi.org/10.5281/zenodo.21977737>
6. PM4Py documentation. <https://processintelligence.solutions/pm4py>

