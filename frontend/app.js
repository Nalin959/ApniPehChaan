/**
 * SovereignPrivacy AI — Frontend Application Logic
 *
 * Manages navigation, WebSocket real-time scanning, API calls,
 * dynamic UI rendering, and all interactive features.
 */

// ═══ State ═══════════════════════════════════════════════════════════════════
const state = {
    currentSection: 'agent',
    scanResults: null,
    selectedJurisdiction: 'dpdp',
    generatedNotice: null,
    complianceRequests: [],
    ws: null,
    isScanning: false,
};

// ═══ Initialization ═════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', () => {
    initParticles();
    initNavigation();
    initScanForm();
    initLegalForm();
    initExposureFilters();
    initProfileSync();
    fetchSystemStatus();
    initRightsAdvisor();
    restoreLatestAgentState();
});

async function restoreLatestAgentState() {
    try {
        const resp = await fetch('/api/agent/latest');
        const data = await resp.json();
        if (data && data.user_id && (data.exposures?.length || data.summary?.exposures_total)) {
            syncAgentToExposuresAndDashboard({ state: data });
        } else {
            renderAgentExposures({ exposures: [] });
        }
    } catch(e) {}
}

// ═══ Particle Background ════════════════════════════════════════════════════
function initParticles() {
    const canvas = document.getElementById('particles-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    let particles = [];
    const particleCount = 60;

    function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    class Particle {
        constructor() { this.reset(); }
        reset() {
            this.x = Math.random() * canvas.width;
            this.y = Math.random() * canvas.height;
            this.vx = (Math.random() - 0.5) * 0.3;
            this.vy = (Math.random() - 0.5) * 0.3;
            this.radius = Math.random() * 1.5 + 0.5;
            this.alpha = Math.random() * 0.4 + 0.1;
        }
        update() {
            this.x += this.vx;
            this.y += this.vy;
            if (this.x < 0 || this.x > canvas.width) this.vx *= -1;
            if (this.y < 0 || this.y > canvas.height) this.vy *= -1;
        }
        draw() {
            ctx.beginPath();
            ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(99, 102, 241, ${this.alpha})`;
            ctx.fill();
        }
    }

    for (let i = 0; i < particleCount; i++) {
        particles.push(new Particle());
    }

    function drawConnections() {
        for (let i = 0; i < particles.length; i++) {
            for (let j = i + 1; j < particles.length; j++) {
                const dx = particles[i].x - particles[j].x;
                const dy = particles[i].y - particles[j].y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < 150) {
                    ctx.beginPath();
                    ctx.moveTo(particles[i].x, particles[i].y);
                    ctx.lineTo(particles[j].x, particles[j].y);
                    ctx.strokeStyle = `rgba(99, 102, 241, ${0.08 * (1 - dist / 150)})`;
                    ctx.lineWidth = 0.5;
                    ctx.stroke();
                }
            }
        }
    }

    function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => { p.update(); p.draw(); });
        drawConnections();
        requestAnimationFrame(animate);
    }
    animate();
}

// ═══ Navigation ═════════════════════════════════════════════════════════════
function initNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            const section = link.dataset.section;
            navigateTo(section);
        });
    });
}

function navigateTo(section) {
    // Update nav
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    const activeLink = document.querySelector(`.nav-link[data-section="${section}"]`);
    if (activeLink) activeLink.classList.add('active');

    // Update sections
    document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
    const activeSection = document.getElementById(`section-${section}`);
    if (activeSection) activeSection.classList.add('active');

    state.currentSection = section;

    // Refresh section data
    if (section === 'compliance') refreshCompliance();
    if (section === 'dashboard') {
        fetchSystemStatus();
        if (state.agentState) updateDashboardFromAgent(state.agentState, state.agentRisk);
    }
    if (section === 'exposures') {
        if (state.agentState) renderAgentExposures(state.agentState);
        else if (state.scanResults) renderExposures(state.scanResults);
        else restoreLatestAgentState();
    }
    if (section === 'legal') {
        prefillLegalForm();
    }

    // Update Rights Advisor
    if (window.RightsAdvisor) {
        window.RightsAdvisor.onTabChange(section);
    }
}

// ═══ System Status ══════════════════════════════════════════════════════════
async function fetchSystemStatus() {
    try {
        const resp = await fetch('/api/status');
        const data = await resp.json();

        document.getElementById('audit-count').textContent = data.audit_trail?.total_receipts || 0;
        document.getElementById('active-requests').textContent = data.compliance_tracker?.total_requests || 0;

        // Prioritize agent results if present
        if (state.agentState) {
            updateDashboardFromAgent(state.agentState, state.agentRisk);
        } else if (state.scanResults) {
            updateDashboardFromResults(state.scanResults);
        }
    } catch (e) {
        console.error('Failed to fetch status:', e);
    }
}

function updateDashboardFromResults(results) {
    const summary = results.summary || {};
    const risk = results.risk_assessment || {};

    // Update stats
    const riskScore = Math.round(risk.overall_score || 0);
    document.getElementById('risk-score-value').textContent = riskScore;
    document.getElementById('breach-count').textContent = summary.total_breaches || 0;
    document.getElementById('broker-count').textContent = summary.total_broker_matches || 0;
    document.getElementById('paste-count').textContent = summary.total_paste_matches || 0;

    // Update risk badge
    const badge = document.getElementById('risk-level-badge');
    badge.textContent = risk.risk_level || 'Unknown';
    badge.style.background = risk.risk_color ? `${risk.risk_color}22` : '';
    badge.style.color = risk.risk_color || '';

    // Update risk card color
    const riskCard = document.getElementById('stat-risk-score');
    if (riskScore >= 60) {
        riskCard.style.borderColor = 'rgba(239, 68, 68, 0.3)';
    } else if (riskScore >= 30) {
        riskCard.style.borderColor = 'rgba(245, 158, 11, 0.3)';
    } else {
        riskCard.style.borderColor = 'rgba(16, 185, 129, 0.3)';
    }

    // Show recommendations
    if (risk.recommendations && risk.recommendations.length > 0) {
        const recsCard = document.getElementById('recommendations-card');
        const recsList = document.getElementById('recommendations-list');
        recsCard.style.display = 'block';
        recsList.innerHTML = risk.recommendations.map(r =>
            `<div class="recommendation-item">${escapeHtml(r)}</div>`
        ).join('');
    }
}

// ═══ Scan Form & WebSocket ══════════════════════════════════════════════════
function initScanForm() {
    const form = document.getElementById('scan-form');
    form.addEventListener('submit', (e) => {
        e.preventDefault();
        startScan();
    });
}

async function startScan() {
    if (state.isScanning) return;
    state.isScanning = true;

    const profile = {
        name: document.getElementById('input-name').value,
        email: document.getElementById('input-email').value,
        phone: document.getElementById('input-phone').value,
        city: document.getElementById('input-city').value,
        pan: document.getElementById('input-pan').value,
        aadhaar: document.getElementById('input-aadhaar').value.replace(/\s/g, ''),
    };

    // UI: switch to scanning state
    const btnContent = document.querySelector('.scan-btn-content');
    const btnLoading = document.querySelector('.scan-btn-loading');
    btnContent.style.display = 'none';
    btnLoading.style.display = 'flex';
    document.getElementById('btn-start-scan').disabled = true;

    // Activate radar
    document.getElementById('radar-sweep').classList.add('active');

    // Clear scan log
    const logEl = document.getElementById('scan-log');
    logEl.innerHTML = '';

    function addLog(text, cls = '') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${cls}`;
        entry.textContent = text;
        logEl.appendChild(entry);
        logEl.scrollTop = logEl.scrollHeight;
    }

    function setProgress(pct) {
        document.getElementById('scan-progress-fill').style.width = `${pct}%`;
    }

    // Try WebSocket first, fall back to REST
    try {
        const wsProtocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${wsProtocol}//${location.host}/ws/scan`);

        ws.onopen = () => {
            addLog('Connection established. Starting scan...', 'log-success');
            ws.send(JSON.stringify({ action: 'start_scan', profile }));
        };

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'scan_step') {
                addLog(msg.detail, msg.step.includes('done') ? 'log-success' : '');
                setProgress(msg.progress);
            } else if (msg.type === 'scan_complete') {
                state.scanResults = msg.results;
                addLog('✓ All scans complete! Processing results...', 'log-success');
                setProgress(100);

                // Update UI
                updateDashboardFromResults(msg.results);
                renderExposures(msg.results);
                showToast('Privacy scan complete!', 'success');

                // Reset button
                finishScan();
                ws.close();
            }
        };

        ws.onerror = () => {
            // Fallback to REST
            addLog('WebSocket unavailable. Falling back to REST API...', 'log-warning');
            ws.close();
            doRestScan(profile, addLog, setProgress);
        };

        ws.onclose = () => {};

    } catch {
        doRestScan(profile, addLog, setProgress);
    }
}

async function doRestScan(profile, addLog, setProgress) {
    try {
        addLog('Starting full privacy scan via REST API...');
        setProgress(10);

        const resp = await fetch('/api/scan/full', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(profile),
        });

        setProgress(80);
        addLog('Processing results...');

        const data = await resp.json();
        state.scanResults = data;

        addLog(`HIBP: ${data.summary?.total_breaches || 0} breach matches`, 'log-success');
        addLog(`Brokers: ${data.summary?.total_broker_matches || 0} high-risk matches`, 'log-success');
        addLog(`Dark Web: ${data.summary?.total_paste_matches || 0} leak matches`, 'log-success');
        addLog(`Risk Score: ${Math.round(data.summary?.risk_score || 0)}/100 (${data.summary?.risk_level})`,
            data.summary?.risk_score >= 60 ? 'log-danger' : 'log-success');

        setProgress(100);
        addLog('✓ Full scan complete!', 'log-success');

        updateDashboardFromResults(data);
        renderExposures(data);
        showToast('Privacy scan complete!', 'success');
    } catch (e) {
        addLog(`Error: ${e.message}`, 'log-danger');
        showToast('Scan failed: ' + e.message, 'error');
    }

    finishScan();
}

function finishScan() {
    state.isScanning = false;
    document.querySelector('.scan-btn-content').style.display = 'flex';
    document.querySelector('.scan-btn-loading').style.display = 'none';
    document.getElementById('btn-start-scan').disabled = false;
    document.getElementById('radar-sweep').classList.remove('active');
}

// ═══ Exposure Rendering ═════════════════════════════════════════════════════
function renderExposures(results) {
    const container = document.getElementById('exposure-cards');
    container.innerHTML = '';

    const cards = [];

    // HIBP Breaches
    if (results.hibp?.breaches) {
        results.hibp.breaches.forEach(breach => {
            cards.push(createExposureCard({
                title: breach.title || breach.name,
                source: 'breach',
                severity: breach.severity || 'medium',
                domain: breach.domain,
                date: breach.breach_date,
                pwnCount: breach.pwn_count,
                dataClasses: breach.data_classes || [],
                type: 'Verified Breach',
                companyName: breach.title || breach.name,
            }));
        });
    }

    // Paste matches
    if (results.pastes?.matches) {
        results.pastes.matches.forEach(match => {
            cards.push(createExposureCard({
                title: `Dark Web Leak: ${match.paste_type.replace('_', ' ')}`,
                source: 'paste',
                severity: match.severity || 'high',
                domain: match.source,
                date: match.date_found?.split('T')[0] || '',
                dataClasses: match.entity_types_found || [],
                entityCount: match.entity_count,
                preview: match.content_preview,
                type: 'Dark Web Paste',
                companyName: match.source,
            }));
        });
    }

    if (cards.length === 0) {
        container.innerHTML = `<div class="glass-card empty-state"><div class="empty-icon">✅</div><h3>No Significant Exposures</h3><p>No critical data exposures were found for the provided identity.</p></div>`;
    } else {
        cards.forEach(card => container.appendChild(card));
    }
}

/* ── Canonical field names → what a person actually reads ─────────────────────
   The backend emits canonical snake_case field names ("government_id"). A card
   is read by someone deciding what to change first, so it names the data the
   way a person would. Anything unmapped is title-cased rather than dropped — a
   field the backend adds later degrades to readable, never to blank. */
const FIELD_LABELS = {
    aadhaar: 'Aadhaar Number', pan: 'PAN', credit_card: 'Credit Card Data',
    bank_account: 'Bank Account Details', password: 'Passwords',
    government_id: 'Government ID', passport: 'Passport Number',
    ssn: 'Social Security Number', auth_token: 'Authentication Tokens',
    security_question: 'Security Questions & Answers',
    session_cookies: 'Session Cookies', religion: 'Religion',
    sexual_preference: 'Sexual Preference', health: 'Health Data',
    ethnicity: 'Ethnicity', biometric: 'Biometric Data',
    address: 'Physical Address', phone: 'Phone Number',
    date_of_birth: 'Date of Birth', private_message: 'Private Messages',
    income: 'Income Level', vehicle: 'Vehicle Details', email: 'Email Address',
    employer: 'Employer', username: 'Username', social_profile: 'Social Profiles',
    photo: 'Profile Photo', purchase: 'Purchase History',
    academic: 'Academic Records', gender: 'Gender', nationality: 'Nationality',
    marital_status: 'Marital Status', ip_address: 'IP Address', city: 'City',
    name: 'Name', age_range: 'Age Range', interests: 'Interests',
    device: 'Device Information', browser: 'Browser Details',
    language: 'Spoken Language', website_activity: 'Website Activity',
};

