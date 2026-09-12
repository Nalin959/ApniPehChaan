/**
 * SovereignPrivacy AI — Frontend Application Logic
 *
 * Manages navigation, WebSocket real-time scanning, API calls,
 * dynamic UI rendering, and all interactive features.
 */

// ═══ State ═══════════════════════════════════════════════════════════════════
const state = {
    currentSection: 'dashboard',
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
    initBenchmark();
    initExposureFilters();
    initProfileSync();
    fetchSystemStatus();
    initAICopilot();
});

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
    }
    if (section === 'legal') {
        prefillLegalForm();
    }

    // Update AI Copilot
    if (window.AIAssistant) {
        window.AIAssistant.onTabChange(section);
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

    // Indian sources first — this is a DPDP Act product, so the domestic
    // surface leads. Each carries its legal classification, because erasure
    // is available against a people-search site and is NOT available against
    // a court record or an MCA filing.
    if (window.__indianSources?.length) {
        const rank = { critical: 0, high: 1, medium: 2, low: 3 };
        const erasable = { dpdp_erasure: 'DPDP s.12 — erasure available',
                           dpdp_limited: 'Retention duty applies — dispute/correct only',
                           statutory_publication: 'Statutory publication — erasure does not lie',
                           judicial_record: 'Court record — needs a court application' };
        [...window.__indianSources]
            .sort((a, b) => (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9))
            .forEach(src => {
                const servable = src.legal_class === 'dpdp_erasure';
                cards.push(createExposureCard({
                    title: src.name,
                    source: 'broker',
                    severity: src.severity || 'medium',
                    domain: src.website,
                    category: `${src.category} · India`,
                    removalDifficulty: erasable[src.legal_class] || src.legal_class,
                    optOutUrl: src.removal_url,
                    type: servable ? 'Indian Source · Servable' : 'Indian Source · Not servable',
                    companyName: src.name,
                    companyEmail: '',
                    noNotice: !servable,
                }));
            });
    }

    // Global directory context. These are CATEGORY HEURISTICS, not confirmed
    // matches — "people-search sites of this kind typically hold records like
    // yours". Previously this sliced the first 20 alphabetically, which handed
    // an Indian user a screenful of Alabama court-record sites. Sort by
    // likelihood, cap it, and label it honestly.
    if (results.brokers?.high_risk) {
        [...results.brokers.high_risk]
            .sort((a, b) => (b.exposure_likelihood || 0) - (a.exposure_likelihood || 0))
            .slice(0, 9)
            .forEach(broker => {
                cards.push(createExposureCard({
                    title: broker.broker_name,
                    source: 'broker',
                    severity: broker.exposure_likelihood >= 0.80 ? 'medium' : 'low',
                    domain: broker.website,
                    category: broker.category,
                    removalDifficulty: broker.removal_difficulty,
                    optOutUrl: broker.opt_out_url,
                    type: `Global directory · likely (${Math.round((broker.exposure_likelihood || 0) * 100)}%)`,
                    companyName: broker.broker_name,
                    companyEmail: broker.privacy_email || '',
                }));
            });
    }

    if (cards.length === 0) {
        container.innerHTML = `<div class="glass-card empty-state"><div class="empty-icon">✅</div><h3>No Significant Exposures</h3><p>No critical data exposures were found for the provided identity.</p></div>`;
    } else {
        cards.forEach(card => container.appendChild(card));
    }
}

