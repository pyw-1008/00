const ADMIN_PASSWORD_KEY = "slice4:adminPassword";
const OPTION_COUNT = 6;

const loginPanel = document.querySelector("#loginPanel");
const adminPanel = document.querySelector("#adminPanel");
const loginForm = document.querySelector("#loginForm");
const passwordInput = document.querySelector("#passwordInput");
const loginFeedback = document.querySelector("#loginFeedback");
const questionList = document.querySelector("#questionList");
const questionForm = document.querySelector("#questionForm");
const questionIdInput = document.querySelector("#questionId");
const questionInput = document.querySelector("#questionInput");
const optionInputs = document.querySelector("#optionInputs");
const newQuestionButton = document.querySelector("#newQuestionButton");
const clearVotesButton = document.querySelector("#clearVotesButton");
const adminFeedback = document.querySelector("#adminFeedback");

let adminPassword = sessionStorage.getItem(ADMIN_PASSWORD_KEY) || "";
let questions = [];

function adminHeaders() {
  return {
    "Content-Type": "application/json",
    "X-Admin-Password": adminPassword,
  };
}

function renderOptionInputs(values = []) {
  optionInputs.innerHTML = "";
  for (let index = 0; index < OPTION_COUNT; index += 1) {
    const label = document.createElement("label");
    const title = document.createElement("span");
    const input = document.createElement("input");

    title.textContent = `选项 ${index + 1}`;
    input.type = "text";
    input.className = "option-input";
    input.value = values[index] || "";
    input.placeholder = index < 2 ? "必填" : "可选";

    label.append(title, input);
    optionInputs.append(label);
  }
}

function setLoggedIn(loggedIn) {
  loginPanel.hidden = loggedIn;
  adminPanel.hidden = !loggedIn;
}

function setEditor(question) {
  questionIdInput.value = question?.id || "";
  questionInput.value = question?.title || "";
  renderOptionInputs(question?.options?.map((option) => option.label) || ["", ""]);
  adminFeedback.textContent = "";
}

async function login(password) {
  const response = await fetch("/api/admin/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ password }),
  });
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "登录失败");
  }
}

async function loadQuestions() {
  const response = await fetch("/api/admin/questions", {
    headers: adminHeaders(),
  });
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "题目加载失败");
  }
  questions = data.questions;
  renderQuestionList();
  if (!questionIdInput.value && questions[0]) {
    setEditor(questions[0]);
  }
}

function renderQuestionList() {
  questionList.innerHTML = "";
  questions.forEach((question) => {
    const row = document.createElement("div");
    const item = document.createElement("button");
    const activateButton = document.createElement("button");

    row.className = "question-row";
    item.type = "button";
    item.className = question.status === "active" ? "question-item is-active" : "question-item";
    item.textContent = question.status === "active" ? `当前：${question.title}` : question.title;
    item.addEventListener("click", () => {
      setEditor(question);
    });

    activateButton.type = "button";
    activateButton.className = "secondary-button compact-button";
    activateButton.textContent = "设为当前";
    activateButton.disabled = question.status === "active";
    activateButton.addEventListener("click", async () => {
      adminFeedback.textContent = "正在切换...";
      try {
        await activateQuestion(question.id);
        await loadQuestions();
        adminFeedback.textContent = "已切换当前题；票数已重置";
      } catch (error) {
        adminFeedback.textContent = error.message;
      }
    });

    row.append(item, activateButton);
    questionList.append(row);
  });
}

function collectQuestionPayload() {
  const options = Array.from(document.querySelectorAll(".option-input"))
    .map((input) => input.value.trim())
    .filter(Boolean);

  return {
    id: questionIdInput.value ? Number(questionIdInput.value) : null,
    title: questionInput.value.trim(),
    options,
  };
}

async function saveQuestion(payload) {
  const response = await fetch("/api/admin/questions", {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "保存失败");
  }
  return data.question;
}

async function clearVotes() {
  const response = await fetch("/api/admin/clear-votes", {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({}),
  });
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "清空失败");
  }
}

async function activateQuestion(id) {
  const response = await fetch("/api/admin/activate", {
    method: "POST",
    headers: adminHeaders(),
    body: JSON.stringify({ id }),
  });
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "切换失败");
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginFeedback.textContent = "正在验证...";
  try {
    await login(passwordInput.value);
    adminPassword = passwordInput.value;
    sessionStorage.setItem(ADMIN_PASSWORD_KEY, adminPassword);
    setLoggedIn(true);
    await loadQuestions();
    loginFeedback.textContent = "";
  } catch (error) {
    sessionStorage.removeItem(ADMIN_PASSWORD_KEY);
    loginFeedback.textContent = error.message;
  }
});

questionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  adminFeedback.textContent = "正在保存...";
  try {
    await saveQuestion(collectQuestionPayload());
    await loadQuestions();
    adminFeedback.textContent = "已保存，并设为当前题；票数已重置";
  } catch (error) {
    adminFeedback.textContent = error.message;
  }
});

newQuestionButton.addEventListener("click", () => {
  setEditor(null);
});

clearVotesButton.addEventListener("click", async () => {
  adminFeedback.textContent = "正在清空...";
  try {
    await clearVotes();
    await loadQuestions();
    adminFeedback.textContent = "当前题票数已清空";
  } catch (error) {
    adminFeedback.textContent = error.message;
  }
});

renderOptionInputs(["", ""]);
if (adminPassword) {
  setLoggedIn(true);
  loadQuestions().catch((error) => {
    sessionStorage.removeItem(ADMIN_PASSWORD_KEY);
    setLoggedIn(false);
    loginFeedback.textContent = error.message;
  });
}
