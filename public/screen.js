const POLL_INTERVAL_MS = 1500;

const titleElement = document.querySelector("#screenQuestionTitle");
const totalVotesElement = document.querySelector("#totalVotes");
const chartElement = document.querySelector("#chart");

async function fetchQuestion() {
  const response = await fetch("/api/current-question");
  const data = await response.json();
  if (!data.ok) {
    throw new Error(data.error || "投票结果加载失败");
  }
  renderQuestion(data.question);
}

function renderQuestion(question) {
  titleElement.textContent = question.title;
  totalVotesElement.textContent = `总票数：${question.total_votes}`;

  chartElement.innerHTML = "";
  question.options.forEach((option) => {
    const row = document.createElement("div");
    row.className = "bar-row";

    const label = document.createElement("div");
    label.className = "bar-label";
    label.textContent = option.label;

    const track = document.createElement("div");
    track.className = "bar-track";

    const fill = document.createElement("div");
    fill.className = "bar-fill";
    fill.style.width = `${option.percentage}%`;

    const value = document.createElement("div");
    value.className = "bar-value";
    value.textContent = `${option.votes} 票 / ${option.percentage}%`;

    track.append(fill);
    row.append(label, track, value);
    chartElement.append(row);
  });
}

fetchQuestion().catch((error) => {
  titleElement.textContent = "投票结果加载失败";
  totalVotesElement.textContent = error.message;
});
setInterval(() => {
  fetchQuestion().catch((error) => {
    totalVotesElement.textContent = error.message;
  });
}, POLL_INTERVAL_MS);