function createExposureCard(data) {
    const card = document.createElement('div');
    card.className = `exposure-card severity-${data.severity}`;
    card.dataset.source = data.source;
    card.dataset.severity = data.severity;

    const tagsHtml = (data.dataClasses || []).slice(0, 6).map(dc =>
        `<span class="pii-tag">${escapeHtml(dc)}</span>`
    ).join('');

    let metaHtml = '';
    if (data.domain) metaHtml += `<span>${escapeHtml(data.domain)}</span>`;
    if (data.date) metaHtml += ` · <span>${data.date}</span>`;
    if (data.pwnCount) metaHtml += ` · <span>${formatNumber(data.pwnCount)} records</span>`;
    if (data.category) metaHtml += ` · <span>${data.category}</span>`;
    if (data.removalDifficulty) metaHtml += ` · Removal: ${data.removalDifficulty}`;

    // A source that cannot lawfully be served must not offer a notice button.
    // Drafting a DPDP erasure notice against a court judgment or an MCA filing
    // produces a letter with no addressee in law — worse than useless, because
    // it tells the user they have a remedy they do not have.
    let actionsHtml = data.noNotice
        ? `<span class="exposure-nonservable">Erasure not available — see basis</span>`
        : `<button class="exposure-action-btn" onclick="generateNoticeForExposure('${escapeHtml(data.companyName || '')}', '${escapeHtml(data.companyEmail || '')}')">Generate Legal Notice</button>`;
    if (data.optOutUrl) {
        actionsHtml += `<a href="${escapeHtml(data.optOutUrl)}" target="_blank" class="exposure-action-btn danger">Opt-Out Link ↗</a>`;
    }

    card.innerHTML = `
        <div class="exposure-header">
            <span class="exposure-title">${escapeHtml(data.title)}</span>
            <span class="severity-badge ${data.severity}">${data.severity}</span>
        </div>
        <div class="exposure-meta">${data.type}${metaHtml ? ' · ' + metaHtml : ''}</div>
        <div class="exposure-tags">${tagsHtml}</div>
        <div class="exposure-actions">${actionsHtml}</div>
    `;

    return card;
}

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
        if (state.generatedNotice) {
            navigator.clipboard.writeText(state.generatedNotice.notice_text).then(() => {
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

function generateNoticeForExposure(companyName, companyEmail) {
    navigateTo('legal');
    document.getElementById('legal-company').value = companyName || '';
    document.getElementById('legal-company-email').value = companyEmail || '';
    if (state.scanResults) {
        const piiSummary = buildPIISummary();
        document.getElementById('legal-pii-summary').value = piiSummary;
    }
}

function buildPIISummary() {
    if (!state.scanResults) return '';
    const parts = [];
    const risk = state.scanResults.risk_assessment;
    if (risk?.breakdown?.entity_counts) {
        for (const [type, count] of Object.entries(risk.breakdown.entity_counts)) {
            parts.push(`${type}: ${count} instance(s) detected`);
        }
    }
    return parts.join('\n') || 'Personal data detected in your systems.';
}

function renderNoticePreview(data) {
    const preview = document.getElementById('notice-preview-content');
    preview.textContent = data.notice_text;

    // Show action buttons
    document.getElementById('btn-copy-notice').style.display = '';
    document.getElementById('btn-dispatch-notice').style.display = '';

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
    const payload = {
        jurisdiction: data.jurisdiction,
        company_name: data.recipient.company_name,
        company_email: document.getElementById('legal-company-email').value,
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
            showToast(result.message, 'success');
            navigateTo('compliance');
        } else {
            showToast('Dispatch failed', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
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
        container.innerHTML = `<div class="glass-card empty-state"><div class="empty-icon">⏱️</div><h3>No Active Requests</h3><p>Generate and dispatch a legal notice to begin tracking statutory compliance deadlines.</p><button class="action-btn primary-action" onclick="navigateTo('legal')">Go to Legal Studio</button></div>`;
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
                    <span class="timeline-date">${new Date(ms.date).toLocaleDateString()} (Day ${ms.day})</span>
                </div>
            `;
        }).join('');

        return `
            <div class="compliance-request-card">
                <div class="compliance-header">
                    <span class="compliance-title">${escapeHtml(req.company_name)}</span>
                    <span class="compliance-status ${req.status}">${req.status}</span>
                </div>
                <div class="compliance-meta">
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Jurisdiction</div>
                        <div class="compliance-meta-value">${req.jurisdiction.toUpperCase()}</div>
                    </div>
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Days Remaining</div>
                        <div class="compliance-meta-value" style="color: ${req.is_overdue ? 'var(--accent-danger)' : 'var(--text-primary)'}">${req.is_overdue ? 'OVERDUE' : req.days_remaining + ' days'}</div>
                    </div>
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Reference</div>
                        <div class="compliance-meta-value" style="font-family: var(--font-mono); font-size: 0.75rem;">${req.notice_reference}</div>
                    </div>
                    <div class="compliance-meta-item">
                        <div class="compliance-meta-label">Request ID</div>
                        <div class="compliance-meta-value" style="font-family: var(--font-mono); font-size: 0.75rem;">${req.request_id}</div>
                    </div>
                </div>
                <div class="compliance-progress-bar">
                    <div class="compliance-progress-fill" style="width: ${req.progress_pct}%; background: ${progressColor};"></div>
                </div>
                <div class="compliance-timeline">${milestonesHtml}</div>
                <div class="compliance-actions">
                    <button class="exposure-action-btn" onclick="updateRequestStatus('${req.request_id}', 'acknowledged', 'Company acknowledged receipt')">Mark Acknowledged</button>
                    <button class="exposure-action-btn" onclick="updateRequestStatus('${req.request_id}', 'completed', 'Data deletion confirmed')">Mark Completed</button>
                    <button class="exposure-action-btn danger" onclick="updateRequestStatus('${req.request_id}', 'escalated', 'Escalated to ${req.jurisdiction === 'dpdp' ? 'DPBI' : 'Supervisory Authority'}')">Escalate</button>
                </div>
            </div>
        `;
    }).join('');
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

// ═══ Benchmark ══════════════════════════════════════════════════════════════
function initBenchmark() {
    document.getElementById('btn-run-benchmark').addEventListener('click', runBenchmark);
}

async function runBenchmark() {
    const btn = document.getElementById('btn-run-benchmark');
    const statusEl = document.getElementById('benchmark-status');
    btn.disabled = true;
    statusEl.textContent = 'Running benchmark...';

    try {
        const resp = await fetch('/api/pii/benchmark');
        const data = await resp.json();

        // Show results
        document.getElementById('benchmark-results').style.display = 'block';
        document.getElementById('bench-precision').textContent = `${(data.aggregate.precision * 100).toFixed(1)}%`;
        document.getElementById('bench-recall').textContent = `${(data.aggregate.recall * 100).toFixed(1)}%`;
        document.getElementById('bench-f1').textContent = `${(data.aggregate.f1 * 100).toFixed(1)}%`;
        document.getElementById('bench-samples').textContent = data.total_samples;

        // Category breakdown
        const catContainer = document.getElementById('benchmark-categories');
        catContainer.innerHTML = Object.entries(data.per_category).map(([cat, metrics]) => {
            const f1Pct = (metrics.f1 * 100).toFixed(1);
            return `
                <div class="category-card">
                    <div class="category-name">${escapeHtml(cat)}</div>
                    <div class="category-metrics">
                        <div class="category-metric">
                            <div class="category-metric-value">${(metrics.precision * 100).toFixed(0)}%</div>
                            <div class="category-metric-label">Precision</div>
                        </div>
                        <div class="category-metric">
                            <div class="category-metric-value">${(metrics.recall * 100).toFixed(0)}%</div>
                            <div class="category-metric-label">Recall</div>
                        </div>
                        <div class="category-metric">
                            <div class="category-metric-value">${f1Pct}%</div>
                            <div class="category-metric-label">F1</div>
                        </div>
                    </div>
                    <div class="metric-bar"><div class="metric-bar-fill" style="width: ${f1Pct}%"></div></div>
                </div>
            `;
        }).join('');

        statusEl.textContent = `Complete — ${data.total_samples} samples tested`;
        showToast('Benchmark complete!', 'success');
    } catch (e) {
        statusEl.textContent = `Error: ${e.message}`;
        showToast('Benchmark failed: ' + e.message, 'error');
    }

    btn.disabled = false;
}

// ═══ Utilities ══════════════════════════════════════════════════════════════
function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
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
        phone: agEl('ag-phone').value.trim(),
        city: agEl('ag-city').value.trim(),
        country: agEl('ag-country').value,
        declared_accounts: (agEl('ag-declared')?.value || '').trim(),
        password: (agEl('ag-password')?.value || ''),
        sandbox: !!agEl('ag-sandbox')?.checked,
        known_usernames: (agEl('ag-usernames')?.value || '').trim(),
        alt_emails: (agEl('ag-altemails')?.value || '').trim(),
        alt_phones: (agEl('ag-altphones')?.value || '').trim(),
        date_of_birth: (agEl('ag-dob')?.value || '').trim(),
        upi_id: (agEl('ag-upi')?.value || '').trim(),
        websites: (agEl('ag-websites')?.value || '').trim(),
        search_guessed_handles: !!agEl('ag-guessed')?.checked,
        aadhaar: (agEl('ag-aadhaar')?.value || '').trim(),
        pan: (agEl('ag-pan')?.value || '').trim(),
    };
}

function traceClear() {
    agEl('agent-trace').innerHTML =
        '<div class="trace-empty">The agent\'s reasoning and every tool call will stream here in real time.</div>';
}

function traceAdd(agent, message, status) {
    const box = agEl('agent-trace');
    const empty = box.querySelector('.trace-empty');
    if (empty) empty.remove();
    const row = document.createElement('div');
    row.className = 'trace-row' + (status === 'error' ? ' err' : '') +
                    (status === 'awaiting_approval' ? ' approval' : '');
    const a = document.createElement('span');
    a.className = 'trace-agent a-' + (agent || 'orchestrator');
    a.textContent = agent || 'agent';
    const m = document.createElement('span');
    m.className = 'trace-msg';
    m.textContent = message;
    row.append(a, m);
    box.appendChild(row);
    box.scrollTop = box.scrollHeight;
}

function traceReasoning(text) {
    const box = agEl('agent-trace');
    const empty = box.querySelector('.trace-empty');
    if (empty) empty.remove();
    const d = document.createElement('div');
    d.className = 'trace-reasoning';
    d.textContent = text;
    box.appendChild(d);
    box.scrollTop = box.scrollHeight;
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

    // A static "Agent working…" for two minutes is indistinguishable from a
    // hang. An LLM planner spends a round trip per decision, so a full run
    // legitimately takes 1-3 minutes — the button has to show that it is
    // progressing, not just that it is busy.
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
    ].map(([l, v]) => `<div class="risk-stat"><div class="risk-stat-v">${v}</div><div class="risk-stat-l">${l}</div></div>`).join('');

    agEl('agent-summary').textContent = msg.summary || '';

    // Approval gate
    Agent.drafted = st.requests.filter(r => r.status === 'awaiting_approval');
    const panel = agEl('approval-panel');
    if (Agent.drafted.length) {
        panel.hidden = false;
        agEl('approval-list').innerHTML = Agent.drafted.map((r, i) => `
            <div class="approval-item">
                <input type="checkbox" id="apv-${i}" value="${r.id}" checked>
                <div class="approval-body">
                    <div class="approval-head">
                        <span class="approval-broker">${agEsc(r.source_name)}</span>
                        <span class="approval-statute">${agEsc(r.statute)}</span>
                    </div>
                    <div class="approval-meta">Ref ${agEsc(r.reference_id)} · respond within ${r.deadline_days} days</div>
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
                            ${it.effort_minutes ? `<span class="plan-min">~${it.effort_minutes} min</span>` : ''}
                            <span class="ev-badge ev-${agEsc(it.evidence_class || '')}">${agEsc((it.evidence_class || '').replace('_', ' '))}</span>
                            ${it.url ? `<a class="plan-link" href="${agEsc(it.url)}" target="_blank" rel="noopener noreferrer">Open removal page ↗</a>` : ''}
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

    // Update Copilot if open
    if (window.AIAssistant) {
        window.AIAssistant.updateContextStats();
    }
}

function updateDashboardFromAgent(st, riskScore) {
    if (!st) return;
    const s = st.summary || {};
    const exposures = (st.exposures || []).filter(e => e.status !== 'not_mine');
    const breaches = exposures.filter(e => e.source_type === 'breach').length;
    const brokers = exposures.filter(e => e.source_type === 'data_broker' || e.source_type === 'public_profile').length;
    const pastes = exposures.filter(e => e.source_type === 'paste').length;

    const score = Math.round(riskScore != null ? riskScore : (s.overall_risk || 0));
    const scoreEl = document.getElementById('risk-score-value');
    if (scoreEl) scoreEl.textContent = score;

    const bEl = document.getElementById('breach-count');
    if (bEl) bEl.textContent = breaches;
    const brEl = document.getElementById('broker-count');
    if (brEl) brEl.textContent = brokers;
    const pEl = document.getElementById('paste-count');
    if (pEl) pEl.textContent = pastes;

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
    const exposures = (st.exposures || []).filter(e => e.status !== 'not_mine');

    exposures.forEach(exp => {
        const isCand = exp.status === 'unconfirmed';
        const d = exp.detail || {};
        const isNotServable = exp.evidence_class === 'judicial_record' || exp.evidence_class === 'statutory_publication';

        let srcType = 'broker';
        let typeBadge = 'Data Broker';
        if (exp.source_type === 'breach') {
            srcType = 'breach';
            typeBadge = 'Verified Breach';
        } else if (exp.source_type === 'paste') {
            srcType = 'paste';
            typeBadge = 'Dark Web Leak';
        } else if (exp.source_type === 'public_profile') {
            srcType = 'broker';
            typeBadge = isCand ? 'Candidate Account (Unconfirmed)' : 'Public Profile';
        }

        let domain = d.url ? d.url.replace(/^https?:\/\//, '').split('/')[0] : (d.website || exp.source_name);
        const card = createExposureCard({
            title: isCand ? `${exp.source_name} (@${exp.record_id})` : exp.source_name,
            source: srcType,
            severity: exp.severity || (isCand ? 'low' : 'medium'),
            domain: domain,
            date: (exp.discovered_at || '').split('T')[0] || (d.date_found ? d.date_found.split('T')[0] : ''),
            pwnCount: d.pwn_count,
            dataClasses: exp.data_found || [],
            type: typeBadge,
            companyName: exp.source_name,
            companyEmail: d.privacy_email || '',
            removalDifficulty: d.removal_difficulty || (exp.status === 'removed' ? 'Removed' : (isCand ? 'Requires Confirmation' : 'Standard')),
            optOutUrl: d.url || d.removal_url || d.opt_out_url || '',
            noNotice: isNotServable || isCand,
        });
        cards.push(card);
    });

    if (cards.length === 0) {
        container.innerHTML = `<div class="glass-card empty-state"><div class="empty-icon">✅</div><h3>No Significant Exposures</h3><p>No critical data exposures were found for the provided identity.</p></div>`;
    } else {
        cards.forEach(c => container.appendChild(c));
    }
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

function agEsc(v) {
    return String(v == null ? '' : v).replace(/[&<>"']/g,
        c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

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
        traceAdd('orchestrator', 'Could not reach the agent: ' + e.message, 'error');
        agentSetBusy(false);
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
        traceAdd('orchestrator', 'Could not reach the agent: ' + e.message, 'error');
        agentSetBusy(false);
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
        agEl('agent-outcome').hidden = true;
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
    } catch (e) { window.__indianSources = []; }
}

document.addEventListener('DOMContentLoaded', () => {
    loadIndianSources();
    if (!document.getElementById('section-agent')) return;
    agentInit();
    agEl('ag-run').addEventListener('click', agentRun);
    agEl('ag-approve').addEventListener('click', agentApprove);
    agEl('ag-reset').addEventListener('click', agentReset);
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
                ${d.url ? `<a class="cand-link" href="${agEsc(d.url)}" target="_blank" rel="noopener noreferrer">view ↗</a>` : ''}
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

async function confirmCandidate(exposureId, isMine, btn) {
    const row = agEl('cand-' + exposureId);
    try {
        const resp = await fetch('/api/agent/confirm', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...agProfile(), exposure_id: exposureId, is_mine: isMine }),
        });
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
    } catch (e) {
        if (row) row.querySelector('.cand-why').textContent = 'Could not save that. Try again.';
    }
}

/* ═══════════════════════════════════════════════════════════════════════════
   Sitewide AI Copilot Assistant Module
   ═══════════════════════════════════════════════════════════════════════════ */

const AIAssistant = {
    isOpen: false,
    history: [],
    currentTab: 'dashboard',

    init() {
        const trigger = document.getElementById('ai-copilot-trigger');
        const panel = document.getElementById('ai-copilot-panel');
        const closeBtn = document.getElementById('copilot-close-btn');
        const clearBtn = document.getElementById('copilot-clear-btn');
        const sendBtn = document.getElementById('copilot-send-btn');
        const input = document.getElementById('copilot-input');

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
            const tag = document.getElementById('copilot-model-tag');
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
        const panel = document.getElementById('ai-copilot-panel');
        if (!panel) return;
        this.isOpen = force !== undefined ? force : !this.isOpen;
        panel.hidden = !this.isOpen;
        if (this.isOpen) {
            this.updateContextStats();
            const input = document.getElementById('copilot-input');
            if (input) setTimeout(() => input.focus(), 150);
        }
    },

    onTabChange(tab) {
        this.currentTab = tab;
        const tabEl = document.getElementById('copilot-active-tab');
        if (tabEl) tabEl.textContent = tab.replace('-', ' ');

        this.updateContextStats();
        this.renderChipsForTab(tab);
    },

    updateContextStats() {
        const riskEl = document.getElementById('copilot-risk-badge');
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
        const chipsContainer = document.getElementById('copilot-chips');
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
            <button class="copilot-chip" data-prompt="${agEsc(c.prompt)}">${agEsc(c.label)}</button>
        `).join('');

        chipsContainer.querySelectorAll('.copilot-chip').forEach(btn => {
            btn.addEventListener('click', () => {
                this.sendMessage(btn.dataset.prompt);
            });
        });
    },

    clearChat() {
        this.history = [];
        const msgContainer = document.getElementById('copilot-messages');
        if (msgContainer) {
            msgContainer.innerHTML = `
                <div class="copilot-msg bot">
                    <div class="copilot-msg-bubble">
                        Chat cleared. How can I assist you with data privacy and statutory rights?
                    </div>
                    <span class="copilot-msg-time">Ready</span>
                </div>
            `;
        }
    },

    async sendMessage(text) {
        if (!text || !text.trim()) return;
        const msgContainer = document.getElementById('copilot-messages');
        if (!msgContainer) return;

        this.appendMessage('user', text);
        this.history.push({ role: 'user', content: text });

        const typingEl = document.createElement('div');
        typingEl.className = 'copilot-typing';
        typingEl.id = 'copilot-typing-indicator';
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
        const msgContainer = document.getElementById('copilot-messages');
        if (!msgContainer) return;

        const msgDiv = document.createElement('div');
        msgDiv.className = `copilot-msg ${role}`;

        const bubble = document.createElement('div');
        bubble.className = 'copilot-msg-bubble';

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
                    btn.className = 'copilot-action-btn';
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
        timeSpan.className = 'copilot-msg-time';
        timeSpan.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        msgDiv.appendChild(bubble);
        msgDiv.appendChild(timeSpan);
        msgContainer.appendChild(msgDiv);
        msgContainer.scrollTop = msgContainer.scrollHeight;
    },

    formatMarkdown(text) {
        if (!text) return '';
        let s = escapeHtml(text);

        // Bold
        s = s.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
        // Inline code
        s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Headers
        s = s.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        s = s.replace(/^## (.*$)/gim, '<h4>$1</h4>');
        // Bullets
        s = s.replace(/^\s*[-•]\s+(.*$)/gim, '<li>$1</li>');
        s = s.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
        // Newlines
        s = s.replace(/\n\n/g, '<p></p>');

        return s;
    }
};

function initAICopilot() {
    window.AIAssistant = AIAssistant;
    AIAssistant.init();
}

