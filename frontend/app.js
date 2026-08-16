"use strict"

// The browser talks only to FastAPI. FastAPI is responsible
// for reading and writing the conversation in Redis.
const API_BASE_URL = "http://127.0.0.1:8000"
const SESSION_STORAGE_KEY = "hr_agent_session_id"

let sessionId = localStorage.getItem(SESSION_STORAGE_KEY)
let requestInProgress = false
let toastTimer = null

const elements = {
  messages: document.getElementById("messages"),
  questionForm: document.getElementById("questionForm"),
  questionInput: document.getElementById("questionInput"),
  sendButton: document.getElementById("sendButton"),
  typingIndicator: document.getElementById("typingIndicator"),
  historyList: document.getElementById("historyList"),
  historyCount: document.getElementById("historyCount"),
  newSessionButton: document.getElementById("newSessionButton"),
  clearSessionButton: document.getElementById("clearSessionButton"),
  suggestionList: document.getElementById("suggestionList"),
  connectionPill: document.getElementById("connectionPill"),
  connectionText: document.getElementById("connectionText"),
  toast: document.getElementById("toast"),
  historyPanel: document.getElementById("historyPanel"),
  suggestionsPanel: document.getElementById("suggestionsPanel"),
  mobileHistoryButton: document.getElementById("mobileHistoryButton"),
  closeHistoryButton: document.getElementById("closeHistoryButton"),
  suggestionsToggle: document.getElementById("suggestionsToggle"),
  closeSuggestionsButton: document.getElementById("closeSuggestionsButton"),
  mobileBackdrop: document.getElementById("mobileBackdrop"),
}

const fallbackSuggestions = [
  {
    icon: "↗",
    title: "Who has the lowest salary?",
    subtitle: "Payroll insight",
  },
  {
    icon: "⌘",
    title: "Show employee count by department",
    subtitle: "Department overview",
  },
  {
    icon: "◎",
    title: "What is the AI Engineer salary?",
    subtitle: "Designation lookup",
  },
  {
    icon: "◷",
    title: "Which employees have attendance risk?",
    subtitle: "Attendance analytics",
  },
  {
    icon: "◇",
    title: "Who can access payroll information?",
    subtitle: "HR policy",
  },
]

function showWelcome() {
  elements.messages.replaceChildren()

  const welcome = document.createElement("section")
  welcome.className = "welcome-card"

  const spark = document.createElement("div")
  spark.className = "welcome-spark"
  spark.setAttribute("aria-hidden", "true")
  spark.textContent = "✦"

  const heading = document.createElement("h1")
  heading.append("How can I help with ")
  const accent = document.createElement("span")
  accent.textContent = "HR today?"
  heading.append(accent)

  const description = document.createElement("p")
  description.textContent =
    "Ask naturally about employees, departments, payroll, attendance, training, or workplace policies."

  const capabilities = document.createElement("div")
  capabilities.className = "welcome-capabilities"

  for (const label of [
    "Employees",
    "Payroll",
    "Attendance",
    "Departments",
    "Policies",
  ]) {
    const chip = document.createElement("span")
    chip.textContent = label
    capabilities.append(chip)
  }

  welcome.append(spark, heading, description, capabilities)
  elements.messages.append(welcome)
}

function createMessage(role, content, feedbackQuestion = null) {
  const row = document.createElement("article")
  row.className = `message-row ${role}`

  const avatar = document.createElement("div")
  avatar.className = "message-avatar"
  avatar.textContent = role === "user" ? "You" : "HR"

  const stack = document.createElement("div")
  stack.className = "message-stack"

  const label = document.createElement("span")
  label.className = "message-label"
  label.textContent = role === "user" ? "You" : "HR Agent"

  const bubble = document.createElement("div")
  bubble.className = "message-bubble"
  bubble.textContent = String(content || "")

  stack.append(label, bubble)

  if (role === "assistant" && feedbackQuestion) {
    stack.append(createFeedbackBox(feedbackQuestion, String(content || "")))
  }

  row.append(avatar, stack)
  elements.messages.append(row)
  scrollToLatestMessage()

  return row
}

function scrollToLatestMessage() {
  elements.messages.scrollTop = elements.messages.scrollHeight
}

function setBusy(isBusy) {
  requestInProgress = isBusy
  elements.sendButton.disabled = isBusy
  elements.questionInput.disabled = isBusy
  elements.typingIndicator.classList.toggle("hidden", !isBusy)

  if (isBusy) {
    scrollToLatestMessage()
  }
}

function setConnection(state, text) {
  elements.connectionPill.classList.remove("connected", "disconnected")

  if (state === "connected") {
    elements.connectionPill.classList.add("connected")
  }

  if (state === "disconnected") {
    elements.connectionPill.classList.add("disconnected")
  }

  elements.connectionText.textContent = text
}

