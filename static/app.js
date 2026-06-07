document.addEventListener('DOMContentLoaded', () => {
    // Theme Management
    const themeToggle = document.getElementById('theme-toggle');
    const themeToggleIcon = document.getElementById('theme-toggle-icon');
    const themeToggleText = document.getElementById('theme-toggle-text');

    function setTheme(theme) {
        if (theme === 'dark') {
            document.body.classList.add('dark-mode');
            if (themeToggleIcon) themeToggleIcon.setAttribute('data-feather', 'sun');
            if (themeToggleText) themeToggleText.textContent = 'Light Mode';
        } else {
            document.body.classList.remove('dark-mode');
            if (themeToggleIcon) themeToggleIcon.setAttribute('data-feather', 'moon');
            if (themeToggleText) themeToggleText.textContent = 'Dark Mode';
        }
        if (window.feather) {
            try {
                feather.replace();
            } catch (e) {
                console.error('Feather Error:', e);
            }
        }
        localStorage.setItem('theme', theme);
    }

    // Initialize theme
    const savedTheme = localStorage.getItem('theme') || 'light';
    setTheme(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', (e) => {
            e.preventDefault();
            const currentTheme = document.body.classList.contains('dark-mode') ? 'dark' : 'light';
            setTheme(currentTheme === 'dark' ? 'light' : 'dark');
        });
    }

    // Determine the initial target view
    let targetView = localStorage.getItem('target_view');

    // If it's a redirect from landing page, consume it and save as active tab
    if (targetView) {
        localStorage.removeItem('target_view');
        localStorage.setItem('active_tab', targetView);
    } else {
        // Otherwise, restore the last active tab, or default to 'todos'
        targetView = localStorage.getItem('active_tab') || 'todos';
    }

    // Load initial data
    loadData(targetView);

    // Update sidebar active state and page title based on the active tab
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        if (item.getAttribute('data-target') === targetView) {
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');
            const pageTitle = document.getElementById('page-title');
            if (pageTitle) pageTitle.textContent = item.textContent.trim();
        }
    });

    // Configure marked to handle line breaks (GFM style)
    marked.setOptions({
        breaks: true,
        gfm: true
    });

    window.showToast = (message, isError = false) => {
        const toast = document.createElement('div');
        toast.className = 'toast-notification';
        if (isError) toast.style.background = '#cf222e';
        toast.innerHTML = `
            <i data-feather="${isError ? 'alert-circle' : 'check-circle'}" style="width: 18px;"></i>
            <span>${message}</span>
        `;
        document.body.appendChild(toast);
        feather.replace();
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(20px)';
            toast.style.transition = 'all 0.3s ease-in';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    };

    // Mobile Menu Logic
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileCloseBtn = document.getElementById('mobile-close-btn');
    const sidebar = document.getElementById('sidebar');

    // Create overlay element
    const overlay = document.createElement('div');
    overlay.className = 'sidebar-overlay';
    document.body.appendChild(overlay);

    function toggleMobileMenu(show) {
        if (show) {
            sidebar.classList.add('mobile-open');
            overlay.classList.add('active');
        } else {
            sidebar.classList.remove('mobile-open');
            overlay.classList.remove('active');
        }
    }

    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => toggleMobileMenu(true));
    }
    if (mobileCloseBtn) {
        mobileCloseBtn.addEventListener('click', () => toggleMobileMenu(false));
    }
    overlay.addEventListener('click', () => toggleMobileMenu(false));

    // Navigation logic
    const pageTitle = document.getElementById('page-title');

    navItems.forEach(item => {
        // Skip theme toggle in navigation logic
        if (item.id === 'theme-toggle') return;

        item.addEventListener('click', (e) => {
            e.preventDefault();

            // Update active state
            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            // Update title
            const target = item.getAttribute('data-target');
            if (pageTitle) pageTitle.textContent = item.textContent.trim();

            // Load data
            loadData(target);

            // Persist active tab across page reloads
            localStorage.setItem('active_tab', target);

            // Close mobile menu if open
            if (window.innerWidth <= 768) {
                toggleMobileMenu(false);
            }
        });
    });
});

async function fetchApi(endpoint, options = {}) {
    try {
        const url = `/api/${endpoint}`;
        const fetchOptions = { ...options };
        if (fetchOptions.body && !fetchOptions.headers) {
            fetchOptions.headers = {
                'Content-Type': 'application/json'
            };
        }
        const response = await fetch(url, fetchOptions);
        if (!response.ok) throw new Error('Network response was not ok');
        return await response.json();
    } catch (error) {
        console.error(`Error fetching ${endpoint}:`, error);
        return null;
    }
}

async function showConfirmModal(title, message) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('modal-overlay');
        const titleEl = document.getElementById('modal-title');
        const messageEl = document.getElementById('modal-message');
        const cancelBtn = document.getElementById('modal-cancel');
        const confirmBtn = document.getElementById('modal-confirm');

        titleEl.textContent = title;
        messageEl.textContent = message;
        overlay.classList.remove('hidden');

        const cleanup = (result) => {
            overlay.classList.add('hidden');
            cancelBtn.removeEventListener('click', onCancel);
            confirmBtn.removeEventListener('click', onConfirm);
            resolve(result);
        };

        const onCancel = () => cleanup(false);
        const onConfirm = () => cleanup(true);

        cancelBtn.addEventListener('click', onCancel);
        confirmBtn.addEventListener('click', onConfirm);
    });
}



async function loadData(type) {
    window.currentView = type;
    const container = document.getElementById('data-container');

    // Custom render for the interactive skills tool
    if (type === 'skills') {
        renderSkillsForm(container);
        return;
    }

    container.innerHTML = '<div class="loading-state">Loading...</div>';

    if (type === 'todos') {
        const data = await fetchApi('todos');
        renderTodos(data?.todos || [], container);
    } else if (type === 'bookmarks') {
        const data = await fetchApi('bookmarks');
        renderBookmarks(data?.bookmarks || [], container);
    } else if (type === 'jobs') {
        const data = await fetchApi('applications');
        renderJobs(data?.applications || [], container);
    } else if (type === 'scraped_jobs') {
        const data = await fetchApi('scraped-jobs');
        const status = await fetchApi('scraped-jobs/status');
        renderScrapedJobs(data?.jobs || [], status || {}, container);
    } else if (type === 'resumes') {
        const data = await fetchApi('resumes');
        renderResumes(data?.resumes || [], container);
    } else if (type === 'reminders') {
        const data = await fetchApi('reminders');
        renderReminders(data?.reminders || [], container);
    } else if (type === 'crons') {
        const data = await fetchApi('reminders');
        renderCrons(data?.reminders || [], container);
    } else if (type === 'learning') {
        renderLearning(container);
        renderResearch(data?.reports || [], container);
    } else if (type === 'finance') {
        const cats = await fetchApi('finance/categories');
        const trans = await fetchApi(`finance/transactions?month=${currentFinanceMonth}`);
        renderFinance(cats?.categories || [], trans?.transactions || [], container);
    } else if (type === 'nutrition') {
        const d = window.currentNutritionDate || getLocalDateISO();
        const targetsRes = await fetchApi('food/targets');
        const logsRes = await fetchApi(`food/logs?date=${formatDateDDMMYYYY(d)}`);
        renderNutrition(targetsRes?.targets || {}, logsRes?.logs || [], container, logsRes?.date || d);
    } else if (type === 'settings') {
        renderSettings(container);
    } else if (type === 'calendar') {
        const data = await fetchApi('calendar/events');
        renderCalendar(data?.events || [], container);
    } else if (type === 'workouts') {
        const d = window.currentWorkoutDate || getLocalDateISO();
        const data = await fetchApi(`workouts?date=${formatDateDDMMYYYY(d)}`);
        renderWorkouts(data?.workouts || [], container, d);
    } else if (type === 'dumps') {
        const data = await fetchApi('dumps');
        const meta = await fetchApi('dumps/metadata');
        renderDumps(data?.dumps || [], meta || {}, container);
    }
}


// Quick Add Helper
function renderQuickAdd(placeholder, iconName, onSubmit) {
    const container = document.createElement('div');
    container.className = 'quick-add-container';
    container.innerHTML = `
        <div class="quick-add-wrapper">
            <i data-feather="${iconName || 'plus'}" class="quick-add-icon"></i>
            <input type="text" class="quick-add-input" placeholder="${placeholder}" />
            <span class="quick-add-hint">Press Enter ↵</span>
        </div>
    `;

    // Ensure icon renders correctly if appended async
    setTimeout(() => typeof feather !== 'undefined' && feather.replace(), 0);

    const input = container.querySelector('.quick-add-input');
    input.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
            const val = input.value.trim();
            if (val) {
                input.disabled = true;
                const prevPlaceholder = input.placeholder;
                input.placeholder = "Saving...";
                input.value = '';

                const success = await onSubmit(val);

                if (!success) {
                    input.value = val;
                }
                input.disabled = false;
                input.placeholder = prevPlaceholder;
                input.focus();
            }
        }
    });

    return container;
}

