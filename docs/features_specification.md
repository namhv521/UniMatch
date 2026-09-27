# Features Specification — Student & Advisor Features

**Ngày:** 26/09/2026 | **Status:** Feature Design Complete

---

## 1. Sinh Viên (Student) Features

| Feature Name | Type | Range | Description | Source |
|--------------|------|-------|-------------|--------|
| `student_id` | String (UUID) | - | Unique identifier | Database PK |
| `full_name` | String | - | Full name of student | Database |
| `year` | Integer | {2023, 2024, 2025, 2026} | Academic year | Database |
| `major` | Categorical | {AI/ML, SE, IS, Security, Data Science, Other} | Major/specialization | Database |
| `thesis_title` | String | - | Title of thesis topic | PDF/Database |
| `thesis_abstract` | String | - | Abstract (Vietnamese text) | PDF |
| `thesis_keywords` | List[String] | - | Extracted keywords | NLP |
| `research_interests` | List[String] | - | Research areas mentioned | NLP extraction |
| `gpa` | Float | [0.0, 4.0] | Cumulative GPA | Database |
| `prior_advisor_id` | String (optional) | - | Previous advisor (if any) | Database |
| `preference_ranking` | List[String] | Top 3 | Preference ranking of advisors | Lifecycle V2+ |

**Semantics:**
- Text fields (thesis_abstract, research_interests) are preprocessed with Vietnamese NLP
- year/major are categorical and can be one-hot encoded
- gpa is normalized to [0, 1]

---

## 2. Giảng Viên (Advisor) Features

| Feature Name | Type | Range | Description | Source |
|--------------|------|-------|-------------|--------|
| `advisor_id` | String (UUID) | - | Unique identifier | Database PK |
| `full_name` | String | - | Full name of advisor | Database |
| `title` | Categorical | {Prof, Assoc Prof, Lecturer, Teaching Asst} | Academic title | Database |
| `department` | Categorical | {AI/ML, SE, IS, Security, Network, Other} | Department/group | Database |
| `specialization` | String | - | Main research specialization | Profile |
| `research_areas` | List[String] | - | List of research topics | Publications/Profile |
| `bio` | String | - | Biography (Vietnamese text) | Profile |
| `publications_summary` | String | - | Summary of recent publications | Bibliographic data |
| `keywords` | List[String] | - | Extracted keywords from publications | NLP on publications |
| `max_quota` | Integer | [1, 10] | Maximum students to advise | Policy |
| `current_load` | Integer | [0, max_quota] | Current number of advisees | Database (dynamic) |

**Semantics:**
- Bio and publications_summary are preprocessed with Vietnamese NLP
- specialization and research_areas drive compatibility scoring
- keywords extracted from publications and profile using NLP
- current_load updates dynamically during matching

---

## 3. Derived Features (Compatibility Matrix)

**Compatibility Score:** $\text{comp}(s, a) \in [0, 1]$

Calculated as **Cosine Similarity** between:
- **Student representation:** TF-IDF + Dense embeddings from {thesis_title, abstract, keywords}
- **Advisor representation:** TF-IDF + Dense embeddings from {specialization, research_areas, bio, keywords}

Formula:
$$\text{comp}(s, a) = \frac{\mathbf{e}_s \cdot \mathbf{e}_a}{|\mathbf{e}_s| \cdot |\mathbf{e}_a|}$$

**Output:** 198×39 matrix (students × advisors), values ∈ [0, 1]

---

## 4. State Features (from MDP)

State $s_t$ at step $t$ uses:
- **Compatibility vector** (1×39): scores for student $t$ vs all advisors
- **Remaining capacity** (1×39): $(C_j - L_{t,j}) / C_j$ for each advisor
- **Load ratio** (1×39): $L_{t,j} / C_j$ for each advisor

Total state dimension: **3×39 = 117**

---

## 5. Data Types & Validation

### Student Table Schema
```yaml
students:
  student_id: String (primary key)
  full_name: String (non-null)
  year: Integer (in {2023, 2024, 2025, 2026})
  major: String (categorical)
  thesis_title: String (non-null)
  thesis_abstract: String (can be null initially, filled from PDF)
  gpa: Float (in [0.0, 4.0])
  prior_advisor_id: String (nullable, foreign key to advisors)
```

### Advisor Table Schema
```yaml
advisors:
  advisor_id: String (primary key)
  full_name: String (non-null)
  title: String (categorical)
  department: String (non-null)
  specialization: String (non-null)
  max_quota: Integer (in [1, 10])
```

### Compatibility Matrix Schema
```yaml
compatibility:
  student_id: String (foreign key)
  advisor_id: String (foreign key)
  score: Float (in [0.0, 1.0])
```

---

## 6. Data Quality Rules

1. **No Null Values:** All compatibility scores must be in [0.0, 1.0], no NaN
2. **Normalization:** Text features normalized before vectorization
3. **Temporal Consistency:** Year field consistent with cohort assignment
4. **Uniqueness:** student_id and advisor_id are unique
5. **Referential Integrity:** prior_advisor_id (if present) must reference valid advisor_id

---

## 7. Feature Engineering Pipeline

1. **Text Preprocessing (Vietnamese NLP)**
   - Tokenization (NLTK/spaCy for Vietnamese)
   - Stop word removal
   - Stemming/Lemmatization

2. **TF-IDF Vectorization**
   - Fit on train set only
   - Vocabulary size: 5000–10000 terms

3. **Dense Embeddings**
   - Pre-trained Sentence Transformers model
   - Model: `sentence-transformers/all-MiniLM-L6-v2` (Vietnamese-friendly)
   - Embedding dimension: 384

4. **Similarity Computation**
   - Cosine similarity between embeddings
   - Range: [0.0, 1.0]

---

**Features design aligns with MDP formulation (DAY-02) and ready for data pipeline (DAY-04+).**