function fieldLabel(field) {
    const key = String(field == null ? '' : field).trim().toLowerCase();
    if (!key) return '';
    return FIELD_LABELS[key] ||
        key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function fieldLabels(fields) {
    return (fields || []).map(fieldLabel).filter(Boolean);
}

/* ── Info-stealer infection ──────────────────────────────────────────────────
   This is not "a site leaked your address". A computer that held this address
   was infected, so everything saved in its browser — every password, cookie and
   session token — was taken together, and those credentials are CURRENT, not
   historic. It is therefore the one finding that leads the page, carries its
   own card, and ends in three steps rather than a legal notice: there is no
   fiduciary to serve, the data is already in criminal hands.

   Every value shown arrives masked from the source and is rendered exactly as
   received. Nothing here unmasks anything, and the password guard below drops
   any value that is not still masked. */
function looksMasked(value) {
    return /\*/.test(String(value == null ? '' : value));
}

function createInfostealerCard(exp) {
    const d = exp.detail || {};
    const machines = Array.isArray(d.machines) ? d.machines : [];
    const severity = exp.severity || 'critical';

    const card = document.createElement('div');
    card.className = `exposure-card severity-${severity} infostealer-card`;
    card.dataset.source = 'infostealer';
    card.dataset.severity = severity;

    let metaHtml = '';
    if (d.source_dataset) metaHtml += ` · <span>${escapeHtml(d.source_dataset)}</span>`;
    if (machines.length) {
        metaHtml += ` · <span>${machines.length} infected machine${machines.length === 1 ? '' : 's'}</span>`;
    }
    if (d.user_services != null) metaHtml += ` · <span>${escapeHtml(d.user_services)} personal accounts exposed</span>`;
    if (d.corporate_services != null) metaHtml += ` · <span>${escapeHtml(d.corporate_services)} corporate accounts exposed</span>`;

    const machinesHtml = machines.map(m => {
        const rows = [
            ['Computer', m.computer_name],
            ['Operating system', m.operating_system],
            ['Compromised on', (m.date_compromised || '').split('T')[0]],
            ['IP address (masked at source)', m.ip],
            ['Antivirus present', Array.isArray(m.antiviruses) ? m.antiviruses.join(', ') : m.antiviruses],
            ['Malware path', m.malware_path],
        ].filter(([, v]) => v != null && String(v).trim() !== '');

        const rowsHtml = rows.map(([label, value]) => `
            <div class="stealer-row">
                <span class="stealer-row-label">${escapeHtml(label)}</span>
                <span class="stealer-row-value">${escapeHtml(value)}</span>
            </div>`).join('');

        // Logins and passwords are masked by the source. The password list is
        // filtered again here: if a value no longer carries its mask it is not
        // rendered at all, so no upstream change can turn this into a password
        // display.
        const logins = (m.top_logins || []).filter(v => String(v || '').trim() !== '').slice(0, 6);
        const passwords = (m.top_passwords || []).filter(looksMasked).slice(0, 6);

        const loginsHtml = logins.length ? `
            <div class="stealer-creds">
                <span class="stealer-creds-label">Accounts saved on it (masked at source)</span>
                <div class="stealer-creds-tags">${logins.map(v => `<span class="stealer-masked">${escapeHtml(v)}</span>`).join('')}</div>
            </div>` : '';

        const passwordsHtml = passwords.length ? `
            <div class="stealer-creds">
                <span class="stealer-creds-label">Stolen passwords — shown masked, never unmasked</span>
                <div class="stealer-creds-tags">${passwords.map(v => `<span class="stealer-masked">${escapeHtml(v)}</span>`).join('')}</div>
            </div>` : '';

        return `<div class="stealer-machine">${rowsHtml}${loginsHtml}${passwordsHtml}</div>`;
    }).join('');

    const tagsHtml = fieldLabels(exp.data_found || []).map(dc =>
        `<span class="pii-tag pii-tag-danger">${escapeHtml(dc)}</span>`
    ).join('');

    card.innerHTML = `
        <div class="exposure-header">
            <span class="exposure-title">🚨 ${escapeHtml(exp.source_name || 'Info-stealer malware infection')}</span>
            <span class="severity-badge ${escapeHtml(severity)}">${escapeHtml(severity)}</span>
        </div>
        <div class="exposure-meta">Info-Stealer Infection${metaHtml}</div>
        <div class="stealer-lede">Every credential saved in this computer's browser was taken at once — not one site's password, all of them. These credentials are current, not historic, so a stolen session cookie can be replayed without any password at all.</div>
        ${machinesHtml || `<div class="stealer-machine"><div class="stealer-row"><span class="stealer-row-value">The dataset confirmed the infection but returned no machine detail.</span></div></div>`}
        <div class="exposure-tags">${tagsHtml}</div>
        <div class="stealer-fix">
            <div class="stealer-fix-title">Do this now, in this order</div>
            <ol class="stealer-steps">
                <li>Change every password saved in that browser, starting with email and banking — from a different, clean device.</li>
                <li>Sign out of all sessions everywhere, on every account, to kill the stolen session cookies.</li>
                <li>Turn on two-factor authentication everywhere it is offered.</li>
            </ol>
        </div>
        <div class="exposure-actions">
            <span class="stealer-nonotice">No erasure notice applies — this data is in criminal hands, not a company record that can be served.</span>
        </div>
    `;

    return card;
}

function createExposureCard(data) {
    const card = document.createElement('div');
    card.className = `exposure-card severity-${data.severity}`;
    card.dataset.source = data.source;
    card.dataset.severity = data.severity;
    if (data.isCandidate) card.dataset.candidate = 'true';
    if (data.isIndian) card.dataset.indian = 'true';

    // A breach can leak a dozen field types. Show the first six and say how many
    // were held back, rather than silently truncating the list.
    const dataClasses = data.dataClasses || [];
    let tagsHtml = dataClasses.slice(0, 6).map(dc =>
        `<span class="pii-tag">${escapeHtml(dc)}</span>`
    ).join('');
    if (dataClasses.length > 6) {
        tagsHtml += `<span class="pii-tag pii-tag-more">+${dataClasses.length - 6} more</span>`;
    }

    let metaHtml = '';
    if (data.domain) metaHtml += `<span>${escapeHtml(data.domain)}</span>`;
    if (data.date) metaHtml += ` · <span>${escapeHtml(data.date)}</span>`;
    if (data.pwnCount) metaHtml += ` · <span>${escapeHtml(formatNumber(data.pwnCount))} records</span>`;
    if (data.category) metaHtml += ` · <span>${escapeHtml(data.category)}</span>`;
    if (data.removalDifficulty) metaHtml += ` · Removal: ${escapeHtml(data.removalDifficulty)}`;

    // A source that cannot lawfully be served must not offer a notice button.
    //
    // Every value below is third-party: companyName is a breach name from
    // XposedOrNot or a LeakCheck source name, and the URLs come from a search
    // engine or a Gravatar profile. So no button here carries an inline
    // handler. The value goes into a data-* attribute and wireExposureCard()
    // attaches the behaviour, because dataset values are read back by the DOM
    // as plain strings and can never be parsed as code. It also fixes the
    // benign case: a breach named Domino's Pizza used to render a dead button,
    // since the apostrophe closed the JS string literal.
    const optOutUrl = safeUrl(data.optOutUrl);
    const profileUrl = safeUrl(data.profileUrl);
    let actionsHtml = '';
    if (data.isCandidate) {
        actionsHtml = `
            <div class="cand-actions" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                <button class="cand-btn yes" data-act="confirm" data-exposure-id="${escapeHtml(data.exposureId)}" data-mine="1">✓ Yes, mine</button>
                <button class="cand-btn no" data-act="confirm" data-exposure-id="${escapeHtml(data.exposureId)}" data-mine="0">✗ Not me</button>
                ${profileUrl ? `<a href="${escapeHtml(profileUrl)}" target="_blank" rel="noopener noreferrer" class="cand-link" style="margin-left:6px;">View Profile ↗</a>` : ''}
            </div>
        `;
    } else if (data.noNotice) {
        actionsHtml = `<span class="exposure-nonservable">Erasure not available — see basis</span>`;
        if (optOutUrl) {
            actionsHtml += `<a href="${escapeHtml(optOutUrl)}" target="_blank" rel="noopener noreferrer" class="exposure-action-btn danger" style="margin-left:8px;">Opt-Out Link ↗</a>`;
        }
    } else {
        actionsHtml = `<button class="exposure-action-btn" data-act="notice" data-exposure-id="${escapeHtml(data.exposureId || '')}" data-company-name="${escapeHtml(data.companyName || '')}" data-company-email="${escapeHtml(data.companyEmail || '')}">Generate Legal Notice</button>`;
        if (optOutUrl) {
            actionsHtml += `<a href="${escapeHtml(optOutUrl)}" target="_blank" rel="noopener noreferrer" class="exposure-action-btn danger">Opt-Out Link ↗</a>`;
        }
    }

    card.innerHTML = `
        <div class="exposure-header">
            <span class="exposure-title">${escapeHtml(data.title)}</span>
            <span class="severity-badge ${escapeHtml(data.severity)}">${escapeHtml(data.severity)}</span>
        </div>
        <div class="exposure-meta">${escapeHtml(data.type)}${metaHtml ? ' · ' + metaHtml : ''}</div>
        ${data.description ? `<div class="exposure-desc">${escapeHtml(data.description)}</div>` : ''}
        <div class="exposure-tags">${tagsHtml}</div>
        <div class="exposure-actions">${actionsHtml}</div>
    `;

    wireExposureCard(card);
    return card;
}

/* The Agent tab's pattern, applied to the exposure cards: read the value back
   out of dataset and call the handler directly. Nothing untrusted is ever
   compiled as JavaScript, so quotes, backslashes and </script> in a breach name
   are all just characters. */
function wireExposureCard(card) {
    card.querySelectorAll('button[data-act="confirm"]').forEach(btn => {
        btn.addEventListener('click', () =>
            confirmCandidateCard(btn.dataset.exposureId, btn.dataset.mine === '1', btn));
    });
    card.querySelectorAll('button[data-act="notice"]').forEach(btn => {
        btn.addEventListener('click', () =>
            generateNoticeForExposure(btn.dataset.companyName || '', btn.dataset.companyEmail || '', btn.dataset.exposureId || ''));
    });
}

window.confirmCandidateCard = async function(exposureId, isMine, btn) {
    const card = btn.closest('.exposure-card');
    try {
        btn.disabled = true;
        const profile = typeof agProfile === 'function' ? agProfile() : {};
        const resp = await fetch('/api/agent/confirm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...profile, exposure_id: exposureId, is_mine: isMine }),
        });
        if (!resp.ok) {
            const errBody = await resp.json().catch(() => ({}));
            throw new Error(errBody.detail || `Server error (${resp.status})`);
        }
        const data = await resp.json();
        if (card) {
            if (!isMine) {
                card.style.transition = 'all 0.3s ease';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.95)';
                setTimeout(() => card.remove(), 300);
            } else {
                card.classList.remove('severity-low');
                card.classList.add('severity-medium');
                delete card.dataset.candidate;
                const meta = card.querySelector('.exposure-meta');
                if (meta) meta.textContent = 'Confirmed Account · DPDP s.12 Erasure Available';
                const actions = card.querySelector('.exposure-actions');
                if (actions) actions.innerHTML = `<span class="ev-badge ev-verified" style="color:var(--accent-success);font-weight:700;">✓ Confirmed as yours</span>`;
            }
        }
        if (data && data.state) {
            syncAgentToExposuresAndDashboard({ state: data.state });
        }
        showToast(isMine ? 'Account confirmed and added to removal plan' : 'Account dismissed as not yours', 'success');
    } catch(e) {
        btn.disabled = false;
        showToast('Could not update attribution: ' + e.message, 'error');
    }
};

function initExposureFilters() {
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const filter = btn.dataset.filter;
            document.querySelectorAll('.exposure-card').forEach(card => {
                if (filter === 'all') {
                    card.style.display = '';
                } else if (['critical', 'high', 'medium', 'low'].includes(filter)) {
                    card.style.display = card.dataset.severity === filter ? '' : 'none';
                } else if (filter === 'candidates') {
                    card.style.display = card.dataset.candidate === 'true' ? '' : 'none';
                } else if (filter === 'indian') {
                    card.style.display = card.dataset.indian === 'true' ? '' : 'none';
                } else {
                    card.style.display = card.dataset.source === filter ? '' : 'none';
                }
            });
        });
    });
}

// ═══ Legal Remediation ══════════════════════════════════════════════════════
function initLegalForm() {
    // Jurisdiction selector
    document.querySelectorAll('.jurisdiction-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.jurisdiction-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.selectedJurisdiction = btn.dataset.jurisdiction;
        });
    });

    // Form submission
    document.getElementById('legal-form').addEventListener('submit', async (e) => {
        e.preventDefault();
        await generateNotice();
    });

    // Copy button
    document.getElementById('btn-copy-notice').addEventListener('click', () => {
        const preview = document.getElementById('notice-preview-content');
        const liveText = (preview.innerText || preview.textContent || '').trim();
        if (liveText) {
            navigator.clipboard.writeText(liveText).then(() => {
                showToast('Notice copied to clipboard!', 'success');
            });
        }
    });

    // Dispatch button
    document.getElementById('btn-dispatch-notice').addEventListener('click', async () => {
        await dispatchNotice();
    });
}