// Render Functions
// Render Functions
function renderTodos(todos, container) {
    container.innerHTML = ''; // initial clear

    // Add quick add input
    const quickAdd = renderQuickAdd("Add a new todo...", "check-square", async (val) => {
        try {
            const res = await fetch('/api/todos', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task: val })
            });
            if (res.ok) {
                loadData('todos');
                return true;
            } else {
                window.showToast("Failed to add todo", true);
                return false;
            }
        } catch (e) {
            console.error(e);
            window.showToast("Error adding todo", true);
            return false;
        }
    });
    container.appendChild(quickAdd);

    if (todos.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.innerHTML = 'No todos yet. Add one above!';
        container.appendChild(empty);
        return;
    }

    const list = document.createElement('div');
    list.className = 'data-list';

    todos.forEach(t => {
        const isCompleted = t.status === 'completed';
        const item = document.createElement('div');
        item.className = 'data-item todo-block';

        // Clean up langchain artifact text if present
        const cleanTask = t.task.split("', Additional_Kwargs")[0].replace(/^'|'$/g, '');

        item.innerHTML = `
                <div class="todo-checkbox ${isCompleted ? 'completed' : ''}" data-id="${t.id}" data-status="${t.status}"></div>
                <div class="todo-text ${isCompleted ? 'completed' : ''}">
                    ${cleanTask}
                    ${t.date ? `<div class="todo-date" style="font-size: 11px; color: var(--text-muted); margin-top: 2px; display: flex; align-items: center; gap: 4px;"><i data-feather="calendar" style="width: 11px; height: 11px;"></i>${formatDateDDMMYYYY(t.date)}</div>` : ''}
                </div>
                <div class="todo-delete" data-id="${t.id}" title="Delete Todo">
                    <i data-feather="trash-2" style="width: 14px; height: 14px;"></i>
                </div>
            `;

        // Add event listeners
        const checkbox = item.querySelector('.todo-checkbox');
        const deleteBtn = item.querySelector('.todo-delete');

        checkbox.addEventListener('click', async () => {
            const newStatus = checkbox.dataset.status === 'completed' ? 'pending' : 'completed';
            const id = checkbox.dataset.id;
            checkbox.style.opacity = '0.5'; // loading state
            try {
                const res = await fetch(`/api/todos/${id}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: newStatus })
                });
                if (res.ok) {
                    loadData('todos'); // reload list
                }
            } catch (e) {
                console.error('Failed to update todo', e);
                checkbox.style.opacity = '1';
            }
        });

        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            window.confirmInlineDelete(e.currentTarget, 'todo', t.id);
        });

        list.appendChild(item);
    });

    container.appendChild(list);
    feather.replace(); // Ensure the trash icons are rendered
}

function renderBookmarks(bookmarks, container) {
    container.innerHTML = ''; // initial clear

    // Add quick add input
    const quickAdd = renderQuickAdd("Add a new bookmark...", "bookmark", async (val) => {
        try {
            const res = await fetch('/api/bookmarks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url: val })
            });
            if (res.ok) {
                loadData('bookmarks');
                return true;
            } else {
                window.showToast("Failed to save bookmark", true);
                return false;
            }
        } catch (e) {
            console.error(e);
            window.showToast("Error saving bookmark", true);
            return false;
        }
    });
    container.appendChild(quickAdd);

    if (bookmarks.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.innerHTML = 'No bookmarks saved. Add one above!';
        container.appendChild(empty);
        return;
    }

    const list = document.createElement('div');
    list.className = 'data-list';

    bookmarks.forEach(b => {
        const item = document.createElement('div');
        item.className = 'data-item bookmark-block';

        item.innerHTML = `
                <a href="${b.url}" target="_blank" class="bookmark-link">${b.url}</a>
                <div class="delete-action" title="Delete Bookmark">
                    <i data-feather="trash-2" style="width: 14px; height: 14px;"></i>
                </div>
            `;

        const deleteBtn = item.querySelector('.delete-action');
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            window.confirmInlineDelete(e.currentTarget, 'bookmark', b.id);
        });

        list.appendChild(item);
    });

    container.appendChild(list);
    feather.replace();
}


function renderJobs(jobs, container) {
    if (jobs.length === 0) {
        container.innerHTML = '<div class="empty-state">No job applications tracked yet.</div>';
        return;
    }

    container.innerHTML = `
            <table class="notion-table">
                <thead>
                    <tr>
                        <th>Company</th>
                        <th>Position</th>
                        <th>Recruiter Email</th>
                        <th>Job URL</th>
                        <th>Status</th>
                        <th>Date Applied</th>
                        <th style="width: 40px;"></th>
                    </tr>
                </thead>
                <tbody id="jobs-tbody"></tbody>
            </table>
        `;

    const tbody = document.getElementById('jobs-tbody');
    jobs.forEach(j => {
        const statusOptions = ['Pending', 'Applied', 'Interviewing', 'Offer', 'Rejected'];
        const currentStatus = j.Status || j.status || 'Pending';
        const optionsHtml = statusOptions.map(opt => {
            const selected = currentStatus.toLowerCase() === opt.toLowerCase() ? 'selected' : '';
            return `<option value="${opt}" ${selected}>${opt}</option>`;
        }).join('');

        const tr = document.createElement('tr');
        tr.innerHTML = `
                <td class="editable-cell" contenteditable="true" data-field="company" style="font-weight: 500;">${j.Company || j.company || '-'}</td>
                <td class="editable-cell" contenteditable="true" data-field="position">${j.Position || j.position || '-'}</td>
                <td class="editable-cell" contenteditable="true" data-field="email" style="font-family: monospace; font-size: 13px;">${j.Email || j.email || ''}</td>
                <td>
                    <div style="display: flex; align-items: center; gap: 6px;">
                        <span class="editable-cell" contenteditable="true" data-field="url" style="flex: 1; min-width: 80px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; outline: none; border: none;">${j.URL || j.url || ''}</span>
                        ${(j.URL || j.url) ? `<a href="${j.URL || j.url}" target="_blank" style="color: var(--primary-color); display: flex; align-items: center;" title="Open Job Posting"><i data-feather="external-link" style="width: 13px; height: 13px;"></i></a>` : ''}
                    </div>
                </td>
                <td>
                    <select class="status-select" data-id="${j.id}" data-status="${currentStatus}">
                        ${optionsHtml}
                    </select>
                </td>
                <td class="date-applied-cell">${formatDateDDMMYYYY(j['Date Applied'] || j.Date || j.date || '-')}</td>
                <td style="text-align: right;">
                    <div class="delete-job-btn" data-id="${j.id}" title="Delete Application" style="display: inline-block; cursor: pointer; color: var(--text-muted); opacity: 0.7; transition: opacity 0.2s;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.7">
                        <i data-feather="trash-2" style="width: 14px; height: 14px;"></i>
                    </div>
                </td>
            `;

        const editableCells = tr.querySelectorAll('.editable-cell');
        editableCells.forEach(cell => {
            let originalValue = cell.textContent.trim();
            cell.addEventListener('focus', () => {
                originalValue = cell.textContent.trim();
            });
            cell.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    cell.blur();
                }
            });
            cell.addEventListener('blur', async () => {
                const newValue = cell.textContent.trim();
                if (newValue === originalValue) return;

                const field = cell.dataset.field;
                const res = await fetchApi(`applications/${j.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({ [field]: newValue })
                });

                if (res && res.success) {
                    showToast(`Updated ${field} to "${newValue}"`);
                    originalValue = newValue;
                    if (field === 'url') {
                        const linkEl = cell.parentElement.querySelector('a');
                        if (newValue) {
                            if (linkEl) {
                                linkEl.href = newValue;
                            } else {
                                const newLink = document.createElement('a');
                                newLink.href = newValue;
                                newLink.target = '_blank';
                                newLink.style.cssText = 'color: var(--primary-color); display: flex; align-items: center;';
                                newLink.title = 'Open Job Posting';
                                newLink.innerHTML = '<i data-feather="external-link" style="width: 13px; height: 13px;"></i>';
                                cell.parentElement.appendChild(newLink);
                                if (typeof feather !== 'undefined') feather.replace();
                            }
                        } else if (linkEl) {
                            linkEl.remove();
                        }
                    }
                } else {
                    showToast(`Failed to update ${field}`, true);
                    cell.textContent = originalValue;
                }
            });
        });

        const statusSelect = tr.querySelector('.status-select');
        if (statusSelect && j.id) {
            statusSelect.addEventListener('change', async (e) => {
                const newStatus = e.target.value;
                const res = await fetchApi(`applications/${j.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({ status: newStatus })
                });
                if (res && res.success) {
                    showToast(`Status updated to ${newStatus}`);
                    statusSelect.dataset.status = newStatus;
                    if (newStatus.toLowerCase() === 'applied') {
                        const dateCell = tr.querySelector('.date-applied-cell');
                        if (dateCell) {
                            const today = new Date();
                            const yyyy = today.getFullYear();
                            const mm = String(today.getMonth() + 1).padStart(2, '0');
                            const dd = String(today.getDate()).padStart(2, '0');
                            dateCell.textContent = `${dd}/${mm}/${yyyy}`;
                        }
                    }
                } else {
                    showToast('Failed to update status', true);
                    e.target.value = currentStatus;
                    statusSelect.dataset.status = currentStatus;
                }
            });
        }

        const deleteBtn = tr.querySelector('.delete-job-btn');
        if (deleteBtn && j.id) {
            deleteBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                window.confirmInlineDelete(e.currentTarget, 'job', j.id);
            });
        }

        tbody.appendChild(tr);
    });

    if (typeof feather !== 'undefined') feather.replace();
}


function renderScrapedJobs(jobs, status, container) {
    container.innerHTML = "";

    // 1. Render Scraper Control Header Card
    const controlCard = document.createElement('div');
    controlCard.className = 'notion-card scraper-control-card';
    controlCard.style.padding = '14px 20px';
    controlCard.style.borderRadius = '12px';
    controlCard.style.marginBottom = '24px';
    controlCard.style.background = 'var(--bg-secondary)';
    controlCard.style.border = '1px solid var(--border-light)';

    // Date formatting helper
    let dateStr = "";
    if (status.last_run_time) {
        try {
            dateStr = new Date(status.last_run_time).toLocaleString();
        } catch (e) {
            dateStr = status.last_run_time;
        }
    }

    controlCard.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div style="display: flex; align-items: center; gap: 16px; flex-wrap: wrap;">
                <div id="scraper-status-box" style="display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text-main);">
                    <span class="status-dot" style="width: 8px; height: 8px; border-radius: 50%; display: inline-block; background-color: ${status.is_running ? '#22c55e' : '#888'};"></span>
                    <span><strong>Status:</strong> ${status.status_message}</span>
                </div>
                ${status.last_run_time ? `<div style="font-size: 11px; color: var(--text-muted);">Last run: ${dateStr} (${status.scraped_count} new jobs imported)</div>` : ''}
                ${status.error_message ? `<div style="font-size: 12px; color: var(--danger, #ef4444); font-weight: 500;">⚠️ Error: ${status.error_message}</div>` : ''}
            </div>
            <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                <button id="trigger-scraper-btn" class="notion-button primary" style="display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 6px; font-weight: 500;" ${status.is_running ? 'disabled' : ''}>
                    <i data-feather="play" style="width: 14px; height: 14px;"></i> Run Scraper
                </button>
                <button id="toggle-settings-btn" class="notion-button" style="display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 6px; font-weight: 500; border: 1px solid var(--border-light); background: transparent;">
                    <i data-feather="settings" style="width: 14px; height: 14px;"></i> Settings
                </button>
                <button id="clear-scraped-btn" class="notion-button" style="display: flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 6px; font-weight: 500; border: 1px solid var(--border-light); background: transparent;">
                    <i data-feather="trash-2" style="width: 14px; height: 14px;"></i> Clear All
                </button>
            </div>
        </div>
    `;

    container.appendChild(controlCard);

    // 1.5 Render Scraper Settings Panel (Initially Hidden)
    const settingsPanel = document.createElement('div');
    settingsPanel.id = 'scraper-settings-panel';
    settingsPanel.className = 'notion-card';
    settingsPanel.style.display = 'none';
    settingsPanel.style.padding = '24px';
    settingsPanel.style.borderRadius = '16px';
    settingsPanel.style.marginBottom = '24px';
    settingsPanel.style.background = 'var(--bg-secondary)';
    settingsPanel.style.border = '1px solid var(--border-light)';
    
    settingsPanel.innerHTML = `
        <h3 style="margin: 0 0 16px 0; font-size: 1.1rem; font-weight: 700; color: var(--text-main); display: flex; align-items: center; gap: 8px;">
            <i data-feather="sliders" style="width: 16px; height: 16px;"></i> Scraper Configuration
        </h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 20px;">
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Keywords (comma separated)</label>
                <input type="text" id="cfg-keywords" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Locations (comma separated)</label>
                <input type="text" id="cfg-locations" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Mandatory Skill</label>
                <input type="text" id="cfg-mandatory" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Nice-to-Have Skills (comma separated)</label>
                <input type="text" id="cfg-nice-to-have" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Experience Min (years)</label>
                <input type="number" id="cfg-exp-min" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Experience Max (years)</label>
                <input type="number" id="cfg-exp-max" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Max Pages to Scrape (Naukri)</label>
                <input type="number" id="cfg-naukri-pages" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Pages to Search (LinkedIn/Yahoo)</label>
                <input type="number" id="cfg-yahoo-pages" class="notion-input">
            </div>
            <div>
                <label style="font-size: 11px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; display: block; letter-spacing: 0.5px;">Request Delay (seconds)</label>
                <input type="number" step="0.5" id="cfg-delay" class="notion-input">
            </div>
        </div>
        <div style="display: flex; gap: 12px; justify-content: flex-end;">
            <button id="save-settings-btn" class="notion-button primary" style="font-weight: 600; padding: 8px 16px; border-radius: 6px;">
                Save Config
            </button>
        </div>
    `;
    container.appendChild(settingsPanel);

    // Polling logic for progress if running
    if (status.is_running) {
        if (!window.scraperStatusInterval) {
            window.scraperStatusInterval = setInterval(async () => {
                const currentStatus = await fetchApi('scraped-jobs/status');
                const statusBox = document.getElementById('scraper-status-box');
                const triggerBtn = document.getElementById('trigger-scraper-btn');
                if (statusBox) {
                    statusBox.innerHTML = `
                        <span class="status-dot animate-pulse" style="width: 8px; height: 8px; border-radius: 50%; display: inline-block; background-color: #22c55e;"></span>
                        <span><strong>Status:</strong> ${currentStatus.status_message}</span>
                    `;
                }
                if (!currentStatus.is_running) {
                    clearInterval(window.scraperStatusInterval);
                    window.scraperStatusInterval = null;
                    if (triggerBtn) triggerBtn.disabled = false;
                    loadData('scraped_jobs');
                }
            }, 2000);
        }
    } else {
        if (window.scraperStatusInterval) {
            clearInterval(window.scraperStatusInterval);
            window.scraperStatusInterval = null;
        }
    }

    // Trigger scraper event listener
    const triggerBtn = controlCard.querySelector('#trigger-scraper-btn');
    triggerBtn.addEventListener('click', async () => {
        triggerBtn.disabled = true;
        showToast("Triggering job scraper agent...");
        try {
            const res = await fetch('/api/scraped-jobs/scrape', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
            if (res.ok) {
                showToast("Job scraper started successfully!");
                loadData('scraped_jobs');
            } else {
                showToast("Failed to start scraper", true);
                triggerBtn.disabled = false;
            }
        } catch (e) {
            console.error(e);
            showToast("Error starting scraper", true);
            triggerBtn.disabled = false;
        }
    });

    // Toggle Settings event listener
    const toggleSettingsBtn = controlCard.querySelector('#toggle-settings-btn');
    toggleSettingsBtn.addEventListener('click', async () => {
        if (settingsPanel.style.display === 'none') {
            try {
                const config = await fetchApi('scraped-jobs/config');
                settingsPanel.querySelector('#cfg-keywords').value = (config.keywords || []).join(', ');
                settingsPanel.querySelector('#cfg-locations').value = (config.locations || []).join(', ');
                settingsPanel.querySelector('#cfg-mandatory').value = config.mandatory_skill || '';
                settingsPanel.querySelector('#cfg-nice-to-have').value = (config.nice_to_have || []).join(', ');
                settingsPanel.querySelector('#cfg-exp-min').value = config.exp_min || 0;
                settingsPanel.querySelector('#cfg-exp-max').value = config.exp_max || 0;
                settingsPanel.querySelector('#cfg-naukri-pages').value = config.naukri_max_pages || 3;
                settingsPanel.querySelector('#cfg-yahoo-pages').value = config.search_pages || 2;
                settingsPanel.querySelector('#cfg-delay').value = config.delay_between_reqs || 3.0;
            } catch (e) {
                console.error("Error loading config", e);
                showToast("Error loading configuration", true);
            }
            settingsPanel.style.display = 'block';
            toggleSettingsBtn.style.background = 'var(--hover-bg)';
        } else {
            settingsPanel.style.display = 'none';
            toggleSettingsBtn.style.background = 'transparent';
        }
        if (window.feather) feather.replace();
    });

    // Save Settings event listener
    const saveSettingsBtn = settingsPanel.querySelector('#save-settings-btn');
    saveSettingsBtn.addEventListener('click', async () => {
        saveSettingsBtn.disabled = true;
        saveSettingsBtn.innerHTML = "Saving...";
        
        const keywords = settingsPanel.querySelector('#cfg-keywords').value.split(',').map(s => s.trim()).filter(Boolean);
        const locations = settingsPanel.querySelector('#cfg-locations').value.split(',').map(s => s.trim()).filter(Boolean);
        const mandatory_skill = settingsPanel.querySelector('#cfg-mandatory').value.trim();
        const nice_to_have = settingsPanel.querySelector('#cfg-nice-to-have').value.split(',').map(s => s.trim()).filter(Boolean);
        const exp_min = parseInt(settingsPanel.querySelector('#cfg-exp-min').value) || 0;
        const exp_max = parseInt(settingsPanel.querySelector('#cfg-exp-max').value) || 0;
        const naukri_max_pages = parseInt(settingsPanel.querySelector('#cfg-naukri-pages').value) || 3;
        const search_pages = parseInt(settingsPanel.querySelector('#cfg-yahoo-pages').value) || 2;
        const delay_between_reqs = parseFloat(settingsPanel.querySelector('#cfg-delay').value) || 3.0;
        
        try {
            const res = await fetch('/api/scraped-jobs/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    keywords,
                    locations,
                    naukri_max_pages,
                    search_pages,
                    delay_between_reqs,
                    mandatory_skill,
                    nice_to_have,
                    exp_min,
                    exp_max
                })
            });
            if (res.ok) {
                showToast("Configuration saved successfully!");
                settingsPanel.style.display = 'none';
                toggleSettingsBtn.style.background = 'transparent';
            } else {
                showToast("Failed to save configuration", true);
            }
        } catch (e) {
            console.error("Error saving config", e);
            showToast("Error saving configuration", true);
        } finally {
            saveSettingsBtn.disabled = false;
            saveSettingsBtn.innerHTML = "Save Config";
        }
    });

    // Clear all event listener
    const clearBtn = controlCard.querySelector('#clear-scraped-btn');
    clearBtn.addEventListener('click', async () => {
        const confirmed = await showConfirmModal(
            "Clear all scraped jobs?",
            "Are you sure you want to delete all scraped job listings from the database? This cannot be undone."
        );
        if (confirmed) {
            try {
                const res = await fetch('/api/scraped-jobs', { method: 'DELETE' });
                if (res.ok) {
                    showToast("Database cleared");
                    loadData('scraped_jobs');
                } else {
                    showToast("Failed to clear scraped jobs", true);
                }
            } catch (e) {
                console.error(e);
                showToast("Error clearing jobs", true);
            }
        }
    });

    // 3. Render List Container
    const listContainer = document.createElement('div');
    listContainer.id = 'scraped-jobs-list-container';
    container.appendChild(listContainer);

    // Initial render of table
    renderJobsTable(jobs, listContainer);
}

function renderJobsTable(jobs, container) {
    if (jobs.length === 0) {
        container.innerHTML = '<div class="empty-state" style="padding: 40px; text-align: center; color: var(--text-muted);">No matching scraped jobs found.</div>';
        return;
    }

    container.innerHTML = `
        <table class="notion-table">
            <thead>
                <tr>
                    <th>Job Title</th>
                    <th>Company</th>
                    <th>Location</th>
                    <th>Date Posted</th>
                    <th style="width: 120px; text-align: right;">Actions</th>
                </tr>
            </thead>
            <tbody id="scraped-tbody"></tbody>
        </table>
    `;

    const tbody = container.querySelector('#scraped-tbody');
    jobs.forEach(j => {
        const tr = document.createElement('tr');

        tr.innerHTML = `
            <td>
                <div>
                    <a href="${j.url}" target="_blank" class="bookmark-link" style="font-weight: 600; color: var(--text-main); display: inline-flex; align-items: center; gap: 4px; text-decoration: none;">
                        ${j.title} <i data-feather="external-link" style="width: 11px; height: 11px; opacity: 0.5;"></i>
                    </a>
                </div>
                <div style="font-size: 10px; color: var(--text-muted); opacity: 0.7; margin-top: 3px; max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: var(--font-mono, monospace);" title="${j.url}">
                    ${j.url}
                </div>
            </td>
            <td><span style="font-weight: 500; color: var(--text-muted);">${j.company}</span></td>
            <td><span style="font-size: 13px; color: var(--text-muted);"><i data-feather="map-pin" style="width: 12px; height: 12px; vertical-align: middle; margin-right: 4px;"></i>${j.location}</span></td>
            <td><span style="font-size: 12px; color: var(--text-muted);">${j.date_posted}</span></td>
            <td style="text-align: right; white-space: nowrap;">
                <button class="track-btn notion-button primary" data-company="${j.company.replace(/"/g, '&quot;')}" data-title="${j.title.replace(/"/g, '&quot;')}" style="font-size: 11px; padding: 4px 8px; margin-right: 8px; border-radius: 4px;">
                    <i data-feather="plus" style="width: 10px; height: 10px; vertical-align: middle; margin-right: 2px;"></i>Track
                </button>
                <div class="delete-scraped-btn" data-id="${j.id}" title="Delete listing" style="display: inline-block; cursor: pointer; color: var(--text-muted); opacity: 0.6; padding: 4px;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.6">
                    <i data-feather="trash-2" style="width: 13px; height: 13px;"></i>
                </div>
            </td>
        `;

        // Track job button listener
        const trackBtn = tr.querySelector('.track-btn');
        trackBtn.addEventListener('click', async () => {
            trackBtn.disabled = true;
            trackBtn.innerHTML = `<i data-feather="loader" style="width: 10px; height: 10px; vertical-align: middle; margin-right: 2px;"></i>Tracking...`;
            if (window.feather) feather.replace();
            try {
                const res = await fetch(`/api/scraped-jobs/${j.id}/track`, { method: 'POST' });
                const data = await res.json();
                if (res.ok && data.success) {
                    showToast(data.message || `Tracking ${j.title} at ${j.company}`);
                    // Fade row out and remove — it's now in Job Tracker
                    tr.style.transition = 'opacity 0.3s, transform 0.3s';
                    tr.style.opacity = '0';
                    tr.style.transform = 'translateX(12px)';
                    setTimeout(() => tr.remove(), 310);
                } else {
                    showToast(data.detail || "Failed to track job", true);
                    trackBtn.disabled = false;
                    trackBtn.innerHTML = `<i data-feather="plus" style="width: 10px; height: 10px; vertical-align: middle; margin-right: 2px;"></i>Track`;
                    if (window.feather) feather.replace();
                }
            } catch (e) {
                console.error(e);
                showToast("Error tracking job application", true);
                trackBtn.disabled = false;
                trackBtn.innerHTML = `<i data-feather="plus" style="width: 10px; height: 10px; vertical-align: middle; margin-right: 2px;"></i>Track`;
                if (window.feather) feather.replace();
            }
        });

        // Delete button listener
        const deleteBtn = tr.querySelector('.delete-scraped-btn');
        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            window.confirmInlineDelete(deleteBtn, 'scraped_job', j.id);
        });

        tbody.appendChild(tr);
    });

    if (window.feather) feather.replace();
}


