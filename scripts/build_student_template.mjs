import fs from "node:fs/promises";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workDir = path.join(repoRoot, "outputs", "student-template");
const requireFromWorkDir = createRequire(path.join(workDir, "artifact-runner.cjs"));
const { SpreadsheetFile, Workbook } = requireFromWorkDir("@oai/artifact-tool");
const schemaPath = path.join(repoRoot, "configs", "student_survey_schema.json");
const dataPath = path.join(repoRoot, "data", "curated", "theses.json");
const outputPath = path.join(repoRoot, "assets", "student-skills-template.xlsx");
const previewDir = path.join(workDir, "previews");
await fs.mkdir(path.dirname(outputPath), { recursive: true });
await fs.mkdir(previewDir, { recursive: true });

const schema = JSON.parse(await fs.readFile(schemaPath, "utf8"));
const sourceBytes = await fs.readFile(dataPath);
const theses = JSON.parse(sourceBytes.toString("utf8"));
const sourceSha256 = crypto.createHash("sha256").update(sourceBytes).digest("hex");
if (schema.version !== "2.0" || schema.sheet !== "KhaoSat" || schema.header_mode !== "labels"
    || schema.header_row !== 1 || schema.columns.length !== 26) {
  throw new Error("Student survey schema must define KhaoSat v2 with 26 Vietnamese labels on row 1.");
}

const sourceSkillKeys = [
  "web_languages", "app_languages", "frontend_frameworks", "backend_frameworks",
  "ai_frameworks", "database_cache", "app_db_backend", "ai_problems", "data_tools",
  "data_models", "research_methods", "primary_role", "secondary_roles",
];
const sourceSkillColumns = sourceSkillKeys.map((key) => {
  const column = schema.columns.find((candidate) => candidate.key === key);
  if (!column) throw new Error(`Missing source matching field: ${key}`);
  return column;
});
const placeholders = new Set(["không rõ", "không có", "none", "unknown", "chưa xác định"]);
const piiValues = new Set(theses.flatMap((row) => [row.student_name, row.advisor_name])
  .filter(Boolean).map((value) => String(value).trim().toLocaleLowerCase("vi")));
const cleanValue = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
function isAllowedDictionaryValue(value) {
  const normalized = value.toLocaleLowerCase("vi");
  return value.length > 0 && !placeholders.has(normalized) && !piiValues.has(normalized)
    && !/^https?:\/\//i.test(value) && !/\.(pdf|docx?|xlsx?|csv)$/i.test(value);
}
const dictionaryByField = new Map();
for (const column of sourceSkillColumns) {
  const values = new Map();
  for (const thesis of theses) {
    const entries = Array.isArray(thesis[column.key]) ? thesis[column.key] : [thesis[column.key]];
    for (const entry of entries) {
      const value = cleanValue(entry);
      const normalized = value.toLocaleLowerCase("vi");
      if (isAllowedDictionaryValue(value) && !values.has(normalized)) values.set(normalized, value);
    }
  }
  dictionaryByField.set(column.key,
    [...values.values()].sort((a, b) => a.localeCompare(b, "vi", { sensitivity: "base" })));
}
const dictionaryRows = sourceSkillColumns.flatMap((column) =>
  dictionaryByField.get(column.key).map((value) => [column.key, column.label, value]));
if (!dictionaryRows.length) throw new Error("No curated matching values were found.");

const font = "Arial";
const c = {
  navy: "#17365D", blue: "#1F4E78", teal: "#0F6B78", purple: "#6554A4",
  green: "#548235", slate: "#5B6573", lightBlue: "#D9EAF7", paleBlue: "#F4F8FC",
  paleAmber: "#FFF8E7", paleGreen: "#F2F8EE", palePurple: "#F5F1FA",
  paleGray: "#F3F4F6", amber: "#F4B183", gray: "#E7E6E6", text: "#1F2937",
  muted: "#5B6573", border: "#C9D3DF", white: "#FFFFFF",
};
const workbook = Workbook.create();
const input = workbook.worksheets.add("KhaoSat");
const guide = workbook.worksheets.add("HuongDan");
const dictionary = workbook.worksheets.add("DanhMucSkill");