function showToast(message, type = "success") {
  window.clearTimeout(toastTimer)
  elements.toast.textContent = message
  elements.toast.className = `toast ${type}`

  toastTimer = window.setTimeout(() => {
    elements.toast.classList.add("hidden")
  }, 5000)
}

function errorMessageFrom(data, fallback) {
  if (typeof data?.detail === "string") {
    return data.detail
  }

  if (Array.isArray(data?.detail) && data.detail[0]?.msg) {
    return data.detail[0].msg
  }

  if (typeof data?.message === "string") {
    return data.message
  }

  return fallback
}

async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  })

  let data = null

  try {
    data = await response.json()
  } catch {
    data = null
  }

  if (!response.ok) {
    throw new Error(
      errorMessageFrom(
        data,
        `The request could not be completed (${response.status}).`,
      ),
    )
  }

  return data
}

function extractAnswer(data) {
  if (typeof data === "string") {
    return data
  }

  for (const value of [
    data?.answer,
    data?.response,
    data?.explanation,
    data?.message,
  ]) {
    if (typeof value === "string" && value.trim()) {
      return value.trim()
    }
  }

  return "I could not find that information in the available HR context."
}

function historyMessagesFrom(data) {
  if (Array.isArray(data)) {
    return data
  }

  if (Array.isArray(data?.history)) {
    return data.history
  }

  if (Array.isArray(data?.messages)) {
    return data.messages
  }

  return []
}

function clearHistoryView() {
  elements.historyList.replaceChildren()
  elements.historyCount.textContent = "0"

  const empty = document.createElement("div")
  empty.className = "empty-state compact-empty"

  const icon = document.createElement("span")
  icon.className = "empty-icon"
  icon.textContent = "✦"

  const text = document.createElement("p")
  text.textContent = "Your recent questions will appear here."

  empty.append(icon, text)
  elements.historyList.append(empty)
}

function historyTime(timestamp) {
  if (!timestamp) {
    return "Just now"
  }

  const date = new Date(timestamp)

  if (Number.isNaN(date.getTime())) {
    return "This session"
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })
}

function addHistoryItem(question, timestamp = null) {
  elements.historyList.querySelector(".empty-state")?.remove()

  const button = document.createElement("button")
  button.type = "button"
  button.className = "history-item"
  button.title = question

  const icon = document.createElement("span")
  icon.className = "history-item-icon"
  icon.textContent = "?"

  const copy = document.createElement("span")
  copy.className = "history-item-copy"

  const title = document.createElement("strong")
  title.textContent = question

  const time = document.createElement("small")
  time.textContent = historyTime(timestamp)

  copy.append(title, time)
  button.append(icon, copy)

  button.addEventListener("click", () => {
    elements.historyList.querySelectorAll(".history-item").forEach((item) => {
      item.classList.remove("active")
    })

    button.classList.add("active")
    elements.questionInput.value = question
    resizeQuestionInput()
    elements.questionInput.focus()
    closeMobilePanels()
  })

  elements.historyList.append(button)
  elements.historyCount.textContent = String(
    elements.historyList.querySelectorAll(".history-item").length,
  )
}

async function loadSessionHistory() {
  if (!sessionId) {
    showWelcome()
    clearHistoryView()
    return
  }

  try {
    const data = await apiRequest(
      `/hr-agent/session/${encodeURIComponent(sessionId)}`,
    )
    const history = historyMessagesFrom(data)

    elements.messages.replaceChildren()
    clearHistoryView()

    if (!history.length) {
      showWelcome()
      return
    }

    let latestQuestion = null

    for (const message of history) {
      const role = message?.role === "assistant" ? "assistant" : "user"
      const content = message?.content || message?.message || ""

      if (!content) {
        continue
      }

      if (role === "user") {
        latestQuestion = content
        addHistoryItem(content, message?.timestamp)
        createMessage("user", content)
      } else {
        createMessage("assistant", content, latestQuestion)
      }
    }

    setConnection("connected", "Redis session active")
  } catch (error) {
    console.error("Could not restore the session:", error)
    sessionId = null
    localStorage.removeItem(SESSION_STORAGE_KEY)
    showWelcome()
    clearHistoryView()
    setConnection("disconnected", "Backend unavailable")
  }
}