function renderWorkouts(workouts, container, currentDate = '') {
    container.innerHTML = '';

    const quickAdd = renderQuickAdd("Log workout (e.g. 30 pushups, or bench press 3x10 80kg)", "heart", async (val) => {
        try {
            if (!val.trim()) {
                window.showToast("Workout log cannot be empty", true);
                return false;
            }
            const res = await fetch('/api/workouts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: val,
                    date: formatDateDDMMYYYY(currentDate)
                })
            });
            if (res.ok) {
                const data = await res.json();
                window.showToast(data.message || "Workout logged successfully!");
                loadData('workouts');
                return true;
            } else {
                const err = await res.json();
                window.showToast(err.detail || "Failed to log workout", true);
                return false;
            }
        } catch (e) {
            console.error(e);
            window.showToast("Error logging workout", true);
            return false;
        }
    });
    
    container.innerHTML = `
        <div class="workout-dashboard">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                <h2 style="margin: 0; font-size: 1.1rem; font-weight: 700; color: var(--text-main);">Daily Exercises</h2>
                <div class="custom-date-picker-wrapper">
                    <label style="position: relative; padding: 8px 16px; font-size: 13px; font-weight: 600; border-radius: 20px; border: 1px solid var(--border-light); background: var(--bg-secondary); color: var(--text-main); display: flex; align-items: center; gap: 8px; cursor: pointer; transition: all 0.2s;" onclick="const inp = this.querySelector('input'); if(inp.showPicker) inp.showPicker(); else inp.click();">
                        <i data-feather="calendar" style="width: 14px; height: 14px;"></i>
                        <span id="workout-date-display">${formatDateDDMMYYYY(currentDate)}</span>
                        <input type="date" value="${convertToISO(currentDate)}" 
                               style="position: absolute; width:0; height:0; opacity:0; pointer-events:none;"
                               onclick="event.stopPropagation()"
                               onchange="window.currentWorkoutDate = this.value; loadData('workouts');">
                    </label>
                </div>
            </div>
        </div>
    `;
    
    const dashboard = container.querySelector('.workout-dashboard');
    dashboard.appendChild(quickAdd);

    if (workouts.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.innerHTML = 'No workouts logged. Use the bot or the input above!';
        container.appendChild(empty);
        return;
    }

    dashboard.insertAdjacentHTML('beforeend', `
        <div style="margin-top: 24px;">
            <table class="notion-table">
                <thead>
                    <tr>
                        <th>Exercise</th>
                        <th>Sets</th>
                        <th>Reps</th>
                        <th>Weight</th>
                        <th style="width: 40px;"></th>
                    </tr>
                </thead>
                <tbody id="workouts-tbody"></tbody>
            </table>
        </div>
    `);

    const tbody = document.getElementById('workouts-tbody');
    workouts.forEach(w => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td style="font-weight: 600; color: var(--text-main);">${w.exercise}</td>
            <td><span class="badge" style="background: var(--hover-bg); color: var(--text-main); font-weight: 600; padding: 4px 8px; border-radius: 6px;">${w.sets}</span></td>
            <td><span class="badge" style="background: var(--hover-bg); color: var(--text-main); font-weight: 600; padding: 4px 8px; border-radius: 6px;">${w.reps}</span></td>
            <td><span style="font-weight: 700; color: var(--primary);">${w.weight}</span> <span style="font-size: 10px; color: var(--text-muted); text-transform: uppercase;">kg</span></td>
            <td style="text-align: right;">
                <div class="delete-workout-btn" data-id="${w.id}" title="Delete Log" style="cursor: pointer; color: var(--text-muted); opacity: 0.5; transition: all 0.2s;" onmouseover="this.style.opacity=1" onmouseout="this.style.opacity=0.5">
                    <i data-feather="trash-2" style="width: 14px; height: 14px;"></i>
                </div>
            </td>
        `;

        const delBtn = tr.querySelector('.delete-workout-btn');
        delBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            window.confirmInlineDelete(e.currentTarget, 'workout', w.id);
        });

        tbody.appendChild(tr);
    });

    if (typeof feather !== 'undefined') feather.replace();
}

function renderDumps(dumps, metadata, container, activeCategory = null) {
    container.innerHTML = '';

    // Quick Add
    const quickAdd = renderQuickAdd("Dump anything... (notes, recipes, ideas)", "archive", async (val) => {
        try {
            const res = await fetch('/api/dumps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content: val })
            });
            if (res.ok) {
                loadData('dumps');
                return true;
            } else {
                window.showToast("Failed to save dump", true);
                return false;
            }
        } catch (e) {
            console.error(e);
            window.showToast("Error saving dump", true);
            return false;
        }
    });
    container.appendChild(quickAdd);

    // Filters & Metadata
    const filterSection = document.createElement('div');
    filterSection.className = 'dump-filters';
    filterSection.style.margin = '24px 0';
    filterSection.style.display = 'flex';
    filterSection.style.flexWrap = 'wrap';
    filterSection.style.gap = '8px';

    const categories = metadata.categories || [];
    const tags = metadata.tags || [];

    if (categories.length > 0) {
        // Add "All" pill
        const allPill = document.createElement('div');
        allPill.className = `filter-pill${!activeCategory ? ' active' : ''}`;
        allPill.textContent = 'All';
        allPill.onclick = () => loadData('dumps');
        filterSection.appendChild(allPill);

        categories.forEach(cat => {
            const pill = document.createElement('div');
            pill.className = `filter-pill${activeCategory === cat ? ' active' : ''}`;
            pill.textContent = cat;
            pill.onclick = async () => {
                const data = await fetchApi(`dumps?category=${cat}`);
                renderDumps(data?.dumps || [], metadata, container, cat);
            };
            filterSection.appendChild(pill);
        });

        container.appendChild(filterSection);
    }

    if (dumps.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.innerHTML = 'Your Digital Garden is empty. Dump something above!';
        container.appendChild(empty);
        return;
    }

    // Masonry-like grid
    const grid = document.createElement('div');
    grid.className = 'dump-grid';
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = 'repeat(auto-fill, minmax(300px, 1fr))';
    grid.style.gap = '20px';
    grid.style.alignItems = 'start';

    dumps.forEach(d => {
        const card = document.createElement('div');
        card.className = 'notion-card dump-card';
        card.style.padding = '20px';
        card.style.display = 'flex';
        card.style.flexDirection = 'column';
        card.style.gap = '12px';
        card.style.position = 'relative';

        const categoryIcon = {
            'Recipe': 'coffee',
            'Idea': 'zap',
            'Link': 'link',
            'Quote': 'message-square',
            'Code': 'code',
            'Note': 'file-text'
        }[d.category] || 'file-text';

        card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <i data-feather="${categoryIcon}" style="width: 14px; height: 14px; color: var(--primary);"></i>
                    <span style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-muted);">${d.category}</span>
                </div>
                <div class="dump-delete" data-id="${d.id}" style="cursor: pointer; opacity: 0.5; transition: opacity 0.2s;" title="Delete">
                    <i data-feather="trash-2" style="width: 14px; height: 14px;"></i>
                </div>
            </div>
            <h3 style="margin: 0; font-size: 1.1rem; font-weight: 600;">${d.title || 'Untitled'}</h3>
            <div class="dump-content" style="font-size: 14px; line-height: 1.6; color: var(--text-main); overflow: hidden; display: -webkit-box; -webkit-line-clamp: 10; -webkit-box-orient: vertical;">
                ${marked.parse(d.content)}
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: auto; padding-top: 12px;">
                ${d.tags.map(t => `<span class="dump-tag">#${t}</span>`).join('')}
            </div>
        `;

        const delBtn = card.querySelector('.dump-delete');
        delBtn.onmouseover = () => delBtn.style.opacity = '1';
        delBtn.onmouseout = () => delBtn.style.opacity = '0.5';
        delBtn.onclick = (e) => {
            e.stopPropagation();
            window.confirmInlineDelete(delBtn, 'dump', d.id);
        };

        grid.appendChild(card);
    });

    container.appendChild(grid);
    if (typeof feather !== 'undefined') feather.replace();
}

function renderReminders(reminders, container) {
    if (!reminders) return;

    container.innerHTML = ''; // initial clear

    // Add quick add input
    const quickAdd = renderQuickAdd("Remind me to...", "bell", async (val) => {
        try {
            window.showToast("Scheduling reminder...");
            const res = await fetch('/api/reminders', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: val })
            });
            if (res.ok) {
                const data = await res.json();
                window.showToast(data.message || "Reminder set!");
                loadData('reminders');
                return true;
            } else {
                const error = await res.json();
                window.showToast(error.detail || "Failed to schedule reminder", true);
                return false;
            }
        } catch (e) {
            console.error(e);
            window.showToast("Error scheduling reminder", true);
            return false;
        }
    });

    container.appendChild(quickAdd);

    // Filter for ONE-OFF reminders only
    const filteredReminders = reminders.filter(r => !r.is_recurring && !r.message.startsWith('🎓'));

    if (filteredReminders.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.innerHTML = 'No active reminders. Add one above!';
        container.appendChild(empty);
        return;
    }

    const list = document.createElement('div');
    list.className = 'data-list';

    filteredReminders.forEach(r => {
        const item = document.createElement('div');
        item.className = 'data-item reminder-block';

        const isRecurring = r.is_recurring;
        const iconName = isRecurring ? 'refresh-cw' : 'bell';
        const d = r.next_run_time ? new Date(r.next_run_time) : null;
        const dateStr = (d && !isNaN(d.getTime())) ? `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}` : "Not scheduled";

        const scheduleTag = isRecurring ? `<span class="recurring-tag" style="font-size: 0.75rem; background: var(--hover-bg); padding: 2px 6px; border-radius: 4px; margin-left: 8px; color: var(--primary-color); font-weight: 500;">${r.schedule}</span>` : '';

        item.innerHTML = `
                <div class="reminder-icon-container ${isRecurring ? 'recurring' : ''}">
                    <i data-feather="${iconName}" style="width: 20px; height: 20px;"></i>
                </div>
                <div class="reminder-content">
                    <div class="reminder-title">${r.message} ${scheduleTag}</div>
                    <div class="reminder-time">
                        <i data-feather="clock"></i> ${isRecurring ? 'Next:' : ''} ${dateStr}
                    </div>
                </div>
                <div class="reminder-delete" title="Delete ${isRecurring ? 'Task' : 'Reminder'}" data-id="${r.id}">
                    <i data-feather="trash-2" style="width: 16px; height: 16px;"></i>
                </div>
            `;

        const deleteBtn = item.querySelector('.reminder-delete');
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            window.confirmInlineDelete(e.currentTarget, 'reminder', r.id);
        });

        list.appendChild(item);
    });

    container.appendChild(list);
    feather.replace();
}

function renderCrons(reminders, container) {
    if (!reminders) return;

    container.innerHTML = '';

    // Filter for RECURRING tasks only
    const crons = reminders.filter(r => r.is_recurring);

    if (crons.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'empty-state';
        empty.innerHTML = 'No recurring tasks found. You can set them up via the bot!';
        container.appendChild(empty);
        return;
    }

    const list = document.createElement('div');
    list.className = 'data-list';

    crons.forEach(r => {
        const item = document.createElement('div');
        item.className = 'data-item reminder-block';

        const iconName = 'refresh-cw';
        const d = r.next_run_time ? new Date(r.next_run_time) : null;
        const dateStr = (d && !isNaN(d.getTime())) ? `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}` : "Paused / Not scheduled";

        const scheduleTag = `<span class="recurring-tag" style="font-size: 0.75rem; background: var(--hover-bg); padding: 2px 6px; border-radius: 4px; margin-left: 8px; color: var(--primary-color); font-weight: 500;">${r.schedule}</span>`;

        item.innerHTML = `
                <div class="reminder-icon-container recurring">
                    <i data-feather="${iconName}" style="width: 20px; height: 20px;"></i>
                </div>
                <div class="reminder-content">
                    <div class="reminder-title">${r.message} ${scheduleTag}</div>
                    <div class="reminder-time">
                        <i data-feather="clock"></i> Next: ${dateStr}
                    </div>
                </div>
                <div class="reminder-delete" title="Delete Task" data-id="${r.id}">
                    <i data-feather="trash-2" style="width: 16px; height: 16px;"></i>
                </div>
            `;

        const deleteBtn = item.querySelector('.reminder-delete');
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            window.confirmInlineDelete(e.currentTarget, 'reminder', r.id);
        });

        list.appendChild(item);
    });

    container.appendChild(list);
    feather.replace();
}

async function renderLearning(container) {
    container.innerHTML = '<div class="loading-state">Opening your library...</div>';
    renderLibraryView(container);
}

async function renderLibraryView(container) {
    try {
        const res = await fetch('/api/learning/topics');
        const { topics } = await res.json();

        container.innerHTML = '';

        // Add simple quick-add input
        const quickAdd = renderQuickAdd("What do you want to learn? (e.g., 'Python decorators')", "book-open", async (val) => {
            try {
                window.showToast(`AI is identifying best path for "${val}"...`);
                const res = await fetch('/api/learning/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ topic_title: val })
                });

                if (res.ok) {
                    window.showToast("Path generated successfully!");
                    loadData('learning');
                    return true;
                } else {
                    const err = await res.json();
                    window.showToast(err.detail || "Failed to generate path", true);
                    return false;
                }
            } catch (e) {
                console.error(e);
                window.showToast("Error starting generator", true);
                return false;
            }
        });
        container.appendChild(quickAdd);

        if (!topics || topics.length === 0) {
            return;
        }

        const gridContainer = document.createElement('div');
        gridContainer.innerHTML = `
            <div class="topic-grid" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 24px;">
            </div>
        `;
        container.appendChild(gridContainer);
        const grid = gridContainer.querySelector('.topic-grid');
        topics.forEach(t => {
            // Safety fallbacks for progress counts
            const total = t.total_lessons || 5;
            const completed = t.completed_lessons || 0;
            const progress = (completed / total) * 100;
            const isMicro = t.type === 'micro';

            const card = document.createElement('div');
            card.className = 'topic-card notion-card';
            card.style.padding = '24px';
            card.style.background = 'var(--bg-color)';
            card.style.border = '1px solid var(--border-color)';
            card.style.borderRadius = '12px';
            card.style.cursor = 'pointer';
            card.style.transition = 'transform 0.2s, box-shadow 0.2s, border-color 0.2s';
            card.style.display = 'flex';
            card.style.flexDirection = 'column';
            card.style.gap = '16px';
            card.style.position = 'relative';

            card.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div style="background: var(--accent-primary-bg); padding: 10px; border-radius: 10px;">
                        <i data-feather="${isMicro ? 'layers' : (t.status === 'completed' ? 'award' : 'box')}" style="color: var(--primary); width: 24px; height: 24px;"></i>
                    </div>
                    <div style="display: flex; gap: 8px;">
                        ${isMicro ? `
                            <div style="font-size: 0.65rem; font-weight: 800; background: var(--accent-primary-bg); color: var(--primary); padding: 2px 8px; border-radius: 20px; text-transform: uppercase;">🧩 Micro</div>
                        ` : ''}
                        <div style="font-size: 0.75rem; font-weight: 700; color: ${t.status === 'completed' ? 'var(--success)' : 'var(--text-muted)'}; text-transform: uppercase; letter-spacing: 0.05em;">
                            ${t.status === 'completed' ? 'Completed' : 'Active'}
                        </div>
                    </div>
                </div>
                <div>
                    <h3 style="margin: 0 0 8px 0; font-size: 1.2rem; font-weight: 600; color: var(--text-main);">${t.title}</h3>
                    <div style="color: var(--text-muted); font-size: 0.85rem;">
                        ${completed}/${total}
                    </div>
                </div>
                <div class="progress-bar-container" style="background: var(--bg-tertiary); height: 6px; border-radius: 3px; position: relative; margin-top: auto;">
                    <div class="progress-bar-fill" style="background: ${t.status === 'completed' ? 'var(--success)' : 'var(--primary)'}; height: 100%; border-radius: 3px; width: ${progress}%"></div>
                </div>
        `;

            card.onmouseenter = () => {
                card.style.transform = 'translateY(-4px)';
                card.style.borderColor = 'var(--primary)';
                card.style.boxShadow = '0 10px 20px rgba(0,0,0,0.05)';
            };
            card.onmouseleave = () => {
                card.style.transform = 'translateY(0)';
                card.style.borderColor = 'var(--border-color)';
                card.style.boxShadow = 'none';
            };

            card.onclick = () => renderFocusView(t, container);
            grid.appendChild(card);
        });

        feather.replace();
    } catch (err) {
        console.error('Failed to render library:', err);
        container.innerHTML = '<div class="empty-state">Failed to load library.</div>';
    }
}

