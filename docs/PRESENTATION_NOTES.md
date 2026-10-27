# B.Tech Minor Project Presentation Notes & Slide Blueprint

**Project Title:** Intelligent Invoice Processing for Automated Accounting Book Generation  
**Department:** Computer Science & Engineering, Bharati Vidyapeeth's College of Engineering (GGSIPU), New Delhi  
**Authors:** Anand Misra (04011502723), Pratham Nahata (05611502723)  
**Supervisor:** Dr. Jolly Parikh (Assistant Professor)  
**Academic Cycle:** September – December 2026  

---

## Slide-by-Slide Presentation Blueprint

### Slide 1: Title & Team
* **Project Title:** Intelligent Invoice Processing for Automated Accounting Book Generation
* **Subtitle:** An End-to-End Multimodal Document Intelligence & Double-Entry Accounting Framework
* **Presenters:** Anand Misra (04011502723), Pratham Nahata (05611502723)
* **Guide:** Dr. Jolly Parikh, Assistant Professor, Department of CSE

### Slide 2: Motivation & The Industrial Problem
* **The Manual Bottleneck:** Invoices arrive in heterogeneous formats (scanned, digital, multi-page, varied layouts). Accountants manually inspect, verify line items, determine GST treatments, and post double entries.
* **The Gap in Modern AI:** Existing state-of-the-art Document AI (LayoutLM, Donut, OCR pipelines) stops at **information extraction**. No system connects extracted tabular data directly to **verifiable double-entry accounting records** (Journals, Ledgers, Trial Balance, P&L, Balance Sheet).
* **Research Challenge:** How to achieve template-free extraction while enforcing strict financial invariants where LLMs are prone to arithmetic and accounting hallucinations.

### Slide 3: Research Foundations & Base Papers
* **Base Paper 1 (Rana et al., 2025 - JISEM):**
  * *Focus:* Template-free invoice digitization using SmolVLM + heuristic post-processing.
  * *Strength:* Lightweight VLM eliminates supplier-specific templates; low compute overhead.
  * *Limitation:* Tested on private data; stops at field extraction; no accounting integration.
* **Base Paper 2 (Yao et al., 2026 - Canadian AI / PMLR):**
  * *Focus:* Multimodal document extraction with table layout correction.
  * *Strength:* Hybrid Markdown/HTML representation fixes table header-row-column associations (evaluated with TEDS).
  * *Limitation:* Evaluated only on paystubs and QA tasks; no line-item reconciliation or financial ledger generation.
* **Our Contribution:** Unifying template-free extraction (Rana et al.) with multimodal table layout correction (Yao et al.) and coupling it with an **Accounting Interpretation & Deterministic Invariant Engine**.

### Slide 4: Proposed System Architecture (Methodology Flow)
* **Stage 1 (Ingestion & Preprocessing):** PDF vector text extraction or OpenCV deskew/contrast normalization for scans.
* **Stage 2 (Multimodal Extraction):** Template-free Vision-Language extraction (SmolVLM / Multimodal VLM).
* **Stage 3 (Table Layout Correction):** Hybrid Markdown/HTML row-column alignment to accurately associate descriptions, quantities, unit prices, and tax rates.
* **Stage 4 (Heuristic Validation):** Strict mathematical verification (Qty × Rate = Line Total, Subtotal + Tax − Discount = Grand Total).
* **Stage 5 (Accounting Interpretation):** LLM-assisted transaction classification and account mapping based on the Chart of Accounts and GST rules.
* **Stage 6 (Deterministic Accounting Engine):** Hardcoded double-entry invariant verification (Debits == Credits, exact decimal arithmetic, active COA accounts).
* **Stage 7 (Review & Financial Books):** Human-in-the-loop review UI, immutable Journal posting, Ledger generation, and automated Trial Balance / Financial Statements.

### Slide 5: Dataset & Evaluation Strategy
* **Data Sources:** Public invoice benchmarks (CORD, SROIE, DocILE) supplemented with synthetic, legally safe Indian GST invoices covering diverse layouts, tax slabs, and line items.
* **Leakage-Free Splitting:** Supplier/Template-disjoint train/test split (unseen vendors in test set) to prove true template-free generalization.
* **Ablation Studies (E1 to E6):**
  * E1: Baseline SmolVLM template-free extraction.
  * E2: SmolVLM + Rana et al. Heuristic Validation.
  * E3: Table Layout Correction (Yao et al. hybrid representation).
  * E4: Integrated Document Intelligence (Extraction + Correction + Validation).
  * E5: Full Pipeline with Accounting Interpretation.
  * E6: Complete End-to-End System with Deterministic Invariants & Human Review.

### Slide 6: Comparative Evaluation Metrics
| Metric Category | Metrics Used | Compared Against |
|---|---|---|
| **Field Extraction** | Field Exact Match (EM), Precision, Recall, F1 | Rana et al. (2025) baseline |
| **Table Structure** | Tree-Edit-Distance-based Similarity (TEDS) | Yao et al. (2026) baseline |
| **Validation Reliability** | Arithmetic Error Detection Rate, Hallucination Catch Rate | Raw VLM without heuristics |
| **Accounting Precision** | Account Mapping Accuracy, Debit/Credit Correctness, Journal EM | Standard manual posting |
| **Operational Impact** | Processing Latency, Human-in-the-Loop Review Percentage | Traditional manual data entry |

### Slide 7: Live Demonstration Walkthrough (The Golden Case)
* **Input Document:** Fictional invoice from *ABC Furniture Mart* (₹50,000 furniture + ₹9,000 GST = ₹59,000).
* **System Processing:**
  1. OCR/VLM extracts fields & tabular line items.
  2. Table correction aligns 2 line items and checks `50,000 + 9,000 == 59,000`.
  3. Engine identifies asset capitalization policy: Office Furniture A/c (Debit ₹50,000), Input GST A/c (Debit ₹9,000), ABC Furniture Mart (Credit ₹59,000).
  4. Invariant validator confirms exact decimal equality (`59,000.00 Dr == 59,000.00 Cr`).
  5. User approves in dashboard; ledger updates; Trial Balance balances instantaneously.

### Slide 8: Technology Stack & Engineering Rigor
* **Backend:** Python 3.11, FastAPI, Pydantic v2 (strict typed schemas), SQLAlchemy 2.0.
* **Financial Integrity:** Exact `Decimal` arithmetic (zero floating-point drift).
* **AI & Document Intelligence:** SmolVLM / Multimodal VLM adapters, PyMuPDF, OpenCV.
* **Frontend:** React, Vite, Tailwind CSS (Side-by-side invoice reviewer, ledger & statement viewer).
* **Testing:** Automated Pytest suite testing accounting invariants and extraction math.

### Slide 9: Conclusion & Future Scope
* **Key Achievements:** Built an end-to-end bridge between multimodal document intelligence and audited financial reporting, extending prior research beyond pure OCR.
* **Future Work:** Multi-currency support, automated bank reconciliation against bank statements, and deployment as an ERP plugin (Tally / Busy export).