async function generateNotice() {
    // Auto-fill user data from scan if available
    const userProfile = getSavedProfile();

    const aiTailored = document.getElementById('legal-ai-toggle')?.checked ?? true;
    const payload = {
        jurisdiction: state.selectedJurisdiction,
        user_name: userProfile.name || '',
        user_email: userProfile.email || '',
        user_phone: userProfile.phone || '',
        additional_ids: userProfile.pan ? `PAN: ${userProfile.pan}` : '',
        company_name: document.getElementById('legal-company').value,
        company_email: document.getElementById('legal-company-email').value,
        company_address: document.getElementById('legal-company-address').value,
        detected_pii_summary: document.getElementById('legal-pii-summary').value,
        ai_tailored: aiTailored,
    };

    try {
        const resp = await fetch('/api/legal/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const data = await resp.json();

        if (data.status === 'generated') {
            state.generatedNotice = data;
            renderNoticePreview(data);
            showToast(`${data.jurisdiction_short} notice generated!`, 'success');
        } else {
            showToast('Failed to generate notice', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

const KNOWN_FIDUCIARIES = {
    "iimjobs": {
        company_name: "Info Edge (India) Limited (IIMjobs)",
        dpo_email: "grievance@iimjobs.com",
        address: "B-8, Sector 132, Noida, Uttar Pradesh 201301, India",
        self_serve_url: "https://www.iimjobs.com/settings",
        jurisdiction: "dpdp"
    },
    "zomato": {
        company_name: "Zomato Limited",
        dpo_email: "grievance@zomato.com",
        address: "Ground Floor, 12A, 94 Meghdoot, Nehru Place, New Delhi 110019, India",
        self_serve_url: "https://www.zomato.com/privacy",
        jurisdiction: "dpdp"
    },
    "yatra": {
        company_name: "Yatra Online Limited",
        dpo_email: "grievance@yatra.com",
        address: "Gulf Adiba, 4th Floor, Plot No. 272, Phase II, Udyog Vihar, Gurugram, Haryana 122008, India",
        self_serve_url: "https://www.yatra.com/",
        jurisdiction: "dpdp"
    },
    "linkedin": {
        company_name: "LinkedIn Ireland UC / LinkedIn India Pvt Ltd",
        dpo_email: "linkedin_dpo@linkedin.com",
        address: "Tower A, Global Technology Park, Outer Ring Road, Bengaluru 560103, Karnataka, India",
        self_serve_url: "https://www.linkedin.com/psettings/account-management/close-account",
        jurisdiction: "dpdp"
    },
    "canva": {
        company_name: "Canva Pty Ltd",
        dpo_email: "privacy@canva.com",
        address: "110 Kippax St, Surry Hills NSW 2010, Australia",
        self_serve_url: "https://www.canva.com/settings/your-account",
        jurisdiction: "gdpr"
    },
    "bigbasket": {
        company_name: "Supermarket Grocery Supplies Pvt. Ltd. (BigBasket / Tata Enterprise)",
        dpo_email: "grievance@bigbasket.com",
        address: "2nd Floor, Fairway Business Park, Challaghatta Village, Domlur, Bengaluru 560071, Karnataka, India",
        self_serve_url: "https://www.bigbasket.com/",
        jurisdiction: "dpdp"
    },
    "naukri": {
        company_name: "Info Edge (India) Limited (Naukri.com)",
        dpo_email: "grievance@naukri.com",
        address: "B-8, Sector 132, Noida, Uttar Pradesh 201301, India",
        self_serve_url: "https://www.naukri.com/",
        jurisdiction: "dpdp"
    },
    "jeevansathi": {
        company_name: "Info Edge (India) Limited (Jeevansathi)",
        dpo_email: "grievance@jeevansathi.com",
        address: "B-8, Sector 132, Noida, Uttar Pradesh 201301, India",
        self_serve_url: "https://www.jeevansathi.com/",
        jurisdiction: "dpdp"
    },
    "shaadi": {
        company_name: "People Interactive (India) Private Limited (Shaadi.com)",
        dpo_email: "grievanceofficer@peopleinteractive.in",
        address: "Ground Floor, Film Centre, 68 Tardeo Road, Mumbai 400034, Maharashtra, India",
        self_serve_url: "https://www.shaadi.com/",
        jurisdiction: "dpdp"
    },
    "bharatmatrimony": {
        company_name: "Matrimony.com Limited (BharatMatrimony)",
        dpo_email: "grievanceofficer@matrimony.com",
        address: "No.94, TVH Beliciaa Towers, MRC Nagar, Chennai 600028, Tamil Nadu, India",
        self_serve_url: "https://www.bharatmatrimony.com/",
        jurisdiction: "dpdp"
    },
    "dominos": {
        company_name: "Jubilant FoodWorks Limited (Domino's Pizza India)",
        dpo_email: "grievance@jublfood.com",
        address: "Plot 1A, Sector 16A, Noida 201301, Uttar Pradesh, India",
        self_serve_url: "https://pizzaonline.dominos.co.in/",
        jurisdiction: "dpdp"
    },
    "airindia": {
        company_name: "Air India Limited (Tata Group)",
        dpo_email: "grievance@airindia.com",
        address: "Airlines House, 113 Gurudwara Rakabganj Road, New Delhi 110001, India",
        self_serve_url: "https://www.airindia.com/",
        jurisdiction: "dpdp"
    },
    "upstox": {
        company_name: "RKSV Securities India Private Limited (Upstox)",
        dpo_email: "grievance@upstox.com",
        address: "807, New Delhi House, Barakhamba Road, Connaught Place, New Delhi 110001, India",
        self_serve_url: "https://upstox.com/",
        jurisdiction: "dpdp"
    },
    "apollo247": {
        company_name: "Apollo Hospitals Enterprise Limited (Apollo 24|7)",
        dpo_email: "grievance@apollo247.com",
        address: "19 Bishop Gardens, Raja Annamalaipuram, Chennai 600028, Tamil Nadu, India",
        self_serve_url: "https://www.apollo247.com/",
        jurisdiction: "dpdp"
    },
    "adobe": {
        company_name: "Adobe Systems India Pvt. Ltd.",
        dpo_email: "dpo@adobe.com",
        address: "Adobe Towers, Sector 132, Expressway, Noida 201305, Uttar Pradesh, India",
        self_serve_url: "https://account.adobe.com/privacy",
        jurisdiction: "dpdp"
    },
    "dropbox": {
        company_name: "Dropbox, Inc.",
        dpo_email: "privacy@dropbox.com",
        address: "1800 Owens Street, San Francisco, CA 94158, USA",
        self_serve_url: "https://www.dropbox.com/account/delete",
        jurisdiction: "ccpa"
    },
    "truecaller": {
        company_name: "Truecaller AB / True Software Scandinavia",
        dpo_email: "dpo@truecaller.com",
        address: "Mäster Samuelsgatan 56, 111 21 Stockholm, Sweden",
        self_serve_url: "https://www.truecaller.com/unlisting",
        jurisdiction: "dpdp"
    },
    "gravatar": {
        company_name: "Automattic Inc. (Gravatar)",
        dpo_email: "privacypolicy@automattic.com",
        address: "60 29th Street #343, San Francisco, CA 94110, USA",
        self_serve_url: "https://en.gravatar.com/profiles/edit",
        jurisdiction: "ccpa"
    },
    "github": {
        company_name: "GitHub, Inc. (Microsoft)",
        dpo_email: "privacy@github.com",
        address: "88 Colin P Kelly Jr St, San Francisco, CA 94107, USA",
        self_serve_url: "https://github.com/settings/admin",
        jurisdiction: "ccpa"
    }
};

function getFiduciaryContact(nameOrId) {
    if (!nameOrId) return {};
    const clean = nameOrId.toLowerCase().replace(/[^a-z0-9]/g, '');
    for (const [key, spec] of Object.entries(KNOWN_FIDUCIARIES)) {
        if (clean.includes(key) || key.includes(clean)) return Object.assign({}, spec);
    }
    if (window.__indianSources?.length) {
        const found = window.__indianSources.find(s => {
            const sc = (s.name || '').toLowerCase().replace(/[^a-z0-9]/g, '');
            return sc.includes(clean) || clean.includes(sc);
        });
        if (found) {
            return {
                company_name: found.operator || found.name,
                dpo_email: found.privacy_email || `grievance@${clean}.in`,
                address: found.address || `${found.name} Corporate Office, India`,
                self_serve_url: found.removal_url || found.website || '',
                jurisdiction: found.jurisdiction || 'dpdp'
            };
        }
    }
    return {
        company_name: `${nameOrId} Data Fiduciary`,
        dpo_email: `privacy@${clean}.com`,
        address: `Corporate Grievance Office, ${nameOrId} Registered Headquarters`,
        self_serve_url: `https://${clean}.com/privacy`,
        jurisdiction: 'dpdp'
    };
}

function generateNoticeForExposure(companyName, companyEmail, exposureId) {
    navigateTo('legal');
    const contact = getFiduciaryContact(companyName);

    const compEl = document.getElementById('legal-company');
    if (compEl) compEl.value = contact.company_name || companyName || '';

    const emailEl = document.getElementById('legal-company-email');
    if (emailEl) emailEl.value = contact.dpo_email || companyEmail || '';

    const addrEl = document.getElementById('legal-company-address');
    if (addrEl) addrEl.value = contact.address || '';

    if (contact.jurisdiction) {
        const jurisEl = document.getElementById('legal-jurisdiction');
        if (jurisEl) jurisEl.value = contact.jurisdiction;
    }

    const piiSummary = buildComprehensivePIISummary(companyName, exposureId);
    const piiEl = document.getElementById('legal-pii-summary');
    if (piiEl) piiEl.value = piiSummary;
}

function buildComprehensivePIISummary(companyName, exposureId) {
    const parts = [];
    const prof = typeof agProfile === 'function' ? agProfile() : {};
    if (prof.name) parts.push(`• Data Principal: ${prof.name}`);
    if (prof.email) parts.push(`• Primary Email: ${prof.email}`);
    if (prof.phone) parts.push(`• Registered Mobile: ${prof.phone}`);
    if (prof.aadhaar) parts.push(`• National Identity Reference: Resident Identification Verified`);

    const exposures = state.agentState?.exposures || [];
    let targetExp = exposures.find(e => e.id === exposureId);
    if (!targetExp && companyName) {
        const cClean = companyName.toLowerCase();
        targetExp = exposures.find(e => (e.source_name || '').toLowerCase().includes(cClean));
    }

    if (targetExp && targetExp.data_found?.length) {
        parts.push(`• Compromised / Processed Categories in ${targetExp.source_name}:`);
        targetExp.data_found.forEach(df => parts.push(`  - ${df}`));
    } else if (state.scanResults?.risk_assessment?.breakdown?.entity_counts) {
        for (const [type, count] of Object.entries(state.scanResults.risk_assessment.breakdown.entity_counts)) {
            parts.push(`  - ${type}: ${count} instance(s) detected`);
        }
    } else {
        parts.push(`• Processed Categories: Account profile, contact records, and stored authentication metadata.`);
    }
    parts.push(`\nStatutory grounds: Personal data is no longer necessary for the original processing purpose and/or consent is explicitly withdrawn under Section 12 of DPDP Act 2023.`);
    return parts.join('\n');
}

function buildPIISummary() {
    return buildComprehensivePIISummary('', '');
}

function renderNoticePreview(data) {
    const preview = document.getElementById('notice-preview-content');
    preview.textContent = data.notice_text;

    // Make the notice text editable so user can tweak before dispatch
    preview.contentEditable = 'true';
    preview.spellcheck = false;
    preview.setAttribute('data-editable', 'true');

    // Show action buttons
    document.getElementById('btn-copy-notice').style.display = '';
    document.getElementById('btn-dispatch-notice').style.display = '';

    // Show AI badge if notice was generated via LLM
    const aiBadge = document.getElementById('notice-ai-badge');
    if (aiBadge) {
        if (data.ai_generated) {
            aiBadge.style.display = 'inline-flex';
            aiBadge.textContent = `✨ AI-Drafted (${data.ai_model || 'Gemini'})`;
        } else {
            aiBadge.style.display = 'none';
        }
    }

    // Show receipt
    const receipt = document.getElementById('notice-receipt');
    receipt.style.display = '';
    document.getElementById('receipt-ref-id').textContent = data.reference_id;
    document.getElementById('receipt-hash').textContent = data.receipt_hash;
    document.getElementById('receipt-deadline').textContent =
        `${data.response_deadline_days} days (${new Date(data.response_deadline).toLocaleDateString()})`;
}

async function dispatchNotice() {
    if (!state.generatedNotice) return;

    const data = state.generatedNotice;

    // Get the (possibly edited) notice text from the editable preview
    const preview = document.getElementById('notice-preview-content');
    const noticeBody = (preview.innerText || preview.textContent || '').trim();

    // Recipient email from the form field
    const recipientEmail = (document.getElementById('legal-company-email').value || '').trim();
    const companyName = data.recipient?.company_name || document.getElementById('legal-company').value || 'Data Controller';

    // Build subject line
    const subject = `Data Erasure / Privacy Notice – ${companyName} [Ref: ${data.reference_id || ''}]`;

    // Open the default mail client via mailto: link
    const mailtoUrl = `mailto:${encodeURIComponent(recipientEmail)}` +
        `?subject=${encodeURIComponent(subject)}` +
        `&body=${encodeURIComponent(noticeBody)}`;

    window.open(mailtoUrl, '_blank');

    // Also persist dispatch to backend for compliance tracking
    const payload = {
        jurisdiction: data.jurisdiction,
        company_name: companyName,
        company_email: recipientEmail,
        user_name: data.sender.name,
        user_email: data.sender.email,
        notice_reference: data.reference_id,
        receipt_hash: data.receipt_hash,
    };

    try {
        const resp = await fetch('/api/legal/dispatch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        const result = await resp.json();

        if (result.status === 'dispatched') {
            showToast(result.message + ' — Mail app opened.', 'success');
            navigateTo('compliance');
        } else {
            showToast('Notice opened in mail app. Backend dispatch failed — track manually.', 'warning');
        }
    } catch (e) {
        // mailto already opened, so the user can still send — just warn about tracking
        showToast('Mail app opened. Backend tracking error: ' + e.message, 'warning');
    }
}

// ═══ Compliance Tracker ═════════════════════════════════════════════════════
async function refreshCompliance() {
    try {
        const resp = await fetch('/api/compliance/requests');
        const data = await resp.json();
        renderComplianceRequests(data.requests || []);
    } catch (e) {
        console.error('Failed to refresh compliance:', e);
    }
}

function renderComplianceRequests(requests) {
    const container = document.getElementById('compliance-content');

    if (!requests.length) {
        container.innerHTML = `<div class="glass-card empty-state"><div class="empty-icon">⏱️</div><h3>No Active Requests</h3><p>Generate and dispatch a legal notice to begin tracking statutory compliance deadlines.</p><button class="action-btn primary-action" data-act="goto-legal">Go to Legal Studio</button></div>`;
        const goLegal = container.querySelector('button[data-act="goto-legal"]');
        if (goLegal) goLegal.addEventListener('click', () => navigateTo('legal'));
        return;
    }

    container.innerHTML = requests.map(req => {
        const progressColor = req.is_overdue ? 'var(--accent-danger)' :
            req.progress_pct > 70 ? 'var(--accent-warning)' : 'var(--accent-primary)';

        const milestonesHtml = (req.milestones || []).map((ms, i) => {
            const isCompleted = ms.status === 'completed';
            const isNext = !isCompleted && i === (req.milestones || []).findIndex(m => m.status !== 'completed');
            return `
                <div class="timeline-item ${isCompleted ? 'completed' : ''} ${isNext ? 'active' : ''}">
                    <span class="timeline-label">${escapeHtml(ms.label)}</span>
                    <span class="timeline-date">${escapeHtml(new Date(ms.date).toLocaleDateString())} (Day ${escapeHtml(ms.day)})</span>
                </div>
            `;
        }).join('');

        return `
            <div class="compliance-request-card">
                <div class="compliance-header">
                    <span class="compliance-title">${escapeHtml(req.company_name)}</span>
                    <span class="compliance-status ${escapeHtml(req.status)}">${escapeHtml(req.status)}</span>
                </div>
                <div class="compliance-meta">
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Jurisdiction</div>
                        <div class="compliance-meta-value">${escapeHtml(String(req.jurisdiction || '').toUpperCase())}</div>
                    </div>
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Days Remaining</div>
                        <div class="compliance-meta-value" style="color: ${req.is_overdue ? 'var(--accent-danger)' : 'var(--text-primary)'}">${req.is_overdue ? 'OVERDUE' : escapeHtml(req.days_remaining) + ' days'}</div>
                    </div>
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Reference</div>
                        <div class="compliance-meta-value" style="font-family: var(--font-mono); font-size: 0.75rem;">${escapeHtml(req.notice_reference)}</div>
                    </div>
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Request ID</div>
                        <div class="compliance-meta-value" style="font-family: var(--font-mono); font-size: 0.75rem;">${escapeHtml(req.request_id)}</div>
                    </div>
                </div>
                <div class="compliance-progress-bar">
                    <div class="compliance-progress-fill" style="width: ${Number(req.progress_pct) || 0}%; background: ${progressColor};"></div>
                </div>
                <div class="compliance-timeline">${milestonesHtml}</div>
                <div class="compliance-actions">
                    <button class="exposure-action-btn" data-act="req-status" data-req-id="${escapeHtml(req.request_id)}" data-status="acknowledged" data-note="Company acknowledged receipt">Mark Acknowledged</button>
                    <button class="exposure-action-btn" data-act="req-status" data-req-id="${escapeHtml(req.request_id)}" data-status="completed" data-note="Data deletion confirmed">Mark Completed</button>
                    <button class="exposure-action-btn danger" data-act="req-status" data-req-id="${escapeHtml(req.request_id)}" data-status="escalated" data-note="Escalated to ${req.jurisdiction === 'dpdp' ? 'DPBI' : 'Supervisory Authority'}">Escalate</button>
                </div>
            </div>
        `;
    }).join('');

    container.querySelectorAll('button[data-act="req-status"]').forEach(btn => {
        btn.addEventListener('click', () =>
            updateRequestStatus(btn.dataset.reqId, btn.dataset.status, btn.dataset.note));
    });
}

async function updateRequestStatus(requestId, status, note) {
    try {
        const resp = await fetch('/api/compliance/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ request_id: requestId, status, note }),
        });
        const data = await resp.json();
        showToast(`Status updated to: ${status}`, 'success');
        refreshCompliance();
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ═══ Utilities ══════════════════════════════════════════════════════════════
/* Escapes the five characters that can change the meaning of HTML text OR of a
   double-quoted attribute value. The previous textContent -> innerHTML form
   escaped only & < >, leaving " and ' intact, so any third-party string could
   close the attribute it sat in and open new ones.

   This is sufficient for TEXT and for QUOTED ATTRIBUTE positions and nowhere
   else. It is deliberately NOT sufficient for two positions, which is why no
   third-party value in this file is rendered into either:
     - inside inline handler JavaScript (onclick="..."): the HTML parser decodes
       &#39; back to ' before the JS parser runs, so escaping cannot secure a JS
       string literal. Use data-* attributes + addEventListener instead.
     - inside an href/src URL: the scheme is not a quoting problem. Use
       safeUrl() below. */
function escapeHtml(str) {
    return String(str == null ? '' : str).replace(/[&<>"']/g,
        c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* A URL from a search engine, a Gravatar profile or a broker record is
   third-party data, and escaping does nothing to `javascript:alert(1)` — the
   parser decodes entities before the navigation happens. Only http and https
   may reach an href; every other scheme, and anything not recognisable as an
   absolute web URL, becomes '' and the caller then renders no link at all. */
function safeUrl(value) {
    const raw = String(value == null ? '' : value).trim();
    if (!raw) return '';
    // Browsers strip control characters and whitespace while parsing a scheme,
    // so "java\tscript:x" still navigates. Test a stripped copy, and accept the
    // value only if that stripped copy is plainly http(s).
    const probe = raw.replace(/[\u0000-\u0020\u007f-\u00a0\u2028\u2029]/g, '').toLowerCase();
    if (!/^https?:\/\//.test(probe)) return '';
    // Percent-encode the characters that have structural meaning in HTML. They
    // are not legal in a URL unencoded anyway, and encoding them here means the
    // returned value cannot break out of an attribute even if a future caller
    // forgets to escape it. The link still works.
    const ENC = { '"': '%22', "'": '%27', '<': '%3C', '>': '%3E', '`': '%60' };
    return raw.replace(/["'<>`\s]/g, c => ENC[c] ||
        '%' + c.charCodeAt(0).toString(16).toUpperCase().padStart(2, '0'));
}

/* ── Markdown to HTML Renderer ─────────────────────────────────────────────
   Converts structured LLM summaries (headings, GFM tables, numbered/bullet
   lists, code spans, links, and bold/italic markup) into clean, secure HTML. */
function formatInlineMarkdown(str) {
    if (!str) return '';
    let s = escapeHtml(str);

    // 1. Protect code spans
    const codeSpans = [];
    s = s.replace(/`([^`]+)`/g, (match, code) => {
        const id = `@@CODE${codeSpans.length}@@`;
        codeSpans.push(`<code class="summary-code">${code}</code>`);
        return id;
    });

    // 2. Links: [text](url) - only http/https allowed via safeUrl
    const links = [];
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^\s\)"'<>]+)\)/g, (match, text, url) => {
        const clean = safeUrl(url);
        if (!clean) return text;
        const id = `@@LINK${links.length}@@`;
        links.push(`<a href="${clean}" target="_blank" rel="noopener noreferrer" class="summary-link">${text}</a>`);
        return id;
    });

    // 3. Bold: **text** or __text__
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');

    // 4. Italic: *text* or _text_ with word-boundary awareness (GFM: no intra-word underscores)
    s = s.replace(/(^|[^\*])\*([^*\s][^*]*[^*\s]|\S)\*(?!\*)/g, '$1<em>$2</em>');
    s = s.replace(/(^|[\s(])_([^_\s][^_]*[^_\s]|\S)_(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>');

    // 5. Restore links & code spans
    s = s.replace(/@@LINK(\d+)@@/g, (m, idx) => links[Number(idx)] || '');
    s = s.replace(/@@CODE(\d+)@@/g, (m, idx) => codeSpans[Number(idx)] || '');

    return s;
}

function preprocessMarkdown(text) {
    if (!text) return '';
    let raw = String(text).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (raw.includes('\\n') && !raw.includes('\n')) {
        raw = raw.replace(/\\n/g, '\n');
    }

    // Defensive fixes if markdown was flattened or lacks breaks:
    raw = raw.replace(/\|\s*\|/g, '|\n|');
    raw = raw.replace(/\s*---\s*(#{1,6}\s+)/g, '\n\n---\n\n$1');
    raw = raw.replace(/([.!?])\s*---\s*/g, '$1\n\n---\n\n');
    raw = raw.replace(/(#{1,6}\s+[^|\n]+?)\s+(\|)/g, '$1\n\n$2');
    raw = raw.replace(/(#{1,6}\s+[^\d\n]+?)\s+(\d+\.\s+\*\*)/g, '$1\n\n$2');
    raw = raw.replace(/([.!?|])\s*(#{1,6}\s+[A-Za-z])/g, '$1\n\n$2');
    raw = raw.replace(/\|\s*(\*[A-Z])/g, '|\n\n$1');
    raw = raw.replace(/^(#{1,6}\s+(?:Executive Summary|Summary of Remediation Routes|Concrete Next Actions[A-Za-z ]*?))\s+([A-Z0-9])/gim, '$1\n\n$2');
    raw = raw.replace(/([.!?])\s*(\d+\.\s+\*\*)/g, '$1\n\n$2');

    return raw;
}

function renderMarkdown(text) {
    if (!text) return '';
    const raw = preprocessMarkdown(text);
    const lines = raw.split('\n');
    const out = [];
    let i = 0;

    const isHr = (line) => /^\s*([-*_]){3,}\s*$/.test(line);
    const isHeading = (line) => /^\s*#{1,6}\s+/.test(line);
    const isTopOl = (line) => /^\s{0,3}\d+\.\s+/.test(line);
    const isTopUl = (line) => /^\s{0,3}[-*•]\s+/.test(line);
    const isTableRow = (line) => /^\s*\|.*\|\s*$/.test(line);
    const isTableSep = (line) => /^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$/.test(line);

    while (i < lines.length) {
        const line = lines[i];
        const trimmed = line.trim();

        if (!trimmed) {
            i++;
            continue;
        }

        if (isHr(trimmed)) {
            out.push('<hr class="summary-hr">');
            i++;
            continue;
        }

        const headingMatch = trimmed.match(/^\s*(#{1,6})\s+(.*)$/);
        if (headingMatch) {
            const level = Math.min(6, Math.max(2, headingMatch[1].length + 1));
            out.push(`<h${level} class="summary-heading">${formatInlineMarkdown(headingMatch[2])}</h${level}>`);
            i++;
            continue;
        }

        // Markdown Table
        if (isTableRow(trimmed) && i + 1 < lines.length && isTableSep(lines[i + 1])) {
            const parseCells = (rowStr) => {
                let s = rowStr.trim();
                if (s.startsWith('|')) s = s.substring(1);
                if (s.endsWith('|')) s = s.substring(0, s.length - 1);
                return s.split('|').map(c => c.trim());
            };

            const headers = parseCells(trimmed);
            i += 2;

            const rows = [];
            while (i < lines.length && isTableRow(lines[i])) {
                const cells = parseCells(lines[i]);
                rows.push(cells);
                i++;
            }

            let tableHtml = '<div class="summary-table-wrap"><table class="summary-table">';
            tableHtml += '<thead><tr>' + headers.map(h => `<th>${formatInlineMarkdown(h)}</th>`).join('') + '</tr></thead>';
            tableHtml += '<tbody>';
            for (const r of rows) {
                tableHtml += '<tr>' + r.map(c => {
                    let tdContent = formatInlineMarkdown(c);
                    const lower = c.toLowerCase();
                    let cls = '';
                    if (lower.includes('critical')) cls = ' class="td-severity-crit"';
                    else if (lower.includes('high')) cls = ' class="td-severity-high"';
                    else if (lower.includes('medium')) cls = ' class="td-severity-med"';
                    return `<td${cls}>${tdContent}</td>`;
                }).join('') + '</tr>';
            }
            tableHtml += '</tbody></table></div>';
            out.push(tableHtml);
            continue;
        }

        // Top-level Ordered List (with potential nested bullets or continuations)
        if (isTopOl(line)) {
            let listHtml = '<ol class="summary-ol">';
            while (i < lines.length) {
                const cur = lines[i];
                const m = cur.match(/^\s{0,3}(\d+)\.\s+(.*)$/);
                if (m) {
                    let itemText = formatInlineMarkdown(m[2]);
                    i++;
                    const subBullets = [];
                    while (i < lines.length) {
                        const sub = lines[i];
                        const subTrim = sub.trim();
                        if (!subTrim) {
                            let nextIdx = i + 1;
                            while (nextIdx < lines.length && !lines[nextIdx].trim()) nextIdx++;
                            if (nextIdx < lines.length && (isTopOl(lines[nextIdx]) || /^\s{2,}/.test(lines[nextIdx]))) {
                                i = nextIdx;
                                continue;
                            }
                            break;
                        }
                        const subM = sub.match(/^\s{2,}[-*•]\s+(.*)$/);
                        if (subM) {
                            subBullets.push(formatInlineMarkdown(subM[1]));
                            i++;
                        } else if (/^\s{2,}\S/.test(sub) && !isTopOl(sub) && !isTopUl(sub) && !isHr(subTrim) && !isHeading(subTrim)) {
                            itemText += ' ' + formatInlineMarkdown(subTrim);
                            i++;
                        } else {
                            break;
                        }
                    }
                    let subHtml = '';
                    if (subBullets.length > 0) {
                        subHtml = '<ul class="summary-sub-ul">' + subBullets.map(b => `<li>${b}</li>`).join('') + '</ul>';
                    }
                    listHtml += `<li>${itemText}${subHtml}</li>`;
                } else {
                    break;
                }
            }
            listHtml += '</ol>';
            out.push(listHtml);
            continue;
        }

        // Top-level Unordered List
        if (isTopUl(line)) {
            let listHtml = '<ul class="summary-ul">';
            while (i < lines.length) {
                const cur = lines[i];
                const m = cur.match(/^\s{0,3}[-*•]\s+(.*)$/);
                if (m) {
                    let itemText = formatInlineMarkdown(m[1]);
                    i++;
                    const subBullets = [];
                    while (i < lines.length) {
                        const sub = lines[i];
                        const subTrim = sub.trim();
                        if (!subTrim) {
                            let nextIdx = i + 1;
                            while (nextIdx < lines.length && !lines[nextIdx].trim()) nextIdx++;
                            if (nextIdx < lines.length && (isTopUl(lines[nextIdx]) || /^\s{2,}/.test(lines[nextIdx]))) {
                                i = nextIdx;
                                continue;
                            }
                            break;
                        }
                        const subM = sub.match(/^\s{2,}[-*•]\s+(.*)$/);
                        if (subM) {
                            subBullets.push(formatInlineMarkdown(subM[1]));
                            i++;
                        } else if (/^\s{2,}\S/.test(sub) && !isTopUl(sub) && !isTopOl(sub) && !isHr(subTrim) && !isHeading(subTrim)) {
                            itemText += ' ' + formatInlineMarkdown(subTrim);
                            i++;
                        } else {
                            break;
                        }
                    }
                    let subHtml = '';
                    if (subBullets.length > 0) {
                        subHtml = '<ul class="summary-sub-ul">' + subBullets.map(b => `<li>${b}</li>`).join('') + '</ul>';
                    }
                    listHtml += `<li>${itemText}${subHtml}</li>`;
                } else {
                    break;
                }
            }
            listHtml += '</ul>';
            out.push(listHtml);
            continue;
        }

        // Regular Paragraph
        const paraLines = [];
        while (i < lines.length) {
            const cur = lines[i];
            const curTrim = cur.trim();
            if (!curTrim || isHr(curTrim) || isHeading(curTrim) || isTopOl(cur) || isTopUl(cur) || (isTableRow(curTrim) && i + 1 < lines.length && isTableSep(lines[i + 1]))) {
                break;
            }
            paraLines.push(curTrim);
            i++;
        }
        if (paraLines.length > 0) {
            out.push(`<p class="summary-p">${formatInlineMarkdown(paraLines.join(' '))}</p>`);
        }
    }

    return out.join('\n');
}

function formatNumber(n) {
    if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
    if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
    if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
    return String(n);
}

function getSavedProfile() {
    return {
        name: document.getElementById('input-name')?.value || '',
        email: document.getElementById('input-email')?.value || '',
        phone: document.getElementById('input-phone')?.value || '',
        pan: document.getElementById('input-pan')?.value || '',
    };
}

function showToast(message, type = 'info') {
    // Remove existing toasts
    document.querySelectorAll('.toast').forEach(t => t.remove());

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'toastOut 0.3s ease-out forwards';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

/* ═══════════════════════════════════════════════════════════════════════════
   PRIVACY AGENT
   Streams the agent's real execution over /ws/agent. Every line appears when
   the agent actually reaches that step — there is no scripted animation.
   ═══════════════════════════════════════════════════════════════════════════ */

const Agent = {
    ws: null,
    profile: null,
    userId: null,
    riskBefore: null,
    drafted: [],
    busy: false,
    steps: 0,
    startedAt: 0,
    timer: null,
};

function agEl(id) { return document.getElementById(id); }

function agProfile() {
    return {
        name: agEl('ag-name').value.trim(),
        email: agEl('ag-email').value.trim(),
        phone: getMultiValues('ag-phone').join(', '),
        city: agEl('ag-city').value.trim(),
        country: agEl('ag-country').value,
        declared_accounts: (agEl('ag-declared')?.value || '').trim(),
        password: (agEl('ag-password')?.value || ''),
        known_usernames: (agEl('ag-usernames')?.value || '').trim(),
        alt_emails: (agEl('ag-altemails')?.value || '').trim(),
        alt_phones: getMultiValues('ag-altphones').join(', '),
        date_of_birth: (agEl('ag-dob')?.value || '').trim(),
        upi_id: getMultiValues('ag-upi').join(', '),
        websites: getMultiValues('ag-websites').join(', '),
        search_guessed_handles: agEl('ag-guess') ? agEl('ag-guess').checked : true,
        aadhaar: (agEl('ag-aadhaar')?.value || '').trim(),
        pan: (agEl('ag-pan')?.value || '').trim(),
    };
}

function traceClear() {
    agEl('agent-trace').innerHTML =
        '<div class="trace-empty">The agent\'s reasoning and every tool call will stream here in real time.</div>';
}

function traceAdd(agent, message, status) {
    if (!message) return;
    if (message.length > 350) {
        const summaryCard = agEl('agent-summary');
        if (summaryCard && !summaryCard.innerHTML.trim()) {
            summaryCard.innerHTML = renderMarkdown(message);
        }
        return;
    }
    const box = agEl('agent-trace');
    if (!box) return;
    const empty = box.querySelector('.trace-empty');
    if (empty) empty.remove();
    const row = document.createElement('div');
    row.className = 'trace-row' + (status === 'error' ? ' err' : '') +
                    (status === 'awaiting_approval' ? ' approval' : '');
    const a = document.createElement('span');
    a.className = 'trace-agent a-' + (agent || 'orchestrator');
    const AGENT_LABELS = {
        forensics: '🕵️ Forensics',
        legal_counsel: '⚖️ Legal',
        remediation: '🛡️ Remediation',
        swarm_coordinator: '🤖 Lead',
        orchestrator: '⚡ Swarm',
        identity: '🪪 Identity',
        discovery: '🔍 Discovery',
        risk: '📊 Risk',
        action: '📝 Action',
        followup: '⏱️ Followup',
        verification: '✅ Verify'
    };
    a.textContent = AGENT_LABELS[agent] || agent || 'agent';
    const m = document.createElement('span');
    m.className = 'trace-msg';
    m.textContent = message;
    row.append(a, m);
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
}

function renderThreatSurface(data) {
    const container = document.getElementById('threat-surface-container');
    const grid = document.getElementById('threat-vectors-grid');
    const gradeEl = document.getElementById('threat-surface-grade');
    if (!container || !grid) return;

    if (!data) {
        container.hidden = true;
        return;
    }

    const vectors = data.threat_vectors || data.vectors || [];
    if (!vectors.length) {
        container.hidden = true;
        return;
    }

    const grade = (data.overall_surface_grade || 'MODERATE').toUpperCase();
    if (gradeEl) {
        gradeEl.textContent = grade;
        gradeEl.className = 'threat-surface-grade ' + grade;
    }

    grid.innerHTML = '';
    vectors.forEach(v => {
        const card = document.createElement('div');
        card.className = 'threat-vector-card';
        const sev = (v.severity || 'medium').toLowerCase();
        const sources = (v.affected_sources || []).join(', ');

        card.innerHTML = `
            <div class="threat-vector-top">
                <div class="threat-vector-name">${agEsc(v.vector || 'Compound Threat Vector')}</div>
                <span class="threat-vector-sev ${sev}">${sev}</span>
            </div>
            ${sources ? `<div class="threat-vector-sources">Correlated Sources: <span>${agEsc(sources)}</span></div>` : ''}
            <div class="threat-vector-model">${agEsc(v.adversary_playbook || v.threat_model || 'Adversary leverages correlated credentials and contact telemetry across services.')}</div>
            <div class="threat-vector-fix"><strong>Shield Action:</strong> ${agEsc(v.blue_team_mitigation || v.mitigation || 'Rotate credentials immediately and configure hardware 2FA.')}</div>
        `;
        grid.appendChild(card);
    });

    container.hidden = false;
}

function traceReasoning(text) {
    const summaryCard = agEl('agent-summary');
    if (summaryCard) {
        summaryCard.innerHTML = renderMarkdown(text);
    }
}

async function agentInit() {
    try {
        const info = await (await fetch('/api/agent/info')).json();
        const badge = agEl('planner-badge');
        agEl('planner-mode').textContent = info.llm_active
            ? `LLM PLANNER · ${info.model}` : 'DETERMINISTIC PLANNER';
        agEl('planner-note').textContent = info.note;
        badge.classList.toggle('live', !!info.llm_active);
    } catch (e) { /* badge is cosmetic */ }

    try {
        const b = await (await fetch('/api/agent/brokers')).json();
        agEl('ag-disclosure').textContent = b.disclosure;
    } catch (e) { /* disclosure is cosmetic */ }
}

function agentConnect() {
    return new Promise((resolve, reject) => {
        if (Agent.ws && Agent.ws.readyState === WebSocket.OPEN) return resolve(Agent.ws);
        const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${proto}//${location.host}/ws/agent`);
        ws.onopen = () => { Agent.ws = ws; resolve(ws); };
        ws.onerror = () => reject(new Error('WebSocket failed'));
        ws.onmessage = (ev) => agentOnMessage(JSON.parse(ev.data));
        ws.onclose = () => { Agent.ws = null; };
    });
}

function agentOnMessage(msg) {
    if (msg.type === 'agent_event') {
        Agent.steps = (Agent.steps || 0) + 1;
        traceAdd(msg.agent, msg.message, msg.status);
        if (msg.tool_output && (msg.tool_name === 'analyze_threat_surface' || msg.agent === 'forensics')) {
            const tm = msg.tool_output.threat_surface || msg.tool_output;
            if (tm && (tm.threat_vectors || tm.overall_surface_grade)) {
                renderThreatSurface(tm);
            }
        }
    } else if (msg.type === 'agent_reasoning') {
        traceReasoning(msg.text);
    } else if (msg.type === 'phase_complete') {
        agentRender(msg);
        syncAgentToExposuresAndDashboard(msg);
        agentSetBusy(false);
    } else if (msg.type === 'error') {
        traceAdd('orchestrator', msg.message, 'error');
        agentSetBusy(false);
    }
}

function agentSetBusy(busy) {
    Agent.busy = busy;
    agEl('ag-run').disabled = busy;
    agEl('ag-reset').disabled = busy;
    const approve = agEl('ag-approve');
    if (approve) approve.disabled = busy;
    agEl('trace-live').hidden = !busy;

    if (busy) {
        Agent.startedAt = Date.now();
        Agent.steps = 0;
        const tick = () => {
            if (!Agent.busy) return;
            const secs = Math.floor((Date.now() - Agent.startedAt) / 1000);
            agEl('ag-run').textContent =
                `Working… ${secs}s · ${Agent.steps} step${Agent.steps === 1 ? '' : 's'}`;
        };
        tick();
        Agent.timer = setInterval(tick, 1000);
    } else {
        clearInterval(Agent.timer);
        agEl('ag-run').textContent = 'Deploy Privacy Agent';
    }
}

function agentRender(msg) {
    const st = msg.state;
    Agent.userId = msg.user_id;
    const s = st.summary;

    // Risk delta
    const riskAfter = msg.risk_after != null ? msg.risk_after : null;
    agEl('agent-outcome').hidden = false;
    if (msg.action === 'scan') {
        Agent.riskBefore = agentScoreFrom(msg) ?? Agent.riskBefore;
        agEl('risk-before').textContent = '—';
        agEl('risk-after').textContent = Agent.riskBefore != null ? Agent.riskBefore : '—';
    } else {
        agEl('risk-before').textContent = Agent.riskBefore != null ? Agent.riskBefore : '—';
        agEl('risk-after').textContent = agentScoreFrom(msg) ?? '—';
    }
    const lvl = agentLevelFor(parseFloat(agEl('risk-after').textContent));
    agEl('risk-level').textContent = lvl.label;
    agEl('risk-level').style.color = lvl.color;
    agEl('risk-after').style.color = lvl.color;

    agEl('risk-stats').innerHTML = [
        ['Exposures', s.exposures_total],
        ['High risk', s.high_risk],
        ['Notices sent', s.requests_submitted],
        ['Verified removed', s.removals_verified],
    ].map(([l, v]) => `<div class="risk-stat"><div class="risk-stat-v">${agEsc(v)}</div><div class="risk-stat-l">${agEsc(l)}</div></div>`).join('');

    agEl('agent-summary').innerHTML = renderMarkdown(msg.summary || '');

    // Fetch and render Threat Surface Matrix
    if (msg.user_id) {
        fetch('/api/agent/threat-surface/' + encodeURIComponent(msg.user_id))
            .then(r => r.json())
            .then(renderThreatSurface)
            .catch(() => {});
    }

    // Approval gate
    Agent.drafted = st.requests.filter(r => r.status === 'awaiting_approval');
    const panel = agEl('approval-panel');
    if (Agent.drafted.length) {
        panel.hidden = false;
        agEl('approval-list').innerHTML = Agent.drafted.map((r, i) => `
            <div class="approval-item">
                <input type="checkbox" id="apv-${i}" value="${agEsc(r.id)}" checked>
                <div class="approval-body">
                    <div class="approval-head">
                        <span class="approval-broker">${agEsc(r.source_name)}</span>
                        <span class="approval-statute">${agEsc(r.statute)}</span>
                    </div>
                    <div class="approval-meta">Ref ${agEsc(r.reference_id)} · respond within ${agEsc(r.deadline_days)} days</div>
                    <button class="approval-toggle" data-t="${i}">Read the notice</button>
                    <pre class="approval-text" id="apt-${i}" hidden>${agEsc(r.request_text)}</pre>
                </div>
            </div>`).join('');
        agEl('approval-list').querySelectorAll('.approval-toggle').forEach(b => {
            b.addEventListener('click', () => {
                const pre = agEl('apt-' + b.dataset.t);
                pre.hidden = !pre.hidden;
                b.textContent = pre.hidden ? 'Read the notice' : 'Hide the notice';
            });
        });
    } else {
        panel.hidden = true;
    }

    // Removal plan — grouped by how the data actually comes down. Most of this
    // is a link and three steps, not a legal notice.
    const plan = st.removal_plan;
    const planPanel = agEl('plan-panel');
    if (plan && plan.groups && plan.groups.length) {
        planPanel.hidden = false;
        agEl('plan-principle').textContent = plan.principle || '';
        agEl('plan-effort').textContent =
            `${plan.self_serve_count} you can do yourself · ~${plan.estimated_minutes} min total · ` +
            `${plan.needs_notice_count} need a legal notice`;
        agEl('plan-groups').innerHTML = plan.groups.map(g => `
            <div class="plan-group pg-${agEsc(g.method)}">
                <div class="plan-group-head">
                    <h4>${agEsc(g.label || g.method)}</h4>
                    <span class="plan-group-why">${agEsc(g.why || '')}</span>
                    <span class="plan-group-count">${g.items.length} · ${agEsc(g.typical_time || '')}</span>
                </div>
                ${g.items.map(it => `
                    <div class="plan-item">
                        <div class="plan-item-head">
                            <span class="plan-src">${agEsc(it.source)}</span>
                            ${it.effort_minutes ? `<span class="plan-min">~${agEsc(it.effort_minutes)} min</span>` : ''}
                            <span class="ev-badge ev-${agEsc(it.evidence_class || '')}">${agEsc((it.evidence_class || '').replace('_', ' '))}</span>
                            ${safeUrl(it.url) ? `<a class="plan-link" href="${agEsc(safeUrl(it.url))}" target="_blank" rel="noopener noreferrer">Open removal page ↗</a>` : ''}
                        </div>
                        ${it.steps && it.steps.length
                            ? `<ol class="plan-steps">${it.steps.map(x => `<li>${agEsc(x)}</li>`).join('')}</ol>`
                            : ''}
                        ${it.escalation ? `<div class="plan-escalation"><b>If that fails:</b> ${agEsc(it.escalation)}</div>` : ''}
                    </div>`).join('')}
            </div>`).join('');
    } else {
        planPanel.hidden = true;
    }

    renderCandidates(st);

    // Ledger
    agEl('ledger-panel').hidden = st.exposures.length === 0;
    // Every row states HOW it is known, and can show the raw proof. Nothing
    // appears in this table that was not either checked or declared.
    agEl('ledger').innerHTML =
        '<thead><tr><th>Source</th><th>How we know</th><th>Data exposed</th><th>Proof</th><th>Status</th></tr></thead><tbody>' +
        st.exposures.map((e, i) => {
            const cls = e.evidence_class || 'unknown';
            const evs = e.evidence || [];
            const proof = evs.map(v => {
                const lines = [
                    `<b>check</b>      ${agEsc(v.check || '')}`,
                    `<b>endpoint</b>   ${agEsc(v.endpoint || '')}`,
                    `<b>queried</b>    ${agEsc(v.queried_at || '')}`,
                    v.http_status != null ? `<b>HTTP</b>       ${agEsc(v.http_status)}` : '',
                    `<b>evidence</b>   ${agEsc(v.proof || '')}`,
                    `<b>means</b>      ${agEsc(v.interpretation || '')}`,
                    v.reproduce ? `<b>verify it</b>  ${agEsc(v.reproduce)}` : '',
                ].filter(Boolean);
                return lines.join('\n');
            }).join('\n\n');
            return `
            <tr>
                <td class="src">${agEsc(e.source_name)}</td>
                <td><span class="ev-badge ev-${agEsc(cls)}">${agEsc(cls.replace('_', ' '))}</span></td>
                <td>${agEsc((e.data_found || []).slice(0, 5).join(', ')) || '—'}</td>
                <td>${evs.length ? `<button class="proof-toggle" data-p="${i}">show proof</button>` : '—'}</td>
                <td><span class="pill ${agEsc(e.status)}">${agEsc(e.status)}</span>
                    ${e.verified_at ? ' <span class="verified-tag">✓ REMOVAL VERIFIED</span>' : ''}</td>
            </tr>
            ${evs.length ? `<tr id="proof-${i}" hidden><td colspan="5"><div class="proof-box">${proof}</div></td></tr>` : ''}`;
        }).join('') + '</tbody>';

    agEl('ledger').querySelectorAll('.proof-toggle').forEach(b => {
        b.addEventListener('click', () => {
            const row = agEl('proof-' + b.dataset.p);
            row.hidden = !row.hidden;
            b.textContent = row.hidden ? 'show proof' : 'hide proof';
        });
    });
}

function agentScoreFrom(msg) {
    if (msg.risk_after != null) return msg.risk_after;
    const m = (msg.summary || '').match(/Risk Score ([\d.]+)/);
    return m ? parseFloat(m[1]) : null;
}

function agentLevelFor(score) {
    if (isNaN(score)) return { label: '', color: 'var(--text-primary)' };
    if (score >= 80) return { label: 'Critical', color: '#ef4444' };
    if (score >= 60) return { label: 'High', color: '#f97316' };
    if (score >= 40) return { label: 'Medium', color: '#eab308' };
    if (score >= 20) return { label: 'Low', color: '#22c55e' };
    return { label: 'Minimal', color: '#10b981' };
}

/* ── Bridge: Agent Findings → Exposures Tab & Command Center Dashboard ───── */

function syncAgentToExposuresAndDashboard(msg) {
    if (!msg || !msg.state) return;
    const st = msg.state;
    state.agentState = st;
    state.agentSummary = st.summary || {};
    state.agentRisk = agentScoreFrom(msg) ?? (st.summary && st.summary.overall_risk);

    // Update Command Center stats
    updateDashboardFromAgent(st, state.agentRisk);

    // Render cards in Exposures tab
    renderAgentExposures(st);

    // Update Rights Advisor if open
    if (window.RightsAdvisor) {
        window.RightsAdvisor.updateContextStats();
    }
}

function updateDashboardFromAgent(st, riskScore) {
    if (!st) return;
    const s = st.summary || {};
    const exposures = (st.exposures || []).filter(e => e.status !== 'not_mine');
    const breaches = exposures.filter(e => e.source_type === 'breach').length;
    const brokers = exposures.filter(e => e.source_type === 'data_broker'
        || e.source_type === 'public_profile' || e.source_type === 'open_web').length;
    const pastes = exposures.filter(e => e.source_type === 'paste').length;
    // An info-stealer infection is neither a company breach nor a broker record.
    // Folding it into "Breach Incidents" would bury the one number on this page
    // that means "act today", so it gets a counter of its own.
    const infostealers = exposures.filter(e => e.source_type === 'infostealer').length;

    const score = Math.round(riskScore != null ? riskScore : (s.overall_risk || 0));
    const scoreEl = document.getElementById('risk-score-value');
    if (scoreEl) scoreEl.textContent = score;

    const bEl = document.getElementById('breach-count');
    if (bEl) bEl.textContent = breaches;
    const brEl = document.getElementById('broker-count');
    if (brEl) brEl.textContent = brokers;
    const pEl = document.getElementById('paste-count');
    if (pEl) pEl.textContent = pastes;
    const iEl = document.getElementById('infostealer-count');
    if (iEl) iEl.textContent = infostealers;
    const iCard = document.getElementById('stat-infostealer');
    if (iCard) iCard.classList.toggle('stat-alarm', infostealers > 0);

    const badge = document.getElementById('risk-level-badge');
    if (badge) {
        const lvl = agentLevelFor(score);
        badge.textContent = lvl.label;
        badge.style.background = lvl.color ? `${lvl.color}22` : '';
        badge.style.color = lvl.color || '';
    }

    const riskCard = document.getElementById('stat-risk-score');
    if (riskCard) {
        if (score >= 60) riskCard.style.borderColor = 'rgba(239, 68, 68, 0.4)';
        else if (score >= 30) riskCard.style.borderColor = 'rgba(245, 158, 11, 0.4)';
        else riskCard.style.borderColor = 'rgba(16, 185, 129, 0.4)';
    }

    const recsCard = document.getElementById('recommendations-card');
    const recsList = document.getElementById('recommendations-list');
    if (recsCard && recsList) {
        const recs = [];
        // Stolen live credentials come before anything a legal notice can fix.
        if (infostealers > 0) {
            recs.push(`🚨 Malware Infection: ${infostealers} infected machine record${infostealers > 1 ? 's' : ''} carried your address — every password saved in that browser was stolen. Change them all (email and banking first), sign out of all sessions everywhere, and enable two-factor authentication.`);
        }
        const plan = st.removal_plan;
        if (plan) {
            if (plan.self_serve_count > 0) {
                recs.push(`⚡ Quick Action: ${plan.self_serve_count} exposure${plan.self_serve_count > 1 ? 's' : ''} can be removed immediately via self-serve links (~${plan.estimated_minutes} min total).`);
            }
            if (plan.needs_notice_count > 0) {
                recs.push(`⚖️ Statutory Notice: ${plan.needs_notice_count} data fiduciaries require legal erasure notices under DPDP Act s.12.`);
            }
        }
        const unconfirmed = (st.exposures || []).filter(e => e.status === 'unconfirmed').length;
        if (unconfirmed > 0) {
            recs.push(`🔍 Attribution Gate: ${unconfirmed} candidate handle${unconfirmed > 1 ? 's' : ''} require your review in Privacy Agent before any action.`);
        }
        if (recs.length === 0 && score > 0) {
            recs.push("Review identified exposures in the Exposures tab and initiate takedowns.");
        }
        if (recs.length > 0) {
            recsCard.style.display = 'block';
            recsList.innerHTML = recs.map(r => `<div class="recommendation-item">${escapeHtml(r)}</div>`).join('');
        }
    }
}

function renderAgentExposures(st) {
    const container = document.getElementById('exposure-cards');
    if (!container || !st) return;
    container.innerHTML = '';

    const cards = [];
    // An info-stealer infection outranks every other finding on this page — it
    // is live credentials in criminal hands, not a historic record — so it is
    // built by its own card builder and placed at the top of the list. Handling
    // it before the badge ladder below also means it can never fall through to
    // the generic "Data Broker" default.
    const urgent = [];
    const exposures = (st.exposures || []).filter(e => e.status !== 'not_mine');

    // 1. Render identity-attributed findings & candidate accounts
    exposures.forEach(exp => {
        if (exp.source_type === 'infostealer') {
            urgent.push(createInfostealerCard(exp));
            return;
        }

        const isCand = exp.status === 'unconfirmed';
        const d = exp.detail || {};
        const isNotServable = exp.evidence_class === 'judicial_record' || exp.evidence_class === 'statutory_publication';

        let srcType = 'broker';
        let typeBadge = 'Data Broker';
        if (exp.source_type === 'breach') {
            srcType = 'breach';
            // Name the corpus that confirmed it. "Verified Breach · XposedOrNot"
            // tells the user which dataset to go and check; a bare label does not.
            typeBadge = d.source_dataset ? `Verified Breach · ${d.source_dataset}` : 'Verified Breach';
        } else if (exp.source_type === 'paste') {
            srcType = 'paste';
            typeBadge = 'Dark Web Leak';
        } else if (exp.source_type === 'public_profile') {
            srcType = 'broker';
            typeBadge = isCand ? 'Candidate Account (Unconfirmed)' : 'Public Profile';
        } else if (exp.source_type === 'open_web') {
            // Found by searching the open web, then confirmed by fetching the
            // page and finding the identifier on it. Say which identifier, so
            // the badge carries the evidence rather than a generic label.
            srcType = 'breach';
            const what = (d.identifier_type || 'identifier').replace('_', ' ');
            typeBadge = `Open Web · your ${what} found on this page`;
        }

        let domain = d.url ? d.url.replace(/^https?:\/\//, '').split('/')[0] : (d.website || exp.source_name);
        const contact = getFiduciaryContact(exp.source_name);
        const card = createExposureCard({
            exposureId: exp.id,
            title: isCand ? `${exp.source_name} (@${exp.record_id})` : exp.source_name,
            source: srcType,
            severity: exp.severity || (isCand ? 'low' : 'medium'),
            domain: domain,
            date: (exp.discovered_at || '').split('T')[0] || (d.date_found ? d.date_found.split('T')[0] : ''),
            pwnCount: d.pwn_count,
            dataClasses: fieldLabels(exp.data_found || []),
            // The breach datasets carry their own prose and industry label; both
            // say more about what actually happened than the source name does.
            description: exp.source_type === 'breach' ? (d.description || '') : '',
            category: exp.source_type === 'breach' && d.industry ? `Industry: ${d.industry}` : '',
            type: typeBadge,
            companyName: contact.company_name || exp.source_name,
            companyEmail: d.privacy_email || contact.dpo_email || '',
            removalDifficulty: d.removal_difficulty || (exp.status === 'removed' ? 'Removed' : (isCand ? 'Requires Attribution' : 'Standard')),
            optOutUrl: d.url || d.removal_url || d.opt_out_url || contact.self_serve_url || '',
            profileUrl: d.url || '',
            noNotice: isNotServable,
            isCandidate: isCand,
            isIndian: !!(
                d.is_indian ||
                contact.jurisdiction === 'dpdp' ||
                (domain && (domain.endsWith('.in') || domain.includes('.in/'))) ||
                (window.__indianSources?.some(s => (s.name || '').toLowerCase() === (exp.source_name || '').toLowerCase()))
            ),
        });
        cards.push(card);
    });

    const ordered = urgent.concat(cards);
    if (ordered.length === 0) {
        container.innerHTML = `<div class="glass-card empty-state"><div class="empty-icon">✅</div><h3>No Significant Exposures</h3><p>No critical data exposures were found for the provided identity.</p></div>`;
    } else {
        ordered.forEach(c => container.appendChild(c));
    }
}

function renderIndianSourcesDirectory() {
    const container = document.getElementById('indian-registry-grid');
    if (!container || !window.__indianSources?.length) return;
    container.innerHTML = '';
    const rank = { critical: 0, high: 1, medium: 2, low: 3 };
    const erasable = {
        dpdp_erasure: 'DPDP s.12 — erasure available',
        dpdp_limited: 'Retention duty applies — dispute/correct only',
        statutory_publication: 'Statutory publication — erasure does not lie',
        judicial_record: 'Court record — needs a court application'
    };

    [...window.__indianSources]
        .sort((a, b) => (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9))
        .forEach(src => {
            const servable = src.legal_class === 'dpdp_erasure';
            const card = createExposureCard({
                title: src.name,
                source: 'broker',
                severity: src.severity || 'medium',
                domain: src.website,
                category: `${src.category} · India`,
                removalDifficulty: erasable[src.legal_class] || src.legal_class,
                optOutUrl: src.removal_url,
                type: servable ? 'Reference Directory · Servable' : 'Reference Directory · Statutory Exemption',
                companyName: src.name,
                companyEmail: '',
                noNotice: !servable,
                isIndian: true,
            });
            container.appendChild(card);
        });
}

/* ── Profile Sync Across Tabs ────────────────────────────────────────────── */

function initProfileSync() {
    const pairs = [
        ['ag-name', 'input-name', 'user-name'],
        ['ag-email', 'input-email', 'user-email'],
        ['ag-phone', 'input-phone', 'user-phone'],
        ['ag-city', 'input-city'],
        ['ag-aadhaar', 'input-aadhaar'],
        ['ag-pan', 'input-pan'],
    ];

    // Load from localStorage if present
    const saved = localStorage.getItem('sovereign_profile');
    if (saved) {
        try {
            const p = JSON.parse(saved);
            Object.entries(p).forEach(([k, val]) => {
                const el = document.getElementById(k);
                if (el && val && !el.value) el.value = val;
            });
        } catch(e) {}
    }

    pairs.forEach(group => {
        group.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', () => {
                const val = el.value;
                group.forEach(otherId => {
                    if (otherId !== id) {
                        const other = document.getElementById(otherId);
                        if (other) other.value = val;
                    }
                });
                const profileObj = {};
                ['ag-name', 'ag-email', 'ag-phone', 'ag-city', 'ag-aadhaar', 'ag-pan', 'input-name', 'input-email'].forEach(fid => {
                    const f = document.getElementById(fid);
                    if (f) profileObj[fid] = f.value;
                });
                localStorage.setItem('sovereign_profile', JSON.stringify(profileObj));
            });
        });
    });
}

function prefillLegalForm() {
    const name = document.getElementById('ag-name')?.value || document.getElementById('input-name')?.value;
    const email = document.getElementById('ag-email')?.value || document.getElementById('input-email')?.value;
    const phone = document.getElementById('ag-phone')?.value || document.getElementById('input-phone')?.value;
    const pan = document.getElementById('ag-pan')?.value || document.getElementById('input-pan')?.value;
    const aadhaar = document.getElementById('ag-aadhaar')?.value || document.getElementById('input-aadhaar')?.value;
    const city = document.getElementById('ag-city')?.value || document.getElementById('input-city')?.value;

    const un = document.getElementById('user-name');
    if (un && !un.value && name) un.value = name;
    const ue = document.getElementById('user-email');
    if (ue && !ue.value && email) ue.value = email;
    const up = document.getElementById('user-phone');
    if (up && !up.value && phone) up.value = phone;
    const uid = document.getElementById('user-id-number');
    if (uid && !uid.value) {
        if (pan) uid.value = `PAN: ${pan}`;
        else if (aadhaar) uid.value = `Aadhaar: ${aadhaar}`;
    }
    const uaddr = document.getElementById('user-address');
    if (uaddr && !uaddr.value && city) uaddr.value = city;
}

// Kept as the name the Agent tab already uses; one escaper, one behaviour.
function agEsc(v) { return escapeHtml(v); }

async function agentRun() {
    const profile = agProfile();
    if (!profile.name && !profile.email) {
        alert('Enter at least a name or an email address.');
        return;
    }
    Agent.profile = profile;
    Agent.riskBefore = null;
    traceClear();
    agEl('agent-outcome').hidden = true;
    agEl('approval-panel').hidden = true;
    agEl('ledger-panel').hidden = true;
    const pp = agEl('plan-panel'); if (pp) pp.hidden = true;
    const cp = agEl('candidates-panel'); if (cp) cp.hidden = true;
    agentSetBusy(true);
    try {
        const ws = await agentConnect();
        ws.send(JSON.stringify({ action: 'scan', profile }));
    } catch (e) {
        traceAdd('orchestrator', 'Connecting via Sovereign Cloud Execution API…', 'running');
        try {
            const resp = await fetch('/api/agent/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(profile),
            });
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Server error (${resp.status})`);
            }
            const data = await resp.json();
            for (const ev of (data.events || [])) {
                Agent.steps = (Agent.steps || 0) + 1;
                traceAdd(ev.agent, ev.message, ev.status);
            }
            const msg = { action: 'scan', ...data };
            agentRender(msg);
            syncAgentToExposuresAndDashboard(msg);
        } catch (err) {
            traceAdd('orchestrator', 'Agent scan failed: ' + err.message, 'error');
        } finally {
            agentSetBusy(false);
        }
    }
}

async function agentApprove() {
    const ids = Array.from(document.querySelectorAll('#approval-list input:checked')).map(i => i.value);
    if (!ids.length) { alert('Select at least one notice to dispatch.'); return; }
    agentSetBusy(true);
    traceAdd('orchestrator', `User approved ${ids.length} notice(s) for dispatch.`, 'ok');
    try {
        const ws = await agentConnect();
        ws.send(JSON.stringify({ action: 'approve', profile: Agent.profile, request_ids: ids }));
    } catch (e) {
        traceAdd('orchestrator', 'Dispatching notices via Sovereign Cloud Execution API…', 'running');
        try {
            const resp = await fetch('/api/agent/approve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ...Agent.profile, request_ids: ids }),
            });
            if (!resp.ok) {
                const errData = await resp.json().catch(() => ({}));
                throw new Error(errData.detail || `Server error (${resp.status})`);
            }
            const data = await resp.json();
            for (const ev of (data.events || [])) {
                Agent.steps = (Agent.steps || 0) + 1;
                traceAdd(ev.agent, ev.message, ev.status);
            }
            const msg = { action: 'approve', ...data };
            agentRender(msg);
            syncAgentToExposuresAndDashboard(msg);
        } catch (err) {
            traceAdd('orchestrator', 'Remediation dispatch failed: ' + err.message, 'error');
        } finally {
            agentSetBusy(false);
        }
    }
}

async function agentReset() {
    const profile = agProfile();
    if (!profile.name && !profile.email) { alert('Enter the identity you want to reset.'); return; }
    agentSetBusy(true);
    try {
        await fetch('/api/agent/reset', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(profile),
        });
        traceClear();
        clearMultiInputs();
        agEl('agent-outcome').hidden = true;
        agEl('agent-summary').innerHTML = '';
        agEl('approval-panel').hidden = true;
        agEl('ledger-panel').hidden = true;
        traceAdd('orchestrator', 'Identity reset. The demo can be run again from a clean slate.', 'ok');
    } catch (e) {
        traceAdd('orchestrator', 'Reset failed: ' + e.message, 'error');
    }
    agentSetBusy(false);
}

async function loadIndianSources() {
    try {
        const d = await (await fetch('/api/sources/indian')).json();
        window.__indianSources = d.sources || [];
        renderIndianSourcesDirectory();
    } catch (e) { window.__indianSources = []; }
}

document.addEventListener('DOMContentLoaded', () => {
    loadIndianSources();
    if (!document.getElementById('section-agent')) return;
    agentInit();
    agEl('ag-run').addEventListener('click', agentRun);
    agEl('ag-approve').addEventListener('click', agentApprove);
    agEl('ag-reset').addEventListener('click', agentReset);
    initMultiInputs();
    initPasswordToggle();
});

/* ── Candidates: matched a handle, nothing ties them to you ───────────────── */

function renderCandidates(st) {
    const panel = agEl('candidates-panel');
    if (!panel) return;
    const cands = (st.exposures || []).filter(e => e.status === 'unconfirmed');
    if (!cands.length) { panel.hidden = true; return; }

    panel.hidden = false;
    agEl('cand-count').textContent = `${cands.length} unconfirmed — not counted as yours`;
    agEl('candidates-list').innerHTML = cands.map(e => {
        const d = e.detail || {};
        const risk = d.collision_risk || 'medium';
        const riskClass = (risk === 'confirmed' || risk === 'low') ? 'low' : (risk === 'high' ? 'high' : 'medium');
        const riskLabel = (risk === 'confirmed' || risk === 'low')
            ? 'low collision risk'
            : (risk === 'high' ? 'high collision risk (common name)' : `${risk} collision risk`);

        const whyNote = d.collision_note || (d.attribution || {}).explanation || 'Candidate handle matched during discovery. Verify before attributing.';

        return `
        <div class="cand-item" id="cand-${agEsc(e.id)}">
            <div class="cand-head">
                <span class="cand-site">${agEsc(e.source_name)}</span>
                <span class="cand-handle">@${agEsc(e.record_id)}</span>
                <span class="cand-risk risk-${agEsc(riskClass)}">${agEsc(riskLabel)}</span>
                ${d.handle_source ? `<span class="cand-source">from ${agEsc(d.handle_source.replace('_', ' '))}</span>` : ''}
                ${safeUrl(d.url) ? `<a class="cand-link" href="${agEsc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer">view ↗</a>` : ''}
                <span class="cand-actions">
                    <button class="cand-btn yes" data-id="${agEsc(e.id)}" data-mine="1">Yes, mine</button>
                    <button class="cand-btn no"  data-id="${agEsc(e.id)}" data-mine="0">Not me</button>
                </span>
            </div>
            <div class="cand-why">${agEsc(whyNote)}</div>
        </div>`;
    }).join('');

    agEl('candidates-list').querySelectorAll('.cand-btn').forEach(b => {
        b.addEventListener('click', () => confirmCandidate(b.dataset.id, b.dataset.mine === '1', b));
    });
}

/* ── Multi-Value Input Helpers (Phone, UPI, Websites) ────────────────── */

/**
 * Stores multi-values per group. Key = input id prefix (e.g. 'ag-phone'),
 * value = array of added strings.
 */
const _multiValues = {};

function initMultiInputs() {
    const groups = ['ag-phone', 'ag-altphones', 'ag-upi', 'ag-websites'];

    groups.forEach(groupId => {
        _multiValues[groupId] = [];
        const input = document.getElementById(groupId);
        const addBtn = document.querySelector(`.multi-add-btn[data-group="${groupId}"]`);

        if (!input) return;

        // Add on button click
        if (addBtn) {
            addBtn.addEventListener('click', () => {
                const val = input.value.trim();
                if (val) {
                    addMultiTag(groupId, val);
                    input.value = '';
                    input.focus();
                }
            });
        }

        // Add on Enter key or comma
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ',') {
                e.preventDefault();
                const val = input.value.trim();
                if (val) {
                    addMultiTag(groupId, val);
                    input.value = '';
                }
            }
        });

        // Add on paste (e.g. pasted comma-separated list)
        input.addEventListener('paste', () => {
            setTimeout(() => {
                const val = input.value.trim();
                if (val.includes(',') || val.includes('\n')) {
                    addMultiTag(groupId, val);
                    input.value = '';
                }
            }, 20);
        });
    });
}

function addMultiTag(groupId, value) {
    if (!value) return;
    if (!_multiValues[groupId]) _multiValues[groupId] = [];
    const parts = value.split(/[,;\n]+/).map(s => s.trim()).filter(Boolean);
    const tagsContainer = document.getElementById(groupId + '-tags');

    parts.forEach(part => {
        if (_multiValues[groupId].includes(part)) return;
        _multiValues[groupId].push(part);

        if (!tagsContainer) return;

        const tag = document.createElement('span');
        tag.className = 'multi-tag';
        tag.dataset.value = part;

        const text = document.createElement('span');
        text.textContent = part;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'multi-tag-remove';
        removeBtn.textContent = '×';
        removeBtn.title = 'Remove';
        removeBtn.addEventListener('click', () => {
            removeMultiTag(groupId, part, tag);
        });

        tag.append(text, removeBtn);
        tagsContainer.appendChild(tag);
    });
}

function removeMultiTag(groupId, value, tagEl) {
    if (!_multiValues[groupId]) return;
    const idx = _multiValues[groupId].indexOf(value);
    if (idx !== -1) _multiValues[groupId].splice(idx, 1);
    if (tagEl) {
        tagEl.style.transition = 'all 0.2s ease';
        tagEl.style.opacity = '0';
        tagEl.style.transform = 'scale(0.8)';
        setTimeout(() => tagEl.remove(), 200);
    }
}

/**
 * Collect all values for a multi-input group: the already-added tags
 * plus whatever is currently typed in the input field.
 */
function getMultiValues(groupId) {
    const vals = [...(_multiValues[groupId] || [])];
    const input = document.getElementById(groupId);
    if (input) {
        const current = input.value.trim();
        if (current) {
            const parts = current.split(/[,;\n]+/).map(s => s.trim()).filter(Boolean);
            parts.forEach(p => {
                if (!vals.includes(p)) vals.push(p);
            });
        }
    }
    return vals;
}

function clearMultiInputs() {
    ['ag-phone', 'ag-altphones', 'ag-upi', 'ag-websites'].forEach(groupId => {
        _multiValues[groupId] = [];
        const container = document.getElementById(groupId + '-tags');
        if (container) container.innerHTML = '';
        const input = document.getElementById(groupId);
        if (input) input.value = '';
    });
}

/* ── Password Visibility Toggle ──────────────────────────────────────── */

function initPasswordToggle() {
    const toggle = document.getElementById('ag-password-toggle');
    const input = document.getElementById('ag-password');
    if (!toggle || !input) return;

    toggle.addEventListener('click', () => {
        const isPassword = input.type === 'password';
        input.type = isPassword ? 'text' : 'password';
        toggle.classList.toggle('active', isPassword);
        toggle.title = isPassword ? 'Hide password' : 'Show password';

        // Swap eye icons
        const eyeOpen = toggle.querySelector('.eye-open');
        const eyeClosed = toggle.querySelector('.eye-closed');
        if (eyeOpen && eyeClosed) {
            eyeOpen.style.display = isPassword ? 'none' : '';
            eyeClosed.style.display = isPassword ? '' : 'none';
        }
    });
}


async function confirmCandidate(exposureId, isMine, btn) {
    const row = agEl('cand-' + exposureId);
    try {
        const resp = await fetch('/api/agent/confirm', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...agProfile(), exposure_id: exposureId, is_mine: isMine }),
        });
        if (!resp.ok) {
            const errBody = await resp.json().catch(() => ({}));
            throw new Error(errBody.detail || `Server error (${resp.status})`);
        }
        const data = await resp.json();
        if (row) {
            row.querySelectorAll('.cand-btn').forEach(x => { x.disabled = true; x.classList.add('done'); });
            if (!isMine) {
                row.querySelector('.cand-why').textContent = '✗ Marked as someone else — excluded permanently.';
                row.style.opacity = '0.5';
                setTimeout(() => {
                    row.style.transition = 'all 0.3s ease';
                    row.style.maxHeight = '0px';
                    row.style.padding = '0px';
                    row.style.margin = '0px';
                    row.style.overflow = 'hidden';
                    setTimeout(() => {
                        row.remove();
                        const remaining = document.querySelectorAll('#candidates-list .cand-item').length;
                        const countEl = agEl('cand-count');
                        if (countEl) {
                            countEl.textContent = remaining > 0 ? `${remaining} unconfirmed — not counted as yours` : 'All candidates reviewed ✓';
                        }
                        if (remaining === 0) {
                            setTimeout(() => {
                                const panel = agEl('candidates-panel');
                                if (panel) panel.hidden = true;
                            }, 1000);
                        }
                    }, 300);
                }, 600);
            } else {
                row.querySelector('.cand-why').textContent = '✓ Confirmed as yours — added to exposures & removal plan.';
                row.style.borderColor = 'rgba(16, 185, 129, 0.4)';
            }
        }
        if (data && data.state) {
            syncAgentToExposuresAndDashboard({ state: data.state });
        }
        showToast(isMine ? 'Confirmed as yours' : 'Marked as not yours', 'success');
    } catch (e) {
        console.error('Confirm candidate error:', e);
        if (row) row.querySelector('.cand-why').textContent = 'Could not save: ' + (e.message || 'network error. Try again.');
        showToast('Could not save: ' + (e.message || 'Unknown error'), 'error');
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
   Sitewide Rights Advisor Module
   ═══════════════════════════════════════════════════════════════════════════ */

const RightsAdvisor = {
    isOpen: false,
    history: [],
    currentTab: 'dashboard',

    init() {
        const trigger = document.getElementById('ai-advisor-trigger');
        const panel = document.getElementById('ai-advisor-panel');
        const closeBtn = document.getElementById('advisor-close-btn');
        const clearBtn = document.getElementById('advisor-clear-btn');
        const sendBtn = document.getElementById('advisor-send-btn');
        const input = document.getElementById('advisor-input');

        if (!trigger || !panel) return;

        trigger.addEventListener('click', () => this.toggle());
        if (closeBtn) closeBtn.addEventListener('click', () => this.toggle(false));
        if (clearBtn) clearBtn.addEventListener('click', () => this.clearChat());

        if (sendBtn && input) {
            sendBtn.addEventListener('click', () => {
                const text = input.value.trim();
                if (text) {
                    this.sendMessage(text);
                    input.value = '';
                    input.style.height = 'auto';
                }
            });

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendBtn.click();
                }
            });

            input.addEventListener('input', () => {
                input.style.height = 'auto';
                input.style.height = Math.min(input.scrollHeight, 90) + 'px';
            });
        }

        this.fetchModelStatus();
        this.onTabChange(state.currentSection || 'dashboard');
    },

    async fetchModelStatus() {
        try {
            const resp = await fetch('/api/agent/info');
            const data = await resp.json();
            const tag = document.getElementById('advisor-model-tag');
            if (tag) {
                if (data.planner === 'openai_compat') {
                    tag.innerHTML = `<span class="status-dot online"></span> Groq · GPT-OSS Active`;
                } else if (data.planner === 'anthropic') {
                    tag.innerHTML = `<span class="status-dot online"></span> Claude 3.5 Active`;
                } else {
                    tag.innerHTML = `<span class="status-dot online"></span> AI Sovereign Engine`;
                }
            }
        } catch(e) {}
    },

    toggle(force) {
        const panel = document.getElementById('ai-advisor-panel');
        if (!panel) return;
        this.isOpen = force !== undefined ? force : !this.isOpen;
        panel.hidden = !this.isOpen;
        if (this.isOpen) {
            this.updateContextStats();
            const input = document.getElementById('advisor-input');
            if (input) setTimeout(() => input.focus(), 150);
        }
    },

    onTabChange(tab) {
        this.currentTab = tab;
        const tabEl = document.getElementById('advisor-active-tab');
        if (tabEl) tabEl.textContent = tab.replace('-', ' ');

        this.updateContextStats();
        this.renderChipsForTab(tab);
    },

    updateContextStats() {
        const riskEl = document.getElementById('advisor-risk-badge');
        if (!riskEl) return;
        const score = state.agentRisk != null
            ? Math.round(state.agentRisk)
            : (state.scanResults?.risk_assessment?.overall_score != null
                ? Math.round(state.scanResults.risk_assessment.overall_score)
                : null);

        if (score != null) {
            riskEl.textContent = `Risk: ${score}/100`;
            riskEl.style.color = score >= 60 ? 'var(--accent-danger)' : (score >= 30 ? 'var(--accent-warning)' : 'var(--accent-success)');
        } else {
            riskEl.textContent = 'Risk: Not scanned';
            riskEl.style.color = 'var(--text-tertiary)';
        }
    },

    renderChipsForTab(tab) {
        const chipsContainer = document.getElementById('advisor-chips');
        if (!chipsContainer) return;

        const tabChips = {
            dashboard: [
                { label: "⚡ Deploy Privacy Agent", prompt: "How does the autonomous Privacy Agent discover and verify my data?" },
                { label: "📊 Explain Risk Score", prompt: "How is my privacy risk score calculated and what affects it?" },
                { label: "🇮🇳 India DPDP Act", prompt: "What are my statutory erasure rights under India's DPDP Act 2023?" },
            ],
            agent: [
                { label: "🔍 Explain Attribution", prompt: "How does the agent attribute accounts without false positives?" },
                { label: "👥 What are Candidates?", prompt: "Why are some handles parked as unconfirmed candidates?" },
                { label: "🛡️ Verification Proof", prompt: "How does the agent prove that a removal actually occurred?" },
            ],
            scanner: [
                { label: "🎯 Threat Vector Analysis", prompt: "What is the difference between verified breaches and data brokers?" },
                { label: "🔑 Password Exposure", prompt: "How does k-anonymous password checking protect my credentials?" },
            ],
            exposures: [
                { label: "📞 Remove Truecaller", prompt: "How do I delist my phone number from Truecaller?" },
                { label: "🏛️ Indian Registry Limits", prompt: "Why can court records and MCA filings not be deleted under DPDP?" },
                { label: "⚖️ Draft Legal Notice", prompt: "Which exposures should I serve a formal statutory erasure notice to?" },
            ],
            legal: [
                { label: "📜 DPDP Section 12", prompt: "Explain the legal grounds and requirements of DPDP Act 2023 Section 12." },
                { label: "⏳ 30-Day Deadline", prompt: "What are the legal consequences if a data fiduciary ignores the 30-day deadline?" },
                { label: "🇪🇺 GDPR vs DPDP", prompt: "How does DPDP Section 12 compare to EU GDPR Article 17?" },
            ],
            compliance: [
                { label: "🏛️ Escalate to DPBI", prompt: "How does escalation to the Data Protection Board of India work?" },
                { label: "📋 Audit Receipts", prompt: "How do SHA-256 cryptographic audit receipts prove legal compliance?" },
            ]
        };

        const chips = tabChips[tab] || tabChips.dashboard;
        chipsContainer.innerHTML = chips.map(c => `
            <button class="advisor-chip" data-prompt="${agEsc(c.prompt)}">${agEsc(c.label)}</button>
        `).join('');

        chipsContainer.querySelectorAll('.advisor-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                this.sendMessage(btn.dataset.prompt);
            });
        });
    },

    clearChat() {
        this.history = [];
        const msgContainer = document.getElementById('advisor-messages');
        if (msgContainer) {
            msgContainer.innerHTML = `
                <div class="advisor-msg bot">
                    <div class="advisor-msg-bubble">
                        Chat cleared. How can I assist you with data privacy and statutory rights?
                    </div>
                    <span class="advisor-msg-time">Ready</span>
                </div>
            `;
        }
    },

    async sendMessage(text) {
        if (!text || !text.trim()) return;
        const msgContainer = document.getElementById('advisor-messages');
        if (!msgContainer) return;

        this.appendMessage('user', text);
        this.history.push({ role: 'user', content: text });

        const typingEl = document.createElement('div');
        typingEl.className = 'advisor-typing';
        typingEl.id = 'advisor-typing-indicator';
        typingEl.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
        msgContainer.appendChild(typingEl);
        msgContainer.scrollTop = msgContainer.scrollHeight;

        const profile = typeof agProfile === 'function' ? agProfile() : {};
        const score = state.agentRisk != null ? state.agentRisk : (state.scanResults?.risk_assessment?.overall_score || null);
        const exposuresCount = (state.agentState?.exposures || []).length || (state.scanResults?.summary?.total_breaches || 0);

        try {
            const resp = await fetch('/api/agent/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    history: this.history.slice(-6),
                    context: {
                        tab: this.currentTab,
                        risk_score: score,
                        exposure_count: exposuresCount,
                        profile: { name: profile.name || '', email: profile.email || '' },
                    }
                })
            });

            const data = await resp.json();
            typingEl.remove();

            if (data.reply) {
                this.history.push({ role: 'assistant', content: data.reply });
                this.appendMessage('bot', data.reply, data.suggested_actions);
            } else {
                this.appendMessage('bot', 'Received empty response. Please try again.');
            }
        } catch (e) {
            typingEl.remove();
            this.appendMessage('bot', 'Could not contact the assistant. Check server connection.');
        }
    },

    appendMessage(role, text, actions = []) {
        const msgContainer = document.getElementById('advisor-messages');
        if (!msgContainer) return;

        const msgDiv = document.createElement('div');
        msgDiv.className = `advisor-msg ${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'advisor-msg-bubble';

        if (role === 'bot') {
            bubble.innerHTML = this.formatMarkdown(text);
            if (actions && actions.length) {
                const actionsDiv = document.createElement('div');
                actionsDiv.style.marginTop = '8px';
                actionsDiv.style.display = 'flex';
                actionsDiv.style.gap = '6px';
                actionsDiv.style.flexWrap = 'wrap';

                actions.forEach(act => {
                    const btn = document.createElement('button');
                    btn.className = 'advisor-action-btn';
                    btn.textContent = `→ ${act.label}`;
                    btn.addEventListener('click', () => {
                        if (act.action === 'navigate_tab' && act.tab) {
                            navigateTo(act.tab);
                        } else if (act.action === 'ask' && act.prompt) {
                            this.sendMessage(act.prompt);
                        }
                    });
                    actionsDiv.appendChild(btn);
                });
                bubble.appendChild(actionsDiv);
            }
        } else {
            bubble.textContent = text;
        }

        const timeSpan = document.createElement('span');
        timeSpan.className = 'advisor-msg-time';
        timeSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        msgDiv.appendChild(bubble);
        msgDiv.appendChild(timeSpan);
        msgContainer.appendChild(msgDiv);
        msgContainer.scrollTop = msgContainer.scrollHeight;
    },

    formatMarkdown(text) {
        return renderMarkdown(text);
    }
};

function initRightsAdvisor() {
    window.RightsAdvisor = RightsAdvisor;
    RightsAdvisor.init();
}