async function renderFocusView(topic, container) {
    container.innerHTML = '<div class="loading-state">Loading curriculum...</div>';

    try {
        const res = await fetch(`/api/learning/topics/${topic.id}/subtopics`);
        const { subtopics } = await res.json();

        // Blog-style container: centered, vertical
        container.innerHTML = `
            <div class="focus-view blog-style" style="display: flex; flex-direction: column; align-items: center; gap: 32px; height: 100%;">
                <div class="focus-header" style="width: 100%; max-width: 1000px; display: flex; align-items: center; border-bottom: 1px solid var(--border-color); padding-bottom: 24px; margin-bottom: 16px;">
                    <button id="back-to-library" class="notion-button" style="padding: 10px; border-radius: 10px; background: var(--bg-secondary); border: 1px solid var(--border-color); margin-right: 20px;">
                        <i data-feather="arrow-left" style="width: 20px; height: 20px;"></i>
                    </button>
                    <div>
                        <h2 id="current-lesson-title" style="margin: 0; font-size: 1.6rem; font-weight: 700; color: var(--text-main);">Select a Phase</h2>
                    </div>
                </div>

                <div id="lesson-content-container" style="width: 100%; max-width: 1000px; animation: fadeIn 0.4s ease-out;">
                    <!-- Centered Blog Content -->
                </div>
            </div>
        `;

        container.querySelector('#back-to-library').onclick = () => renderLibraryView(container);

        const contentPlace = container.querySelector('#lesson-content-container');

        const firstPending = subtopics.find(s => s.status !== 'completed');
        const initialIdx = firstPending ? subtopics.indexOf(firstPending) : 0;

        renderLessonBlog(subtopics, initialIdx, contentPlace, topic, container);

        feather.replace();
    } catch (err) {
        console.error('Focus view failed:', err);
    }
}

function renderLessonBlog(subtopics, idx, container, topic, mainContainer) {
    const lesson = subtopics[idx];
    if (!lesson) return;

    // Update Header Title
    const titleEl = document.getElementById('current-lesson-title');
    if (titleEl) titleEl.textContent = `${idx + 1}. ${lesson.title}`;

    const meta = (typeof lesson.metadata === 'string') ? JSON.parse(lesson.metadata || '{}') : (lesson.metadata || {});

    // Utility for Section Headers
    const renderSectionHeader = (icon, title, color = 'var(--text-muted)') => `
        <h3 style="font-size: 0.85rem; margin-bottom: 20px; color: ${color}; text-transform: uppercase; letter-spacing: 0.12em; display: flex; align-items: center; gap: 10px; font-weight: 800; border-bottom: 1px solid var(--border-light); padding-bottom: 8px;">
            <i data-feather="${icon}" style="width: 16px; height: 16px;"></i> ${title}
        </h3>
    `;
    // 1. The Mental Model (Main Path) or Logic Bridge (Legacy) or Basics (Micro)
    const mModel = meta.mental_model;
    const bridge = meta.logic_bridge;
    const basics = meta.the_basics;

    let introHtml = '';
    if (mModel) {
        introHtml = `
            <div class="blog-body blog-content" style="font-size: 1.15rem; line-height: 1.7; margin-bottom: 32px;">
                <div style="font-weight: 700; font-size: 1.25rem; color: var(--text-main); margin-bottom: 16px;">${mModel.definition}</div>
                <div style="margin-top: 24px; padding: 24px; background: rgba(0,0,0,0.03); border-radius: 12px; border: 1px dashed var(--border-color); display: flex; align-items: flex-start; gap: 16px;">
                    <i data-feather="link" style="width: 24px; height: 24px; margin-top: 4px; color: var(--text-muted);"></i>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; letter-spacing: 0.05em;">The Mental Model</strong>
                        <div style="font-size: 1.05rem; line-height: 1.6; color: var(--text-main); font-style: italic;">"${mModel.analogy}"</div>
                    </div>
                </div>
            </div>
        `;
    } else if (bridge) {
        introHtml = `
            <div class="blog-body blog-content" style="font-size: 1.15rem; line-height: 1.7; margin-bottom: 32px;">
                ${marked.parse(bridge.root_cause)}
                <div style="margin-top: 24px; padding: 24px; background: rgba(0,0,0,0.03); border-radius: 12px; border: 1px dashed var(--border-color); display: flex; align-items: flex-start; gap: 16px;">
                    <i data-feather="link" style="width: 24px; height: 24px; margin-top: 4px; color: var(--text-muted);"></i>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; letter-spacing: 0.05em;">The Anchor Analogy</strong>
                        <div style="font-size: 1.05rem; line-height: 1.6; color: var(--text-main); font-style: italic;">"${bridge.anchor_analogy}"</div>
                    </div>
                </div>
            </div>
        `;
    } else {
        const realDeal = meta.real_deal || (basics ? basics.simple_def : (lesson.content_summary || ''));
        introHtml = `<div class="blog-body blog-content" style="font-size: 1.15rem; line-height: 1.7; margin-bottom: 32px;">${marked.parse(realDeal)}</div>`;
    }

    // 2. The System Flow (Main Path) or Inner Workings (Legacy) or Expert Lens (Micro)
    const sFlow = meta.system_flow;
    const workings = meta.inner_workings;
    const lens = meta.expert_lens || meta.the_truth;

    let middleHtml = '';
    if (sFlow) {
        middleHtml = `
            <div class="insight-card workings" style="margin-top: 48px; border-top: 1px solid var(--border-light); padding-top: 32px;">
                ${renderSectionHeader('refresh-cw', 'The System Flow', 'var(--text-main)')}
                <div style="margin-bottom: 32px; padding: 20px; background: rgba(0,0,0,0.02); border: 1px solid var(--border-light); border-radius: 12px; display: flex; align-items: center; gap: 16px;">
                    <i data-feather="fast-forward" style="width: 20px; height: 20px; color: var(--text-muted);"></i>
                    <div style="font-size: 1rem; color: var(--text-main);">
                        <strong style="opacity: 0.6; text-transform: uppercase; font-size: 0.7rem; letter-spacing: 0.05em; margin-right: 12px;">I/O Mapping</strong>
                        <span style="font-weight: 500;">${sFlow.io}</span>
                    </div>
                </div>
                <div class="execution-logic-container" style="margin-top: 24px;">
                    <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 20px; letter-spacing: 0.05em;">Execution Logic</strong>
                    <div class="terminal-window" style="background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: 12px; overflow: hidden;">
                        <div class="terminal-header" style="background: var(--hover-bg); padding: 8px 16px; border-bottom: 1px solid var(--border-light); display: flex; gap: 6px;">
                            <div style="width: 8px; height: 8px; border-radius: 50%; background: #ff5f56;"></div>
                            <div style="width: 8px; height: 8px; border-radius: 50%; background: #ffbd2e;"></div>
                            <div style="width: 8px; height: 8px; border-radius: 50%; background: #27c93f;"></div>
                        </div>
                        <ul style="margin: 0; padding: 24px; list-style: none;">
                            ${sFlow.steps.map((step, i) => `
                                <li style="display: flex; gap: 20px; align-items: flex-start; margin-bottom: 20px; border-left: 2px solid var(--border-light); padding-left: 20px; position: relative;">
                                    <span style="position: absolute; left: -11px; top: 0; background: var(--bg-secondary); color: var(--text-muted); font-size: 0.65rem; font-weight: 800; font-family: monospace; padding: 2px 0;">P-${i + 1}</span>
                                    <div style="font-size: 14px; color: var(--text-main); line-height: 1.5; width: 100%;" class="markdown-body compact-md">${marked.parse(step)}</div>
                                </li>
                            `).join('')}
                        </ul>
                    </div>
                </div>
            </div>
        `;
    } else if (workings) {
        middleHtml = `
            <div class="insight-card workings" style="margin-top: 48px; border-top: 1px solid var(--border-light); padding-top: 32px;">
                ${renderSectionHeader('cpu', 'The Inner Workings', 'var(--text-main)')}
                <div style="margin-bottom: 32px;">
                    <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 16px; letter-spacing: 0.05em;">The Blueprint</strong>
                    <ul style="margin: 0; padding: 0; list-style: none;">
                        ${workings.step_by_step_flow.map((step, i) => `
                            <li style="display: flex; gap: 16px; align-items: flex-start; margin-bottom: 16px;">
                                <span style="font-weight: 800; color: var(--text-muted); font-size: 0.9rem; font-family: monospace;">0${i + 1}</span>
                                <div style="font-size: 1rem; color: var(--text-main); line-height: 1.5;">${step}</div>
                            </li>
                        `).join('')}
                    </ul>
                </div>
                <div style="padding: 20px; background: var(--text-main); color: var(--bg-main); border-radius: 8px;">
                    <strong style="display: block; font-size: 0.7rem; text-transform: uppercase; opacity: 0.6; margin-bottom: 8px; letter-spacing: 0.05em;">The Core Truth</strong>
                    <div style="font-size: 1rem; font-weight: 500;">${workings.core_truth}</div>
                </div>
            </div>
        `;
    } else if (lens) {
        const h0 = lens.hidden_cost || lens.the_pain || '';
        const h1 = lens.breaking_point || lens.the_catch || '';
        const h2 = lens.myth || lens.the_no_go || '';
        const label0 = lens.hidden_cost ? 'The Hidden Cost' : 'The Real Pain';
        const label1 = lens.breaking_point ? 'The Breaking Point' : 'The Catch';
        const label2 = lens.myth ? 'The Common Myth' : 'When to say NO';

        middleHtml = `
            <div class="insight-card expert" style="margin-top: 48px; border-top: 1px solid var(--border-light); padding-top: 32px;">
                ${renderSectionHeader('eye', lens.hidden_cost ? 'The Expert Lens' : 'The Reality Check', 'var(--text-main)')}
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 32px;">
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">${label0}</strong>
                        <div style="font-size: 0.95rem; line-height: 1.6; color: var(--text-main);">${h0}</div>
                    </div>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">${label1}</strong>
                        <div style="font-size: 0.95rem; line-height: 1.6; color: var(--text-main);">${h1}</div>
                    </div>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">${label2}</strong>
                        <div style="font-size: 0.95rem; line-height: 1.6; color: var(--text-main);">${h2}</div>
                    </div>
                </div>
            </div>
        `;
    }

    // 3. The Pro Reality (Main Path) or Legacy Reality or Strategic Pivot (Micro)
    const pReality = meta.pro_reality;
    const legacyReality = meta.professional_reality;
    const pivot = meta.strategic_pivot || (meta.the_interview_edge ? meta.the_interview_edge.the_pivot : '');
    const edge = meta.the_interview_edge;

    let bottomHtml = '';
    if (pReality) {
        bottomHtml = `
            <div class="insight-card reality" style="margin-top: 40px; border-top: 1px solid var(--border-light); padding-top: 32px;">
                ${renderSectionHeader('briefcase', 'The Pro Reality', 'var(--text-main)')}
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 32px;">
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">Strategic Trade-off</strong>
                        <div style="font-size: 1rem; line-height: 1.6; color: var(--text-main);">${pReality.trade_off}</div>
                    </div>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">Breaking Point</strong>
                        <div style="font-size: 1rem; line-height: 1.6; color: var(--text-main);">${pReality.breaking_point}</div>
                    </div>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">The Beginner Trap</strong>
                        <div style="font-size: 1rem; line-height: 1.6; color: var(--text-main); font-weight: 500;">${pReality.trap}</div>
                    </div>
                </div>
            </div>
        `;
    } else if (legacyReality) {
        bottomHtml = `
            <div class="insight-card reality" style="margin-top: 40px; border-top: 1px solid var(--border-light); padding-top: 32px;">
                ${renderSectionHeader('briefcase', 'The Professional Reality', 'var(--text-main)')}
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 32px;">
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">The Trade-off</strong>
                        <div style="font-size: 1rem; line-height: 1.6; color: var(--text-main); border-left: 2px solid var(--border-light); padding-left: 20px;">${legacyReality.the_trade_off}</div>
                    </div>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">Stress Test</strong>
                        <div style="font-size: 1rem; line-height: 1.6; color: var(--text-main); border-left: 2px solid var(--border-light); padding-left: 20px;">${legacyReality.breaking_point}</div>
                    </div>
                </div>
            </div>
        `;
    } else if (pivot || edge) {
        bottomHtml = `
            <div class="insight-card strategy" style="margin-top: 32px; border-top: 1px solid var(--border-light); padding-top: 32px;">
                ${renderSectionHeader('zap', edge ? 'The Interview Edge' : 'The Strategic Pivot', 'var(--text-main)')}
                ${edge ? `
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 32px; margin-bottom: 32px;">
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">The Trap</strong>
                        <div style="font-size: 0.95rem; line-height: 1.6; color: var(--text-main);">${edge.junior_trap}</div>
                    </div>
                    <div>
                        <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">The Signal</strong>
                        <div style="font-size: 0.95rem; line-height: 1.6; color: var(--text-main);">${edge.senior_signal}</div>
                    </div>
                </div>
                ` : ''}
                <div style="background: rgba(0,0,0,0.02); padding: 24px; border-radius: 12px; border: 1px solid var(--border-light);">
                    <strong style="display: block; font-size: 0.75rem; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; letter-spacing: 0.05em;">${edge ? 'The Pivot' : 'Strategy'}</strong>
                    <div style="font-size: 1rem; line-height: 1.6; color: var(--text-main); font-style: italic; font-weight: 500;">"${pivot}"</div>
                </div>
            </div>
        `;
    }

    // 4. Scenarios
    let scenariosHtml = '';
    const scenarios = Array.isArray(lesson.examples) ? lesson.examples : (typeof lesson.examples === 'string' ? JSON.parse(lesson.examples || '[]') : []);
    if (scenarios.length > 0) {
        scenariosHtml = `
            <div class="scenarios-section" style="margin-top: 56px;">
                ${renderSectionHeader('book-open', 'Industry Scenarios', 'var(--text-main)')}
                <div style="display: flex; flex-direction: column; gap: 24px;">
                    ${scenarios.map(sc => `
                        <div class="scenario-card" style="padding: 20px; border-radius: 12px; border: 1px solid var(--border-light); background: linear-gradient(145deg, var(--bg-color), var(--bg-secondary)); position: relative; overflow: hidden; margin-bottom: 4px;">
                            <div style="position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: var(--primary); opacity: 0.2;"></div>
                            <div style="font-size: 0.65rem; font-weight: 800; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; letter-spacing: 0.1em; display: flex; align-items: center; gap: 8px;">
                                <i data-feather="terminal" style="width: 12px; height: 12px;"></i> Situation Analysis
                            </div>
                            <div class="scenario-content markdown-body compact-md" style="font-size: 14px; line-height: 1.5; color: var(--text-main);">
                                ${marked.parse(sc)}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    // 5. Practice Questions
    const questionsHtml = (lesson.questions || []).map((qa, i) => {
        const question = typeof qa === 'object' ? (qa.q || qa.question) : qa;
        const answer = typeof qa === 'object' ? (qa.a || qa.answer) : null;

        let answerContent = '';
        if (answer && typeof answer === 'object') {
            answerContent = `
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <div style="border-left: 3px solid var(--border-light); padding-left: 16px;">
                        <strong style="display: block; font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.05em;">Lame Answer</strong>
                        <div style="font-size: 14px; color: var(--text-main); line-height: 1.5;">${answer.red_flag}</div>
                    </div>
                    <div style="border-left: 3px solid var(--border-light); padding-left: 16px;">
                        <strong style="display: block; font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 4px; letter-spacing: 0.05em;">Pro Answer</strong>
                        <div style="font-size: 14px; color: var(--text-main); line-height: 1.5; font-weight: 500;">${answer.pro_answer}</div>
                    </div>
                    <div style="padding: 16px; border-top: 1px solid var(--border-light); font-size: 14px; color: var(--text-main);" class="markdown-body compact-md">
                        <strong style="display: block; font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 8px; letter-spacing: 0.05em;">The Reasoning</strong>
                        <div style="color: var(--text-main);">${marked.parse(answer.why || '')}</div>
                    </div>
                </div>
            `;
        } else if (answer) {
            answerContent = marked.parse(answer || '');
        }

        return `
            <li style="margin-bottom: 20px; list-style: none; border: 1px solid var(--border-color); border-radius: 12px; overflow: hidden;">
                <div style="padding: 24px; cursor: pointer;" class="answer-toggle">
                    <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px;">
                        <div style="font-weight: 700; color: var(--text-main); font-size: 15px;">Q${i + 1}: ${question}</div>
                        <i data-feather="chevron-down" style="width: 20px; opacity: 0.5;"></i>
                    </div>
                </div>
                <div class="answer-content hidden" style="padding: 0 24px 24px 24px; border-top: 1px solid var(--border-light);">
                    <div style="padding-top: 24px;">
                        ${answerContent}
                    </div>
                </div>
            </li>
        `;
    }).join('');

    container.innerHTML = `
        <div class="blog-post" style="max-width: 850px; margin: 0 auto; padding-bottom: 80px;">
            ${introHtml}

            ${middleHtml}
            ${bottomHtml}
            ${scenariosHtml}

            <div class="blog-qa" style="margin-top: 56px;">
                ${renderSectionHeader('shield', 'Practice Gauntlet', 'var(--text-main)')}
                <ul style="margin: 0; padding: 0;">
                    ${questionsHtml}
                </ul>
            </div>

            <div class="blog-footer" style="margin-top: 64px; display: flex; align-items: center; justify-content: space-between; padding-top: 32px; border-top: 1px solid var(--border-color);">
                <div style="display: flex; gap: 12px;">
                    ${idx > 0 ? `
                        <button class="notion-button" id="prev-lesson" style="padding: 10px 16px; border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-main); background: transparent; font-weight: 600; display: flex; align-items: center; cursor: pointer;">
                            <i data-feather="arrow-left" style="width: 16px; height: 16px; margin-right: 6px;"></i> Previous
                        </button>
                    ` : '<span></span>'}
                    
                    ${idx < subtopics.length - 1 ? `
                        <button class="notion-button" id="next-lesson" style="padding: 10px 16px; border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-main); background: transparent; font-weight: 600; display: flex; align-items: center; cursor: pointer;">
                            Next <i data-feather="arrow-right" style="width: 16px; height: 16px; margin-left: 6px;"></i>
                        </button>
                    ` : ''}
                </div>
                
                ${lesson.status !== 'completed' ? `
                    <button class="notion-button primary-btn" id="complete-btn-blog" style="padding: 10px 24px; font-weight: 700; border-radius: 10px; cursor: pointer;">
                        Mark as Mastered
                    </button>
                ` : `
                    <div style="display: flex; align-items: center; gap: 10px; color: var(--success); font-weight: 800; text-transform: uppercase; font-size: 0.9rem; letter-spacing: 0.05em;">
                        <i data-feather="award" style="width: 24px; height: 24px;"></i> Mastered
                    </div>
                `}
            </div>
        </div>
    `;

    // Interaction logic
    container.querySelectorAll('.answer-toggle').forEach(btn => {
        btn.onclick = () => {
            const content = btn.nextElementSibling;
            content.classList.toggle('hidden');
            const icon = btn.querySelector('[data-feather="chevron-down"], [data-feather="chevron-up"]');
            const isHidden = content.classList.contains('hidden');
            if (icon) {
                icon.setAttribute('data-feather', isHidden ? 'chevron-down' : 'chevron-up');
            }
            feather.replace();
        };
    });

    const prevBtn = container.querySelector('#prev-lesson');
    const nextBtn = container.querySelector('#next-lesson');
    if (prevBtn && idx > 0) prevBtn.onclick = () => renderLessonBlog(subtopics, idx - 1, container, topic, mainContainer);
    if (nextBtn && idx < subtopics.length - 1) nextBtn.onclick = () => renderLessonBlog(subtopics, idx + 1, container, topic, mainContainer);

    const completeBtn = container.querySelector('#complete-btn-blog');
    if (completeBtn) {
        completeBtn.onclick = async () => {
            completeBtn.disabled = true;
            try {
                const res = await fetch(`/api/learning/complete/${lesson.id}`, { method: 'POST' });
                const result = await res.json();
                if (result.success) {
                    lesson.status = 'completed';
                    renderLessonBlog(subtopics, idx, container, topic, mainContainer);
                }
            } catch (err) {
                console.error("Failed to complete:", err);
                completeBtn.disabled = false;
            }
        };
    }

    feather.replace();
    mainContainer.scrollTop = 0;
}

function renderResumes(resumes, container) {
    if (resumes.length === 0) {
        container.innerHTML = '<div class="empty-state">No resumes uploaded. Handle via Telegram bot.</div>';
        return;
    }

    const list = document.createElement('div');
    list.className = 'data-list';

    resumes.forEach(r => {
        const item = document.createElement('div');
        item.className = 'data-item';
        item.style.alignItems = 'center';

        const cleanName = r.file_name.includes('_') ? r.file_name.split('_').slice(1).join('_') : r.file_name;

        item.innerHTML = `
                <div class="resume-view-trigger" style="display: flex; align-items: center; gap: 8px; flex: 1; cursor: pointer;">
                    <i data-feather="file-text" style="width: 16px; color: var(--text-muted);"></i>
                    <span class="bookmark-title">${cleanName}</span>
                </div>
                <div class="delete-action" title="Delete Resume">
                    <i data-feather="trash-2" style="width: 14px; height: 14px;"></i>
                </div>
            `;

        const viewTrigger = item.querySelector('.resume-view-trigger');
        viewTrigger.onclick = () => {
            window.open(`/resumes/${r.file_name}`, '_blank');
        };

        const deleteBtn = item.querySelector('.delete-action');
        deleteBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            window.confirmInlineDelete(deleteBtn, 'resume', r.id);
        });

        list.appendChild(item);
    });

    container.innerHTML = '';
    container.appendChild(list);
    feather.replace(); // Ensure icons render
}

