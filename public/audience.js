const questionTitle = document.querySelector("#questionTitle");
const optionsContainer = document.querySelector("#options");
const voteForm = document.querySelector("#voteForm");
const submitButton = document.querySelector("#submitVote");
const feedback = document.querySelector("#feedback");
const messageForm = document.querySelector("#messageForm");
const messageInput = document.querySelector("#messageInput");
const messageCount = document.querySelector("#messageCount");
const submitMessageButton = document.querySelector("#submitMessage");
const messageFeedback = document.querySelector("#messageFeedback");

const MESSAGE_MAX_LENGTH = 50;
const MESSAGE_COOLDOWN_MS = 3000;
const LAST_MESSAGE_AT_KEY = "slice2:lastMessageAt";

let currentQuestion = null;

async function fetchQuestion() {
  const response = await fetch("/api/current-question");
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "题目加载失败");
  }
  currentQuestion = data.question;
  renderQuestion(currentQuestion);
}

function renderQuestion(question) {
  questionTitle.textContent = question.title;
  optionsContainer.innerHTML = "";

  question.options.forEach((option) => {
    const label = document.createElement("label");
    label.className = "option-card";

    const input = document.createElement("input");
    input.type = "radio";
    input.name = "option";
    input.value = option.id;

    const text = document.createElement("span");
    text.textContent = option.label;

    label.append(input, text);
    optionsContainer.append(label);
  });

  submitButton.disabled = false;
}

voteForm.addEventListener("change", () => {
  feedback.textContent = "";
});

voteForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const selected = new FormData(voteForm).get("option");
  if (!selected) {
    feedback.textContent = "请先选择一个选项";
    return;
  }

  submitButton.disabled = true;
  feedback.textContent = "正在提交...";

  try {
    const response = await fetch("/api/votes", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ option_id: Number(selected) }),
    });
    const data = await response.json();
    if (!data.ok) {
      throw new Error(data.error || "投票失败");
    }
    feedback.textContent = "已收到";
    currentQuestion = data.question;
  } catch (error) {
    feedback.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

messageInput.addEventListener("input", () => {
  const length = messageInput.value.length;
  messageCount.textContent = `${length}/${MESSAGE_MAX_LENGTH}`;
  messageFeedback.textContent = "";
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const body = messageInput.value.trim();
  if (!body) {
    messageFeedback.textContent = "请输入留言";
    return;
  }
  if (body.length > MESSAGE_MAX_LENGTH) {
    messageFeedback.textContent = "留言最多 50 字";
    return;
  }

  const lastMessageAt = Number(localStorage.getItem(LAST_MESSAGE_AT_KEY) || 0);
  const remainingMs = MESSAGE_COOLDOWN_MS - (Date.now() - lastMessageAt);
  if (remainingMs > 0) {
    messageFeedback.textContent = `发送太快了，请 ${Math.ceil(remainingMs / 1000)} 秒后再试`;
    return;
  }

  submitMessageButton.disabled = true;
  messageFeedback.textContent = "正在发送...";

  try {
    const response = await fetch("/api/messages", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ body }),
    });
    const data = await response.json();
    if (!data.ok) {
      throw new Error(data.error || "留言发送失败");
    }
    localStorage.setItem(LAST_MESSAGE_AT_KEY, String(Date.now()));
    messageInput.value = "";
    messageCount.textContent = `0/${MESSAGE_MAX_LENGTH}`;
    messageFeedback.textContent = "已发送";
  } catch (error) {
    messageFeedback.textContent = error.message;
  } finally {
    submitMessageButton.disabled = false;
  }
});

fetchQuestion().catch((error) => {
  questionTitle.textContent = "题目加载失败";
  feedback.textContent = error.message;
});
