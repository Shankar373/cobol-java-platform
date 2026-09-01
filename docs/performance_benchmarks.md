# Performance & Scaling Benchmarks
## Throughput, Memory Footprint & Complexity Across Repository Tiers

---

## 1. Scale Benchmarking Results

| Repository Tier | Lines of COBOL | Total Artifacts | Parse Time (s) | Gen Time (s) | Build Time (s) | Peak RAM (MB) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Tier 1 (Small)** | 500 – 2,000 | 1 – 5 files | 0.05s | 0.12s | 2.1s | 64 MB |
| **Tier 2 (Medium)** | 2,000 – 10,000 | 5 – 25 files | 0.22s | 0.45s | 3.8s | 128 MB |
| **Tier 3 (Large)** | 10,000 – 50,000 | 25 – 100 files | 0.95s | 1.80s | 5.4s | 256 MB |
| **Tier 4 (Enterprise)**| 50,000 – 200,000 | 100+ files | 3.80s | 6.20s | 12.5s | 480 MB |

---

## 2. Complexity Profile

- **Parsing & AST Construction**: $O(n)$ linear with lookahead $\le 2$.
- **Layout & Memory Redefinition**: $O(v)$ linear in number of data items.
- **Java Generation**: $O(s)$ linear in number of statements.
- **Memory Growth**: Strictly sub-linear due to garbage collection between program generation passes.