async function renderSkillsForm(container) {
    container.innerHTML = `
        <div class="skills-view-wrapper">
            <div class="notion-tabs">
                <button class="notion-tab active" data-tab="tracker">
                    <i data-feather="bar-chart-2" style="width: 14px;"></i> Skill Tracker
                </button>
                <button class="notion-tab" data-tab="analysis">
                    <i data-feather="zap" style="width: 14px;"></i> Gap Analysis
                </button>
            </div>
            
            <div id="skills-tab-content">
                <div class="loading-state">Syncing with Google Sheets...</div>
            </div>
        </div>
    `;

    feather.replace();

    const tabs = container.querySelectorAll(".notion-tab");
    tabs.forEach(tab => {
        tab.onclick = () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            renderTabContent(tab.dataset.tab);
        };
    });

    const contentDiv = container.querySelector("#skills-tab-content");

    async function renderTabContent(tab) {
        if (tab === "tracker") {
            contentDiv.innerHTML = '<div class="loading-state">Fetching your skill gaps...</div>';
            const data = await fetchApi("skills");
            const skills = data?.skills || [];

            contentDiv.innerHTML = '';

            if (skills.length === 0) {
                const empty = document.createElement('div');
                empty.className = 'empty-state';
                empty.innerHTML = `
                    <p>No skill gaps tracked yet. Run an analysis on a Job Description to populate your tracker.</p>
                    <button class="notion-button secondary-btn" style="margin-top: 16px;" onclick="document.querySelector('[data-tab=analysis]').click()">Start Analysis</button>
                `;
                contentDiv.appendChild(empty);
                return;
            }

            // Sort skills by count
            skills.sort((a, b) => b.count - a.count);

            const listContainer = document.createElement('div');
            listContainer.className = 'skills-tracker-view';
            listContainer.innerHTML = `
                    <p style="color: var(--text-muted); margin-bottom: 24px; font-size: 14px;">Skills identified as missing in your tracked applications.</p>
                    <div class="skills-list-container">
                        ${skills.map(s => `
                            <div class="skill-list-item">
                                <div class="skill-info">
                                    <div style="background: var(--hover-bg); padding: 6px; border-radius: 6px;">
                                        <i data-feather="target" style="width: 16px; height: 16px; color: var(--text-muted);"></i>
                                    </div>
                                    <div style="display: flex; align-items: center;">
                                        <span class="skill-name">${s.skill}</span>
                                    </div>
                                </div>
                                <div class="skill-row-actions">
                                    <button class="skill-action-btn learn-btn" data-skill="${s.skill}" title="Generate Roadmap">
                                        <i data-feather="book" style="width: 14px;"></i>
                                    </button>
                                    <button class="skill-delete-btn" data-skill="${s.skill}" title="Remove Skill">
                                        <i data-feather="trash-2" style="width: 14px;"></i>
                                    </button>
                                </div>
                            </div>
                        `).join("")}
                    </div>
                </div>
            `;

            contentDiv.appendChild(listContainer);
            feather.replace();

            // Skill Deletion Handler
            contentDiv.querySelectorAll(".skill-delete-btn").forEach(btn => {
                btn.onclick = () => {
                    const skill = btn.dataset.skill;
                    window.confirmInlineDelete(btn, 'skill', skill);
                };
            });

            // Learning Trigger
            contentDiv.querySelectorAll(".learn-btn").forEach(btn => {
                btn.onclick = async () => {
                    const skill = btn.dataset.skill;
                    showToast(`Generating 5-day roadmap for "${skill}"...`);
                    try {
                        const res = await fetch("/api/skills/learn", {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ skill: skill })
                        });
                        if (res.ok) {
                            showToast("Roadmap generated! Check 'Learning' tab.");
                        }
                    } catch (e) { console.error(e); }
                };
            });

        } else if (tab === "analysis") {
            contentDiv.innerHTML = `
                <div class="skills-tool-container">
                    <div class="selector-overlay">
                        <h3 style="font-size: 14px; font-weight: 600; margin-bottom: 12px; color: var(--text-main);">Analyze New Application</h3>
                        <textarea id="jd-input" class="notion-textarea" placeholder="Paste Job Description here..." rows="8" style="margin-top: 12px;"></textarea>
                        <button id="analyze-btn" class="notion-button primary-btn" style="margin-top: 16px; width: 100%; height: 40px; font-weight: 700; border-radius: 8px;">Analyze Gaps</button>
                    </div>
                    
                    <div id="analysis-result" class="analysis-card hidden"></div>
                </div>
            `;

            feather.replace();

            const analyzeBtn = contentDiv.querySelector("#analyze-btn");
            const jdInput = contentDiv.querySelector("#jd-input");
            const resultDiv = contentDiv.querySelector("#analysis-result");

            analyzeBtn.onclick = async () => {
                const jd = jdInput.value.trim();
                if (!jd) { alert("Please provide a Job Description."); return; }

                analyzeBtn.disabled = true;
                analyzeBtn.innerHTML = 'Analyzing... <span class="loader"></span>';
                resultDiv.classList.add("hidden");
                resultDiv.innerHTML = '<div class="empty-state">Agent is identifying gaps...</div>';

                try {
                    const res = await fetch("/api/analyze-skills", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ job_description: jd })
                    });
                    const data = await res.json();
                    if (data.analysis) {
                        resultDiv.classList.remove("hidden");
                        resultDiv.innerHTML = marked.parse(data.analysis);
                    } else {
                        resultDiv.classList.remove("hidden");
                        resultDiv.innerHTML = '<div class="empty-state">No analysis returned.</div>';
                    }
                } catch (err) {
                    resultDiv.classList.remove("hidden");
                    resultDiv.innerHTML = `<div class="empty-state" style="color: #e03e3e;">Error: ${err.message}</div>`;
                } finally {
                    analyzeBtn.disabled = false;
                    analyzeBtn.innerHTML = "Analyze Gaps";
                    feather.replace();
                }
            };
        }
    }

    // Initial load
    renderTabContent("tracker");
}

// --- Finance Rendering ---
let currentFinanceMonth = (() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, '0');
    return `${y}-${m}`;
})();

window.changeFinanceMonth = function (offset) {
    let [y, m] = currentFinanceMonth.split('-').map(Number);
    m += offset;
    while (m > 12) {
        m -= 12;
        y += 1;
    }
    while (m < 1) {
        m += 12;
        y -= 1;
    }
    currentFinanceMonth = `${y}-${String(m).padStart(2, '0')}`;
    loadData('finance');
};

function formatMonthYear(yyyymm) {
    const [y, m] = yyyymm.split('-');
    const d = new Date(y, m - 1, 1);
    return d.toLocaleString('default', { month: 'long', year: 'numeric' });
}

