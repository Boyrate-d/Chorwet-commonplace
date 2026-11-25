let currentUser = null;

async function api(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || "Request failed");
    return data;
}

function escapeHtml(value) {
    return String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
}

async function initialize() {
    try {
        const me = await api("/api/me");
        currentUser = me.user;
        document.getElementById("dashboard-user").textContent = currentUser.username;
        document.getElementById("dashboard-avatar").textContent = currentUser.username.charAt(0).toUpperCase();
        await Promise.all([loadPosts(), loadNetwork(), loadEvents(), loadAnnouncements(), loadCulture(), loadProfile()]);
    } catch (error) {
        window.location.href = "/login.html";
    }
}

async function loadPosts() {
    const data = await api("/api/posts");
    const list = document.getElementById("feed-list");
    list.innerHTML = data.posts.length ? data.posts.map(post => `
        <article class="post-card">
            <div class="post-author">${escapeHtml(post.username).charAt(0).toUpperCase()}</div>
            <div>
                <strong>${escapeHtml(post.username)}</strong>
                <time>${escapeHtml(post.created_at)}</time>
                <p>${escapeHtml(post.content)}</p>
                ${post.media_url && post.media_type && post.media_type.startsWith("image/")
                    ? `<img class="post-media" src="${escapeHtml(post.media_url)}" alt="Shared by ${escapeHtml(post.username)}" loading="lazy">`
                    : ""}
                ${post.media_url && post.media_type && post.media_type.startsWith("video/")
                    ? `<video class="post-media" src="${escapeHtml(post.media_url)}" controls preload="metadata"></video>`
                    : ""}
            </div>
        </article>
    `).join("") : '<p class="empty-state">No posts yet. Start the conversation.</p>';
}

document.getElementById("post-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const content = document.getElementById("post-content").value.trim();
    const media = document.getElementById("post-media").files[0];
    if (!content && !media) return;
    try {
        await api("/api/posts", {
            method: "POST",
            body: new FormData(form),
        });
        form.reset();
        document.getElementById("upload-name").textContent = "No file selected";
        await loadPosts();
    } catch (error) {
        alert(error.message);
    }
});

document.getElementById("post-media").addEventListener("change", event => {
    document.getElementById("upload-name").textContent =
        event.target.files[0] ? event.target.files[0].name : "No file selected";
});

let networkData = { followers: [], following: [] };

async function loadNetwork() {
    const data = await api("/api/network");
    networkData = data;
    document.getElementById("followers-count").textContent = data.followers.length;
    document.getElementById("following-count").textContent = data.following.length;
    renderNetwork("followers");
    document.getElementById("follow-suggestions").innerHTML = data.suggestions.length
        ? data.suggestions.map(person => `
            <article class="person-card">
                <span class="person-card-avatar">${escapeHtml(person.username).charAt(0).toUpperCase()}</span>
                <strong>${escapeHtml(person.username)}</strong>
                <button class="text-button" data-follow-id="${person.id}" type="button">Follow</button>
            </article>
        `).join("")
        : '<p class="empty-state">You are following everyone for now.</p>';

    document.querySelectorAll("[data-follow-id]").forEach(button => {
        button.addEventListener("click", async () => {
            await api(`/api/follow/${button.dataset.followId}`, {
                method: "POST",
            });
            await loadNetwork();
        });
    });
}

function renderNetwork(type) {
    const people = networkData[type];
    document.getElementById("network-list").innerHTML = people.length
        ? people.map(person => `
            <article class="person-card">
                <span class="person-card-avatar">${escapeHtml(person.username).charAt(0).toUpperCase()}</span>
                <strong>${escapeHtml(person.username)}</strong>
                <span class="person-card-label">${type === "followers" ? "Follows you" : "You follow them"}</span>
            </article>
        `).join("")
        : `<p class="empty-state">No ${type} yet. Start by following someone below.</p>`;
}