input.showGridLines = false;
input.tabColor = c.navy;
input.getRange("A1:Z1").values = [schema.columns.map((column) => column.label)];
for (const [range, fill] of [["A1:D1", c.navy], ["E1:Q1", c.teal], ["R1:S1", c.purple],
  ["T1:X1", c.green], ["Y1:Z1", c.slate]]) {
  input.getRange(range).format = {
    fill, font: { name: font, size: 10, bold: true, color: c.white },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
    borders: { preset: "all", style: "thin", color: c.white },
  };
}
input.getRange("A1:Z1").format.rowHeight = 54;
for (const [range, fill] of [["A2:D1001", c.paleBlue], ["E2:Q1001", c.paleAmber],
  ["R2:S1001", c.palePurple], ["T2:X1001", c.paleGreen], ["Y2:Z1001", c.paleGray]]) {
  input.getRange(range).format = {
    fill, font: { name: font, size: 10, color: c.text }, verticalAlignment: "center",
    wrapText: false, borders: { insideHorizontal: { style: "thin", color: "#EEF1F4" } },
    numberFormat: "@",
  };
}
input.getRange("A2:Z1001").format.rowHeight = 21;
input.getRange("A2:A1001").setNumberFormat("@");
for (const [range, width] of [["A:A", 16], ["B:B", 25], ["C:D", 19], ["E:Q", 23],
  ["R:S", 24], ["T:T", 27], ["U:U", 40], ["V:V", 32], ["W:X", 30],
  ["Y:Y", 34], ["Z:Z", 44]]) input.getRange(range).format.columnWidth = width;
input.freezePanes.freezeRows(1);
input.freezePanes.freezeColumns(2);

guide.showGridLines = false;
guide.tabColor = "#5B9BD5";
guide.mergeCells("A1:E1");
guide.getRange("A1").values = [["Hướng dẫn khảo sát năng lực sinh viên trước khóa luận"]];
guide.getRange("A1:E1").format = { font: { name: font, size: 15, bold: true, color: c.navy }, verticalAlignment: "center" };
guide.getRange("A1:E1").format.rowHeight = 30;
const instructions = [
  "Chỉ nhập tại sheet KhaoSat, bắt đầu từ dòng 2. Không đổi tên sheet hoặc hàng tiêu đề.",
  "Mã sinh viên và Họ và tên là bắt buộc. Tên đề tài và mô tả ở cuối bảng có thể để trống.",
  "Điền ít nhất một kỹ năng hoặc framework hiện có. Nhiều giá trị trong một ô ngăn cách bằng dấu chấm phẩy (;).",
  "Chỉ khai kỹ năng đã học hoặc đã dùng. Kỹ năng muốn học thêm phải điền riêng ở cột Kỹ năng muốn học thêm.",
  "Mức độ từng kỹ năng là tùy chọn, dùng dạng Python|2; React|1 và chỉ ghi cho kỹ năng đã khai.",
  "Dự án, phần việc và link sản phẩm là minh chứng hỗ trợ rà soát, không bắt buộc phải có.",
  `Vai trò chuyên môn và phương pháp nghiên cứu có thể để trống nếu chưa xác định. Tối đa ${schema.max_students} sinh viên.`,
];
guide.getRange("A3:A9").values = instructions.map((_, i) => [i + 1]);
guide.getRange("A3:A9").format = { fill: c.blue, font: { name: font, size: 10, bold: true, color: c.white }, horizontalAlignment: "center", verticalAlignment: "center" };
for (let row = 3; row <= 9; row += 1) guide.mergeCells(`B${row}:E${row}`);
guide.getRange("B3:E9").values = instructions.map((text) => [text]);
guide.getRange("B3:E9").format = { fill: c.paleBlue, font: { name: font, size: 10, color: c.text }, verticalAlignment: "center", wrapText: true };
guide.getRange("A3:E9").format.borders = { preset: "outside", style: "thin", color: c.border };
guide.getRange("A3:E9").format.rowHeight = 42;

guide.mergeCells("A11:E11");
guide.getRange("A11").values = [["Thang mức độ tự khai (tùy chọn, không phải điểm thi)"]];
guide.getRange("A11:E11").format = { fill: c.green, font: { name: font, size: 10, bold: true, color: c.white }, verticalAlignment: "center" };
const levelRows = Object.entries(schema.level_scale);
guide.getRange("A12:A14").values = levelRows.map(([level]) => [level]);
guide.getRange("A12:A14").format = { fill: c.paleGreen, font: { name: font, size: 10, bold: true, color: c.green }, horizontalAlignment: "center", verticalAlignment: "center" };
for (let row = 12; row <= 14; row += 1) guide.mergeCells(`B${row}:E${row}`);
guide.getRange("B12:E14").values = levelRows.map(([, meaning]) => [meaning]);
guide.getRange("B12:E14").format = { fill: c.paleGreen, font: { name: font, size: 10, color: c.text }, verticalAlignment: "center" };