function renderFinance(categories, transactions, container) {
    if (!container) return;

    // Calculate Summary
    const totalExpense = transactions
        .filter(t => t.category_type === 'expense')
        .reduce((sum, t) => sum + t.amount, 0);

    const totalIncome = transactions
        .filter(t => t.category_type === 'income')
        .reduce((sum, t) => sum + t.amount, 0);

    const balance = totalIncome - totalExpense;
    const balanceClass = balance >= 0 ? "finance-positive" : "finance-negative";

    const displayMonth = formatMonthYear(currentFinanceMonth);

    let html = `
        <div class="finance-dashboard">
            <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 24px; gap: 16px;">
                <button onclick="changeFinanceMonth(-1)" class="icon-btn" style="background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: 8px; padding: 6px; color: var(--text-muted);" title="Previous Month">
                    <i data-feather="chevron-left" style="width: 18px; height: 18px;"></i>
                </button>
                <div style="font-size: 1.1rem; font-weight: 700; color: var(--text-main); min-width: 140px; text-align: center;">
                    ${displayMonth}
                </div>
                <button onclick="changeFinanceMonth(1)" class="icon-btn" style="background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: 8px; padding: 6px; color: var(--text-muted);" title="Next Month">
                    <i data-feather="chevron-right" style="width: 18px; height: 18px;"></i>
                </button>
            </div>
            
            <div class="finance-header-cards">
                <div class="finance-card">
                    <div class="finance-card-title">Total Income</div>
                    <div class="finance-card-val finance-positive">₹${totalIncome.toFixed(2)}</div>
                </div>
                <div class="finance-card">
                    <div class="finance-card-title">Total Expenses</div>
                    <div class="finance-card-val finance-negative">₹${totalExpense.toFixed(2)}</div>
                </div>
                <div class="finance-card">
                    <div class="finance-card-title">Net Balance</div>
                    <div class="finance-card-val ${balanceClass}">₹${balance.toFixed(2)}</div>
                </div>
            </div>

            <div class="finance-grid" id="finance-grid-container" style="grid-template-columns: 1fr;">
                <!-- Transactions Column -->
                <div class="finance-transactions-col">
                    <div class="flex-between mb-4">
                        <h3 class="section-title" style="margin: 0;">Recent Transactions</h3>
                        <button onclick="toggleCategoriesPanel()" style="background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: 12px; padding: 2px 6px; display: flex; align-items: center; gap: 4px; color: var(--text-muted); font-size: 11px; font-weight: 500; cursor: pointer; transition: all 0.2s; box-shadow: 0 1px 2px rgba(0,0,0,0.02);" onmouseover="this.style.background='var(--hover-bg)'; this.style.color='var(--text-main)';" onmouseout="this.style.background='var(--bg-secondary)'; this.style.color='var(--text-muted)';">
                            <i data-feather="sidebar" style="width: 12px; height: 12px;"></i>
                            Categories
                        </button>
                    </div>

                    `;

    const isCurrentMonth = currentFinanceMonth === (() => {
        const today = new Date();
        const y = today.getFullYear();
        const m = String(today.getMonth() + 1).padStart(2, '0');
        return `${y}-${m}`;
    })();

    if (isCurrentMonth) {
        const todayStr = formatDateDDMMYYYY(getLocalDateISO());
        html += `
                    <div class="quick-add-container" style="margin-bottom: 16px;">
                        <div class="quick-add-wrapper">
                            <i data-feather="plus" class="quick-add-icon"></i>
                            <input type="text" id="finance-input" class="quick-add-input" placeholder="What did you spend? (e.g., uber 200, dosa 150)" onkeypress="handleFinanceInput(event)" />
                            <label class="finance-date-picker-label" style="position: relative; border-left: 1px solid var(--border-light); padding: 0 16px; display: flex; align-items: center; gap: 8px; cursor: pointer; background: var(--bg-secondary); min-width: 140px; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1); border-top-right-radius: 12px; border-bottom-right-radius: 12px;" 
                                onmouseover="this.style.background='var(--hover-bg)'; this.style.borderColor='var(--border-color)';" 
                                onmouseout="this.style.background='var(--bg-secondary)'; this.style.borderColor='var(--border-light)';"
                                onclick="const inp = this.querySelector('input'); if(inp.showPicker) inp.showPicker(); else inp.click();">
                                <i data-feather="calendar" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                                <span id="finance-date-display" style="font-size: 13px; color: var(--text-main); font-weight: 600; letter-spacing: 0.01em;">${formatDateDDMMYYYY(todayStr)}</span>
                                <input type="date" id="finance-date-input" value="${convertToISO(todayStr)}" 
                                    style="position: absolute; width:0; height:0; opacity:0; pointer-events:none;" 
                                    onclick="event.stopPropagation()"
                                    onchange="document.getElementById('finance-date-display').textContent = formatDateDDMMYYYY(this.value);" />
                            </label>
                        </div>
                    </div>
        `;
    }

    html += `
                    
                    <div class="data-list" style="margin-top: 16px; width: 100%;">
    `;

    if (transactions.length === 0) {
        html += `<div class="empty-state" style="text-align: center; padding: 24px;">No transactions logged yet.</div>`;
    } else {
        transactions.forEach(t => {
            const isIncome = t.category_type === 'income';
            const amountPrefix = isIncome ? "+" : "-";
            const amountClass = isIncome ? "finance-positive" : "";

            // Format the item name (description) and fallback to category if empty
            const itemName = t.description || 'Unknown Item';

            html += `
                <!-- Display Row -->
                <div id="trans-row-${t.id}" class="data-item finance-item" style="cursor: pointer; padding: 12px; border-radius: 8px; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between; border: 1px solid var(--border-light);" onclick="toggleDetailsVisibility(${t.id})">
                    <div style="flex: 1; display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
                        <div style="display: flex; align-items: center; min-width: 150px;">
                            <span style="font-weight: 600; color: var(--text-main);">${itemName}</span>
                            <span id="trans-details-${t.id}" style="display: none; margin-left: 12px; align-items: center; gap: 8px;">
                                <span style="background: rgba(var(--primary-rgb), 0.1); border: 1px solid rgba(var(--primary-rgb), 0.2); padding: 4px 10px; border-radius: 100px; font-size: 11px; font-weight: 500; color: var(--primary); display: inline-flex; align-items: center; white-space: nowrap;">
                                    ${t.category_name}
                                </span>
                                <span style="background: var(--bg-secondary); border: 1px solid var(--border-light); padding: 4px 10px; border-radius: 100px; font-size: 11px; font-weight: 500; color: var(--text-muted); display: inline-flex; align-items: center; white-space: nowrap;">
                                    <i data-feather="calendar" style="width: 12px; height: 12px; margin-right: 6px;"></i>
                                    ${formatDateDDMMYYYY(t.date_logged)}
                                </span>
                            </span>
                        </div>
                    </div>
                    <div style="display: flex; align-items: center; gap: 16px;">
                        <span style="font-weight: 600; font-size: 15px; min-width: 80px; text-align: right;" class="${amountClass}">${amountPrefix}₹${t.amount.toFixed(2)}</span>
                        <div style="display: flex; gap: 4px;">
                            <button class="icon-btn edit-btn" onclick="event.stopPropagation(); toggleEditTransaction(${t.id})" title="Edit Transaction" style="background: transparent; border: none; box-shadow: none; padding: 4px;">
                                <i data-feather="edit-2" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                            </button>
                            <button class="icon-btn delete-btn" onclick="event.stopPropagation(); window.confirmInlineDelete(this, 'transaction', ${t.id})" title="Delete Transaction" style="background: transparent; border: none; box-shadow: none; padding: 4px;">
                                <i data-feather="trash-2" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                            </button>
                        </div>
                    </div>
                </div>
                <!-- Edit Row (Hidden by default) -->
                <div id="trans-edit-${t.id}" class="data-item finance-item finance-edit" style="display: none; padding: 12px; border-radius: 8px; margin-bottom: 4px; border: 1px solid var(--border-light); background: var(--bg-secondary); align-items: center; justify-content: space-between; gap: 16px; flex-wrap: wrap;">
                    <div style="flex: 1; display: flex; align-items: center; gap: 8px; min-width: 250px;">
                        <input type="text" id="edit-desc-${t.id}" class="notion-input" value="${escapeQuote(t.description)}" placeholder="Item name" style="flex: 2; padding: 6px; font-size: 13px;">
                        <select id="edit-cat-${t.id}" class="notion-input" style="flex: 1; padding: 6px; font-size: 13px; max-width: 140px;">
                            ${categories.map(c => `<option value="${c.id}" ${c.id === t.category_id ? 'selected' : ''}>${c.name}</option>`).join('')}
                        </select>
                    </div>
                    <div style="display: flex; align-items: center;">
                        <label style="position: relative; display: flex; align-items: center; gap: 6px; cursor: pointer; background: var(--bg-tertiary); border: 1px solid var(--border-light); padding: 4px 8px; border-radius: 4px; min-width: 110px;" onclick="const inp = this.querySelector('input'); if(inp.showPicker) inp.showPicker(); else inp.click();">
                            <i data-feather="calendar" style="width: 12px; height: 12px; color: var(--text-muted);"></i>
                            <span id="edit-date-display-${t.id}" style="font-size: 12px; color: var(--text-main);">${formatDateDDMMYYYY(t.date_logged)}</span>
                            <input type="date" id="edit-date-${t.id}" value="${convertToISO(t.date_logged)}" 
                                   style="position: absolute; width:0; height:0; opacity:0; pointer-events:none;"
                                   onclick="event.stopPropagation()"
                                   onchange="document.getElementById('edit-date-display-${t.id}').textContent = formatDateDDMMYYYY(this.value);">
                        </label>
                    </div>
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <input type="number" step="0.01" id="edit-amount-${t.id}" class="notion-input" value="${t.amount}" style="width: 100px; text-align: right; padding: 6px; font-size: 13px;">
                        <div style="display: flex; gap: 4px;">
                            <button class="icon-btn" onclick="submitInlineEdit(${t.id})" title="Save" style="background: var(--success); color: white; border: none; padding: 4px; border-radius: 4px;">
                                <i data-feather="check" style="width: 14px; height: 14px;"></i>
                            </button>
                            <button class="icon-btn delete-btn" onclick="toggleEditTransaction(${t.id})" title="Cancel" style="background: transparent; border: none; box-shadow: none; padding: 4px;">
                                <i data-feather="x" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    html += `
                    </div>
                </div>

                <!-- Categories Column -->
                <div class="finance-categories-col" id="finance-categories-panel" style="display: none;">
                    <div class="flex-between mb-4">
                        <h3 class="section-title" style="margin: 0;">Categories</h3>
                        <button class="notion-button primary empty-state" onclick="showAddCategoryModal()" style="padding: 4px 12px; font-size: 13px;">+ Add</button>
                    </div>

                    <div class="notion-list" style="margin-top: 16px;">
    `;

    if (categories.length === 0) {
        html += `<div class="notion-list-item empty-state">No categories found.</div>`;
    } else {
        categories.forEach(c => {
            html += `
                <div class="notion-list-item" style="padding: 6px 12px; margin-bottom: 2px; border-radius: 4px;">
                    <div class="item-content flex-space-between w-100" style="display: flex; align-items: center; justify-content: space-between;">
                        <span style="font-weight: 400; font-size: 13px;">${c.name}</span>
                        <button class="icon-btn delete-btn" onclick="event.stopPropagation(); window.confirmInlineDelete(this, 'category', ${c.id})" title="Delete Category" style="margin-left: 8px; border: none; background: transparent; box-shadow: none; padding: 2px;">
                            <i data-feather="trash-2" style="width: 12px; height: 12px; color: var(--text-muted);"></i>
                        </button>
                    </div>
                </div>
            `;
        });
    }

    html += `
                    </div>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
    if (window.feather) {
        try {
            feather.replace();
        } catch (e) {
            console.error('Feather Error:', e);
        }
    }
}

window.selectCatType = function (val, btnElem) {
    document.getElementById('new-cat-type').value = val;
    document.querySelectorAll('#cat-type-segment .segment-btn').forEach(btn => btn.classList.remove('active'));
    if (btnElem) {
        btnElem.classList.add('active');
    }
};

window.showAddCategoryModal = function () {
    // Reset state
    document.getElementById('new-cat-name').value = '';
    const expenseBtn = document.querySelector('#cat-type-segment .segment-btn[data-value=\"expense\"]');
    if (expenseBtn) window.selectCatType('expense', expenseBtn);

    document.getElementById('add-category-modal').style.display = 'flex';
    // Re-initialize feather icons in case new ones were added dynamically
    if (window.feather) {
        try {
            feather.replace();
        } catch (e) {
            console.error('Feather Error:', e);
        }
    }
};

window.cancelAddCategory = function () {
    document.getElementById('add-category-modal').style.display = 'none';
    document.getElementById('new-cat-name').value = '';
};

window.submitAddCategory = async function () {
    const name = document.getElementById('new-cat-name').value.trim();
    const type = document.getElementById('new-cat-type').value;

    if (!name) {
        showToast("Category name is required", true);
        return;
    }

    try {
        const res = await fetch('/api/finance/categories', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, type })
        });

        if (res.ok) {
            showToast("Category added successfully");
            cancelAddCategory();
            loadData('finance');
        } else {
            const d = await res.json();
            showToast(d.detail || "Failed to add category", true);
        }
    } catch (e) {
        showToast("Error adding category", true);
    }
};

window.confirmInlineDelete = function (element, type, id) {
    if (element.dataset.confirming === 'true') {
        element.innerHTML = '<i data-feather="loader" style="width: 14px; height: 14px; animation: spin 1s linear infinite;"></i>';
        if (window.feather) { try { feather.replace(); } catch (e) { } }
        window.deleteItem(type, id, true);
    } else {
        element.dataset.confirming = 'true';
        element.style.opacity = '1';
        element.innerHTML = '<i data-feather="check" style="width: 14px; height: 14px; color: var(--danger);"></i>';
        if (window.feather) {
            try {
                feather.replace();
            } catch (e) {
                console.error('Feather Error:', e);
            }
        }

        // Reset after 5 seconds if not confirmed
        setTimeout(() => {
            if (element && element.dataset.confirming === 'true' && document.contains(element)) {
                element.dataset.confirming = 'false';
                element.style.opacity = '';
                element.innerHTML = '<i data-feather="trash-2" style="width: 14px; height: 14px; color: var(--text-muted);"></i>';
                if (window.feather) {
                    try {
                        feather.replace();
                    } catch (e) {
                        console.error('Feather Error:', e);
                    }
                }
            }
        }, 3000);
    }
};

window.deleteItem = async function (type, id, skipConfirm = false) {
    if (!skipConfirm) {
        const confirmed = await showConfirmModal(
            `Delete ${type.charAt(0).toUpperCase() + type.slice(1)}?`,
            `Are you sure you want to remove this ${type}? This action cannot be undone.`
        );
        if (!confirmed) return;
    }

    let endpoint = "";
    let dataTab = "";

    // Comprehensive mappings for all item types
    if (type === 'todo') { endpoint = `todos/${id}`; dataTab = 'todos'; }
    else if (type === 'bookmark') { endpoint = `bookmarks/${id}`; dataTab = 'bookmarks'; }
    else if (type === 'resume') { endpoint = `resumes/${id}`; dataTab = 'resumes'; }
    else if (type === 'reminder') { endpoint = `reminders/${id}`; dataTab = 'reminders'; }
    else if (type === 'workout') { endpoint = `workouts/${id}`; dataTab = 'workouts'; }
    else if (type === 'dump') { endpoint = `dumps/${id}`; dataTab = 'dumps'; }
    else if (type === 'category') { endpoint = `finance/categories/${id}`; dataTab = 'finance'; }
    else if (type === 'transaction') { endpoint = `finance/transactions/${id}`; dataTab = 'finance'; }
    else if (type === 'food') { endpoint = `food/logs/${id}`; dataTab = 'nutrition'; }
    else if (type === 'skill') { endpoint = `skills`; dataTab = 'skills'; }
    else if (type === 'job') { endpoint = `applications/${id}`; dataTab = 'jobs'; }
    else if (type === 'scraped_job') { endpoint = `scraped-jobs/${id}`; dataTab = 'scraped_jobs'; }
    else if (type === 'calendar') { endpoint = `calendar/events/${id}`; dataTab = 'calendar'; }


    if (!endpoint) {
        console.error(`No delete mapping for type: ${type}`);
        return;
    }

    try {
        const options = { method: 'DELETE' };
        if (type === 'skill') {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify({ skill: id });
        }

        const res = await fetch(`/api/${endpoint}`, options);
        if (res.ok) {
            showToast(`${type.charAt(0).toUpperCase() + type.slice(1)} deleted`);
            loadData(dataTab || document.querySelector('.nav-item.active')?.getAttribute('data-target'));
        } else {
            const d = await res.json();
            showToast(d.detail || `Failed to delete ${type}`, true);
        }
    } catch (e) {
        showToast(`Error deleting ${type}`, true);
    }
};

