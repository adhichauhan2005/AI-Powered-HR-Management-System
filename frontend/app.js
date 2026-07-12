const API_BASE_URL = "http://127.0.0.1:8000"

let lastQuestion = ""
let lastSelectedAgent = ""
let lastResponse = null

function setExample(question) {
  document.getElementById("questionInput").value = question
}

function setStatus(message) {
  document.getElementById("statusMessage").innerText = message
}

function setRawJson(data) {
  document.getElementById("rawJsonOutput").innerText = JSON.stringify(
    data,
    null,
    2,
  )
}

function clearResult() {
  document.getElementById("questionInput").value = ""
  document.getElementById("cleanResult").innerHTML = ""
  document.getElementById("rawJsonOutput").innerText = ""
  document.getElementById("feedbackComment").value = ""
  document.getElementById("feedbackStatus").innerText = ""
  setStatus("No request submitted yet.")

  lastQuestion = ""
  lastSelectedAgent = ""
  lastResponse = null
}

function getSelectedMode() {
  return document.getElementById("agentMode").value
}

function getQuestion() {
  return document.getElementById("questionInput").value.trim()
}

async function askQuestion() {
  const mode = getSelectedMode()
  const question = getQuestion()

  if (!question && !mode.startsWith("analytics_")) {
    alert("Please enter a question.")
    return
  }

  setStatus("Processing request...")
  document.getElementById("cleanResult").innerHTML = ""
  document.getElementById("feedbackStatus").innerText = ""

  try {
    let responseData

    if (mode === "auto") {
      responseData = await postRequest("/orchestrator/ask", {
        question: question,
      })
    } else if (mode === "sql") {
      responseData = await postRequest("/sql-agent/ask", {
        question: question,
      })
    } else if (mode === "rag") {
      responseData = await postRequest("/rag/ask", {
        question: question,
      })
    } else if (mode === "analytics_attendance") {
      responseData = await getRequest("/analytics/attendance-risk")
    } else if (mode === "analytics_payroll") {
      responseData = await getRequest("/analytics/payroll-anomalies")
    } else if (mode === "analytics_scorecard") {
      responseData = await getRequest("/analytics/department-scorecard")
    }

    lastQuestion = question || mode
    lastResponse = responseData
    lastSelectedAgent = detectSelectedAgent(mode, responseData)

    setStatus("Request completed successfully.")
    setRawJson(responseData)
    renderCleanResult(responseData)
  } catch (error) {
    console.error(error)
    setStatus(
      "Request failed. Check FastAPI server, MySQL, Ollama, or browser console.",
    )
    document.getElementById("cleanResult").innerHTML = `
            <div class="result-card">
                <strong>Error:</strong> ${error.message}
            </div>
        `
  }
}

async function postRequest(endpoint, body) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const errorData = await response.json()
    throw new Error(JSON.stringify(errorData))
  }

  return response.json()
}

async function getRequest(endpoint) {
  const response = await fetch(`${API_BASE_URL}${endpoint}`)

  if (!response.ok) {
    const errorData = await response.json()
    throw new Error(JSON.stringify(errorData))
  }

  return response.json()
}

function detectSelectedAgent(mode, responseData) {
  if (responseData && responseData.selected_agent) {
    return responseData.selected_agent
  }

  if (mode === "sql") {
    return "sql"
  }

  if (mode === "rag") {
    return "rag"
  }

  if (mode.startsWith("analytics_")) {
    return "analytics"
  }

  return "unknown"
}

function renderCleanResult(data) {
  const container = document.getElementById("cleanResult")

  if (!data) {
    container.innerHTML = "<p>No data returned.</p>"
    return
  }

  let html = ""

  if (data.selected_agent) {
    html += createCard("Selected Agent", data.selected_agent)
  }

  if (data.answer_type) {
    html += createCard("Answer Type", data.answer_type)
  }

  if (data.matched_intent) {
    html += createCard("Matched Intent", data.matched_intent)
  }

  if (data.analysis_name) {
    html += createCard("Analysis Name", data.analysis_name)
  }

  if (data.explanation) {
    html += createCard("Explanation", data.explanation)
  }

  if (data.answer) {
    html += createCard("Answer", data.answer)
  }

  if (data.generated_sql) {
    html += createCard(
      "Generated SQL",
      `<pre>${escapeHtml(data.generated_sql)}</pre>`,
    )
  }

  if (typeof data.row_count !== "undefined") {
    html += createCard("Row Count", data.row_count)
  }

  if (data.results && Array.isArray(data.results)) {
    html += createCard("Results", renderTable(data.results))
  }

  if (data.sources && Array.isArray(data.sources)) {
    html += createCard("Sources", renderSources(data.sources))
  }

  if (!html) {
    html = `<pre>${escapeHtml(JSON.stringify(data, null, 2))}</pre>`
  }

  container.innerHTML = html
}

function createCard(title, value) {
  return `
        <div class="result-card">
            <strong>${title}:</strong>
            <div>${value}</div>
        </div>
    `
}

function renderTable(rows) {
  if (!rows || rows.length === 0) {
    return "No rows returned."
  }

  const columns = Object.keys(rows[0])

  let tableHtml = `
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr>
    `

  columns.forEach((column) => {
    tableHtml += `<th>${escapeHtml(column)}</th>`
  })

  tableHtml += `
                </tr>
            </thead>
            <tbody>
    `

  rows.slice(0, 10).forEach((row) => {
    tableHtml += "<tr>"

    columns.forEach((column) => {
      tableHtml += `<td>${escapeHtml(String(row[column]))}</td>`
    })

    tableHtml += "</tr>"
  })

  tableHtml += `
            </tbody>
        </table>
    `

  if (rows.length > 10) {
    tableHtml += `<p>Showing first 10 of ${rows.length} rows.</p>`
  }

  return tableHtml
}

function renderSources(sources) {
  if (!sources || sources.length === 0) {
    return "No sources returned."
  }

  let sourceHtml = "<ul>"

  sources.forEach((source) => {
    sourceHtml += `
            <li>
                <strong>${escapeHtml(source.source || "Source")}:</strong>
                ${escapeHtml(source.text || JSON.stringify(source))}
            </li>
        `
  })

  sourceHtml += "</ul>"

  return sourceHtml
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;")
}

async function submitFeedback(feedbackValue) {
  if (!lastResponse) {
    alert("Please ask a question before submitting feedback.")
    return
  }

  const comment = document.getElementById("feedbackComment").value.trim()

  const feedbackPayload = {
    question: lastQuestion,
    selected_agent: lastSelectedAgent,
    feedback: feedbackValue,
    comment: comment || null,
    expected_answer: null,
    original_response: lastResponse,
  }

  try {
    const responseData = await postRequest("/feedback", feedbackPayload)

    document.getElementById("feedbackStatus").innerText =
      "Feedback saved successfully."

    document.getElementById("feedbackStatus").className =
      "feedback-status success"

    console.log("Feedback response:", responseData)
  } catch (error) {
    document.getElementById("feedbackStatus").innerText =
      "Feedback submission failed."

    document.getElementById("feedbackStatus").className =
      "feedback-status error"

    console.error(error)
  }
}
