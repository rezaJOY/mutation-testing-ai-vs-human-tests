# mutation-testing-ai-vs-human-tests
Measuring AI-generated vs human-written unit test quality using mutation testing

## 1. Project Title

Evaluating the Quality of AI-Generated Unit Tests 
Using Mutation Coverage Compared to Human-Written Tests

---

## 2. Research Question

Do AI-generated unit tests detect injected faults as 
effectively as human-written tests?

---

## 4. Project Structure

research_project/
├── projects/
│   ├── project_a/                 # cloned repo — untouched
│   │   ├── setup.cfg              # mutmut config added here
│   │   ├── tests/                 # human tests — never modified
│   │   └── ai_tests/              # AI tests — isolated here
│   ├── project_b/
│   └── project_c/
├── scripts/
│   ├── vet_project.py
│   ├── generate_tests.py
│   ├── validate_tests.py
│   ├── extract_scores.py
│   └── record_metadata.py
├── results/
│   ├── results.csv
│   ├── metadata.json
│   └── raw_ai_outputs/            # raw LLM responses before cleaning
├── requirements.txt
└── README.md

---

## 5. Dataset
The 3 open source projects
---

## 6. How to Reproduce
Step by step instructions:
- Clone the repo
- Install dependencies
- Set the API key
- Run the scripts in order
- Extract results

---

## 7. Results Summary
A simple table showing the final mutation scores:

| Project | Module | Human Score | AI Score |
|---|---|---|---|
| schedule | scheduler.py | 74% | 61% |
| boltons | strutils.py | 68% | 57% |
| black | linegen.py | 71% | 63% |

---

## 8. Tools & Versions
| Tool | Version |
|---|---|
| Python | 3.x |
| Mutmut | 2.4.4 |
| Pytest | x.x |
| LLM | Groq llama-3.1-70b-versatile |

---

## 9. Authors
- Md Ziaur Reza
- Kainat


---

## 10. Supervisor


n?
