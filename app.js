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

        // Safe Fallback: Prevent matching self reference bugs
        trackTargetB = (data.song_b.id === trackAnchorA.id) ? data.song_a : data.song_b;
        renderGameUIState();
    } catch (err) {
        console.error("fetchNextTargetSongOnly failed:", err);
    }
}

function renderGameUIState() {
    // Left Card (Anchor State)
    document.getElementById("titleA").innerText  = trackAnchorA.title;
    document.getElementById("artistA").innerText = trackAnchorA.artist;
    document.getElementById("streamsA").innerText = trackAnchorA.stream_count.toLocaleString();

    // Right Card (Challenger State — hidden until guess action runs)
    document.getElementById("titleB").innerText  = trackTargetB.title;
    document.getElementById("artistB").innerText = trackTargetB.artist;
    document.getElementById("streamsB").innerText = trackTargetB.stream_count.toLocaleString();

    // Reset visual UI layers
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