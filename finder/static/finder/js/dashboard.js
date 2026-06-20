/* ==========================================================================
   Abstract Finder - Dashboard JavaScript Core logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // State variables
    let activeTaskId = null;
    let pollingInterval = null;
    let currentPage = 1;
    const pageSize = 20;
    let searchQuery = '';
    let statusFilter = 'all';
    let loadedLogsCount = 0;
    let autoScrollConsole = true;
    let selectedEntryId = null;

    // DOM Elements
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    
    // Screens
    const configScreen = document.getElementById('config-screen');
    const uploadScreen = document.getElementById('upload-screen');
    const progressScreen = document.getElementById('progress-screen');
    const resultsScreen = document.getElementById('results-screen');
    
    // Config Form (Landing)
    const landingConfigForm = document.getElementById('landing-config-form');
    
    // Settings Drawer
    const settingsToggle = document.getElementById('settings-toggle-btn');
    const settingsDrawer = document.getElementById('settings-drawer');
    const settingsClose = document.getElementById('settings-close-btn');
    const settingsOverlay = document.getElementById('drawer-overlay');
    const settingsForm = document.getElementById('settings-form');

    // Guide Drawer
    const guideToggleBtn = document.getElementById('guide-toggle-btn');
    const landingGuideLink = document.getElementById('landing-guide-link');
    const guideDrawer = document.getElementById('guide-drawer');
    const guideCloseBtn = document.getElementById('guide-close-btn');

    // Progress Screen Elements
    const jobFilename = document.getElementById('job-filename');
    const progressStatusText = document.getElementById('progress-status-text');
    const progressPctText = document.getElementById('progress-pct-text');
    const progressBarFill = document.getElementById('progress-bar-fill');
    
    const statProcessed = document.getElementById('stat-processed');
    const statFetched = document.getElementById('stat-fetched');
    const statExisting = document.getElementById('stat-existing');
    const statFailed = document.getElementById('stat-failed');
    
    const consoleLog = document.getElementById('console-log');
    const scrollLockBtn = document.getElementById('scroll-lock-btn');
    const cancelJobBtn = document.getElementById('cancel-job-btn');

    // Results Screen Elements
    const resolvedFilename = document.getElementById('resolved-filename');
    const newJobBtn = document.getElementById('new-job-btn');
    const downloadBtn = document.getElementById('download-resolved-btn');
    
    const cardTotal = document.getElementById('card-total');
    const cardFetched = document.getElementById('card-fetched');
    const cardExisting = document.getElementById('card-existing');
    const cardMissing = document.getElementById('card-missing');
    
    const searchInput = document.getElementById('search-input');
    const filterTabs = document.querySelectorAll('.filter-tab');
    
    const entriesTbody = document.getElementById('entries-tbody');
    const paginationRange = document.getElementById('pagination-range');
    const paginationTotal = document.getElementById('pagination-total');
    const currentPageNum = document.getElementById('current-page-num');
    const prevPageBtn = document.getElementById('prev-page-btn');
    const nextPageBtn = document.getElementById('next-page-btn');

    // Details Drawer Elements
    const detailDrawer = document.getElementById('detail-drawer');
    const detailOverlay = document.getElementById('detail-overlay');
    const detailClose = document.getElementById('detail-close-btn');
    const detailId = document.getElementById('detail-id');
    const detailTitle = document.getElementById('detail-title');
    const detailAuthors = document.getElementById('detail-authors');
    const detailVenue = document.getElementById('detail-venue');
    const detailYear = document.getElementById('detail-year');
    const detailDoiWrapper = document.getElementById('detail-doi-wrapper');
    const detailStatusBadge = document.getElementById('detail-status-badge');
    const detailAbstractTextarea = document.getElementById('detail-abstract-textarea');
    const saveAbstractBtn = document.getElementById('save-abstract-btn');
    const editSaveMsg = document.getElementById('edit-save-msg');

    // Utility: Fetch CSRF Token
    function getCsrfToken() {
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        return csrfInput ? csrfInput.value : '';
    }

    // ==========================================
    // LOCAL CONFIGURATION MANAGEMENT
    // ==========================================
    function checkAndLoadConfig() {
        const s2Key = localStorage.getItem('scholar_key') || '';
        const coreKey = localStorage.getItem('core_key') || '';
        const crossrefEmail = localStorage.getItem('crossref_email') || '';
        const openalexEmail = localStorage.getItem('openalex_email') || '';
        const sleepSecs = localStorage.getItem('sleep_seconds') || '1.0';
        const maxRetries = localStorage.getItem('max_retries') || '4';
        
        // Required fields: Emails and CORE API Key
        const isConfigured = crossrefEmail && openalexEmail && coreKey;
        
        // Sync values to Landing Form
        document.getElementById('landing-s2-key').value = s2Key;
        document.getElementById('landing-core-key').value = coreKey;
        document.getElementById('landing-crossref-mailto').value = crossrefEmail;
        document.getElementById('landing-openalex-mailto').value = openalexEmail;
        document.getElementById('landing-sleep').value = sleepSecs;
        document.getElementById('landing-retries').value = maxRetries;
        
        // Sync values to Settings Drawer Form
        document.getElementById('input-s2-key').value = s2Key;
        document.getElementById('input-core-key').value = coreKey;
        document.getElementById('input-crossref-mailto').value = crossrefEmail;
        document.getElementById('input-openalex-mailto').value = openalexEmail;
        document.getElementById('input-sleep').value = sleepSecs;
        document.getElementById('input-retries').value = maxRetries;
        
        if (isConfigured) {
            settingsToggle.classList.remove('hidden');
            configScreen.classList.add('hidden');
            uploadScreen.classList.remove('hidden');
        } else {
            settingsToggle.classList.add('hidden');
            configScreen.classList.remove('hidden');
            uploadScreen.classList.add('hidden');
        }
    }

    // Call configuration load on startup
    checkAndLoadConfig();

    // Landing Form Save Handler
    landingConfigForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        localStorage.setItem('scholar_key', document.getElementById('landing-s2-key').value.trim());
        localStorage.setItem('core_key', document.getElementById('landing-core-key').value.trim());
        localStorage.setItem('crossref_email', document.getElementById('landing-crossref-mailto').value.trim());
        localStorage.setItem('openalex_email', document.getElementById('landing-openalex-mailto').value.trim());
        localStorage.setItem('sleep_seconds', document.getElementById('landing-sleep').value);
        localStorage.setItem('max_retries', document.getElementById('landing-retries').value);
        
        addLocalLogLine("API credentials saved successfully.", "system");
        checkAndLoadConfig();
    });

    // ==========================================
    // DRAWER HANDLERS (SETTINGS)
    // ==========================================
    function toggleSettings(show) {
        if (show) {
            settingsDrawer.classList.remove('hidden');
            settingsDrawer.classList.add('open');
            settingsOverlay.classList.remove('hidden');
        } else {
            settingsDrawer.classList.remove('open');
            settingsOverlay.classList.add('hidden');
        }
    }

    settingsToggle.addEventListener('click', () => toggleSettings(true));
    settingsClose.addEventListener('click', () => toggleSettings(false));

    // ==========================================
    // DRAWER HANDLERS (GUIDE)
    // ==========================================
    function toggleGuide(show) {
        if (show) {
            guideDrawer.classList.remove('hidden');
            guideDrawer.classList.add('open');
            settingsOverlay.classList.remove('hidden');
        } else {
            guideDrawer.classList.remove('open');
            guideDrawer.classList.add('hidden');
            settingsOverlay.classList.add('hidden');
        }
    }

    if (guideToggleBtn) guideToggleBtn.addEventListener('click', () => toggleGuide(true));
    if (landingGuideLink) landingGuideLink.addEventListener('click', (e) => { e.preventDefault(); toggleGuide(true); });
    if (guideCloseBtn) guideCloseBtn.addEventListener('click', () => toggleGuide(false));

    // Close both drawers when overlay is clicked
    settingsOverlay.addEventListener('click', () => {
        toggleSettings(false);
        toggleGuide(false);
    });

    settingsForm.addEventListener('submit', (e) => {
        e.preventDefault();
        
        localStorage.setItem('scholar_key', document.getElementById('input-s2-key').value.trim());
        localStorage.setItem('core_key', document.getElementById('input-core-key').value.trim());
        localStorage.setItem('crossref_email', document.getElementById('input-crossref-mailto').value.trim());
        localStorage.setItem('openalex_email', document.getElementById('input-openalex-mailto').value.trim());
        localStorage.setItem('sleep_seconds', document.getElementById('input-sleep').value);
        localStorage.setItem('max_retries', document.getElementById('input-retries').value);
        
        toggleSettings(false);
        addLocalLogLine("API configurations updated.", "system");
        checkAndLoadConfig();
    });

    // ==========================================
    // FILE DRAG & DROP
    // ==========================================
    dropZone.addEventListener('click', () => fileInput.click());

    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
        }, false);
    });

    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Upload Execution
    function handleFileUpload(file) {
        if (!file.name.endsWith('.bib') && !file.name.endsWith('.bibtex') && !file.name.endsWith('.csv') && !file.name.endsWith('.ris')) {
            alert("Please upload a valid .bib, .bibtex, .csv, or .ris file.");
            return;
        }

        const formData = new FormData(settingsForm);
        formData.append('file', file);

        // Transition Screen
        uploadScreen.classList.add('hidden');
        progressScreen.classList.remove('hidden');
        jobFilename.textContent = file.name;
        
        // Reset Progress State
        progressStatusText.textContent = "Uploading and parsing file...";
        progressPctText.textContent = "0%";
        progressBarFill.style.width = "0%";
        statProcessed.textContent = "0 / 0";
        statFetched.textContent = "0";
        statExisting.textContent = "0";
        statFailed.textContent = "0";
        
        consoleLog.innerHTML = '<div class="log-line system">[SYSTEM] Uploading bibliography file to server...</div>';
        loadedLogsCount = 1;
        
        fetch('/api/upload/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(err => { throw new Error(err.error || "Upload failed") });
            }
            return response.json();
        })
        .then(data => {
            activeTaskId = data.task_id;
            addLocalLogLine(`Uploaded file successfully. Spawned task: ${activeTaskId}`, "system");
            startPollingTask(activeTaskId);
        })
        .catch(err => {
            addLocalLogLine(`ERROR: ${err.message}`, "error");
            progressStatusText.textContent = "Failed: " + err.message;
            progressBarFill.style.background = "var(--gradient-danger)";
            progressBarFill.style.width = "100%";
        });
    }

    function addLocalLogLine(message, type = "normal") {
        const line = document.createElement('div');
        line.className = `log-line ${type}`;
        const timestamp = new Date().toLocaleTimeString();
        line.textContent = `[${timestamp}] ${message}`;
        consoleLog.appendChild(line);
        if (autoScrollConsole) {
            consoleLog.scrollTop = consoleLog.scrollHeight;
        }
    }

    // ==========================================
    // POLLING WORKFLOW
    // ==========================================
    function startPollingTask(taskId) {
        if (pollingInterval) clearInterval(pollingInterval);
        
        pollingInterval = setInterval(() => {
            fetch(`/api/status/${taskId}/`)
            .then(res => {
                if (!res.ok) throw new Error("Failed to query status");
                return res.json();
            })
            .then(data => {
                updateProgressUI(data);
                
                // If complete, stop polling and show dashboard results
                if (['completed', 'failed', 'cancelled'].includes(data.status)) {
                    clearInterval(pollingInterval);
                    setTimeout(() => {
                        loadResultsDashboard(data);
                    }, 1000);
                }
            })
            .catch(err => {
                addLocalLogLine(`Connection error polling status: ${err.message}`, "error");
            });
        }, 1500);
    }

    function updateProgressUI(task) {
        progressPctText.textContent = `${task.progress_pct}%`;
        progressBarFill.style.width = `${task.progress_pct}%`;
        progressStatusText.textContent = `Fetching abstracts... (${task.status})`;
        
        statProcessed.textContent = `${task.processed_count} / ${task.total_entries}`;
        statFetched.textContent = task.success_count;
        statExisting.textContent = task.existing_count;
        statFailed.textContent = task.failed_count;
        
        // Append logs incrementally
        if (task.logs && task.logs.length > loadedLogsCount) {
            for (let i = loadedLogsCount; i < task.logs.length; i++) {
                const rawLog = task.logs[i];
                const line = document.createElement('div');
                line.className = 'log-line';
                
                // Colorize logs slightly
                if (rawLog.includes('[+] Success')) {
                    line.className = 'log-line success';
                } else if (rawLog.includes('[-] Failed') || rawLog.includes('error') || rawLog.includes('Error')) {
                    line.className = 'log-line error';
                } else if (rawLog.includes('[SYSTEM]') || rawLog.includes('Scan complete')) {
                    line.className = 'log-line system';
                }
                
                line.textContent = rawLog;
                consoleLog.appendChild(line);
            }
            loadedLogsCount = task.logs.length;
            if (autoScrollConsole) {
                consoleLog.scrollTop = consoleLog.scrollHeight;
            }
        }
    }

    // Scroll Lock Toggle
    scrollLockBtn.addEventListener('click', () => {
        autoScrollConsole = !autoScrollConsole;
        scrollLockBtn.classList.toggle('active', autoScrollConsole);
    });

    // Cancel Active Job
    cancelJobBtn.addEventListener('click', () => {
        if (!activeTaskId) return;
        if (!confirm("Are you sure you want to terminate this processing task? Unsaved progress will be resolved up to the current entry.")) return;
        
        fetch(`/api/cancel/${activeTaskId}/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(res => res.json())
        .then(() => {
            addLocalLogLine("Job cancellation requested...", "system");
        })
        .catch(err => {
            alert("Error sending cancellation request: " + err.message);
        });
    });

    // ==========================================
    // PREVIEW RESULTS DASHBOARD
    // ==========================================
    function loadResultsDashboard(task) {
        progressScreen.classList.add('hidden');
        resultsScreen.classList.remove('hidden');
        resolvedFilename.textContent = task.original_filename;
        
        // Populate stats cards
        cardTotal.textContent = task.total_entries;
        cardFetched.textContent = task.success_count;
        cardExisting.textContent = task.existing_count;
        cardMissing.textContent = task.failed_count;
        
        // Reset query conditions
        currentPage = 1;
        searchQuery = '';
        statusFilter = 'all';
        searchInput.value = '';
        
        // Reset filter tab styling
        filterTabs.forEach(tab => {
            tab.classList.toggle('active', tab.getAttribute('data-status') === 'all');
        });
        
        fetchPreviewData();
    }

    function fetchPreviewData() {
        const queryParams = new URLSearchParams({
            page: currentPage,
            page_size: pageSize,
            search: searchQuery,
            status: statusFilter
        });
        
        fetch(`/api/preview/${activeTaskId}/?${queryParams.toString()}`)
        .then(res => res.json())
        .then(data => {
            renderPreviewTable(data);
        })
        .catch(err => {
            console.error("Error loading preview data:", err);
            entriesTbody.innerHTML = `<tr><td colspan="5" class="table-empty error">Failed to load preview items: ${err.message}</td></tr>`;
        });
    }

    function renderPreviewTable(data) {
        entriesTbody.innerHTML = '';
        
        if (!data.entries || data.entries.length === 0) {
            entriesTbody.innerHTML = `<tr><td colspan="5" class="table-empty">No entries matching the criteria found</td></tr>`;
            paginationRange.textContent = "0-0";
            paginationTotal.textContent = "0";
            prevPageBtn.disabled = true;
            nextPageBtn.disabled = true;
            return;
        }
        
        data.entries.forEach(entry => {
            const tr = document.createElement('tr');
            
            // ID column
            const tdId = document.createElement('td');
            const spanId = document.createElement('span');
            spanId.className = 'code-block';
            spanId.textContent = entry.id;
            tdId.appendChild(spanId);
            tr.appendChild(tdId);
            
            // Title & Context column
            const tdTitle = document.createElement('td');
            tdTitle.className = 'paper-title-col';
            
            const spanTitle = document.createElement('span');
            spanTitle.className = 'paper-title';
            spanTitle.textContent = entry.title || "No Title Provided";
            tdTitle.appendChild(spanTitle);
            
            const spanAuthors = document.createElement('span');
            spanAuthors.className = 'paper-authors';
            spanAuthors.textContent = entry.author || "Unknown Authors";
            tdTitle.appendChild(spanAuthors);
            
            const spanMeta = document.createElement('span');
            spanMeta.className = 'paper-meta';
            spanMeta.textContent = `${entry.journal} (${entry.year})`;
            tdTitle.appendChild(spanMeta);

            if (entry.tldr) {
                const tldrDiv = document.createElement('div');
                tldrDiv.className = 'tldr-container';
                
                const tldrBadge = document.createElement('span');
                tldrBadge.className = 'badge-tldr';
                tldrBadge.innerHTML = '<i class="fa-solid fa-bolt"></i> TLDR';
                tldrDiv.appendChild(tldrBadge);
                
                const tldrText = document.createElement('span');
                tldrText.className = 'tldr-text';
                tldrText.textContent = entry.tldr;
                tldrDiv.appendChild(tldrText);
                
                tdTitle.appendChild(tldrDiv);
            }
            
            tr.appendChild(tdTitle);
            
            // DOI column
            const tdDoi = document.createElement('td');
            if (entry.doi) {
                const doiLink = document.createElement('a');
                doiLink.href = `https://doi.org/${entry.doi}`;
                doiLink.target = "_blank";
                doiLink.className = 'doi-link';
                doiLink.innerHTML = `<i class="fa-solid fa-arrow-up-right-from-square"></i> ${entry.doi}`;
                tdDoi.appendChild(doiLink);
            } else {
                tdDoi.innerHTML = '<span class="text-muted">No DOI</span>';
            }
            tr.appendChild(tdDoi);
            
            // Status column
            const tdStatus = document.createElement('td');
            const badge = document.createElement('span');
            badge.className = `badge-tag ${entry.status}`;
            
            let statusText = "Unknown";
            if (entry.status === 'missing') statusText = "Missing";
            else if (entry.status === 'incomplete') statusText = "Incomplete";
            else if (entry.status === 'existing') statusText = "Pre-existing";
            else if (entry.status === 'fetched') statusText = `Fetched (${entry.abstract_source})`;
            else if (entry.status === 'edited') statusText = "Manually Edited";
            
            badge.textContent = statusText;
            tdStatus.appendChild(badge);
            tr.appendChild(tdStatus);
            
            // Actions column
            const tdActions = document.createElement('td');
            const viewBtn = document.createElement('button');
            viewBtn.className = 'icon-btn';
            viewBtn.title = "View / Edit Abstract";
            viewBtn.innerHTML = '<i class="fa-solid fa-pen-to-square"></i>';
            viewBtn.addEventListener('click', () => openDetailDrawer(entry));
            tdActions.appendChild(viewBtn);
            tr.appendChild(tdActions);
            
            entriesTbody.appendChild(tr);
        });
        
        // Update pagination numbers
        const start = (data.page - 1) * data.page_size + 1;
        const end = Math.min(start + data.entries.length - 1, data.total);
        
        paginationRange.textContent = `${start}-${end}`;
        paginationTotal.textContent = data.total;
        currentPageNum.textContent = data.page;
        
        prevPageBtn.disabled = (data.page <= 1);
        nextPageBtn.disabled = (end >= data.total);
    }

    // Pagination Click Events
    prevPageBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            currentPage--;
            fetchPreviewData();
        }
    });

    nextPageBtn.addEventListener('click', () => {
        currentPage++;
        fetchPreviewData();
    });

    // Search input handler (Debounced)
    let searchTimeout = null;
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchQuery = e.target.value.trim();
            currentPage = 1;
            fetchPreviewData();
        }, 300);
    });

    // Filter Tabs
    filterTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            filterTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            statusFilter = tab.getAttribute('data-status');
            currentPage = 1;
            fetchPreviewData();
        });
    });

    // ==========================================
    // DETAIL SLIDE-OUT DRAWER (INLINE EDITING)
    // ==========================================
    function openDetailDrawer(entry) {
        selectedEntryId = entry.id;
        
        detailId.textContent = entry.id;
        detailTitle.textContent = entry.title || "No Title Provided";
        detailAuthors.textContent = entry.author || "Unknown Authors";
        detailVenue.textContent = entry.journal || "N/A";
        detailYear.textContent = entry.year || "N/A";
        
        if (entry.doi) {
            detailDoiWrapper.innerHTML = `<a href="https://doi.org/${entry.doi}" target="_blank" class="doi-link"><i class="fa-solid fa-arrow-up-right-from-square"></i> https://doi.org/${entry.doi}</a>`;
        } else {
            detailDoiWrapper.innerHTML = '<span class="text-muted">N/A</span>';
        }
        
        // Status badge
        detailStatusBadge.className = `badge-tag ${entry.status}`;
        let statusText = "Unknown";
        if (entry.status === 'missing') statusText = "Missing";
        else if (entry.status === 'incomplete') statusText = "Incomplete";
        else if (entry.status === 'existing') statusText = "Pre-existing";
        else if (entry.status === 'fetched') statusText = `Fetched (${entry.abstract_source})`;
        else if (entry.status === 'edited') statusText = "Manually Edited";
        detailStatusBadge.textContent = statusText;
        
        detailAbstractTextarea.value = entry.abstract || '';
        editSaveMsg.classList.add('hidden');
        
        detailDrawer.classList.remove('hidden');
        detailDrawer.classList.add('open');
        detailOverlay.classList.remove('hidden');
    }

    function closeDetailDrawer() {
        detailDrawer.classList.remove('open');
        detailDrawer.classList.add('hidden');
        detailOverlay.classList.add('hidden');
        selectedEntryId = null;
    }

    detailClose.addEventListener('click', closeDetailDrawer);
    detailOverlay.addEventListener('click', closeDetailDrawer);

    // Save Abstract Change
    saveAbstractBtn.addEventListener('click', () => {
        if (!activeTaskId || !selectedEntryId) return;
        
        const newAbstract = detailAbstractTextarea.value.trim();
        
        fetch(`/api/edit/${activeTaskId}/`, {
            method: 'POST',
            body: JSON.stringify({
                entry_id: selectedEntryId,
                abstract: newAbstract
            }),
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken()
            }
        })
        .then(res => {
            if (!res.ok) throw new Error("Failed to save abstract changes");
            return res.json();
        })
        .then(() => {
            editSaveMsg.classList.remove('hidden');
            
            // Update stats cards counts dynamically
            refreshDashboardCounts();
            
            // Reload table items
            fetchPreviewData();
            
            // Hide notification after delay
            setTimeout(() => {
                editSaveMsg.classList.add('hidden');
            }, 3000);
        })
        .catch(err => {
            alert("Error saving abstract: " + err.message);
        });
    });

    function refreshDashboardCounts() {
        fetch(`/api/status/${activeTaskId}/`)
        .then(res => res.json())
        .then(task => {
            cardTotal.textContent = task.total_entries;
            cardFetched.textContent = task.success_count;
            cardExisting.textContent = task.existing_count;
            cardMissing.textContent = task.failed_count;
        });
    }

    // ==========================================
    // DOWNLOAD & RESTART ACTIONS
    // ==========================================
    downloadBtn.addEventListener('click', () => {
        if (!activeTaskId) return;
        window.location.href = `/api/download/${activeTaskId}/?format=bib`;
    });

    const downloadCsvBtn = document.getElementById('download-csv-btn');
    if (downloadCsvBtn) {
        downloadCsvBtn.addEventListener('click', () => {
            if (!activeTaskId) return;
            window.location.href = `/api/download/${activeTaskId}/?format=csv`;
        });
    }

    const downloadRisBtn = document.getElementById('download-ris-btn');
    if (downloadRisBtn) {
        downloadRisBtn.addEventListener('click', () => {
            if (!activeTaskId) return;
            window.location.href = `/api/download/${activeTaskId}/?format=ris`;
        });
    }

    newJobBtn.addEventListener('click', () => {
        if (!confirm("Are you sure you want to exit? Active job details and preview changes will be cleared from this browser session.")) return;
        
        // Reset states
        activeTaskId = null;
        if (pollingInterval) clearInterval(pollingInterval);
        loadedLogsCount = 0;
        
        resultsScreen.classList.add('hidden');
        checkAndLoadConfig();
        
        // Reset input file value
        fileInput.value = '';
    });
});