async function askQuestion(question) {
  if (requestInProgress) {
    return
  }

  const welcome = elements.messages.querySelector(".welcome-card")
  welcome?.remove()

  createMessage("user", question)
  addHistoryItem(question)
  elements.questionInput.value = ""
  resizeQuestionInput()
  setBusy(true)

  try {
    const data = await apiRequest("/hr-agent/ask", {
      method: "POST",
      body: JSON.stringify({
        question,
        session_id: sessionId,
      }),
    })

    if (data?.session_id) {
      sessionId = data.session_id
      localStorage.setItem(SESSION_STORAGE_KEY, sessionId)
    }

    const answer = extractAnswer(data)
    createMessage("assistant", answer, question)

    if (data?.storage_backend === "redis") {
      setConnection("connected", "Redis session active")
    } else {
      setConnection("connected", "HR Agent online")
    }
  } catch (error) {
    console.error("HR Agent request failed:", error)
    createMessage(
      "assistant",
      "I’m having trouble reaching the HR service right now. Please make sure FastAPI is running and try again.",
    )
    setConnection("disconnected", "Backend unavailable")
    showToast(error.message, "error")
  } finally {
    setBusy(false)
    elements.questionInput.focus()
  }
}

function createFeedbackButton(label, value) {
  const button = document.createElement("button")
  button.type = "button"
  button.className = "feedback-button"
  button.dataset.feedback = value
  button.textContent = label
  return button
}

function createFeedbackBox(question, originalAnswer) {
  const box = document.createElement("div")
  box.className = "feedback-box"

  const prompt = document.createElement("p")
  prompt.className = "feedback-prompt"
  prompt.textContent = "Was this answer helpful?"

  const actions = document.createElement("div")
  actions.className = "feedback-actions"

  const correct = createFeedbackButton("✓ Helpful", "correct")
  const wrong = createFeedbackButton("✕ Incorrect", "wrong")
  const improve = createFeedbackButton("◇ Improve", "needs_improvement")

  actions.append(correct, wrong, improve)
  box.append(prompt, actions)

  correct.addEventListener("click", () => {
    submitFeedback({
      box,
      question,
      originalAnswer,
      feedback: "correct",
      expectedAnswer: null,
      comment: null,
    })
  })

  wrong.addEventListener("click", () => {
    showCorrectionArea(box, question, originalAnswer, "wrong")
  })

  improve.addEventListener("click", () => {
    showCorrectionArea(box, question, originalAnswer, "needs_improvement")
  })

  return box
}

function showCorrectionArea(box, question, originalAnswer, feedback) {
  box.querySelector(".correction-area")?.remove()

  const area = document.createElement("div")
  area.className = "correction-area"

  const textarea = document.createElement("textarea")
  textarea.placeholder =
    feedback === "wrong"
      ? "What should the correct answer be?"
      : "How could this answer be improved?"

  const submit = document.createElement("button")
  submit.type = "button"
  submit.className = "correction-submit"
  submit.textContent = "Submit feedback"

  submit.addEventListener("click", () => {
    const correction = textarea.value.trim()

    if (!correction) {
      textarea.focus()
      showToast("Please enter the expected answer or improvement.", "error")
      return
    }

    submitFeedback({
      box,
      question,
      originalAnswer,
      feedback,
      expectedAnswer: correction,
      comment: correction,
    })
  })

  area.append(textarea, submit)
  box.append(area)
  textarea.focus()
}

function setFeedbackDisabled(box, disabled) {
  box.querySelectorAll("button, textarea").forEach((control) => {
    control.disabled = disabled
  })
}

async function submitFeedback({
  box,
  question,
  originalAnswer,
  feedback,
  expectedAnswer,
  comment,
}) {
  setFeedbackDisabled(box, true)

  try {
    await apiRequest("/feedback", {
      method: "POST",
      body: JSON.stringify({
        question,
        selected_agent: "hr_agent",
        feedback,
        comment,
        expected_answer: expectedAnswer,
        original_response: {
          answer: originalAnswer,
          session_id: sessionId,
        },
      }),
    })

    box.querySelector(".correction-area")?.remove()

    const confirmation = document.createElement("p")
    confirmation.className = "feedback-confirmation"
    confirmation.textContent = "Feedback submitted — thank you."
    box.append(confirmation)

    window.setTimeout(() => {
      confirmation.remove()
    }, 5000)
  } catch (error) {
    console.error("Feedback submission failed:", error)
    setFeedbackDisabled(box, false)
    showToast(`Feedback could not be saved: ${error.message}`, "error")
  }
}

function normalizeSuggestions(data) {
  let examples = []

  if (Array.isArray(data)) {
    examples = data
  } else if (Array.isArray(data?.examples)) {
    examples = data.examples
  } else if (Array.isArray(data?.prompts)) {
    examples = data.prompts
  }

  return examples
    .map((item, index) => {
      if (typeof item === "string") {
        return {
          icon: fallbackSuggestions[index % fallbackSuggestions.length].icon,
          title: item,
          subtitle: "Suggested question",
        }
      }

      const title = item?.question || item?.prompt || item?.text

      if (!title) {
        return null
      }

      return {
        icon:
          item?.icon ||
          fallbackSuggestions[index % fallbackSuggestions.length].icon,
        title,
        subtitle: item?.category || item?.label || "Suggested question",
      }
    })
    .filter(Boolean)
}

