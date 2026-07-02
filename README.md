# AI-Powered HR Management System

An intelligent HR backend system built with **MySQL, FastAPI, AI Agents, RAG, Analytics, and LangGraph**.

This project stores structured HR data, exposes REST APIs, answers database questions, retrieves HR policy answers, detects HR risks, and intelligently routes user questions to the correct AI agent.

---

## Project Overview

HR data is usually spread across multiple systems such as employee records, attendance, payroll, leave requests, training records, performance data, and policy documents.

This project solves that problem by creating one intelligent backend system where a user can ask a question and receive the correct response from the right source.

Example questions:

* Show employee count by department
* Who can access payroll information?
* Which employees have attendance risk?

---

## Key Features

* Relational HR database using MySQL
* FastAPI backend with REST endpoints
* Swagger UI for API testing
* SQL Agent for structured database questions
* Llama SQL Agent for natural-language-to-SQL generation
* RAG Agent for HR policy/document questions
* Analytics Agent using pandas and scikit-learn
* LangGraph Orchestrator for intelligent agent routing
* MySQL, ChromaDB, Llama/Ollama, and ML integration

---

## Tech Stack

| Technology      | Purpose                          |
| --------------- | -------------------------------- |
| MySQL           | Stores structured HR data        |
| MySQL Workbench | Database creation and validation |
| Python          | Backend logic                    |
| FastAPI         | REST API development             |
| Swagger         | API testing and documentation    |
| SQLAlchemy      | Python to MySQL connection       |
| pandas          | Data analysis                    |
| scikit-learn    | Risk and anomaly detection       |
| ChromaDB        | Vector database for RAG          |
| Unstructured    | Document chunking                |
| Ollama / Llama  | Local LLM                        |
| LangGraph       | Agent orchestration              |

---

## Database Design

Database name:

```text
HRManagementDB
```

Tables created:

* Department
* Employee
* Attendance
* LeaveRequest
* Payroll
* Training
* PerformanceReview
* JobHistory
* Skills
* Certifications

The `Employee` table is the central table. Other tables connect to it using `employee_id`.

---

## System Architecture

```text
User Question
     ↓
FastAPI API Gateway
     ↓
Middleware
     ↓
LangGraph Orchestrator
     ↓
SQL Agent | RAG Agent | Analytics Agent
     ↓
MySQL | ChromaDB + Llama | pandas + scikit-learn
     ↓
Final Response
```

---

## Agents

### SQL Agent

The SQL Agent answers structured database questions.

Example:

```text
Show employee count by department
```

It detects the intent, selects a safe SQL query, runs it on MySQL, and returns the result.

---

### Llama SQL Agent

The Llama SQL Agent uses a local Llama model through Ollama to generate SQL from natural language.

Safety checks are added so that only `SELECT` queries are allowed.

Blocked operations include:

* DELETE
* DROP
* UPDATE
* INSERT
* ALTER
* TRUNCATE

---

### RAG Agent

The RAG Agent answers HR policy and document-based questions.

Example:

```text
Who can access payroll information?
```

Flow:

```text
Policy Document → Unstructured → Chunks → ChromaDB → Retrieved Context → Llama Answer
```

---

### Analytics Agent

The Analytics Agent uses pandas and scikit-learn to detect HR risks.

It supports:

* Attendance risk detection
* Payroll anomaly detection
* Department scorecard generation

The model uses `IsolationForest` for anomaly detection.

---

### LangGraph Orchestrator

LangGraph decides which agent should answer the question.

Routing logic:

| Question Type                       | Routed To       |
| ----------------------------------- | --------------- |
| Count, salary, overtime, department | SQL Agent       |
| Policy, privacy, access, approval   | RAG Agent       |
| Risk, anomaly, scorecard            | Analytics Agent |

Main endpoint:

```text
POST /orchestrator/ask
```

---

## API Endpoints

### Basic APIs

```text
GET /health
GET /employees
GET /employees/{employee_id}
GET /departments
GET /departments/{department_id}
```

### Employee Record APIs

```text
GET /employees/{employee_id}/attendance
GET /employees/{employee_id}/payroll
GET /employees/{employee_id}/leave-requests
```

### Employee Development APIs

```text
GET /employees/{employee_id}/training
GET /employees/{employee_id}/performance-reviews
GET /employees/{employee_id}/job-history
GET /employees/{employee_id}/skills
GET /employees/{employee_id}/certifications
```

### Agent APIs

```text
POST /sql-agent/ask
POST /sql-agent/llama-ask
POST /rag/ask
GET /analytics/attendance-risk
GET /analytics/payroll-anomalies
GET /analytics/department-scorecard
POST /orchestrator/ask
```

---

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd hr_employee_portal
```

---

### 2. Create Virtual Environment

```bash
python -m venv .venv
```

Activate it:

```bash
.venv\Scripts\activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Create `.env` File

Create a `.env` file in the root folder.

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=HRManagementDB
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
```

Do not upload the real `.env` file to GitHub.

---

### 5. Start MySQL

Make sure the MySQL service is running.

On Windows, check:

```text
Services → MySQL80 → Running
```

---

### 6. Run FastAPI

```bash
python main.py
```

Open Swagger:

```text
http://127.0.0.1:8000/docs
```

---

### 7. Build RAG Index

```bash
python build_rag_index.py
```

---

### 8. Run Ollama

Make sure Ollama is running with the selected model:

```bash
ollama run llama3.2
```

---

## Demo Questions

### SQL Agent

```json
{
  "question": "Show employee count by department"
}
```

Expected result:

```text
Department-wise employee count
```

---

### RAG Agent

```json
{
  "question": "Who can access payroll information?"
}
```

Expected result:

```text
Policy-based answer with sources
```

---

### Analytics Agent

```json
{
  "question": "Which employees have attendance risk?"
}
```

Expected result:

```text
Risk-ranked employees
```

---

## Challenges Faced

* MySQL service was not running
* CSV import had missing/null row issues
* Employee count initially showed 59 instead of 60
* scikit-learn had to be installed in the correct virtual environment
* RAG required ChromaDB indexing
* Orchestrator routing needed correction for policy/privacy questions

---

## Future Enhancements

* Add frontend employee portal
* Add user login and authentication
* Add role-based access control
* Add admin dashboard
* Add more HR policy documents
* Improve Llama SQL accuracy
* Add charts and visual analytics
* Deploy the system to cloud
* Add logging and monitoring

---

## Conclusion

This project demonstrates how structured databases, REST APIs, LLMs, RAG, analytics, and orchestration can work together in one AI-powered HR application.

The final system can store HR data, answer database questions, retrieve policy answers, detect risks, and intelligently route user questions to the correct backend agent.