// --- Nutrition Rendering ---
function escapeQuote(str) {
    if (!str) return '';
    return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function getLocalDateISO() {
    const d = new Date();
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function formatDateDDMMYYYY(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    // If it's YYYY-MM-DD, convert to DD-MM-YYYY
    if (parts[0].length === 4) return `${parts[2]}-${parts[1]}-${parts[0]}`;
    return dateStr;
}

function convertToISO(dateStr) {
    if (!dateStr) return '';
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    // If it's DD-MM-YYYY, convert to YYYY-MM-DD
    if (parts[2].length === 4) return `${parts[2]}-${parts[1]}-${parts[0]}`;
    return dateStr;
}

function renderNutrition(targets, logs, container, currentDate = '') {
    if (!container) return;

    // Calculate Totals
    let totalCal = 0, totalPro = 0, totalCarbs = 0, totalFat = 0;
    logs.forEach(log => {
        totalCal += log.calories || 0;
        totalPro += log.protein || 0;
        totalCarbs += log.carbs || 0;
        totalFat += log.fat || 0;
    });

    // Helper for progress bars
    const getProgress = (current, target) => {
        if (!target) return 0;
        return Math.min(100, Math.round((current / target) * 100));
    };

    const calProgress = getProgress(totalCal, targets.calories);
    const proProgress = getProgress(totalPro, targets.protein);
    const carbProgress = getProgress(totalCarbs, targets.carbs);
    const fatProgress = getProgress(totalFat, targets.fat);

    window._currentNutritionTargets = { ...targets };

    const getInlineTarget = (type, val) => `<span class="macro-target-val">${val}</span>`;

    let html = `
        <div class="nutrition-dashboard">
            <div style="display: flex; justify-content: flex-end; margin-bottom: 20px;">
                <div class="custom-date-picker-wrapper">
                    <label style="position: relative; padding: 8px 16px; font-size: 13px; font-weight: 600; border-radius: 20px; border: 1px solid var(--border-light); background: var(--bg-secondary); color: var(--text-main); display: flex; align-items: center; gap: 8px; cursor: pointer; transition: all 0.2s;" onclick="const inp = this.querySelector('input'); if(inp.showPicker) inp.showPicker(); else inp.click();">
                        <i data-feather="calendar" style="width: 14px; height: 14px;"></i>
                        <span id="nutrition-date-display">${formatDateDDMMYYYY(currentDate)}</span>
                        <input type="date" value="${convertToISO(currentDate)}" 
                               style="position: absolute; width:0; height:0; opacity:0; pointer-events:none;"
                               onclick="event.stopPropagation()"
                               onchange="window.currentNutritionDate = this.value; loadData('nutrition');">
                    </label>
                </div>
            </div>
            <div class="macro-summary-cards">
                <!-- Calories -->
                <div class="macro-card">
                    <div class="macro-title">Calories</div>
                    <div class="macro-val">${Math.round(totalCal)} <span class="macro-target" style="transition: color 0.3s;" id="target-cal-display">/ ${Math.round(targets.calories || 1985)} kcal</span></div>
                    <div class="macro-progress-bg">
                        <div class="macro-progress-fill cal-fill" style="width: ${calProgress}%;"></div>
                    </div>
                </div>
                
                <!-- Protein -->
                <div class="macro-card">
                    <div class="macro-title">Protein</div>
                    <div class="macro-val">${Math.round(totalPro)}g <span class="macro-target">/ ${getInlineTarget('protein', targets.protein || 150)}g</span></div>
                    <div class="macro-progress-bg">
                        <div class="macro-progress-fill pro-fill" style="width: ${proProgress}%;"></div>
                    </div>
                </div>

                <!-- Carbs -->
                <div class="macro-card">
                    <div class="macro-title">Carbs</div>
                    <div class="macro-val">${Math.round(totalCarbs)}g <span class="macro-target">/ ${getInlineTarget('carbs', targets.carbs || 200)}g</span></div>
                    <div class="macro-progress-bg">
                        <div class="macro-progress-fill carb-fill" style="width: ${carbProgress}%;"></div>
                    </div>
                </div>

                <!-- Fat -->
                <div class="macro-card">
                    <div class="macro-title">Fat</div>
                    <div class="macro-val">${Math.round(totalFat)}g <span class="macro-target">/ ${getInlineTarget('fat', targets.fat || 65)}g</span></div>
                    <div class="macro-progress-bg">
                        <div class="macro-progress-fill fat-fill" style="width: ${fatProgress}%;"></div>
                    </div>
                </div>
            </div>

            <div class="nutrition-logs-section" style="margin-top: 32px;">
                <div class="flex-between mb-4">
                    <h3 class="section-title" style="margin: 0;">Food Log</h3>
                </div>
                
                <div class="quick-add-container" style="margin-bottom: 16px;">
                    <div class="quick-add-wrapper">
                        <i data-feather="plus" class="quick-add-icon"></i>
                        <input type="text" id="food-input" class="quick-add-input" placeholder="What did you eat? (e.g., 2 eggs and a bagel)" onkeypress="handleFoodInput(event)" />
                    </div>
                </div>
                
                <div class="data-list" style="margin-top: 16px; width: 100%;">
    `;

    if (logs.length === 0) {
        html += `<div class="empty-state" style="text-align: center; padding: 24px; color: var(--text-muted);">No food logged today. Describe what you ate!</div>`;
    } else {
        html += `
                    <div style="display: flex; justify-content: space-between; padding: 0 12px 8px; font-size: 12px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                        <span style="flex: 1;">Food Item</span>
                        <div style="display: flex; gap: 16px; align-items: center; width: 340px;">
                            <span style="width: 60px; text-align: center;">P</span>
                            <span style="width: 60px; text-align: center;">C</span>
                            <span style="width: 60px; text-align: center;">F</span>
                            <span style="width: 60px; text-align: right;">Kcal</span>
                            <span style="width: 50px;"></span>
                        </div>
                    </div>
        `;
        logs.forEach(log => {
            html += `
                <!-- Display Row -->
                <div id="food-row-${log.id}" class="data-item food-item" style="padding: 12px; border-radius: 8px; margin-bottom: 4px; display: flex; align-items: center; justify-content: space-between; border: 1px solid var(--border-light);">
                    <div style="flex: 1; display: flex; align-items: center;">
                        <span style="font-weight: 600; color: var(--text-main);">${log.quantity || ''} ${log.name}</span>
                    </div>
                    <div style="display: flex; gap: 16px; align-items: center; width: 340px;">
                        <span style="background: rgba(var(--primary-rgb), 0.08); color: var(--text-main); padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; width: 60px; text-align: center; display: inline-block;">${Math.round(log.protein)}</span>
                        <span style="background: rgba(var(--primary-rgb), 0.08); color: var(--text-main); padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; width: 60px; text-align: center; display: inline-block;">${Math.round(log.carbs)}</span>
                        <span style="background: rgba(var(--primary-rgb), 0.08); color: var(--text-main); padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; width: 60px; text-align: center; display: inline-block;">${Math.round(log.fat)}</span>
                        <span style="font-weight: 600; width: 60px; text-align: right;">${Math.round(log.calories)}</span>
                        <div style="display: flex; justify-content: flex-end; gap: 4px; width: 50px;">
                            <button class="icon-btn edit-btn" onclick="toggleEditFoodLog(${log.id})" title="Edit Log" style="background: transparent; border: none; box-shadow: none; padding: 4px;">
                                <i data-feather="edit-2" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                            </button>
                            <button class="icon-btn delete-btn" onclick="event.stopPropagation(); window.confirmInlineDelete(this, 'food', ${log.id})" title="Remove Log" style="background: transparent; border: none; box-shadow: none; padding: 4px;">
                                <i data-feather="trash-2" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Edit Row -->
                <div id="food-edit-${log.id}" class="data-item food-item food-edit" style="display: none; padding: 12px; border-radius: 8px; margin-bottom: 4px; border: 1px solid var(--border-light); background: var(--bg-secondary); align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
                    <div style="flex: 1; display: flex; gap: 8px; min-width: 200px;">
                        <input type="text" id="edit-food-qty-${log.id}" class="notion-input" value="${escapeQuote(log.quantity)}" placeholder="Qty" style="width: 60px; padding: 6px; font-size: 13px;">
                        <input type="text" id="edit-food-name-${log.id}" class="notion-input" value="${escapeQuote(log.name)}" placeholder="Food name" style="flex: 1; padding: 6px; font-size: 13px;">
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                        <input type="number" id="edit-food-p-${log.id}" class="notion-input" value="${log.protein}" placeholder="P" style="width: 60px; padding: 6px; font-size: 13px; text-align: center;">
                        <input type="number" id="edit-food-c-${log.id}" class="notion-input" value="${log.carbs}" placeholder="C" style="width: 60px; padding: 6px; font-size: 13px; text-align: center;">
                        <input type="number" id="edit-food-f-${log.id}" class="notion-input" value="${log.fat}" placeholder="F" style="width: 60px; padding: 6px; font-size: 13px; text-align: center;">
                        <input type="number" id="edit-food-cal-${log.id}" class="notion-input" value="${log.calories}" placeholder="Kcal" style="width: 65px; text-align: right; padding: 6px; font-size: 13px;">
                        <div style="display: flex; gap: 4px; margin-left: 4px;">
                            <button class="icon-btn" onclick="submitInlineEditFoodLog(${log.id})" title="Save" style="background: var(--success); color: white; border: none; padding: 4px; border-radius: 4px;">
                                <i data-feather="check" style="width: 14px; height: 14px;"></i>
                            </button>
                            <button class="icon-btn" onclick="toggleEditFoodLog(${log.id})" title="Cancel" style="background: transparent; border: none; box-shadow: none; padding: 4px;">
                                <i data-feather="x" style="width: 14px; height: 14px; color: var(--text-muted);"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    html += `
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
    if (window.feather) {
        try {
            feather.replace();
        } catch (e) {
            console.error('Feather Error:', e);
        }
    }

    // Render Macro Donut Chart
    if (window.macroChartInst) window.macroChartInst.destroy();
    const ctx = document.getElementById('macro-donut-chart');
    if (ctx && typeof Chart !== 'undefined') {
        const p = targets.protein || 150;
        const c = targets.carbs || 215;
        const f = targets.fat || 60;

        window.macroChartInst = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Protein', 'Carbs', 'Fat'],
                datasets: [{
                    data: [p * 4, c * 4, f * 9], // Scaled by caloric contribution
                    backgroundColor: ['#2eaadc', '#6ee7b7', '#fbcfe8'],
                    borderWidth: 0,
                    hoverOffset: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '75%',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                return `${label}: ${Math.round(value)} kcal`;
                            }
                        }
                    }
                }
            }
        });
    }
}


window.handleFoodInput = async function (e) {
    if (e.key === 'Enter') {
        const val = e.target.value.trim();
        if (!val) return;

        e.target.value = '';
        e.target.placeholder = "Processing...";
        e.target.disabled = true;
        showToast("Analyzing food input...");

        try {
            const d = window.currentNutritionDate || getLocalDateISO();
            const res = await fetch('/api/food/logs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: val, date: formatDateDDMMYYYY(d) })
            });

            if (res.ok) {
                showToast("Food logged successfully!");
                loadData('nutrition');
            } else {
                const data = await res.json();
                showToast(data.detail || "Failed to log food", true);
            }
        } catch (err) {
            console.error("Error logging food:", err);
            showToast("Failed to connect to API", true);
        } finally {
            e.target.placeholder = "What did you eat? (e.g., 2 eggs and a bagel)";
            e.target.disabled = false;
            e.target.focus();
        }
    }
};

let currentEditingFoodLogId = null;


window.toggleEditFoodLog = function (id) {
    const displayRow = document.getElementById(`food-row-${id}`);
    const editRow = document.getElementById(`food-edit-${id}`);

    if (displayRow.style.display === 'none') {
        displayRow.style.display = 'flex';
        editRow.style.display = 'none';
        currentEditingFoodLogId = null;
    } else {
        displayRow.style.display = 'none';
        editRow.style.display = 'flex';
        currentEditingFoodLogId = id;
    }
};

window.submitInlineEditFoodLog = async function (id) {
    const name = document.getElementById(`edit-food-name-${id}`).value.trim();
    const quantity = document.getElementById(`edit-food-qty-${id}`).value.trim();
    const protein = parseFloat(document.getElementById(`edit-food-p-${id}`).value);
    const carbs = parseFloat(document.getElementById(`edit-food-c-${id}`).value);
    const fat = parseFloat(document.getElementById(`edit-food-f-${id}`).value);
    const calories = parseInt(document.getElementById(`edit-food-cal-${id}`).value);

    if (!name) {
        showToast("Food name is required", true);
        return;
    }

    try {
        const res = await fetch(`/api/food/logs/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, quantity, protein, carbs, fat, calories })
        });

        if (res.ok) {
            showToast("Food log updated");
            loadData('nutrition');
        } else {
            const d = await res.json();
            showToast(d.detail || "Failed to update food log", true);
        }
    } catch (e) {
        console.error(e);
        showToast("Error updating food log", true);
    }
};

// --- Macro Targets LLM API ---
window.generateMacrosFromProfile = async function () {
    const input = document.getElementById('macro-profile-input');
    const val = input.value.trim();
    if (!val) {
        showToast("Please describe your profile first", true);
        return;
    }

    document.getElementById('macro-gen-loader').style.display = 'flex';
    input.disabled = true;

    try {
        const res = await fetch('/api/food/generate_targets', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ profile_text: val })
        });
        if (res.ok) {
            showToast("Macros optimized successfully!");
            loadData(window.currentView || 'nutrition');
        } else {
            showToast("Failed to generate macros", true);
        }
    } catch {
        showToast("Network error", true);
    } finally {
        const loader = document.getElementById('macro-gen-loader');
        if (loader) loader.style.display = 'none';
        input.disabled = false;
    }
};

// Finance Transaction Add Methods
window.handleFinanceInput = async function (e) {
    if (e.key === 'Enter') {
        const val = e.target.value.trim();
        if (!val) return;

        const dateInputElem = document.getElementById('finance-date-input');
        const selectedDate = dateInputElem ? dateInputElem.value : formatDateDDMMYYYY(getLocalDateISO());

        e.target.value = '';
        e.target.placeholder = "Processing...";
        e.target.disabled = true;
        showToast("Analyzing finance input...");

        try {
            const res = await fetch('/api/finance/transactions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: val, date_logged: formatDateDDMMYYYY(selectedDate) })
            });

            if (res.ok) {
                showToast("Transaction logged successfully!");
                loadData('finance');
            } else {
                const data = await res.json();
                showToast(data.detail || "Failed to log transaction", true);
            }
        } catch (err) {
            console.error("Error logging transaction:", err);
            showToast("Failed to connect to API", true);
        } finally {
            e.target.placeholder = "What did you spend? (e.g., uber 200, dosa 150)";
            e.target.disabled = false;
            e.target.focus();
        }
    }
};

let currentEditingTransactionId = null;

window.toggleCategoriesPanel = function () {
    const panel = document.getElementById('finance-categories-panel');
    const grid = document.getElementById('finance-grid-container');
    if (panel && grid) {
        if (panel.style.display === 'none') {
            panel.style.display = 'block';
            grid.style.gridTemplateColumns = '1fr 0.5fr';
        } else {
            panel.style.display = 'none';
            grid.style.gridTemplateColumns = '1fr';
        }
    }
};

window.toggleDetailsVisibility = function (id) {
    const detailsSpan = document.getElementById(`trans-details-${id}`);
    if (detailsSpan) {
        if (detailsSpan.style.display === 'none') {
            detailsSpan.style.display = 'inline-flex';
        } else {
            detailsSpan.style.display = 'none';
        }
    }
};

window.toggleEditTransaction = function (id) {
    const displayRow = document.getElementById(`trans-row-${id}`);
    const editRow = document.getElementById(`trans-edit-${id}`);

    if (displayRow.style.display === 'none') {
        displayRow.style.display = 'flex';
        editRow.style.display = 'none';
        currentEditingTransactionId = null;
    } else {
        // Reset previously editing row if exists
        if (currentEditingTransactionId && currentEditingTransactionId !== id) {
            const prevDisplayRow = document.getElementById(`trans-row-${currentEditingTransactionId}`);
            const prevEditRow = document.getElementById(`trans-edit-${currentEditingTransactionId}`);
            if (prevDisplayRow && prevEditRow) {
                prevDisplayRow.style.display = 'flex';
                prevEditRow.style.display = 'none';
            }
        }

        displayRow.style.display = 'none';
        editRow.style.display = 'flex';
        currentEditingTransactionId = id;
    }
};

window.submitInlineEdit = async function (id) {
    const descField = document.getElementById(`edit-desc-${id}`);
    const catField = document.getElementById(`edit-cat-${id}`);
    const amountField = document.getElementById(`edit-amount-${id}`);
    const dateField = document.getElementById(`edit-date-${id}`);

    const desc = descField.value.trim();
    const catId = catField.value;
    const amountStr = amountField.value;
    const dateStr = dateField ? dateField.value : null;

    if (!amountStr || !catId || parseFloat(amountStr) <= 0) {
        showToast("Valid amount and category are required", true);
        return;
    }

    try {
        const payload = {
            amount: parseFloat(amountStr),
            category_id: parseInt(catId),
            description: desc
        };
        if (dateStr) payload.date_logged = formatDateDDMMYYYY(dateStr);

        const res = await fetch(`/api/finance/transactions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            showToast("Transaction updated!");
            loadData('finance'); // Reload to update table
        } else {
            const data = await res.json();
            showToast(data.detail || "Failed to update transaction", true);
        }
    } catch (err) {
        console.error("Error updating transaction:", err);
        showToast("Failed to connect to API", true);
    }
};

