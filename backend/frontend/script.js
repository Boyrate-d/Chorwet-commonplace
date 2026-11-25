const navToggle = document.querySelector(".nav-toggle");
const navLinks = document.querySelector(".nav-links");

if (navToggle && navLinks) {
    navToggle.addEventListener("click", () => {
        const isOpen = navLinks.classList.toggle("open");
        navToggle.setAttribute("aria-expanded", String(isOpen));
    });
}

async function loadAuthState() {
    const authActions = document.getElementById("auth-actions");
    if (!authActions) return;

    try {
        const response = await fetch("/api/me");
        const data = await response.json();
        if (data.success) {
            authActions.innerHTML = `
                <span class="signed-in-name">Hello, ${escapeHtml(data.user.username)}</span>
                <button class="button button-dark" id="logout-button" type="button">Log out</button>
            `;
            document.getElementById("logout-button").addEventListener("click", async () => {
                await fetch("/api/logout", { method: "POST" });
                window.location.href = "/dashboard";
            });
        }
    } catch (error) {
        // The public page remains usable if authentication cannot be reached.
    }
}

async function loadStats() {
    try {
        const response = await fetch("/api/stats");
        const data = await response.json();
        if (!data.success) return;

        const memberCount = document.getElementById("member-count");
        const ideasCount = document.getElementById("ideas-count");
        if (memberCount) {
            memberCount.textContent = `${Number(data.stats.members).toLocaleString()}+`;
        }
        if (ideasCount) {
            ideasCount.textContent = Number(data.stats.ideas_shared_this_week).toLocaleString();
        }
    } catch (error) {
        // Keep the static fallback values shown in the HTML.
    }
}

async function loadTopics() {
    const topicList = document.querySelector(".topic-list");
    if (!topicList) return;

    try {
        const response = await fetch("/api/topics");
        const data = await response.json();
        if (!data.success) return;

        topicList.innerHTML = data.topics.map((topic, index) => `
            <a href="#circles"><span>${String(index + 1).padStart(2, "0")}</span>${escapeHtml(topic)}</a>
        `).join("");
    } catch (error) {
        // Keep the static topic links if the endpoint is unavailable.
    }
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

loadAuthState();
loadStats();
loadTopics();

const loginForm = document.getElementById("login-form");

if (loginForm) {
    let authMode = "login";
    const title = document.getElementById("auth-title");
    const description = document.getElementById("auth-description");
    const submit = document.getElementById("auth-submit");
    const modeToggle = document.getElementById("auth-mode-toggle");
    const modePrompt = document.getElementById("auth-mode-prompt");
    const modeAction = document.getElementById("auth-mode-action");

    modeToggle.addEventListener("click", () => {
        authMode = authMode === "login" ? "register" : "login";
        const isRegister = authMode === "register";
        title.textContent = isRegister ? "Create your account." : "Good to see you.";
        description.textContent = isRegister
            ? "Choose a username and password to join the conversation."
            : "Enter your details to join the conversation.";
        submit.innerHTML = isRegister
            ? 'Create account <span aria-hidden="true">→</span>'
            : 'Log in <span aria-hidden="true">→</span>';
        modePrompt.textContent = isRegister ? "Already a member?" : "New to Chorwet Common Place?";
        modeAction.textContent = isRegister ? "Log in" : "Create an account";
        document.getElementById("email-field").hidden = !isRegister;
        document.getElementById("identity-label").textContent = isRegister ? "Username" : "Username or email";
        document.getElementById("username").autocomplete = isRegister ? "username" : "username";
        document.getElementById("result").textContent = "";
    });

    loginForm.addEventListener("submit", async (event) => {
        event.preventDefault();

        const username = document.getElementById("username").value.trim();
        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value;
        const result = document.getElementById("result");

        result.textContent = authMode === "register" ? "Creating account..." : "Signing in...";

        try {
            const response = await fetch(authMode === "register" ? "/api/register" : "/api/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(authMode === "register"
                    ? { username, email, password }
                    : { identifier: username, password })
            });
            const data = await response.json();
            result.textContent = data.message;

            if (data.success) {
                submit.textContent = authMode === "register" ? "Account created" : "Logged in";
                window.location.href = "/dashboard";
            }
        } catch (error) {
            result.textContent = "Unable to reach the server. Please try again.";
        }
    });
}