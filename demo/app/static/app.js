const queryInput = document.getElementById("queryInput");
const askButton = document.getElementById("askButton");
const loading = document.getElementById("loading");
const resultArea = document.getElementById("resultArea");
const answerContent = document.getElementById("answerContent");
const sourcesBox = document.getElementById("sourcesBox");
const sourcesContent = document.getElementById("sourcesContent");
const sourceCount = document.getElementById("sourceCount");
const charCount = document.getElementById("charCount");
const copyButton = document.getElementById("copyButton");
const systemStatus = document.getElementById("systemStatus");
const statusText = document.getElementById("statusText");

function setLoading(isLoading) {
    askButton.disabled = isLoading;
    loading.classList.toggle("hidden", !isLoading);
}

function showAnswer(message, isError = false) {
    answerContent.textContent = message;
    answerContent.classList.toggle("error", isError);
    resultArea.classList.remove("hidden");
}

function sourceElement(source, index) {
    const article = document.createElement("article");
    article.className = "source-item";

    const header = document.createElement("div");
    header.className = "source-header";

    const title = document.createElement("span");
    title.className = "source-title";
    title.textContent = `Nguồn ${index + 1}`;

    const score = document.createElement("span");
    score.className = "source-score";
    score.textContent = `Độ liên quan ${Number(source.score).toFixed(4)}`;

    const meta = document.createElement("p");
    meta.className = "source-meta";
    meta.textContent = `${source.section_id} · ${source.paragraph_id}`;

    const text = document.createElement("p");
    text.className = "source-text";
    text.textContent = source.text;

    header.append(title, score);
    article.append(header, meta, text);
    return article;
}

function renderSources(sources) {
    sourcesContent.replaceChildren();
    if (!Array.isArray(sources) || sources.length === 0) {
        sourcesBox.classList.add("hidden");
        return;
    }

    const topSources = sources.slice(0, 5);

    topSources.forEach((source, index) => {
        sourcesContent.appendChild(sourceElement(source, index));
    });
    sourceCount.textContent = `${topSources.length} nguồn`;
    sourcesBox.classList.remove("hidden");
}

async function askQuestion() {
    const query = queryInput.value.trim();
    if (!query) {
        queryInput.focus();
        return;
    }

    setLoading(true);
    resultArea.classList.add("hidden");
    sourcesBox.classList.add("hidden");
    answerContent.textContent = "";

    try {
        const response = await fetch("/api/ask", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({query}),
        });
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Không thể xử lý câu hỏi.");
        }

        showAnswer(data.answer || "Hệ thống không trả về nội dung.");
        renderSources(data.sources);
        resultArea.scrollIntoView({behavior: "smooth", block: "start"});
    } catch (error) {
        showAnswer(
            error.message || "Có lỗi xảy ra khi xử lý câu hỏi.",
            true,
        );
        renderSources([]);
    } finally {
        setLoading(false);
    }
}

async function checkHealth() {
    try {
        const response = await fetch("/api/health");
        const data = await response.json();
        const ready = response.ok && data.retriever_ready;
        systemStatus.classList.toggle("ready", ready);
        systemStatus.classList.toggle("error", !ready);
        statusText.textContent = ready
            ? "Hệ thống sẵn sàng"
            : "Cần cấu hình dữ liệu";
        systemStatus.title = data.detail || "";
    } catch {
        systemStatus.classList.add("error");
        statusText.textContent = "Backend chưa kết nối";
    }
}

queryInput.addEventListener("input", () => {
    charCount.textContent = `${queryInput.value.length} / ${queryInput.maxLength}`;
});

queryInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        askQuestion();
    }
});

askButton.addEventListener("click", askQuestion);

copyButton.addEventListener("click", async () => {
    try {
        await navigator.clipboard.writeText(answerContent.textContent);
        copyButton.textContent = "Đã sao chép";
        window.setTimeout(() => {
            copyButton.textContent = "Sao chép";
        }, 1600);
    } catch {
        copyButton.textContent = "Không thể sao chép";
    }
});

checkHealth();