guide.mergeCells("A16:E16");
guide.getRange("A16").values = [["Bảng dưới giải thích 26 câu khảo sát. Ví dụ chỉ hướng dẫn cách nhập; hệ thống chỉ import sheet KhaoSat."]];
guide.getRange("A16:E16").format = { fill: c.amber, font: { name: font, size: 10, bold: true, color: "#7F3F00" }, verticalAlignment: "center", wrapText: true };
guide.getRange("A17:E17").values = [["Khóa dữ liệu", "Câu hỏi trong khảo sát", "Bắt buộc", "Cách nhập", "Mục đích / ví dụ"]];
guide.getRange("A17:E17").format = { fill: c.navy, font: { name: font, size: 10, bold: true, color: c.white }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true, borders: { preset: "all", style: "thin", color: c.white } };
const fieldGuidance = {
  student_id: ["Văn bản", "Giữ số 0 đầu, ví dụ 20260001"], student_name: ["Văn bản", "Họ tên đầy đủ"],
  class_name: ["Văn bản", "Ví dụ D22CQCN01-N"], major: ["Văn bản", "Ví dụ Công nghệ thông tin"],
  web_languages: ["Danh sách, cách nhau bằng ;", "Đã học/dùng, ví dụ JavaScript; HTML; CSS"],
  app_languages: ["Danh sách, cách nhau bằng ;", "Đã học/dùng, ví dụ Python; Java; C#"],
  frontend_frameworks: ["Danh sách, cách nhau bằng ;", "Đã học/dùng, ví dụ React; Vue.js"],
  backend_frameworks: ["Danh sách, cách nhau bằng ;", "Đã học/dùng, ví dụ FastAPI; Spring Boot"],
  ai_frameworks: ["Danh sách, cách nhau bằng ;", "Đã học/dùng, ví dụ PyTorch; scikit-learn"],
  database_cache: ["Danh sách, cách nhau bằng ;", "Đã học/dùng, ví dụ PostgreSQL; Redis"],
  app_db_backend: ["Danh sách, cách nhau bằng ;", "Đã học/dùng, ví dụ Firebase; Supabase"],
  ai_problems: ["Danh sách, cách nhau bằng ;", "Bài toán đã làm, ví dụ Phân loại hình ảnh"],
  data_tools: ["Danh sách, cách nhau bằng ;", "Công cụ đã dùng, ví dụ Pandas; NumPy"],
  data_models: ["Danh sách, cách nhau bằng ;", "Mô hình đã học/dùng, ví dụ CNN; Random Forest"],
  research_methods: ["Danh sách, cách nhau bằng ;", "Tùy chọn; để trống nếu chưa rõ"],
  primary_role: ["Văn bản", "Tùy chọn; vai trò tự tin nhất nếu đã xác định"],
  secondary_roles: ["Danh sách, cách nhau bằng ;", "Tùy chọn; vai trò khác nếu đã xác định"],
  mobile_frameworks: ["Danh sách, cách nhau bằng ;", "Đã dùng, ví dụ Flutter; React Native"],
  dev_tools: ["Danh sách, cách nhau bằng ;", "Đã dùng, ví dụ Git; Docker; Postman"],
  skill_levels: ["Kỹ năng|mức độ, cách nhau bằng ;", "Tùy chọn, ví dụ Python|2; React|1"],
  project_experience: ["Văn bản ngắn", "Dự án, vai trò và phần việc trực tiếp làm"],
  project_links: ["Một hoặc nhiều URL", "Link GitHub/demo nếu có"],
  preferred_fields: ["Danh sách, cách nhau bằng ;", "Mong muốn, không xem là kỹ năng đã có"],
  learning_goals: ["Danh sách, cách nhau bằng ;", "Muốn học thêm, không xem là kỹ năng đã có"],
  thesis_title: ["Văn bản", "Chưa có đề tài thì để trống"], abstract: ["Văn bản", "Chưa có mô tả thì để trống"],
};
const guideRows = schema.columns.map((column) => [column.key, column.label, column.required ? "Có" : "Không", ...fieldGuidance[column.key]]);
guide.getRange(`A18:E${17 + guideRows.length}`).values = guideRows;
guide.getRange(`A18:E${17 + guideRows.length}`).format = { font: { name: font, size: 9, color: c.text }, verticalAlignment: "top", wrapText: true, borders: { preset: "all", style: "thin", color: c.border } };
guide.getRange(`C18:C${17 + guideRows.length}`).format.horizontalAlignment = "center";
for (const [range, width] of [["A:A", 24], ["B:B", 32], ["C:C", 12], ["D:D", 32], ["E:E", 48]]) guide.getRange(range).format.columnWidth = width;
guide.freezePanes.freezeRows(17);

