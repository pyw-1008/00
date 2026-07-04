const questionTitle = document.querySelector("#questionTitle");
const optionsContainer = document.querySelector("#options");
const voteForm = document.querySelector("#voteForm");
const submitButton = document.querySelector("#submitVote");
const feedback = document.querySelector("#feedback");

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

fetchQuestion().catch((error) => {
  questionTitle.textContent = "题目加载失败";
  feedback.textContent = error.message;
});
