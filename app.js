const API_BASE = "/api";

let streakCounter  = 0;
let localHighScore = 0;
let trackAnchorA   = null;
let trackTargetB   = null;
let guessing       = false; // Lock flag to prevent double-click input bugs

// ── Helpers ──────────────────────────────────────────────────

function setButtons(enabled) {
    document.getElementById("btnHigher").disabled = !enabled;
    document.getElementById("btnLower").disabled  = !enabled;
}

// Formats database ISO strings to localized display rules
function formatScrapeDate(isoString) {
    if (!isoString) return "Baseline Seed";
    try {
        const date = new Date(isoString);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    } catch (e) {
        return "Baseline Seed";
    }
}

function preloadCardImages(urlA, urlB) {
    const cleanUrlA = (urlA && urlA.startsWith("//") ? "https:" + urlA : urlA) || "https://placehold.co/300x300/1f2937/ffffff?text=No+Cover";
    const cleanUrlB = (urlB && urlB.startsWith("//") ? "https:" + urlB : urlB) || "https://placehold.co/300x300/1f2937/ffffff?text=No+Cover";

    // Build standalone promise instances for both image assets
    const promiseA = new Promise((resolve) => {
        const img = new Image();
        img.src = cleanUrlA;
        img.onload = () => resolve(cleanUrlA);
        img.onerror = () => resolve(cleanUrlA); // Resolve anyway to prevent game lockouts on bad links
    });

    const promiseB = new Promise((resolve) => {
        const img = new Image();
        img.src = cleanUrlB;
        img.onload = () => resolve(cleanUrlB);
        img.onerror = () => resolve(cleanUrlB);
    });

    // Wait until BOTH files are fully downloaded before letting the game continue
    return Promise.all([promiseA, promiseB]);
}

// ── Fetch a fresh pairing setup from the server ───────────────────────

async function fetchNextGamePairing() {
    try {
        const res = await fetch(`${API_BASE}/game/pair`);
        if (!res.ok) {
            const err = await res.json();
            alert(err.detail || "Could not load a song pair.");
            return;
        }
        const data = await res.json();
        
        await preloadCardImages(data.song_a.image_url, data.song_b.image_url);

        trackAnchorA = data.song_a;
        trackTargetB = data.song_b;
        renderGameUIState();
    } catch (err) {
        console.error("fetchNextGamePairing failed:", err);
    }
}

// Retain current winning Target as the new Anchor, pull a fresh challenger
async function fetchNextTargetSongOnly() {
    try {
        const res  = await fetch(`${API_BASE}/game/pair`);
        const data = await res.json();

        const candidateTarget = (data.song_b.id === trackAnchorA.id) ? data.song_a : data.song_b;

        await preloadCardImages(trackAnchorA.image_url, candidateTarget.image_url);

        trackTargetB = candidateTarget;
        renderGameUIState();
    } catch (err) {
        console.error("fetchNextTargetSongOnly failed:", err);
    }
}

function renderGameUIState() {
    // Left Card (Anchor State)
    document.getElementById("titleA").innerText = trackAnchorA.title;
    document.getElementById("artistA").innerText = trackAnchorA.artist;
    document.getElementById("streamsA").innerText = trackAnchorA.stream_count.toLocaleString();
    
    // Process and attach sanitized source links (Guaranteed to be instantly available!)
    let imgUrlA = trackAnchorA.image_url || "";
    if (imgUrlA.startsWith("//")) imgUrlA = "https:" + imgUrlA;
    document.getElementById("coverA").src = imgUrlA || "https://placehold.co/300x300/1f2937/ffffff?text=No+Cover";

    // Right Card (Challenger State)
    document.getElementById("titleB").innerText = trackTargetB.title;
    document.getElementById("artistB").innerText = trackTargetB.artist;
    document.getElementById("streamsB").innerText = trackTargetB.stream_count.toLocaleString();
    
    let imgUrlB = trackTargetB.image_url || "";
    if (imgUrlB.startsWith("//")) imgUrlB = "https:" + imgUrlB;
    document.getElementById("coverB").src = imgUrlB || "https://placehold.co/300x300/1f2937/ffffff?text=No+Cover";

    // Reset layout visibility modifiers
    document.getElementById("cardB").className = "game-card active-comparison";
    document.getElementById("streamReveal").classList.add("hidden");
    document.getElementById("actionGroup").classList.remove("hidden");
    setButtons(true);

    guessing = false;
}

// ── Core guess logic ─────────────────────────────────────────

async function processPlayerGuess(playerChoice) {
    if (guessing) return;
    guessing = true;
    setButtons(false);

    // Swap UI panels to display the mystery target stream count
    document.getElementById("actionGroup").classList.add("hidden");
    document.getElementById("streamReveal").classList.remove("hidden");

    const countA = trackAnchorA.stream_count;
    const countB = trackTargetB.stream_count;

    const isCorrect =
        (playerChoice === "higher" && countB >= countA) ||
        (playerChoice === "lower"  && countB <= countA);

    // Apply color feedback state indicators
    document.getElementById("cardB").classList.add(isCorrect ? "correct" : "incorrect");

    // Short dramatic suspense pause
    await new Promise(resolve => setTimeout(resolve, 1200));

    if (isCorrect) {
        streakCounter++;
        if (streakCounter > localHighScore) {
            localHighScore = streakCounter;
            document.getElementById("highScore").innerText = localHighScore;
        }
        document.getElementById("currentStreak").innerText = streakCounter;

        // Shift Right Card over to serve as the new baseline left target
        trackAnchorA = trackTargetB;
        fetchNextTargetSongOnly();

    } else {
        alert(
            `❌ Incorrect!\n` +
            `${trackTargetB.title} had ${countB.toLocaleString()} streams\n` +
            `vs ${trackAnchorA.title}'s ${countA.toLocaleString()}.`
        );

        if (streakCounter > 0) {
            await promptLeaderboardSubmission(streakCounter);
        }

        streakCounter = 0;
        document.getElementById("currentStreak").innerText = 0;
        fetchNextGamePairing();
    }
}

// ── Leaderboard ──────────────────────────────────────────────

async function promptLeaderboardSubmission(finalScore) {
    const username = prompt(
        `🎮 Game Over! Streak: ${finalScore}\nEnter your handle for the leaderboard:`
    );
    if (!username || !username.trim()) return;

    try {
        await fetch(`${API_BASE}/game/leaderboard`, {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify({ username: username.trim(), high_score: finalScore }),
        });
        loadLeaderboardData();
    } catch (err) {
        console.error("Leaderboard submit error:", err);
    }
}

async function loadLeaderboardData() {
    const container = document.getElementById("leaderboardContainer");
    try {
        const res    = await fetch(`${API_BASE}/game/leaderboard`);
        const scores = await res.json();

        container.innerHTML = "";
        if (!scores.length) {
            container.innerHTML = "<p style='color:#6b7280;font-size:0.9rem;'>No scores yet — be the first!</p>";
            return;
        }

        scores.forEach((row, index) => {
            const item = document.createElement("div");
            item.className = "leaderboard-item";
            item.innerHTML = `
                <div>
                    <span class="rank-badge">#${index + 1}</span>
                    <span style="color:#fff;font-weight:600;">${row.username}</span>
                </div>
                <span class="streak-badge">${row.high_score} wins</span>
            `;
            container.appendChild(item);
        });
    } catch (err) {
        console.error("Leaderboard load error:", err);
    }
}

// ── Boot sequence initialization ───────────────────────────────
fetchNextGamePairing();
loadLeaderboardData();