async function loadEvents() {
    const data = await api("/api/events");
    const list = document.getElementById("event-list");
    list.innerHTML = data.events.length ? data.events.map(event => `
        <article class="event-card">
            <div class="event-date">
                <strong>${new Date(event.event_date.replace(" ", "T")).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</strong>
                <span>${new Date(event.event_date.replace(" ", "T")).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</span>
            </div>
            <div class="event-card-content">
                <span class="event-category">${escapeHtml(event.category)}</span>
                <h3>${escapeHtml(event.title)}</h3>
                <p>${escapeHtml(event.description)}</p>
                <div class="event-meta"><span>${escapeHtml(event.location)}</span><span>${event.attendees} attending</span></div>
                <button class="button ${event.attending ? "button-dark" : "button-ghost"} event-rsvp" data-event-id="${event.id}" type="button">
                    ${event.attending ? "Going" : "I’m interested"}
                </button>
            </div>
        </article>
    `).join("") : '<p class="empty-state">No events yet. Be the first to host one.</p>';

    document.querySelectorAll(".event-rsvp").forEach(button => {
        button.addEventListener("click", async () => {
            await api(`/api/events/${button.dataset.eventId}/rsvp`, { method: "POST" });
            await loadEvents();
        });
    });
}

document.getElementById("show-event-form").addEventListener("click", () => {
    const form = document.getElementById("event-form");
    form.hidden = !form.hidden;
});

document.getElementById("event-form").addEventListener("submit", async event => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    try {
        await api("/api/events", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(values),
        });
        form.reset();
        form.hidden = true;
        await loadEvents();
    } catch (error) {
        alert(error.message);
    }
});

async function loadCulture() {
    const data = await api("/api/culture");
    document.getElementById("culture-list").innerHTML = data.stories.map(story => `
        <article class="culture-card culture-${escapeHtml(story.color)}">
            <span>${escapeHtml(story.category)}</span>
            <h3>${escapeHtml(story.title)}</h3>
            <p>${escapeHtml(story.description)}</p>
            <button class="text-button" type="button">Explore story <span aria-hidden="true">→</span></button>
        </article>
    `).join("");
}

async function loadProfile() {
    const data = await api(`/api/profile/${currentUser.id}`);
    const profile = data.profile;
    document.getElementById("profile-avatar").textContent = profile.display_name.charAt(0).toUpperCase();
    document.getElementById("profile-display-name").textContent = profile.display_name;
    document.getElementById("profile-username").textContent = `@${profile.username}`;
    document.getElementById("profile-user-id").textContent = profile.user_id;
    document.getElementById("profile-followers").textContent = profile.followers;
    document.getElementById("profile-following").textContent = profile.following;
    document.getElementById("profile-name-input").value = profile.display_name;
    document.getElementById("profile-location-input").value = profile.location;
    document.getElementById("profile-bio-input").value = profile.bio;
}

document.getElementById("profile-form").addEventListener("submit", async event => {
    event.preventDefault();
    const result = document.getElementById("profile-result");
    const form = event.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    try {
        await api("/api/profile", {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(values),
        });
        result.textContent = "Profile updated.";
        await loadProfile();
        document.getElementById("dashboard-user").textContent = values.display_name;
        document.getElementById("dashboard-avatar").textContent = values.display_name.charAt(0).toUpperCase();
    } catch (error) {
        result.textContent = error.message;
    }
});

async function loadAnnouncements() {
    const data = await api("/api/announcements");
    document.getElementById("announcement-list").innerHTML = data.announcements.length
        ? data.announcements.map(item => `
            <article class="announcement-card">
                <span>${escapeHtml(item.category)}</span>
                <h3>${escapeHtml(item.title)}</h3>
                <p>${escapeHtml(item.content)}</p>
                <time>${escapeHtml(item.published_at)}</time>
            </article>
        `).join("")
        : '<p class="empty-state">No official announcements yet.</p>';
}

document.querySelectorAll(".network-tab").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".network-tab").forEach(tab => tab.classList.remove("active"));
        button.classList.add("active");
        renderNetwork(button.dataset.network);
    });
});

document.querySelectorAll(".dashboard-nav-item").forEach(button => {
    button.addEventListener("click", () => showView(button.dataset.view));
});
document.querySelectorAll("[data-view-target]").forEach(button => {
    button.addEventListener("click", () => showView(button.dataset.viewTarget));
});

function showView(viewName) {
    document.querySelectorAll(".dashboard-view").forEach(view => view.classList.remove("active"));
    document.querySelectorAll(".dashboard-nav-item").forEach(button => {
        button.classList.toggle("active", button.dataset.view === viewName);
    });
    document.getElementById(`view-${viewName}`).classList.add("active");
}

document.getElementById("dashboard-logout").addEventListener("click", async () => {
    await api("/api/logout", { method: "POST" });
    window.location.href = "/login.html";
});

initialize();