dictionary.showGridLines = false;
dictionary.tabColor = "#A5A5A5";
dictionary.mergeCells("A1:C1");
dictionary.getRange("A1").values = [["Danh mục tham khảo từ dữ liệu khóa luận hiện hành"]];
dictionary.getRange("A1:C1").format = { font: { name: font, size: 14, bold: true, color: c.navy }, verticalAlignment: "center" };
dictionary.mergeCells("A3:C3");
dictionary.getRange("A3").values = [[`Nguồn: ${theses.length} khóa luận đã có. ${dictionaryRows.length} giá trị dưới đây được trích từ đề tài cũ; sinh viên hiện tại chỉ chọn kỹ năng mình thực sự đã học hoặc đã dùng.`]];
dictionary.getRange("A3:C3").format = { fill: c.gray, font: { name: font, size: 9, italic: true, color: c.muted }, verticalAlignment: "center", wrapText: true };
dictionary.mergeCells("A4:C4");
dictionary.getRange("A4").values = [["Gợi ý bổ sung ngoài dữ liệu nguồn: mobile_frameworks (Flutter; React Native) và dev_tools (Git; Docker; Postman). Đây chỉ là ví dụ khảo sát, không phải giá trị trích từ 215 khóa luận."]];
dictionary.getRange("A4:C4").format = { fill: c.palePurple, font: { name: font, size: 9, italic: true, color: c.purple }, verticalAlignment: "center", wrapText: true };
dictionary.getRange("A6:C6").values = [["Nhóm dữ liệu", "Tên hiển thị", "Giá trị tham khảo từ dữ liệu cũ"]];
dictionary.getRange("A6:C6").format = { fill: c.navy, font: { name: font, size: 10, bold: true, color: c.white }, horizontalAlignment: "center", verticalAlignment: "center", borders: { preset: "all", style: "thin", color: c.white } };
dictionary.getRange(`A7:C${6 + dictionaryRows.length}`).values = dictionaryRows;
dictionary.getRange(`A7:C${6 + dictionaryRows.length}`).format = { font: { name: font, size: 9, color: c.text }, verticalAlignment: "top", wrapText: true, borders: { preset: "all", style: "thin", color: c.border } };
for (const [range, width] of [["A:A", 24], ["B:B", 34], ["C:C", 66]]) dictionary.getRange(range).format.columnWidth = width;
dictionary.freezePanes.freezeRows(6);
dictionary.tables.add(`A6:C${6 + dictionaryRows.length}`, true, "SkillDictionaryTable");

workbook.recalculate();
const inspections = {
  input: (await workbook.inspect({ kind: "table", range: "KhaoSat!A1:Z4", include: "values,formulas", tableMaxRows: 4, tableMaxCols: 26, maxChars: 9000 })).ndjson,
  guide: (await workbook.inspect({ kind: "table", range: "HuongDan!A1:E43", include: "values,formulas", tableMaxRows: 43, tableMaxCols: 5, maxChars: 14000 })).ndjson,
  dictionary: (await workbook.inspect({ kind: "table", range: "DanhMucSkill!A1:C16", include: "values,formulas", tableMaxRows: 16, tableMaxCols: 3, maxChars: 6000 })).ndjson,
  errors: (await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" })).ndjson,
};
for (const [sheetName, range, filename, scale] of [["KhaoSat", "A1:Z14", "khaosat.png", 0.62], ["HuongDan", "A1:E43", "huongdan.png", 0.9], ["DanhMucSkill", "A1:C46", "danhmucskill.png", 1.0]]) {
  const image = await workbook.render({ sheetName, range, scale, format: "png" });
  await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await image.arrayBuffer()));
}
const exported = await SpreadsheetFile.exportXlsx(workbook);
await exported.save(outputPath);
const dictionarySummary = Object.fromEntries(sourceSkillColumns.map((column) => [column.key, dictionaryByField.get(column.key).length]));
await fs.writeFile(path.join(workDir, "skill-dictionary.json"), `${JSON.stringify({ source_sha256: sourceSha256, source_records: theses.length, matching_fields: sourceSkillKeys, unique_values_by_field: dictionarySummary, total_unique_values: dictionaryRows.length }, null, 2)}\n`);
await fs.writeFile(path.join(workDir, "artifact-validation.json"), `${JSON.stringify({ output: path.relative(repoRoot, outputPath).replaceAll("\\", "/"), schema_version: schema.version, sheets: ["KhaoSat", "HuongDan", "DanhMucSkill"], header_labels: schema.columns.map((column) => column.label), field_keys: schema.columns.map((column) => column.key), input_rows_are_blank: true, source_records: theses.length, source_matching_fields: sourceSkillColumns.length, dictionary_values: dictionaryRows.length, inspections }, null, 2)}\n`);
console.log(JSON.stringify({ outputPath, previewDir, schemaVersion: schema.version, surveyColumns: schema.columns.length, sourceRecords: theses.length, sourceMatchingFields: sourceSkillColumns.length, dictionaryValues: dictionaryRows.length, dictionarySummary }, null, 2));