function renderSuggestions(suggestions) {
  elements.suggestionList.replaceChildren()

  for (const suggestion of suggestions) {
    const button = document.createElement("button")
    button.type = "button"
    button.className = "suggestion-card"

    const icon = document.createElement("span")
    icon.className = "suggestion-icon"
    icon.textContent = suggestion.icon

    const copy = document.createElement("span")
    copy.className = "suggestion-copy"

    const title = document.createElement("strong")
    title.textContent = suggestion.title

    const subtitle = document.createElement("small")
    subtitle.textContent = suggestion.subtitle

    const arrow = document.createElement("span")
    arrow.className = "suggestion-arrow"
    arrow.textContent = "›"

    copy.append(title, subtitle)
    button.append(icon, copy, arrow)

    button.addEventListener("click", () => {
      elements.questionInput.value = suggestion.title
      resizeQuestionInput()
      elements.questionInput.focus()
      closeMobilePanels()
    })

    elements.suggestionList.append(button)
  }
}

async function loadSuggestions() {
  try {
    const data = await apiRequest("/hr-agent/prompt-examples")
    const suggestions = normalizeSuggestions(data)
    renderSuggestions(suggestions.length ? suggestions : fallbackSuggestions)
    setConnection("connected", "HR Agent online")
  } catch (error) {
    console.error("Could not load prompt examples:", error)
    renderSuggestions(fallbackSuggestions)
    setConnection("disconnected", "Start FastAPI")
  }
}

function startNewSession() {
  sessionId = null
  localStorage.removeItem(SESSION_STORAGE_KEY)
  showWelcome()
  clearHistoryView()
  elements.questionInput.value = ""
  resizeQuestionInput()
  elements.questionInput.focus()
  closeMobilePanels()
  showToast("New conversation started.")
}

async function clearCurrentSession() {
  if (!sessionId) {
    showWelcome()
    clearHistoryView()
    showToast("This session is already clear.")
    return
  }

  const confirmed = window.confirm(
    "Clear this conversation and its saved history?",
  )

  if (!confirmed) {
    return
  }

  try {
    await apiRequest(`/hr-agent/session/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    })

    sessionId = null
    localStorage.removeItem(SESSION_STORAGE_KEY)
    showWelcome()
    clearHistoryView()
    closeMobilePanels()
    showToast("Session history cleared.")
  } catch (error) {
    console.error("Could not clear session:", error)
    showToast(error.message, "error")
  }
}

function resizeQuestionInput() {
  elements.questionInput.style.height = "auto"
  elements.questionInput.style.height = `${Math.min(elements.questionInput.scrollHeight, 130)}px`
}

function updateBackdrop() {
  const panelOpen =
    elements.historyPanel.classList.contains("open") ||
    elements.suggestionsPanel.classList.contains("open")
  elements.mobileBackdrop.classList.toggle("visible", panelOpen)
}

function openHistoryPanel() {
  elements.suggestionsPanel.classList.remove("open")
  elements.historyPanel.classList.add("open")
  elements.mobileHistoryButton.setAttribute("aria-expanded", "true")
  updateBackdrop()
}

function openSuggestionsPanel() {
  elements.historyPanel.classList.remove("open")
  elements.suggestionsPanel.classList.add("open")
  elements.suggestionsToggle.setAttribute("aria-expanded", "true")
  updateBackdrop()
}

function closeMobilePanels() {
  elements.historyPanel.classList.remove("open")
  elements.suggestionsPanel.classList.remove("open")
  elements.mobileHistoryButton.setAttribute("aria-expanded", "false")
  elements.suggestionsToggle.setAttribute("aria-expanded", "false")
  updateBackdrop()
}

elements.questionForm.addEventListener("submit", (event) => {
  event.preventDefault()
  const question = elements.questionInput.value.trim()

  if (!question || requestInProgress) {
    return
  }

  askQuestion(question)
})

elements.questionInput.addEventListener("input", resizeQuestionInput)

elements.questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault()
    elements.questionForm.requestSubmit()
  }
})

elements.newSessionButton.addEventListener("click", startNewSession)
elements.clearSessionButton.addEventListener("click", clearCurrentSession)
elements.mobileHistoryButton.addEventListener("click", openHistoryPanel)
elements.closeHistoryButton.addEventListener("click", closeMobilePanels)
elements.suggestionsToggle.addEventListener("click", openSuggestionsPanel)
elements.closeSuggestionsButton.addEventListener("click", closeMobilePanels)
elements.mobileBackdrop.addEventListener("click", closeMobilePanels)

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeMobilePanels()
  }
})

async function initialize() {
  showWelcome()
  clearHistoryView()

  await Promise.allSettled([loadSuggestions(), loadSessionHistory()])
  elements.questionInput.focus()
}

initialize()
