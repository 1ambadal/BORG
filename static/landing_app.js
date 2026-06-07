document.addEventListener('DOMContentLoaded', () => {
    // Theme Management
    const themeToggle = document.getElementById('theme-toggle');
    const themeToggleIcon = document.getElementById('theme-toggle-icon');

    function setTheme(theme) {
        if (theme === 'dark') {
            document.body.classList.add('dark-mode');
            if (themeToggleIcon) themeToggleIcon.setAttribute('data-feather', 'sun');
        } else {
            document.body.classList.remove('dark-mode');
            if (themeToggleIcon) themeToggleIcon.setAttribute('data-feather', 'moon');
        }
        if (window.feather) feather.replace();
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

    updateGreeting();
    loadCommandCenterData();
    feather.replace();
});

function updateGreeting() {
    const greetingEl = document.getElementById('greeting-text');
    const dateEl = document.getElementById('current-date');

    if (!greetingEl || !dateEl) return;

    const hour = new Date().getHours();
    let greeting = 'Good evening';
    if (hour < 12) greeting = 'Good morning';
    else if (hour < 18) greeting = 'Good afternoon';

    // User requested "remove workspace"
    greetingEl.textContent = `${greeting}.`;

    const options = { weekday: 'long', month: 'long', day: 'numeric' };
    dateEl.textContent = new Date().toLocaleDateString('en-US', options);
}

window.glanceData = {
    todos: null,
    events: null,
    macros: null
};

async function loadCommandCenterData() {
    const strip = document.getElementById('at-a-glance-strip');
    if (!strip) return;

    // 1. Load Todos
    try {
        const res = await fetch('/api/todos');
        const { todos } = await res.json();
        window.glanceData.todos = todos;
        refreshGlance();
    } catch (e) { console.error('Failed to load todos', e); }

    // 2. Load Calendar Events
    try {
        const res = await fetch('/api/calendar/events');
        const { events } = await res.json();
        window.glanceData.events = events;
        refreshGlance();
    } catch (e) { console.error('Failed to load events', e); }

    // 3. Load Nutrition Data
    try {
        const res = await fetch('/api/food/logs');
        const { logs } = await res.json();
        window.glanceData.macros = logs;
        refreshGlance();
    } catch (e) { console.error('Failed to load nutrition data', e); }

    refreshGlance();
}

function refreshGlance() {
    const strip = document.getElementById('at-a-glance-strip');
    if (!strip) return;

    const sections = [];

    // 1. Upcoming Events
    if (window.glanceData.events) {
        const content = window.glanceData.events.length > 0 
            ? window.glanceData.events.slice(0, 3).map(e => {
                const start = e.start?.dateTime || e.start?.date;
                const time = e.start?.dateTime 
                    ? new Date(e.start.dateTime).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }).toLowerCase()
                    : 'all day';
                const loc = e.location ? ` @ ${e.location}` : '';
                // Add relative day if not today
                const eventDate = new Date(start).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                const isToday = start && start.startsWith(new Date().toISOString().split('T')[0]);
                const dayLabel = isToday ? '' : `${eventDate}: `;
                
                return `&bull; ${dayLabel}${e.summary} (${time}${loc})`;
            }).join('<br>')
            : 'No upcoming events found.';
        sections.push(`
            <div class="glance-section section-events">
                <div class="glance-header"><i data-feather="calendar"></i> Upcoming Events</div>
                <div class="glance-content">${content}</div>
            </div>
        `);
    }

    // 2. Todos
    if (window.glanceData.todos) {
        const pending = window.glanceData.todos.filter(t => t.status !== 'completed');
        const content = pending.length > 0
            ? pending.slice(0, 3).map(t => t.task).join(', ')
            : 'All caught up!';
        sections.push(`
            <div class="glance-section section-todos">
                <div class="glance-header"><i data-feather="check-square"></i> Todo</div>
                <div class="glance-content">${content}</div>
            </div>
        `);
    }

    // 3. Macros
    if (window.glanceData.macros) {
        const totals = window.glanceData.macros.reduce((acc, item) => {
            acc.calories += (item.calories || 0);
            acc.protein += (item.protein || 0);
            acc.carbs += (item.carbs || 0);
            acc.fat += (item.fat || 0);
            return acc;
        }, { calories: 0, protein: 0, carbs: 0, fat: 0 });

        sections.push(`
            <div class="glance-section section-macros">
                <div class="glance-header"><i data-feather="activity"></i> Macros</div>
                <div class="glance-content">
                    ${totals.calories}kcal &bull; P ${totals.protein.toFixed(0)}g &bull; C ${totals.carbs.toFixed(0)}g &bull; F ${totals.fat.toFixed(0)}g
                </div>
            </div>
        `);
    }


    if (sections.length === 0 || window.glanceData.events === null) {
        strip.style.display = 'none';
        return;
    }

    strip.style.display = 'flex';
    strip.innerHTML = sections.join('');
    
    if (window.feather) {
        feather.replace();
    }
}