// --- Settings Page Rendering ---
function renderSettings(container) {
    if (!container) return;

    let html = `
        <div class="command-center">
            <!-- Pulse Bar -->
            <div class="pulse-bar">
                <div class="pulse-item">
                    <span class="pulse-dot"></span>
                    <span class="pulse-label">AI HITS</span>
                    <span class="pulse-value" id="stats-calls">--</span>
                </div>
                <div class="pulse-divider"></div>
                <div class="pulse-item">
                    <span class="pulse-label">TOKENS</span>
                    <span class="pulse-value" id="stats-tokens">--</span>
                </div>
            </div>

            <div class="command-stack compact">
                <!-- About Card -->
                <div class="command-card compact">
                    <div class="card-header mini">
                        <div class="header-main">
                            <i data-feather="user"></i>
                            <h3>About</h3>
                        </div>
                    </div>
                    <div class="card-body mini">
                        <div class="compact-input-wrapper">
                            <textarea id="user-description" placeholder="Who are you? Goals?" class="command-input mini"></textarea>
                            <button id="save-description" class="arrow-submit-btn">
                                <i data-feather="arrow-right"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Macros Card -->
                <div class="command-card compact">
                    <div class="card-header mini">
                        <div class="header-main">
                            <i data-feather="zap"></i>
                            <h3>Macros</h3>
                        </div>
                    </div>
                    <div class="card-body mini">
                        <div class="compact-input-wrapper">
                            <textarea id="macro-profile-input" placeholder="Age, weight, height..." class="command-input mini"></textarea>
                            <div class="macro-actions-group">
                                <div id="macro-gen-loader" class="command-loader mini" style="display: none;">
                                    <i data-feather="loader" class="spin"></i>
                                </div>
                                <button class="arrow-submit-btn" onclick="generateMacrosFromProfile()">
                                    <i data-feather="arrow-right"></i>
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Exercise Master List Card -->
                <div class="command-card compact">
                    <div class="card-header mini">
                        <div class="header-main">
                            <i data-feather="heart"></i>
                            <h3>Exercise Master List</h3>
                        </div>
                    </div>
                    <div class="card-body mini">
                        <div id="exercise-master-container" style="display: flex; flex-wrap: wrap; gap: 8px; max-height: 200px; overflow-y: auto; padding: 4px;">
                            <div class="loading-state mini">Loading...</div>
                        </div>
                    </div>
                </div>

                <!-- User Profile Card -->
                <div class="command-card compact">
                    <div class="card-header mini">
                        <div class="header-main">
                            <i data-feather="user-check"></i>
                            <h3>User Profile (JSON)</h3>
                        </div>
                    </div>
                    <div class="card-body mini">
                        <div class="compact-input-wrapper">
                            <textarea id="profile-json-textarea" class="command-input mini" style="height: 180px; font-family: monospace; font-size: 12px;" placeholder="User profile JSON..."></textarea>
                            <button id="save-profile-btn" class="arrow-submit-btn">
                                <i data-feather="arrow-right"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Cover Letter Card -->
                <div class="command-card compact">
                    <div class="card-header mini">
                        <div class="header-main">
                            <i data-feather="mail"></i>
                            <h3>Cover Letter Template</h3>
                        </div>
                    </div>
                    <div class="card-body mini">
                        <div class="compact-input-wrapper">
                            <textarea id="profile-cover-letter" class="command-input mini" style="height: 180px; font-family: monospace; font-size: 12px;" placeholder="Your default cover letter template..."></textarea>
                            <button id="save-cover-letter-btn" class="arrow-submit-btn">
                                <i data-feather="arrow-right"></i>
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Google Authorization Card -->
                <div class="command-card compact">
                    <div class="card-header mini">
                        <div class="header-main">
                            <i data-feather="globe"></i>
                            <h3>Google Integration</h3>
                        </div>
                    </div>
                    <div class="card-body mini" style="padding: 16px;" id="google-auth-container">
                        <div class="loading-state mini">Checking status...</div>
                    </div>
                </div>

                <!-- Reset System Card -->
                <div class="command-card compact" style="border: 1px solid #eb5757;">
                    <div class="card-body mini" style="padding: 16px; display: flex; flex-direction: column; gap: 12px;">
                        <button id="system-reset-btn" class="notion-button delete-btn" style="width: 100%; justify-content: center; background: #eb5757; color: white; border: none; font-weight: 600; padding: 10px; border-radius: 8px; cursor: pointer;">
                            Reset System Data
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;

    container.innerHTML = html;
    if (window.feather) feather.replace();

    // Render Consumption Stats
    const fetchStats = async () => {
        try {
            const statsRes = await fetchApi('llm/stats');
            if (statsRes) {
                const callsEl = document.getElementById('stats-calls');
                const tokensEl = document.getElementById('stats-tokens');
                
                if (callsEl) callsEl.textContent = statsRes.total_calls.toLocaleString();
                if (tokensEl) tokensEl.textContent = statsRes.total_all.toLocaleString();
            }
        } catch (err) {
            console.error("Stats Error:", err);
        }
    };
    fetchStats();

    // Fetch Workout Master List
    const fetchMasterExercises = async () => {
        try {
            const masterRes = await fetchApi('workouts/master');
            const masterContainer = document.getElementById('exercise-master-container');
            if (masterRes && masterContainer) {
                const exercises = masterRes.exercises || [];
                if (exercises.length === 0) {
                    masterContainer.innerHTML = '<div class="empty-state mini" style="font-size: 12px; color: var(--text-muted);">No exercises recorded yet.</div>';
                } else {
                    masterContainer.innerHTML = exercises.map(ex => `
                        <span class="filter-pill" style="font-size: 11px; padding: 4px 10px; cursor: default; background: var(--bg-secondary); border: 1px solid var(--border-light); border-radius: 20px; color: var(--text-main); font-weight: 500;">
                            ${ex}
                        </span>
                    `).join('');
                }
            }
        } catch (err) {
            console.error("Master Exercises Error:", err);
        }
    };
    fetchMasterExercises();

    // Profile Logic
    const saveBtn = document.getElementById('save-description');
    const textarea = document.getElementById('user-description');
    if (saveBtn && textarea) {
        saveBtn.addEventListener('click', async () => {
            const description = textarea.value.trim();
            if (!description) return;

            saveBtn.disabled = true;
            const originalText = saveBtn.innerHTML;
            saveBtn.innerHTML = '<i data-feather="loader" class="spin" style="width: 14px;"></i> Extracting...';
            if (window.feather) feather.replace();

            try {
                const res = await fetch('/api/user/describe', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ description })
                });
                const data = await res.json();
                if (data.success) {
                    textarea.value = '';
                    window.showToast(`Extracted ${data.facts_extracted} facts!`);
                }
            } catch (e) {
                console.error('Failed to save description', e);
                window.showToast("Failed to extract facts", true);
            } finally {
                saveBtn.disabled = false;
                saveBtn.innerHTML = originalText;
                if (window.feather) feather.replace();
            }
        });
    }

    // Fetch and populate User Profile
    const fetchUserProfile = async () => {
        try {
            const profile = await fetchApi('user/profile');
            if (profile && Object.keys(profile).length > 0) {
                document.getElementById('profile-json-textarea').value = JSON.stringify(profile, null, 2);
            }
        } catch (err) {
            console.error("Profile Fetch Error:", err);
        }
    };
    fetchUserProfile();

    // Fetch and populate Cover Letter
    const fetchCoverLetter = async () => {
        try {
            const data = await fetchApi('user/cover-letter');
            if (data) {
                document.getElementById('profile-cover-letter').value = data.cover_letter || '';
            }
        } catch (err) {
            console.error("Cover Letter Fetch Error:", err);
        }
    };
    fetchCoverLetter();

    // Fetch and populate Google OAuth status
    const fetchGoogleStatus = async () => {
        try {
            const res = await fetch('/api/google/status');
            const data = await res.json();
            const containerEl = document.getElementById('google-auth-container');
            if (!containerEl) return;

            // Helper: wire up a file input to upload credentials.json then redirect to auth
            const wireUpload = (btnOrLink, fileInput, isLink) => {
                if (!btnOrLink || !fileInput) return;
                btnOrLink.addEventListener('click', (e) => { if (isLink) e.preventDefault(); fileInput.click(); });
                fileInput.addEventListener('change', async () => {
                    if (!fileInput.files.length) return;
                    const fd = new FormData();
                    fd.append('file', fileInput.files[0]);
                    try {
                        showToast("Uploading credentials...");
                        const r = await fetch('/api/google/credentials', { method: 'POST', body: fd });
                        const d = await r.json();
                        if (r.ok && d.success) {
                            showToast("Credentials saved! Redirecting...");
                            setTimeout(() => { window.location.href = '/api/google/auth'; }, 800);
                        } else {
                            showToast(d.detail || "Upload failed", true);
                        }
                    } catch (err) { showToast("Upload error", true); }
                });
            };

            if (!data.credentials_valid) {
                // State 1: No valid credentials — show upload
                containerEl.innerHTML = `
                    <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">
                        Upload your Google OAuth <strong>credentials.json</strong> to enable Gmail & Calendar.
                    </div>
                    <input type="file" id="google-creds-file" accept=".json" style="display: none;">
                    <button id="google-upload-btn" class="notion-button primary" style="width: 100%; justify-content: center; font-weight: 600; padding: 10px; border-radius: 8px; cursor: pointer;">
                        Upload credentials.json
                    </button>
                `;
                wireUpload(document.getElementById('google-upload-btn'), document.getElementById('google-creds-file'), false);

            } else if (!data.authenticated) {
                // State 2: Credentials exist but not authorized — show connect
                containerEl.innerHTML = `
                    <button id="google-auth-btn" class="notion-button primary" style="width: 100%; justify-content: center; font-weight: 600; padding: 10px; border-radius: 8px; cursor: pointer; margin-bottom: 6px;">
                        Connect Google Account
                    </button>
                    <div style="text-align: center;">
                        <a href="#" id="google-change-creds" style="font-size: 11px; color: var(--text-muted); text-decoration: underline;">Re-upload credentials.json</a>
                    </div>
                    <input type="file" id="google-creds-file" accept=".json" style="display: none;">
                `;
                document.getElementById('google-auth-btn').addEventListener('click', () => { window.location.href = '/api/google/auth'; });
                wireUpload(document.getElementById('google-change-creds'), document.getElementById('google-creds-file'), true);

            } else {
                // State 3: Fully connected
                containerEl.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 10px; font-size: 13px; color: #2ecc71; font-weight: 600;">
                        <i data-feather="check-circle" style="width: 16px; height: 16px;"></i> Google account connected
                    </div>
                    <button id="google-disconnect-btn" class="notion-button" style="width: 100%; justify-content: center; font-weight: 500; padding: 8px; border-radius: 8px; cursor: pointer; font-size: 12px; background: transparent; border: 1px solid #eb5757; color: #eb5757;">
                        Disconnect
                    </button>
                `;
                if (window.feather) feather.replace();
                document.getElementById('google-disconnect-btn').addEventListener('click', async () => {
                    const confirmed = await showConfirmModal("Disconnect Google?", "This will revoke access. You'll need to re-authorize.");
                    if (!confirmed) return;
                    try {
                        const r = await fetch('/api/google/disconnect', { method: 'POST' });
                        const d = await r.json();
                        if (d.success) { showToast("Disconnected."); fetchGoogleStatus(); }
                        else { showToast(d.message || "Failed", true); }
                    } catch { showToast("Failed to disconnect", true); }
                });
            }
        } catch (err) {
            console.error("Google Auth Status Error:", err);
        }
    };
    fetchGoogleStatus();

    // Save User Profile Event Listener
    const saveProfileBtn = document.getElementById('save-profile-btn');
    if (saveProfileBtn) {
        saveProfileBtn.addEventListener('click', async () => {
            const jsonStr = document.getElementById('profile-json-textarea').value.trim();
            if (!jsonStr) {
                showToast("Profile JSON cannot be empty.", true);
                return;
            }

            let profileData;
            try {
                profileData = JSON.parse(jsonStr);
            } catch (e) {
                showToast("Invalid JSON format. Please check syntax.", true);
                return;
            }

            // Simple validation of required fields
            const required = ['current_role', 'experience_level', 'experience_years', 'skills', 'industry', 'domain', 'example_type'];
            for (const field of required) {
                if (profileData[field] === undefined) {
                    showToast(`Missing required field: ${field}`, true);
                    return;
                }
            }

            saveProfileBtn.disabled = true;
            const originalTextProfile = saveProfileBtn.innerHTML;
            saveProfileBtn.innerHTML = '<i data-feather="loader" class="spin" style="width: 14px; height: 14px;"></i>';
            if (window.feather) feather.replace();

            try {
                const res = await fetch('/api/user/profile', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(profileData)
                });
                if (res.ok) {
                    showToast("User Profile saved successfully!");
                } else {
                    showToast("Failed to save User Profile", true);
                }
            } catch (err) {
                console.error("Save Profile Error:", err);
                showToast("Error connecting to API", true);
            } finally {
                saveProfileBtn.disabled = false;
                saveProfileBtn.innerHTML = originalTextProfile;
                if (window.feather) feather.replace();
            }
        });
    }

    // Save Cover Letter Event Listener
    const saveCoverLetterBtn = document.getElementById('save-cover-letter-btn');
    if (saveCoverLetterBtn) {
        saveCoverLetterBtn.addEventListener('click', async () => {
            const cover_letter = document.getElementById('profile-cover-letter').value;

            saveCoverLetterBtn.disabled = true;
            const originalTextCover = saveCoverLetterBtn.innerHTML;
            saveCoverLetterBtn.innerHTML = '<i data-feather="loader" class="spin" style="width: 14px; height: 14px;"></i>';
            if (window.feather) feather.replace();

            try {
                const res = await fetch('/api/user/cover-letter', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cover_letter })
                });
                if (res.ok) {
                    showToast("Cover Letter saved successfully!");
                } else {
                    showToast("Failed to save Cover Letter", true);
                }
            } catch (err) {
                console.error("Save Cover Letter Error:", err);
                showToast("Error connecting to API", true);
            } finally {
                saveCoverLetterBtn.disabled = false;
                saveCoverLetterBtn.innerHTML = originalTextCover;
                if (window.feather) feather.replace();
            }
        });
    }

    // System Reset Logic
    const resetBtn = document.getElementById('system-reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', async () => {
            const confirmed = await showConfirmModal(
                "Reset System Data?",
                "Are you absolutely sure you want to permanently delete all resumes, learning profile, chat history, trackers, nutrition records, finances, and reminders? This cannot be undone."
            );
            if (!confirmed) return;

            resetBtn.disabled = true;
            resetBtn.textContent = "Resetting...";

            try {
                const res = await fetch('/api/system/reset', { method: 'POST' });
                if (res.ok) {
                    const data = await res.json();
                    showToast(data.message || "System reset successfully!");
                    setTimeout(() => {
                        window.location.reload();
                    }, 2000);
                } else {
                    const data = await res.json();
                    showToast(data.detail || "Failed to reset system", true);
                }
            } catch (e) {
                console.error("Reset error:", e);
                showToast("Error resetting system data", true);
            } finally {
                resetBtn.disabled = false;
                resetBtn.textContent = "Reset System Data";
            }
        });
    }
}

// --- Calendar Rendering ---
function renderCalendar(events, container) {
    container.innerHTML = `
        <div class="quick-add-section" style="margin-bottom: 32px;">
            <div class="quick-add-container">
                <div class="quick-add-wrapper">
                    <i data-feather="calendar" class="quick-add-icon"></i>
                    <input type="text" id="calendar-quick-add" class="quick-add-input" placeholder="Quick add: 'Dinner at 8pm tomorrow'" />
                    <span class="quick-add-hint">Press Enter ↵</span>
                </div>
            </div>
        </div>

        <div class="data-list" id="calendar-list"></div>
    `;

    const list = container.querySelector('#calendar-list');
    const quickAddInput = container.querySelector('#calendar-quick-add');

    quickAddInput.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter' && quickAddInput.value.trim()) {
            const res = await fetchApi('calendar/quick-add', {
                method: 'POST',
                body: JSON.stringify({ text: quickAddInput.value.trim() })
            });
            if (res && res.success) {
                showToast(`Event added: ${res.event.summary}`);
                loadData('calendar');
            }
        }
    });

    if (events.length === 0) {
        list.innerHTML = '<div class="empty-state">No upcoming events found.</div>';
    } else {
        events.forEach(e => {
            const item = document.createElement('div');
            item.className = 'data-item calendar-item';
            
            const startStr = e.start.dateTime || e.start.date;
            const d = new Date(startStr);
            const timeStr = e.start.dateTime ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'All Day';
            const dateStr = d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });

            item.innerHTML = `
                <div class="calendar-date-badge">
                    <span class="day">${d.getDate()}</span>
                    <span class="month">${d.toLocaleDateString([], { month: 'short' }).toUpperCase()}</span>
                </div>
                <div class="calendar-content">
                    <div class="calendar-summary">${e.summary}</div>
                    <div class="calendar-meta">
                        <span><i data-feather="clock" style="width: 12px;"></i> ${timeStr}</span>
                        ${e.location ? `<span><i data-feather="map-pin" style="width: 12px;"></i> ${e.location}</span>` : ''}
                    </div>
                </div>
                ${e.eventType !== 'birthday' ? `
                <div class="delete-action" title="Delete Event" data-id="${e.id}">
                    <i data-feather="trash-2" style="width: 14px; height: 14px;"></i>
                </div>
                ` : ''}
            `;

            const deleteAction = item.querySelector('.delete-action');
            if (deleteAction) {
                deleteAction.addEventListener('click', (ev) => {
                    ev.preventDefault();
                    window.confirmInlineDelete(ev.currentTarget, 'calendar', e.id);
                });
            }

            list.appendChild(item);
        });
    }

    if (window.feather) feather.replace();
}

